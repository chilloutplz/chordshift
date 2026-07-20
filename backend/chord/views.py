import os
import tempfile

from PIL import Image

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services.ocr_service import OCRService


service = OCRService()


class UploadChordImageView(APIView):

    def post(self, request):

        image = request.FILES.get("image")

        if image is None:

            return Response(
                {
                    "success": False,
                    "message": "이미지를 선택하세요."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 항상 PNG로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp:

            img = Image.open(image)

            # 투명 GIF 대응
            if img.mode != "RGB":
                img = img.convert("RGB")

            img.save(temp.name, "PNG")

            temp_path = temp.name

        try:

            texts = service.detect(temp_path)

            return Response(
                {
                    "success": True,
                    "message": "OCR 완료",
                    "data": {
                        "texts": texts
                    }
                }
            )

        finally:

            if os.path.exists(temp_path):
                os.remove(temp_path)