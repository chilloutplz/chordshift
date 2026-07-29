from django.db import models
from django.utils import timezone
import uuid


class ScoreSheet(models.Model):
    """기타 악보 시트 – OCR 후 조옮김 가능한 코드 데이터 저장"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, blank=True, default='')
    # 편집용 원본(최적화) 이미지 — 덮어쓰지 않음
    optimized_image = models.ImageField(upload_to='scores/optimized/', blank=True, null=True)
    # 확정 후 생성된 결과 악보 (별도 표시)
    result_image = models.ImageField(upload_to='scores/result/', blank=True, null=True)
    ocr_raw_text = models.TextField(blank=True, default='')
    # [{"id","chord","x","y","w","h"}, ...] 정규화 좌표
    chords = models.JSONField(default=list, blank=True)
    original_key = models.CharField(max_length=10, blank=True, default='')
    transpose_semitones = models.IntegerField(default=0)
    lyrics_or_notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    share_token = models.CharField(max_length=32, unique=True, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"Score {self.id}"

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.share_token = uuid.uuid4().hex[:16]
        super().save(*args, **kwargs)
