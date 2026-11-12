"""Friendly Windows launcher; secrets stay local and are never put in source."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from scripts.dev import load_env

load_env()
print('\n课间晴雨 课堂表情管理\n', flush=True)
print('地址：http://127.0.0.1:8010', flush=True)
print('账号：student / student2 / teacher / teacher2 / admin', flush=True)
print('本地演示密码：' + os.environ['DEMO_PASSWORD'], flush=True)
print('窗口保持打开；结束使用时按 Ctrl+C。\n', flush=True)

def open_browser():
    import urllib.request
    for _ in range(45):
        try:
            urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=1)
            webbrowser.open('http://127.0.0.1:8010')
            return
        except Exception:
            time.sleep(1)

threading.Thread(target=open_browser, daemon=True).start()
try:
    result = subprocess.run([sys.executable, 'scripts/dev.py', '--seed'])
except KeyboardInterrupt:
    pass
