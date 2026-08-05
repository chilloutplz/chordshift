"""Song repository + temp upload APIs - 분리형 (502 해결)"""
import threading
import time
import uuid
from collections import deque
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

# --- 502 해결용: 메모리에서 job 관리 (단순 버전) ---
JOBS = {}

# 메모리 0.5GB 환경에서 OCR 동시 실행 시 OOM으로 워커가 죽는 문제 방지
# → RapidOCR 추론은 한 번에 하나씩만 돌게 강제 (동시 업로드 시 순차 대기)
_OCR_SEMAPHORE = threading.Semaphore(1)

# 대기 순번 계산용 - 도착한 순서대로 job_id를 쌓아두고, 처리 시작하면 빼냄
_QUEUE_LOCK = threading.Lock()
_QUEUE_ORDER = []

# 최근 완료된 OCR 소요시간(초) - 다음 대기자의 예상 대기시간 추정에 사용
_RECENT_DURATIONS = deque(maxlen=5)
_DEFAULT_DURATION_ESTIMATE = 25  # 이력이 없을 때 쓸 기본 추정치(초), 로그 상 실측 평균 근사치

@api_view(['POST'])
def temp_upload(request):
    """이미지 업로드 → tmp 저장만. OCR 절대 안 함. 1초컷."""
    cleanup_old_temps()
    f = request.FILES.get('image')
    if not f:
        return Response({'error': 'image 필수'}, status=400)
    title = request.data.get('title', '')

    optimized = optimize_for_mobile(f)
    info = save_temp_image(optimized)
    meta = load_meta(info['temp_id']) or {}
    meta['title'] = title or getattr(f, 'name', '')
    meta['chords'] = []
    meta['ocr_raw_text'] = ''
    save_meta(info['temp_id'], meta)

    _abs = request.build_absolute_uri(info['url']) if not info['url'].startswith('http') else info['url']
    if _abs.startswith('http://'):
        _abs = _abs.replace('http://', 'https://')

    return Response({
        'temp_id': info['temp_id'],
        'title': meta['title'],
        'optimized_image': _abs,
        'chords': [],
        'ocr_raw_text': '',
        'transpose_semitones': 0,
        'is_temp': True,
    }, status=201)


@api_view(['POST'])
def temp_ocr(request, temp_id):
    """OCR 시작 → 바로 job_id 반환, 백그라운드에서 처리"""
    path = image_path(temp_id)
    if not path:
        return Response({'error': '임시 파일 없음'}, status=404)

    job_id = str(uuid.uuid4())[:12]
    JOBS[job_id] = {"status": "queued", "temp_id": temp_id, "result": None}

    with _QUEUE_LOCK:
        _QUEUE_ORDER.append(job_id)

    def do_ocr_job():
        with _OCR_SEMAPHORE:
            # 세마포어 획득 = 내 차례가 됨 → 큐에서 제거
            with _QUEUE_LOCK:
                try:
                    _QUEUE_ORDER.remove(job_id)
                except ValueError:
                    pass
            JOBS[job_id] = {"status": "processing", "temp_id": temp_id, "result": None}
            started_at = time.time()
            try:
                from .utils.ocr import run_ocr as do_ocr
                result = do_ocr(str(path))
                meta = load_meta(temp_id) or {'temp_id': temp_id}
                meta['chords'] = result.get('chords') or result.get('chord_lines') or []
                meta['ocr_raw_text'] = result.get('raw_text', '')
                save_meta(temp_id, meta)
                JOBS[job_id] = {"status": "done", "temp_id": temp_id, "result": meta}
            except Exception as e:
                JOBS[job_id] = {"status": "failed", "temp_id": temp_id, "error": str(e)}
            finally:
                _RECENT_DURATIONS.append(time.time() - started_at)

    threading.Thread(target=do_ocr_job, daemon=True).start()

    return Response({"job_id": job_id, "status": "processing"}, status=202)


