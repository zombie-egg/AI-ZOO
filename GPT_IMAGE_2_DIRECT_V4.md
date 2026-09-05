# AI 动物合照机 V4：无模板、直连 GPT-image-2 的生产流程

> 决策日期：2026-09-02  
> 核心原则：真实身份优先于“好看”，真实照片感优先于宣传片感。  
> 本方案替代“本地模板换脸 → 免费预览 → GPT 精修”的旧流程。

## 1. 结论

旧方案停止使用。新方案不再把游客塞进任何固定图片模板，也不再生成本地免费换脸预览。

新流程是：

```text
选择文字场景选项（只提交 scene_id，不选择、也不生成模板图）
→ 四连拍并从连拍中挑清晰帧
→ 支付/工作人员测试授权
→ 后端查出该选项对应的固定完整长 Prompt
→ 把固定 Prompt + 四张顾客原图直接发给 GPT-image-2
→ 本地真人相似度与画面规则质检
→ 必要时带原始人像做一次定向修复
→ 顾客确认
→ 高清电子版 + Canon SELPHY CP1500 打印
```

任何 GPT 调用失败都不能再退回本地假换脸图。失败就明确提示重试、人工处理或退款，不能把明显不合格的图当成成品交付。

## 2. 上一张图为什么失败

这不是单纯的审美问题，而是当前架构从输入开始就错了。

1. `imageforge/app/pipelines.py` 先用 `local-dev` 把脸粗糙地贴进固定模板，得到 `local_master.jpg`，再让 GPT “锁死母版构图”。GPT 的自由度被坏母版绑住了。
2. 最终生成只取了四张游客照片中的第一张作为真人参考，其余三张没有进入最终生成调用。
3. 中转接口如果不接受 `image[]` 多图字段，`imageforge/app/providers.py` 会静默退回单图请求；退回后只发送坏母版，真人参考图全部消失。这种兼容回退必须删除。
4. 当前 `local-dev` 的“人脸相似度”并不是人脸识别。它只是把整张图片缩到 128×128 后比较灰度直方图，所以那张明显不像本人的成品仍以 `0.7072` 通过了 `0.55` 的门槛。
5. 摄像头目前只申请 `1280×720` 视频流。1200 万像素相机没有发挥静态拍照能力，脸部有效像素偏少。
6. 旧提示词要求保留母版的衣服、姿势、动物位置和接触点，所以白 T 恤被母版里的毛衣替换、人物僵坐、熊猫像后贴上去，都是架构必然结果。

上一张图的具体问题包括：脸与头颈比例不自然，肤色没有吃到场景暖光，眼镜反光和皮肤曝光不统一，衣服被改，人与熊猫没有可信的空间关系，画面过度摆拍且像景区宣传图。

## 3. 新版顾客流程（8 步）

### 第 1 步：开始与授权

- 扫码或工作人员本机开始。
- 明确告知：会把本次人像发送给图像生成服务，仅用于生成本次照片；原图、衍生图按约定时间删除。
- 未成年人必须由监护人确认。

### 第 2 步：选择文字场景

这里不再叫“模板”。页面展示的是“想和谁合照 / 想拍什么样的照片”的文字选项。前端只提交 `scene_id`，不提交模板图片，也不负责拼 Prompt。

每个 `scene_id` 在服务端一一对应一份**固定、完整、可版本化的长 Prompt**。例如：

```text
PANDA_CASUAL_01  → 和大熊猫在真实熊猫馆自然同框 → panda-casual-v1 完整 Prompt
GIRAFFE_WINDOW_01 → 长颈鹿从观景窗旁自然探头     → giraffe-window-v1 完整 Prompt
CAPYBARA_LAWN_01 → 和水豚在园区草地轻松合照     → capybara-lawn-v1 完整 Prompt
```

一份场景记录至少包含：

