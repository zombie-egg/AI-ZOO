# 工程决策记录

本文件记录主指令未直接定义、但为完成项目必须作出的技术决策。日期使用 Asia/Shanghai 时区。

## 2026-08-27 · Phase 1 本地运行采用 Docker 等效 LNMP

- 决策：本地开发与验收使用 Docker Compose 提供 PHP 8.0、Nginx、MySQL 8.0 与 Redis；前端仍使用宿主机 Node.js 构建。
- 备选方案：在 Windows 宿主机直接安装 PHP、Composer、MySQL、Redis、Nginx；使用宝塔测试机。
- 理由：当前宿主机仅有 Node.js 与 Docker Desktop，缺少其余服务。容器方案与上游部署文档的版本和运行目录约束一致，环境隔离、可复现，也不会污染用户已有系统服务。生产环境仍按宝塔/LNMP 路线部署。
- 回滚：停止并移除本项目 Compose 容器即可；项目数据使用具名卷保存，不影响源码。

## 2026-08-27 · Phase 1 裁剪优先使用路由封禁与菜单禁用

- 决策：业务代码存在共享依赖的模块优先通过服务端路由封禁和数据库菜单禁用使其不可达；完全独立且属于生产攻击面的代码生成器、演示中间件再物理移除。被裁剪业务表不删除。
- 备选方案：一次性物理删除裁决表中所有控制器、逻辑、模型、前端页面与资源。
- 理由：主指令要求最小侵入并保留回滚能力。上游项目依赖数据库动态菜单和 ThinkPHP 自动路由，直接大批删除容易制造隐藏的类引用错误；先锁入口、跑回归，再移除无共享依赖的危险代码更稳妥。
- 回滚：恢复被禁用的路由/菜单迁移；物理删除项可从 Git 历史恢复。

## 2026-08-27 · Phase 1 基础镜像使用 DaoCloud 前缀镜像

- 决策：本地 Compose 仅对缺失的 Docker Hub 基础镜像使用 `m.daocloud.io/docker.io/` 前缀；项目源码和依赖版本不变。
- 备选方案：等待本机 `127.0.0.1:33210` 代理恢复；修改 Docker 全局 registry mirror；放弃 PHP 8.0 改用宿主机其他版本。
- 理由：当前 Docker Desktop 的手工代理端口未监听，Docker Hub 直连又超时。DaoCloud 官方公开镜像仓库文档明确支持此前缀形式；它允许继续使用指定的 PHP 8.0/MySQL 8.0 镜像，避免改变运行时版本。
- 本机临时环境：构建期间曾备份 Docker 的 `settings-store.json` 并把所需域名加入 no-proxy 列表；Phase 1 环境就绪后已恢复原文件并核对 SHA-256 一致。现有容器未中断，设置在 Docker Desktop 下次重启时完全重新载入。
- 回滚：将镜像名改回 Docker Hub 原名，并恢复 Docker 设置备份后重启 Docker Desktop。

## 2026-08-27 · PHP vendor 使用 Linux 命名卷

- 决策：本地 Docker 的 `/var/www/html/vendor` 使用独立命名卷，源码仍从 Windows 工作区绑定挂载。
- 原因：`topthink/think-queue` 包含小写 `src/config.php`，而 ThinkPHP 框架包含类文件 `think/Config.php`；Windows 大小写不敏感文件系统会让 Composer 自动加载错误地命中配置文件。Linux 命名卷保留文件名大小写，行为与目标服务器一致。
- 影响：首次启动需在容器中执行一次 `composer install`；删除命名卷即可重建依赖，不影响源码。

## 2026-08-27 · 管理员新密码使用本机临时安全交接文件

- 决策：修改导入库中的默认管理员密码；新密码仅写入仓库根目录 `.phase1-admin-password.txt`，该文件已被 Git 忽略，不在文档、命令输出或版本历史中展示。
- 备选方案：写入项目文档；保持默认密码；直接保存到密码管理器。
- 理由：前两项不安全；当前环境没有获得用户指定密码管理器的写入通道，无法擅自选择外部存储。忽略文件是本机临时交接，不是生产密钥管理方案。
- 后续：用户取得密码后迁移到其密码管理器并删除临时文件；生产上线再轮换一次管理员密码。

## 2026-08-27 · 上游失效后增加仅本机 Luna 协议桩

- 事实：导入库中的 Luna `secret/secret_key` 为空，原地址 `prod.luna.aws.iartai.com` 经公共 DNS 查询为 NXDOMAIN；继续等待旧凭据也无法连接该地址。
- 决策：增加 Compose 内网 `luna-stub`，按原 V3 鉴权、multipart 上传、提交、轮询和模板脸位协议返回固定合成素材，用它验证原项目的事务、余额、队列和前端状态流。
- 安全边界：示例配置默认关闭；开启时仅允许 `luna-stub`/localhost 上游，离线登录同时要求本机 Host；UI 和文档明确标注“非微信”“离线验收”。stub 不执行 AI，也不作为 Luna 官方成功证据。
- 回滚：关闭 `OFFLINE_ACCEPTANCE`/`PHASE1_STUB_ENABLED` 并恢复官方 `BASE_URL`；删除 sidecar 不影响原业务表和正式登录入口。

## 2026-08-27 · uni-app 构建版本与 i18n 模式收敛

- 决策：把 Vite 从 5.2.6 固定为旧版 uni-app 插件声明支持的 4.5.14，并把 vue-i18n 设为 Composition API 模式。
- 原因：旧插件在 Vite 5 下生成的 `import.meta.globEager` 无法执行，H5 空白；页面使用 `useI18n()`，而旧的默认 legacy 模式会在确认页抛错。两项均在浏览器端阻断原 Phase 1 UI 链。
- 验证：H5 能从登录页完成模板选择、制作、队列轮询并进入结果相册；`mp-weixin` 与 H5 生产构建均通过。
