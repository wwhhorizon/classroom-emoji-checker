"""Download four officially licensed adult-actor clips for the classroom simulation.

Clips are selected by the dataset's intended emotion, never by model predictions.
The parent composition adds the Chinese classroom-stage frame and attribution.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.request

import cv2

from ai_service.classifier import EmotionClassifier

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'demo-assets' / 'source'
REPO = 'https://github.com/CheyneyComputerScience/CREMA-D'
RAW = 'https://raw.githubusercontent.com/CheyneyComputerScience/CREMA-D/master/'
MEDIA = 'https://media.githubusercontent.com/media/CheyneyComputerScience/CREMA-D/master/'
CLIPS = [('1045_IEO_NEU_XX.flv', 'NEU', 'neutral'),
         ('1045_IEO_HAP_HI.flv', 'HAP', 'happy'),
         ('1045_IEO_SAD_HI.flv', 'SAD', 'sad'),
         ('1045_IEO_ANG_HI.flv', 'ANG', 'angry')]


def fetch(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'ClassroomEmojiChecker-course-project/1.0'})
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def prepare():
    import imageio_ffmpeg
    SOURCE.mkdir(parents=True, exist_ok=True)
    license_bytes = fetch(RAW + 'LICENSE.txt')
    (SOURCE / 'CREMA-D-LICENSE.txt').write_bytes(license_bytes)
    demographic = fetch(RAW + 'VideoDemographics.csv')
    (SOURCE / 'CREMA-D-VideoDemographics.csv').write_bytes(demographic)
    classifier = EmotionClassifier()
    manifest = {'repository': REPO, 'license_database': 'ODbL-1.0',
                'license_content': 'DbCL-1.0',
                'license_url': REPO + '/blob/master/LICENSE.txt',
                'demographics_source': REPO + '/blob/master/VideoDemographics.csv',
                'actor_metadata': {'dataset_actor_id': 1045, 'age': 22, 'sex': 'Male', 'race': 'Asian'},
                'selection_rule': 'Same adult actor; the preselected NEU/HAP/SAD/ANG intended-expression labels, without prediction-based selection',
                'sampling_rule': 'First frame and then every 0.5 seconds in each complete clip; all samples retained',
                'classroom_context': 'Licensed facial-expression footage composed with classroom-stage graphics',
                'clips': []}
    for filename, label, emoji in CLIPS:
        pointer = fetch(RAW + 'VideoFlash/' + filename).decode('ascii')
        digest = re.search(r'oid sha256:([0-9a-f]{64})', pointer).group(1)
        length = int(re.search(r'size (\d+)', pointer).group(1))
        original = SOURCE / filename
        if not original.exists() or hashlib.sha256(original.read_bytes()).hexdigest() != digest:
            original.write_bytes(fetch(MEDIA + 'VideoFlash/' + filename))
        if original.stat().st_size != length or hashlib.sha256(original.read_bytes()).hexdigest() != digest:
            raise ValueError('Official clip failed Git LFS hash check: ' + filename)
        converted = original.with_suffix('.mp4')
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
                        '-i', str(original), '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '19',
                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(converted)], check=True)
        capture = cv2.VideoCapture(str(converted))
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not capture.isOpened() or fps <= 0:
            raise RuntimeError('Converted clip could not be read: ' + filename)
        samples = []
        index = 0
        step = max(1, round(fps * .5))
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if index % step == 0:
                    ok, data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    if not ok:
                        raise RuntimeError('Frame encode failed')
                    result = classifier.infer(data.tobytes())
                    samples.append({'seconds': round(index / fps, 3), **result})
                index += 1
        finally:
            capture.release()
        clip = {'file': filename, 'intended_expression': label, 'intended_emoji': emoji,
                'source_url': REPO + '/blob/master/VideoFlash/' + filename,
                'sha256': digest, 'original_bytes': length,
                'browser_video': 'demo-assets/source/' + converted.name,
                'duration_seconds': round(index / fps, 3), 'fps': fps, 'width': width, 'height': height,
                'samples': samples}
        manifest['clips'].append(clip)
        print(filename, 'duration', clip['duration_seconds'], 'samples',
              [(s['seconds'], s['detected'], [(r['emoji'],r['confidence']) for r in s['results']]) for s in samples], flush=True)
    (ROOT / 'demo-assets' / 'source-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SOURCE_TOTAL_BYTES', sum(p.stat().st_size for p in SOURCE.iterdir() if p.is_file()), flush=True)


if __name__ == '__main__':
    prepare()
