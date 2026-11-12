# 实现协作契约

项目：课间晴雨 表情符号课堂情绪检查器。根目录 D:/课程/软件工程/emoji-checker。旧 course-project 保留。

## 共用约定

- FastAPI + SQLAlchemy + 原生 JS ES modules；浏览器替代 Android。SQLite 本地；MySQL Compose。
- 三角色 student / teacher / admin；会话 cookie emoji_session；写请求 X-Requested-With: EmojiApp；错误 {code,message}；成功数据直接返回对象或数组。
- emoji 枚举 happy / neutral / sad / surprised / angry / fearful / disgusted（七类）。MANUAL / AI 来源。
- UTC ISO 时间后缀 Z；前端按 Asia/Shanghai 显示；查询 from/to 接收带时区 ISO；后端存 naive UTC。
- 登录用户 {id,username,role,email,active}。演示账号 student / student2 / teacher / teacher2 / admin，密码由本地 .env DEMO_PASSWORD 产生；注册教师/管理员需邀请码。
- 只初始化账号、课程、课堂与名单，不初始化任何表情记录。初始课程软件工程实践、数据库系统；初始课堂当前时间前1小时至后3小时，班级计算机2301/G2-B403。

## API v1（前端/验证共同依赖）

- POST /api/auth/register {username,password,role,email?,invite_code?}；POST login {username,password} -> {user,access_token,token_type}；POST logout；PUT password {old_password,new_password}；GET /api/users/me
- GET /api/courses -> [{id,name,teacher_id,teacher}]，按角色范围。POST /api/admin/courses {name,teacher_id}
- GET /api/sessions -> [{id,course_id,course,teacher_id,teacher,start_at,end_at,class_name,room,scheduled_count,enrolled,version}]，学生限已排课，教师限自己课程。
- POST /api/admin/sessions {course_id,start_at,end_at,class_name,room}；PUT /api/admin/sessions/{id} 同字段加 version。
- GET /api/admin/sessions/{id}/schedule -> [{id,username,role,...}]；POST /api/admin/sessions/{id}/schedule {user_ids:[id...],version} 全量替换仅学生，拒绝重复和无效/停用用户，递增课堂 version。GET /api/admin/users 数组；PUT /api/admin/users/{id} {active}
- POST /api/emoji {session_id,emoji} -> record；必须排课且处于课堂时间。GET /api/emoji/history?session_id=&course=&class_name=&from=&to=&source=&page=1&page_size=20 -> {items:[record],total,page,page_size}，record {id,user_id,username,session_id,course,class_name,emoji,source,confidence,device_id,model_version,timestamp}
- GET /api/emoji/statistics（同上过滤） -> {total,manual,ai,participants,distribution:{happy:0,...},trend:[{minute,total,happy,neutral,...}],courses:[{name,total}],classes:[{name,total}]}。学生仅本人；教师只自己课程；管理员全部。
- GET /api/admin/dashboard/realtime?sessionId=id 与 statistics 结构一致（教师/管理员）；GET /api/admin/statistics 同统计；GET /api/admin/emoji/export 同过滤返回 BOM CSV（仅管理员）。WebSocket /ws/dashboard?sessionId=id，每2秒 {type:'statistics',data:statistics}，cookie 授权，拒绝学生/非自己课堂。
- GET /api/admin/audit -> 最多100条数组。
- POST /api/ai/emoji-results（Authorization: Bearer AI_SERVICE_TOKEN，无需网页校验头）{session_id,emoji,confidence,timestamp,device_id,event_id,model_version,user_id?} -> {accepted:bool,reason?,record?}；阈值默认0.6；当前课堂时间与事件时间校验；event_id 唯一幂等；AI 可匿名 user_id=null。
- GET /api/ai/config（登录教师/管理员） -> {threshold,sample_seconds,model_version?}。
- POST /api/ai/frame?session_id=id（教师/管理员，有该课堂权限）multipart file JPEG/PNG 内存代理到独立 AI /infer；无文件持久化。返回 {detected,accepted,rejected,results:[{emoji,confidence,...}],message?}；无脸为零条，无模型明确503。后端将高置信度结果通过同一入库服务记录；匿名。

## 独立AI服务（AI负责人实现）

- FastAPI ai_service.main:app，127.0.0.1:8011；/health 返回模型是否加载；POST /infer 使用独立令牌、multipart file，限制2MB与图像尺寸，OpenCV Haar 检测 + FER+ ONNX 推理；返回 {detected,results:[{emoji,confidence,model_version}],model_version}，无需后端概念。
- ai_service/worker.py CLI --source 0|path --session ID --backend URL --ai-url URL，采样配置 AI_SAMPLE_SECONDS，阈值 AI_CONFIDENCE_THRESHOLD，网络重试退避，内存jpeg，调用infer与emoji-results，event UUID，匿名。不保存帧/视频。
- 模型本地 ai_service/models/emotion-ferplus-8.onnx；提供 download_model.py ，真实权重随提交包附带；来源记录 LICENSE/模型说明。
- 模型实现与测试由AI负责人处理，前端/后端负责人不得假造分类。

## 文件职责

后端：app/*.py、database/schema.sql、scripts/dev.py、scripts/export_contract.py、compose.yaml、Dockerfile、依赖、tests/test_backend.py。AI：ai_service/**、tests/test_ai.py、requirements-ai.txt、docs/ai-model.md。前端：app/static/**、PRODUCT.md、DESIGN.md、docs/ui-design.md。主代理：其余 docs、端到端脚本、视频、LaTeX、包装与综合验收。
