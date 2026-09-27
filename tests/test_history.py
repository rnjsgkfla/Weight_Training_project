"""기록 목록·상세·삭제·발전 추이. 분석은 가짜 결과로 대신한다."""
import os
from datetime import datetime, timedelta, timezone

import pytest

import api
from conftest import signup
from test_api import FAKE_ITEM, FAKE_REPORT, FAKE_STATS, VIDEO


def make_stats(knee_ratio, knee_fault):
    return {'score': 50 if knee_fault else 100, 'rep_count': {'side': 1},
            'reps': [{'view': 'side', 'rep': 1, 'fault_count': int(knee_fault), 'metrics': [
                {'feature': 'knee', 'name': '무릎 깊이', 'unit': '°', 'dev': 15.0 * knee_ratio,
                 'tol': 15.0, 'ratio': knee_ratio, 'fault': knee_fault},
                {'feature': 'trunk', 'name': '상체 기울기', 'unit': '°', 'dev': 0.0,
                 'tol': 12.0, 'ratio': 0.0, 'fault': False},
            ]}], 'score_detail': None, 'warnings': []}


@pytest.fixture
def analyze_as(client, monkeypatch):
    """analyze_as(headers, stats, exercise) → 가짜 결과로 /analyze 를 호출해 session_id 반환."""
    monkeypatch.setattr(api, '_jpeg', lambda video, frame: b'jpeg-' + video.encode())
    monkeypatch.setattr(api.issue_cards, 'render_frames',
                        lambda frames: [f'frame{n}'.encode() for n in range(len(frames))])

    def run(headers, stats=FAKE_STATS, exercise='squat'):
        monkeypatch.setattr(api, 'analyze_for_ui', lambda *a, **k: ([FAKE_ITEM], '요약', stats, FAKE_REPORT))
        res = client.post('/analyze', data={'exercise': exercise}, files=VIDEO, headers=headers)
        assert res.status_code == 200, res.text
        return res.json()['session_id']
    return run


def test_list_sessions(client, analyze_as):
    headers = signup(client)
    first = analyze_as(headers)
    second = analyze_as(headers, exercise='lunge')
    rows = client.get('/sessions', headers=headers).json()
    assert [r['id'] for r in rows] == [second, first]  # 최신순
    assert rows[1]['score'] == 75
    assert rows[1]['rep_count'] == {'side': 1}
    assert rows[1]['top_faults'] == ['무릎 깊이']
    assert rows[1]['created_at'].endswith(('Z', '+00:00'))  # UTC 명시

    squat_only = client.get('/sessions', params={'exercise': 'squat'}, headers=headers).json()
    assert [r['id'] for r in squat_only] == [first]


def test_list_sessions_time_filter(client, analyze_as):
    headers = signup(client)
    analyze_as(headers)
    now = datetime.now(timezone.utc)
    future = (now + timedelta(hours=1)).isoformat()
    past = (now - timedelta(hours=1)).isoformat()
    assert client.get('/sessions', params={'since': future}, headers=headers).json() == []
    assert len(client.get('/sessions', params={'since': past}, headers=headers).json()) == 1
    assert client.get('/sessions', params={'until': past}, headers=headers).json() == []
    # 시간대가 다른(KST) 시각도 UTC 로 환산해 비교한다
    kst_future = (now + timedelta(hours=1)).astimezone(timezone(timedelta(hours=9))).isoformat()
    assert client.get('/sessions', params={'since': kst_future}, headers=headers).json() == []


def test_session_detail_restores_response(client, analyze_as):
    headers = signup(client)
    sid = analyze_as(headers)
    res = client.get(f'/sessions/{sid}', headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body['session_id'] == sid
    assert body['stats'] == FAKE_STATS
    item = body['items'][0]
    assert item['message'] == '더 앉으세요'
    assert item['ref_image'] == api.jpeg_data_uri(b'jpeg-r.mp4')
    assert item['user_image'] == api.jpeg_data_uri(b'jpeg-u.mp4')


def test_session_detail_restores_issue_cards(client, analyze_as):
    headers = signup(client)
    sid = analyze_as(headers)
    body = client.get(f'/sessions/{sid}', headers=headers).json()
    issue = body['issues'][0]
    assert body['good_points'] == ['상체 기울기']
    assert issue['headline'] == FAKE_REPORT['issues'][0]['headline']
    assert issue['thumb_user'] == api.jpeg_data_uri(b'frame1')
    assert [c['phase'] for c in issue['clip']] == ['하강', '최저']
    assert issue['clip'][1]['ref_image'] == api.jpeg_data_uri(b'frame4')


def test_old_session_without_report_has_no_issues(client, analyze_as):
    # 문제 카드 기능 이전에 저장된 기록(report 없음)은 issues 가 null → 앱이 예전 목록을 보여준다
    import db
    headers = signup(client)
    sid = analyze_as(headers)
    with db.SessionLocal() as s:
        s.get(db.WorkoutSession, sid).report = None
        s.commit()
    body = client.get(f'/sessions/{sid}', headers=headers).json()
    assert body['issues'] is None and body['good_points'] == []


def test_other_users_session_is_hidden(client, analyze_as):
    mine = signup(client, email='a@example.com')
    theirs = signup(client, email='b@example.com')
    sid = analyze_as(mine)
    assert client.get(f'/sessions/{sid}', headers=theirs).status_code == 404
    assert client.delete(f'/sessions/{sid}', headers=theirs).status_code == 404
    assert client.get('/sessions', headers=theirs).json() == []


def test_delete_session_removes_images(client, analyze_as):
    headers = signup(client)
    sid = analyze_as(headers)
    media_dir = os.path.join(os.environ['MEDIA_DIR'], str(sid))
    assert os.path.isdir(media_dir)
    assert client.delete(f'/sessions/{sid}', headers=headers).status_code == 204
    assert client.get(f'/sessions/{sid}', headers=headers).status_code == 404
    assert not os.path.exists(media_dir)


def test_delete_me_removes_sessions_and_images(client, analyze_as):
    headers = signup(client)
    sid = analyze_as(headers)
    client.delete('/me', headers=headers)
    assert not os.path.exists(os.path.join(os.environ['MEDIA_DIR'], str(sid)))
    headers = signup(client)  # 같은 이메일로 재가입해도 이전 기록은 없다
    assert client.get('/sessions', headers=headers).json() == []


def test_progress(client, analyze_as):
    headers = signup(client)
    analyze_as(headers, make_stats(2.5, True))
    analyze_as(headers, make_stats(0.8, False))
    analyze_as(headers, exercise='lunge')  # 다른 운동은 제외
    res = client.get('/progress/squat', headers=headers)
    assert res.status_code == 200
    points = res.json()['points']
    assert [p['score'] for p in points] == [50, 100]  # 오래된 순
    knee = [next(f for f in p['features'] if f['feature'] == 'knee') for p in points]
    assert [k['avg_ratio'] for k in knee] == [2.5, 0.8]
    assert [k['fault_rate'] for k in knee] == [1.0, 0.0]
    assert knee[0]['view'] == 'side' and knee[0]['name'] == '무릎 깊이'


def test_progress_unknown_exercise(client):
    headers = signup(client)
    assert client.get('/progress/pushup', headers=headers).status_code == 400
