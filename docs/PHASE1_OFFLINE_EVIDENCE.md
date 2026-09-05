# Phase 1 本机离线验收证据

日期：2026-08-27（Asia/Shanghai）

本记录只证明克隆项目的 Luna V3 协议适配、事务、余额、队列和前端状态流可运行，不代表 Luna 官方服务或微信登录可用。所有 token、fixture secret 和本地上传路径均不记录。

## 协议级验证

1. `POST /api/login/phase1OfflineLogin`：返回原项目终端 token，合成测试用户 id=9。
2. `POST /api/lunaDraw/uploadImage`：实际 multipart 经过 `UploadService` 和 `LunaDrawService`，返回 `up_file_id=910001`、人脸 `up_face_id=910101`，本地数字分身记录存在。
3. `GET /api/swapTemplate/groupList?id=2`：返回单图换脸分组及模板。
4. `POST /api/lunaDraw/submitDrawingV3`：经原业务逻辑写任务、扣余额并投递 Redis 队列。
5. 队列 Job 调用原轮询逻辑；终态写回 `status=2`、`result_images=["synthetic-result.png"]`。

## 浏览器 UI 验证

H5 使用与 `mp-weixin` 相同的 uni-app 页面代码，实际完成：

```text
离线验收登录（非微信）
  → 单图换脸首页
  → 选择“高管证件照-男”分组中的一个模板
  → 选择预置合成数字分身
  → 制作照片
  → /pages/draw/generate
  → /pages/user/photoAlbum?from=generate
```

最终任务：

```text
user_id: 9
up_task_id: 7806844626
draw_number: 1
status: 2 (success)
result_images: ["synthetic-result.png"]
账户流水 change_type: 502
余额变化: 59 → 58
```

结果页加载地址：

```text
http://127.0.0.1:8080/resource/image/phase1/synthetic-result.png
```

## 合成素材

- 输入：`server/public/resource/image/phase1/synthetic-input.png`
- 固定结果：`server/public/resource/image/phase1/synthetic-result.png`

两张图均为本次通过内置图像生成器创建的虚构成年人素材，不对应真实人物。stub 只是返回固定结果图，没有执行换脸或其他 AI 处理。

## 外部不可验事实

- 导入数据库的 Luna `secret/secret_key` 为空。
- 导入数据库的微信 `app_id/app_secret` 为空。
- 本机未安装微信开发者工具。
- 原 Luna 域名 `prod.luna.aws.iartai.com` 经公共 DNS 查询返回 NXDOMAIN。

因此不得把本记录中的离线结果写成“微信真实登录成功”或“Luna 官方任务成功”。
