"""Song repository + temp upload APIs - patched for chord_font_size"""
from django.conf import settings
from django.db.models import Q
from django.core.files import File
from rest_framework.decorators import api_view, action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import viewsets

from .models import Song, ScoreVariant, OcrUsage
from .serializers import SongSerializer, ScoreVariantSerializer
from .utils.image_process import optimize_for_mobile
from .utils.temp_store import save_temp_image, load_meta, save_meta, image_path, delete_temp, cleanup_old_temps
from .utils.ocr import get_usage_stats, OcrQuotaExceeded, OcrConfigError

from .utils.config import DEFAULT_CHORD_FONT_SIZE

@api_view(['POST'])
def temp_upload(request):
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
    meta['chord_font_size'] = int(request.data.get('chord_font_size', DEFAULT_CHORD_FONT_SIZE) or DEFAULT_CHORD_FONT_SIZE)
    chords = []
    ocr_raw = ''
    ocr_usage = None
    if run_ocr:
        try:
            from .utils.ocr import run_ocr as do_ocr
            result = do_ocr(info['path'])
            chords = result.get('chords') or result.get('chord_lines') or []
            ocr_raw = result.get('raw_text', '') or result.get('ocr_raw_text', '')
            ocr_usage = result.get('ocr_usage')
        except OcrQuotaExceeded as e:
            return Response({
                'error': 'ocr_quota_exceeded',
                'message': f'이번 달 OCR 한도를 모두 사용했습니다 ({e.used}/{e.limit}). 다음 달에 다시 이용해주세요.',
                'ocr_usage': {'used': e.used, 'limit': e.limit, 'remaining': 0, 'exceeded': True},
                'temp_id': info['temp_id'],
                'title': meta['title'],
                'optimized_image': info['url'],
                'chords': [],
                'is_temp': True,
            }, status=429)
        except OcrConfigError as e:
            ocr_raw = f'[OCR 설정 오류] {e}'
        except Exception as e:
            ocr_raw = f'[OCR error] {e}'
    meta['chords'] = chords
    meta['ocr_raw_text'] = ocr_raw
    save_meta(info['temp_id'], meta)
    payload = {
        'temp_id': info['temp_id'],
        'title': meta['title'],
        'optimized_image': info['url'],
        'chords': chords,
        'chord_font_size': meta['chord_font_size'],
        'ocr_raw_text': ocr_raw,
        'is_temp': True,
    }
    if ocr_usage:
        payload['ocr_usage'] = ocr_usage
    return Response(payload, status=201)


@api_view(['POST'])
def temp_ocr(request, temp_id):
    path = image_path(temp_id)
    if not path:
        return Response({'error': '임시 파일 없음'}, status=404)
    try:
        from .utils.ocr import run_ocr as do_ocr
        result = do_ocr(str(path))
    except OcrQuotaExceeded as e:
        return Response({
            'error': 'ocr_quota_exceeded',
            'message': f'이번 달 OCR 한도를 모두 사용했습니다 ({e.used}/{e.limit}).',
            'ocr_usage': {'used': e.used, 'limit': e.limit, 'remaining': 0, 'exceeded': True},
        }, status=429)
    except OcrConfigError as e:
        return Response({'error': 'ocr_config', 'message': str(e)}, status=503)
    except Exception as e:
        return Response({'error': f'OCR 실패: {e}'}, status=500)
    meta = load_meta(temp_id) or {'temp_id': temp_id}
    meta['chords'] = result.get('chords') or []
    meta['ocr_raw_text'] = result.get('raw_text', '') or result.get('ocr_raw_text', '')
    save_meta(temp_id, meta)
    return Response({
        'temp_id': temp_id,
        'chords': meta['chords'],
        'ocr_raw_text': meta['ocr_raw_text'],
        'chord_font_size': meta.get('chord_font_size', DEFAULT_CHORD_FONT_SIZE),
        'is_temp': True,
        'ocr_usage': result.get('ocr_usage'),
    })


@api_view(['GET'])
def ocr_usage(request):
    """이번 달 Google Vision OCR 사용량 (프론트 가시화용)"""
    try:
        stats = get_usage_stats()
        return Response(stats)
    except Exception as e:
        return Response({'error': str(e), 'used': 0, 'limit': 1000, 'remaining': 1000, 'exceeded': False}, status=200)


@api_view(['PATCH', 'POST'])
def temp_update_chords(request, temp_id):
    meta = load_meta(temp_id)
    if not meta:
        return Response({'error': '임시 세션 없음'}, status=404)
    if 'chords' in request.data:
        meta['chords'] = request.data['chords']
    if 'title' in request.data:
        meta['title'] = request.data['title']
    if 'chord_font_size' in request.data:
        try:
            meta['chord_font_size'] = int(request.data['chord_font_size'])
        except:
            pass
    save_meta(temp_id, meta)
    return Response({**meta, 'is_temp': True})


@api_view(['DELETE'])
def temp_delete(request, temp_id):
    delete_temp(temp_id)
    return Response(status=204)


@api_view(['POST'])
def song_from_temp(request):
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
    font_size = DEFAULT_CHORD_FONT_SIZE
    if 'chord_font_size' in request.data:
        try:
            font_size = int(request.data['chord_font_size'])
        except:
            font_size = DEFAULT_CHORD_FONT_SIZE
    elif meta and 'chord_font_size' in meta:
        try:
            font_size = int(meta['chord_font_size'])
        except:
            font_size = DEFAULT_CHORD_FONT_SIZE

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
        song.chord_font_size = font_size
        if meta:
            song.ocr_raw_text = meta.get('ocr_raw_text') or song.ocr_raw_text
        with open(path, 'rb') as fh:
            song.original_image.save(path.name, File(fh), save=True)
        song.save()
    else:
        song = Song(title=title, chords=chords or [], ocr_raw_text=(meta or {}).get('ocr_raw_text', ''), chord_font_size=font_size)
        with open(path, 'rb') as fh:
            song.original_image.save(path.name, File(fh), save=False)
        song.save()

    delete_temp(temp_id)
    data = SongSerializer(song, context={'request': request}).data
    data['message'] = '보정본이 저장되었습니다'
    return Response(data, status=201)



