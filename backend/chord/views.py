from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


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

        return Response(
            {
                "success": True,
                "message": "업로드 성공",
                "filename": image.name,
                "codes": []
            },
            status=status.HTTP_200_OK
        )