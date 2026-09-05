-- Phase 5: 场景之后选择人物朝向，并将姿势贯穿订单与生图 Prompt。
-- MySQL 8 可重复执行；生产执行前仍应先做全量备份。

SET @ddl = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `ai_kiosk_order` ADD COLUMN `pose_id` varchar(32) NOT NULL DEFAULT '''' AFTER `scene_id`',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_order' AND COLUMN_NAME = 'pose_id'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
