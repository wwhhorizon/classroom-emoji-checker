# 测试用例与验收记录

本次验收环境为Windows、Python 3.12、SQLite、Chromium和OpenCV CPU。各脚本使用独立数据库，执行时间见 verification.json。

## 自动化结果

pytest共52项，失败0项，错误0项，跳过0项，用时42.01秒。包含34项后端、业务及安全测试和18项AI测试。JUnit原始记录为artifacts/pytest-results.xml（提交包内复制到测试证据目录）。

| 类别 | 核心用例及预期 |
|---|---|
| 账号 | 三类注册、邀请码、两字中文姓名、用户名长度、弱密码、加盐哈希、登录失败限速 |
| 会话 | 退出、改密、账号停用立即失效；WebSocket期间过期或停用也断开 |
| 名单 | 有效学生、重复和非学生拒绝、版本冲突、提交与修改串行 |
| 时间 | 未开始和已结束不能人工提交；AI事件时间范围和新鲜度校验 |
| 范围 | 学生只本人；教师只所授课堂；学生不能进入管理接口 |
| 表情 | 枚举、来源、历史分页、统计分布、同一筛选范围 |
| CSV | BOM、公式前缀转义、导出权限与审计 |
| AI入库 | 独立令牌、阈值、事件幂等、冲突事件、可选学生关联范围 |
| 图像 | JPEG/PNG、大小和像素限制、无脸、模型缺失、全程内存 |
| 推理 | 七类概率映射、官方模型SHA256、空白图与动态视频链路 |
| 重试 | 429/网络/5xx退避、永久错误终止、相同事件负载重试 |
| 文档 | 本地Swagger资源、严格CSP、接口定义可显示，不依赖CDN |

## 浏览器端到端

1. 注册学生账号
2. 三角色登录；初始表情记录为零
3. 管理员创建课程、课堂时段及三人名单
4. 两名学生提交三条反馈，个人历史隔离
5. 教师实时看板无需刷新收到第四条反馈
6. 课程、班级、时间组合筛选与四条记录CSV导出
7. 账号停用阻止登录，启用后恢复
8. 浏览器修改密码并重新登录
9. 学生与非任课教师越权被后端拒绝
10. 390像素手机界面无横向溢出，表单与按钮有可读标签
11. 导出与课堂安排操作审计可查

浏览器结果为通过，JavaScript页面错误为0。原始记录与截图索引位于 browser-verification.json。下载CSV经解析，确认UTF-8 BOM及四条人工记录。

可访问性检查覆盖登录、教师看板、统计分析和390像素手机学生页：可见表单控件有标签、按钮有名称、页面无整体横向溢出。另检查三角色桌面和手机截图、名单对话框及摄像头停止状态。

## 视频采样

课堂样例采用CREMA-D动态表情素材，依次展示四个教学环节。视频长32.0秒，每3秒采样一次；worker采样11帧、检测11张人脸、保存9条记录、过滤2条低置信度结果，错误0项。哈希、逐帧结果及入库记录见ai-verification.json，来源见demo-assets/ATTRIBUTION.md。模型局限与误判分析见ai-model.md及实验报告。

独立脚本与浏览器本地视频分别验证worker和网页采样路径。演示课程由丁老师授课，袁谦朗、吴卫昊、李阳、吕祖灿分别提交反馈。最终包含4条人工记录、7条AI记录、4名参与学生；CSV导出11条，记录见demo-verification.json。

摄像头路径通过Chromium测试媒体设备输入执行getUserMedia，调用独立AI服务并保存1条记录。停止后视频轨道全部结束，结果见camera-verification.json。

## 性能

50条记录、100次历史查询，每页20条，分别测量1与10并发；P50、P95、最大延迟和吞吐见 performance.json。

## 部署验证状态

本地SQLite流程已验证。MySQL建表脚本与Compose配置已提供，Docker环境未执行；远程CI任务因GitHub账号账单锁定未启动，详情见ci-verification.json。

## 复现

```powershell
python -m pytest -q --junitxml=artifacts/pytest-results.xml
python scripts/browser_verify.py
python -m ai_service.verify_pipeline --session 1
python scripts/camera_verify.py
python scripts/performance.py
python scripts/record_demo.py --dry-run
```

AI与浏览器脚本需要8011独立服务运行，浏览器脚本另需安装Chromium。使用本机Edge时设置DEMO_BROWSER_CHANNEL=msedge。录制和素材生成依赖 requirements-video.txt。
