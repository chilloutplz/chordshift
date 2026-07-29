from rest_framework import serializers
from .models import ScoreSheet


class ScoreSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoreSheet
        fields = [
            'id',
            'title',
            'optimized_image',
            'result_image',
            'ocr_raw_text',
            'chords',
            'original_key',
            'transpose_semitones',
            'lyrics_or_notes',
            'share_token',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'share_token', 'created_at', 'updated_at',
            'optimized_image', 'result_image',
        ]


class ScoreSheetUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
    title = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
