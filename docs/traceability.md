# 指导书验收对照

| 指导书条目 | 实现位置 | 验收方式 |
|---|---|---|
| 学生注册、登录、改密 | app/main.py、schemas.py；登录和账号页 | 后端测试；浏览器注册与改密 |
| 学生发送 emoji 与个人历史 | POST /api/emoji；GET /api/emoji/history | 学生操作后检查本人历史，第二学生隔离 |
| 教师所授课堂历史与统计 | repository.py 课程范围；教师页面 | teacher 与 teacher2 交叉访问拒绝 |
| 课堂、课程与特定时间用户列表 | Course、ClassSession、ScheduleUser | 管理员新建课堂、替换名单、版本冲突 |
| 用户查看与管理 | GET/PUT /api/admin/users | 教师及学生访问拒绝；停用会话失效 |
| 实时课堂汇总与趋势 | /api/admin/dashboard/realtime；/ws/dashboard | 两个浏览器会话提交与接收更新 |
| 课程、班级、时间多维图表 | /api/admin/statistics；统计页 | 组合筛选与导出记录数对照 |
| CSV 导出与注入防护 | services.export_csv/safe_cell | BOM、公式前缀、权限、筛选测试 |
| 修改版 MVC 和分层 | 浏览器 model/view/controller；Controller/Service/Repository | docs/design.md、报告架构图 |
| 关系数据库及核心实体 | app/models.py、database/schema.sql | SQLite 实际测试；提供 MySQL 建表与部署配置 |
| Session 与 RBAC | main.current_user/admin/teacher_or_admin | 越权、会话吊销、停用与WebSocket测试 |
| 统一错误与 OpenAPI | main.py 异常处理；/docs；docs/openapi.json | 输入验证和接口契约导出 |
| 视频采样、检测、分类 | ai_service/worker.py 与推理模块；浏览器采样 | worker与网页视频采样、摄像头getUserMedia链路验证，结果经后端入库 |
| 至少五类情绪 | 七类 emoji 映射 | 模型输出8类，contempt与neutral合并 |
| 配置阈值与采样频率 | AI_CONFIDENCE_THRESHOLD、AI_SAMPLE_SECONDS | 高低阈值边界与采样配置测试 |
| AI 来源、时间、课堂与置信度 | EmojiRecord；/api/ai/emoji-results | 持久化字段与事件幂等测试 |
| 默认不保存原始人脸与视频 | 内存采样、内存解码、无图像存储表 | 代码检查、测试时目录对照 |
| 断线重试与日志 | AI worker | 异常退避和事件重试测试 |
| 单元、接口、端到端、安全、可用性 | tests/、scripts/browser_verify.py | docs/verification.json 和实际记录 |
| API、设计、测试、部署、用户手册 | docs/ | 文档、可运行命令与运行结果核对 |
| 演示视频5～8分钟 | deliverables/ | 中文解说、实际浏览器录制、视频时长检查 |
| 实验报告及AI局限分析 | deliverables/latex-report/report.tex 与 PDF | 编译、逐页查看、与实测结果核对 |
| Git 分支管理 | GitHub 源码仓库 | 按实现阶段提交，开发分支合并main |

成员信息按已确认的提交范围列姓名和学号。

选做内容包括 Docker Compose、CI 配置和匿名 AI 聚合。MySQL、Compose 和远端 CI 的执行状态见测试记录。