- `scene_id`：稳定的程序 ID；
- `title`：给顾客看的短标题；
- `description`：给顾客看的两三句话；
- `prompt_version`：如 `panda-casual-v1`；
- `full_prompt`：实际原样提交给 GPT-image-2 的完整长 Prompt；
- `enabled`：是否上线。

开发时可以用公共“身份与真实感规则”帮助维护各场景 Prompt，但发布时必须编译并保存为每个选项自己的完整文本。生成时不再临时拼 `{animal}`、`{lighting}` 等变量，避免漏字段、串场景或不同服务器生成出不同 Prompt。

前端只能读取 `scene_id/title/description`；`full_prompt` 只保存在服务端。订单同时记录 `scene_id + prompt_version + prompt_hash`，方便以后准确复现和对比哪个 Prompt 的效果最好。

产品上最好把“动物 + 照片风格 + 互动方式”做成一个完整选项，例如“和大熊猫在熊猫馆自然同框”，而不是让顾客分别选择三个下拉框后临时拼 Prompt。若以后确实需要组合，也要提前为每个允许的组合生成唯一 `scene_id` 和固定完整 Prompt。

不要生成或保存模板图、人物姿势坐标、固定脸框和本地合成母版。

### 第 3 步：高质量四连拍

四张照片改成：

1. **半身正面自然照**：作为发型、穿搭、体型和配饰锚点；
2. **正面轻微微笑**：作为主要身份参考；
3. **左 30° 三分之二侧脸**：补充鼻梁、颧骨、下颌；
4. **右 30° 三分之二侧脸**：补充另一侧五官。

取消“纯侧面”和夸张大笑。它们对稳定身份帮助小，反而容易让模型改变脸型。

每个姿势短连拍 3 帧，本地只做清晰度、曝光和单主体检测，然后自动选最清晰一帧。质检用于选片，不用于换脸。

相机实现优先使用 Chromium `ImageCapture.takePhoto()` 获取设备支持的最高静态分辨率；不支持时才回退到视频帧 Canvas。视频流也应读取 `getCapabilities()` 后选择相机可用的最高合理分辨率，而不是写死 1280×720。

### 第 4 步：拍摄确认

顾客只确认四张原始缩略图，确认“本人、眼镜、发型、衣服都拍清楚”。这里不生成 AI 图，也不产生假预览。

### 第 5 步：支付或测试授权

- 商业模式：支付成功后才提交 GPT-image-2，避免免费生成被刷。
- 本机测试模式：允许工作人员跳过支付，但按钮必须写清楚“真实调用 GPT-image-2，本次会产生费用”。
- 删除“本机演示模式返回模板图”的逻辑。测试模式只能跳过支付，不能跳过真实生成。

### 第 6 步：GPT-image-2 直接生成

服务端根据 `scene_id` 读取对应的固定完整长 Prompt，并把同一游客的四张原始照片按固定顺序传给 `/v1/images/edits`：

1. 半身原图（穿搭/体型锚点）；
2. 正面轻微微笑原图（主要身份参考）；
3. 左 30° 三分之二侧脸原图；
4. 右 30° 三分之二侧脸原图。

四张照片均保持原始画面内容，只允许修正 EXIF 朝向；不美颜、不调肤色、不锐化脸。脸部裁剪只在本地身份质检中使用，不作为第 5 张生成输入。不要发送 `local_master.jpg`，不要发送任何旧模板。

官方 GPT Image 文档支持在一次图像编辑请求中提供一张或多张参考图；GPT-image-2 会自动以高保真处理所有输入图，因此不需要传 `input_fidelity`。中转站必须先做多图兼容测试，确认它完整转发所有重复图片字段；如果不支持就直接报错，绝不能静默丢弃真人参考图。

建议正式输出使用官方支持的竖版尺寸 `1024x1536`、`quality=high`、JPEG。打印前只做色彩管理、裁切和打印尺寸适配，不再用 GFPGAN 重画五官。

### 第 7 步：两层质检与一次修复

第一层是本地硬质检：

