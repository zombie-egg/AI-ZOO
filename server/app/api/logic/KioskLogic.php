<?php

namespace app\api\logic;

use app\common\enum\PayEnum;
use app\common\enum\user\UserTerminalEnum;
use app\common\logic\BaseLogic;
use app\common\logic\PaymentLogic;
use app\common\logic\PayNotifyLogic;
use app\common\model\kiosk\KioskOrder;
use app\common\model\kiosk\KioskParticipant;
use app\common\model\kiosk\KioskPhoto;
use app\common\model\kiosk\UnlockOrder;
use app\common\service\kiosk\KioskAuditService;
use app\common\service\kiosk\KioskImageForgeService;
use app\common\service\luna\LunaDrawService;
use think\facade\Db;

class KioskLogic extends BaseLogic
{
    /** Upload order is part of the GPT-image-2 prompt contract. Never sort alphabetically. */
    private const SHOT_TYPES = [
        'body_anchor',
        'front_smile',
        'left_three_quarter',
        'right_three_quarter',
    ];

    public static function scenes(): array
    {
        $catalog = (new KioskImageForgeService())->catalog();
        return [
            'scenes' => (array)($catalog['scenes'] ?? []),
            'poses' => (array)($catalog['poses'] ?? []),
        ];
    }

    /**
     * Return only historical kiosk outputs whose local print callback was done.
     * Generation URLs are freshly signed by ImageForge and no source/reference
     * photos are exposed.
     */
    public static function printedGallery(): array
    {
        $orders = KioskOrder::where('print_status', 'done')
            ->where('generation_id', '<>', '')
            ->where('status', '<>', 'deleted')
            ->order('id desc')
            ->limit(12)
            ->select();
        $items = [];
        $forge = new KioskImageForgeService();
        foreach ($orders as $order) {
            try {
                $state = $forge->generationStatus((string)$order->generation_id);
                $url = (string)($state['final_url'] ?? '');
                if ($url === '') continue;
                $items[] = [
                    'src' => $url,
                    'label' => (string)($order->scene_id ?: '已打印合照'),
                    'order_no' => (string)$order->order_no,
                    'printed_at' => (int)($order->update_time ?: $order->create_time ?: 0),
                ];
            } catch (\Throwable $ignored) {
                // A stale/expired generation must not prevent other history
                // from rendering.
            }
        }
        return ['photos' => $items];
    }

    public static function createOrder(array $params, int $userId = 0): array
    {
        $participantCount = (int)($params['participant_count'] ?? 1);
        if ($participantCount < 1 || $participantCount > 4) {
            throw new \RuntimeException('合照人数必须为 1 至 4 人');
        }
        $orderNo = 'K' . date('ymdHis') . strtoupper(substr(bin2hex(random_bytes(4)), 0, 5));
        Db::startTrans();
        try {
            $order = KioskOrder::create([
                'order_no' => $orderNo,
                'user_id' => $userId,
                'device_id' => substr((string)($params['device_id'] ?? 'kiosk-01'), 0, 64),
                'participant_count' => $participantCount,
                'status' => 'created',
                'expire_time' => time() + 86400,
            ]);
            for ($slot = 1; $slot <= $participantCount; $slot++) {
                KioskParticipant::create([
                    'kiosk_order_id' => $order->id,
                    'slot_no' => $slot,
                    'status' => 'pending',
                ]);
            }
            Db::commit();
        } catch (\Throwable $error) {
            Db::rollback();
            throw $error;
        }
        return ['id' => $order->id, 'order_no' => $orderNo, 'status' => 'created', 'participant_count' => $participantCount];
    }

