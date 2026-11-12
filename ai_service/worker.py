"""Read a camera/video, sample frames, infer and send anonymous records to the backend.

python -m ai_service.worker --source 0 --session 1
python -m ai_service.worker --source clip.mp4 --session 1 --max-samples 5
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
import math
import os
from pathlib import Path
import time
import uuid

import cv2
import httpx

from ai_service.classifier import MAX_BYTES

logger = logging.getLogger('emoji.ai.worker')


def load_local_env():
    path = Path(__file__).resolve().parents[1] / '.env'
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


def retry_request(client: httpx.Client, method: str, url: str, *, attempts=5, **kwargs):
    """Retain the caller's event_id across retries; do not retry permanent 4xx failures."""
    for attempt in range(attempts):
        try:
            response = client.request(method, url, **kwargs)
            if response.status_code not in {408, 425, 429} and response.status_code < 500:
                response.raise_for_status()
                return response
            response.raise_for_status()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            retryable = isinstance(exc, httpx.TransportError) or exc.response.status_code in {408, 425, 429} or exc.response.status_code >= 500
            if not retryable or attempt == attempts - 1:
                raise
            delay = min(60, 2 ** attempt)
            logger.warning('Service unavailable; retry %s/%s in %ss', attempt + 1, attempts - 1, delay)
            time.sleep(delay)
    raise RuntimeError('unreachable')


def run(args) -> dict:
    token = os.getenv('AI_SERVICE_TOKEN', '')
    if not token:
        raise ValueError('请在.env中配置AI_SERVICE_TOKEN')
    sample_seconds = args.sample_seconds
    threshold = args.threshold
    if not math.isfinite(sample_seconds) or sample_seconds <= 0 or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('采样间隔须大于0，置信度阈值须介于0与1之间')
    source = int(args.source) if str(args.source).isdigit() else args.source
    is_camera = isinstance(source, int)
    camera = cv2.VideoCapture(source)
    if not camera.isOpened():
        raise RuntimeError('无法打开摄像头或视频文件')
    counts = {'sampled': 0, 'detected': 0, 'accepted': 0, 'rejected': 0, 'errors': 0}
    next_sample = 0.0
    frame_number = 0
    fps = camera.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0
    device_id = args.device_id or ('camera-' + str(source) if is_camera else 'video-worker')
    headers = {'Authorization': 'Bearer ' + token}
    try:
        with httpx.Client(timeout=httpx.Timeout(35, connect=8), headers=headers) as client:
            while True:
                ok, frame = camera.read()
                if not ok:
                    break
                position = time.monotonic() if is_camera else frame_number / fps
                frame_number += 1
                if position < next_sample:
                    continue
                next_sample = position + sample_seconds
                counts['sampled'] += 1
                # Frames and JPEG data only live in memory; no cv2.imwrite / VideoWriter in this worker.
                ratio = min(1.0, 1280 / max(frame.shape[:2]))
                if ratio < 1:
                    frame = cv2.resize(frame, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_AREA)
                ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ok or len(jpeg) > MAX_BYTES:
                    counts['errors'] += 1
                    logger.warning('Skipped frame: encoding failed or size exceeds 2MB')
                    continue
                timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                try:
                    result = retry_request(client, 'POST', args.ai_url.rstrip('/') + '/infer',
                                           files={'file': ('frame.jpg', jpeg.tobytes(), 'image/jpeg')}).json()
                    counts['detected'] += result['detected']
                    for face in result['results']:
                        if face['confidence'] < threshold:
                            counts['rejected'] += 1
                            continue
                        event = dict(session_id=args.session, emoji=face['emoji'], confidence=face['confidence'],
                                     timestamp=timestamp, device_id=device_id,
                                     event_id=str(uuid.uuid4()), model_version=face['model_version'], user_id=None)
                        saved = retry_request(client, 'POST', args.backend.rstrip('/') + '/api/ai/emoji-results', json=event).json()
                        counts['accepted' if saved.get('accepted') else 'rejected'] += 1
                    logger.info('Sample %s: faces=%s, accepted=%s, filtered=%s',
                                counts['sampled'], result['detected'], counts['accepted'], counts['rejected'])
                except (httpx.HTTPError, ValueError, KeyError):
                    counts['errors'] += 1
                    # Do not include response payloads, file names, frame bytes or face data in logs.
                    logger.warning('Frame inference or result submission failed after retry policy')
                if args.max_samples and counts['sampled'] >= args.max_samples:
                    break
    finally:
        camera.release()
    return counts


def main():
    load_local_env()
    parser = argparse.ArgumentParser(description='课堂表情摄像头/视频采样进程')
    parser.add_argument('--source', default='0', help='摄像头编号或本地视频路径')
    parser.add_argument('--session', type=int, required=True)
    parser.add_argument('--backend', default=os.getenv('BACKEND_URL', 'http://127.0.0.1:8010'))
    parser.add_argument('--ai-url', default=os.getenv('AI_URL', 'http://127.0.0.1:8011'))
    parser.add_argument('--sample-seconds', type=float, default=float(os.getenv('AI_SAMPLE_SECONDS', '3')))
    parser.add_argument('--threshold', type=float, default=float(os.getenv('AI_CONFIDENCE_THRESHOLD', '0.6')))
    parser.add_argument('--device-id', default='')
    parser.add_argument('--max-samples', type=int, default=0, help='0为持续采样，其他值用于有界验收')
    args = parser.parse_args()
    if args.session < 1 or args.max_samples < 0:
        parser.error('课堂ID须大于0，max-samples不能为负数')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        print(run(args))
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
