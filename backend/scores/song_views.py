"""Song repository + temp upload APIs"""
import shutil
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.core.files import File
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import Song, ScoreVariant
from .serializers import SongSerializer, ScoreVariantSerializer
from .utils.image_process import optimize_for_mobile
from .utils.temp_store import save_temp_image, load_meta, save_meta, image_path, delete_temp, cleanup_old_temps


@api_view(['POST'])
def temp_upload(request):
    """이미지 업로드 → tmp 저장 + OCR. DB 레코드 없음."""
    cleanup_old_temps()
    f = request.FILES.get('image')
    if not f:
        return Response({'error': 'image 필수'}, status=400)
    title = request.data.get('title', '')
    run_ocr = str(request.data.get('run_ocr', 'true')).lower() in ('1', 'true', 'yes')

    optimized = optimize_for_mobile(f)
    info = save_temp_image(optimized)
    meta = load_meta(info['temp_id']) or {}
    meta['title'] = title or getattr(f, 'name', '')
    chords = []
    ocr_raw = ''
    if run_ocr:
        try:
            from .utils.ocr import run_ocr as do_ocr
            result = do_ocr(info['path'])
            chords = result.get('chords') or result.get('chord_lines') or []
            ocr_raw = result.get('raw_text', '')
        except Exception as e:
            ocr_raw = f'[OCR error] {e}'
    meta['chords'] = chords
    meta['ocr_raw_text'] = ocr_raw
    save_meta(info['temp_id'], meta)

    return Response({
        'temp_id': info['temp_id'],
        'title': meta['title'],
        'image_url': request.build_absolute_uri(info['url']) if not info['url'].startswith('http') else info['url'],
        'optimized_image': info['url'],  # 프론트 호환
        'chords': chords,
        'ocr_raw_text': ocr_raw,
        'transpose_semitones': 0,
        'is_temp': True,
    }, status=201)


@api_view(['POST'])
def temp_ocr(request, temp_id):
    path = image_path(temp_id)
    if not path:
        return Response({'error': '임시 파일 없음'}, status=404)
    try:
        from .utils.ocr import run_ocr as do_ocr
        result = do_ocr(str(path))
    except Exception as e:
        return Response({'error': f'OCR 실패: {e}'}, status=500)
    meta = load_meta(temp_id) or {'temp_id': temp_id}
    meta['chords'] = result.get('chords') or []
    meta['ocr_raw_text'] = result.get('raw_text', '')
    save_meta(temp_id, meta)
    return Response({
        'temp_id': temp_id,
        'chords': meta['chords'],
        'ocr_raw_text': meta['ocr_raw_text'],
        'is_temp': True,
    })


@api_view(['PATCH', 'POST'])
def temp_update_chords(request, temp_id):
    meta = load_meta(temp_id)
    if not meta:
        return Response({'error': '임시 세션 없음'}, status=404)
    if 'chords' in request.data:
        meta['chords'] = request.data['chords']
    if 'title' in request.data:
        meta['title'] = request.data['title']
    save_meta(temp_id, meta)
    return Response({**meta, 'is_temp': True})


@api_view(['DELETE'])
def temp_delete(request, temp_id):
    delete_temp(temp_id)
    return Response(status=204)


@api_view(['POST'])
def song_from_temp(request):
    """
    보정본 저장 → 이때 비로소 Song DB 생성.
    body: { temp_id, title, chords, merge_song_id? }
    같은 제목이 있으면 409 + candidates (merge_song_id 로 기존 곡에 병합 가능)
    """
    temp_id = request.data.get('temp_id')
    title = (request.data.get('title') or '').strip()
    chords = request.data.get('chords')
    merge_id = request.data.get('merge_song_id')
    force_new = str(request.data.get('force_new', 'false')).lower() in ('1', 'true', 'yes')

    meta = load_meta(temp_id) if temp_id else None
    path = image_path(temp_id) if temp_id else None
    if not path or not path.is_file():
        return Response({'error': '임시 파일이 없습니다. 다시 업로드하세요.'}, status=400)

    if chords is None and meta:
        chords = meta.get('chords') or []
    if not title and meta:
        title = meta.get('title') or ''

    # 중복 제목 검사
    if title and not merge_id and not force_new:
        existing = list(Song.objects.filter(title__iexact=title)[:10])
        if existing:
            return Response({
                'error': 'duplicate_title',
                'message': f'같은 제목의 곡이 {len(existing)}개 있습니다.',
                'candidates': SongSerializer(existing, many=True, context={'request': request}).data,
            }, status=409)

    if merge_id:
        try:
            song = Song.objects.get(id=merge_id)
        except Song.DoesNotExist:
            return Response({'error': '병합할 곡이 없습니다'}, status=404)
        song.title = title or song.title
        song.chords = chords or song.chords
        if meta:
            song.ocr_raw_text = meta.get('ocr_raw_text') or song.ocr_raw_text
        # 원본 이미지는 유지하거나 교체
        with open(path, 'rb') as fh:
            song.original_image.save(path.name, File(fh), save=True)
        song.save()
    else:
        song = Song(title=title, chords=chords or [], ocr_raw_text=(meta or {}).get('ocr_raw_text', ''))
        with open(path, 'rb') as fh:
            song.original_image.save(path.name, File(fh), save=False)
        song.save()

    delete_temp(temp_id)
    data = SongSerializer(song, context={'request': request}).data
    data['message'] = '보정본이 저장되었습니다'
    return Response(data, status=201)


