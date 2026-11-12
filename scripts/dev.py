"""Start backend and independent AI service; Ctrl+C stops both processes."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time


def load_env():
    path=Path('.env')
    if not path.exists():
        path.write_text('\n'.join([f'AI_SERVICE_TOKEN={secrets.token_urlsafe(32)}',
            f'ADMIN_INVITE_CODE={secrets.token_urlsafe(16)}',f'TEACHER_INVITE_CODE={secrets.token_urlsafe(16)}',
            f'DEMO_PASSWORD=Class-{secrets.token_urlsafe(12)}9','AI_CONFIDENCE_THRESHOLD=0.6','AI_SAMPLE_SECONDS=3'])+'\n',encoding='utf-8')
    for line in path.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#') and '=' in line:
            key,value=line.split('=',1);os.environ.setdefault(key,value)


def main():
    os.chdir(Path(__file__).resolve().parents[1])
    parser=argparse.ArgumentParser();parser.add_argument('--seed',action='store_true')
    parser.add_argument('--port',type=int,default=8010);parser.add_argument('--ai-port',type=int,default=8011)
    parser.add_argument('--backend-only',action='store_true');args=parser.parse_args()
    load_env();os.environ.setdefault('AI_URL',f'http://127.0.0.1:{args.ai_port}')
    if args.seed:subprocess.run([sys.executable,'-m','app.seed'],check=True)
    processes=[]
    try:
        processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(args.port)]))
        if not args.backend_only:
            processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','ai_service.main:app','--host','127.0.0.1','--port',str(args.ai_port)]))
        print(f'浏览器打开 http://127.0.0.1:{args.port}；接口文档 /docs；配置 .env',flush=True)
        while all(p.poll() is None for p in processes):time.sleep(1)
    except KeyboardInterrupt:pass
    finally:
        for p in processes:
            if p.poll() is None:p.terminate()
        for p in processes:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill()


if __name__=='__main__':main()
