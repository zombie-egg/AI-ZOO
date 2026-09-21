# 自然表情提示词升级与运维说明

版本：`natural-expression-v1`（兼容代码发布版 `natural-expression-v1-compatible-20260921`）

## 真实链路与审计结论

当前 Kiosk 先让用户从九个场景中选择一个，再从 `FRONT`、`SIDE`、`BACK` 三个姿势中三选一；每位参与者随后按 `body_anchor`、`front_smile`、`left_three_quarter`、`right_three_quarter` 的固定顺序拍四张照片。PHP 服务验证支付/操作员测试权限后，将场景、单一姿势和按参与者分组的 face ID 交给 ImageForge。ImageForge 从私有目录读取参考图，编译一次提示词并调用 RelayRouter 的 Gemini 原生 `generateContent` 接口。结果进入身份质检、人工确认、签名下载和打印链路。

已证实问题：

- 旧公共提示词对全部场景和姿势统一要求“不微笑、闭嘴、直视镜头”，与部分场景看动物的叙事及 `BACK` 姿势冲突。
- 旧身份约束同时使用“completely consistent”“do not reconstruct”等过强措辞，容易让模型把自然表情变化也当成禁止项。
- `BACK` 的旧姿势文本仍要求完整美颜和瘦脸，与项目当前的自然外观目标冲突。
- Gemini 请求过去只有一段总文本后接全部图片，没有与实际图片一一对应的角色标签。
- 旧任务只保存 prompt hash/version；服务重启恢复队列时会用当时的新代码重新编译，无法保证重试使用入队版本。
- 上传图片过去未在模型入口统一应用 EXIF 方向；最多四人时会传 16 张图，超过当前 Gemini 3.1 文档的 14 张总参考图上限。
- `generation_job.provider` 在 Gemini 为主供应商时仍可能记录 GPT 配置的 model ID。

公开展示图中可以观察到：部分成品是紧抿嘴、眼周参与不足或偏“证件照式”的中性表情；也有少数露齿笑。由于仓库没有这些成品逐张对应的原始身份参考，不能据此判断“是否像本人”，也不能把它当作严格 A/B。

未验证项：当前没有失败图与原始授权参考的配对样本，也没有可明确归属测试账号的非生产配额，因此新版的人物相似度、表情改善幅度和实际单次费用仍须真实 A/B 验证。

## 提示词结构

唯一生产组装入口是 `imageforge/app/scene_catalog.py::compose_generation_prompt`，新版具体编译器在 `imageforge/app/prompt_builder.py`。职责顺序为：

1. `REFERENCE ROLES`：只列出真实传入的身份参考及其实际顺序。
2. `IDENTITY`：保留脸型、五官比例、年龄观感、肤色、发型、配饰、体型和穿搭；明确允许眼睑、脸颊、嘴部、眉部和下颌为表情自然变化。
3. `GROUP COMPOSITION`：锁定人数和各参与者边界。
4. `SELECTED SCENE`：只包含本次场景；不再决定人物视线和表情。
5. `SELECTED POSE`、`HEAD ORIENTATION AND ATTENTION`：只包含本次姿势，并解析成一个视线目标。
6. `FACIAL EXPRESSION`：每个请求只有一个已解析策略。
7. `VISUAL STYLE AND COMPOSITION`、面部渲染和输出约束：保留 2:3 写实随手拍风格，不添加强美颜或长负面词表。

完整、无占位符的实际提示词可直接从生产编译器输出：

```bash
cd imageforge
python scripts/render_prompt_examples.py --scene PANDA_CASUAL_01
```

该命令会输出真实熊猫场景分别配合 `FRONT`、`SIDE`、`BACK` 的三份完整提示词，不读取照片、URL 或密钥。

## 三个真实姿势的表情映射

| 姿势 ID | 业务含义 | 唯一视线目标 | 表情策略 |
|---|---|---|---|
| `FRONT` | 身体与脸正对镜头 | 镜头 | `gentle_camera_smile`：轻松、含蓄、闭唇小微笑 |
| `SIDE` | 身体侧转 45–60°，脸自然回向镜头 | 镜头 | `spontaneous_warmth`：短暂真实愉悦，可轻微启唇但不要求露齿 |
| `BACK` | 背影面向场景，20–35° 回眸 | 回眸方向的附近动物 | `attentive_interest`：安静兴趣、嘴部放松、不过度惊讶 |

