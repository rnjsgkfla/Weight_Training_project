"""
scoring.py — DTW 정렬 결과로 운동 자세 점수(0~100)를 계산한다.

계산 순서 (모든 운동 공통):
  1. DTW 대응쌍마다 특징별 절대 오차   d_{i,t} = |expert_{i,t} − user_{i,t}|
  2. 특징별 전체 평균 오차              D_i = (1/T) Σ_t d_{i,t}
     (여러 회차면 모든 회차의 대응쌍을 합쳐 한 번에 평균낸다)
  3. 허용 오차로 정규화                 e_i = min(D_i / T_i, 1)
     (좌우 특징은 좌우 평균 오차를 먼저 구한 뒤 정규화)
  4. 가중합                             E = Σ w_i e_i
  5. 점수                               Score = clamp(100 (1 − E), 0, 100)

'프레임별 종합 점수 → 평균' 방식은 쓰지 않는다. 특징별 평균 오차를 먼저 구한다.

입력 aligned: [(expert_rep, user_rep, path), ...]
  expert_rep / user_rep : rep_features.slice_reps 의 반복 dict ('features' 에 특징 시계열)
  path                  : dtw.align_reps 의 정렬 경로 [(expert_idx, user_idx), ...]

점수 항목은 스쿼트·런지는 측면, 사이드 레터럴 레이즈는 정면 영상에서 계산한다 (SCORE_VIEW).
"""

import numpy as np

# 운동별 점수 계산에 쓰는 영상 방향
SCORE_VIEW = {'squat': 'side', 'lunge': 'side', 'lateral_raise': 'front'}

# 점수 항목 → 사용할 특징 이름 (여러 개면 좌우 평균 오차)
SCORE_ITEM_FEATURES = {
    'squat': {
        'knee':   ['knee'],          # 무릎 각도 (골반–무릎–발목)
        'pelvis': ['hip_depth'],     # 골반 높이 (무릎 높이 − 골반 높이)
        'torso':  ['trunk'],         # 상체 기울기
    },
    'lunge': {
        'front_knee': ['knee'],      # 앞쪽 무릎 각도
        'rear_knee':  ['back_knee'], # 뒤쪽 무릎 각도
        'pelvis':     ['hip_depth'], # 골반 높이 (앞무릎 높이 − 골반 중심 높이)
        'torso':      ['trunk'],     # 상체 기울기
    },
    'lateral_raise': {
        'shoulder': ['shoulder_L', 'shoulder_R'],  # 어깨 각도 (골반–어깨–팔꿈치)
        'elbow':    ['elbow_L', 'elbow_R'],        # 팔꿈치 각도
        'wrist':    ['wrist_L', 'wrist_R'],        # 손목 높이
        'torso':    ['trunk'],                     # 상체 기울기
    },
}

# 운동별 가중치 (합 1.00)
SCORE_WEIGHTS = {
    'squat':         {'knee': 0.40, 'pelvis': 0.35, 'torso': 0.25},
    'lunge':         {'front_knee': 0.35, 'rear_knee': 0.20, 'pelvis': 0.25, 'torso': 0.20},
    'lateral_raise': {'shoulder': 0.35, 'elbow': 0.20, 'wrist': 0.30, 'torso': 0.15},
}

# 운동별 허용 오차 T_i (각도: °, 위치: 상체 길이=1 단위). 평균 오차가 이만큼이면 그 항목은 0점.
# 지금은 judge.py 결함 판정 허용오차와 같은 값으로 시작한다 (라벨 데이터로 보정 예정).
SCORE_TOLERANCES = {
    'squat':         {'knee': 15.0, 'pelvis': 0.15, 'torso': 12.0},
    'lunge':         {'front_knee': 25.0, 'rear_knee': 20.0, 'pelvis': 0.45, 'torso': 12.0},
    'lateral_raise': {'shoulder': 15.0, 'elbow': 15.0, 'wrist': 0.15, 'torso': 10.0},
}

