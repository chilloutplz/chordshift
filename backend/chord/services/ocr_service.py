from paddleocr import PaddleOCR

# 서버 시작 시 한 번만 모델 로드
ocr = PaddleOCR(
    lang="korean"
)


class OCRService:

    def detect(self, image_path):

        result = ocr.predict(image_path)

        texts = []

        for page in result:

            rec_texts = page.get("rec_texts", [])

            for text in rec_texts:
                texts.append(text)

        return texts