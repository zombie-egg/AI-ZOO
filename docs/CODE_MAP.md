# Luna 业务壳代码地图

> Phase 1 定稿（2026-08-27）。本文件描述当前代码，不把静态分析或导入库中的历史记录冒充本次真实上游验收。所有示例均移除凭据、令牌、用户图片 URL 与签名查询串。

## 1. 三端运行边界

| 端 | 目录 | Phase 1 职责 |
| --- | --- | --- |
| 服务端 | `server/` | ThinkPHP 6：登录、模板、余额/充值、Luna 任务、队列轮询、支付回调 |
| 管理后台 | `admin/` | Vue 3：任务、模板、用户、充值及系统配置；菜单由服务端数据库动态下发 |
| 微信小程序 | `uniapp/` | uni-app：微信登录、模板浏览、上传、提交任务、查看结果 |

Phase 1 只保留 Luna 官方 AI 链路；ImageForge、GPT 文案、付费后 `/finalize`、私有高清图及打印状态机属于后续 Phase 2/3，当前代码中不得假装已经实现。

## 2. AI 作图主链路

1. 小程序调用 `app/api/controller/LunaDrawController::submitDrawingV3`，请求体被构造成 `User` 与 `app/common/types/user_draft/Draft`。
2. `app/api/logic/LunaDrawLogic::submitTaskV3(User, Draft)` 只接受单模板玩法；Phase 1 对 `is_collection=true` 直接拒绝。
3. Logic 从 `Draft::template_face_mapping` 得到 `FaceMappingList`，以映射条数计算 `draw_number`，并通过 `DrawLogic::checkAbleDraw` 校验 `ai_user.balance_draw`。
4. `app/common/service/luna/LunaDrawService::submitDrawingTaskV3` 调用 Luna `createSwapEnhanceV3`。
5. 上游返回 `data.messageId` 后，在同一数据库事务内写 `ai_swap_task` 并以账户流水类型 `502 / DRAW_DEC_IMAGE` 扣减作图余额。
6. 提交 `app/job/LunaDrawingPollingJob` 到 `queue_luna_draw_poll_task`，首次延迟 5 秒。
7. Job 调用 `LunaDrawLogic::pollTaskStatusV3`；处理中使用 `release(5)` 再次延迟，终态删除队列任务。
8. 成功时把 `messageList[].sourceFilePath` 写入 `ai_swap_task.result_images`；失败或校验失败时退回作图余额并写 `602 / DRAW_INC_DRAW_FAIL` 流水。
9. 小程序通过任务详情/列表读取本地任务状态和结果，不直接轮询 Luna。

核心持久化字段：`user_id`、`up_task_id`、`draw_number`、`face_mapping`、`user_draft`、`strategy_id`、`status`、`error_msg`、`upstream_resp`、`result_images`。其中四个结构字段由 `SwapTask` 模型按 JSON 读写。

## 3. Luna 上游协议

### 3.1 鉴权

- `POST https://prod.luna.aws.iartai.com/api/app/authentication`
- JSON：`{"secret":"<redacted>","secretKey":"<redacted>"}`
- 成功读取：`data.accessToken`
- 缓存：`luna_draw_token:<sha256(secretKey)>`，避免缓存缺失日志泄露凭据；TTL 约 239 分钟，响应码 `4002` 时清理并刷新。

### 3.2 提交 V3 任务

- `POST /api/userMessage/createSwapEnhanceV3`
- Header：`JWTHEADER: <redacted>`
- JSON 根节点是 `FaceMappingList::toArray()` 返回的数组，不再包一层对象。
- 成功读取：`data.messageId`，并使用可选的 `data.consumingTime` 计算前端预计时间。

脱敏请求结构：

```json
[
  {"up_file_id":82240,"targetFileId":82240,"mapping":{"454477":1091448}},
  {"up_file_id":82318,"targetFileId":82318,"mapping":{"454442":1091448}}
]
```

字段语义：

