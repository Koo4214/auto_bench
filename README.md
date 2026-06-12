## 开发环境设置


### Windows环境（PowerShell终端）

准备工作：下载并解压ffmpeg，然后把ffmpeg.exe、ffprobe.exe放到项目tools目录下；打包后的软件会内置这两个文件，设置页的 FFmpeg 路径默认留空即可。

```powershell
# 安装独立python环境
python -m venv venv
# 设置python环境变量
$env:PYTHONPATH="$PWD;$env:PYTHONPATH"
# 安装python依赖库
.\venv\Scripts\python.exe -m pip install -r .\requirements.txt
# 运行程序
.\venv\Scripts\python.exe .\src\app\m1_app.py
# 编译打包
.\venv\Scripts\python.exe -m PyInstaller --noconfirm --clean .\auto_bench.spec
```
