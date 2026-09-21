# 外观忠实与自然表情提示词升级

当前兼容发布版：`reference-faithful-v2-compatible-20260921`

提示词版本：`legacy` → `natural-expression-v1` → `reference-faithful-v2`。在授权素材真实 A/B 完成前，生产默认仍保持 `legacy`。

## 真实运行链路

Kiosk 先从九个场景中选一个，再从 `FRONT`、`SIDE`、`BACK` 三个姿势中选一个；每位参与者按 `body_anchor`、`front_smile`、`left_three_quarter`、`right_three_quarter` 四连拍。PHP 验证订单和付款/操作员测试权限后，将场景 ID、单一姿势 ID 和分组 face ID 交给 ImageForge。

ImageForge 从私有目录取回当前任务的原始上传图，编译并冻结 prompt/版本/参考清单，通过 RelayRouter 的 Gemini `v1beta/models/{model}:generateContent` 接口调用 `gemini-3.1-flash-image-preview`。图片作为 `inlineData` 真实进入每次请求，不是只传文件名、路径或文字外观描述。成品进入人工确认、签名下载和打印链路。

当前没有场景示例图或姿势模特图进入生产请求；场景和姿势都是服务端文本。生成失败图从不会加入 `source_paths_json` 或作为下次的身份参考。

## 失败样例诊断

2026-09-21 提供的小熊猫失败图与生产公开成品中的 `K260921130309B99EF` 匹配，真实选项为 `RED_PANDA_VIEW_01 / BACK`。它生成时服务端默认版本仍是 `legacy`，并未命中 `natural-expression-v1`。

可直接观察到：用户提供的室内正面图无眼镜、刘海密且遮挡大部分额头；失败成品增加了细框眼镜，改变了刘海/额头暴露程度，且脸侧和头发出现局部高饱和绿色亮斑。回头中景与正面近照的角度、透视和光线不同，不将所有轮廓差异都归类为五官变形。

运行证据可确认该成功任务必须有四个不同的有效 face ID、四个存在的私有文件，并将四张图都发为 Gemini `inlineData`。但当前开发工作区无权读取 Zeabur 生产私有卷，因此不能确认另外三张是否佩戴眼镜，也不伪造它们的尺寸。

`legacy` 中小熊猫场景和通用光线合同都明确要求绿色反光作用于皮肤、头发或衣物，并在多处泛化提到 `glasses`。这是与本次色斑和无依据配饰相关的已证实请求风险，但不能凭单张图宣布已确定唯一根因。

## `reference-faithful-v2` 结构

唯一生产入口仍是 `imageforge/app/scene_catalog.py::compose_generation_prompt`，实际编译器在 `imageforge/app/prompt_builder.py`。

1. `REFERENCE ROLES`：严格按实际传输顺序列出 `SUBJECT_PRIMARY` 和 `SUBJECT_ADDITIONAL`。
2. `SUBJECT APPEARANCE`：主参考决定当前发型、刘海、眼镜状态和可见配饰；其他角度只补充身份、穿搭和目标角度。
3. `SELECTED SCENE AND POSE`：只包含当前场景和当前姿势。
4. `HEAD ORIENTATION AND ATTENTION`：编译为一个头部方向和一个视线目标。
5. `EXPRESSION`：默认沿用主参考中性/放松神态，先保外观；不用放大眼睛、上提嘴角或收窄下颌来“优化表情”。
6. `STYLE AND LIGHTING`：保留 2:3 动物园手机随手拍风格；环境反光只能是微弱、宽泛、符合物理的色彩，不得在脸上生成局部绿色聚光斑。
7. `OUTPUT`：保持一张、2:3、现有人数、无拼贴/水印。

完整生产提示词可重复渲染：

```bash
cd imageforge
python scripts/render_prompt_examples.py --scene PANDA_CASUAL_01
python scripts/render_prompt_examples.py --failure-sample
```

`--failure-sample` 只把已经由授权附件确认的“无眼镜、密刘海、中性神态”注入本地 dry-run，不会把这些外观特征写入其他用户的默认提示词。

## 参考图角色、顺序和诊断

- `front_smile` 是 `SUBJECT_PRIMARY`，作为当前面部外观、发型/刘海和眼镜状态的权威参考；其拍摄时的微笑不是强制目标表情。
- `body_anchor`、`left_three_quarter`、`right_three_quarter` 是 `SUBJECT_ADDITIONAL`。
- 真实 Gemini 顺序优先放主参考，再根据姿势放相关侧面和身体/穿搭。`BACK` 单人顺序为：`front_smile`、`left_three_quarter`、`body_anchor`、`right_three_quarter`。
- 1–3 人使用每人 4 张；4 人在 14 张总限制内对称选取每人 3 张，不重复凑数。
- 上传入口纠正 EXIF、最长边限制 3072px，并保存为高质量 JPEG；不裁脸、美颜或生成中间脸。
- 创建任务和 worker 调用前都验证文件存在、可解码、方向后尺寸和 MIME。缺少主体图时直接失败，禁止静默退化成随机人物文生图。
- 内部 `GET /v4/generations/{id}/debug` 返回脱敏诊断：task/request ID、model ID、prompt 版本、图片数、每张的角色/尺寸/MIME/解码状态。不返回私有路径、base64、密钥或签名 URL。

## 版本、重试和缓存

- `GENERATION_PROMPT_VERSION` 只由服务端环境变量选择；客户端 schema 不接受 prompt 版本。
- 任务入队时冻结完整 prompt、hash、版本和参考清单；worker、重试和重启恢复使用原快照。历史任务缺少快照时回落 `legacy`。
- 没有跨订单生成结果缓存。同一 `order_no` 的幂等请求返回原任务，不会用新版 prompt 隐式重做已付费订单。
- Gemini 失败不会退化到本地随机图；任何备用供应商路径都必须继续传同一组主体参考。

## 测试、发布与回退

静态测试覆盖 9 场景 × 3 姿势、参考优先级、角色/顺序/诊断元数据、损坏文件失败、Gemini 图文交错、MIME 一致性、禁止纯文生图、入队快照、客户端无法改版本、旧版回退、鉴权和结果访问。

真实 A/B 应在授权测试账号和非生产配额下进行，最多 6 次；先测背景置换 A，再测场景+回头 B，只有实际存在模特示例图依赖时才测 C。当前生产没有场景/姿势图，所以 C 不适用。没有凭据或配额时只运行 dry-run，不宣称视觉改善。

发布沿用 GitHub `main` → Zeabur。视觉验收前只发布兼容代码，生产保持 `GENERATION_PROMPT_VERSION=legacy`。发布后检查 `/healthz` 的服务、队列、model ID、prompt 版本和 release 版本。

提示词回退：设置 `GENERATION_PROMPT_VERSION=legacy` 并只重新部署 Web 服务。应用回退：重新部署本次发布前 commit，或对当前 commit 执行可审计的 `git revert`。不回滚 SQLite/MySQL，不删除上传、订单或新产生的用户数据。

## 能力依据

- Google Gemini 图片生成文档：https://ai.google.dev/gemini-api/docs/image-generation
- Google Cloud Nano Banana 提示词指南：https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana
- RelayRouter Gemini v1beta 文档：https://doc.relayrouter.ai/en/reference/gemini-v1beta
