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
    _items, _summary, stats = result
    assert stats['rep_count'] == {'side': 4, 'front': 5}
    assert stats['score'] == 47


def test_faulted_features_per_rep(result):
    _items, _summary, stats = result
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
    items, _summary, stats = result
    # 결함 항목 수 == 회차별 fault_count 합
    assert sum(not it['ok'] for it in items) == sum(r['fault_count'] for r in stats['reps'])
    # 모든 회차가 그 뷰의 판정 대상 특징을 빠짐없이 가진다
    expected = {'side': {'knee', 'hip_depth', 'trunk', 'knee_travel'},
                'front': {'valgus', 'stance', 'sym_knee', 'sym_hip'}}
    for r in stats['reps']:
        assert {m['feature'] for m in r['metrics']} == expected[r['view']]
        # 결함으로 지적된 특징은 반드시 허용오차를 넘은 적이 있다
        assert all(m['ratio'] > 1 for m in r['metrics'] if m['fault'])
