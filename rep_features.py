"""
rep_features.py — 파이프라인 6단계: 반복별 특징 시계열 분할

역할:
  rep_segmentation 이 찾은 (시작·최저·종료) 구간으로 features CSV 를 잘라,
  '반복별 로컬 특징 시계열'을 만든다. 이것이 이후 반복별 DTW 정렬의 입력이 된다.

프레임 정합:
  rep 분할은 정규화 전 smoothed CSV 로, 특징은 정규화 CSV 로 계산했지만
  둘 다 같은 영상의 같은 프레임 수(정규화는 1:1 변환)라 배열 인덱스가 일치한다.
  → smoothed 에서 얻은 (start, bottom, end) 인덱스로 features 를 그대로 슬라이싱한다.
"""

import numpy as np
from rep_segmentation import segment
from features import load_features


def slice_reps(features_csv, smoothed_csv, **rep_kwargs):
    """반복 구간으로 특징 시계열을 잘라 반복별 로컬 시계열을 만든다.

    Args:
        features_csv : save_features 로 저장한 특징 CSV (정규화 기반)
        smoothed_csv : rep 분할용 랜드마크 CSV (정규화 전 smoothed)
        rep_kwargs   : detect_reps 파라미터 (low_frac, high_frac, min_rep_frames)

    Returns:
        reps : 각 원소는 rep_segmentation 결과에 아래가 추가된 dict
               - 'features' : {특징이름: 그 rep 구간의 값 배열}
               - 'bottom_rel': 잘린 구간 내에서의 최저점 인덱스 (0-based)
               - 'length'   : 구간 프레임 수
        leg  : 카메라쪽 다리
    """
    reps, info, angle, leg = segment(smoothed_csv, **rep_kwargs)
    frames, feats = load_features(features_csv)

    # 프레임 수 정합 확인 (rep 분할 신호와 특징이 같은 프레임 수여야 인덱스가 맞다)
    if len(frames) != len(angle):
        raise ValueError(f"프레임 수 불일치: features {len(frames)} vs landmarks {len(angle)} "
                         f"— 같은 영상의 features/smoothed CSV 인지 확인할 것")

    for r in reps:
        s, e = r['start'], r['end']
        r['features']    = {name: feats[name][s:e + 1] for name in feats}
        r['align_signal'] = angle[s:e + 1]   # 무릎 각도 구간 → DTW 정렬 기준(국면 신호)
        r['bottom_rel']  = r['bottom'] - s
        r['length']      = e - s + 1
    return reps, leg


# ── 실행: 정면/측면 반복별 특징 슬라이싱 (검증용) ──────────────────────────────
if __name__ == "__main__":
    jobs = [
        ('side',  "data/processed/squat_side_features.csv",
                  "data/processed/squat_side_landmarks_smoothed.csv"),
        ('front', "data/processed/squat_front_features.csv",
                  "data/processed/squat_front_landmarks_smoothed.csv"),
    ]
    for tag, feat_csv, sm_csv in jobs:
        reps, leg = slice_reps(feat_csv, sm_csv)
        print(f"[{tag}] 카메라쪽={leg} | 반복 {len(reps)}개")
        for k, r in enumerate(reps, 1):
            names = list(r['features'])
            print(f"   {k}회차: 구간 f{r['start_f']}~f{r['end_f']} "
                  f"({r['length']}프레임), 최저 로컬idx {r['bottom_rel']}")
            print(f"      특징 {names}")
            # 최저점에서의 특징값 확인
            bvals = {n: round(float(r['features'][n][r['bottom_rel']]), 2) for n in names}
            print(f"      최저점 값: {bvals}")
