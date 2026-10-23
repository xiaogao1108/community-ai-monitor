# Windows 本机部署

这台 Windows 电脑负责运行社区网站和 AI 视频分析，无需 Linux、Docker、单独安装 MySQL 或购买服务器。网站使用独立 SQLite 数据库；原项目数据库不变。电脑必须开机，公网分享及 DeepSeek 分析还需要联网。

## 本机使用

当前入口支持本机运行、异地访问：双击项目根目录的 `打开网站.cmd`，自动连接配置的隧道，连续三次公网健康检查通过后打开网址；用完双击 `关闭网站.cmd`。仅自己使用时，运行下面的本机模式。

当前电脑已经完成安装。双击 `deploy/windows-local.cmd`，浏览器打开 http://127.0.0.1:8765 。登录账号和随机密码见项目根目录 `.windows/admin-login.txt`；社区登录 `/login/` 与 Django 后台 `/admin/` 首次账号均为 `admin001`，是两套独立账号，之后修改密码也各自生效。

换一台 Windows 64 位电脑时：安装 Python 3.12 并勾选添加到 PATH，解压 `community-windows-deploy.zip`，进入 `community-deploy` 文件夹，先双击 `deploy/windows-setup.cmd`，完成后再双击 `deploy/windows-local.cmd`。首次安装需要联网下载依赖，部署包不是离线安装包。

也可以在项目根目录的 PowerShell 执行：

```powershell
python deploy/windows.py setup
python deploy/windows.py local
```

本机模式只监听 `127.0.0.1:8765`，其他电脑无法访问。这个模式使用本机 HTTP，CSRF 和权限校验仍然开启。不要自行把监听地址改成 `0.0.0.0` 或把这个 HTTP 模式映射到公网。

## 分享给别人访问

本机已切换为 [Tailscale Funnel 固定入口](TAILSCALE.md)，继续双击原有“打开网站.cmd”和“关闭网站.cmd”。手机访问和项目重启后网址保持不变均已验证；详细范围见该说明中的验收记录。换电脑需要重新安装、设备登录及首次 Funnel 开通，不能直接沿用另一台设备的域名。首次公网 DNS 发布可能等待约 10 分钟。下面的 Cloudflare 说明适用于新安装默认模式或回退使用。

### Cloudflare 临时网址

双击项目根目录 `打开网站.cmd`，等待浏览器打开。把浏览器地址发给异地测试人员即可；最新网址也保存在 `.windows/公网访问地址.txt`。启动后可以关闭命令窗口，网站和隧道在后台运行。

- 网站、数据库、录像与 AI 进程都在本机。Cloudflare 只转发网络请求，没有把代码或数据库部署到云端。
- 旧项目继续使用原 ngrok；本脚本不读取它的令牌、不修改它的配置、不关闭它的进程。新项目只转发 `127.0.0.1:8765`。
- 如果本项目此前处于仅本机模式，入口会先停止本项目旧进程，再切换为 HTTPS 公网模式。已开启分享时，再次双击只打开当前网址，不重复建立隧道。
- 电脑必须开机联网。隧道退出后会自动重连，网址可能改变；请重新查看地址文件，不要把临时链接当作永久网址。
- 关闭时双击 `关闭网站.cmd`，网站和本次隧道一并退出。AI 若在独立窗口运行，需要另外 Ctrl+C 停止。

本机已安装并校验 Cloudflare 官方程序，无需账号或域名。换电脑时入口会自动下载所需程序；下载失败不会执行残缺文件。HTTPS、CSRF、精确域名校验和录像权限保持开启。登录页面的 Bootstrap、jQuery 和字体资源使用项目内相同版本副本，减少手机访问外部资源网站时的等待。

手动排查时可在根目录运行（通常无需自己执行）：

```powershell
python deploy/windows.py share
python deploy/windows.py status
python deploy/windows.py stop
```

连接失败查看 `.windows/logs/localhost-run.log`（Cloudflare 为 `tunnel.log`）；启动失败查看 `.windows/logs/share-launcher-error.log` 与 `web.log`。隧道进程退出后会自动重连；域名变化后自动同步网站允许域名。公网检查失败时状态变为 degraded，地址文件会标注未通过检查。若端口被其他软件占用，不会按进程名批量停止任何程序。

如果 Cloudflare 返回 `Unauthorized: Tunnel not found`，说明临时隧道已被服务端移除，即使隧道进程仍在运行也无法继续使用。脚本会自动结束本次失效隧道、申请新网址并更新网站域名；不用重装项目或修改密钥。启动窗口最多等待三分钟，并显示连接恢复和检查进度；电脑休眠或断网后需要先恢复联网。

电脑关机或进程意外结束后，状态文件可能仍显示旧网址。入口会同时检查本项目进程锁与网站端口；确认旧服务已退出后重新启动，不再要求已经不存在的旧进程回应停止。请用“打开网站.cmd”取得当前网址，不要长期收藏免费临时地址。

维护人员可运行 `python deploy/verify_public.py`，连续检查健康接口、登录页、样式/脚本/字体、录像权限和 CSRF 拒绝行为；报告存入 `.windows/logs/public-verification-*.json`。默认直接连接公网，加 `--system-proxy` 可对比本机代理线路，不会修改系统代理设置。该检查不读取真实用户密码，也不能代替手机流量实测。连续三次健康检查只说明当时可达，不等于长期稳定性验收。