@api_view(['GET'])
def temp_job_status(request, job_id):
    """OCR 큐 상태 폴링 - 임시 호환용 stub. 실제로는 temp_id로 meta 조회"""
    from .utils.temp_store import load_meta
    # job_id가 temp_id인 경우도 있고, 실제 job 시스템이 없으면 temp_id로 시도
    meta = load_meta(job_id)
    if meta:
        return Response({
            'job_id': job_id,
            'status': 'done' if meta.get('chords') else 'processing',
            'chords': meta.get('chords', []),
            'ocr_raw_text': meta.get('ocr_raw_text',''),
            'chord_font_size': meta.get('chord_font_size', DEFAULT_CHORD_FONT_SIZE),
        })
    # job 시스템이 있다면 여기서 조회, 없으면 404 대신 queued 반환으로 프론트 무한대기 방지
    return Response({
        'job_id': job_id,
        'status': 'queued',
        'message': 'job system not configured, using temp_id polling fallback',
    })


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
        song = self.get_object()
        if not song.original_image:
            return Response({'error': '원본 이미지 없음'}, status=400)
        from .utils.chord_transpose import transpose_chord_str, normalize_semitones
        try:
            semitones = normalize_semitones(request.data.get('semitones', 0))
        except Exception:
            semitones = 0
        chords = request.data.get('chords') or song.chords or []
        font_size = int(request.data.get('chord_font_size') or getattr(song, 'chord_font_size', DEFAULT_CHORD_FONT_SIZE) or DEFAULT_CHORD_FONT_SIZE)
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
                try:
                    content = render_transposed_sheet(img_path, render_chords, font_size=font_size)
                except TypeError:
                    content = render_transposed_sheet(img_path, render_chords)
        except Exception as e:
            return Response({'error': f'렌더 실패: {e}'}, status=500)

        kind = ScoreVariant.KIND_CORRECTED if semitones == 0 else ScoreVariant.KIND_TRANSPOSED
        label = (request.data.get('label') or '').strip()
        if not label:
            first = 'C'
            src = render_chords or song.chords or []
            if src and isinstance(src[0], dict) and src[0].get('items'):
                first = (src[0]['items'][0] or {}).get('chord') or 'C'
            elif src and isinstance(src[0], str):
                first = src[0]
            elif src and isinstance(src[0], dict):
                first = src[0].get('chord') or 'C'
            if render_chords and isinstance(render_chords[0], dict) and render_chords[0].get('items'):
                shown = (render_chords[0]['items'][0] or {}).get('chord') or first
            else:
                shown = transpose_chord_str(first, semitones) if semitones else first
            import re
            m = re.match(r'([A-Ga-g][#b]?)', str(shown).strip())
            root = (m.group(1)[0].upper() + m.group(1)[1:]) if m else 'C'
            label = f'{root}코드'

        variant, _ = ScoreVariant.objects.get_or_create(
            song=song, transpose_semitones=semitones,
            defaults={'kind': kind, 'label': label, 'chord_font_size': font_size},
        )
        variant.kind = kind
        variant.label = label
        variant.chord_font_size = font_size
        filename = f'{song.id}_t{semitones}.jpg'
        if variant.image and variant.image.name:
            try:
                variant.image.delete(save=False)
            except Exception:
                pass
        variant.image.save(filename, content, save=True)
        song.save(update_fields=['updated_at'])
        song = Song.objects.prefetch_related('variants').get(pk=song.pk)
        variant.refresh_from_db()
        return Response({
            'song': SongSerializer(song, context={'request': request}).data,
            'variant': ScoreVariantSerializer(variant, context={'request': request}).data,
        })

    @action(detail=True, methods=['delete'], url_path=r'variants/(?P<variant_id>[^/.]+)')
    def delete_variant(self, request, id=None, variant_id=None):
        song = self.get_object()
        try:
            variant = song.variants.get(id=variant_id)
        except ScoreVariant.DoesNotExist:
            return Response({'error': '변형 없음'}, status=404)

        if variant.transpose_semitones == 0:
            for v in song.variants.all():
                if v.image and v.image.name:
                    try:
                        v.image.storage.delete(v.image.name)
                    except:
                        pass
            if song.original_image and song.original_image.name:
                try:
                    song.original_image.storage.delete(song.original_image.name)
                except:
                    pass
            song.delete()
            return Response({'deleted': 'song'})

        if variant.image and variant.image.name:
            try:
                variant.image.storage.delete(variant.image.name)
            except:
                pass
        variant.delete()
        song = Song.objects.prefetch_related('variants').get(pk=song.pk)
        return Response({
            'deleted': 'variant',
            'variants': ScoreVariantSerializer(song.variants.all(), many=True, context={'request': request}).data,
            'song': SongSerializer(song, context={'request': request}).data,
        })
        
    def destroy(self, request, *args, **kwargs):
        song = self.get_object()
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
        if 'chord_font_size' in request.data:
            try:
                song.chord_font_size = int(request.data['chord_font_size'])
            except:
                pass
        song.save()
        return Response(SongSerializer(song, context={'request': request}).data)
