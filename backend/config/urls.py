from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('scores.urls')),
    # 임시파일은 DEBUG와 상관없이 항상 로컬에서 서빙 (R2 아님)
    re_path(r'^media/tmp/(?P<path>.*)$', serve, {'document_root': str(settings.MEDIA_ROOT / 'tmp')}),
]

# DEBUG일 때만 전체 media 서빙 (운영은 R2가 하니까)
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)