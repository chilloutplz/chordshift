from django.contrib import admin
from .models import Song, ScoreVariant


class ScoreVariantInline(admin.TabularInline):
    model = ScoreVariant
    extra = 0
    readonly_fields = ('id', 'created_at')


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ('title', 'id', 'updated_at', 'created_at')
    search_fields = ('title', 'share_token')
    readonly_fields = ('id', 'share_token', 'created_at', 'updated_at')
    inlines = [ScoreVariantInline]


@admin.register(ScoreVariant)
class ScoreVariantAdmin(admin.ModelAdmin):
    list_display = ('label', 'song', 'transpose_semitones', 'kind', 'created_at')
    list_filter = ('kind',)
    search_fields = ('label', 'song__title')
