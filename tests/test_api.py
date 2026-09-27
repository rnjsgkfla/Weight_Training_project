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
    'score_detail': None,
    'warnings': [],
}
FRAME = {'video': 'v.mp4', 'frame': 1, 'landmarks': 'lm.csv', 'joints': [25], 'color': (0, 0, 255)}
FAKE_ISSUE = {
    'key': 'side.knee', 'view': 'side', 'view_kr': '측면', 'feature': 'knee', 'name': '무릎 깊이',
    'unit': '°', 'headline': '무릎을 더 굽혀 깊이 앉으세요', 'advice': None, 'reps': [1],
    'total_reps': 1, 'severity': 2.0, 'rep': 1, 'phase': '최저', 'time_sec': 1.0,
    'ref_val': 90.0, 'user_val': 120.0, 'thumb': {'ref': FRAME, 'user': FRAME},
    'clip': [{'ref': FRAME, 'user': FRAME, 'phase': '하강'}, {'ref': FRAME, 'user': FRAME, 'phase': '최저'}],
}
FAKE_REPORT = {'issues': [FAKE_ISSUE], 'good_points': ['상체 기울기']}
EMPTY_REPORT = {'issues': [], 'good_points': []}
EMPTY_STATS = {'score': None, 'score_detail': None, 'rep_count': {}, 'reps': [],
               'warnings': ['측면: 사람을 찾지 못했어요.']}
VIDEO = {'side_video': ('s.mp4', b'fake', 'video/mp4')}


@pytest.fixture(autouse=True)
def fake_analysis(monkeypatch):
    monkeypatch.setattr(api, 'analyze_for_ui', lambda *a, **k: ([FAKE_ITEM], '요약', FAKE_STATS, FAKE_REPORT))
    monkeypatch.setattr(api, '_jpeg', lambda video, frame: b'jpeg-' + video.encode())
    monkeypatch.setattr(api.issue_cards, 'render_frames',
                        lambda frames: [f'frame{n}'.encode() for n in range(len(frames))])


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


def test_analyze_returns_issue_cards(client):
    body = post_analyze(client).json()
    assert body['good_points'] == ['상체 기울기']
    issue = body['issues'][0]
    assert issue['headline'] == '무릎을 더 굽혀 깊이 앉으세요'
    # 이미지 순서: 썸네일(모범, 내 자세) → 비교 프레임마다 (모범, 내 자세)
    assert issue['thumb_ref'] == api.jpeg_data_uri(b'frame0')
    assert issue['thumb_user'] == api.jpeg_data_uri(b'frame1')
    assert [c['phase'] for c in issue['clip']] == ['하강', '최저']
    assert issue['clip'][1]['user_image'] == api.jpeg_data_uri(b'frame5')
    assert 'thumb' not in issue and 'clip_phases' not in issue


def test_analyze_with_login_is_saved(client):
    headers = signup(client)
    res = post_analyze(client, headers)
    assert res.status_code == 200
    assert isinstance(res.json()['session_id'], int)
    assert len(client.get('/sessions', headers=headers).json()) == 1


def test_analyze_with_no_reps_is_not_saved(client, monkeypatch):
    monkeypatch.setattr(api, 'analyze_for_ui', lambda *a, **k: ([], '인식 실패', EMPTY_STATS, EMPTY_REPORT))
    headers = signup(client)
    res = post_analyze(client, headers)
    assert res.status_code == 200
    assert res.json()['stats'] == EMPTY_STATS
    assert res.json()['session_id'] is None
    assert client.get('/sessions', headers=headers).json() == []


def test_analyze_without_score_is_still_saved(client, monkeypatch):
    # 스쿼트 정면 영상만 올리면 점수는 없지만(측면 필요) 피드백은 기록으로 남긴다
    front_only = dict(FAKE_STATS, score=None,
                      warnings=['점수: 측면 영상이 있어야 점수를 계산할 수 있어요.'])
    monkeypatch.setattr(api, 'analyze_for_ui', lambda *a, **k: ([FAKE_ITEM], '요약', front_only, EMPTY_REPORT))
    headers = signup(client)
    res = post_analyze(client, headers)
    assert res.status_code == 200
    assert isinstance(res.json()['session_id'], int)


def test_analyze_with_invalid_token_is_rejected(client):
    res = post_analyze(client, {'Authorization': 'Bearer not-a-token'})
    assert res.status_code == 401