    public static function recordConsent(int $id, array $params): array
    {
        $order = self::order($id);
        $slotNo = (int)($params['participant_no'] ?? 1);
        $participant = self::participant($id, $slotNo);
        $given = filter_var($params['consent_given'] ?? false, FILTER_VALIDATE_BOOLEAN);
        $minor = filter_var($params['minor_involved'] ?? false, FILTER_VALIDATE_BOOLEAN);
        $guardian = filter_var($params['guardian_confirmed'] ?? false, FILTER_VALIDATE_BOOLEAN);
        if (!$given || ($minor && !$guardian)) {
            throw new \RuntimeException('请完成本人授权；未成年人须由监护人确认');
        }
        $participant->save([
            'consent_given' => 1,
            'minor_involved' => $minor ? 1 : 0,
            'guardian_confirmed' => $guardian ? 1 : 0,
            'status' => 'consented',
        ]);
        $consentedCount = KioskParticipant::where(['kiosk_order_id' => $id, 'consent_given' => 1])->count();
        $allConsented = $consentedCount >= (int)$order->participant_count;
        $order->save([
            'consent_given' => $allConsented ? 1 : 0,
            'minor_involved' => KioskParticipant::where(['kiosk_order_id' => $id, 'minor_involved' => 1])->count() > 0 ? 1 : 0,
            'guardian_confirmed' => KioskParticipant::where(['kiosk_order_id' => $id, 'minor_involved' => 1, 'guardian_confirmed' => 0])->count() === 0 ? 1 : 0,
            'status' => $allConsented ? 'consented' : 'consenting',
        ]);
        KioskAuditService::record($order->order_no, 'consent', [
            'version' => $order->consent_version,
            'participant_no' => $slotNo,
            'minor' => $minor,
            'guardian_confirmed' => $guardian,
        ]);
        return ['consent_given' => true, 'participant_no' => $slotNo, 'consented_count' => $consentedCount, 'all_consented' => $allConsented];
    }

    public static function selectScene(int $id, string $sceneId): array
    {
        $order = self::order($id);
        if (!$order->consent_given) {
            throw new \RuntimeException('请先完成人脸信息授权');
        }
        $selected = null;
        foreach ((new KioskImageForgeService())->scenes() as $scene) {
            if ((string)($scene['scene_id'] ?? '') === $sceneId) {
                $selected = $scene;
                break;
            }
        }
        if (!$selected) {
            throw new \RuntimeException('所选文字场景不存在或尚未启用');
        }
        $order->save([
            'scene_id' => $sceneId,
            'pose_id' => '',
            'prompt_version' => (string)$selected['prompt_version'],
            'status' => 'scene_selected',
        ]);
        KioskAuditService::record($order->order_no, 'scene_selected', [
            'scene_id' => $sceneId,
            'prompt_version' => (string)$selected['prompt_version'],
        ]);
        return [
            'scene_id' => $sceneId,
            'title' => (string)$selected['title'],
            'prompt_version' => (string)$selected['prompt_version'],
        ];
    }

    public static function selectPose(int $id, string $poseId): array
    {
        $order = self::order($id);
        if (!$order->consent_given || !$order->scene_id) {
            throw new \RuntimeException('请先完成授权并选择文字场景');
        }
        $selected = null;
        foreach ((new KioskImageForgeService())->poses() as $pose) {
            if ((string)($pose['pose_id'] ?? '') === $poseId) {
                $selected = $pose;
                break;
            }
        }
        if (!$selected) {
            throw new \RuntimeException('所选人物姿势不存在或尚未启用');
        }
        $order->save([
            'pose_id' => $poseId,
            'status' => 'pose_selected',
        ]);
        KioskAuditService::record($order->order_no, 'pose_selected', [
            'scene_id' => (string)$order->scene_id,
            'pose_id' => $poseId,
            'pose_prompt_version' => (string)$selected['prompt_version'],
        ]);
        return [
            'pose_id' => $poseId,
            'title' => (string)$selected['title'],
            'prompt_version' => (string)$selected['prompt_version'],
        ];
    }

