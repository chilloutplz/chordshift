from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScoreSheetViewSet
from . import song_views
from .media_proxy import media_proxy

router = DefaultRouter()
router.register(r'scores', ScoreSheetViewSet, basename='scoresheet')
router.register(r'songs', song_views.SongViewSet, basename='song')

urlpatterns = [
    path('files/<path:name>', media_proxy, name='media-proxy'),
    path('temp/upload/', song_views.temp_upload, name='temp-upload'),
    path('temp/<str:temp_id>/ocr/', song_views.temp_ocr, name='temp-ocr'),
    path('temp/<str:temp_id>/chords/', song_views.temp_update_chords, name='temp-chords'),
    path('temp/<str:temp_id>/', song_views.temp_delete, name='temp-delete'),
    path('songs/from-temp/', song_views.song_from_temp, name='song-from-temp'),
    path('', include(router.urls)),
]