# 각도 항목의 단위 (그 외 위치 항목은 상체 길이=1 단위라 단위 표기 없음)
ANGLE_ITEMS = {'knee', 'front_knee', 'rear_knee', 'torso', 'shoulder', 'elbow'}

# 화면 표시용 항목 이름
SCORE_ITEM_KR = {
    'knee': '무릎 각도', 'front_knee': '앞쪽 무릎 각도', 'rear_knee': '뒤쪽 무릎 각도',
    'pelvis': '골반 높이', 'torso': '상체 기울기',
    'shoulder': '어깨 각도', 'elbow': '팔꿈치 각도', 'wrist': '손목 높이',
}


# ── 공통 계산 ──────────────────────────────────────────────────────────────────
def mean_abs_error(aligned, feature):
    """특징 하나의 DTW 전체 평균 절대 오차 D = (1/T) Σ |expert − user|.

    모든 회차의 대응쌍을 합쳐 평균낸다(회차별 평균을 다시 평균내지 않음).
    """
    abs_errors = []
    for expert_rep, user_rep, path in aligned:
        expert_values = expert_rep['features'][feature]
        user_values = user_rep['features'][feature]
        abs_errors.extend(abs(expert_values[i] - user_values[j]) for i, j in path)
    return float(np.mean(abs_errors))


def normalized_error(mean_error, tolerance):
    """e = min(D / T, 1)  — 0(모범과 같음) ~ 1(허용 오차 이상)."""
    return min(mean_error / tolerance, 1.0)


def weighted_score(aligned, item_features, weights, tolerances):
    """항목별 평균 오차 → 정규화 → 가중합 → 0~100 점수.

    Returns:
        {'score': 0~100 실수, 'combined_error': E,
         'items': [{item, name, weight, tolerance, mean_error, normalized_error}, ...]}
    """
    items = []
    combined_error = 0.0
    for item, features in item_features.items():
        # 좌우 특징은 좌우 평균 오차를 먼저 구한 뒤 정규화한다
        mean_error = float(np.mean([mean_abs_error(aligned, f) for f in features]))
        e = normalized_error(mean_error, tolerances[item])
        combined_error += weights[item] * e
        items.append({'item': item, 'name': SCORE_ITEM_KR[item], 'weight': weights[item],
                      'unit': '°' if item in ANGLE_ITEMS else '',
                      'tolerance': tolerances[item], 'mean_error': round(mean_error, 4),
                      'normalized_error': round(e, 4)})
    score = min(max(100.0 * (1.0 - combined_error), 0.0), 100.0)
    return {'score': score, 'combined_error': round(combined_error, 4), 'items': items}


# ── 운동별 점수 ────────────────────────────────────────────────────────────────
def score_squat(aligned):
    """E = 0.40 e_knee + 0.35 e_pelvis + 0.25 e_torso"""
    return weighted_score(aligned, SCORE_ITEM_FEATURES['squat'],
                          SCORE_WEIGHTS['squat'], SCORE_TOLERANCES['squat'])


def score_lunge(aligned):
    """E = 0.35 e_frontKnee + 0.20 e_rearKnee + 0.25 e_pelvis + 0.20 e_torso"""
    return weighted_score(aligned, SCORE_ITEM_FEATURES['lunge'],
                          SCORE_WEIGHTS['lunge'], SCORE_TOLERANCES['lunge'])


def score_lateral_raise(aligned):
    """E = 0.35 e_shoulder + 0.20 e_elbow + 0.30 e_wrist + 0.15 e_torso (좌우는 평균 오차 후 정규화)"""
    return weighted_score(aligned, SCORE_ITEM_FEATURES['lateral_raise'],
                          SCORE_WEIGHTS['lateral_raise'], SCORE_TOLERANCES['lateral_raise'])


SCORE_FUNCTIONS = {'squat': score_squat, 'lunge': score_lunge, 'lateral_raise': score_lateral_raise}
