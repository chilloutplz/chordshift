from rest_framework import serializers
from .models import ScoreSheet, Song, ScoreVariant


class ScoreSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoreSheet
        fields = [
            'id', 'title', 'optimized_image', 'result_image', 'ocr_raw_text',
            'chords', 'original_key', 'transpose_semitones', 'lyrics_or_notes',
            'share_token', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'share_token', 'created_at', 'updated_at',
            'optimized_image', 'result_image',
        ]


class ScoreSheetUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
    title = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')


class ScoreVariantSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ScoreVariant
        fields = ['id', 'kind', 'transpose_semitones', 'label', 'image', 'created_at']
        read_only_fields = fields

    def get_image(self, obj):
        if not obj.image:
            return None
        from django.conf import settings
        req = self.context.get('request')
        name = getattr(obj.image, 'name', None) or ''
        if getattr(settings, 'USE_R2', False) and name:
            url = f'/api/files/{name}'
            return req.build_absolute_uri(url) if req else url
        try:
            url = obj.image.url
        except Exception:
            return None
        if req and url and url.startswith('/'):
            return req.build_absolute_uri(url)
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
            'chords', 'ocr_raw_text', 'original_key', 'share_token',
            'transpose_semitones', 'variants', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'share_token', 'created_at', 'updated_at',
            'original_image', 'optimized_image', 'result_image', 'variants',
        ]

    def _abs(self, field_file):
        if not field_file:
            return None
        from django.conf import settings
        req = self.context.get('request')
        name = getattr(field_file, 'name', None) or ''
        # R2 등 원격: 브라우저가 직접 못 열 수 있으므로 API 프록시 URL 사용
        if getattr(settings, 'USE_R2', False) and name:
            url = f'/api/files/{name}'
            return req.build_absolute_uri(url) if req else url
        try:
            url = field_file.url
        except Exception:
            return None
        if req and url and url.startswith('/'):
            return req.build_absolute_uri(url)
        return url

    def get_optimized_image(self, obj):
        return self._abs(obj.original_image)

    def get_result_image(self, obj):
        # 가장 최근 변형 이미지 (조옮김 결과 우선 표시)
        variants = list(obj.variants.all())
        if not variants:
            return None
        # created_at 최신
        variants_sorted = sorted(
            variants,
            key=lambda v: (v.created_at or 0,),
            reverse=True,
        )
        for v in variants_sorted:
            if v.image:
                return self._abs(v.image)
        return None

    def get_transpose_semitones(self, obj):
        return 0
