-- Phase 6: 一至四位参与者逐人授权、逐人四连拍与多人合照。
-- MySQL 8 可重复执行；生产执行前仍应先做全量备份。

SET @ddl = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `ai_kiosk_order` ADD COLUMN `participant_count` tinyint unsigned NOT NULL DEFAULT 1 AFTER `device_id`',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_order' AND COLUMN_NAME = 'participant_count'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

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

SET @ddl = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `ai_kiosk_photo` ADD COLUMN `participant_id` bigint unsigned NOT NULL DEFAULT 0 AFTER `kiosk_order_id`',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_photo' AND COLUMN_NAME = 'participant_id'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl = (
  SELECT IF(COUNT(*) > 0,
    'ALTER TABLE `ai_kiosk_photo` DROP INDEX `uniq_order_shot`',
    'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_photo' AND INDEX_NAME = 'uniq_order_shot'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `ai_kiosk_photo` ADD UNIQUE KEY `uniq_participant_shot` (`kiosk_order_id`,`participant_id`,`shot_type`)',
    'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_photo' AND INDEX_NAME = 'uniq_participant_shot'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
