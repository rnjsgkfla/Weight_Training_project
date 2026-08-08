"""
features.py — 스쿼트 특징 추출: 측면 각도 + 정면 비율

뷰별로 뽑는 것이 다르다 (각 뷰는 자기가 바라보는 평면만 정확하므로):
  측면(sagittal) : 깊이·기울기 → 각도 위주, visibility 높은 카메라쪽 다리 1개
  정면(frontal)  : 좌우 정렬·대칭 → 거리 비율 위주, 양쪽 다리 모두

입력: data/processed/squat_{front,side}_landmarks_normalized.csv
  - 각도는 불변량이라 정규화 여부 무관하지만, 위치·비율 특징을 상체길이=1 단위로
    맞추기 위해 정규화본을 사용한다.

각도 계산은 angles.py 엔진을 재사용한다.
"""

import numpy as np
import csv
from smooth_landmarks import load_landmarks
from normalize_landmarks import _xyz
from angles import (joint_angle, angle_to_vertical, select_side, compute_angles,
                    LEFT, RIGHT, SQUAT_SIDE_ANGLES)


def _pt(x, y, i):
    """관절 i 의 (N,2) 좌표."""
    return np.stack([x[:, i], y[:, i]], axis=1)


# ── 측면: 각도 4종 + 위치 특징 2종 ─────────────────────────────────────────────
def extract_side_features(csv_path):
    """측면 영상에서 프레임별 특징 시계열을 뽑는다. 카메라쪽 다리 자동 선택."""
    _, data = load_landmarks(csv_path)
    x, y, z, v = _xyz(data)
    side = select_side(v)

    # 각도 4종: knee, hip, trunk, shin (angles.py 엔진)
    feats = dict(compute_angles(x, y, SQUAT_SIDE_ANGLES, side))

    hip_i, knee_i, foot_i = side['hip'], side['knee'], side['foot']

    # 엉덩이 깊이: knee.y − hip.y (y는 아래로 +).
    #   서있음 ~+1(무릎이 골반보다 아래) → 평행 ~0 → 아래로 앉을수록 음수(골반이 무릎보다 아래)
    feats['hip_depth'] = y[:, knee_i] - y[:, hip_i]

    # 무릎 전방 이동: knee.x − foot.x (측면은 발끝이 +x). >0 이면 무릎이 발끝보다 앞.
    feats['knee_travel'] = x[:, knee_i] - x[:, foot_i]

    return feats, ('LEFT' if side is LEFT else 'RIGHT')


# ── 정면: 거리 비율 + 좌우 대칭 (양쪽 다리) ────────────────────────────────────
def extract_front_features(csv_path):
    """정면 영상에서 프레임별 비율·대칭 특징 시계열을 뽑는다."""
    _, data = load_landmarks(csv_path)
    x, y, z, v = _xyz(data)

    def xdist(i, j):
        return np.abs(x[:, i] - x[:, j])  # 가로(관상면) 간격

    knee_w  = xdist(LEFT['knee'],     RIGHT['knee'])
    ankle_w = xdist(LEFT['ankle'],    RIGHT['ankle'])
    sh_w    = xdist(LEFT['shoulder'], RIGHT['shoulder'])

    feats = {}
    # 무릎 모임(valgus): 무릎간격 / 발목간격. <1 이면 무릎이 발목보다 좁음(안쪽 모임).
    feats['valgus'] = knee_w / (ankle_w + 1e-9)
    # 스탠스 너비: 발목간격 / 어깨너비.
    feats['stance'] = ankle_w / (sh_w + 1e-9)

    # 좌우 대칭: 좌·우 무릎 각도 차, 좌·우 골반 높이 차 (0에 가까울수록 대칭)
    knee_L = joint_angle(_pt(x, y, LEFT['hip']),  _pt(x, y, LEFT['knee']),  _pt(x, y, LEFT['ankle']))
    knee_R = joint_angle(_pt(x, y, RIGHT['hip']), _pt(x, y, RIGHT['knee']), _pt(x, y, RIGHT['ankle']))
    feats['sym_knee'] = np.abs(knee_L - knee_R)
    feats['sym_hip']  = np.abs(y[:, LEFT['hip']] - y[:, RIGHT['hip']])

    return feats


