"""
angles.py — 운동 공통 각도 계산 유틸 (스쿼트·팔굽혀펴기·사이드레터럴 등 확장용)

설계 목표:
  '각도 계산기'는 어떤 운동인지 모르게 만들고, 각 운동은 필요한 각도를
  '관절 역할'로 선언(dict)만 하면 되게 한다. 새 운동 추가 = 정의 dict 한 개 추가.

두 가지 각도 원시함수로 모든 관절 각을 커버한다:
  1) joint_angle(A,B,C)      : 세 점 각 (팔꿈치·무릎·고관절·어깨 …)
  2) angle_to_vertical(P,Q)  : 한 분절이 수직축과 이루는 각 (몸통 기울기·정강이·팔 벌림 …)

좌/우는 '역할 이름'(shoulder, elbow, hip …)으로 두고, visibility 로 카메라쪽을
자동 선택한다. → 팔 운동이든 다리 운동이든 동일 엔진으로 처리.

각도는 크기·위치·해상도에 무관하므로 스무딩본/정규화본 어느 쪽으로 계산해도 값이 같다.
"""

import numpy as np
from smooth_landmarks import load_landmarks
from normalize_landmarks import _xyz


# ── 좌/우 관절 역할 → MediaPipe 관절 번호 ──────────────────────────────────────
LEFT  = dict(shoulder=11, elbow=13, wrist=15, hip=23, knee=25, ankle=27, heel=29, foot=31)
RIGHT = dict(shoulder=12, elbow=14, wrist=16, hip=24, knee=26, ankle=28, heel=30, foot=32)


# ── 각도 원시함수 ──────────────────────────────────────────────────────────────
def joint_angle(a, b, c):
    """세 점 각도. b 가 꼭짓점. a,b,c: 각 (N,2) 배열. 반환: (N,) 도(degree)."""
    ba, bc = a - b, c - b
    cos = (ba * bc).sum(1) / (np.linalg.norm(ba, axis=1) * np.linalg.norm(bc, axis=1) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def angle_to_vertical(p, q):
    """분절 p→q 가 수직축(y)과 이루는 각. 0=완전 수직, 90=수평. 반환: (N,) 도."""
    d = q - p
    return np.degrees(np.arctan2(np.abs(d[:, 0]), np.abs(d[:, 1]) + 1e-9))


# ── 운동별 각도 정의 (선언만 하면 됨) ──────────────────────────────────────────
# 형식: 이름 -> ('joint', 역할A, 역할B, 역할C)  또는  ('vertical', 역할P, 역할Q)
SQUAT_SIDE_ANGLES = {
    'knee':  ('joint', 'hip', 'knee', 'ankle'),       # 무릎 굽힘 (깊이·rep)
    'hip':   ('joint', 'shoulder', 'hip', 'knee'),    # 고관절 굽힘
    'trunk': ('vertical', 'hip', 'shoulder'),         # 몸통 기울기
    'shin':  ('vertical', 'ankle', 'knee'),           # 정강이 각도
}

# 미래 운동 예시 (필요할 때 주석 해제 후 사용):
# PUSHUP_ANGLES = {
#     'elbow': ('joint', 'shoulder', 'elbow', 'wrist'),  # 팔꿈치 굽힘
#     'body':  ('joint', 'shoulder', 'hip', 'ankle'),    # 몸 일직선 유지(~180)
# }
# LATERAL_RAISE_ANGLES = {
#     'abduction': ('vertical', 'shoulder', 'elbow'),    # 팔 벌림 각
# }


# ── 카메라쪽(visibility 높은) 좌/우 선택 ───────────────────────────────────────
def select_side(v):
    """visibility 합이 큰 쪽 관절 역할맵(LEFT/RIGHT)을 반환한다."""
    left_score  = np.nanmean(v[:, list(LEFT.values())])
    right_score = np.nanmean(v[:, list(RIGHT.values())])
    return LEFT if left_score >= right_score else RIGHT


# ── 각도 계산 엔진 ─────────────────────────────────────────────────────────────
def compute_angles(x, y, angle_defs, side):
    """선언된 각도 정의를 프레임별 시계열로 계산한다.

    Args:
        x, y       : (N_frames, 33) 좌표 배열.
        angle_defs : {이름: 정의} dict (위 형식).
        side       : LEFT 또는 RIGHT (select_side 결과).

    Returns:
        {이름: (N_frames,) 각도 시계열} dict.
    """
    def pt(role):
        i = side[role]
        return np.stack([x[:, i], y[:, i]], axis=1)

    result = {}
    for name, d in angle_defs.items():
        if d[0] == 'joint':
            result[name] = joint_angle(pt(d[1]), pt(d[2]), pt(d[3]))
        elif d[0] == 'vertical':
            result[name] = angle_to_vertical(pt(d[1]), pt(d[2]))
        else:
            raise ValueError(f"알 수 없는 각도 유형: {d[0]}")
    return result


def angles_from_csv(csv_path, angle_defs):
    """CSV 를 읽어 카메라쪽 다리를 자동 선택하고 각도 시계열을 계산한다."""
    _, data = load_landmarks(csv_path)
    x, y, z, v = _xyz(data)
    side = select_side(v)
    return compute_angles(x, y, angle_defs, side), side


# ── 실행: 측면 스쿼트 각도 계산 (검증용 요약 출력) ─────────────────────────────
if __name__ == "__main__":
    angles, side = angles_from_csv(
        "data/processed/squat_side_landmarks_normalized.csv", SQUAT_SIDE_ANGLES)
    side_name = 'LEFT' if side is LEFT else 'RIGHT'
    bottom = int(np.argmin(angles['knee']))  # 무릎 각도 최소 = 최저점
    print(f"측면 스쿼트 각도 (카메라쪽 다리: {side_name}, 최저점 frame={bottom})")
    for name, series in angles.items():
        print(f"  {name:6s}: 서있음 {series[0]:6.1f}deg  →  최저점 {series[bottom]:6.1f}deg")