- 只出现一个游客主体、没有额外人脸；
- 人脸可检测、眼睛鼻口布局完整；
- 用真正的 ArcFace/InsightFace embedding 比较四张原照与成品脸，取多参考综合分；
- 输出尺寸、曝光、清晰度合格；
- 无明显多肢、畸形手、重复动物、文字或水印。

当前灰度直方图相似度必须彻底停用。阈值需要用至少 30 位不同游客的同人/非同人样本校准，不能继续拍脑袋写 `0.55`。

第二层是人工可见质检：成品先让顾客或工作人员看大图，重点看“像不像、衣服有没有变、脸与环境光是否融合、手和动物是否正常”。机器分数不能代替这一步。

若身份或局部结构失败，只允许自动修复一次：把“失败成品 + 全部原始真人参考图”再次发给 GPT-image-2，要求只修脸、手或光线，锁住已经正确的区域。不能只拿失败成品继续改，否则身份会继续漂。

### 第 8 步：确认、打印与删除

- 顾客确认后再发送到 Canon SELPHY CP1500。
- 保存高清电子版下载链接；成品图片本体和打印画面不叠加“AI 生成”角标或其他文字。
- 原始照片、人脸裁剪、embedding、失败候选和成品均按隐私策略到期删除。
- 每个订单使用幂等键 `order_no + generation_attempt`，避免网络重试导致重复计费。

## 4. 生产主 Prompt（直接可用）

以下是编写固定长 Prompt 的生产底稿。每个场景上线前把具体场景内容填入并保存成一份完整不可变文本；运行时根据 `scene_id` 直接读取该文本，不做动态占位符拼接，也不接收游客自由输入。

```text
Create ONE new photorealistic zoo visitor photograph using the supplied reference images of the SAME real visitor. This is a new scene generation, not a face swap and not a template composite.

REFERENCE CONTRACT — follow the upload order exactly:
- Reference image 1 is the BODY / OUTFIT ANCHOR. Preserve the visitor's real hairstyle, hair color, glasses or accessories, body proportions, and the exact visible outfit category, colors, neckline, sleeves, patterns, and layering.
- Reference image 2 is the PRIMARY FRONT-FACE IDENTITY REFERENCE. Preserve the same real person's face shape, forehead, hairline, eyebrows, eye shape and spacing, nose geometry, lips, jawline, ears, age appearance, natural skin tone, and distinctive visible facial details.
- Reference images 3 and 4 are LEFT and RIGHT THREE-QUARTER IDENTITY REFERENCES. Use them to keep the nose bridge, cheekbones, jaw contour, and facial depth consistent.
- All reference images show one and the same visitor. Do not blend them into a new person. Do not copy their original room background into the result.

PRIORITY ORDER:
1. The visitor must unmistakably be the same real person.
2. The visitor, animal, barriers, and environment must share believable physical space and lighting.
3. The result must look like an ordinary real camera photograph, not advertising artwork.
4. The animal and zoo environment must be anatomically and operationally realistic.

IDENTITY AND APPEARANCE:
Preserve identity exactly. No beautification, face averaging, cosmetic retouching, age change, ethnicity change, gender change, enlarged eyes, narrowed jaw, altered nose, artificial skin smoothing, or hairstyle redesign. Keep natural pores and normal facial asymmetry. Preserve the outfit from reference image 1; do not replace a T-shirt with a sweater, jacket, costume, or other garment. Preserve glasses if present, with physically plausible reflections that do not hide both eyes.

TARGET SCENE:
- Animal: {animal}
- Real location: {location}
- Safe interaction: {interaction}
- Framing: {framing}
- Lighting and weather: {lighting}
- Background details: {background}

PHYSICAL COHERENCE:
Place the visitor and animal at a plausible, safe zoo distance. Respect safety glass, railings, habitat edges, and staff-controlled interaction rules when relevant. Use natural partial occlusion and contact shadows: for example, the visitor may rest a hand on a railing while the animal remains in its own protected space. Both subjects must stand or sit on believable ground planes. No floating, pasted-on head, cut-out edge, fused body, or impossible contact. The animal must have species-accurate anatomy, scale, fur, paws, eyes, and posture.

LIGHTING AND COLOR:
Use one coherent real-world lighting setup. The visitor, animal, and environment must receive light from the same direction with matching shadow direction, softness, exposure, white balance, and highlight roll-off. The visitor's skin, hair, glasses, and clothing must visibly receive subtle reflected color from the environment — including restrained green bounce from foliage or exhibit glass when present — while preserving the visitor's natural underlying skin tone. Avoid a separately lit face.

CAMERA REALISM:
Make it look like a casual friend-held smartphone photo taken during a real zoo visit: eye-level camera, approximately 26 mm full-frame-equivalent lens, plausible perspective, slightly imperfect off-center framing, realistic dynamic range, mild high-ISO grain, tiny natural motion softness, restrained lens imperfection, and believable depth of field. It must not look like a fashion shoot, movie still, commercial poster, studio composite, HDR render, or polished tourism advertisement. Do not use dramatic sunset or cinematic rim light unless explicitly required by {lighting}.

BACKGROUND:
Show a recognizable but ordinary real zoo environment: habitat glass, railing, foliage, worn visitor surfaces, and softly blurred educational signage may appear. Signage must contain no readable text. Avoid logos, branding, perfect symmetry, staged decorations, crowds, or extra people.

ANATOMY AND OUTPUT CONSTRAINTS:
Exactly one human visitor. No additional face, reflected face, face-like pattern, duplicate person, extra limb, fused arm, or detached hand. If fingers are visible, each visible hand must have five naturally arranged fingers; if a clean hand cannot be rendered, use a natural pose or occlusion that hides the fingers rather than inventing them. No malformed animal. No readable text, caption, logo, border, watermark, collage, or split screen.

Before producing the image, silently verify: same identity; same outfit; coherent head-to-neck proportion; matching environmental light on skin; one shadow direction; safe and believable human-animal spacing; correct hands and animal anatomy; ordinary smartphone-photo realism.

Return one portrait-oriented 2:3 photorealistic image only.
```

