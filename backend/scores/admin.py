from django.contrib import admin
from .models import ScoreSheet


@admin.register(ScoreSheet)
class ScoreSheetAdmin(admin.ModelAdmin):
    list_display = ("title", "share_token", "transpose_semitones", "created_at")
    search_fields = ("title", "share_token")
    readonly_fields = ("id", "share_token", "created_at", "updated_at")

