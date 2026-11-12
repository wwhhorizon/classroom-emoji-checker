"""Build the submission archive, excluding credentials and local runtime state."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.venv','data','artifacts','__pycache__','.pytest_cache'}
SUFFIXES={'.pyc','.log','.aux','.toc','.out','.synctex.gz'}


def main():
    evidence=ROOT/'deliverables'/'test-evidence';evidence.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'artifacts'/'pytest-results.xml',evidence/'pytest-results.xml')
    for name in ['verification.json','browser-verification.json','ai-verification.json','performance.json','demo-verification.json','camera-verification.json','ci-verification.json']:
        path=ROOT/'docs'/name
        if path.exists():shutil.copy2(path,evidence/name)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    info='''# 课堂表情管理大作业提交说明

项目：课间晴雨（表情符号课堂情绪检查器系统）。

小组成员：袁谦朗 PB23111711、吴卫昊 PB23111689、李阳 PB23050986、吕祖灿 PB23111729。

- 实验报告：deliverables/表情符号课堂情绪检查器系统实验报告.pdf
- LaTeX源码：deliverables/latex-report/report.tex（附图片资源）
- 中文解说演示：deliverables/课堂表情管理-中文解说演示.mp4
- 专用课堂样例：demo-assets/classroom-expressions.mp4（附授权、原始素材及实际推理记录）
- 测试证据：deliverables/test-evidence/，完整说明见docs/testing.md
- 本地运行：安装Python3.12后双击“启动课堂表情系统.cmd”，首次运行需联网安装依赖。模型权重已包含，首次初始化零表情记录。
- 账号密码：首次运行随机生成并在启动窗口提示，保存在运行机器本地.env；本包不附带已有密码、学生记录或本机数据库。
- 三种角色和操作流程：README.md、docs/user-manual.md、docs/demo.md。
- 源码仓库：https://github.com/wwhhorizon/classroom-emoji-checker

演示课程为“软件工程实践 · 需求分析与用例建模”，丁老师授课，袁谦朗、吴卫昊、李阳、吕祖灿参加。视频依次展示注册、课堂安排、四人反馈、实时看板、视频采样、统计导出和账号维护。

提交包以“四人组”命名，MANIFEST-SHA256.txt列出源码提交号和文件哈希。
'''
    (ROOT/'提交说明.md').write_text(info,encoding='utf-8')
    target=ROOT.parent/'SE-EmojiChecker-四人组-最终提交.zip'
    files=[]
    for path in sorted(ROOT.rglob('*')):
        relative=path.relative_to(ROOT)
        if not path.is_file() or any(p in EXCLUDED for p in relative.parts):continue
        if path.name=='.env' or path.suffix in SUFFIXES or path.name.endswith('.synctex.gz'):continue
        if relative.as_posix()=='deliverables/latex-report/report.pdf':continue
        files.append(path)
    manifest='Source commit: '+commit+'\n'+'\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix() for p in files)+'\n'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in files:z.write(path,'emoji-checker/'+path.relative_to(ROOT).as_posix())
        z.writestr('emoji-checker/MANIFEST-SHA256.txt',manifest.encode('utf-8'))
    with zipfile.ZipFile(target) as z:
        if z.testzip():raise RuntimeError('Archive integrity check failed')
        if any(Path(n).name=='.env' or '/.venv/' in n or '/data/' in n or '/.git/' in n for n in z.namelist()):raise RuntimeError('Private runtime state leaked into archive')
    print(json.dumps({'archive':str(target),'files':len(files)+1,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()},ensure_ascii=False))


if __name__=='__main__':main()
