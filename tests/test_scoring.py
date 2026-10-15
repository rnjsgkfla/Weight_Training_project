"""scoring.py — 점수가 판정(양호/지적)과 일치하는지 확인 (가짜 판정 결과로 빠르게)."""
import pytest

from scoring import item_score, session_score, SCORE_WEIGHTS


def metric(tol, closeness=0.0, n=10):
    return {'dev': 0.0, 'tol': tol, 'ratio': 0.0, 'closeness': closeness, 'n': n}


def fault(feature, max_dev):
    return {'feature': feature, 'max_dev': max_dev}


def squat_side_rep(faults=(), **closeness):
    tols = {'knee': 15.0, 'hip_depth': 0.15, 'trunk': 12.0, 'knee_travel': 0.15}
    return {'view': 'side', 'faults': list(faults),
            'metrics': {f: metric(t, closeness.get(f, 0.0)) for f, t in tols.items()}}


def item(result, key):
    return next(i for i in result['items'] if i['item'] == key)


def test_weights_sum_to_one():
    for weights in SCORE_WEIGHTS.values():
        assert sum(weights.values()) == pytest.approx(1.0)


@pytest.mark.parametrize('closeness, expected', [(0.0, 100.0), (0.5, 90.0), (1.0, 80.0)])
def test_item_without_fault_stays_in_80_100(closeness, expected):
    assert item_score(closeness, 0, 4, None) == pytest.approx(expected)


@pytest.mark.parametrize('fault_reps, severity, expected', [
    (1, 1.0, 79 * (1 - 0.5 * 1 / 4)),           # 1/4 회차, 허용오차 살짝 넘음
    (4, 2.0, 79 * (1 - 0.5 - 0.5 * 0.5)),       # 전 회차, 허용오차의 2배
    (4, 3.0, 0.0), (4, 9.0, 0.0),               # 전 회차, 허용오차의 3배 이상 → 0
])
def test_item_with_fault_is_below_80(fault_reps, severity, expected):
    assert item_score(0.0, fault_reps, 4, severity) == pytest.approx(expected)


def test_perfect_reps_score_100():
    result = session_score('squat', [squat_side_rep(), squat_side_rep()])
    assert result['score'] == pytest.approx(100.0)


def test_all_good_reps_score_at_least_80_even_near_tolerance():
    # 지적은 없지만 내내 허용오차에 바짝 붙어 있던 경우 → 80 (예전 방식은 0 점까지 떨어졌다)
    near = dict(knee=1.0, hip_depth=1.0, trunk=1.0, knee_travel=1.0)
    result = session_score('squat', [squat_side_rep(**near)] * 3)
    assert result['score'] == pytest.approx(80.0)


def test_any_fault_caps_score_below_80():
    # 4회 중 1회만 상체 기울기가 허용오차를 살짝 넘음 → 나머지가 완벽해도 79 이하
    reps = [squat_side_rep([fault('trunk', 12.5)])] + [squat_side_rep() for _ in range(3)]
    result = session_score('squat', reps)
    assert result['score'] == pytest.approx(79.0)
    trunk = item(result, 'side.trunk')
    assert (trunk['fault_reps'], trunk['total_reps']) == (1, 4)
    assert trunk['severity'] == pytest.approx(12.5 / 12.0, abs=0.01)
    assert trunk['score'] < 80
    assert item(result, 'side.knee')['score'] == pytest.approx(100.0)


def test_more_frequent_and_severe_faults_score_lower():
    mild = session_score('squat', [squat_side_rep([fault('knee', 18.0)]), squat_side_rep()])
    severe = session_score('squat', [squat_side_rep([fault('knee', 40.0)]) for _ in range(2)])
    assert severe['score'] < mild['score'] < 80


def test_weights_renormalized_over_uploaded_views():
    # 측면만 올리면 측면 항목 가중치만으로 합이 1
    result = session_score('squat', [squat_side_rep()])
    assert {i['view'] for i in result['items']} == {'side'}
    assert sum(i['weight'] for i in result['items']) == pytest.approx(1.0)


def test_front_view_faults_lower_the_score():
    # 정면 지적(무릎 모임)도 점수에 반영된다
    front = {'view': 'front', 'faults': [fault('valgus', -0.3)],
             'metrics': {f: metric(t) for f, t in
                         {'valgus': 0.15, 'stance': 0.2, 'sym_knee': 8.0, 'sym_hip': 0.08}.items()}}
    result = session_score('squat', [squat_side_rep(), front])
    assert result['score'] < 80
    assert item(result, 'front.valgus')['severity'] == pytest.approx(2.0)


def test_no_scorable_items_returns_none():
    assert session_score('lateral_raise', [squat_side_rep()]) is None


def test_old_score_detail_records_still_validate():
    # 구버전(DTW 평균 오차 방식) 기록도 히스토리 상세 응답으로 열려야 한다
    from schemas import SessionStats
    old = {'score': 12, 'rep_count': {'side': 4}, 'reps': [], 'warnings': [],
           'score_detail': {'combined_error': 0.88, 'items': [
               {'item': 'knee', 'name': '무릎 각도', 'weight': 0.4, 'unit': '°',
                'tolerance': 15.0, 'mean_error': 31.6, 'normalized_error': 1.0}]}}
    assert SessionStats.model_validate(old).score_detail.items[0].normalized_error == 1.0


def lunge_reps(side_faults=(), front_faults=()):
    side = {'view': 'side', 'faults': list(side_faults), 'metrics': {f: metric(t) for f, t in
            {'knee': 25.0, 'back_knee': 20.0, 'hip_depth': 0.45, 'trunk': 12.0, 'knee_travel': 0.65}.items()}}
    front = {'view': 'front', 'faults': list(front_faults), 'metrics': {f: metric(t) for f, t in
             {'trunk': 12.0, 'valgus': 0.12, 'sym_hip': 0.12}.items()}}
    return [side, front]


def test_lunge_side_view_weighs_80_percent():
    result = session_score('lunge', lunge_reps())
    side = sum(i['weight'] for i in result['items'] if i['view'] == 'side')
    assert side == pytest.approx(0.80)
    assert result['score'] == pytest.approx(100.0)


def test_lunge_faulted_items_gain_weight():
    # 상체 기울기가 허용오차의 3배 이상 → p = 1 → 가중치 0.13 × 3
    result = session_score('lunge', lunge_reps(side_faults=[fault('trunk', 40.0)]))
    trunk = item(result, 'side.trunk')
    assert trunk['score'] == 0.0
    assert trunk['weight'] == pytest.approx(0.39 / 1.26, abs=1e-4)
    # 비중 확대가 없으면 100 − 13 = 87 → 79 로 잘리지만, 확대하면 그보다 낮아진다
    assert result['score'] == pytest.approx(100 * (1 - 0.39 / 1.26))


def test_fault_emphasis_is_lunge_only():
    # 스쿼트는 지적 항목도 기본 가중치 그대로
    result = session_score('squat', [squat_side_rep([fault('trunk', 40.0)])])
    assert item(result, 'side.trunk')['weight'] == pytest.approx(0.15 / 0.65, abs=1e-4)
