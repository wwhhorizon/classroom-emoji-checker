# 视频表情推理说明

AI模块使用OpenCV Haar人脸检测器定位正面人脸，将灰度人脸缩放为64×64像素，再调用ONNX Model Zoo发布的FER+卷积网络。推理运行于CPU，与业务后端分别启动。人脸检测和网络推理使用真实模型，未以随机数或规则替代。

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

AI记录默认不关联个人身份，user_id为空，保留课堂、来源AI、置信度、设备标识、事件ID、模型版本和UTC时间。视频中多张脸按独立检测结果记录，不能将样本条数解释为真实上课人数。

```powershell
python -m ai_service.worker --source 0 --session 1
python -m ai_service.worker --source path/to/video.mp4 --session 1 --sample-seconds 3 --threshold 0.6
```

## 服务接口与媒体处理

独立服务在8011端口提供 `POST /infer`，使用 `Authorization: Bearer AI_SERVICE_TOKEN`，接收multipart的file字段，只支持JPEG/PNG，单帧最多2MB、800万像素。返回检测数量和各脸的emoji、confidence、model_version。没有人脸返回空数组，模型缺失或哈希错误返回503。

请求流先检查总大小，再由内存MIME解析器提取文件；未调用会将大文件缓冲至临时磁盘的UploadFile接口。解码图像、采样帧及JPEG仅保留于内存，日志不输出图像、原视频、文件名或完整推理请求。后端只保存结构化结果。项目随附的授权表情素材单独放在demo-assets，用于课堂场景模拟，与运行时采集数据分开。

## 实际验证

`tests/test_ai.py`覆盖七类映射、非法模型输出、图片大小与尺寸、格式错误、无脸真实推理、权重校验、令牌鉴权、模型不可用、请求格式、网络重试及回传幂等负载。实际执行结果由总测试记录汇总。

演示采用CREMA-D官方授权的动态表情素材，选取同一22岁成年演员的Neutral、Happy、Sad、Anger四段完整表演。四段按素材标签事先确定，未根据模型输出筛选。原始FLV共约1.2MB，逐段核验官方Git LFS SHA-256后转为H.264，加入中文课程环节框架，形成 `demo-assets/classroom-expressions.mp4`。画面持续显示“课堂场景模拟”和CREMA-D素材来源。原数据库及选取子集按ODbL-1.0提供，单项内容按DbCL-1.0提供，原许可与来源说明随素材附带。

`python -m ai_service.prepare_classroom_assets`可重新取得四段官方素材、校验哈希，并对每段完整视频从第0帧开始每0.5秒执行真实检测与分类。`demo-assets/source-manifest.json`保留全部检测结果，包括低置信结果及原表演标签与模型输出不一致的样本。本次原始片段检查中，Happy表演随动作变化产生neutral、surprised、happy输出，Sad表演主要识别为neutral，Anger表演主要识别为surprised；这些结果均保留。

`python -m ai_service.verify_pipeline --prepare-only`检查合成视频与原素材哈希。运行 `python -m ai_service.verify_pipeline --session 1` 会自动创建独立测试数据库和8022后端，完整读取课堂场景模拟视频，调用已运行的8011独立AI服务，输出 `docs/ai-verification.json`。本次32秒、1280×720、15fps合成视频每3秒采样一次，共11帧，检测到11张人脸，9条通过0.6阈值并入库，2条被过滤，接口错误为0。9秒处surprised置信度0.575404、12秒处happy置信度0.496400均被过滤；所有逐帧类别与置信度仍保留在JSON的samples字段。日常8010数据库不参与该验证。该验证检查真实视频处理与入库链路；原素材为演员表演，未提供真实课堂识别准确率。

## 局限与偏差

FER+训练数据为FER人脸表情数据及众包标签，未针对本校课堂重新训练。摄像头视角、光照、遮挡、脸部尺寸及不同人群的表情习惯会影响结果。正面Haar检测对侧脸和口罩的适应性有限；表情类别也不能直接证明理解程度或学生的心理状态。教师看板分别展示主动反馈和AI观察结果，教学判断应结合课堂互动及学生主动反馈。

## 官方来源

- ONNX模型说明及输入输出约定：https://github.com/onnx/models/tree/main/validated/vision/body_analysis/emotion_ferplus
- FER+原项目与MIT许可：https://github.com/microsoft/FERPlus
- OpenCV人脸检测器：https://github.com/opencv/opencv/tree/4.x/data/haarcascades
- CREMA-D素材、人口元数据及许可：https://github.com/CheyneyComputerScience/CREMA-D
