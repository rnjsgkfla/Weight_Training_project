"""
media.py — 기록별 비교 이미지(JPEG) 파일 저장소

  MEDIA_DIR/<session_id>/<item_key>_ref.jpg   모범 자세
  MEDIA_DIR/<session_id>/<item_key>_user.jpg  내 자세

지금은 서버 디스크(Docker 볼륨)에 저장한다. 나중에 S3 로 옮길 때는 이 파일만 바꾸면 된다.
"""

import base64
import os
import shutil

DEFAULT_MEDIA_DIR = "./data/media"


def _session_dir(session_id):
    return os.path.join(os.environ.get("MEDIA_DIR", DEFAULT_MEDIA_DIR), str(session_id))


def save_image(session_id, name, jpeg):
    """JPEG 바이트를 저장한다. jpeg 가 None 이면(프레임 추출 실패) 아무것도 안 한다."""
    if jpeg is None:
        return
    d = _session_dir(session_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{name}.jpg"), "wb") as f:
        f.write(jpeg)


def load_image_uri(session_id, name):
    """저장된 이미지를 data URI 로 돌려준다 (없으면 None)."""
    path = os.path.join(_session_dir(session_id), f"{name}.jpg")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return jpeg_data_uri(f.read())


def delete_session_media(session_id):
    shutil.rmtree(_session_dir(session_id), ignore_errors=True)


def jpeg_data_uri(jpeg):
    if jpeg is None:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
