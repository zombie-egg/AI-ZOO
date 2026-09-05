# Phase 1 本地复现手册

本手册是上游 `doc/deploy-*.md` 在当前 Windows 开发机上的等效实现。生产环境仍按宝塔 + LNMP 部署。

## 1. 环境

- Docker Desktop（Linux containers）
- Node.js 18 及以上
- Corepack / Yarn 1.x

## 2. 本地配置

```powershell
Copy-Item .env.phase1.example .env.phase1
Copy-Item server/.env.example server/.env
Copy-Item admin/.env.development.example admin/.env.development
Copy-Item uniapp/.env.development.example uniapp/.env.development
```

- 服务端容器使用数据库主机 `mysql`、Redis 主机 `redis`、表前缀 `ai_`。
- Admin 与 uni-app 的本地 API 地址均为 `http://127.0.0.1:8080`。
- `.env*`、管理员密码交接文件、`vendor/`、`node_modules/`、`dist/` 和运行日志均已加入忽略规则。
- Luna `secret/secret_key` 和微信小程序 `app_id/app_secret` 不进 Git，使用后台安全配置或部署环境注入。

### 本机离线验收开关

官方 Luna 网关已经 DNS NXDOMAIN。若要复演 Phase 1 原链路，在本机未跟踪的 `server/.env` 中设置：

```ini
[PHASE1]
OFFLINE_ACCEPTANCE = true

[LUNA]
BASE_URL = http://luna-stub:8090
OSS_BASE_URL = http://127.0.0.1:8080/resource/image/phase1
PHASE1_STUB_ENABLED = true
SECRET = phase1-offline-secret
SECRET_KEY = phase1-offline-secret-key
```

并在未跟踪的 `uniapp/.env.development` 中设置：

```ini
VITE_PHASE1_OFFLINE_ACCEPTANCE=true
VITE_LUNA_OSS_BASE_URL=http://127.0.0.1:8080/resource/image/phase1
```

示例文件的默认值始终为 `false`。这个模式使用固定合成素材，不调用 AI；生产环境不得开启。

## 3. 启动服务端

```powershell
docker compose --env-file .env.phase1 -f docker-compose.phase1.yml build php queue luna-stub
docker compose --env-file .env.phase1 -f docker-compose.phase1.yml run --rm php composer install --no-interaction
docker compose --env-file .env.phase1 -f docker-compose.phase1.yml up -d
curl.exe http://127.0.0.1:8080/
```

首次创建 MySQL 数据卷时会自动导入工作区根目录的 `loxi_luna_test_20241014_010303.sql.gz`。应用裁剪脚本：

```powershell
Get-Content -Raw server/database/phase1_trim.sql | docker compose --env-file .env.phase1 -f docker-compose.phase1.yml exec -T mysql sh -lc 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" loxi_luna_test'
```

根地址预期：

```json
{"code":1,"show":1,"msg":"hello luna","data":{"db":true,"cache":true,"redis-queue":true}}
```

## 4. 安装与构建前端

```powershell
corepack yarn --cwd admin install --frozen-lockfile
corepack yarn --cwd admin build
corepack yarn --cwd uniapp install --frozen-lockfile
corepack yarn --cwd uniapp build:mp-weixin
corepack yarn --cwd uniapp build:h5
```

开发运行：

```powershell
corepack yarn --cwd admin dev --host 127.0.0.1
corepack yarn --cwd uniapp dev:mp-weixin
corepack yarn --cwd uniapp dev:h5 --host 127.0.0.1 --port 5174
```

- Admin：`http://127.0.0.1:5173/admin/`
- H5 离线验收：`http://127.0.0.1:5174/#/pages/login/login`
- 微信开发者工具导入：`uniapp/dist/build/mp-weixin`

H5 页面中必须先勾选协议，再点击“Phase 1 离线验收登录（非微信）”。真实微信按钮和真实微信登录代码没有被这个入口替换。

## 5. 管理员凭据

默认管理员密码已在本地验收时修改。新密码不写文档、不进 Git；本机交接位置为仓库根目录的 `.phase1-admin-password.txt`（已被 Git 忽略）。进入可用密码管理器后应立即迁移并删除该临时文件。

## 6. 停止与诊断

```powershell
docker compose --env-file .env.phase1 -f docker-compose.phase1.yml ps
docker compose --env-file .env.phase1 -f docker-compose.phase1.yml logs --tail 200 php queue nginx mysql redis
docker compose --env-file .env.phase1 -f docker-compose.phase1.yml down
```

不要添加 `-v`，除非明确要清空本项目 MySQL/Redis/Composer vendor 具名卷并重新导入数据。
