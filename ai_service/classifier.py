"""Haar face localization and official FER+ ONNX inference, entirely in memory."""
from __future__ import annotations

import io
import os
from pathlib import Path
import threading
import warnings

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from ai_service.download_model import DEFAULT_PATH, verify_model

MODEL_VERSION = 'onnx-ferplus-8-sha256-a2a2ba6a335a'
EMOJIS = ('neutral', 'happy', 'surprised', 'sad', 'angry', 'disgusted', 'fearful')
MAX_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 8_000_000


class ModelUnavailable(RuntimeError):
    pass


def probabilities(scores: np.ndarray) -> dict[str, float]:
    """Stable softmax; merge FER+ contempt into neutral before selecting class."""
    values = np.asarray(scores, dtype=np.float64).reshape(-1)
    if values.size != 8 or not np.isfinite(values).all():
        raise ValueError('FER+ returned invalid model output')
    exp = np.exp(values - values.max())
    probs = exp / exp.sum()
    mapped = {name: float(probs[i]) for i, name in enumerate(EMOJIS)}
    mapped['neutral'] += float(probs[7])
    return mapped


def decode_image(data: bytes) -> np.ndarray:
    if not data or len(data) > MAX_BYTES:
        raise ValueError('图片不能为空且大小不能超过2MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {'JPEG', 'PNG'}:
                    raise ValueError('请使用JPEG或PNG图片')
                if image.width * image.height > MAX_PIXELS or min(image.size) < 32:
                    raise ValueError('图片尺寸须至少32像素且总像素不超过800万')
                image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('图片损坏或格式不受支持') from exc
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError('无法读取图片')
    return frame


class EmotionClassifier:
    def __init__(self, model_path: Path | str | None = None):
        self.model_path = Path(model_path or os.getenv('FERPLUS_MODEL_PATH', str(DEFAULT_PATH)))
        self._network = None
        self._lock = threading.Lock()
        cascade_path = os.getenv('FACE_CASCADE_PATH', cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        # OpenCV's Windows file API may not open Chinese paths; load XML from Python memory.
        storage = cv2.FileStorage(Path(cascade_path).read_text(encoding='utf-8'), cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
        self._detector = cv2.CascadeClassifier()
        self._detector.read(storage.getFirstTopLevelNode())
        storage.release()
        if self._detector.empty():
            raise ModelUnavailable('人脸检测模型未找到')

    @property
    def loaded(self) -> bool:
        return self._network is not None

    def load(self) -> None:
        with self._lock:
            if self._network is not None:
                return
            if not verify_model(self.model_path):
                raise ModelUnavailable('FER+权重缺失或校验失败，请运行 python -m ai_service.download_model')
            try:
                self._network = cv2.dnn.readNetFromONNX(np.frombuffer(self.model_path.read_bytes(), dtype=np.uint8))
                self._network.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self._network.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            except cv2.error as exc:
                self._network = None
                raise ModelUnavailable('无法加载FER+权重') from exc

    def infer(self, data: bytes) -> dict:
        frame = decode_image(data)
        self.load()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Bound detector work while keeping a coordinate transform to the source frame.
        scale = min(1.0, 1280 / max(gray.shape))
        detection = cv2.resize(gray, None, fx=scale, fy=scale) if scale < 1 else gray
        with self._lock:
            faces = self._detector.detectMultiScale(detection, scaleFactor=1.1, minNeighbors=5, minSize=(32, 32))
            results = []
            for x, y, width, height in sorted(faces, key=lambda r: int(r[2]) * int(r[3]), reverse=True)[:30]:
                x, y, width, height = [int(round(v / scale)) for v in (x, y, width, height)]
                crop = gray[y:y + height, x:x + width]
                if crop.size == 0:
                    continue
                # The official FER+ model expects grayscale float32 values 0..255, no /255 normalization.
                tensor = cv2.resize(crop, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)[None, None]
                self._network.setInput(tensor)
                probs = probabilities(self._network.forward())
                emoji = max(probs, key=probs.get)
                results.append({'emoji': emoji, 'confidence': round(probs[emoji], 6),
                                'model_version': MODEL_VERSION})
        return {'detected': len(results), 'results': results, 'model_version': MODEL_VERSION}
