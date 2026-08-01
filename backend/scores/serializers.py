from rest_framework import serializers
from .models import Song, ScoreVariant


class ScoreVariantSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ScoreVariant
        fields = ['id', 'kind', 'transpose_semitones', 'label', 'image', 'created_at']

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
                return self._abs(v.image)
        return None

    def get_transpose_semitones(self, obj):
        return 0
