-- Phase 3: Kiosk 后付解锁、可靠生成/打印任务与审计。
-- 可重复执行；生产执行前仍应先做 MySQL 全量备份。

CREATE TABLE IF NOT EXISTS `ai_kiosk_order` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `order_no` varchar(32) NOT NULL,
  `user_id` int unsigned NOT NULL DEFAULT 0,
  `device_id` varchar(64) NOT NULL DEFAULT '',
  `participant_count` tinyint unsigned NOT NULL DEFAULT 1,
  `status` varchar(24) NOT NULL DEFAULT 'created',
  `consent_given` tinyint(1) NOT NULL DEFAULT 0,
  `consent_version` varchar(32) NOT NULL DEFAULT '2026-08-v1',
  `minor_involved` tinyint(1) NOT NULL DEFAULT 0,
  `guardian_confirmed` tinyint(1) NOT NULL DEFAULT 0,
  `scene_id` varchar(64) NOT NULL DEFAULT '',
  `pose_id` varchar(32) NOT NULL DEFAULT '',
  `prompt_version` varchar(255) NOT NULL DEFAULT '',
  `prompt_hash` char(64) NOT NULL DEFAULT '',
  `generation_id` varchar(64) NOT NULL DEFAULT '',
  -- 以下预览字段仅兼容历史订单；V4 新流程不再读取。
  `template_id` int unsigned DEFAULT NULL,
  `preview_task_id` varchar(32) NOT NULL DEFAULT '',
  `preview_url` varchar(1024) NOT NULL DEFAULT '',
  `redo_count` tinyint unsigned NOT NULL DEFAULT 0,
  `unlock_status` varchar(24) NOT NULL DEFAULT 'unpaid',
  `print_status` varchar(24) NOT NULL DEFAULT 'not_requested',
  `print_attempts` tinyint unsigned NOT NULL DEFAULT 0,
  `expire_time` int unsigned NOT NULL DEFAULT 0,
  `create_time` int unsigned DEFAULT NULL,
  `update_time` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_order_no` (`order_no`),
  KEY `idx_user_created` (`user_id`,`create_time`),
  KEY `idx_expire` (`expire_time`,`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Kiosk 拍摄订单';

CREATE TABLE IF NOT EXISTS `ai_kiosk_photo` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `kiosk_order_id` bigint unsigned NOT NULL,
  `participant_id` bigint unsigned NOT NULL DEFAULT 0,
  `shot_type` varchar(32) NOT NULL,
  `private_path` varchar(512) NOT NULL,
  `sha256` char(64) NOT NULL,
  `up_file_id` varchar(32) NOT NULL DEFAULT '',
  `up_face_id` varchar(32) NOT NULL DEFAULT '',
  `quality_passed` tinyint(1) NOT NULL DEFAULT 0,
  `quality_json` json DEFAULT NULL,
  `create_time` int unsigned DEFAULT NULL,
  `update_time` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_participant_shot` (`kiosk_order_id`,`participant_id`,`shot_type`),
  KEY `idx_created` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Kiosk 私有四连拍';

CREATE TABLE IF NOT EXISTS `ai_kiosk_participant` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `kiosk_order_id` bigint unsigned NOT NULL,
  `slot_no` tinyint unsigned NOT NULL,
  `consent_given` tinyint(1) NOT NULL DEFAULT 0,
  `minor_involved` tinyint(1) NOT NULL DEFAULT 0,
  `guardian_confirmed` tinyint(1) NOT NULL DEFAULT 0,
  `status` varchar(24) NOT NULL DEFAULT 'pending',
  `create_time` int unsigned DEFAULT NULL,
  `update_time` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_order_slot` (`kiosk_order_id`,`slot_no`),
  KEY `idx_order_status` (`kiosk_order_id`,`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Kiosk 多人参与者身份分组';

CREATE TABLE IF NOT EXISTS `ai_unlock_order` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL DEFAULT 0,
  `kiosk_order_id` bigint unsigned NOT NULL,
  `sn` varchar(18) NOT NULL,
  `pay_sn` varchar(64) NOT NULL DEFAULT '',
  `terminal` tinyint unsigned NOT NULL DEFAULT 4,
  `sku` varchar(32) NOT NULL DEFAULT 'print_1',
  `order_amount` decimal(10,2) unsigned NOT NULL,
  `pay_way` tinyint NOT NULL DEFAULT 1,
  `pay_status` tinyint(1) NOT NULL DEFAULT 0,
  `pay_time` int unsigned DEFAULT NULL,
  `transaction_id` varchar(128) NOT NULL DEFAULT '',
  `unlock_status` varchar(24) NOT NULL DEFAULT 'pending',
  `finalize_id` varchar(64) NOT NULL DEFAULT '',
  `finalize_status` varchar(24) NOT NULL DEFAULT 'not_started',
  `cost` decimal(10,4) unsigned NOT NULL DEFAULT 0,
  `refund_status` tinyint(1) NOT NULL DEFAULT 0,
  `refund_transaction_id` varchar(255) NOT NULL DEFAULT '',
  `create_time` int unsigned DEFAULT NULL,
  `update_time` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_sn` (`sn`),
  UNIQUE KEY `uniq_kiosk_sku` (`kiosk_order_id`,`sku`),
  KEY `idx_pay_status` (`pay_status`,`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='后付高清解锁订单';

CREATE TABLE IF NOT EXISTS `ai_kiosk_outbox` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `event_key` varchar(96) NOT NULL,
  `event_type` varchar(32) NOT NULL,
  `aggregate_id` bigint unsigned NOT NULL,
  `payload_json` json DEFAULT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'pending',
  `attempts` tinyint unsigned NOT NULL DEFAULT 0,
  `available_time` int unsigned NOT NULL DEFAULT 0,
  `last_error` varchar(500) NOT NULL DEFAULT '',
  `create_time` int unsigned DEFAULT NULL,
  `update_time` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_event_key` (`event_key`),
  KEY `idx_dispatch` (`status`,`available_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付后可靠任务出箱';

CREATE TABLE IF NOT EXISTS `ai_kiosk_audit` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `order_no` varchar(32) NOT NULL DEFAULT '',
  `event_type` varchar(32) NOT NULL,
  `actor_type` varchar(20) NOT NULL DEFAULT 'system',
  `actor_id` varchar(64) NOT NULL DEFAULT '',
  `result` varchar(20) NOT NULL DEFAULT 'success',
  `metadata_json` json DEFAULT NULL,
  `create_time` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_order_event` (`order_no`,`event_type`),
  KEY `idx_created` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='授权/付费/生成/解锁/打印/删除/退款审计';
