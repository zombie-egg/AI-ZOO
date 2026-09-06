# AI ZOO 动物合照机

AI ZOO 是一套完整的现场拍摄、AI 多人合照生成、人工验图与照片打印系统。支持 1–4 位参与者逐人授权、逐人四连拍，再按照人物分组生成一张动物场景合照。

## 完整流程

1. 选择 1–4 人合照。
2. 微信扫码支付 ¥9.90；只有后端支付状态变为 `paid` 后才进入下一步。未配置商户接口时使用模拟支付按钮。
3. 每位参与者分别完成人脸照片授权。
4. 统一选择动物场景和正面、侧身或背影姿势。
5. 每个人单独完成半身、正面、左侧和右侧四连拍，再汇总检查。
6. GPT-image-2 生成，Gemini 图片模型作为失败兜底。
7. Prompt 对每个人独立执行美白、磨皮、黑眼圈淡化和自然瘦脸，并禁止身份、发型、服装互换。
8. 工作人员逐人确认成品后，向打印代理发送一次、单页、单份打印任务。
9. 最终取片二维码直连带签名的高清照片下载，24 小时内有效。

## 项目结构

```text
admin/                 管理后台源码
imageforge/            FastAPI 图片生成、兜底、质检与签名交付服务
kiosk/                 Vue 现场大屏，包含摄像头采集与完整多人流程
print-agent/           Electron 本机打印代理，支持 Canon SELPHY CP1500
server/                ThinkPHP API、订单、支付、照片分组与审计
uniapp/                移动端/微信端源码
optional/facefusion/   可选的生产级人脸相似度组件
deploy/                Zeabur 单容器入口、Nginx 与进程管理配置
Dockerfile             Zeabur 云端 Web 服务构建文件
zeabur.yaml             Zeabur GitHub 自动部署模板
```

## 同一云端域名运行完整流程

Zeabur 运行 Kiosk 网页、PHP API、ImageForge、MySQL 和 Redis。摄像头和打印机不能接入云服务器，必须物理连接现场电脑：

- 摄像头由浏览器通过 `getUserMedia` 直接调用。
- 打印机由现场电脑上的 `print-agent/` 调用系统打印驱动，并主动通过加密 WebSocket 连接 Zeabur 打印中转。
- 用户始终只打开 `https://ai-zoo-zombie.zeabur.app/kiosk/`，不再启动或打开本地 Kiosk 网页，也不再由云端网页访问 `127.0.0.1`。
- 每台新电脑第一次使用时，运行一次 `field-client/start-macos.command` 或 `field-client/start-windows.cmd`。脚本会生成独立随机终端码、自动绑定云端域名，并把打印代理设置为登录后自启。
- 摄像头和打印机仍必须物理连接到正在打开网页的同一台电脑；浏览器授权摄像头，后台代理访问系统打印机。

## 本机启动

```bash
cp .env.phase1.example .env.phase1
cp server/.env.example server/.env
cp imageforge/.env.example imageforge/.env
docker compose -f docker-compose.local-real.yml up -d

cd imageforge
python3 -m venv .venv-macos
.venv-macos/bin/pip install .
.venv-macos/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ../kiosk
npm ci
npm run dev -- --host 127.0.0.1 --port 4175

cd ../print-agent
npm ci
npm start
```

打开 `http://127.0.0.1:4175`。浏览器需要相机权限，macOS/Windows 需要给 Electron 打印权限并安装对应打印机驱动。

其他现场电脑可直接使用 [`field-client/`](field-client/) 内的 macOS 或 Windows 一次性安装脚本。安装结束后会自动打开云端域名，以后直接访问相同云端域名即可。摄像头和打印机均会自动回退到该电脑的系统默认设备，不依赖当前 Mac 的设备名。

## Zeabur 部署

仓库根目录的 `Dockerfile` 会构建 Kiosk，并在一个 Web 服务中运行 Nginx、PHP-FPM、队列和 ImageForge。`zeabur.yaml` 另外创建 MySQL、Redis、持久化卷和域名绑定。

部署密钥只设置在 Zeabur 环境变量中，禁止提交 `.env`：

- `FALLBACK_IMAGE_BASE_URL`
- `FALLBACK_IMAGE_API_KEY`
- `IMAGE_PROVIDER_OVERRIDE`（生产环境固定为 `gemini`）
- `IMAGEFORGE_SECRET`
- `IMAGEFORGE_SECRET_KEY`
- `IMAGEFORGE_ACCESS_TOKEN`
- `IMAGEFORGE_INTERNAL_TOKEN`
- `SIGNING_SECRET`
- `KIOSK_DEVICE_PROXY_TOKEN`
- `KIOSK_PAYMENT_MODE`（未接微信商户接口时设为 `mock`，正式上线时设为 `wechat_native`）

GitHub 的 `main` 分支更新后，Zeabur Git 服务会自动重新构建部署。

## 验证

```bash
cd imageforge && pytest -q
cd kiosk && npm run build
php -l server/app/api/logic/KioskLogic.php
```

生成图片会产生第三方 API 费用。自动化验证不应触发真实生图或实际打印。