身体活泼不会自动升级为夸张笑容。`BACK` 不会为了露脸把身体转成正面。各参与者允许保留适合当前姿势的自然参考表情。

## 参考图处理

- 上传流程和四连拍字段保持不变；ImageForge 在私有目录入口校正 EXIF 方向、等比例限制最长边到 3072px，并保存高质量 JPEG，不裁脸、不美颜、不生成中间标准脸。
- Gemini `contents[0].parts` 现在使用“总提示词 → 角色标签 → 对应图片”的图文交错顺序。标签由服务端根据参与者和固定拍摄顺序生成，客户端不能注入。
- 一至三人继续使用每人四张图。四人时为公平且不超过 Gemini 3.1 / RelayRouter 原生接口预算，每人使用同样的三张：身体/穿搭、正面身份、左三分之四身份，共 12 张；不传重复图。
- 当前模型 ID 为 `gemini-3.1-flash-image-preview`。参考图限制由 `REFERENCE_IMAGE_LIMIT` 只能向下收紧；未知 Gemini model ID 默认保守到 3 张。
- 场景和姿势目前只有文字配置，没有额外场景示例图或姿势模特图，因此新版不会伪造这两类参考标签。

## 版本、队列和日志

- `GENERATION_PROMPT_VERSION=legacy`：原提示词基线。
- `GENERATION_PROMPT_VERSION=natural-expression-v1`：新版编译器。
- 该值只从服务端配置读取；请求 schema 不接受 prompt 版本。任务创建时会把完整 prompt、hash、版本和参考图清单写入 SQLite。worker 和服务重启恢复任务都读取入队快照。
- 旧数据库会在进程启动时幂等增加 `prompt_text`、`reference_manifest_json` 两列，不改写历史数据。历史排队任务缺少快照时按 `legacy` 重建，避免无意升级。
- 日志只记录 request/job ID、prompt 版本、场景 ID、姿势 ID、model ID、实际参考图数量、耗时和状态；不记录 base64、密钥、私有路径或签名 URL。

## 可选表情修复

定向编辑模板保存在 `EXPRESSION_REPAIR_TEMPLATE`，但没有接入自动调用。原因是本轮优先把单次生成做好，且没有可靠的自动视觉判定能证明“确实观察到假笑”。它默认关闭，不增加任何付费调用；未来启用前必须补充全局预算、最多一次编辑、原始身份参考、结果对比和失败保留原图。

## 测试、发布和回退

静态测试覆盖九个场景 × 三个姿势、单人/多人参考顺序、四人参考预算、图文交错、EXIF、入队版本冻结、客户端不能覆盖版本、旧版回退、鉴权与结果访问。测试不得触发真实模型或打印。

真实 A/B 应使用同一授权人物、同一场景、同一姿势、同一模型和参数，旧版与新版各三张（最多六次），记录身份、表情、视线、嘴眼脸颊协调、场景/动物/手部退化、耗时和用量。没有授权参考或非生产配额时只做 dry-run，并保持生产 `legacy`。

发布沿用 GitHub `main` → Zeabur 自动构建。发布后检查 `/healthz` 的 `release_version`、`model_id`、`prompt_version`、进程健康和队列深度。视觉 A/B 未通过前，兼容代码可上线但生产默认保持 `legacy`。

回退提示词只需把 Zeabur 服务端 `GENERATION_PROMPT_VERSION` 改回 `legacy` 并重新部署/重启目标 Web 服务；已入队任务继续使用自己的快照。应用回退使用本次发布前记录的 Git commit 重新部署，不回滚 SQLite、MySQL、上传目录、订单或用户新数据。

能力依据：

- Google Gemini 图片生成文档：https://ai.google.dev/gemini-api/docs/image-generation
- Google Cloud Nano Banana 提示指南：https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana
- RelayRouter Gemini v1beta 文档：https://doc.relayrouter.ai/en/reference/gemini-v1beta
