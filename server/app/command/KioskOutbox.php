<?php
declare(strict_types=1);

namespace app\command;

use app\api\logic\KioskLogic;
use app\common\model\kiosk\KioskOrder;
use app\common\model\kiosk\KioskOutbox as OutboxModel;
use app\common\model\kiosk\UnlockOrder;
use app\common\service\kiosk\KioskAuditService;
use think\console\Command;
use think\console\Input;
use think\console\Output;

class KioskOutbox extends Command
{
    protected function configure()
    {
        $this->setName('kiosk:outbox')->setDescription('投递已支付 Kiosk 订单的 GPT-image-2 直连生成任务');
    }

    protected function execute(Input $input, Output $output)
    {
        $events = OutboxModel::where('status', 'pending')->where('available_time', '<=', time())->order('id asc')->limit(20)->select();
        foreach ($events as $event) {
            $claimed = OutboxModel::where(['id' => $event->id, 'status' => 'pending'])->update(['status' => 'processing']);
            if (!$claimed) continue;
            try {
                $unlock = UnlockOrder::findOrEmpty($event->aggregate_id);
                $kiosk = $unlock->isEmpty() ? null : KioskOrder::findOrEmpty($unlock->kiosk_order_id);
                if (!$kiosk || $kiosk->isEmpty() || !$kiosk->scene_id) {
                    throw new \RuntimeException('直连生成关联订单不完整');
                }
                $result = KioskLogic::startGeneration((int)$kiosk->id, (string)$unlock->sku, false);
                $unlock->save([
                    'finalize_id' => (string)($result['generation_id'] ?? ''),
                    'finalize_status' => (string)($result['status'] ?? 'queued'),
                ]);
                $event->save(['status' => 'done', 'last_error' => '']);
                KioskAuditService::record($kiosk->order_no, 'gpt_direct_generation_dispatched', [
                    'generation_id' => (string)($result['generation_id'] ?? ''),
                    'idempotent' => (bool)($result['idempotent'] ?? false),
                ]);
                $output->writeln('dispatched outbox #' . $event->id);
            } catch (\Throwable $error) {
                $attempts = (int)$event->attempts + 1;
                $event->save([
                    'attempts' => $attempts,
                    'status' => $attempts >= 5 ? 'manual' : 'pending',
                    'available_time' => time() + min(300, 2 ** $attempts * 5),
                    'last_error' => mb_substr($error->getMessage(), 0, 500),
                ]);
                $output->writeln('outbox #' . $event->id . ' retry ' . $attempts);
            }
        }
        return 0;
    }
}
