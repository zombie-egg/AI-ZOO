# Phase 1 验收记录

日期：2026-08-27（Asia/Shanghai）

## 结论

Phase 1 在当前机器上能够完成的内容已全部完成。原 Luna 业务壳、数据库事务、余额、Redis 队列、轮询和 uni-app 结果页已经通过一条本机离线验收链真实串通；该模式不调用任何 AI，也不伪装成 Luna 官方服务。

官方 Luna 与真实微信登录仍不能签署为通过：原网关 `prod.luna.aws.iartai.com` 已经 DNS NXDOMAIN，导入库也没有 Luna 或微信凭据，本机没有微信开发者工具。它们是不可由代码修复的外部前提，不再写成“等一组凭据即可完成”。

| 验收项 | 状态 | 证据/说明 |
| --- | --- | --- |
| 服务端 `db/cache/redis-queue=true` | ✅ | `GET /` 实测返回三项均为 `true` |
| MySQL/Redis/PHP/Nginx/Queue/Luna stub 启动 | ✅ | Compose 六个服务运行；MySQL、Redis、stub healthy |
| 管理后台登录与保留功能浏览 | ✅ | 浏览器实测进入 `/admin/workbench`；任务、模板、订单、用户、充值入口可见 |
| Admin 生产构建 | ✅ | `yarn build` 成功 |
| 微信小程序生产构建 | ✅ | `yarn build:mp-weixin` 成功，产物位于 `uniapp/dist/build/mp-weixin` |
| H5 验收构建 | ✅ | `yarn build:h5` 成功；同时修复旧 uni-app 插件与 Vite 5 不兼容、i18n 模式冲突 |
| 微信小程序真实登录 | ⛔ 外部不可验 | `mnp_setting.app_id/app_secret` 为空；本机没有微信开发者工具。原微信登录入口保持不变，未用离线入口冒充微信 |
| 本机离线验收登录 | ✅ | 仅 `OFFLINE_ACCEPTANCE=true` 且本机 Host 可用；通过原用户/终端 token 体系登录，UI 明示“非微信” |
| 公开模板浏览 API | ✅ | 策略只返回 id=2；模板分组可读；id=1/3 被拒绝 |
| 充值/人工余额调整 | ✅ | Admin API 对测试用户 `+1`、`-1` 均成功，最终恢复并生成验收流水 |
| 支付/回调代码链审计 | ✅ 有缺口 | 链路已记录；生产前仍须补回调金额校验和并发幂等，详见 `CODE_MAP.md` |
| Luna V3 鉴权/上传/提交/轮询协议 | ✅ 离线契约验收 | 本机 stub 实现原五个端点；实际 multipart 上传得到 up_file/face ID，提交与轮询走原 `LunaDrawService` |
| 端到端生成 UI | ✅ 离线功能验收 | 登录 → 模板 → 数字分身 → 制作 → Redis 队列 → 相册；任务 `7806844626` 成功，结果 `synthetic-result.png` |
| 余额扣减 | ✅ | UI 验收任务生成 1 张，流水类型 502，验收余额从 59 降至 58，仅扣一次 |
| Luna 请求/响应脱敏 | ✅ 离线报文 | 运行日志保留方法、路径和协议形状，fixture secret/token 与本地文件路径被遮蔽 |
| Luna 官方新任务 | ⛔ 上游已失效 | `prod.luna.aws.iartai.com` 经公共 DNS 查询为 NXDOMAIN；不能把 stub 结果写成官方结果 |
| 被裁模块不可达且不在页面 | ✅ | API/Admin 守卫返回下线响应；物理删除的旧路由 404；菜单与小程序页面清单已验证 |
| 代码生成器/演示中间件/AiChatService 删除 | ✅ | 文件删除，Composer 自动加载通过 |
| 业务表保留及回滚说明 | ✅ | 无 `DROP TABLE`；详见 `REMOVED_MODULES.md` |
| 默认管理员密码修改 | ✅ | 旧密码已拒绝；新密码仅在 Git 忽略的本机交接文件中 |
| `.env`/密钥文件不进 Git | ✅ | `git check-ignore` 验证 |
| 文档与复现手册 | ✅ | `CODE_MAP`、裁剪清单、本地手册、演示脚本及本记录已更新 |

## 离线验收边界

- stub 只用于验证克隆项目的 Luna V3 HTTP 契约、事务、数据库、队列和前端状态流，不生成图片。
- 输入和结果均为本次生成的虚构成人合成素材，保存在 `server/public/resource/image/phase1/`。
- 默认示例配置全部关闭离线模式；服务端还要求本机 Host，并只允许 stub 地址指向 `luna-stub`/localhost。
- ImageForge、GPT `/finalize`、私有高清图和打印状态机均未开始；仍属于第二步及以后。
