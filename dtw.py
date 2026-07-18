"""
dtw.py — 파이프라인 7단계: 반복별 DTW 시간 정렬

역할:
  기준(템플릿) 반복과 사용자 반복을 시간축으로 정렬한다. 스쿼트 속도·프레임 수가
  달라도 같은 국면(하강·최저·상승)끼리 대응시켜, 이후 국면별 자세 비교를 가능케 한다.

방식:
  - 정렬 기준 신호 = '무릎 각도'(국면을 가장 잘 나타내는 1D 신호). 이 신호로 정렬 경로를
    구한 뒤, 같은 경로를 모든 특징(각도·비율·위치)에 적용해 국면별로 비교한다.
  - DTW 는 순수 numpy 로 구현(외부 라이브러리 불필요). 정렬 경로(warping path)를 반환한다.

DTW 개념:
  두 시계열 a, b 의 모든 (i, j) 쌍에 대해 국소 비용을 쌓아 최소 누적비용 경로를 찾는다.
  경로는 (i, j) 쌍들의 나열로, "기준의 i 프레임 ↔ 사용자의 j 프레임"이 대응됨을 뜻한다.
"""

import numpy as np


def dtw(a, b):
    """두 시계열을 DTW 로 정렬한다.

    Args:
        a, b : (n,) 또는 (n, F) 배열. 1D면 절대차, 다차원이면 유클리드 거리를 국소 비용으로.

    Returns:
        path     : [(i, j), ...] 정렬 경로 (i=a 인덱스, j=b 인덱스, 오름차순)
        distance : 경로를 따른 총 누적 비용
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n, m = len(a), len(b)

    # 국소 비용 계산 (1D: |a-b|, 다차원: L2 노름)
    def cost(i, j):
        d = a[i] - b[j]
        return abs(d) if a.ndim == 1 else float(np.linalg.norm(d))

    # 누적 비용 행렬 (1-based 패딩, 가장자리는 무한대)
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = cost(i - 1, j - 1) + min(D[i - 1, j],      # a 진행(삽입)
                                               D[i, j - 1],      # b 진행(삭제)
                                               D[i - 1, j - 1])  # 동시 진행(대각)

    # 역추적으로 경로 복원
    path = []
    i, j = n, m
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        step = np.argmin([D[i - 1, j - 1], D[i - 1, j], D[i, j - 1]])
        if step == 0:
            i, j = i - 1, j - 1
        elif step == 1:
            i -= 1
        else:
            j -= 1
    path.reverse()
    return path, float(D[n, m])


def warp_index(path, i_ref):
    """정렬 경로에서 기준 인덱스 i_ref 에 대응하는 사용자 인덱스를 반환한다.

    한 기준 프레임이 여러 사용자 프레임에 대응할 수 있어(정지 구간 등), 대응된
    사용자 인덱스들의 중앙값(정수)을 대표값으로 돌려준다.
    """
    js = [j for (i, j) in path if i == i_ref]
    if not js:
        return None
    return int(np.median(js))


def _minmax(a):
    """시계열을 [0,1] 로 min-max 정규화한다(모양만 남기고 크기 차이는 제거)."""
    a = np.asarray(a, dtype=float)
    lo, hi = a.min(), a.max()
    return (a - lo) / (hi - lo + 1e-9)


def align_reps(ref_rep, user_rep):
    """기준 반복과 사용자 반복을 무릎 각도의 '모양'으로 위상 정렬한다.

    정렬 신호를 rep 마다 min-max 정규화한 뒤 DTW 를 수행한다. 이렇게 하면 사용자가
    얕게 앉아 각도 범위가 달라도(예: 40°까지 vs 95°까지) 깊이 차이가 정렬을 왜곡하지
    않고, 하강·최저·상승 위상끼리 비례 정렬된다. 깊이 차이 자체는 특징값으로 별도 판정.

    Returns:
        path        : 정렬 경로 (원본 배열 인덱스 기준 — 특징 비교에 그대로 사용)
        distance    : 정규화 신호 기준 총 DTW 거리(위상 정렬 품질 지표)
        norm_dist   : 경로 길이로 나눈 평균 비용(길이 무관 비교용)
        user_bottom : 기준의 최저점에 대응하는 사용자 최저점 인덱스(경로 기반)
    """
    ref_sig  = _minmax(ref_rep['align_signal'])
    user_sig = _minmax(user_rep['align_signal'])
    path, distance = dtw(ref_sig, user_sig)
    norm_dist = distance / len(path)
    user_bottom = warp_index(path, ref_rep['bottom_rel'])
    return path, distance, norm_dist, user_bottom


# ── 실행: 검증 (자기정렬 + 인위적 워핑 사용자) ────────────────────────────────
if __name__ == "__main__":
    from rep_features import slice_reps

    ref_reps, leg = slice_reps("data/processed/squat_side_features.csv",
                               "data/processed/squat_side_landmarks_smoothed.csv")
    ref = ref_reps[0]
    print(f"기준 측면 rep: 길이 {ref['length']}, 최저 로컬idx {ref['bottom_rel']}")

    # 1) 자기 자신과 정렬 → 대각선 경로, 거리 ~0, 최저→최저
    path, dist, nd, ub = align_reps(ref, ref)
    print(f"\n[자기정렬] 거리={dist:.4f}, 평균비용={nd:.4f}, "
          f"기준최저 {ref['bottom_rel']} → 사용자최저 {ub} (같아야 정상)")

    # 2) 인위적 '느린 사용자' 만들기: 무릎각 신호를 1.4배 길이로 늘리고 잡음 추가
    sig = ref['align_signal']
    n_new = int(len(sig) * 1.4)
    xp = np.linspace(0, 1, len(sig))
    xnew = np.linspace(0, 1, n_new)
    slow = np.interp(xnew, xp, sig) + np.random.default_rng(0).normal(0, 1.5, n_new)
    fake_user = {'align_signal': slow, 'bottom_rel': int(np.argmin(slow))}
    path, dist, nd, ub = align_reps(ref, fake_user)
    expected = int(ref['bottom_rel'] * n_new / len(sig))
    print(f"\n[느린 사용자] 원본 {len(sig)}프레임 → 사용자 {n_new}프레임")
    print(f"  DTW 정렬 후: 기준최저 {ref['bottom_rel']} → 사용자최저(경로) {ub}, "
          f"사용자 실제최저 {fake_user['bottom_rel']}, 산술기대 {expected}")
    print(f"  평균비용={nd:.3f}  (작을수록 유사)")
