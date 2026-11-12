# 部署与维护

## 本地运行

推荐 Python 3.12。双击“启动课堂表情系统.cmd”，或按 README 创建虚拟环境并安装 requirements.txt、requirements-ai.txt。首次运行 `python scripts/dev.py --seed` 自动生成 `.env` 中的随机服务令牌、注册邀请码和演示密码，初始化账号、课程、课堂和名单，启动8010后端和8011推理服务。

本地 SQLite 位于 `data/emoji.db`。初始化在缺少相应课程时创建课堂，并保留已有账号和历史。课堂时段到期后，管理员新建课堂并安排名单。

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

部署时设置独立的服务令牌、注册邀请码和数据库密码，并通过受限的.env文件管理配置。正式使用前更换初始化账号密码。

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

本地测试采用SQLite，MySQL/Compose及CI的执行记录见docs/verification.json。

## 备份与恢复

SQLite 维护时先停止后端，再备份 data/emoji.db 和独立保存的.env。恢复时放回原路径，保持同一账户和服务配置。MySQL 使用 mysqldump 等工具备份 emoji 数据库，并验证恢复；不要在运行中直接复制数据库卷目录。

模型文件可根据固定哈希重新取得，课堂视频样例及来源位于demo-assets/。业务备份包含数据库和服务配置。

## 源码和版本

仓库为 https://github.com/wwhhorizon/classroom-emoji-checker 。主体实现位于implementation/classroom，演示及材料修订位于polish/lesson-presentation，交付版本合并至main。源码、测试、文档和录制脚本一同管理。
