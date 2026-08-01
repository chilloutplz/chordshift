from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import song_views
from .media_proxy import media_proxy

router = DefaultRouter()
router.register(r'songs', song_views.SongViewSet, basename='song')

urlpatterns = [
    path('files/<path:name>', media_proxy, name='media-proxy'),
    path('temp/upload/', song_views.temp_upload, name='temp-upload'),
    path('songs/from-temp/', song_views.song_from_temp, name='song-from-temp'),
    path('', include(router.urls)),
]
