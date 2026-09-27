"""/analyze 응답 스키마 확인. 무거운 분석은 가짜로 바꿔 빠르게 돈다."""
import pytest
from fastapi.testclient import TestClient

import api

FAKE_ITEM = {
    'key': 'item0', 'label': '⚠️ 측면 · 1회차 · 무릎 깊이', 'detail': '...', 'ok': False,
    'ref_video': 'r.mp4', 'ref_frame': 1, 'user_video': 'u.mp4', 'user_frame': 1,
    'view': '측면', 'rep': 1, 'feature_name': '무릎 깊이', 'phase': '최저', 'time_sec': 1.0,
    'ref_val': 90.0, 'user_val': 120.0, 'dev': 30.0, 'unit': '°', 'message': '더 앉으세요',
}
FAKE_STATS = {
    'score': 75, 'rep_count': {'side': 1},
    'reps': [{'view': 'side', 'rep': 1, 'fault_count': 1, 'metrics': [
        {'feature': 'knee', 'name': '무릎 깊이', 'unit': '°', 'dev': 30.0, 'tol': 15.0,
         'ratio': 2.0, 'fault': True},
        {'feature': 'trunk', 'name': '상체 기울기', 'unit': '°', 'dev': -3.0, 'tol': 12.0,
         'ratio': -0.25, 'fault': False},
    ]}],
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, 'analyze_for_ui', lambda *a, **k: ([FAKE_ITEM], '요약', FAKE_STATS))
    monkeypatch.setattr(api, '_img_data_uri', lambda *a: None)
    return TestClient(api.app)


def test_analyze_returns_stats(client):
    res = client.post('/analyze', data={'exercise': 'squat'},
                      files={'side_video': ('s.mp4', b'fake', 'video/mp4')})
    assert res.status_code == 200
    body = res.json()
    assert body['stats'] == FAKE_STATS
    assert body['items'][0]['feature_name'] == '무릎 깊이'


def test_stats_score_can_be_null(client, monkeypatch):
    empty = {'score': None, 'rep_count': {'side': 0}, 'reps': []}
    monkeypatch.setattr(api, 'analyze_for_ui', lambda *a, **k: ([], '인식 실패', empty))
    res = client.post('/analyze', data={'exercise': 'squat'},
                      files={'side_video': ('s.mp4', b'fake', 'video/mp4')})
    assert res.status_code == 200
    assert res.json()['stats'] == empty
