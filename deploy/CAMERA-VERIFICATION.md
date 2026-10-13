# 浏览器摄像头分析验收（2026-10-13）

## 已交付

登录后进入“实时监控”，勾选画面分析授权，点击“开启摄像头并分析”。每台电脑或手机使用自己的浏览器摄像头，不自动启动任何远端设备。手机支持选择前置或后置。网站负责后台调用 DeepSeek，无需另开 AI 服务。

新增 `core/camera_service.py`、`core/camera_views.py`、设备会话模型和 `0012_camera_session` 迁移、摄像头页面及 `static/js/camera-monitor.js`。设备状态存入数据库，支持网站多进程；每进程最多两个后台分析任务，无无限排队。当前 Windows 网站单进程，每账号最多八个活跃会话。

抽样帧仅在内存处理中，不保存图片或录像。告警文字进入现有异常记录，并包含设备名、设备编号与用户编号。失败明确显示未完成分析，不当作“没有异常”。停止、退出登录和超时会使旧任务失效；后台页面停止采集。已发送给模型的请求无法撤回。

## 自动测试

- Django：`core.test_camera` 和 `core.test_deployment_security`，20 项通过。
- 前端：`node --test deploy/test_camera_browser.js`，6 项通过。覆盖同意授权、迟到的摄像头授权与启动响应、停止后不上传、后台停机、异常文字安全展示、模型失败停机。
- Windows 启动与隧道：`test_share_service`、`test_windows_launcher`，24 项通过。
- 打包与部署：`test_deployment`，5 项通过。

在 `t7/Python/community_system` 目录运行 Django 测试（使用独立测试数据库）：

```powershell
..\..\..\.windows\venv\Scripts\python.exe manage.py test core.test_camera core.test_deployment_security --settings=core.test_settings --noinput
```

## 实际链路检查

1. 使用一张无隐私的纯灰色图片调用真实 DeepSeek 接口：成功返回结构化结果，并说明画面无法判断。
2. 独立 Edge 测试配置使用模拟摄像头，通过当前 Cloudflare HTTPS 网址打开页面，主动开启后发送真实采样请求。DeepSeek 识别出模拟摄像头的绿色几何动画并返回无明显异常，页面显示最新结果。
3. 点击停止，浏览器视频轨道关闭，服务端对应设备会话变为 `stopped`。
4. 更新前已备份本机数据库；设备会话迁移、静态资源收集完成。仅重启本项目网站进程，保留原公网隧道与网址。

验收脚本和截图留在本机私有 `.windows` 目录，不随公开源码发布。测试没有读取真实摄像头，没有将真实用户画面发送给模型。

## 尚需实机确认的边界

- 用户自己的摄像头、手机权限弹窗和前后摄像头切换，需要在对应设备上点允许后确认。
- 已验证告警写库和页面展示逻辑，但未进行真实火灾识别准确率验证；禁止为测试点火。
- 多设备在容量内轮流抽样，不能保证每台设备连续实时分析。免费隧道稳定性和手机后台限制仍然存在。
- 本功能用于测试阶段辅助观察，不能替代消防报警器。
