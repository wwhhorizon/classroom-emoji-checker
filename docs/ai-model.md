# 视频表情推理说明

AI模块使用OpenCV Haar人脸检测器定位正面人脸，将灰度人脸缩放为64×64像素，再调用ONNX Model Zoo发布的FER+卷积网络。推理运行于CPU，与业务后端分别启动。

## 模型与依赖

| 项目 | 采用内容 |
|---|---|
| 情绪模型 | emotion-ferplus-8.onnx，ONNX opset 8 |
| 权重大小 | 35,040,571字节 |
| SHA-256 | a2a2ba6a335a3b29c21acb6272f962bd3d47f84952aaffa03b60986e04efa61c |
| 推理引擎 | OpenCV DNN CPU，opencv-python-headless 4.13.0.92 |
| 人脸定位 | OpenCV自带haarcascade_frontalface_default.xml |
| 模型版本标识 | onnx-ferplus-8-sha256-a2a2ba6a335a |
| 模型许可 | FER+模型说明指定MIT；原始许可随权重附在models/LICENSE-FERPlus.txt |

权重随工程包提供。重新下载时，在项目根目录执行 `python -m ai_service.download_model`。下载器核对官方Git LFS声明的长度和SHA-256，校验成功后才替换目标文件。

输入采用灰度float32，形状为1×1×64×64，像素值保持0～255。八类网络输出先做数值稳定的softmax，再将contempt概率归入neutral；随后在七类概率中选择最大项。因此confidence是映射后的七类概率，七类概率之和为1。

| FER+输出 | 系统emoji类型 | 显示含义 |
|---|---|---|
| neutral及contempt | neutral | 平静 |
| happiness | happy | 开心 |
| surprise | surprised | 惊讶 |
| sadness | sad | 低落 |
| anger | angry | 生气 |
| disgust | disgusted | 反感 |
| fear | fearful | 紧张 |

## 数据流

摄像头或视频 → 按间隔取帧 → 内存JPEG编码 → 独立AI服务检测与分类 → 置信度过滤 → 关联课堂会话 → 后端API入库 → 教师实时看板。

`ai_service.worker`接收摄像头编号或视频路径。默认每3秒采样一次，默认阈值0.6，可通过AI_SAMPLE_SECONDS和AI_CONFIDENCE_THRESHOLD或命令行调整。每张通过过滤的人脸生成独立event_id；同一次回传的重试复用原event_id，由后端唯一约束避免重复入库。网络超时、429和5xx最多尝试5次，等待1、2、4、8秒；401等永久错误直接结束本次提交。一个样本失败后继续下一次采样。后端再次检查置信度与课堂时间。

AI记录默认采用匿名方式，user_id为空，保存课堂、来源AI、置信度、设备标识、事件ID、模型版本和UTC时间。多张人脸分别生成观测记录，教师看板将AI观测次数与参加学生人数分开展示。

```powershell
python -m ai_service.worker --source 0 --session 1
python -m ai_service.worker --source path/to/video.mp4 --session 1 --sample-seconds 3 --threshold 0.6
```

## 服务接口与媒体处理

独立服务在8011端口提供 `POST /infer`，使用 `Authorization: Bearer AI_SERVICE_TOKEN`，接收multipart的file字段，只支持JPEG/PNG，单帧最多2MB、800万像素。返回检测数量和各脸的emoji、confidence、model_version。没有人脸返回空数组，模型缺失或哈希错误返回503。

请求流先检查总大小，再由内存MIME解析器提取文件。解码图像、采样帧及JPEG在内存中处理，后端保存结构化推理结果。运行日志记录事件、耗时和错误状态。演示视频及原始素材位于demo-assets，来源和许可见该目录的ATTRIBUTION.md。

## 集成验证

`tests/test_ai.py`覆盖七类映射、非法模型输出、图片大小与尺寸、格式错误、无脸输入、权重校验、令牌鉴权、模型不可用、请求格式、网络重试及回传幂等负载，测试结果汇总于docs/testing.md。

演示视频采用CREMA-D数据集中Neutral、Happy、Sad、Anger四段动态表情素材，配合课程环节和教室背景，形成 `demo-assets/classroom-expressions.mp4`。原始FLV共约1.2MB，转换格式前核对官方Git LFS SHA-256。数据库许可为ODbL-1.0，单项内容许可为DbCL-1.0，原许可和来源随素材提供。

`python -m ai_service.prepare_classroom_assets`下载四段素材并校验哈希，从第0帧开始每0.5秒检测与分类；结果保存在 `demo-assets/source-manifest.json`。

`python -m ai_service.verify_pipeline --prepare-only`检查视频与原素材哈希。运行 `python -m ai_service.verify_pipeline --session 1` 自动创建测试数据库和8022后端，调用8011推理服务，输出 `docs/ai-verification.json`。本次32秒、1280×720、15fps视频每3秒采样一次，共11帧，检测到11张人脸，9条通过0.6阈值并入库，2条被过滤，接口错误为0。JSON中的samples字段保存每次采样的类别、置信度及处理结果。

## 局限与偏差

FER+基于FER人脸表情数据及众包标签训练。摄像头视角、光照、遮挡和脸部尺寸会影响分类，正面Haar检测器对侧脸和口罩的检测效果较弱。本次素材测试中，Sad表演多次被判为neutral，Anger表演多次被判为surprised。逐帧类别、置信度和阈值处理结果记录于ai-verification.json。教师可结合主动反馈、课堂提问和练习情况解释表情变化。

## 官方来源

- ONNX模型说明及输入输出约定：https://github.com/onnx/models/tree/main/validated/vision/body_analysis/emotion_ferplus
- FER+原项目与MIT许可：https://github.com/microsoft/FERPlus
- OpenCV人脸检测器：https://github.com/opencv/opencv/tree/4.x/data/haarcascades
- CREMA-D素材、人口元数据及许可：https://github.com/CheyneyComputerScience/CREMA-D
