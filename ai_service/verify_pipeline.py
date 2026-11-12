"""Classroom-stage simulation video -> real AI API -> isolated backend verification.

The attributed CREMA-D performance footage is framed as classroom simulation.
It is not a recording of actual students.
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
import cv2
import httpx
from ai_service.classifier import MODEL_VERSION
from ai_service.worker import load_local_env, run

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / 'demo-assets' / 'classroom-expressions.mp4'
MANIFEST = ROOT / 'demo-assets' / 'source-manifest.json'


def prepare() -> tuple[Path, dict]:
    if not VIDEO.is_file() or not MANIFEST.is_file():
        raise FileNotFoundError('请先生成 demo-assets/classroom-expressions.mp4 课堂场景模拟视频及素材来源清单')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    for clip in manifest['clips']:
        original = ROOT / 'demo-assets' / 'source' / clip['file']
        if hashlib.sha256(original.read_bytes()).hexdigest() != clip['sha256']:
            raise ValueError('CREMA-D原始素材哈希校验失败：' + clip['file'])
    capture = cv2.VideoCapture(str(VIDEO))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not capture.isOpened() or fps <= 0:
            raise ValueError('课堂场景视频无法解码')
        seconds = capture.get(cv2.CAP_PROP_FRAME_COUNT) / fps
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    evidence = {
        'fixture_type': 'Classroom-stage simulation using four officially licensed CREMA-D adult-actor performance clips; not a recording of actual students',
        'video': 'demo-assets/classroom-expressions.mp4',
        'video_sha256': hashlib.sha256(VIDEO.read_bytes()).hexdigest(),
        'source_manifest': 'demo-assets/source-manifest.json',
        'source_repository': manifest['repository'],
        'source_license': {'database': manifest['license_database'], 'content': manifest['license_content']},
        'video_seconds': round(seconds, 3), 'video_fps': fps,
        'width': width, 'height': height, 'model_version': MODEL_VERSION,
        'selection_rule': manifest['selection_rule'],
        'source_clip_sampling': 'Every 0.5 seconds of each complete raw clip, without filtering; exact predictions retained in source-manifest.json',
    }
    return VIDEO, evidence


def main():
    load_local_env()
    parser = argparse.ArgumentParser(description='课堂场景模拟视频核验真实推理链路')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--session', type=int, default=1)
    parser.add_argument('--backend', default='', help='显式指定时写入该后端；默认自动创建隔离数据库及8022测试服务')
    parser.add_argument('--ai-url', default='http://127.0.0.1:8011')
    parser.add_argument('--username', default='admin')
    parser.add_argument('--password', default=os.getenv('DEMO_PASSWORD', ''))
    parser.add_argument('--sample-seconds', type=float, default=3)
    parser.add_argument('--max-samples', type=int, default=0, help='0为完整视频')
    args = parser.parse_args()
    video, evidence = prepare()
    print('Classroom simulation video:', video)
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
                                         ai_url=args.ai_url, sample_seconds=args.sample_seconds, threshold=.6,
                                         device_id='classroom-expression-simulation', max_samples=args.max_samples)
        samples = []
        counts = run(worker_args, on_sample=samples.append)
        after_response = client.get('/api/emoji/history', params=query)
        after_response.raise_for_status()
        after = after_response.json()
        saved = [record for record in after['items'] if record.get('device_id') == 'classroom-expression-simulation']
        if counts['sampled'] < 1 or counts['accepted'] < 1 or counts['errors'] or after['total'] - before != counts['accepted']:
            raise RuntimeError('Actual classroom-video->AI->backend persistence check failed: ' + repr(counts))
        evidence.update({'verified_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                         'sample_seconds': args.sample_seconds, 'threshold': .6,
                         'worker_counts': counts, 'records_before': before, 'records_after': after['total'],
                         'samples': samples,
                         'persisted_record_ids': [record['id'] for record in saved],
                         'persisted_records': [{key: record.get(key) for key in
                            ['id', 'emoji', 'confidence', 'timestamp', 'device_id', 'model_version']} for record in saved],
                         'pipeline_passed': True,
                         'scope': 'Integration check on attributed expression performances in a classroom simulation; no classroom recognition accuracy claim'})
        output = ROOT / 'docs' / 'ai-verification.json'
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
