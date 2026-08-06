"""
조옮김 온디맨드 전환 후 불필요해진 ScoreVariant 이미지·DB 정리.

사용:
  python manage.py cleanup_variants           # dry-run (삭제 안 함, 목록만)
  python manage.py cleanup_variants --apply   # 실제 삭제

원본(Song.original_image)은 건드리지 않습니다.
"""
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage

from scores.models import ScoreVariant


class Command(BaseCommand):
    help = 'ScoreVariant 이미지(스토리지)와 DB 레코드 정리. 원본 악보는 유지.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='실제로 삭제합니다. 없으면 dry-run만 합니다.',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        qs = ScoreVariant.objects.all().select_related('song')
        total = qs.count()
        with_image = 0
        deleted_files = 0
        errors = []

        self.stdout.write(f'ScoreVariant 레코드: {total}개')
        if not apply:
            self.stdout.write(self.style.WARNING('dry-run 모드 — 삭제하지 않습니다. --apply 로 실행하세요.'))

        for v in qs.iterator():
            name = getattr(v.image, 'name', None) or ''
            if name:
                with_image += 1
                if apply:
                    try:
                        if default_storage.exists(name):
                            default_storage.delete(name)
                            deleted_files += 1
                            self.stdout.write(f'  file deleted: {name}')
                        else:
                            self.stdout.write(f'  file missing: {name}')
                    except Exception as e:
                        errors.append(f'{name}: {e}')
                        self.stderr.write(self.style.ERROR(f'  file error: {name} — {e}'))
                else:
                    self.stdout.write(f'  would delete file: {name} (song={v.song_id})')

        if apply:
            deleted_rows, _ = ScoreVariant.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(
                f'완료: DB {deleted_rows}행 삭제, 스토리지 파일 {deleted_files}개 삭제 '
                f'(이미지 있던 레코드 {with_image}개)'
            ))
        else:
            self.stdout.write(
                f'요약: 레코드 {total}개, 이미지 있는 것 {with_image}개 — '
                f'적용하려면: python manage.py cleanup_variants --apply'
            )

        if errors:
            self.stderr.write(self.style.ERROR(f'오류 {len(errors)}건'))
