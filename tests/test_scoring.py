"""scoring.py — 스펙 수식대로 계산되는지 확인 (가짜 반복 데이터로 빠르게)."""
import numpy as np
import pytest

from scoring import (normalized_error, mean_abs_error, score_squat, score_lunge,
                     score_lateral_raise, SCORE_WEIGHTS)


def rep(n, **features):
    """특징값이 모두 같은 가짜 반복 (길이 n)."""
    return {'features': {k: np.full(n, float(v)) for k, v in features.items()}}


def identity_path(n):
    return [(t, t) for t in range(n)]


def item(result, name):
    return next(i for i in result['items'] if i['item'] == name)


@pytest.mark.parametrize('D, T, expected', [
    (0, 20, 0.0), (5, 20, 0.25), (10, 20, 0.5), (15, 20, 0.75), (20, 20, 1.0), (25, 20, 1.0),  # 각도 예시
    (0.02, 0.10, 0.2), (0.05, 0.10, 0.5), (0.08, 0.10, 0.8), (0.10, 0.10, 1.0), (0.3, 0.10, 1.0),  # 위치 예시
])
def test_normalized_error_examples(D, T, expected):
    assert normalized_error(D, T) == pytest.approx(expected)


def test_weights_sum_to_one():
    for weights in SCORE_WEIGHTS.values():
        assert sum(weights.values()) == pytest.approx(1.0)


def test_mean_error_pools_all_pairs_across_reps():
    # 회차별 평균의 평균이 아니라, 모든 대응쌍을 합친 평균이어야 한다
    expert = rep(6, knee=100)
    short = (expert, rep(2, knee=110), [(0, 0), (1, 1)])            # 오차 10 × 2쌍
    long = (expert, rep(6, knee=100), identity_path(6))             # 오차 0 × 6쌍
    assert mean_abs_error([short, long], 'knee') == pytest.approx(20 / 8)  # (회차 평균의 평균이면 5)


def test_mean_error_is_absolute():
    expert = rep(4, knee=100)
    user = {'features': {'knee': np.array([90.0, 110.0, 90.0, 110.0])}}
    assert mean_abs_error([(expert, user, identity_path(4))], 'knee') == pytest.approx(10.0)


def test_squat_score():
    # 무릎 6° (e=6/15=0.4), 골반 0.03 (e=0.03/0.15=0.2), 상체 0 → E = 0.40×0.4 + 0.35×0.2 = 0.23
    expert = rep(5, knee=90, hip_depth=0.0, trunk=30)
    user = rep(5, knee=96, hip_depth=0.03, trunk=30)
    result = score_squat([(expert, user, identity_path(5))])
    assert item(result, 'knee')['mean_error'] == pytest.approx(6.0)
    assert item(result, 'knee')['normalized_error'] == pytest.approx(0.4)
    assert item(result, 'pelvis')['normalized_error'] == pytest.approx(0.2)
    assert item(result, 'torso')['normalized_error'] == pytest.approx(0.0)
    assert result['combined_error'] == pytest.approx(0.23)
    assert result['score'] == pytest.approx(77.0)


def test_score_is_clamped_to_0_100():
    expert = rep(5, knee=90, hip_depth=0.0, trunk=30)
    assert score_squat([(expert, rep(5, knee=200, hip_depth=5, trunk=90), identity_path(5))])['score'] == 0.0
    assert score_squat([(expert, rep(5, knee=90, hip_depth=0.0, trunk=30), identity_path(5))])['score'] == 100.0


def test_lunge_uses_four_items():
    expert = rep(3, knee=90, back_knee=90, hip_depth=0.1, trunk=10)
    user = rep(3, knee=90, back_knee=100, hip_depth=0.1, trunk=10)   # 뒷무릎만 10° (e=10/20=0.5)
    result = score_lunge([(expert, user, identity_path(3))])
    assert [i['item'] for i in result['items']] == ['front_knee', 'rear_knee', 'pelvis', 'torso']
    assert result['combined_error'] == pytest.approx(0.20 * 0.5)
    assert result['score'] == pytest.approx(90.0)


def test_lateral_raise_averages_left_right_before_normalizing():
    # 어깨: 왼쪽 오차 10°, 오른쪽 20° → D = 15 → e = min(15/15, 1) = 1.0
    # (좌우를 따로 정규화한 뒤 평균내면 (0.667 + 1.0) / 2 = 0.833 이 되어 틀린 계산)
    base = dict(shoulder_L=80, shoulder_R=80, elbow_L=160, elbow_R=160, wrist_L=-1, wrist_R=-1, trunk=0)
    user = dict(base, shoulder_L=90, shoulder_R=100)
    result = score_lateral_raise([(rep(4, **base), rep(4, **user), identity_path(4))])
    shoulder = item(result, 'shoulder')
    assert shoulder['mean_error'] == pytest.approx(15.0)
    assert shoulder['normalized_error'] == pytest.approx(1.0)
    assert result['combined_error'] == pytest.approx(0.35)
    assert result['score'] == pytest.approx(65.0)
