-- Phase 1 裁剪：仅关闭入口，不删除历史业务表。
-- 适用于项目随附的 ai_ 前缀数据库；重复执行安全。

UPDATE ai_system_menu
SET is_disable = 1, update_time = UNIX_TIMESTAMP()
WHERE id IN (
    24, 39, 40, 41, 42, 43, 44,
    70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 105, 106,
    107, 108, 109,
    174, 175, 176, 177, 178, 179, 259, 260,
    183, 184, 192, 198, 254, 255, 262, 263, 264, 265, 266, 267, 268,
    269, 270, 288, 298, 299, 300, 301, 302,
    202, 283,
    207, 208
);

-- 盲盒/跨组玩法保留数据，只允许 Phase 1 的单张换脸策略（id=2）出现在接口中。
UPDATE ai_swap_strategy
SET status = CASE WHEN id = 2 THEN 1 ELSE 0 END,
    update_time = UNIX_TIMESTAMP()
WHERE id IN (1, 2, 3);
