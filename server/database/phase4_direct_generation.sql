-- Phase 4: 无模板、四张原图直连 GPT-image-2。
-- MySQL 8 可重复执行；执行前仍应备份生产数据库。
-- MySQL 8.0 不支持 ADD COLUMN IF NOT EXISTS，故按 information_schema 动态判断。

SET @ddl = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `ai_kiosk_order` ADD COLUMN `scene_id` varchar(64) NOT NULL DEFAULT '''' AFTER `guardian_confirmed`',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_order' AND COLUMN_NAME = 'scene_id'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `ai_kiosk_order` ADD COLUMN `prompt_version` varchar(255) NOT NULL DEFAULT '''' AFTER `scene_id`',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_order' AND COLUMN_NAME = 'prompt_version'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Prompt 版本由场景、姿势、人数和生成规则组成，64 字符不足以完整保存。
SET @ddl = (
  SELECT IF(COALESCE(MAX(CHARACTER_MAXIMUM_LENGTH), 0) < 255,
    'ALTER TABLE `ai_kiosk_order` MODIFY COLUMN `prompt_version` varchar(255) NOT NULL DEFAULT ''''',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_order' AND COLUMN_NAME = 'prompt_version'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `ai_kiosk_order` ADD COLUMN `prompt_hash` char(64) NOT NULL DEFAULT '''' AFTER `prompt_version`',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_order' AND COLUMN_NAME = 'prompt_hash'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `ai_kiosk_order` ADD COLUMN `generation_id` varchar(64) NOT NULL DEFAULT '''' AFTER `prompt_hash`',
    'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_kiosk_order' AND COLUMN_NAME = 'generation_id'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- template_id / preview_task_id / preview_url 暂留一版只为历史订单迁移。
-- 新代码不会写入或读取它们；确认线上无旧订单后再安排独立删列窗口。
