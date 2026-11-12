"""Private inference API. Multipart bytes are parsed in RAM, with no upload spool."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from email import policy
from email.parser import BytesParser
import hmac
import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from ai_service.classifier import EmotionClassifier, MAX_BYTES, MODEL_VERSION, ModelUnavailable

logger = logging.getLogger('emoji.ai')
classifier = EmotionClassifier()


@asynccontextmanager
async def lifespan(app):
    try:
        await asyncio.to_thread(classifier.load)
    except ModelUnavailable:
        logger.warning('FER+ weights unavailable; inference returns 503 until installed')
    yield


app = FastAPI(title='课堂表情独立AI服务', version='1.0.0', lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({'code': f'HTTP_{exc.status_code}', 'message': str(exc.detail)}, status_code=exc.status_code)


@app.get('/health')
async def health():
    return {'status': 'ok' if classifier.loaded else 'model_unavailable',
            'model_loaded': classifier.loaded, 'model_version': MODEL_VERSION,
            'raw_media_storage': False}


async def read_memory_upload(request: Request) -> bytes:
    """No Request.form()/UploadFile: neither parser nor application creates temp files."""
    content_type = request.headers.get('content-type', '')
    if not content_type.lower().startswith('multipart/form-data') or 'boundary=' not in content_type:
        raise HTTPException(415, '请使用multipart/form-data上传file字段')
    limit = MAX_BYTES + 64 * 1024
    try:
        declared = int(request.headers.get('content-length', '0'))
    except ValueError:
        raise HTTPException(400, 'Content-Length无效')
    if declared > limit:
        raise HTTPException(413, '图片不能超过2MB')
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, '图片不能超过2MB')
    try:
        message = BytesParser(policy=policy.default).parsebytes(
            ('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode('ascii') + bytes(body))
        parts = [part for part in message.iter_parts() if part.get_param('name', header='content-disposition') == 'file']
        if len(parts) != 1:
            raise HTTPException(422, '需要一个file图片字段')
        data = parts[0].get_payload(decode=True)
    except (UnicodeError, ValueError, AttributeError) as exc:
        raise HTTPException(400, '上传数据格式无效') from exc
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(413, '图片不能为空且不能超过2MB')
    return data


@app.post('/infer', openapi_extra={
    'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': {
        'type': 'object', 'required': ['file'], 'properties': {'file': {'type': 'string', 'format': 'binary'}}}}}},
    'security': [{'AIServiceToken': []}],
})
async def infer(request: Request):
    expected = os.getenv('AI_SERVICE_TOKEN', '')
    auth = request.headers.get('authorization', '')
    token = auth[7:] if auth.startswith('Bearer ') else ''
    if not expected or not token or not hmac.compare_digest(expected.encode('utf-8'), token.encode('utf-8')):
        raise HTTPException(401, 'AI服务令牌无效')
    data = await read_memory_upload(request)
    try:
        return await asyncio.to_thread(classifier.infer, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception:
        logger.exception('Inference failed; image bytes are never logged')
        raise HTTPException(503, '表情识别暂时不可用，请稍后重试')


_original_openapi = app.openapi


def openapi():
    schema = _original_openapi()
    schema.setdefault('components', {}).setdefault('securitySchemes', {})['AIServiceToken'] = {
        'type': 'http', 'scheme': 'bearer', 'description': '仅供服务间调用的AI_SERVICE_TOKEN'}
    return schema


app.openapi = openapi