Cloudflare Quick Tunnel 用于测试，免费网址会在重建隧道后变化，且没有持续可用性保证；参见 [官方说明](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)。localhost.run 的兼容代码保留，但因实测间歇协议误标、手机无法打开，当前不作为默认线路。没有关闭 HTTPS 检查来掩盖线路故障。

## 使用本机、异地电脑和手机摄像头（推荐）

无需另开 AI 命令窗口。每台设备都按下面三步操作：

1. 用电脑浏览器或手机自带浏览器打开当前 HTTPS 网址，登录后进入“实时监控”。
2. 填写设备名称，选择前置或后置摄像头，勾选同意发送画面。
3. 点击“开启摄像头并分析”，允许摄像头权限，等待“最近结果”。用完点击“停止摄像头和分析”。

登录不会自动开启摄像头，也不能替其他设备授予权限。每个页面单独处理自己的画面；管理员和员工可在“异常记录”查看各设备的告警文字，普通用户不能查看全站记录。告警包含设备名称、设备编号和用户编号。检测到疑似火情等会在当前页面提示，并尝试播放提示音；管理员在线时沿用网站的全局提醒。

每轮抽取最多 3 张 JPEG 画面，最长边 640 像素，发送间隔至少 15 秒。画面经本机后端发送给 DeepSeek，密钥不会下发到浏览器。本站不保存抽样图片或完整录像，只保存设备状态、最新结果与告警文字。手机锁屏、页面进入后台、离开页面、退出登录或分析失败时会停止；回来需要手动重新开启。停止无法撤回已发送给模型的画面，但服务端收到停止请求后会丢弃该会话尚未完成的结果；连接丢失的会话在 120 秒后失效。

当前单进程同时分析最多 2 组画面，其余设备提示忙碌并重试；每账号最多 8 个活跃摄像头会话。这是少量设备测试方案，不能保证所有设备同时连续实时分析。相同设备同类告警两分钟内合并，变更异常类型会另行记录。辅助识别可能漏报或误报，不替代消防报警器。免费隧道不收费，但 DeepSeek 调用消耗 API 额度。

如果需要更换密钥，使用下方 `set-key` 命令。使用代码更新现有安装时，先备份 `.windows/data/db.sqlite3`，执行 `python deploy/windows.py manage migrate --noinput` 和 `python deploy/windows.py manage collectstatic --noinput`，再重启本项目网站。

## 视频文件或固定摄像头的独立 AI 分析（可选）

先启动网站，再打开另一个 PowerShell，切换到项目根目录。当前电脑沿用已存在的私有密钥配置；换电脑或换新密钥时运行：

```powershell
python deploy/windows.py set-key
```

按提示粘贴密钥，输入不会显示，保存到 `.windows/secrets/deepseek_api_key.txt`。该文件不会进入部署包。曾发在聊天中的密钥建议在 DeepSeek 控制台更换。

选择一种输入：

```powershell
# 视频文件：改成你自己的绝对路径
python deploy/windows.py ai "D:\Videos\demo.mp4"
# 本机第一个摄像头
python deploy/windows.py ai 0
# 带密码的 RTSP 地址：交互输入，避免留在命令历史
python deploy/windows.py ai
```

AI 窗口保持运行，Ctrl+C 停止。视频文件读完后停止分析，服务可能仍驻留，Ctrl+C 关闭后可以重新选择视频。启动 AI 会调用 DeepSeek 并产生账户费用；只有获准使用的视频才应提交分析。当前未自动打开摄像头或启动计费分析。

录像和缩略图位于 `.windows/data/media/video`，状态文件位于 `.windows/data/ai`。AI 通过本机接口写入同一个社区数据库，管理员在网站的监控、异常记录页面查看结果。浏览器实时画面与 AI 私有 WebSocket 没有额外做公网转发；本方案支持服务端分析及网站查阅记录、录像。

Windows 安装中使用 `imageio-ffmpeg` 提供 FFmpeg，用于把录像转成浏览器可播放的 H.264，无需另外配置系统 PATH。AI 模型仍通过 DeepSeek API 调用，不需要本机 GPU。

## 关闭、查看状态和备份

```powershell
python deploy/windows.py status
python deploy/windows.py stop
```

`stop` 关闭这次脚本启动的网站和隧道；AI 是独立窗口，需要再按 Ctrl+C 停止。后台运行网站时同样可以用 `stop` 关闭。不要用进程名批量结束所有 Python。

数据库、上传文件、配置、随机密码和密钥都在 `.windows` 文件夹。备份前先停止 AI 和网站，再复制整个 `.windows` 到自己保管的位置；虚拟环境 `venv` 可以重新安装，不必备份。请勿公开分享整个 `.windows`。分享源码请使用 `dist/community-windows-deploy.zip`，其中没有运行数据、用户资料或密钥。

首次数据库是空的，只生成管理员，原数据库的业务数据没有迁移。公告、商品和人员可在后台录入。SQLite 适合当前单机演示和少量用户；大量并发或长期正式运营需另做容量与运维评估。

## 本次交付状态（2026-10-12）

Windows 本机环境已初始化，改用 Cloudflare 后用户已确认手机可看到登录页面，自动恢复测试通过。持续访问仍存在连接错误和超时，严格稳定性验收未通过；详细数据见 `WINDOWS-VERIFICATION.md`。真实管理员登录曾在本机验证；公网验证不提交真实管理员密码。