@api_view(['GET'])
def temp_job_status(request, job_id):
    """폴링용: GET /api/temp/job/<job_id>/"""
    job = JOBS.get(job_id)
    if not job:
        return Response({'error': 'job 없음'}, status=404)

    resp = dict(job)
    if job.get('status') == 'queued':
        with _QUEUE_LOCK:
            try:
                position = _QUEUE_ORDER.index(job_id)  # 0 = 바로 다음 차례
            except ValueError:
                position = 0
        avg_duration = (
            sum(_RECENT_DURATIONS) / len(_RECENT_DURATIONS)
            if _RECENT_DURATIONS else _DEFAULT_DURATION_ESTIMATE
        )
        resp['ahead_count'] = position
        resp['estimated_wait_seconds'] = round(position * avg_duration + avg_duration, 1)

    return Response(resp)


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
            defaults={'kind': kind, 'label': label},
        )
        variant.kind = kind
        variant.label = label
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

    def _delete_song_fully(self, song):
        """
        [내부 공용] 곡 완전 삭제 - 데코레이터 없음, API로 직접 호출 불가
        - 언제 호출: destroy(), delete_variant()에서 보정본 삭제 시, delete_variant_by_semitones()에서 semitones=0일 때
        - 역할: 모든 ScoreVariant 이미지 파일 삭제 + 원본 이미지 파일 삭제 + Song 레코드 삭제
        - 보정본=곡 자체이므로 보정본 삭제 요청 시 이 함수가 호출됨
        """
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

    @action(detail=True, methods=['delete'], url_path='variants/(?P<variant_id>[^/.]+)')
    def delete_variant(self, request, id=None, variant_id=None):
        """
        개별 버전 삭제 API (ID 기반)
        - 언제 호출: DELETE /api/songs/{song_id}/variants/{variant_id}/
        - 역할:
        1) variant가 보정본( transpose_semitones==0 또는 KIND_CORRECTED )이면 -> _delete_song_fully() 호출로 곡 전체 삭제
        2) 조옮김 버전이면 -> 해당 variant 이미지 파일 + DB 레코드만 삭제, Song은 유지
        - 반환: 보정본 삭제 시 {deleted:'song'}, 조옮김 삭제 시 갱신된 SongSerializer
        """
        song = self.get_object()
        try:
            variant = song.variants.get(id=variant_id)
        except ScoreVariant.DoesNotExist:
            return Response({'error': '버전 없음'}, status=404)

        # 보정본 삭제 = 곡 전체 삭제
        is_corrected = (variant.transpose_semitones == 0) or (variant.kind == ScoreVariant.KIND_CORRECTED)
        if is_corrected:
            self._delete_song_fully(song)
            return Response({'deleted': 'song', 'message': '보정본 삭제 - 곡 전체가 삭제되었습니다'}, status=200)

        # 조옮김 버전만 삭제
        if variant.image and variant.image.name:
            try:
                variant.image.storage.delete(variant.image.name)
            except Exception:
                pass
        variant.delete()
        song = Song.objects.prefetch_related('variants').get(pk=song.pk)
        return Response(SongSerializer(song, context={'request': request}).data)

    @action(detail=True, methods=['delete'], url_path='variant_by_semitones')
    def delete_variant_by_semitones(self, request, id=None):
        """
        개별 버전 삭제 API (semitones 기반) - 프론트 편의용
        - 언제 호출: DELETE /api/songs/{song_id}/variant_by_semitones/?semitones=2
        - 역할:
        1) semitones==0이면 보정본으로 간주 -> _delete_song_fully() 호출로 곡 전체 삭제
        2) semitones!=0이면 해당 semitones의 variant 이미지 + DB만 삭제
        - 반환: 보정본 삭제 시 {deleted:'song'}, 조옮김 삭제 시 갱신된 SongSerializer
        """
        song = self.get_object()
        semitones = request.query_params.get('semitones')
        if semitones is None:
            return Response({'error': 'semitones 필수'}, status=400)
        try:
            from .utils.chord_transpose import normalize_semitones
            semitones = normalize_semitones(semitones)
        except Exception:
            try:
                semitones = int(semitones)
            except:
                semitones = 0

        # 보정본(0) 삭제 요청 = 곡 전체 삭제
        if semitones == 0:
            self._delete_song_fully(song)
            return Response({'deleted': 'song', 'message': '보정본 삭제 - 곡 전체가 삭제되었습니다'}, status=200)

        qs = song.variants.filter(transpose_semitones=semitones)
        if not qs.exists():
            return Response({'error': '해당 버전 없음'}, status=404)
        for v in qs:
            if v.image and v.image.name:
                try:
                    v.image.storage.delete(v.image.name)
                except Exception:
                    pass
        qs.delete()
        song = Song.objects.prefetch_related('variants').get(pk=song.pk)
        return Response(SongSerializer(song, context={'request': request}).data)
    
    def partial_update(self, request, *args, **kwargs):
        song = self.get_object()
        if 'chords' in request.data:
            song.chords = request.data['chords']
        if 'title' in request.data:
            song.title = request.data['title']
        song.save()
        return Response(SongSerializer(song, context={'request': request}).data)