# ── 정면: 사이드레터럴레이즈 (좌우 개별 각도 + 좌우 높이차) ────────────────────
def extract_front_lateral_raise_features(csv_path):
    """정면 사이드레터럴레이즈 특징을 뽑는다. 정면이라 양팔 모두 그대로 쓴다
    (측면처럼 카메라쪽 한쪽을 고를 필요가 없음 — 양팔이 항상 카메라를 향함).

    좌우를 평균으로 뭉개지 않고 따로 남겨(arm_L/R, elbow_L/R) 어느 쪽이 문제인지
    특정할 수 있게 하고, 대칭은 각도 차 대신 실제 높이차(손목·어깨 y)로 직접 잰다.
    """
    _, data = load_landmarks(csv_path)
    x, y, z, v = _xyz(data)

    def pt(i):
        return np.stack([x[:, i], y[:, i]], axis=1)

    feats = {}

    # 좌우 어깨 외전각(거상각): 어깨→팔꿈치 분절이 수직축과 이루는 각.
    # 0=팔을 내림, ~90=수평(목표 상단 자세)
    feats['arm_L'] = angle_to_vertical(pt(LEFT['shoulder']), pt(LEFT['elbow']))
    feats['arm_R'] = angle_to_vertical(pt(RIGHT['shoulder']), pt(RIGHT['elbow']))

    # 좌우 팔꿈치 각도: 어깨-팔꿈치-손목. 살짝 굽힌 상태를 일정하게 유지해야 함.
    feats['elbow_L'] = joint_angle(pt(LEFT['shoulder']), pt(LEFT['elbow']), pt(LEFT['wrist']))
    feats['elbow_R'] = joint_angle(pt(RIGHT['shoulder']), pt(RIGHT['elbow']), pt(RIGHT['wrist']))

    # 몸통 기울기: 골반중심→어깨중심 분절이 수직축과 이루는 각(정면이므로 좌우 기울임을 측정).
    # 반동을 쓰려고 몸을 옆으로 기울이면 커진다.
    hip_center  = (pt(LEFT['hip']) + pt(RIGHT['hip'])) / 2
    sh_center   = (pt(LEFT['shoulder']) + pt(RIGHT['shoulder'])) / 2
    feats['trunk'] = angle_to_vertical(hip_center, sh_center)

    # 좌우 손목 높이(원점=골반, 아래로 갈수록 y 가 커짐 → 작을수록 높이 든 것).
    # 좌우를 서로 비교(차이)하지 않고 각각 기준 영상의 같은 순간(DTW 정렬) 손목 높이와
    # 직접 비교한다 — "반대쪽보다 낮다/높다"가 아니라 "그 손목이 기준보다 낮다/높다"를
    # 바로 판정할 수 있어, 한쪽만 기준보다 과도하게 높이 든 경우도 곧바로 잡힌다.
    feats['wrist_L'] = y[:, LEFT['wrist']]
    feats['wrist_R'] = y[:, RIGHT['wrist']]

    # 좌우 어깨 높이차(부호 있음, 위와 동일 규약): 한쪽 어깨만 으쓱 올라가거나 몸이
    # 한쪽으로 기운 경우 감지.
    feats['shoulder_height_diff'] = y[:, LEFT['shoulder']] - y[:, RIGHT['shoulder']]

    return feats


# ── 운동·뷰 선택 디스패처 ──────────────────────────────────────────────────────
def extract_features(exercise, view, csv_path):
    """운동과 뷰를 고르면 해당 특징 시계열(dict)을 반환한다.

    - 스쿼트는 뷰별 전용 추출기(각도+위치, 비율)를 사용.
    - 사이드레터럴레이즈는 정면 전용 추출기를 사용 (측면은 미지원).
    - 그 외 운동(팔굽혀펴기 등)은 아직 뷰 전용 로직이 없으므로
      angles 엔진으로 그 운동의 '각도'만 계산해 돌려준다. (비율·위치 특징은
      해당 운동을 구현할 때 여기에 뷰 전용 추출기를 추가하면 된다.)
    """
    if exercise == 'squat':
        if view == 'side':
            feats, _leg = extract_side_features(csv_path)
            return feats
        if view == 'front':
            return extract_front_features(csv_path)
        raise ValueError(f"스쿼트에 없는 뷰: {view}")

    if exercise == 'lateral_raise':
        if view == 'front':
            return extract_front_lateral_raise_features(csv_path)
        raise ValueError("사이드레터럴레이즈는 정면 영상만 지원합니다")

    # 각도만 필요한 운동은 angles 엔진으로 바로 (카메라쪽 자동 선택)
    from angles import angles_from_csv, exercise_angle_defs
    feats, _side = angles_from_csv(csv_path, exercise_angle_defs(exercise))
    return feats


