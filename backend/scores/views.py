from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import ScoreSheet
from .serializers import ScoreSheetSerializer, ScoreSheetUploadSerializer
from .utils.image_process import optimize_for_mobile


class ScoreSheetViewSet(viewsets.ModelViewSet):
    queryset = ScoreSheet.objects.all()
    serializer_class = ScoreSheetSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return ScoreSheet.objects.all()

    @action(detail=False, methods=['get'])
    def search(self, request):
        """제목·공유토큰 검색"""
        from django.db.models import Q
        q = (request.query_params.get('q') or '').strip()
        qs = ScoreSheet.objects.all()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(share_token__icontains=q))
        qs = qs.order_by('-updated_at')[:50]
        return Response(ScoreSheetSerializer(qs, many=True, context={'request': request}).data)


    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        """이미지 업로드 → 모바일 최적화 → (옵션) OCR(위치 포함)"""
        ser = ScoreSheetUploadSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded = ser.validated_data['image']
        title = ser.validated_data.get('title', '')
        run_ocr = str(request.data.get('run_ocr', request.query_params.get('run_ocr', 'true'))).lower() in (
            '1', 'true', 'yes',
        )

        optimized_content = optimize_for_mobile(uploaded)
        sheet = ScoreSheet(title=title or getattr(uploaded, 'name', 'Untitled'))
        sheet.optimized_image.save(optimized_content.name, optimized_content, save=True)

        if hasattr(uploaded, 'close'):
            try:
                uploaded.close()
            except Exception:
                pass

        if run_ocr and sheet.optimized_image:
            try:
                from .utils.ocr import run_ocr as do_ocr
                from .utils.file_local import local_image_path
                with local_image_path(sheet.optimized_image) as _p:
                    ocr_result = do_ocr(_p)
                sheet.ocr_raw_text = ocr_result.get('raw_text', '')
                sheet.chords = ocr_result.get('chords', [])
                sheet.save(update_fields=['ocr_raw_text', 'chords', 'updated_at'])
            except Exception as e:
                sheet.ocr_raw_text = f'[OCR error] {e}'
                sheet.save(update_fields=['ocr_raw_text', 'updated_at'])

        return Response(
            ScoreSheetSerializer(sheet, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def ocr(self, request, id=None):
        """PaddleOCR 실행 → 코드+위치 저장"""
        sheet = self.get_object()
        if not sheet.optimized_image:
            return Response({'error': '이미지가 없습니다'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from .utils.ocr import run_ocr as do_ocr
            from .utils.file_local import local_image_path
            with local_image_path(sheet.optimized_image) as _p:
                result = do_ocr(_p)
        except Exception as e:
            import traceback
            return Response(
                {
                    'error': f'OCR 실패: {e}',
                    'detail': traceback.format_exc(),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        sheet.ocr_raw_text = result.get('raw_text', '')
        apply_chords = request.data.get('apply_chords', True)
        if apply_chords:
            sheet.chords = result.get('chords', [])
            sheet.transpose_semitones = 0
        sheet.save(update_fields=['ocr_raw_text', 'chords', 'transpose_semitones', 'updated_at'])

        data = ScoreSheetSerializer(sheet, context={'request': request}).data
        data['ocr_lines'] = [
            {'text': l.get('text'), 'confidence': l.get('confidence'), 'norm': l.get('norm')}
            for l in result.get('lines', [])
        ]
        return Response(data)

    @action(detail=True, methods=['post'])
    def transpose(self, request, id=None):
        """
        조옮김 반음 수만 저장. 보정된 원본 chords(위치·코드)는 유지.
        화면/확정 렌더는 원본 + semitones 로 계산.
        """
        sheet = self.get_object()
        semitones = request.data.get('semitones')
        if semitones is None:
            return Response({'error': 'semitones 필수'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            semitones = int(semitones)
        except (TypeError, ValueError):
            return Response({'error': 'semitones는 정수여야 함'}, status=status.HTTP_400_BAD_REQUEST)

        sheet.transpose_semitones = semitones
        sheet.save(update_fields=['transpose_semitones', 'updated_at'])
        return Response(ScoreSheetSerializer(sheet, context={'request': request}).data)

    @action(detail=True, methods=['patch'])
    def update_chords(self, request, id=None):
        """코드 목록/위치 수정 (오버레이 편집 결과 저장)"""
        sheet = self.get_object()
        chords = request.data.get('chords')
        if chords is None:
            return Response({'error': 'chords 필수'}, status=status.HTTP_400_BAD_REQUEST)

        sheet.chords = chords
        for field in ('ocr_raw_text', 'title', 'original_key', 'lyrics_or_notes'):
            if field in request.data:
                setattr(sheet, field, request.data[field])
        sheet.save()
        return Response(ScoreSheetSerializer(sheet, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, id=None):
        """
        확정: 현재 코드(조옮김 반영)로 새 악보 이미지 생성.
        원본 optimized_image 위에 코드를 다시 그려 새 파일로 저장.
        """
        sheet = self.get_object()
        if not sheet.optimized_image:
            return Response({'error': '이미지가 없습니다'}, status=status.HTTP_400_BAD_REQUEST)

        # 클라이언트에서 넘긴 표시용 chords(조옮김 반영) 우선, 없으면 저장된 원본 + semitones
        from .utils.chord_transpose import transpose_chord_str
        render_chords = request.data.get('chords')
        if render_chords is None:
            render_chords = sheet.chords or []
            delta = sheet.transpose_semitones or 0
            if delta:
                applied = []
                for item in render_chords:
                    if isinstance(item, dict) and 'items' in item:
                        line = dict(item)
                        line['items'] = [
                            {**it, 'chord': transpose_chord_str(it.get('chord', ''), delta)}
                            if isinstance(it, dict) else it
                            for it in (item.get('items') or [])
                        ]
                        applied.append(line)
                    else:
                        applied.append(item)
                render_chords = applied

        try:
            from .utils.render_sheet import render_transposed_sheet
            from .utils.file_local import local_image_path
            with local_image_path(sheet.optimized_image) as _p:
                content = render_transposed_sheet(_p, render_chords)
        except Exception as e:
            return Response({'error': f'렌더 실패: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 원본(optimized)은 유지, 결과는 result_image에 별도 저장
        sheet.result_image.save(content.name, content, save=True)

        data = ScoreSheetSerializer(sheet, context={'request': request}).data
        data['message'] = '새 기타 코드 악보가 생성되었습니다'
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        """DB + optimized_image + result_image 삭제. 파일 없으면 무시."""
        import os
        sheet = self.get_object()
        for field_name in ('optimized_image', 'result_image'):
            field_file = getattr(sheet, field_name, None)
            if field_file is None:
                continue
            name = getattr(field_file, 'name', None) or ''
            # storage 삭제
            if name:
                try:
                    field_file.storage.delete(name)
                except Exception:
                    pass
            # 로컬 path 삭제
            try:
                path = field_file.path
            except Exception:
                path = None
            if path:
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except Exception:
                    pass
            # 필드 값 클리어 (삭제 전)
            try:
                setattr(sheet, field_name, None)
            except Exception:
                pass
        try:
            sheet.save(update_fields=['optimized_image', 'result_image'])
        except Exception:
            pass
        sheet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='by-token/(?P<token>[^/.]+)')
    def by_token(self, request, token=None):
        sheet = get_object_or_404(ScoreSheet, share_token=token)
        return Response(ScoreSheetSerializer(sheet, context={'request': request}).data)
