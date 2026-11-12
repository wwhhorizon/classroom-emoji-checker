"""Actual FER+ inference and API protections; no business database imports."""
import io
from pathlib import Path

import cv2
import httpx
import numpy as np
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from ai_service.classifier import EmotionClassifier, ModelUnavailable, decode_image, probabilities
from ai_service.download_model import DEFAULT_PATH, verify_model
from ai_service.main import app, classifier
from ai_service.worker import retry_request


def image_bytes(color='white', size=(96, 96), fmt='PNG'):
    stream = io.BytesIO()
    Image.new('RGB', size, color).save(stream, fmt)
    return stream.getvalue()


def test_softmax_mapping_has_seven_valid_probabilities():
    result = probabilities(np.array([0, 0, 0, 0, 0, 0, 0, 1000]))
    assert set(result) == {'neutral', 'happy', 'surprised', 'sad', 'angry', 'disgusted', 'fearful'}
    assert sum(result.values()) == pytest.approx(1)
    assert result['neutral'] == pytest.approx(1)


@pytest.mark.parametrize('invalid', [np.zeros(7), np.array([float('nan')] * 8), np.array([float('inf')] * 8)])
def test_softmax_rejects_invalid_model_output(invalid):
    with pytest.raises(ValueError):
        probabilities(invalid)


@pytest.mark.parametrize('data', [b'', b'not an image', b'x' * (2 * 1024 * 1024 + 1), image_bytes(fmt='GIF'), image_bytes(size=(16, 16))])
def test_decode_rejects_bad_or_oversize_input(data):
    with pytest.raises(ValueError):
        decode_image(data)


def test_decode_rejects_large_dimensions():
    with pytest.raises(ValueError):
        decode_image(image_bytes(size=(3000, 3000)))


def test_official_weights_hash_and_real_no_face_inference():
    assert verify_model(DEFAULT_PATH)
    result = EmotionClassifier().infer(image_bytes())
    assert result['detected'] == 0
    assert result['results'] == []


def test_missing_weights_fail_explicitly(tmp_path):
    engine = EmotionClassifier(tmp_path / 'missing.onnx')
    with pytest.raises(ModelUnavailable):
        engine.infer(image_bytes())


def test_inference_token_required_and_non_ascii_token_rejected(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-ai-token')
    with TestClient(app) as client:
        assert client.post('/infer', files={'file': ('frame.png', image_bytes(), 'image/png')}).status_code == 401
        # Starlette decodes byte-oriented headers as latin1; invalid credentials still return 401.
        assert client.post('/infer', headers=[(b'Authorization', b'Bearer \xff')], files={'file': ('frame.png', image_bytes(), 'image/png')}).status_code == 401


def test_inference_api_accepts_real_frame_and_reports_model_state(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-ai-token')
    with TestClient(app) as client:
        response = client.post('/infer', headers={'Authorization': 'Bearer test-ai-token'},
                               files={'file': ('frame.png', image_bytes(), 'image/png')})
        assert response.status_code == 200
        assert response.json()['detected'] == 0
        assert client.get('/health').json()['model_loaded'] is True
        schema = client.get('/openapi.json').json()
        assert 'AIServiceToken' in schema['components']['securitySchemes']


def test_inference_rejects_oversize_and_malformed_multipart(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-ai-token')
    headers = {'Authorization': 'Bearer test-ai-token'}
    with TestClient(app) as client:
        assert client.post('/infer', headers=headers, files={'file': ('a.png', b'x' * (2 * 1024 * 1024 + 1), 'image/png')}).status_code == 413
        assert client.post('/infer', headers=headers, json={}).status_code == 415
        assert client.post('/infer', headers={**headers, 'Content-Type': 'multipart/form-data; boundary=abc'}, content=b'bad').status_code == 422
        assert client.post('/infer', headers=headers, files={'wrong': ('a.png', image_bytes(), 'image/png')}).status_code == 422


def test_inference_returns_503_for_unavailable_model(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-ai-token')
    def unavailable(_):
        raise ModelUnavailable('missing weights')
    with TestClient(app) as client:
        monkeypatch.setattr(classifier, 'infer', unavailable)
        response = client.post('/infer', headers={'Authorization': 'Bearer test-ai-token'}, files={'file': ('a.png', image_bytes(), 'image/png')})
        assert response.status_code == 503


def test_retry_keeps_same_event_payload_and_recovers(monkeypatch):
    calls = []
    def serve(request):
        calls.append(request.content)
        return httpx.Response(503 if len(calls) == 1 else 200, json={'accepted': True})
    monkeypatch.setattr('ai_service.worker.time.sleep', lambda seconds: None)
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        response = retry_request(client, 'POST', 'http://backend/api/ai/emoji-results', json={'event_id': 'stable-uuid'})
    assert response.status_code == 200
    assert len(calls) == 2 and calls[0] == calls[1]


def test_retry_does_not_repeat_permanent_auth_failure(monkeypatch):
    calls = []
    def serve(request):
        calls.append(request)
        return httpx.Response(401)
    with httpx.Client(transport=httpx.MockTransport(serve)) as client, pytest.raises(httpx.HTTPStatusError):
        retry_request(client, 'POST', 'http://ai/infer')
    assert len(calls) == 1
