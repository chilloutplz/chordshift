from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from rest_framework.routers import DefaultRouter
from . import song_views
from .media_proxy import media_proxy

router = DefaultRouter()
router.register(r'songs', song_views.SongViewSet, basename='song')

urlpatterns = [
    path('files/<path:name>', media_proxy, name='media-proxy'),
    path('temp/upload/', song_views.temp_upload, name='temp-upload'),
    path('temp/<str:temp_id>/chords/', song_views.temp_update_chords, name='temp-update-chords'),
    path('temp/<str:temp_id>/ocr/', song_views.temp_ocr, name='temp-ocr'),
    path('temp/job/<str:job_id>/', song_views.temp_job_status, name='temp-job-status'),
    path('temp/<str:temp_id>/', song_views.temp_delete, name='temp-delete'),
    path('songs/from-temp/', song_views.song_from_temp, name='song-from-temp'),
    path('', include(router.urls)),
    # --- 임시파일은 로컬에서 직접 서빙 (R2와 무관) ---
    re_path(r'^media/tmp/(?P<path>.*)$', serve, {'document_root': str(settings.MEDIA_ROOT / 'tmp')}),
]