## 5. 大熊猫场景参数示例

不要再使用“大熊猫长椅模板”。把下面参数注入主 Prompt：

```text
{animal} = one adult giant panda with species-accurate black-and-white fur and natural body proportions

{location} = a real giant-panda habitat viewing area in a modern Chinese zoo, with slightly used dark safety railing, habitat glass, bamboo vegetation, and an ordinary visitor walkway

{interaction} = the visitor stands naturally beside the viewing railing, body turned slightly toward the panda and face toward the camera; one hand may rest on the railing. The panda remains inside its protected habitat a short believable distance behind or beside the visitor, calmly eating bamboo or briefly looking toward the camera. There is no direct unsafe touching and no staged bench pose.

{framing} = casual waist-up friend-held smartphone photograph, visitor slightly off center, panda clearly visible but not perfectly mirrored with the visitor

{lighting} = soft overcast daylight mixed with realistic green bounce from bamboo and exhibit glass; neutral skin exposure, one soft key-light direction, no golden-hour glow

{background} = bamboo, habitat rocks, slightly reflective safety glass, a softly blurred educational sign with no readable text, and subtle traces of a real public zoo environment
```

## 6. 失败后的“定向修复 Prompt”

仅在第一次成品没有通过身份、手部或光影质检时调用。第 1 张输入图是失败成品，第 2～5 张仍然是同一游客的四张原始照片。

