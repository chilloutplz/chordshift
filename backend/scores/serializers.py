from rest_framework import serializers
from .models import Song, ScoreVariant


class ScoreVariantSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ScoreVariant
        fields = ['id', 'kind', 'transpose_semitones', 'label', 'image', 'created_at', 'chord_font_size']

    def get_image(self, obj):
        if not obj.image:
            return None
        return _file_url(obj.image, self.context.get('request'))


def _file_url(field_file, request=None):
    """브라우저/프록시에서 쓰기 쉬운 상대 경로 우선."""
    if not field_file:
        return None
    from django.conf import settings
    name = getattr(field_file, 'name', None) or ''
    if getattr(settings, 'USE_R2', False) and name:
        return f'/api/files/{name}'
    try:
        url = field_file.url
    except Exception:
        return None
    if not url:
        return None
    # 절대 URL이면 path만 사용 (호스트 불일치 방지)
    if url.startswith('http://') or url.startswith('https://'):
        from urllib.parse import urlparse
        return urlparse(url).path or url
    return url


class SongSerializer(serializers.ModelSerializer):
    variants = ScoreVariantSerializer(many=True, read_only=True)
    optimized_image = serializers.SerializerMethodField()
    result_image = serializers.SerializerMethodField()
    transpose_semitones = serializers.SerializerMethodField()

    class Meta:
        model = Song
        fields = [
            'id', 'title', 'original_image', 'optimized_image', 'result_image',
            'chords', 'chord_font_size', 'ocr_raw_text', 'original_key', 'share_token',
            'transpose_semitones', 'variants', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'share_token', 'created_at', 'updated_at',
            'original_image', 'optimized_image', 'result_image', 'variants',
        ]

    def get_optimized_image(self, obj):
        return _file_url(obj.original_image, self.context.get('request'))

    def get_result_image(self, obj):
        # 온디맨드 렌더 전환 후 variant 이미지에 의존하지 않음
        # 하위 호환: 예전에 저장된 variant 이미지가 있으면 반환
        variants = list(obj.variants.all())
        if not variants:
            return None
        variants_sorted = sorted(
            variants,
            key=lambda v: (v.created_at or 0,),
            reverse=True,
        )
        for v in variants_sorted:
            if v.image:
                return _file_url(v.image, self.context.get('request'))
        return None

    def get_transpose_semitones(self, obj):
        return 0