class SongViewSet(viewsets.ModelViewSet):
    queryset = Song.objects.all()
    serializer_class = SongSerializer
    lookup_field = 'id'
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return Song.objects.prefetch_related('variants').all()

    @action(detail=False, methods=['get'])
    def search(self, request):
        q = (request.query_params.get('q') or '').strip()
        qs = self.get_queryset()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(share_token__icontains=q))
        qs = qs.order_by('-updated_at')[:50]
        return Response(SongSerializer(qs, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def render_variant(self, request, id=None):
        """현재 chords + semitones 로 변형 이미지 생성·저장"""
        song = self.get_object()
        if not song.original_image:
            return Response({'error': '원본 이미지 없음'}, status=400)
        from .utils.chord_transpose import transpose_chord_str, normalize_semitones
        try:
            semitones = normalize_semitones(request.data.get('semitones', 0))
        except Exception:
            semitones = 0
        chords = request.data.get('chords') or song.chords or []
        from .utils.render_sheet import render_transposed_sheet

        render_chords = chords
        if semitones:
            applied = []
            for item in chords:
                if isinstance(item, dict) and 'items' in item:
                    line = dict(item)
                    line['items'] = [
                        {**it, 'chord': transpose_chord_str(it.get('chord', ''), semitones)}
                        if isinstance(it, dict) else it
                        for it in (item.get('items') or [])
                    ]
                    applied.append(line)
                else:
                    applied.append(item)
            render_chords = applied

        try:
            from .utils.file_local import local_image_path
            with local_image_path(song.original_image) as img_path:
                content = render_transposed_sheet(img_path, render_chords)
        except Exception as e:
            return Response({'error': f'렌더 실패: {e}'}, status=500)

        kind = ScoreVariant.KIND_CORRECTED if semitones == 0 else ScoreVariant.KIND_TRANSPOSED
        label = (request.data.get('label') or '').strip()
        if not label:
            from .utils.chord_transpose import transpose_chord_str
            first = 'C'
            src = render_chords or song.chords or []
            if src and isinstance(src[0], dict) and src[0].get('items'):
                first = (src[0]['items'][0] or {}).get('chord') or 'C'
            elif src and isinstance(src[0], str):
                first = src[0]
            elif src and isinstance(src[0], dict):
                first = src[0].get('chord') or 'C'
            # render_chords already transposed when semitones applied above
            root_src = first if semitones else first
            if semitones and render_chords is not chords:
                pass  # already transposed in render_chords
            # extract root from whatever is in first of render_chords
            if render_chords and isinstance(render_chords[0], dict) and render_chords[0].get('items'):
                shown = (render_chords[0]['items'][0] or {}).get('chord') or first
            else:
                shown = transpose_chord_str(first, semitones) if semitones else first
            import re
            m = re.match(r'([A-Ga-g][#b]?)', str(shown).strip())
            root = (m.group(1)[0].upper() + m.group(1)[1:]) if m else 'C'
            label = f'{root}코드'

        # 같은 song + semitones 는 한 레코드, 이미지는 고정 키로 덮어쓰기
        variant, _ = ScoreVariant.objects.get_or_create(
            song=song, transpose_semitones=semitones,
            defaults={'kind': kind, 'label': label},
        )
        variant.kind = kind
        variant.label = label
        # 예: songs/variants/<song_id>_t0.jpg  (보정본), _t2.jpg (조옮김)
        filename = f'{song.id}_t{semitones}.jpg'
        if variant.image and variant.image.name:
            try:
                variant.image.delete(save=False)
            except Exception:
                pass
        variant.image.save(filename, content, save=True)
        song.save(update_fields=['updated_at'])
        # relation cache 갱신 후 직렬화
        song = Song.objects.prefetch_related('variants').get(pk=song.pk)
        variant.refresh_from_db()
        return Response({
            'song': SongSerializer(song, context={'request': request}).data,
            'variant': ScoreVariantSerializer(variant, context={'request': request}).data,
        })

    def destroy(self, request, *args, **kwargs):
        import os
        song = self.get_object()
        # variants 이미지
        for v in song.variants.all():
            if v.image and v.image.name:
                try:
                    v.image.storage.delete(v.image.name)
                except Exception:
                    pass
        if song.original_image and song.original_image.name:
            try:
                song.original_image.storage.delete(song.original_image.name)
            except Exception:
                pass
        song.delete()
        return Response(status=204)

    def partial_update(self, request, *args, **kwargs):
        song = self.get_object()
        if 'chords' in request.data:
            song.chords = request.data['chords']
        if 'title' in request.data:
            song.title = request.data['title']
        song.save()
        return Response(SongSerializer(song, context={'request': request}).data)
