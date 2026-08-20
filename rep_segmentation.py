"""
rep_segmentation.py — 파이프라인 5단계: 반복(rep) 분할

역할:
  운동 반복 횟수를 세고, 각 반복의 (시작 · 극점(bottom) · 종료) 프레임 구간을 확정한다.
  이후 이 구간으로 비교 특징 시계열을 잘라 반복별 DTW·판정에 사용한다.
  '극점'은 운동마다 의미가 다르다 — 스쿼트는 가장 깊이 앉은 지점, 사이드레터럴레이즈는
  팔을 가장 높이 든 지점. 이 모듈은 그 차이를 REP_SIGNAL_CONFIG 로 흡수해 운동 공용으로 쓴다.

설계:
  - 입력은 '정규화 전' smoothed CSV. (정규화하면 골반이 원점이라 '골반 깊이' 같은
    위치 신호가 안 움직이므로, 반복 탐지는 정규화 전 데이터로 한다.)
  - 반복 신호(1차 신호)로는 운동을 가장 잘 대표하는 각도 1개를 쓴다
    (스쿼트=무릎 각도, 사이드레터럴레이즈=양팔 평균 거상각). 크기·위치·해상도에
    무관하고, 반복 1회마다 골짜기(또는 봉우리) 1개가 생겨 세기 쉽다.
  - 히스테리시스 상태기계: 신호가 T_down 아래로 내려갔다가 T_up 위로 복귀하면 1회.
    임계값 2개를 써서 골짜기 근처 잔떨림에 중복으로 세는 것을 막는다.
    (극점이 '큰 값'인 운동은 신호를 내부적으로 부호 반전해 같은 상태기계를 재사용한다.)
  - 임계값은 각 영상의 최소·최대 사이 비율로 잡아 사람·카메라와 무관하게 동작한다.
  - rep 안에서 '실제 극점'은 보조 위치 신호(스쿼트=고관절 y 최대, 사이드레터럴레이즈=
    손목 y 최소)로 정하고, 1차 신호 기준 극점과의 차이를 교차검증 지표로 남긴다.

각도 계산은 angles.py 엔진을 재사용한다.
"""

import numpy as np
from angles import angles_from_csv, ANGLE_LIBRARY, LEFT, RIGHT, angle_to_vertical
from smooth_landmarks import load_landmarks
from normalize_landmarks import _xyz

L_HIP, R_HIP = 23, 24

# 운동별 반복 신호 설정
#   invert         : 1차 신호의 극점이 '큰 값'인 운동이면 True (히스테리시스 재사용을 위해 부호 반전)
#   refine_extreme : 보조 신호에서 실제 극점을 찾을 때 'max'(화면 아래/큰 값) 또는 'min'(화면 위/작은 값)
REP_SIGNAL_CONFIG = {
    'squat':         dict(invert=False, refine_extreme='max'),
    'lateral_raise': dict(invert=True,  refine_extreme='min'),
    'lunge':         dict(invert=True,  refine_extreme='max'),
}


def rep_signal(csv_path, exercise='squat'):
    """반복 탐지용 1차 신호(각도)와 보조 신호(위치)를 반환한다.

    Returns:
        frames  : frame_number 배열
        primary : (N,) 1차 신호(도). 스쿼트=카메라쪽 무릎 각도, 사이드레터럴레이즈=양팔 평균 거상각.
        refine  : (N,) 보조 위치 신호(원본 이미지 좌표계). rep 안에서 '실제 극점'을 잡는 데 쓴다.
                  (정규화하면 골반이 원점이라 못 쓰므로 정규화 전 좌표를 쓴다.)
        leg     : 선택된 카메라쪽 다리 (정면 운동처럼 좌우 선택이 필요 없으면 None)
    """
    frames, data = load_landmarks(csv_path)
    x, y, z, v = _xyz(data)

    if exercise == 'squat':
        angles, side = angles_from_csv(csv_path, {'knee': ANGLE_LIBRARY['knee']})
        primary = angles['knee']
        refine = (y[:, L_HIP] + y[:, R_HIP]) / 2
        leg = 'LEFT' if side is LEFT else 'RIGHT'
    elif exercise == 'lateral_raise':
        def pt(i):
            return np.stack([x[:, i], y[:, i]], axis=1)
        arm_L = angle_to_vertical(pt(LEFT['shoulder']), pt(LEFT['elbow']))
        arm_R = angle_to_vertical(pt(RIGHT['shoulder']), pt(RIGHT['elbow']))
        primary = (arm_L + arm_R) / 2
        refine = (y[:, LEFT['wrist']] + y[:, RIGHT['wrist']]) / 2
        leg = None  # 정면 양팔 운동은 카메라쪽 선택이 필요 없음
    elif exercise == 'lunge':
        # 런지는 rep 마다 앞다리가 바뀔 수 있어(제자리에서 앞/뒤 다리를 교체) '카메라쪽
        # 다리의 무릎 각도' 같은 단일 다리 신호를 1차 신호로 못 쓴다. 대신 골반 y 는
        # 어느 다리가 앞이든 내려앉을수록 항상 아래로(값 증가) 움직이므로 그대로 쓴다.
        # (보조 신호도 같은 골반 y — 이미 위치 신호라 무릎각처럼 별도 교차검증 신호가
        # 필요 없다.)
        pelvis_y = (y[:, L_HIP] + y[:, R_HIP]) / 2
        primary = pelvis_y
        refine = pelvis_y
        leg = None  # 앞다리가 rep 마다 바뀔 수 있어 고정된 '카메라쪽 다리' 개념이 없음
    else:
        raise ValueError(f"rep_signal 미지원 운동: {exercise}")

    return frames, primary, refine, leg


