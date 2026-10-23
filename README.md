# 社区管理与 AI 视频监控

社区管理网站与视频分析服务，支持公告、居民反馈、举报处理、积分商品、异常记录和录像查阅。当前运行方案为 Windows 本机部署，通过免费 HTTPS 隧道提供异地测试访问。

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `t7/Python/community_system/` | Django 网站、业务接口、页面模板和数据库迁移 |
| `t7/Python/aiWatchdog-main/` | FastAPI / OpenCV 视频分析服务、DeepSeek 接口及录像处理 |
| `deploy/` | Windows / Docker 部署脚本、测试、使用说明和验收记录 |
| `打开网站.cmd`、`关闭网站.cmd` | Windows 公网测试的一键入口 |

本仓库收录当前部署使用的 Python 网站、AI 服务及完整部署源码。本地原项目中的另一套 Vue / Java 实现未纳入此发布版本。

## Windows 快速开始

1. 安装 Python 3.12（64 位），并将 Python 加入 PATH。
2. 下载或克隆仓库，双击 `deploy/windows-setup.cmd` 安装依赖并初始化独立数据库。
3. 双击 `打开网站.cmd`，等待公网检查完成后打开网站；仅本机使用可双击 `deploy/windows-local.cmd`。
4. 初始管理员账号和随机密码保存在本机 `.windows/admin-login.txt`。用完双击 `关闭网站.cmd`。

首次安装需要联网。Cloudflare 免费隧道无需购买服务器；网站、数据库和录像仍在运行项目的电脑上。电脑必须开机联网，隧道重建后网址可能变化，以 `.windows/公网访问地址.txt` 为准。

需要固定网址时，按照 [Tailscale Funnel 说明](deploy/TAILSCALE.md) 登录设备并开通 Funnel，将本机配置的 `provider` 设为 `tailscale`。原有一键入口继续使用，保留同一账号、设备注册和名称即可沿用域名；访问者无需安装 Tailscale。当前测试电脑已切换至该模式。

详细说明：[Windows 部署](deploy/WINDOWS.md)。Docker 部署材料见 [部署说明](deploy/README.md)。

## AI 配置

在项目根目录运行以下命令，按提示输入自己的 DeepSeek 密钥，输入不会显示：

```powershell
python deploy/windows.py set-key
```

本机或异地电脑、手机登录网站后，进入“实时监控”，勾选同意发送画面，点击“开启摄像头并分析”，允许摄像头权限即可。不需要另开 AI 窗口。疑似火灾、烟雾等会提醒当前设备，并进入管理员的异常记录。每台设备独立授权、独立启停；切换后台或锁屏会停止，回来需重新开启。

AI 使用 DeepSeek API；调用会消耗账户额度。登录不会自动开启摄像头或付费分析。抽样画面不在本站保存为录像，告警只保存文字；辅助识别不能替代消防报警器。密钥保存在本机私有目录，不应提交到 GitHub。每账号最多八个活跃摄像头会话，当前 Windows 运行方式同时分析两组画面，其余设备自动等待。

如需分析视频文件，可另行运行 `python deploy/windows.py ai "D:\Videos\demo.mp4"`。详细操作见 [Windows 部署](deploy/WINDOWS.md)，测试范围见 [摄像头验收](deploy/CAMERA-VERIFICATION.md)。

## 验证与限制

- 相关启动、部署安全和打包检查已通过；测试命令与记录见 [Windows 验收记录](deploy/WINDOWS-VERIFICATION.md)。
- 已实测手机流量访问、网站及隧道进程自动恢复。
- Tailscale 固定网址已通过手机流量访问、项目关闭重开后域名一致性、直连与代理线路各 24 项检查，以及模拟摄像头到 AI 分析和停止流程。详见 [本次验收记录](deploy/TAILSCALE.md#本机验收记录2026-10-23)。
- 未进行一个月持续在线测试。此前免费线路及首次 DNS 发布期间存在连接失败和超时；本项目适合功能测试，不承诺持续可用或安全事件识别准确率。

## 公开版本说明

发布采用独立的干净 Git 历史。仓库不包含 API 密钥、私人配置、管理员密码、数据库内容、上传文件、监控录像、IDE 聊天记录、旧压缩包或运行日志；首次启动会创建新的空数据库。

页面沿用 Bootstrap 5.1.3、jQuery 3.6.0 和 Font Awesome 6.0.0，并随项目提供静态资源及其原始许可证。第三方许可证位于 `t7/Python/community_system/static/js/vendor/LICENSE.*.txt`。