- `up_file_id`：Luna 目标模板文件 ID。
- `targetFileId`：同一目标模板文件 ID，为算法端兼容字段。
- `mapping`：对象键为模板脸位 ID，值为用户图片经 Luna 上传/质检后得到的上游人脸 ID。
- 一个数组元素代表一张待生成模板图；数组长度也就是本地扣减的 `draw_number`。

该示例来自导入库历史成功任务的已落库请求形状，只用于印证字段结构，不是本次环境新发出的请求。

### 3.3 轮询

- `GET /api/userMessage/polling?messageId=<id>&isThumbnail=0`
- Header：`JWTHEADER: <redacted>`
- 上游状态：`0` 处理中、`1` 成功、`-2` 未检测到人脸；`-1`/`-3` 和其他非预期状态按失败处理。
- 成功结果：`data.messageList[].sourceFilePath`。

导入库中的脱敏历史响应形状：

```json
{
  "id": 37525,
  "status": 1,
  "errorMsg": null,
  "messageList": [
    {
      "id": 339362,
      "status": 1,
      "sourceFilePath": "prod/generateImages/...webp",
      "enhanceFile": "https://...webp?<signed-query-redacted>"
    }
  ],
  "consumingTime": 0
}
```

### 3.4 上传与质检

- `POST /api/userMessage/checkUserImageUpload`
- Header：`JWTHEADER: <redacted>`
- `multipart/form-data` 字段：`file`
- 业务错误：`6001` 重复；`9001` 无脸；`9002` 遮挡；`9003` 眼镜；`9004` 名人；`9005` 安全；`9006` 偏转；`9007` 清晰度；`9008` 儿童。

另有 `GET /api/userMessage/getMaterialFileFaceList?id=<id>` 用于读取模板脸位。

### 3.5 配置与日志安全

后台 `LunaServiceSettingController` → `LunaServiceSettingLogic` → `ConfigService`，最终读取/写入 `ai_config` 中：

- `type=luna_service, name=secret`
- `type=luna_service, name=secret_key`

`LunaDrawService` 的结构化日志会保留方法、URL 和协议形状，但递归遮蔽 `secret`、`secretKey`、`JWTHEADER`、`accessToken`、本地文件路径，并移除签名 URL 查询串。

当前导入库这两个配置值均为空；同时，原官方地址 `prod.luna.aws.iartai.com` 已经 DNS NXDOMAIN。因此本次环境不能完成新的官方 Luna 调用，第 3.2/3.3 的历史记录也不能替代真实验收报文。

### 3.6 本机离线契约验收

为了在上游消失后仍验证原项目自己的集成代码，Compose 增加了不暴露宿主机端口的 `luna-stub` sidecar。它严格限制在 `PHASE1_STUB_ENABLED=true`、本机 Host 和 `luna-stub`/localhost 地址下，提供：

- `/api/app/authentication`
- `/api/userMessage/checkUserImageUpload`
- `/api/userMessage/createSwapEnhanceV3`
- `/api/userMessage/polling`
- `/api/userMessage/getMaterialFileFaceList`

stub 不执行 AI，只返回固定的虚构成人合成素材；任务仍经过原 `LunaDrawService`、`LunaDrawLogic`、数据库事务、余额流水、Redis 队列与 uni-app 轮询页面。验收 UI 明示“Phase 1 离线验收（非微信）”，所以该结果只能证明本地协议和功能链完整，不能证明 Luna 官方服务可用。

离线登录同样是独立的开发入口：默认关闭，服务端限本机 Host，内部仍使用原微信终端用户与 token 模型，并为合成测试用户准备固定数字分身。真实 `mnpLogin` 代码和微信按钮保持不变。

## 4. 本地任务状态机与余额边界

| 本地值 | 常量 | 来源/迁移 | 是否终态 |
| --- | --- | --- | --- |
| 0 | `STATUS_DEFAULT` | 兼容默认值 | 否 |
| 1 | `STATUS_PROCESSING` | 上游提交成功；轮询状态 `0` | 否 |
| 2 | `STATUS_SUCCESS` | 上游轮询状态 `1` | 是 |
| 3 | `STATUS_FAIL` | 上游 `-1`、`-3` 或其他异常终态 | 是 |
| 4 | `STATUS_VALIDATION_FAIL` | 上游状态 `-2` | 是 |