    public static function uploadPhoto(int $id, int $participantNo, string $shotType, $file): array
    {
        $order = self::order($id);
        $participant = self::participant($id, $participantNo);
        if (!$order->consent_given) {
            throw new \RuntimeException('尚未完成人脸授权');
        }
        if (!$order->scene_id) {
            throw new \RuntimeException('请先选择文字场景');
        }
        if (!$order->pose_id) {
            throw new \RuntimeException('请先选择人物姿势');
        }
        if (!in_array($shotType, self::SHOT_TYPES, true)) {
            throw new \RuntimeException('拍摄角度不在新版四连拍清单内');
        }
        if (!$file || $file->getSize() > 16 * 1024 * 1024) {
            throw new \RuntimeException('照片缺失或超过 16MB');
        }
        if (!in_array(strtolower((string)$file->getOriginalExtension()), ['jpg', 'jpeg', 'png', 'webp'], true)) {
            throw new \RuntimeException('只允许 JPG/PNG/WebP 照片');
        }

        $directory = runtime_path('kiosk-private/' . date('Y/m/d'));
        if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) {
            throw new \RuntimeException('照片私有目录创建失败');
        }
        $saved = $file->move($directory, bin2hex(random_bytes(18)) . '.jpg');
        $path = $saved->getPathname();
        $upstream = (new LunaDrawService())->uploadFile($path);
        $face = $upstream['fileFaceList'][0] ?? null;
        if (!$face) {
            @unlink($path);
            throw new \RuntimeException('没有检测到可用人脸，请重拍');
        }

