# 部署包验证记录

日期：2026-10-12。目标：社区管理网站 + 服务器 AI 视频分析，先准备部署包，不连接云端。

## 已通过

| 验证 | 结果 |
| --- | --- |
| 生产配置及数据库检查 | 7 项通过；缺密钥拒绝启动、Docker secret读取、HTTPS代理头、数据库健康状态 |
| 网站权限与数据写入 | 11 项通过；用户角色、CSRF、图片与媒体权限、密码哈希、长告警保存和失败回滚 |
| DeepSeek及AI运行逻辑 | 18 项通过；包含原6项API请求测试及新增12项部署测试 |
| 部署文件与打包规则 | 5 项通过；只发布80/443、不打包密钥/数据、初始化不覆盖密钥 |
| 新数据库结构 | 在内存SQLite从零迁移成功，所有core模型字段齐全，迁移与模型一致 |
| Django生产检查 | Django5.2.18下 `check --deploy --fail-level WARNING` 通过 |
| 静态文件 | 临时目录中 `collectstatic` 成功，收集143个文件 |

AI测试使用程序生成的短视频和模拟HTTP请求，验证文件只读取一次、EOF后完成、启动失败释放资源、服务健康状态、上报令牌与代理头、H.264回退调用。没有访问实体摄像头或调用真实DeepSeek计费接口。FFmpeg转码分支做了模拟命令验证，不等于实际Linux编码兼容性测试。

数据库测试只使用独立内存SQLite，不修改本机MySQL和现有项目数据。SQLite通过不能代替部署服务器上的MySQL完整测试。

生产依赖已在隔离的Python3.12依赖目录验证关键模块导入，未替换原本机依赖。

最终压缩包已检查CRC、57个Python文件语法、逐文件SHA256及本地密钥排除。还在不含本地配置的解压副本中重新通过7项生产测试和11项权限测试，确认包内源码能够独立加载。

## 尚未执行

- 本机未安装Docker，未实际构建/运行Linux镜像。
- 未执行Docker Compose运行时验证和Caddy配置加载，未申请域名证书。
- 未部署云端、未导入旧业务数据、未测试真实网络摄像头。
- 未重新验证本次服务器环境的DeepSeek账户额度、网络或识别效果。

因此交付结果是“源代码与配置已验证的部署准备包”，不是“已经上线并通过公网验收”。服务器上的步骤见 `README.md`。

## 复查命令

在AI目录：

```bash
python -m unittest test_deepseek test_deployment -v
```

在Django目录（依赖安装后）：

```bash
python -m unittest community_project.test_production -v
python manage.py test core.test_deployment_security --settings=core.test_settings -v 2
```

在项目根目录（部署文件检查需要PyYAML，可安装deploy/requirements.validation.txt）：

```bash
python -m unittest discover -s deploy -p test_deployment.py -v
python deploy/build_bundle.py
```

容器实际部署后的检查步骤、备份和停服命令见 `README.md`。
