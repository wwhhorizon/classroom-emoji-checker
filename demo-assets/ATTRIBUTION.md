# 课堂场景演示素材来源

本目录的课堂样例由CREMA-D表情视频制作，人物来自数据集中的成年演员。视频保留动态表演，加入教室背景、中文课程环节与素材来源。

来源：Crowd-sourced Emotional Multimodal Actors Dataset（CREMA-D），官方仓库 https://github.com/CheyneyComputerScience/CREMA-D 。原数据库及本次整理的素材子集与元数据依照Open Database License 1.0（ODbL-1.0）提供，原素材单项内容依照Database Contents License 1.0（DbCL-1.0）提供。原仓库LICENSE原文随素材保留在 `source/CREMA-D-LICENSE.txt`。

- 数据库许可：https://opendatacommons.org/licenses/odbl/1.0/
- 单项内容许可：https://opendatacommons.org/licenses/dbcl/1.0/
- 数据集说明及原许可：https://github.com/CheyneyComputerScience/CREMA-D/blob/master/README.md
- 数据集人员元数据：https://github.com/CheyneyComputerScience/CREMA-D/blob/master/VideoDemographics.csv

选用数据集1045号成年演员的NEU、HAP、SAD、ANG四段原始表演。官方元数据记录其采集时年龄22岁，四段来自同一演员。同一人物的不同表演有助于展示时间变化，四段按原素材标签选取。去除英文语音后转换为H.264浏览器视频，原始FLV与其官方Git LFS SHA-256均已保留。

| 原始文件 | 原素材标签 | 转换视频 |
|---|---|---|
| 1045_IEO_NEU_XX.flv | Neutral | source/1045_IEO_NEU_XX.mp4 |
| 1045_IEO_HAP_HI.flv | Happy | source/1045_IEO_HAP_HI.mp4 |
| 1045_IEO_SAD_HI.flv | Sad | source/1045_IEO_SAD_HI.mp4 |
| 1045_IEO_ANG_HI.flv | Anger | source/1045_IEO_ANG_HI.mp4 |

`source-manifest.json`包含每段原始素材的哈希、尺寸、时长、来源链接以及每0.5秒采样的FER+预测。原素材标签、检测状态、置信度与分类结果分别记录。课堂环节与教室背景由scripts/build_classroom_sample.py编排生成。

素材准备可通过 `python -m ai_service.prepare_classroom_assets` 重现。该脚本下载四段官方小文件，核验哈希、转换格式并重新计算全部采样推理结果。执行 `python scripts/build_classroom_sample.py` 生成主视频 `classroom-expressions.mp4`：每段完整循环8秒，原始绿幕替换为绘制教室背景，保留人物表情动态并去除原声。合成顺序、尺寸和哈希见 `composition.json`。

数据集出处：Cao H, Cooper DG, Keutmann MK, Gur RC, Nenkova A, Verma R. CREMA-D: Crowd-sourced Emotional Multimodal Actors Dataset. IEEE Transactions on Affective Computing, 2014, 5(4):377–390. DOI:10.1109/TAFFC.2014.2336244.
