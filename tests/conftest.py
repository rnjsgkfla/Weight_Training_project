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
