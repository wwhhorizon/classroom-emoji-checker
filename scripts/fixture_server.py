"""Disposable application databases for browser verification and recording."""
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.dev import load_env


@contextmanager
def fixture_server(name='browser', port=8020):
    os.chdir(ROOT)
    load_env()
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', port)) == 0:
            raise RuntimeError(f'Port {port} is already in use; choose an unused test port')
    target = ROOT / 'data' / f'{name}-{datetime.now():%Y%m%d-%H%M%S-%f}.db'
    target.parent.mkdir(exist_ok=True)
    env = os.environ.copy()
    env['DATABASE_URL'] = 'sqlite:///' + target.as_posix()
    env['AI_URL'] = 'http://127.0.0.1:8011'
    env['PYTHONIOENCODING'] = 'utf-8'
    subprocess.run([sys.executable, '-m', 'app.seed'], cwd=ROOT, env=env, check=True, capture_output=True)
    logpath = ROOT / 'artifacts' / f'{name}-server.log'
    logpath.parent.mkdir(exist_ok=True)
    log = logpath.open('w', encoding='utf-8')
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
        '--port', str(port)], cwd=ROOT, env=env, stdout=log, stderr=log,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    import httpx
    base = f'http://127.0.0.1:{port}'
    try:
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError(f'Application did not start: {logpath}')
            try:
                if httpx.get(base + '/health', timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.25)
        else:
            raise RuntimeError('Application startup timed out')
        yield base, env['DEMO_PASSWORD'], target
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
