"""judge_rep 이 결함 여부와 무관하게 특징별 측정값(metrics)을 돌려주는지 확인."""
import copy

import pytest

from conftest import require_reference
from judge import judge_rep, SQUAT_FAULT_RULES
from rep_features import slice_reps

SIDE = ("data/processed/squat_side_features.csv", "data/processed/squat_side_landmarks_smoothed.csv")
FRONT = ("data/processed/squat_front_features.csv", "data/processed/squat_front_landmarks_smoothed.csv")


@pytest.fixture(scope="module")
def side_ref():
    require_reference(*SIDE)
    return slice_reps(*SIDE)[0][0]


@pytest.fixture(scope="module")
def front_ref():
    require_reference(*FRONT)
    return slice_reps(*FRONT)[0][0]


def test_identical_rep_has_metrics_within_tolerance(side_ref):
    faults, meta = judge_rep(side_ref, copy.deepcopy(side_ref))
    assert faults == []
    expected = {f for f in SQUAT_FAULT_RULES if f in side_ref['features']}
    assert set(meta['metrics']) == expected
    for m in meta['metrics'].values():
        assert m['ratio'] == pytest.approx(0.0)


def test_high_bad_injection_is_measured_and_faulted(side_ref):
    bad = copy.deepcopy(side_ref)
    b = bad['bottom_rel']
    bad['features']['trunk'] = bad['features']['trunk'].copy()
    bad['features']['trunk'][b:] += 20.0
    faults, meta = judge_rep(side_ref, bad)
    m = meta['metrics']['trunk']
    assert m['dev'] == pytest.approx(20.0, abs=1e-6)
    assert m['ratio'] == pytest.approx(20.0 / 12.0, abs=1e-6)
    assert 'trunk' in {f['feature'] for f in faults}


def test_low_bad_injection_uses_negative_direction(front_ref):
    bad = copy.deepcopy(front_ref)
    b = bad['bottom_rel']
    bad['features']['valgus'] = bad['features']['valgus'].copy()
    bad['features']['valgus'][b:] -= 0.5
    faults, meta = judge_rep(front_ref, bad)
    m = meta['metrics']['valgus']
    assert m['dev'] == pytest.approx(-0.5, abs=1e-6)
    assert m['ratio'] > 1
    assert 'valgus' in {f['feature'] for f in faults}
