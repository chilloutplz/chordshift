from django.db import models
from django.utils import timezone
import uuid


class Song(models.Model):
    """
    곡 단위 저장소(repository).
    - original_image: 업로드·최적화된 원본 악보
    - chords: 사용자가 보정한 코드·위치 (조옮김 0 기준)
    조옮김 결과는 저장하지 않고 원본+chords로 실시간 렌더.
    ScoreVariant는 레거시(과거 저장된 변형 이미지)용이며 cleanup_variants 로 정리 가능.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, blank=True, default='', db_index=True)
    original_image = models.ImageField(upload_to='songs/original/', blank=True, null=True)
    chords = models.JSONField(default=list, blank=True)
    chord_font_size = models.IntegerField(default=13)
    ocr_raw_text = models.TextField(blank=True, default='')
    original_key = models.CharField(max_length=10, blank=True, default='')
    share_token = models.CharField(max_length=32, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f'Song {self.id}'

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.share_token = uuid.uuid4().hex[:16]
        super().save(*args, **kwargs)


class ScoreVariant(models.Model):
    """원본 보정 렌더 / 조옮김 결과 등 변형 악보"""
    KIND_CORRECTED = 'corrected'
    KIND_TRANSPOSED = 'transposed'
    KIND_CHOICES = [
        (KIND_CORRECTED, '수정본'),
        (KIND_TRANSPOSED, '변조본'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='variants')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_CORRECTED)
    transpose_semitones = models.IntegerField(default=0)
    label = models.CharField(max_length=80, blank=True, default='')
    chord_font_size = models.IntegerField(default=13)
    image = models.ImageField(upload_to='songs/variants/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['transpose_semitones', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['song', 'transpose_semitones'],
                name='uniq_song_semitones',
            ),
        ]

    def __str__(self):
        return self.label or f'{self.kind} {self.transpose_semitones}'

class OcrUsage(models.Model):
    """월별 Google Vision OCR 사용 횟수 추적 (무료 티어 가시화)"""
    month = models.CharField(max_length=7, unique=True, help_text='YYYY-MM')
    count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-month']

    def __str__(self):
        return f'{self.month}: {self.count}'

