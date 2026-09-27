"""테스트 공통 설정: 프로젝트 루트 기준 상대경로(data/...)를 쓰므로 루트에서 실행되게 한다."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)


def require_reference(*paths):
    """기준 데이터가 없으면 건너뛴다 (python build_references.py 로 생성)."""
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        pytest.skip(f"기준 데이터 없음 (python build_references.py 실행 필요): {missing}")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """임시 SQLite DB·이미지 폴더를 쓰는 API 테스트 클라이언트 (lifespan 으로 init_db 실행)."""
    from fastapi.testclient import TestClient
    import api

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    with TestClient(api.app) as c:
        yield c


def signup(client, email="me@example.com", password="password123"):
    """회원가입 후 Authorization 헤더 dict 를 돌려준다."""
    res = client.post("/auth/signup", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
