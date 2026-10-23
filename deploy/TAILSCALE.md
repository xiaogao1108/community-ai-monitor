# Tailscale 固定网址（Windows 本机）

网站、数据库和摄像头分析后端仍在这台电脑上。Tailscale Funnel 只提供公网 HTTPS 入口；异地访问者直接使用浏览器，不用安装 Tailscale。

## 初次连接

1. 安装 [Tailscale 官方 Windows 客户端](https://tailscale.com/download/windows)，用个人账号登录并确认设备。
2. 在首次 Funnel 开通页面允许 HTTPS 和 Funnel。安装系统服务需要 Windows 管理员确认；账号登录与开通需要由账号所有者完成。
3. 连接就绪后，项目配置 `.windows/config.json` 的 `provider` 设为 `tailscale`。首次切换前检查 `tailscale funnel status --json`，不得覆盖已有的 443 分享配置。
4. 双击项目根目录“打开网站.cmd”。连续三次公网健康检查通过后自动打开固定网址，同时写入 `.windows/公网访问地址.txt`。

首次开通后，公共 DNS 记录可能需要最多约 10 分钟才出现。入口最多等待约 11 分钟并显示进度；等待期间不反复重建隧道，也不关闭 HTTPS 校验。超时后后台仍持续检查，可以稍后再次打开入口。

Tailscale 初次设备登录可使用：

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' up --hostname=community-ai-monitor --accept-dns=false --accept-routes=false
```

以上参数适用于新安装设备，不接管原 DNS 或其他网络路由；已有 Tailscale 配置应先核对再调整。

## 日常使用

- 继续双击“打开网站.cmd”和“关闭网站.cmd”。关闭只结束本项目网站与它启动的 Funnel 会话，不退出 Tailscale 账号、不关闭其他 ngrok 项目。
- 项目守护进程维护前台 Funnel 子进程；意外退出后会尝试恢复。使用者无需一直开着终端窗口。
- 重启电脑后重新双击“打开网站.cmd”；只要保持同一 Tailscale 账号、设备注册及名称，就继续使用同一 `ts.net` 网址。不要删除设备或改名。
- 地址保留不等于持续在线：电脑必须开机联网，网站和 Tailscale 都必须运行。请检查设备密钥有效期覆盖测试期；到期需重新认证。
- 每次启动仍检查精确域名、HTTPS、CSRF 和公网健康，不跳过登录、录像权限或摄像头授权。
- Tailscale Personal 面向个人非商业使用；Funnel 有带宽限制。费用和规则以官方为准，DeepSeek 分析依然消耗 API 额度。

日志位置：`.windows/logs/tailscale-funnel.log`、`web.log`、`share-launcher-error.log`。不要公开分享日志中的设备开通或登录链接。

## 验证与回退

用 `deploy/verify_public.py --rounds 3 --interval 2` 检查公网登录、资源和权限，再用手机流量打开登录页和摄像头页面。关闭后重开，确认网址没有改变。未完成这些步骤前，不将固定域名视为已成功上线。

回退时先关闭本项目，将 `.windows/config.json` 的 `provider` 改回 `cloudflare`，再双击“打开网站.cmd”。回退会重新取得临时网址；数据库和用户文件仍保留。

## 本机验收记录（2026-10-23）

- 用户使用手机流量、未安装 Tailscale，确认固定网址能显示登录页。
- 使用项目停止命令后，网站状态变为 stopped，Funnel 前台配置自动释放；重新打开后回到 running，设备域名与重启前一致。本次重启的是项目服务，没有重启 Windows。
- 重启后直连和本机既有代理线路各检查 3 轮，每轮 8 项，分别通过 24/24。覆盖健康接口、登录页、静态资源、匿名录像访问拒绝和 CSRF 拒绝。初次发布期间曾有 DNS 解析失败和瞬时连接错误，最终系统 DNS 已能解析。
- Edge 模拟摄像头通过固定 HTTPS 网址完成抽样、上传及真实 AI 分析，显示最近结果；点击停止后，浏览器画面与后台会话均停止。模拟图像没有火情，未据此验证真实火灾识别准确率，也未读取真实摄像头。
- 部署、入口和 Funnel 单元检查 35 项、打包部署检查 5 项、摄像头前端检查 6 项通过。

验收报告保存在本机 `.windows/logs/public-verification-*.json`，不提交运行日志。以上是短时功能和恢复验证，不代表已经完成一个月的连续在线测试。域名可继续沿用，网络、电脑休眠或服务停止仍会导致暂时无法访问。

官方参考：[Funnel](https://tailscale.com/docs/features/tailscale-funnel)、[命令与重启行为](https://tailscale.com/docs/reference/tailscale-cli/funnel)。
