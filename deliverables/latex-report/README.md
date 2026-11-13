# 编译实验报告

安装TeX Live与中文字体包后，在当前目录执行两遍：

```powershell
xelatex -interaction=nonstopmode -halt-on-error report.tex
xelatex -interaction=nonstopmode -halt-on-error report.tex
```

图片资源位于assets/，数据库ER图附矢量PDF和可编辑SVG。scripts/build_report.py根据验收JSON与JUnit结果生成报告；重新生成ER图需安装requirements-report.txt中的依赖。
