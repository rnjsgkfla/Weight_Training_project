"""샘플 사용자 영상(data/raw/user_squat_*) 전체 파이프라인 회귀 테스트.

파이프라인·판정 규칙을 고쳐서 아래 값이 바뀌면, 의도한 변화인지 확인한 뒤 기대값을 갱신한다.
"""
import pytest

from conftest import require_reference
from analyze import analyze_for_ui, REFERENCE

SIDE_VIDEO = "data/raw/user_squat_side_raw.mp4"
FRONT_VIDEO = "data/raw/user_squat_front_raw.mp4"


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    require_reference(*REFERENCE['squat']['side'], *REFERENCE['squat']['front'])
    return analyze_for_ui('squat', SIDE_VIDEO, FRONT_VIDEO,
                          workdir=str(tmp_path_factory.mktemp("work")))


def test_rep_count_and_score(result):
    _items, _summary, stats, _report = result
    assert stats['rep_count'] == {'side': 4, 'front': 5}
    # 점수(scoring.py)는 판정 결과로 계산: 지적이 있으니 79 이하, 매 회차 얕고 무릎이 모여 크게 깎인다
    assert stats['score'] == 42
    items = {i['item']: i for i in stats['score_detail']['items']}
    assert set(items) == {'side.knee', 'side.hip_depth', 'side.trunk', 'side.knee_travel',
                          'front.valgus', 'front.stance', 'front.sym_knee', 'front.sym_hip'}
    # 지적된 항목은 80 미만, 지적 없는 항목은 80 이상 (판정과 일치)
    faulted = {f"{r['view']}.{m['feature']}" for r in stats['reps'] for m in r['metrics'] if m['fault']}
    for key, it in items.items():
        assert (it['score'] < 80) == (key in faulted)
    assert items['side.hip_depth']['score'] == 0.0     # 4회 모두, 허용오차의 3.5배
    assert (items['front.sym_knee']['fault_reps'], items['front.sym_knee']['total_reps']) == (1, 5)


def test_faulted_features_per_rep(result):
    _items, _summary, stats, _report = result
    faulted = [(r['view'], r['rep'], sorted(m['feature'] for m in r['metrics'] if m['fault']))
               for r in stats['reps']]
    assert faulted == [
        ('side', 1, ['hip_depth', 'knee']),
        ('side', 2, ['hip_depth', 'knee']),
        ('side', 3, ['hip_depth', 'knee']),
        ('side', 4, ['hip_depth', 'knee']),
        ('front', 1, ['stance', 'valgus']),
        ('front', 2, ['stance', 'valgus']),
        ('front', 3, ['stance', 'valgus']),
        ('front', 4, ['stance', 'valgus']),
        ('front', 5, ['stance', 'sym_knee', 'valgus']),
    ]


def test_stats_consistent_with_items(result):
    items, _summary, stats, _report = result
    # 결함 항목 수 == 회차별 fault_count 합
    assert sum(not it['ok'] for it in items) == sum(r['fault_count'] for r in stats['reps'])
    # 모든 회차가 그 뷰의 판정 대상 특징을 빠짐없이 가진다
    expected = {'side': {'knee', 'hip_depth', 'trunk', 'knee_travel'},
                'front': {'valgus', 'stance', 'sym_knee', 'sym_hip'}}
    for r in stats['reps']:
        assert {m['feature'] for m in r['metrics']} == expected[r['view']]
        # 결함으로 지적된 특징은 반드시 허용오차를 넘은 적이 있다
        assert all(m['ratio'] > 1 for m in r['metrics'] if m['fault'])


def test_issue_cards(result):
    _items, _summary, stats, report = result
    issues = report['issues']
    # 측면·정면 모두 모든 회차에서 반복된 문제가 먼저, 그중 더 심한 순 → 측면 엉덩이 깊이(3.5배)가 1순위
    assert [i['key'] for i in issues] == [
        'side.hip_depth', 'side.knee', 'front.valgus', 'front.stance', 'front.sym_knee']
    top = issues[0]
    assert top['reps'] == [1, 2, 3, 4] and top['total_reps'] == 4
    assert top['name'] == '엉덩이 깊이'
    # 상위 3개만 비교 프레임, DTW 로 맞춘 국면 라벨이 붙는다
    assert [len(i['clip']) for i in issues] == [12, 12, 12, 0, 0]
    assert {c['phase'] for c in top['clip']} <= {'하강', '최저', '상승'}
    assert report['good_points'] == ['상체 기울기', '무릎 전방이동', '골반 수평']
