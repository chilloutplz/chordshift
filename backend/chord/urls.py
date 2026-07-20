from django.urls import path

from .views import UploadChordImageView

urlpatterns = [
    path("upload/", UploadChordImageView.as_view(), name="upload-image"),
]