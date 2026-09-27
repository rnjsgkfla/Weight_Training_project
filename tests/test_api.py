"""/analyze 응답 스키마와 기록 저장 여부 확인. 무거운 분석은 가짜로 바꿔 빠르게 돈다."""
import pytest

import api
from conftest import signup

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
EMPTY_STATS = {'score': None, 'rep_count': {'side': 0}, 'reps': []}
VIDEO = {'side_video': ('s.mp4', b'fake', 'video/mp4')}


@pytest.fixture(autouse=True)
def fake_analysis(monkeypatch):
    monkeypatch.setattr(api, 'analyze_for_ui', lambda *a, **k: ([FAKE_ITEM], '요약', FAKE_STATS))
    monkeypatch.setattr(api, '_jpeg', lambda video, frame: b'jpeg-' + video.encode())


def post_analyze(client, headers=None):
    return client.post('/analyze', data={'exercise': 'squat'}, files=VIDEO, headers=headers or {})


def test_analyze_without_login_is_not_saved(client):
    res = post_analyze(client)
    assert res.status_code == 200
    body = res.json()
    assert body['stats'] == FAKE_STATS
    assert body['session_id'] is None
    assert body['items'][0]['feature_name'] == '무릎 깊이'
    assert body['items'][0]['ref_image'].startswith('data:image/jpeg;base64,')


def test_analyze_with_login_is_saved(client):
    headers = signup(client)
    res = post_analyze(client, headers)
    assert res.status_code == 200
    assert isinstance(res.json()['session_id'], int)
    assert len(client.get('/sessions', headers=headers).json()) == 1


def test_analyze_with_no_reps_is_not_saved(client, monkeypatch):
    monkeypatch.setattr(api, 'analyze_for_ui', lambda *a, **k: ([], '인식 실패', EMPTY_STATS))
    headers = signup(client)
    res = post_analyze(client, headers)
    assert res.status_code == 200
    assert res.json()['stats'] == EMPTY_STATS
    assert res.json()['session_id'] is None
    assert client.get('/sessions', headers=headers).json() == []


def test_analyze_with_invalid_token_is_rejected(client):
    res = post_analyze(client, {'Authorization': 'Bearer not-a-token'})
    assert res.status_code == 401
