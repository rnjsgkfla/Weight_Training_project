"""
rep_segmentation.py — 파이프라인 5단계: 반복(rep) 분할

역할:
  운동 반복 횟수를 세고, 각 반복의 (시작 · 최저점 · 종료) 프레임 구간을 확정한다.
  이후 이 구간으로 비교 특징 시계열을 잘라 반복별 DTW·판정에 사용한다.

설계:
  - 입력은 '정규화 전' smoothed CSV. (정규화하면 골반이 원점이라 '골반 깊이' 같은
    위치 신호가 안 움직이므로, 반복 탐지는 정규화 전 데이터로 한다.)
  - 반복 신호로는 '무릎 각도'를 쓴다. 크기·위치·해상도에 무관하고, 스쿼트 1회마다
    각도가 크게 떨어졌다(앉음) 올라오는(섬) 골짜기 1개가 생겨 세기 쉽다.
  - 히스테리시스 상태기계: 각도가 T_down 아래로 내려갔다가 T_up 위로 복귀하면 1회.
    임계값 2개를 써서 골짜기 근처 잔떨림에 중복으로 세는 것을 막는다.
  - 임계값은 각 영상의 최소·최대 사이 비율로 잡아 사람·카메라와 무관하게 동작한다.

무릎 각도 계산은 angles.py 엔진을 재사용한다.
"""

import numpy as np
from angles import angles_from_csv, ANGLE_LIBRARY, LEFT
from smooth_landmarks import load_landmarks
from normalize_landmarks import _xyz

L_HIP, R_HIP = 23, 24


def rep_signal(csv_path):
    """반복 탐지용 신호를 반환한다.

    Returns:
        frames : frame_number 배열
        knee   : 카메라쪽 무릎 각도(도). rep '세기'(사이클 경계)용.
        hip_y  : 원본 이미지 좌표의 골반 중심 y. 클수록 화면 아래(=깊음).
                 각 rep 안에서 '실제 최저점'을 잡는 보조 신호.
                 (정규화하면 골반이 원점이라 못 쓰므로 정규화 전 좌표를 쓴다.)
        leg    : 선택된 카메라쪽 다리
    """
    angles, side = angles_from_csv(csv_path, {'knee': ANGLE_LIBRARY['knee']})
    frames, data = load_landmarks(csv_path)
    x, y, z, v = _xyz(data)
    hip_y = (y[:, L_HIP] + y[:, R_HIP]) / 2
    leg = 'LEFT' if side is LEFT else 'RIGHT'
    return frames, angles['knee'], hip_y, leg


def detect_reps(angle, low_frac=0.35, high_frac=0.65, min_rep_frames=10):
    """무릎 각도 시계열에서 반복 구간을 히스테리시스로 검출한다.

    Args:
        angle          : (N,) 무릎 각도 시계열(도). 서있음=큼, 앉음=작음.
        low_frac       : T_down 임계 비율. 각도가 (min + low_frac*범위) 아래로
                         내려가야 '앉음'으로 인정 → 얕은 흔들림 무시.
        high_frac      : T_up 임계 비율. (min + high_frac*범위) 위로 올라와야
                         '섬'으로 인정 → 반복 종료.
        min_rep_frames : 시작~종료가 이 프레임 수 미만이면 노이즈로 보고 버린다.

    Returns:
        reps  : [{'start': i, 'bottom': i, 'end': i}, ...]  (모두 0-based 배열 인덱스)
        info  : {'T_down', 'T_up', 'min', 'max'} (임계값 등, 시각화·디버그용)
    """
    a = np.asarray(angle, dtype=float)
    lo, hi = np.nanmin(a), np.nanmax(a)
    rng = hi - lo
    T_down = lo + low_frac * rng
    T_up   = lo + high_frac * rng

    reps = []
    state = 'up'        # 'up'(서있음) 또는 'down'(앉는 중)
    top_frame = 0       # 최근에 '섬(T_up 이상)'으로 확인된 프레임 → 하강 시작점 후보
    descent_start = 0

    for i, v in enumerate(a):
        if np.isnan(v):
            continue
        if state == 'up':
            if v >= T_up:
                top_frame = i           # 서있는 동안 계속 갱신 → 마지막 '섬' 지점 기억
            elif v < T_down:
                state = 'down'
                descent_start = top_frame  # 하강 시작 = 직전 마지막으로 서있던 지점
        else:  # 'down'
            if v >= T_up:
                # 각도가 다시 올라옴 → 반복 완료. 무릎 기준 최저(교차검증용)만 여기서 기록.
                knee_bottom = descent_start + int(np.argmin(a[descent_start:i + 1]))
                if (i - descent_start) >= min_rep_frames:
                    reps.append({'start': descent_start, 'knee_bottom': knee_bottom, 'end': i})
                state = 'up'
                top_frame = i

    info = {'T_down': T_down, 'T_up': T_up, 'min': lo, 'max': hi}
    return reps, info


def segment(csv_path, **kwargs):
    """CSV 하나에서 반복 구간을 검출해 frame_number 로 매핑한 결과를 반환한다.

    무릎 각도로 사이클(시작·종료)을 잡고, 각 rep 안에서 '실제 최저점(bottom)'은
    원본 고관절 y 가 가장 낮은(=가장 아래) 지점으로 정한다. 무릎 기준 최저
    (knee_bottom)와의 프레임 차이(bottom_offset)는 교차검증 지표로 함께 남긴다.
    """
    frames, angle, hip_y, leg = rep_signal(csv_path)
    reps, info = detect_reps(angle, **kwargs)
    for r in reps:
        s, e = r['start'], r['end']
        # 실제 최저점 = rep 구간 내 고관절 y 최대(화면상 가장 아래)
        r['bottom'] = s + int(np.argmax(hip_y[s:e + 1]))
        r['bottom_offset'] = r['bottom'] - r['knee_bottom']  # 고관절-무릎 최저 프레임 차이
        # 배열 인덱스 → 실제 frame_number
        r['start_f']       = int(frames[r['start']])
        r['bottom_f']      = int(frames[r['bottom']])
        r['knee_bottom_f'] = int(frames[r['knee_bottom']])
        r['end_f']         = int(frames[r['end']])
    return reps, info, angle, leg


# ── 실행: 정면/측면 반복 분할 (검증용) ─────────────────────────────────────────
if __name__ == "__main__":
    for tag in ['side', 'front']:
        csv = f"data/processed/squat_{tag}_landmarks_smoothed.csv"
        reps, info, angle, leg = segment(csv)
        print(f"[{tag}] 카메라쪽 다리={leg} | 무릎각 {info['min']:.0f}~{info['max']:.0f}° "
              f"| 임계 T_down={info['T_down']:.0f}° T_up={info['T_up']:.0f}° "
              f"| 검출된 반복 {len(reps)}회")
        for k, r in enumerate(reps, 1):
            print(f"   {k}회차: 시작 f{r['start_f']} → 최저(고관절) f{r['bottom_f']} "
                  f"→ 종료 f{r['end_f']}  "
                  f"[교차검증: 무릎최저 f{r['knee_bottom_f']}, 차이 {r['bottom_offset']:+d}프레임]")
