# 课堂场景演示素材来源

本目录包含由CREMA-D公开授权表情视频制作的课堂场景模拟素材。人物为数据集中的成年演员，视频没有采集实际学生或真实课堂。主体表演保留原始动态，主画面加入中文课程环节、模拟场景说明与来源标注。

来源：Crowd-sourced Emotional Multimodal Actors Dataset（CREMA-D），官方仓库 https://github.com/CheyneyComputerScience/CREMA-D 。原数据库及本次整理的素材子集与元数据依照Open Database License 1.0（ODbL-1.0）提供，原素材单项内容依照Database Contents License 1.0（DbCL-1.0）提供。原仓库LICENSE原文随素材保留在 `source/CREMA-D-LICENSE.txt`。

- 数据库许可：https://opendatacommons.org/licenses/odbl/1.0/
- 单项内容许可：https://opendatacommons.org/licenses/dbcl/1.0/
- 数据集说明及原许可：https://github.com/CheyneyComputerScience/CREMA-D/blob/master/README.md
- 数据集人员元数据：https://github.com/CheyneyComputerScience/CREMA-D/blob/master/VideoDemographics.csv

选用数据集1045号成年演员的NEU、HAP、SAD、ANG四段原始表演。官方元数据记录其采集时年龄22岁，四段来自同一演员。同一人物的不同表演有助于展示时间变化，四段均事先按原标签选定，没有按模型预测结果挑选。去除英文语音后转换为H.264浏览器视频，原始FLV与其官方Git LFS SHA-256均已保留。

| 原始文件 | 原素材标签 | 转换视频 |
|---|---|---|
| 1045_IEO_NEU_XX.flv | Neutral | source/1045_IEO_NEU_XX.mp4 |
| 1045_IEO_HAP_HI.flv | Happy | source/1045_IEO_HAP_HI.mp4 |
| 1045_IEO_SAD_HI.flv | Sad | source/1045_IEO_SAD_HI.mp4 |
| 1045_IEO_ANG_HI.flv | Anger | source/1045_IEO_ANG_HI.mp4 |

`source-manifest.json`包含每段原始素材的哈希、尺寸、时长、来源链接以及每0.5秒采样的全部真实FER+预测。原素材的表演标签与模型实际输出独立保留，包括未检测、低置信结果及误判。课堂环节属于演示编排，不是原数据集的采集场景；界面与视频中的“课堂场景模拟”标识用于说明这一点。

素材准备可通过 `python -m ai_service.prepare_classroom_assets` 重现。该脚本下载四段官方小文件，核验哈希、转换格式并重新计算全部采样推理结果。执行 `python scripts/build_classroom_sample.py` 生成主视频 `classroom-expressions.mp4`：每段完整循环8秒，原始绿幕替换为绘制教室背景，保持人物表情动态，去除原声；不加入模型预测文字。合成顺序、尺寸和哈希见 `composition.json`。

数据集出处：Cao H, Cooper DG, Keutmann MK, Gur RC, Nenkova A, Verma R. CREMA-D: Crowd-sourced Emotional Multimodal Actors Dataset. IEEE Transactions on Affective Computing, 2014, 5(4):377–390. DOI:10.1109/TAFFC.2014.2336244.
