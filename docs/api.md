# API 使用说明

API 版本为 1.0.0。开发地址 `http://127.0.0.1:8010`，Swagger 位于 `/docs`，可机读契约为 `docs/openapi.json`。完整字段、约束与错误响应以导出契约和 `schemas.py` 为准。

## 认证

登录返回 `user` 和 `access_token`，同时设置 `emoji_session` HttpOnly Cookie。浏览器请求自动带 Cookie；其他客户端可使用 `Authorization: Bearer <access_token>`。写请求增加 `X-Requested-With: EmojiApp`，跨来源写入被拒绝。AI 回传使用独立 `AI_SERVICE_TOKEN`，不使用用户会话。

登录示例：

```http
POST /api/auth/login
Content-Type: application/json
X-Requested-With: EmojiApp

{"username":"student","password":"本地生成的演示密码"}
```

成功响应按接口返回对象或数组；错误统一为 `{"code":"HTTP_403","message":"需要管理员权限"}`。主要状态码：401 未登录或令牌失效，403 角色/来源不符，404 无相应数据范围，409 版本或状态冲突，422 字段/时间不合法，429 登录限速，503 AI 暂不可用。

## 接口分组

| 方法与路径 | 使用者 | 说明 |
|---|---|---|
| POST /api/auth/register | 未登录 | 学生自注册；教师/管理员需邀请码 |
| POST /api/auth/login、logout | 用户 | 建立或吊销会话 |
| PUT /api/auth/password | 用户 | 原密码与新密码；修改后重新登录 |
| GET /api/users/me | 用户 | 当前账号 |
| GET /api/courses、/api/sessions | 用户 | 返回角色可见课程及课堂 |
| POST /api/admin/courses | 管理员 | 课程关联有效教师 |
| POST /api/admin/sessions | 管理员 | 新建含时段、班级和教室的课堂 |
| PUT /api/admin/sessions/{id} | 管理员 | 带 version 更新课堂 |
| GET、POST /api/admin/sessions/{id}/schedule | 管理员 | 查看或全量替换学生名单 |
| POST /api/emoji | 学生 | 在已安排的进行中课堂提交表情 |
| GET /api/emoji/history | 用户 | 分页查询，角色及记录归属约束 |
| GET /api/emoji/statistics | 用户 | 同一数据范围的汇总 |
| GET /api/admin/statistics | 教师/管理员 | 多维筛选统计 |
| GET /api/admin/dashboard/realtime | 教师/管理员 | sessionId 指定课堂 |
| WebSocket /ws/dashboard | 教师/管理员 | sessionId 查询参数，每两秒推送汇总 |
| GET /api/admin/emoji/export | 管理员 | 过滤范围内 CSV |
| GET、PUT /api/admin/users[/{id}] | 管理员 | 账号列表及状态 |
| GET /api/admin/audit | 管理员 | 最近100条审计 |
| GET /api/ai/config | 教师/管理员 | 阈值及采样秒数 |
| POST /api/ai/frame?session_id=... | 任课教师/管理员 | multipart file；内存帧代理与结果入库 |
| POST /api/ai/emoji-results | AI 服务 | JSON 结果回传；独立令牌 |

## 筛选与时间

历史、统计和 CSV 支持 `session_id`、`course`（课程ID）、`class_name`、`from`、`to`、`source`；历史额外支持 `page` 与 `page_size`（1～100）。时间必须含时区，例如 `2026-11-12T00:00:00+08:00`；URL 中加号应编码。输出时间统一带 `Z`。起止时间均包含边界。

统计返回 total、manual、ai、participants、distribution、trend、courses、classes。participants 为有身份的不同学生数，匿名 AI 不计入人数。trend 按记录时间聚合为 UTC 分钟桶。

WebSocket 消息结构为 `{"type":"statistics","data":{...}}`。握手与每轮推送核对会话和课堂访问范围；不接受学生连接。浏览器在切换课堂或退出时关闭旧连接。

## AI 事件

```json
{
  "session_id": 1,
  "emoji": "happy",
  "confidence": 0.94,
  "timestamp": "2026-11-12T03:00:00Z",
  "device_id": "classroom-camera-1",
  "event_id": "每次观测唯一的UUID",
  "model_version": "emotion-ferplus-8"
}
```

示例时间需替换为实际课堂时段内的采样时间。事件必须新鲜、所属课堂正在进行，且情绪和置信度有效。低于阈值返回 `accepted:false`；重复相同事件返回原记录；相同事件编号配不同内容返回409。默认省略 user_id，保存匿名记录。

独立 AI 服务在 `http://127.0.0.1:8011`，`POST /infer` 接收 multipart `file` 与独立令牌，只返回人脸数、情绪、分数和模型版本；`/health` 报告模型状态。两侧限制输入大小，服务不提供图像下载或持久化接口。
