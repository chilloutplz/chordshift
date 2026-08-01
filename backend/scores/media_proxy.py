"""R2/로컬 스토리지 파일을 앱 서버 경유해 브라우저에 전달."""
import mimetypes

from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponseNotFound, HttpResponseForbidden
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


@api_view(['GET', 'HEAD'])
@permission_classes([AllowAny])
def media_proxy(request, name: str):
    """
    GET /api/files/<storage-relative-path>
    예: /api/files/songs/variants/xxx.jpg
    """
    # 경로 조작 방지
    name = (name or '').lstrip('/')
    if not name or '..' in name.split('/'):
        return HttpResponseForbidden('invalid path')

    if not default_storage.exists(name):
        return HttpResponseNotFound('not found')

    try:
        fh = default_storage.open(name, 'rb')
    except Exception:
        return HttpResponseNotFound('open failed')

    content_type, _ = mimetypes.guess_type(name)
    content_type = content_type or 'application/octet-stream'
    resp = FileResponse(fh, content_type=content_type)
    resp['Cache-Control'] = 'public, max-age=3600'
    return resp
