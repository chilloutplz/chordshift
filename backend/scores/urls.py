from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScoreSheetViewSet

router = DefaultRouter()
router.register(r'scores', ScoreSheetViewSet, basename='scoresheet')

urlpatterns = [
    path('', include(router.urls)),
]
