# 社区管理与 AI 视频分析部署说明

**没有 Linux 服务器：请使用 [Windows 本机部署说明](WINDOWS.md)。** Windows 方案支持本机运行网站和 AI，并可通过临时 HTTPS 隧道分享。以下保留 Linux 服务器方案。

本包部署 Django 社区网站、MySQL 8.4 数据库、DeepSeek 视频分析进程，以及负责 HTTPS 和静态文件的 Caddy。它不部署另一套 Vue + Java 业务系统。MySQL镜像版本参照[官方镜像清单](https://github.com/docker-library/official-images/blob/master/library/mysql)。

**目前交付的是部署包，没有创建云服务器，也没有公网网址。** 包内没有数据库数据、用户上传文件、现有 API 密钥或默认管理员账号。首次部署得到空数据库，需创建管理员并录入公告、商品和社区用户。

## 1. 准备什么

- 一台可 SSH 登录、安装 Docker Engine 和 Docker Compose 插件的 Linux 服务器。以下按 Ubuntu 24.04 LTS 示例；安装参照 [Docker 官方 Ubuntu 说明](https://docs.docker.com/engine/install/ubuntu/)。Python 3 仅用于初始化配置，应用依赖由镜像安装。
- 一个已解析到服务器公网 IP 的域名。开放 TCP 80、443，SSH 只允许自己使用；**不要开放 3306、8000、16532**。
- 可用的 DeepSeek API Key，以及一段获准使用的视频或服务器能够访问的网络摄像头地址。
- 本方案调用远端模型，不需要 GPU。资源使用受视频分辨率、并发人数和录像量影响；先做小规模验证，再按实际内存、磁盘和费用调整配置。

Caddy 根据域名申请并续期 HTTPS 证书，需要 DNS 正确且公网能够到达 80/443。细节见 [Caddy 自动 HTTPS 文档](https://caddyserver.com/docs/automatic-https)。尚无域名时，请先在服务器内测试，不要为了临时访问关闭 HTTPS 和权限检查。

## 2. 上传并初始化

将 `community-deploy.zip` 上传到服务器的普通用户目录，例如 `/home/你的用户/`，然后执行：

```bash
unzip community-deploy.zip
cd community-deploy/deploy
python3 init_config.py --domain community.example.com
```

把 `community.example.com` 换成你的实际域名。脚本会隐藏输入 DeepSeek Key，生成 `.env` 和 `secrets/` 下的随机密钥文件，已有文件不会被覆盖。不要把这些文件再次打包分享。

密钥以只读文件挂载给需要它的容器，不烘焙进镜像。`.env` 只存域名、视频源、模型名；若 RTSP 地址含密码，`.env` 也必须保密。Docker secret 文件的机制见 [Docker 官方说明](https://docs.docker.com/compose/how-tos/use-secrets/)。

请妥善备份 `secrets/` 和 `.env`。数据库创建后不要随意重新生成数据库密码文件；修改文件本身不会更新 MySQL 中已有账号的密码。

## 3. 首次启动网站

以下命令都在 `deploy/` 目录执行：

```bash
docker compose build web
docker compose up -d db
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py createsuperuser
docker compose up -d web proxy
docker compose ps
```

数据库首次初始化需要时间，Compose 会等待数据库健康检查通过。迁移只应对本包专用的新数据库执行。**不要直接导入项目旧 SQL 或连接现有生产数据库**；旧数据迁移需要单独核对表结构、明文密码、重复记录及用户媒体。

访问：

- `https://你的域名/`：社区首页。
- `https://你的域名/admin/`：Django 管理后台，使用刚创建的超级管理员。
- `https://你的域名/login/`：社区用户登录。
- `https://你的域名/monitoring/`：社区管理员或值班员工查看监控结果。

后台管理员和社区用户是两个账号体系。使用 Django 后台创建或管理社区用户，给需要查看监控的人设置“管理员”或“值班员工”；普通住户可以在网站注册。不要沿用原 README 中的演示密码。

## 4. 启动服务器 AI 视频分析

### 视频文件

把视频放在 `deploy/input/source.mp4`。`.env` 默认有：

```dotenv
VIDEO_SOURCE=/input/source.mp4
DEEPSEEK_MODEL=deepseek-flash
```

然后执行：

```bash
docker compose --profile ai build ai
docker compose --profile ai up -d ai
docker compose --profile ai ps
docker compose --profile ai logs --tail 80 ai
```

AI 会按视频播放速度读取画面，抽帧发给 DeepSeek，并把识别出的异常写入网站。**文件读完后不循环、不继续计费**；分析完成后可以更换文件，再执行 `docker compose --profile ai restart ai` 重新分析。

短视频也会在读完后分析剩余画面。一次真实演示建议用超过 15 秒的授权素材。是否识别到异常取决于视频内容和模型输出，成功启动并不等于一定产生告警。

### 网络摄像头

将 `.env` 中 `VIDEO_SOURCE` 改成服务器实际可达的 RTSP/HTTP 视频流地址，再执行：

```bash
docker compose --profile ai up -d --force-recreate ai
```

云服务器无法直接访问家里 `192.168.*` 的摄像头，也不会自动使用你电脑的摄像头；需要自行建立受控网络连接。不要把摄像头管理页面直接暴露到公网。

此版本一次运行一个视频源。网页上的“举报上传”负责保存举报视频，**不会自动提交到 AI 分析队列**；如需分析某文件，使用上面的 `input/` 挂载方式。原网页启动本机 Python 进程的按钮已停用，AI 生命周期由 Compose 管理。

DeepSeek 会接收抽取的画面和文字提示，持续分析会产生 API 费用。分析结束或不需要监控时停止 AI：

```bash
docker compose --profile ai stop ai
```

## 5. 检查是否运行正常

```bash
docker compose ps
docker compose logs --tail 80 web proxy
docker compose exec web python manage.py check --deploy --fail-level WARNING
docker compose --profile ai exec ai python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:16532/health/').read().decode())"
```

依次检查：首页和 CSS 正常；能注册、登录；后台能创建公告/商品；未登录访问监控被拒绝；AI 有成功分析记录；测试异常产生后，工作人员账号能查看对应录像。

`/health/` 只检查网站数据库就绪情况，不能证明所有业务都正确。AI 状态 `completed` 表示文件已读完；分析失败或视频流中断会返回 HTTP 503，并需检查日志。网络流中断后需恢复网络并重启 AI，当前不自动重连。AI 的 16532 端口不映射公网，WebSocket 原始视频接口也不对外开放；当前网站主要查看已入库异常记录及录像。受保护视频可播放，尚未优化 HTTP Range 拖拽播放。

排查常见问题：

| 现象 | 检查位置 |
| --- | --- |
| 证书签发失败 | 域名解析、80/443防火墙、`docker compose logs proxy` |
| 数据库启动失败 | `docker compose logs db`；检查 secrets 文件存在且不是空文件 |
| AI 打不开视频 | 文件名、挂载路径、视频格式，或服务器是否能访问 RTSP 网络 |
| DeepSeek 401/402/429 | 密钥、账户额度、请求频率；不要把密钥贴进日志或截图 |
| 页面没有告警 | 确认 AI 最近分析成功、视频存在异常；正常视频不会生成异常记录 |
| 上传或写入被403拒绝 | 登录角色和 CSRF 防护；不要通过关闭检查解决 |
| 原测试账号无法登录 | 本包无旧数据；生产环境拒绝明文密码，使用新建账号 |

如果在明确批准的旧数据库迁移中需要转换社区密码：先做备份，运行 `python manage.py hash_community_passwords` 查看数量，再人工确认执行 `python manage.py hash_community_passwords --apply`。它只转换原明文密码，不改变登录密码本身。不要在尚未确认的数据库上执行。

## 6. 停止、备份和更新

停止全部项目容器：

```bash
docker compose --profile ai stop
```

普通 `docker compose --profile ai down` 会删除容器和项目网络，保留命名数据卷。**不要加 `-v`，那会删除数据库和录像数据。**

持久化内容：`db_data` 保存 MySQL、`media_data` 保存上传媒体和异常视频、`ai_data` 保存分析历史和日志、`caddy_data` 保存证书。容器重建不会自动清除这些卷，但服务器磁盘丢失仍会丢失数据。AI 录像没有自动清理策略，需要监控磁盘余量和制定保留周期。

备份至少包含数据库、媒体、AI历史和配置。数据库导出示例（在 Linux shell 执行，密码不写在命令行参数中）：

```bash
umask 077
mkdir -p backups
docker compose exec -T db sh -c 'MYSQL_PWD="$(cat /run/secrets/db_password)" exec mysqldump -u community --single-transaction --no-tablespaces community' > backups/community.sql
docker compose cp web:/app/t7/front/public backups/media
docker compose --profile ai cp ai:/data/ai backups/ai
```

为保证录像备份完整，可先停止 AI 再复制；`secrets/`、`.env` 用你自己的加密备份方式保存。备份含用户数据，不要放入网站静态目录。定期在隔离环境练习恢复。

更新前先备份，保留上一版部署包，确认数据库迁移兼容，再重新 build、手动 migrate、up。不要自动执行旧 SQL 覆盖数据库。回退代码并不能自动回退数据库结构，遇到不兼容迁移需使用已验证的备份恢复方案。

## 7. 本次交付的验证范围

验证结果记录在同目录 `VERIFICATION.md`。源代码测试与配置检查不能代替 Linux 容器实际构建和公网联调。当前本机未安装 Docker，因此镜像构建、Caddy 证书签发、真实摄像头网络连接需要在你的服务器上按以上步骤验证。

生产依赖单独写在 `requirements.production.txt`。本机开发配置仍保留，原密钥被移至被忽略的本地配置文件。部署包使用文件白名单生成，不包含本机数据库、SQL、监控素材、日志、IDE 历史或密钥文件。

若继续在本机分别运行 Django 与 AI，请为两个进程设置相同的 `AI_INGEST_TOKEN` 环境变量，再启动服务；AI上报现需令牌认证。Docker部署已自动把同一令牌挂载给两个服务。

可以在源码项目根目录重新打包：

```bash
python deploy/build_bundle.py
```

产物在 `dist/community-deploy.zip`，旁边的 `.sha256` 可校验压缩包，包内 `SHA256SUMS` 可校验每个源文件。只分享此部署包，不要压缩整个“期末大项目”目录。