        $old = KioskPhoto::where([
            'kiosk_order_id' => $id,
            'participant_id' => $participant->id,
            'shot_type' => $shotType,
        ])->findOrEmpty();
        $quality = is_array($upstream['quality'] ?? null) ? $upstream['quality'] : [
            'ok' => true,
            'face_count' => 1,
            'reasons' => [],
        ];
        $warnings = array_values(array_filter((array)($quality['reasons'] ?? [])));
        $values = [
            'private_path' => $path,
            'sha256' => hash_file('sha256', $path),
            'up_file_id' => (string)$upstream['id'],
            'up_face_id' => (string)$face['id'],
            'quality_passed' => 1,
            'quality_json' => json_encode(array_merge($quality, [
                'passed' => true,
                'source' => 'imageforge-capture-selection-only',
            ]), JSON_UNESCAPED_UNICODE),
        ];
        if ($old->isEmpty()) {
            KioskPhoto::create(array_merge($values, [
                'kiosk_order_id' => $id,
                'participant_id' => $participant->id,
                'shot_type' => $shotType,
            ]));
        } else {
            $oldPath = $old->private_path;
            $old->save($values);
            if ($oldPath && $oldPath !== $path && is_file($oldPath)) {
                @unlink($oldPath);
            }
        }
        $participantCount = KioskPhoto::where([
            'kiosk_order_id' => $id,
            'participant_id' => $participant->id,
            'quality_passed' => 1,
        ])->count();
        $participant->save(['status' => $participantCount >= 4 ? 'captured' : 'capturing']);
        $totalCount = KioskPhoto::where(['kiosk_order_id' => $id, 'quality_passed' => 1])->count();
        $expectedCount = (int)$order->participant_count * count(self::SHOT_TYPES);
        $order->save(['status' => $totalCount >= $expectedCount ? 'captured' : 'capturing']);
        return ['quality' => [
            'passed' => true,
            'score' => ((int)($quality['face_count'] ?? 0)) > 0 ? 0.90 : 0.72,
            'reason' => $warnings
                ? '照片已接收：' . implode('；', $warnings)
                : '清晰度与曝光可用',
        ], 'accepted_count' => $participantCount, 'total_accepted_count' => $totalCount];
    }

    public static function status(int $id): array
    {
        $order = self::order($id);
        $unlock = UnlockOrder::where('kiosk_order_id', $id)->order('id desc')->findOrEmpty();
        return [
            'order_no' => $order->order_no,
            'status' => $order->status,
            'scene_id' => $order->scene_id,
            'pose_id' => $order->pose_id,
            'participant_count' => (int)$order->participant_count,
            'captured_count' => KioskPhoto::where(['kiosk_order_id' => $id, 'quality_passed' => 1])->count(),
            'participants' => self::participantStatus($id),
            'unlock_status' => $unlock->isEmpty() ? 'unpaid' : $unlock->unlock_status,
            'generation_id' => (string)$order->generation_id,
            'print_status' => $order->print_status,
        ];
    }

    public static function createPayment(int $id, string $sku): array
    {
        $order = self::order($id);
        if ($order->status === 'deleted') {
            throw new \RuntimeException('订单已结束，无法创建支付');
        }
        $catalog = ['print_1' => 9.90, 'digital_only' => 9.90];
        if (!isset($catalog[$sku])) {
            throw new \RuntimeException('所选商品不存在');
        }
        $unlock = UnlockOrder::where(['kiosk_order_id' => $id, 'sku' => $sku])->findOrEmpty();
        if ($unlock->isEmpty()) {
            $unlock = UnlockOrder::create([
                'user_id' => $order->user_id,
                'kiosk_order_id' => $id,
                'sn' => 'U' . date('ymdHis') . strtoupper(substr(bin2hex(random_bytes(3)), 0, 5)),
                'terminal' => UserTerminalEnum::PC,
                'sku' => $sku,
                'order_amount' => $catalog[$sku],
                'pay_way' => PayEnum::WECHAT_PAY,
                'pay_status' => PayEnum::UNPAID,
            ]);
        }
        if ((int)$unlock->pay_status === PayEnum::ISPAID) {
            return [
                'paid' => true,
                'unlock_order_id' => $unlock->id,
                'amount' => $catalog[$sku],
                'currency' => 'CNY',
                'payment_mode' => self::paymentMode(),
            ];
        }
        if (self::paymentMode() === 'mock') {
            return [
                'paid' => false,
                'unlock_order_id' => $unlock->id,
                'code_url' => 'AI-ZOO-WECHAT-PAY-MOCK:' . $unlock->sn . ':CNY:9.90',
                'amount' => $catalog[$sku],
                'currency' => 'CNY',
                'payment_mode' => 'mock',
            ];
        }
        $payment = PaymentLogic::pay(PayEnum::WECHAT_PAY, 'unlock', $unlock->toArray(), UserTerminalEnum::PC, '');
        if ($payment === false) {
            throw new \RuntimeException(PaymentLogic::getError() ?: '微信支付下单失败');
        }
        return [
            'unlock_order_id' => $unlock->id,
            'code_url' => $payment['config'] ?? '',
            'amount' => $catalog[$sku],
            'currency' => 'CNY',
            'payment_mode' => 'wechat_native',
        ];
    }

    public static function simulatePayment(int $id): array
    {
        if (self::paymentMode() !== 'mock') {
            throw new \RuntimeException('正式微信支付模式不允许模拟到账');
        }
        self::order($id);
        $unlock = UnlockOrder::where('kiosk_order_id', $id)->order('id desc')->findOrEmpty();
        if ($unlock->isEmpty()) {
            throw new \RuntimeException('请先创建微信支付订单');
        }
        $result = PayNotifyLogic::handle('unlock', (string)$unlock->sn, [
            'transaction_id' => 'MOCK-' . date('YmdHis') . '-' . $unlock->id,
        ]);
        if ($result !== true) {
            throw new \RuntimeException((string)$result);
        }
        return [
            'paid' => true,
            'unlock_order_id' => $unlock->id,
            'unlock_status' => 'paid',
            'payment_mode' => 'mock',
        ];
    }

    public static function startGeneration(int $id, string $sku, bool $operatorTest = false): array
    {
        $order = self::order($id);
        if (!$order->scene_id || !$order->pose_id || $order->status === 'deleted') {
            throw new \RuntimeException('订单场景或人物姿势无效');
        }
        $participants = [];
        $participantRows = KioskParticipant::where('kiosk_order_id', $id)->order('slot_no asc')->select();
        foreach ($participantRows as $participant) {
            $photos = KioskPhoto::where([
                'kiosk_order_id' => $id,
                'participant_id' => $participant->id,
                'quality_passed' => 1,
            ])->select();
            $byType = [];
            foreach ($photos as $photo) {
                $byType[(string)$photo->shot_type] = $photo;
            }
            $faceIds = [];
            foreach (self::SHOT_TYPES as $shotType) {
                if (empty($byType[$shotType]) || !$byType[$shotType]->up_face_id) {
                    throw new \RuntimeException('第 ' . $participant->slot_no . ' 位参与者的四张参考照片不完整');
                }
                $faceIds[] = (string)$byType[$shotType]->up_face_id;
            }
            $participants[] = ['slot' => (int)$participant->slot_no, 'face_ids' => $faceIds];
        }
        if (count($participants) !== (int)$order->participant_count) {
            throw new \RuntimeException('参与者数量与订单不一致');
        }

        $unlock = UnlockOrder::where('kiosk_order_id', $id)
            ->where('pay_status', PayEnum::ISPAID)->order('id desc')->findOrEmpty();
        $runtimeFlag = getenv('KIOSK_OPERATOR_TEST_MODE');
        $operatorAllowed = filter_var(
            $runtimeFlag !== false ? $runtimeFlag : env('kiosk.operator_test_mode', false),
            FILTER_VALIDATE_BOOLEAN
        );
        if ($unlock->isEmpty() && !($operatorTest && $operatorAllowed)) {
            throw new \RuntimeException('订单尚未支付，不能调用付费生成');
        }
        if ($order->generation_id) {
            return (new KioskImageForgeService())->generationStatus((string)$order->generation_id);
        }

        $result = (new KioskImageForgeService())->generate(
            $order->order_no,
            (string)$order->scene_id,
            (string)$order->pose_id,
            $participants,
            $sku
        );
        $generationId = (string)($result['generation_id'] ?? '');
        if ($generationId === '') {
            throw new \RuntimeException('GPT-image-2 任务创建失败');
        }
        $order->save([
            'generation_id' => $generationId,
            'prompt_version' => (string)($result['prompt_version'] ?? $order->prompt_version),
            'prompt_hash' => (string)($result['prompt_hash'] ?? ''),
            'status' => 'generating',
        ]);
        if (!$unlock->isEmpty()) {
            $unlock->save([
                'finalize_id' => $generationId,
                'finalize_status' => (string)($result['status'] ?? 'queued'),
            ]);
        }
        KioskAuditService::record($order->order_no, 'gpt_direct_generation', [
            'generation_id' => $generationId,
            'scene_id' => (string)$order->scene_id,
            'pose_id' => (string)$order->pose_id,
            'prompt_version' => (string)$order->prompt_version,
            'participant_count' => count($participants),
            'reference_count' => count($participants) * count(self::SHOT_TYPES),
            'operator_test' => $operatorTest && $operatorAllowed,
        ]);
        return $result;
    }

    public static function generationStatus(int $id): array
    {
        $order = self::order($id);
        if (!$order->generation_id) {
            throw new \RuntimeException('直连生成任务尚未创建');
        }
        $state = (new KioskImageForgeService())->generationStatus((string)$order->generation_id);
        $status = (string)($state['status'] ?? 'queued');
        if ($status === 'review_required') {
            $order->save(['status' => 'review_required']);
        } elseif ($status === 'failed') {
            $order->save(['status' => 'generation_failed']);
        } elseif ($status === 'done') {
            $order->save(['status' => 'final_ready', 'print_status' => 'ready']);
        }
        $unlock = UnlockOrder::where('kiosk_order_id', $id)->order('id desc')->findOrEmpty();
        if (!$unlock->isEmpty()) {
            $unlock->save([
                'finalize_status' => $status,
                'cost' => round(((int)($state['cost_cents'] ?? 0)) / 100, 4),
            ]);
        }
        return $state;
    }

    public static function approveResult(int $id): array
    {
        $order = self::order($id);
        if (!$order->generation_id) {
            throw new \RuntimeException('没有可确认的生成结果');
        }
        $state = (new KioskImageForgeService())->approve((string)$order->generation_id);
        $order->save(['status' => 'final_ready', 'print_status' => 'ready']);
        KioskAuditService::record($order->order_no, 'result_approved', [
            'generation_id' => (string)$order->generation_id,
        ]);
        return $state;
    }

    public static function printStatus(int $id): array
    {
        $order = self::order($id);
        return ['status' => $order->print_status, 'attempts' => $order->print_attempts];
    }

    public static function reportPrint(int $id, array $params): array
    {
        $order = self::order($id);
        $status = (string)($params['status'] ?? '');
        if (!in_array($status, ['printing', 'done', 'failed'], true)) {
            throw new \RuntimeException('打印状态无效');
        }
        $attempts = $order->print_attempts + ($status === 'printing' ? 1 : 0);
        if ($status === 'failed' && $attempts >= 2) {
            $status = 'refund_required';
        }
        $order->save(['print_status' => $status, 'print_attempts' => $attempts]);
        KioskAuditService::record($order->order_no, 'print', [
            'status' => $status,
            'attempts' => $attempts,
        ]);
        return ['status' => $status, 'attempts' => $attempts];
    }

    public static function deleteData(int $id): array
    {
        $order = self::order($id);
        Db::startTrans();
        try {
            $photos = KioskPhoto::where('kiosk_order_id', $id)->select();
            foreach ($photos as $photo) {
                if ($photo->private_path && is_file($photo->private_path)) {
                    @unlink($photo->private_path);
                }
            }
            KioskPhoto::where('kiosk_order_id', $id)->delete();
            KioskParticipant::where('kiosk_order_id', $id)->delete();
            $order->save(['status' => 'deleted']);
            KioskAuditService::record($order->order_no, 'delete', ['scope' => 'all_order_media']);
            Db::commit();
        } catch (\Throwable $error) {
            Db::rollback();
            throw $error;
        }
        try {
            (new KioskImageForgeService())->deleteOrder($order->order_no);
        } catch (\Throwable $ignored) {
        }
        return ['deleted' => true];
    }

    private static function order(int $id): KioskOrder
    {
        $order = KioskOrder::findOrEmpty($id);
        if ($order->isEmpty()) {
            throw new \RuntimeException('Kiosk 订单不存在');
        }
        return $order;
    }

    private static function paymentMode(): string
    {
        $runtimeMode = getenv('KIOSK_PAYMENT_MODE');
        $mode = strtolower(trim((string)(
            $runtimeMode !== false ? $runtimeMode : env('kiosk.payment_mode', 'mock')
        )));
        return in_array($mode, ['wechat', 'wechat_native', 'production'], true)
            ? 'wechat_native'
            : 'mock';
    }

    private static function participant(int $orderId, int $slotNo): KioskParticipant
    {
        $participant = KioskParticipant::where([
            'kiosk_order_id' => $orderId,
            'slot_no' => $slotNo,
        ])->findOrEmpty();
        if ($participant->isEmpty()) {
            throw new \RuntimeException('参与者编号不存在');
        }
        return $participant;
    }

    private static function participantStatus(int $orderId): array
    {
        $result = [];
        $rows = KioskParticipant::where('kiosk_order_id', $orderId)->order('slot_no asc')->select();
        foreach ($rows as $row) {
            $result[] = [
                'participant_no' => (int)$row->slot_no,
                'consent_given' => (bool)$row->consent_given,
                'status' => (string)$row->status,
                'captured_count' => KioskPhoto::where([
                    'kiosk_order_id' => $orderId,
                    'participant_id' => $row->id,
                    'quality_passed' => 1,
                ])->count(),
            ];
        }
        return $result;
    }
}
