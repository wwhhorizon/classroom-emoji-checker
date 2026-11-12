"""Fetch the official FER+ weights, verifying the Git LFS SHA-256."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import urllib.request

MODEL_NAME = 'emotion-ferplus-8.onnx'
MODEL_URL = ('https://media.githubusercontent.com/media/onnx/models/main/'
             'validated/vision/body_analysis/emotion_ferplus/model/' + MODEL_NAME)
MODEL_SHA256 = 'a2a2ba6a335a3b29c21acb6272f962bd3d47f84952aaffa03b60986e04efa61c'
MODEL_SIZE = 35040571
DEFAULT_PATH = Path(__file__).parent / 'models' / MODEL_NAME


def verify_model(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size != MODEL_SIZE:
        return False
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest() == MODEL_SHA256


def download(path: Path = DEFAULT_PATH) -> Path:
    path = Path(path)
    if verify_model(path):
        print('FER+ weights verified:', path)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.onnx.download')
    try:
        digest = hashlib.sha256()
        total = 0
        request = urllib.request.Request(MODEL_URL, headers={'User-Agent': 'EmojiChecker-model-installer/1.0'})
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open('wb') as target:
            while block := response.read(256 * 1024):
                total += len(block)
                if total > MODEL_SIZE:
                    raise ValueError('Downloaded weights exceed the official file size')
                target.write(block)
                digest.update(block)
        if total != MODEL_SIZE or digest.hexdigest() != MODEL_SHA256:
            raise ValueError('FER+ weights failed size/SHA-256 verification')
        os.replace(temporary, path)
        print('FER+ weights downloaded and verified:', path)
        return path
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    download()