def detect_reps(signal, low_frac=0.35, high_frac=0.65, min_rep_frames=10, invert=False):
    """1차 신호 시계열에서 반복 구간을 히스테리시스로 검출한다.

    Args:
        signal         : (N,) 1차 신호 시계열(도). invert=False 면 '쉬는 자세=큼, 극점=작음'
                         (예: 스쿼트 무릎각). invert=True 면 그 반대(예: 팔 거상각).
        low_frac       : T_down 임계 비율. 신호가 (min + low_frac*범위) 아래로
                         내려가야 '움직임 시작'으로 인정 → 얕은 흔들림 무시.
        high_frac      : T_up 임계 비율. (min + high_frac*범위) 위로 올라와야
                         '쉬는 자세 복귀'로 인정 → 반복 종료.
        min_rep_frames : 시작~종료가 이 프레임 수 미만이면 노이즈로 보고 버린다.
        invert         : True 면 신호 부호를 반전해 계산(극점이 큰 값인 운동용).

    Returns:
        reps  : [{'start': i, 'primary_extreme': i, 'end': i}, ...]  (모두 0-based 배열 인덱스)
        info  : {'T_down', 'T_up', 'min', 'max'} (임계값 등, 시각화·디버그용. 원래 부호 기준)
    """
    a = np.asarray(signal, dtype=float)
    if invert:
        a = -a
    lo, hi = np.nanmin(a), np.nanmax(a)
    rng = hi - lo
    T_down = lo + low_frac * rng
    T_up   = lo + high_frac * rng

    reps = []
    state = 'up'        # 'up'(쉬는 자세) 또는 'down'(움직이는 중)
    top_frame = 0       # 최근에 '쉬는 자세(T_up 이상)'으로 확인된 프레임 → 시작점 후보
    descent_start = 0

    for i, v in enumerate(a):
        if np.isnan(v):
            continue
        if state == 'up':
            if v >= T_up:
                top_frame = i           # 쉬는 동안 계속 갱신 → 마지막 '쉬는' 지점 기억
            elif v < T_down:
                state = 'down'
                descent_start = top_frame  # 시작 = 직전 마지막으로 쉬고 있던 지점
        else:  # 'down'
            if v >= T_up:
                # 신호가 다시 쉬는 자세로 복귀 → 반복 완료. 1차 신호 기준 극점(교차검증용) 기록.
                primary_extreme = descent_start + int(np.argmin(a[descent_start:i + 1]))
                if (i - descent_start) >= min_rep_frames:
                    reps.append({'start': descent_start, 'primary_extreme': primary_extreme, 'end': i})
                state = 'up'
                top_frame = i

    if invert:
        info = {'T_down': -T_up, 'T_up': -T_down, 'min': -hi, 'max': -lo}
    else:
        info = {'T_down': T_down, 'T_up': T_up, 'min': lo, 'max': hi}
    return reps, info


def segment(csv_path, exercise='squat', **kwargs):
    """CSV 하나에서 반복 구간을 검출해 frame_number 로 매핑한 결과를 반환한다.

    1차 신호로 사이클(시작·종료)을 잡고, 각 rep 안에서 '실제 극점(bottom)'은
    운동별 보조 신호(REP_SIGNAL_CONFIG)로 정한다. 1차 신호 기준 극점(primary_extreme)과의
    프레임 차이(bottom_offset)는 교차검증 지표로 함께 남긴다.
    """
    cfg = REP_SIGNAL_CONFIG[exercise]
    frames, primary, refine, leg = rep_signal(csv_path, exercise)
    reps, info = detect_reps(primary, invert=cfg['invert'], **kwargs)
    extreme_func = np.argmax if cfg['refine_extreme'] == 'max' else np.argmin
    for r in reps:
        s, e = r['start'], r['end']
        r['bottom'] = s + int(extreme_func(refine[s:e + 1]))
        r['bottom_offset'] = r['bottom'] - r['primary_extreme']
        # 배열 인덱스 → 실제 frame_number
        r['start_f']            = int(frames[r['start']])
        r['bottom_f']           = int(frames[r['bottom']])
        r['primary_extreme_f']  = int(frames[r['primary_extreme']])
        r['end_f']              = int(frames[r['end']])
    return reps, info, primary, leg


# ── 실행: 정면/측면 반복 분할 (검증용) ─────────────────────────────────────────
if __name__ == "__main__":
    jobs = [
        ('squat', 'side',  "data/processed/squat_side_landmarks_smoothed.csv"),
        ('squat', 'front', "data/processed/squat_front_landmarks_smoothed.csv"),
        ('lateral_raise', 'front', "data/processed/sidelateralraise_front_landmarks_smoothed.csv"),
        ('lunge', 'side',  "data/processed/lunge_side_landmarks_smoothed.csv"),
        ('lunge', 'front', "data/processed/lunge_front_landmarks_smoothed.csv"),
    ]
    for exercise, tag, csv in jobs:
        reps, info, signal, leg = segment(csv, exercise=exercise)
        leg_label = leg if leg else "정면(양팔)/앞다리 자동판별"
        print(f"[{exercise}/{tag}] {leg_label} | 신호범위 {info['min']:.0f}~{info['max']:.0f}° "
              f"| 임계 T_down={info['T_down']:.0f}° T_up={info['T_up']:.0f}° "
              f"| 검출된 반복 {len(reps)}회")
        for k, r in enumerate(reps, 1):
            print(f"   {k}회차: 시작 f{r['start_f']} → 극점 f{r['bottom_f']} "
                  f"→ 종료 f{r['end_f']}  "
                  f"[교차검증: 1차신호극점 f{r['primary_extreme_f']}, 차이 {r['bottom_offset']:+d}프레임]")
