"""Controlled public-domain video -> real AI API -> backend persistence verification.

The generated sample is visibly marked and is not a recording of a classroom.
python -m ai_service.verify_pipeline --prepare-only
python -m ai_service.verify_pipeline --session 1
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

import httpx
from PIL import Image, ImageDraw

from ai_service.classifier import MODEL_VERSION, EmotionClassifier
from ai_service.worker import load_local_env, run

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_URL = 'https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/astronaut.png'
FIXTURE_SHA256 = '88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5'
FIXTURE_DIR = ROOT / 'artifacts' / 'ai-fixture'


def prepare() -> tuple[Path, Path, dict]:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    image_path = FIXTURE_DIR / 'astronaut.png'
    if not image_path.exists():
        request = urllib.request.Request(FIXTURE_URL, headers={'User-Agent': 'EmojiChecker-test-fixture/1.0'})
        image_path.write_bytes(urllib.request.urlopen(request, timeout=45).read())
    if hashlib.sha256(image_path.read_bytes()).hexdigest() != FIXTURE_SHA256:
        raise ValueError('Public-domain source image failed SHA-256 verification')
    preview = FIXTURE_DIR / 'astronaut-controlled-preview.png'
    with Image.open(image_path) as image:
        image = image.convert('RGB')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, image.height - 29, image.width, image.height), fill=(20, 29, 42))
        draw.text((12, image.height - 20), 'CONTROLLED VIDEO INPUT  |  NASA PUBLIC-DOMAIN PHOTO', fill='white')
        image.save(preview)
    video = FIXTURE_DIR / 'astronaut-controlled.mp4'
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
                    '-loop', '1', '-framerate', '12', '-i', str(preview), '-t', '12',
                    '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    str(video)], check=True)
    inference = EmotionClassifier().infer(image_path.read_bytes())
    evidence = {'fixture_type': 'Controlled 12-second video encoded from one public-domain NASA photo; not a classroom recording',
                'source_url': FIXTURE_URL, 'source_sha256': FIXTURE_SHA256,
                'license_source': 'https://github.com/scikit-image/scikit-image/blob/v0.25.2/skimage/data/_fetchers.py',
                'video_seconds': 12, 'video_fps': 12, 'model_version': MODEL_VERSION,
                'image_inference': inference}
    (FIXTURE_DIR / 'provenance.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    return image_path, video, evidence


def main():
    load_local_env()
    parser = argparse.ArgumentParser(description='使用公开标注样图形成的受控视频核验真实推理链路')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--session', type=int, default=1)
    parser.add_argument('--backend', default='', help='显式指定时写入该后端；默认自动创建隔离数据库及8022测试服务')
    parser.add_argument('--ai-url', default='http://127.0.0.1:8011')
    parser.add_argument('--username', default='admin')
    parser.add_argument('--password', default=os.getenv('DEMO_PASSWORD', ''))
    args = parser.parse_args()
    image, video, evidence = prepare()
    print('Prepared controlled sample:', video)
    if args.prepare_only:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return
    from scripts.fixture_server import fixture_server
    context = nullcontext((args.backend, args.password, None)) if args.backend else fixture_server(name='ai-integration', port=8022)
    with context as (base, password, database):
        args.backend = base
        args.password = password
        evidence['isolated_database'] = database.name if database else None
        verify(args, video, evidence)


def verify(args, video, evidence):
    with httpx.Client(base_url=args.backend, timeout=35, headers={'X-Requested-With': 'EmojiApp'}) as client:
        login = client.post('/api/auth/login', json={'username': args.username, 'password': args.password})
        login.raise_for_status()
        query = {'session_id': args.session, 'source': 'AI', 'page_size': 100}
        before_response = client.get('/api/emoji/history', params=query)
        before_response.raise_for_status()
        before = before_response.json()['total']
        worker_args = argparse.Namespace(source=str(video), session=args.session, backend=args.backend,
                                         ai_url=args.ai_url, sample_seconds=3, threshold=.6,
                                         device_id='controlled-nasa-video', max_samples=3)
        counts = run(worker_args)
        after_response = client.get('/api/emoji/history', params=query)
        after_response.raise_for_status()
        after = after_response.json()
        saved = [record for record in after['items'] if record.get('device_id') == 'controlled-nasa-video']
        if counts['sampled'] != 3 or counts['accepted'] < 1 or after['total'] - before != counts['accepted']:
            raise RuntimeError('Actual video->AI->backend persistence check failed: ' + repr(counts))
        evidence.update({'verified_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                         'worker_counts': counts, 'records_before': before, 'records_after': after['total'],
                         'persisted_record_ids': [record['id'] for record in saved[:counts['accepted']]],
                         'pipeline_passed': True,
                         'scope': 'Integration check only; no labeled classroom evaluation or accuracy claim'})
        output = ROOT / 'docs' / 'ai-verification.json'
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
