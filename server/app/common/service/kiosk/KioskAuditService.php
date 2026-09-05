<?php

namespace app\common\service\kiosk;

use app\common\model\kiosk\KioskAudit;

class KioskAuditService
{
    /** 审计元数据只允许订单/状态/成本等非敏感字段，禁止照片、人脸向量和密钥。 */
    public static function record(string $orderNo, string $eventType, array $metadata = [], string $result = 'success'): void
    {
        KioskAudit::create([
            'order_no' => $orderNo,
            'event_type' => $eventType,
            'actor_type' => 'system',
            'actor_id' => '',
            'result' => $result,
            'metadata_json' => json_encode($metadata, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
        ]);
    }
}

