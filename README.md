# 课间晴雨

表情符号课堂情绪检查器系统。学生选择表情反馈课程感受，教师查看所授课堂的实时分布和历史，管理员维护课程、课堂时间和学生名单，筛选统计并导出 CSV。独立 AI 服务对摄像头或本地视频采样，以人脸检测和 FER+ 模型给出匿名表情记录。

软件工程实践大作业，对应工作区中的《表情符号课堂情绪检查器系统》实验指导书。

## 快速运行

Windows 安装 Python 3.12 后，双击 `启动课堂表情系统.cmd`。首次运行会创建虚拟环境、安装依赖、确认模型文件并初始化账号、课程、课堂和名单，然后启动两个服务。首次初始化没有任何表情记录。

也可在 PowerShell 中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-ai.txt
.\.venv\Scripts\python.exe -m ai_service.download_model
.\.venv\Scripts\python.exe scripts/dev.py --seed
```

浏览器打开 <http://127.0.0.1:8010>；接口文档 <http://127.0.0.1:8010/docs>。独立推理服务位于8011。终端保持运行，按 Ctrl+C 关闭。

账号为 `student`、`student2`、`teacher`、`teacher2`、`admin`。首次启动随机生成密码，保存在本地 `.env` 的 `DEMO_PASSWORD` 中。教师和管理员注册分别需要 `.env` 中的 `TEACHER_INVITE_CODE` 和 `ADMIN_INVITE_CODE`。`.env` 不提交到源码仓库。

初始课堂是初始化时的当前时段，第二天演示请通过管理员新建当前时段课堂并安排学生。重复启动保留原数据，不修改旧课堂时间或密码。

## 功能

- 学生注册、登录、改密；在排课时段内提交七类表情；查询本人历史。
- 教师查看所授课堂；实时分布、分钟趋势与多维筛选；摄像头或本地视频采样。
- 管理员管理用户、课程、课堂、时段名单；版本冲突保护；CSV 导出与审计。
- bcrypt 密码哈希、可吊销 Session、后端 RBAC 与课程范围校验、写入来源校验、安全 CSV。
- 本地 Haar 人脸检测及 FER+ ONNX 推理；独立服务令牌；阈值过滤、匿名记录、事件去重与断线重试。
- 原始图像与视频仅在内存处理，默认不保存。AI 观测次数和人工反馈次数在界面中分别展示。
- 电脑及手机浏览器界面；MySQL Compose 配置；本地 SQLite 直接运行。

## 测试与演示

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/export_contract.py
```

演示围绕丁老师的“需求分析与用例建模”课堂展开，袁谦朗、吴卫昊、李阳、吕祖灿依次完成注册、课堂反馈和历史查询，随后展示教师看板、视频表情识别和统计导出。录制方法见 [演示说明](docs/demo.md)，视频素材来源及制作步骤见 [素材说明](demo-assets/ATTRIBUTION.md)。

## 文档与提交材料

| 材料 | 位置 |
|---|---|
| 需求规格与验收条件 | [docs/requirements.md](docs/requirements.md) |
| 架构、修改版 MVC、ER 与顺序图 | [docs/design.md](docs/design.md) |
| 指导书逐项对照 | [docs/traceability.md](docs/traceability.md) |
| API 与 OpenAPI | [docs/api.md](docs/api.md)、[docs/openapi.json](docs/openapi.json) |
| AI 模型、来源与局限 | [docs/ai-model.md](docs/ai-model.md) |
| 部署说明 | [docs/deployment.md](docs/deployment.md) |
| 用户手册 | [docs/user-manual.md](docs/user-manual.md) |
| 测试用例与实测记录 | [docs/testing.md](docs/testing.md)、[docs/verification.json](docs/verification.json) |
| 沿用的要求与 skills | [docs/continuity.md](docs/continuity.md) |
| 中文解说演示 | deliverables/课堂表情管理-中文解说演示.mp4 |
| 实验报告与 LaTeX | deliverables/表情符号课堂情绪检查器系统实验报告.pdf、deliverables/latex-report/ |

## 项目结构

```text
app/            路由、业务服务、范围查询、关系实体、浏览器界面
ai_service/     模型下载、推理服务、摄像头或视频采样 worker
database/       MySQL 建表脚本
tests/          业务、权限、安全与AI测试
scripts/        启动、契约导出、浏览器验证、演示与报告制作
docs/           需求、设计、接口、测试、部署、手册
deliverables/   PDF、LaTeX源码与中文解说视频
```

源码仓库：<https://github.com/wwhhorizon/classroom-emoji-checker>。

成员：袁谦朗 PB23111711、吴卫昊 PB23111689、李阳 PB23050986、吕祖灿 PB23111729。
