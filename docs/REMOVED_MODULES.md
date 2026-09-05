# Phase 1 瘦身与回滚清单

> 结论：被裁模块均已从菜单/页面入口移除，并由服务端守卫返回统一下线响应或稳定 404；数据库没有执行 `DROP TABLE`。`server/database/phase1_trim.sql` 是可重复执行的菜单/玩法关闭脚本。

| 模块 | Phase 1 处理 | 保留的数据 | 回滚方法 | 验证结果 |
| --- | --- | --- | --- | --- |
| 二级分销与邀请奖励 | Admin/API 守卫封禁；菜单禁用；小程序链接入口清理；移除仅由短信/分享使用的腾讯云 SDK | `ai_task_share`、`ai_task_invite`、`ai_invite_task_couple` 及 `ai_config` 配置 | 恢复守卫规则、菜单状态和 Composer 依赖 | 下线响应；后台无菜单 |
| 兑换码体系 | 清理后台通用链接选择器中的陈旧入口 | 本次 SQL dump 中不存在兑换码 controller、菜单或业务表 | 从 Git 恢复链接项 | 无可达路由或菜单 |
| 文章/资讯 | Admin 守卫封禁；文章菜单禁用；链接选择器清理 | 本次 SQL dump 中不存在 `ai_article*` 表 | 恢复守卫和菜单 | 下线响应；后台无菜单 |
| 抖音登录/支付入口 | 删除登录页抖音分支与 manifest 的 mp-toutiao 配置；API 守卫封禁抖音登录及支付通知 | `ai_config` 中 `douyin_mnp_setting` 配置和共享订单结构保留 | 恢复前端入口、manifest 和守卫规则 | 下线响应；微信入口保留 |
| 会员订阅与会员包评论 | Admin/API 守卫封禁；会员菜单和工作台统计移除 | `ai_member_benefits`、`ai_member_order`、`ai_member_package`、`ai_member_package_comment`；共享代码保留 | 恢复守卫、菜单和工作台区块 | 下线响应；后台无会员入口 |
| `AiChatService` | 确认无业务引用后物理删除 | 无独立表 | 从 Git 恢复 `server/app/common/service/AiChatService.php` | 文件不存在；自动加载通过 |
| 短信 | Admin/API 守卫封禁；短信配置菜单禁用 | `ai_sms_log`、`ai_config` | 恢复守卫和菜单 | 下线响应；后台无短信入口 |
| Feedback | Admin/API 守卫封禁；菜单禁用；小程序反馈页/API 删除；客服悬浮按钮改为微信客服 | `ai_feedback` | 恢复守卫、菜单及前端文件 | 下线响应；页面入口不存在 |
| 代码生成器 | controller/logic/lists/validate/model/service/core/stub 与后台页面/API 物理删除；菜单禁用 | `ai_generate_table`、`ai_generate_column` 保留但不可达 | 从 Git 恢复文件与菜单 | 旧地址稳定 404；后台无菜单 |
| 演示模式中间件 | 从中间件栈注销并物理删除两个 middleware | 无 | 从 Git 恢复注册和文件 | 服务端启动/路由正常 |
| 合辑随机盲盒 | 仅下发策略 2；策略 1/3 禁用；group/template API 拒绝其他策略；提交 Logic 再次拒绝 `is_collection`；小程序删除盲盒页面 | `ai_swap_strategy*`、`ai_swap_template_collection_relation` 全部保留 | 恢复状态、API 限制、Logic 分支和页面 | 策略列表只有 id=2，id=1/3 不可用 |

## 服务端守卫

- Admin：`server/app/adminapi/http/middleware/Phase1ModuleGuardMiddleware.php`
- API：`server/app/api/http/middleware/Phase1ModuleGuardMiddleware.php`
- 注册位置：各自 `app/*/config/route.php`，放在初始化中间件之后。
- 返回：JSON `code=0`、`msg=该功能已在 Phase 1 下线`；代码生成器被物理移除后为 404。

守卫是必要的，因为本项目使用 ThinkPHP 自动路由；只隐藏菜单并不能阻止旧 URL 被直接访问。

## 数据策略与回滚

- 没有删除业务表，没有清理历史任务、订单或用户数据。
- `phase1_trim.sql` 只把明确菜单 ID 和策略 1/3 的 `status` 置为 0；语句可重复执行。
- 回滚时从 Git 恢复物理删除文件和前端入口，移除对应守卫项，再按部署前数据库备份恢复菜单/玩法状态。
- 不建议在不了解历史配置前批量把所有相关菜单状态置为 1；应使用部署前数据库备份做精确回滚。

## 已保留业务回归范围

- 管理员登录、动态菜单、工作台。
- 换脸任务、模板/分组/单图玩法。
- 用户管理、作图余额、充值套餐/充值订单。
- 系统设置、权限与组织管理。
- 微信小程序启动、微信登录入口、模板浏览、单图提交和结果查看代码路径。
