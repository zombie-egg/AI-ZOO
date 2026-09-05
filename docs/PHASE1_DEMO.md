# Phase 1 十分钟演示脚本

> 目标：复演部署、自检、后台裁剪，以及本机离线的 Luna 原协议单图任务。不要把离线结果称为 Luna 官方生成结果。

## 演示前提

- Docker 服务已按 `docs/PHASE1_LOCAL.md` 启动。
- 已按 `docs/PHASE1_LOCAL.md` 开启仅本机离线验收开关。
- H5 验收页运行在 `http://127.0.0.1:5174/`；`mp-weixin` 产物已完成生产构建。
- 测试用户有至少 1 次 `balance_draw`；可通过充值套餐或后台人工调整，演示前后记录余额与流水。
- 管理员密码从本机安全交接文件/密码管理器读取，不在录屏或日志中展示。

## 0:00–1:00 环境自检

1. 运行 `docker compose --env-file .env.phase1 -f docker-compose.phase1.yml ps`，确认 MySQL/Redis 健康，PHP/Nginx/Queue 运行。
2. 打开 `http://127.0.0.1:8080/`，展示 `db=true`、`cache=true`、`redis-queue=true`。

## 1:00–3:00 后台与裁剪结果

1. 打开 `http://127.0.0.1:5173/admin/` 并登录。
2. 展示工作台、换脸任务、换脸模板、订单、用户、充值套餐仍可访问。
3. 展示菜单中没有文章、会员、分销邀请、短信、Feedback、代码生成器和盲盒入口。
4. 直接请求一个旧入口，展示统一 Phase 1 下线响应或 404，且没有 500。

## 3:00–5:00 离线登录与模板浏览

1. 打开 H5 登录页，勾选协议并点击“Phase 1 离线验收登录（非微信）”。
2. 进入单图换脸首页，展示策略列表只包含 `id=2`。
3. 浏览模板分组和一张单图模板；确认没有抖音登录、文章、会员、分销、反馈和随机盲盒入口。

## 5:00–6:00 余额

1. 在后台打开测试用户，记录调整前作图余额。
2. 通过充值套餐或后台人工调整增加 1 次作图额度。
3. 刷新用户余额并展示对应账户流水。

## 6:00–9:00 Luna 原协议离线任务

1. 使用仓库 `server/public/resource/image/phase1/synthetic-input.png` 的虚构成人合成图片。
2. 选择单图模板并提交。
3. 服务端应写 `ai_swap_task`，扣减 `balance_draw`，把任务投递到 `queue_luna_draw_poll_task`。
4. 展示脱敏日志：鉴权、`createSwapEnhanceV3` 请求结构、`messageId`、`polling` 响应；确认没有 secret、token、用户原图 URL 或签名查询串。
5. 等待任务变为 `STATUS_SUCCESS=2`，在 H5 相册展示 `synthetic-result.png`；后台任务列表能看到同一任务。

## 9:00–10:00 结果与回归

1. 对照任务前后余额：成功任务只扣一次；失败测试（如执行）应只退一次。
2. 展示 `docs/CODE_MAP.md` 与 `docs/REMOVED_MODULES.md`。
3. 明确 Phase 1 只验证 Luna 原链路；ImageForge、付费后 GPT `/finalize`、私有高清图和打印状态机尚未开始。

## 当前环境说明

截至 2026-08-27，导入库中的 Luna 与微信小程序凭据均为空，本机也没有微信开发者工具；更重要的是，原 Luna 域名 `prod.luna.aws.iartai.com` 已是 DNS NXDOMAIN。因此本脚本只签署本机协议/功能链验收，不签署真实微信登录或 Luna 官方生成结果。若未来获得新的官方服务地址，应另做一次外部集成验收，不能沿用本记录。