# ── 특징 CSV 저장 ──────────────────────────────────────────────────────────────
def save_features(out_csv, frames, feats):
    """특징 시계열(dict)을 frame_number 와 함께 CSV 로 저장한다.

    컬럼: frame_number, <특징1>, <특징2>, ...  (특징마다 프레임당 값 1개)
    """
    names = list(feats)
    with open(out_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frame_number'] + names)
        for i, fr in enumerate(frames):
            writer.writerow([fr] + [feats[n][i] for n in names])


def load_features(csv_path):
    """save_features 로 저장한 특징 CSV 를 (frames, {이름: 배열}) 로 읽는다."""
    with open(csv_path, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    names = header[1:]
    frames = np.array([int(r[0]) for r in rows])
    feats = {n: np.array([float(r[1 + i]) for r in rows]) for i, n in enumerate(names)}
    return frames, feats


def extract_and_save(exercise, view, input_csv, output_csv):
    """운동·뷰의 특징을 계산해 CSV 로 저장한다. 저장한 특징 dict 를 반환."""
    feats = extract_features(exercise, view, input_csv)
    frames, _ = load_landmarks(input_csv)
    save_features(output_csv, frames, feats)
    print(f"특징 저장 [{exercise}/{view}] {list(feats)} → {output_csv}")
    return feats


# ── 실행: 정면/측면 특징 추출 → CSV 저장 (+ 검증용 요약) ───────────────────────
if __name__ == "__main__":
    side_feats = extract_and_save(
        'squat', 'side',
        "data/processed/squat_side_landmarks_normalized.csv",
        "data/processed/squat_side_features.csv")
    b = int(np.argmin(side_feats['knee']))  # 무릎 각도 최소 = 최저점
    print(f"[측면] 최저점 frame={b}")
    for name, s in side_feats.items():
        unit = 'deg' if name in ('knee', 'hip', 'trunk', 'shin') else '   '
        print(f"  {name:11s}: 서있음 {s[0]:7.2f}{unit}  →  최저점 {s[b]:7.2f}{unit}")

    front_feats = extract_and_save(
        'squat', 'front',
        "data/processed/squat_front_landmarks_normalized.csv",
        "data/processed/squat_front_features.csv")
    # 정면 최저점: 좌우 무릎각 평균 최소 지점 근사
    _, fdata = load_landmarks("data/processed/squat_front_landmarks_normalized.csv")
    fx, fy, _, _ = _xyz(fdata)
    kL = joint_angle(_pt(fx, fy, LEFT['hip']),  _pt(fx, fy, LEFT['knee']),  _pt(fx, fy, LEFT['ankle']))
    kR = joint_angle(_pt(fx, fy, RIGHT['hip']), _pt(fx, fy, RIGHT['knee']), _pt(fx, fy, RIGHT['ankle']))
    fb = int(np.argmin((kL + kR) / 2))
    print(f"[정면] 최저점 frame={fb}")
    for name, s in front_feats.items():
        print(f"  {name:9s}: 서있음 {s[0]:7.3f}  →  최저점 {s[fb]:7.3f}")

    lr_feats = extract_and_save(
        'lateral_raise', 'front',
        "data/processed/sidelateralraise_front_landmarks_normalized.csv",
        "data/processed/sidelateralraise_front_features.csv")
    peak = int(np.argmax((lr_feats['arm_L'] + lr_feats['arm_R']) / 2))
    print(f"[사이드레터럴레이즈/정면] 최고점 frame={peak}")
    for name, s in lr_feats.items():
        print(f"  {name:14s}: 시작 {s[0]:7.2f}  →  최고점 {s[peak]:7.2f}")