```text
Edit reference image 1 only where necessary. Keep its already-correct composition, animal, background, camera perspective, and framing unchanged.

References 2–5 show the SAME real visitor and are the authoritative identity and outfit sources. Correct the visitor in image 1 so the face unmistakably matches references 2–5: exact face shape, eyes, eyebrows, nose, lips, jaw, skin tone, hairline, hairstyle, glasses, and age appearance. Restore the exact outfit shown in reference 2. Do not beautify or redesign the person.

Also correct only these detected defects:
{qa_failures}

Relight corrected skin, hair, glasses, and clothing with the existing scene's light direction, white balance, shadow softness, and environmental bounce color. Preserve natural skin texture and coherent head-to-neck anatomy. If a hand is malformed, repair it to a natural five-finger hand or hide the fingers with a plausible existing occlusion.

Do not add people, faces, animals, text, logos, or watermarks. Return one photorealistic edited image only.
```

`{qa_failures}` 必须由程序从有限枚举中生成，例如 `identity mismatch`、`outfit changed`、`face lighting mismatch`、`malformed visible hand`，不要把任意用户文本直接拼进去。

## 7. API 请求规则

服务端请求必须满足：

```text
POST {GPT_IMAGE_BASE_URL}/images/edits
Authorization: Bearer <server-side secret>
multipart/form-data:
  model = gpt-image-2
  prompt = <scene_id 对应的固定完整长 Prompt>
  size = 1024x1536
  quality = high
  output_format = jpeg
  image[] = body-anchor.jpg
  image[] = face-front-smile.jpg
  image[] = face-left-three-quarter.jpg
  image[] = face-right-three-quarter.jpg
```

规则：

- API Key 只能存服务端环境变量，绝不进入 Vue、浏览器请求、日志、Markdown 或 Git。
- 当前测试密钥曾以明文出现在聊天中，正式部署前必须在中转站撤销并重新生成，只把新密钥写入服务器环境变量；旧密钥不能继续用于生产。
- 启动时先做能力探针，确认中转站支持 GPT-image-2、多图片 multipart、`1024x1536` 和 JPEG 返回。
- 如果中转站返回“不支持多图”，订单进入 `provider_incompatible`，由工作人员处理；不能改发单图。
- 记录每次调用的请求 ID、耗时、HTTP 状态和上传图片数量，但日志不记录照片内容与密钥。
- 网络超时结果未知时先按订单幂等状态查询，不能立刻盲目重试造成重复扣费。
- 默认 1 次生成；只有质检明确失败时才允许 1 次修复。总付费调用上限为 2 次。

## 8. 代码改造清单

### Kiosk 前端

- `kiosk/src/KioskApp.vue`
  - 删除 `template`、`waiting`、`preview` 三个旧阶段；
  - 删除 `templates`、`templateAsset()`、`selectedTemplate`、`buildPreview()`、`redoPreview()`；
  - 新增 `scene`、`capture_review`、`generating`、`quality_review` 阶段；
  - 流程改成 `idle → scan → consent → scene → capture → capture_review → pay → generating → quality_review → printing → result`；
  - 删除“免费预览”“本地合成”“GPT 精修模板图”等文案；
  - 本机测试按钮明确显示会产生真实 API 费用。
- `kiosk/src/config.js`
  - 删除 `imageforgePublicBaseUrl` 和 `templateAsset()`；
  - 新增纯文字 `sceneOptions`，前端只保存 `scene_id/title/description`，不保存长 Prompt；
  - `demoMode` 不得再返回假图，可拆为 `skipPaymentForOperator`。
- `kiosk/src/services/camera.js`
  - 优先 `ImageCapture.takePhoto()`；
  - 每个姿势短连拍 3 帧并选最清晰帧；
  - 读取真实设备能力并提高静态分辨率。

### PHP 业务层

- `server/app/api/logic/KioskLogic.php`
  - 删除 `startPreview()` 及“预览完成后才可付款”的前置条件；
  - 订单保存 `scene_id`，支付成功后创建 `generation_job`；
  - 四张照片必须全部上传完成且通过基础质检后才允许支付/生成；
  - 正式生成状态直接映射 `queued / generating / qa / repairing / ready / failed`。
- `server/app/api/controller/KioskController.php` 与路由
  - 移除 `start_preview` 和 preview status 入口；
  - 新增 `scene`、`create-generation`、`generation-status`、`approve-result`。

