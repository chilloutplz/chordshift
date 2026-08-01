"""R2 등 원격 스토리지 FieldFile → 로컬 임시 경로."""
import os
import tempfile
from contextlib import contextmanager


@contextmanager
def local_image_path(field_file):
    """
    ImageFieldFile 등에서 로컬 파일 경로를 얻는다.
    - 로컬 스토리지: .path 사용
    - R2/S3: 임시 파일로 받은 뒤 사용, 종료 시 삭제
    """
    if not field_file:
        raise ValueError('파일이 없습니다')

    # 로컬 스토리지
    try:
        path = field_file.path
        if path and os.path.isfile(path):
            yield path
            return
    except NotImplementedError:
        pass
    except Exception:
        pass

    name = getattr(field_file, 'name', '') or 'image.jpg'
    suffix = os.path.splitext(name)[1] or '.jpg'
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        field_file.open('rb')
        try:
            with open(tmp_path, 'wb') as out:
                if hasattr(field_file, 'chunks'):
                    for chunk in field_file.chunks():
                        out.write(chunk)
                else:
                    out.write(field_file.read())
        finally:
            try:
                field_file.close()
            except Exception:
                pass
        yield tmp_path
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
