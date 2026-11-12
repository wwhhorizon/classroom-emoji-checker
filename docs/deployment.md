# 部署与维护

## 本地运行

推荐 Python 3.12。双击“启动课堂表情系统.cmd”，或按 README 创建虚拟环境并安装 requirements.txt、requirements-ai.txt。首次运行 `python scripts/dev.py --seed` 自动生成 `.env` 中的随机服务令牌、注册邀请码和演示密码，初始化账号、课程、课堂和名单，启动8010后端和8011推理服务。

本地 SQLite 位于 `data/emoji.db`。初始化只在缺少相应课程时创建课堂，不重置原有账号密码和历史。课堂时段到期后，管理员新建课堂并安排名单；不回填和篡改已有课堂时间。

服务启动后检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/health
Invoke-RestMethod http://127.0.0.1:8011/health
```

AI 健康响应应显示模型已加载。权重文件随工程提供；若缺失，运行 `python -m ai_service.download_model`，下载器校验35,040,571字节和固定SHA-256。模型许可位于 ai_service/models/。

## 配置

| 变量 | 作用 |
|---|---|
| DATABASE_URL | 默认为 sqlite:///data/emoji.db；MySQL 可用 mysql+pymysql URL |
| AI_SERVICE_TOKEN | 后端和推理服务共享的独立服务令牌 |
| ADMIN_INVITE_CODE / TEACHER_INVITE_CODE | 管理员、教师注册邀请码 |
| DEMO_PASSWORD | 初次生成的基础演示账号密码 |
| AI_CONFIDENCE_THRESHOLD | 默认0.6，范围0～1 |
| AI_SAMPLE_SECONDS | 默认3秒，浏览器和worker的采样间隔 |
| AI_URL | 本地 http://127.0.0.1:8011，Compose 内为 http://ai:8011 |
| COOKIE_SECURE | HTTPS 使用1，本地 HTTP 使用0 |
| MYSQL_PASSWORD | Compose 数据库用户密码 |

生产环境自行设置强随机配置，避免将 `.env` 提交到 Git。不要把数据库连接字符串或服务令牌粘贴到公开日志。演示初始化账号应在正式部署前停用或替换。

## 摄像头与视频 worker

```powershell
python -m ai_service.worker --source 0 --session 1
python -m ai_service.worker --source path/to/video.mp4 --session 1 --sample-seconds 3 --threshold 0.6
```

在项目根目录运行时，worker读取本地.env。摄像头编号通常从0开始；课堂必须正在进行。系统不识别人脸身份，默认写入匿名观测。

浏览器采样应从 localhost 或 HTTPS 页面主动打开；停止、切换课堂或离开页面时释放摄像头。本地视频在浏览器内播放，只发送抽取的帧，不上传保存视频文件。

## MySQL 与 Compose

提供 MySQL 8.4、业务后端和独立 AI 服务三个容器，数据库使用持久化卷。`database/schema.sql` 由当前实体生成，包含外键、枚举检查、唯一键和复合索引。后端启动时创建缺少的表并初始化账号。

```powershell
# 首次本地运行生成.env后，在.env填写MYSQL_PASSWORD
docker compose up --build -d
docker compose ps
docker compose logs backend ai
```

数据库端口不直接暴露；后端仅绑定本机8010。远程访问通过反向代理配置域名、HTTPS与WebSocket升级。使用 HTTPS 时设置 COOKIE_SECURE=1；代理须保持同一公开来源，并正确转发Host及协议。不要直接对公网开放 AI 端口。

本次本地验收环境没有 Docker，MySQL/Compose 配置和远端工作流实际状态记录在 docs/verification.json。提供配置不等于容器部署已通过验收。

## 备份与恢复

SQLite 维护时先停止后端，再备份 data/emoji.db 和独立保存的.env。恢复时放回原路径，保持同一账户和服务配置。MySQL 使用 mysqldump 等工具备份 emoji 数据库，并验证恢复；不要在运行中直接复制数据库卷目录。

模型文件不包含业务数据，可根据固定哈希重新取得。系统没有需要备份的运行时人脸图片或视频目录。受控测试素材位于 artifacts/，由验证脚本主动生成，不属于采集数据。

## 源码和版本

仓库为 https://github.com/wwhhorizon/classroom-emoji-checker 。需求基线与实现阶段按真实修改提交，开发分支为 implementation/classroom，完成后合并主分支。测试、文档与录制脚本一同管理，不补造成员贡献历史。