终态在每次轮询入口会短路，不再查询上游。失败退款与状态保存处于同一个数据库事务，但当前实现是“读取状态后再更新”，没有行锁或退款唯一键；正常单队列消费者下可避免重复退款，并发执行同一任务时仍存在重复退款窗口。生产化应增加行锁/条件更新及唯一业务流水约束。

## 5. 微信支付链路

### 5.1 下单

1. `PayController::payWay` 返回当前终端可用支付方式。
2. `PayController::prepay` 校验参数，`PaymentLogic::getPayOrderInfo` 取得充值订单。
3. `PaymentLogic::pay` 检查微信绑定，调用 `formatOrderSn` 给 18 位业务订单号附加终端/时间后缀，再交给 `WeChatPayService::pay`。
4. 金额为 0 的充值单不请求支付平台，直接进入 `PayNotifyLogic::handle('recharge', ...)`。

会员支付分支仍存在于共享底层类以避免侵入性重构，但 Phase 1 路由守卫和菜单已使会员业务不可达。

### 5.2 微信回调

1. `PayController::notifyMnp` / `notifyOa` 构造 `WeChatPayService` 并调用 `notify()`。
2. EasyWeChat `Server::handlePaid` 负责解析微信支付通知及平台签名/证书验证。
3. 仅处理 `trade_state=SUCCESS`；业务订单号截回前 18 位，以 `attach` 选择 `recharge` 分支。
4. 找不到订单或订单已支付时直接返回成功。
5. `PayNotifyLogic::handle` 开启数据库事务；`recharge` 增加 `balance_draw`/`total_amount`，写账户流水 `601 / DRAW_INC_RECHARGE` 和可选 `603 / DRAW_INC_RECHARGE_GIVE`，再更新交易号、支付状态、支付时间并投递 `queue_pay_success`。

### 5.3 已确认的支付缺口

- **金额校验缺口**：业务代码没有把回调中的 `amount.total`、币种与本地订单金额逐项比较；生产上线前必须补齐。
- **并发幂等缺口**：回调外层有 `pay_status` 已支付短路，内部事务却没有对订单加行锁，也没有 `transaction_id`/业务事件唯一约束；并发重复通知仍可能重复入账。
- 这两项不能用“SDK 已验签”替代。SDK 验签解决消息真实性，不解决业务金额一致性或并发幂等。

## 6. 数据模型索引

- AI：`ai_swap_task`、`ai_swap_strategy`、`ai_swap_strategy_group_relation`、`ai_swap_template`、`ai_swap_template_group`、`ai_swap_template_group_relation`、`ai_swap_template_collection_relation`。
- 用户/余额：`ai_user`、账户流水表（`AccountLogLogic` 对应模型）。
- 充值/支付：`ai_recharge_order`、`ai_recharge_package`、支付配置/方式表。
- 配置：`ai_config`。
- 队列：Redis，Luna 轮询队列名 `queue_luna_draw_poll_task`；支付成功队列名 `queue_pay_success`。

## 7. Phase 2/3 交接关注点

- 用统一 `GenerationAdapter` 替换 Luna 时，保持 `FaceMappingList` 以外的本地任务、余额和队列边界稳定。
- GPT 仅允许在已确认支付后的 `/finalize` 调用；Phase 1 预览链路不能出现付费模型请求。
- 原图/高清图必须私有存储，只有已支付最终任务和受审计的重打才能打印。
- 生产前修复支付金额校验、回调并发幂等、作图退款并发幂等。
- 当前后台存在可向已登录管理员返回 Luna token 的历史接口，应在生产加固阶段删除或最小权限化。
- 若未来接入新的官方上游地址，必须重新做外部集成验收；不得沿用离线 stub 的通过结论。