### ImageForge

- `imageforge/app/pipelines.py`
  - 删除 `run_preview_pipeline()` 和基于 `master_path` 的 finalize 链路；
  - 新增 `run_direct_generation_pipeline()`：读取全部原图 → 生成角色参考裁剪 → 多图直发 GPT → ArcFace 质检 → 可选修复；
  - 删除失败后交付本地母版的降级逻辑。
- `imageforge/app/providers.py`
  - 接口改为 `generate(prompt, reference_images, size)`；
  - 所有参考图以重复 multipart 图片字段发送；
  - 删除“多图失败后只发 scene_master.jpg”的静默回退；
  - 响应中记录服务商 request id，错误分类后返回业务层。
- `imageforge/app/prompts.py`
  - 建立服务端固定 Prompt 目录：一个 `scene_id` 对应一份完整长 Prompt 和明确版本；
  - 公共底稿只用于开发期编译，运行时直接读取已编译完整 Prompt，不动态拼场景变量；
  - 用本文身份规则替换 `IDENTITY_AND_CAMERA_LOCK_V2`；
  - 删除 `Image 1 is the composition-locked local scene master`；
  - Prompt 版本升级为 `direct-realism-v4`。
- `imageforge/app/face_engine.py`
  - 删除 `LocalFaceEngine.similarity()` 的灰度直方图验收资格；
  - 本地开发引擎只能展示调试警告，不能把订单标记为通过；
  - 正式环境启用真实 ArcFace/InsightFace 多参考 embedding，只用于质检，不再用于模板换脸。
- `imageforge/app/main.py`
  - 停止挂载 `/template-assets`；
  - 停止公开旧 preview API；
  - 新增直接生成 API，并在健康检查里明确显示 `multi_image_ready`、`real_face_qa_ready`。

### 数据库迁移

- 新增 `scene_id`、`generation_id`、`reference_count`、`provider_request_id`、`qa_result_json`、`repair_count`。
- 旧的 `template_id`、`preview_task_id`、`preview_url` 暂时保留一版只为数据迁移，不再被新流程读取；确认无旧订单后再删列和旧文件。

## 9. 上线顺序与验收标准

1. **中转站能力测试**：先用非真人测试图验证多图字段确实全部传到模型；失败立即停止，不做单图回退。
2. **直接生成最小链路**：用四张内部授权测试照直发 GPT-image-2，不经过模板和本地换脸。
3. **相机升级**：确认实际静态照片分辨率、脸部像素和眼镜反光可用。
4. **真实身份质检**：启用 ArcFace/InsightFace 并用真人样本校准阈值。
5. **UI 改造**：删除全部模板和免费预览入口，接通支付后生成。
6. **打印验收**：用 CP1500 实机检查裁切、色偏、肤色和边距。
7. **灰度上线**：工作人员逐张复核前 50 单，再决定是否自动放行。

上线前必须全部满足：

- 首次 GPT 请求实际收到恰好 4 张顾客原始照片，日志能证明输入数量和固定顺序；
- 任何兼容错误都不会退回单图或本地母版；
- 白 T 恤不会被改成毛衣，眼镜、发型和脸型稳定；
- 人脸皮肤确实带有场景环境反光，但底层肤色不漂；
- 人与动物有可信的遮挡、地面和安全距离；
- 不出现额外人脸、文字水印、明显畸形手或错误动物解剖；
- 顾客确认前不自动打印；
- API 密钥不在前端包、仓库和日志中。

## 10. 官方依据

- GPT-image-2 模型说明：<https://developers.openai.com/api/docs/models/gpt-image-2>
- OpenAI 图像生成与多参考图编辑指南：<https://developers.openai.com/api/docs/guides/image-generation>

本项目使用第三方中转站。上述能力是 OpenAI 官方接口行为，中转站是否完整兼容必须用能力探针单独确认，不能靠“请求返回 200”推断所有参考图都被模型收到。
