# 编译实验报告

安装TeX Live与中文字体包后，在当前目录执行两遍：

```powershell
xelatex -interaction=nonstopmode -halt-on-error report.tex
xelatex -interaction=nonstopmode -halt-on-error report.tex
```

图片资源位于assets/，均为项目真实运行截图。报告不包含参考文献或个人贡献比例。主项目中的scripts/build_report.py根据实测JSON与JUnit结果重建本文件。
