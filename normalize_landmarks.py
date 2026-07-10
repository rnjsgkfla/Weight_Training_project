"""
normalize_landmarks.py — 스쿼트 자세 분석 파이프라인 4단계: 좌표 정규화

역할:
  스무딩된 관절 좌표를 '몸 크기·카메라 거리·화면 위치'에 무관하도록 정규화한다.
  이렇게 하면 기준 영상과 사용자 영상의 촬영 조건이 달라도 자세를 직접 비교할 수 있다.

정규화 방식:
  norm = (joint − pelvis) / torso_scale
    - pelvis      : 골반 중심 = midpoint(왼골반23, 오른골반24)  → 원점(0,0,0)으로 이동
    - torso_scale : 어깨중심(11,12) ~ 골반중심(23,24) 거리의 '영상 전체 median'
                    → 몸 크기로 나눠 스케일 통일 (상수 1개, 프레임별 아님)

  프레임별 상체 길이를 쓰지 않는 이유:
    스케일은 몸 크기·카메라 거리를 제거하려는 것이라 영상 내내 상수여야 한다.
    프레임별로 쓰면 스쿼트 시 상체가 앞으로 기울며 생기는 투영 길이 변화(포어쇼트닝)가
    스케일에 섞여 실제 자세를 왜곡한다. median 은 이 변동을 걸러 기립 자세 상체 길이를 잡는다.

종횡비 보정:
  MediaPipe 정규화 x 는 화면 너비, y 는 높이 기준이라 스케일이 다르다.
  x·너비, y·높이(z 는 x 처럼 너비)로 픽셀 환산해 실제 비율을 복원한 뒤 거리를 계산한다.
  (절대 해상도가 아니라 종횡비만 영향을 주지만, 명료하게 width·height 를 인자로 받는다.)

좌우 반전 (측면 전용):
  측면 영상이 왼쪽을 보든 오른쪽을 보든 기준과 방향을 맞추기 위해,
  발끝(31,32)이 발뒤꿈치(29,30)보다 +x 쪽에 오도록(=발끝이 오른쪽을 향하도록) x 를 뒤집는다.
  정면은 좌우 대칭 평가를 해야 하므로 반전하지 않는다.

입력:  data/processed/squat_{front,side}_landmarks_smoothed.csv
출력:  data/processed/squat_{front,side}_landmarks_normalized.csv  (동일한 133컬럼 구조)
"""

import numpy as np
import cv2
from smooth_landmarks import load_landmarks, save_landmarks, NUM_LANDMARKS

# MediaPipe 관절 번호
L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP           = 23, 24
L_HEEL, R_HEEL         = 29, 30
L_FOOT, R_FOOT         = 31, 32   # foot index(발끝)


def _xyz(data):
    """(N,132) 데이터에서 x,y,z 를 각각 (N,33) 배열로 분리한다. v 는 별도 반환."""
    x = data[:, 0::4]  # 컬럼 0,4,8,... → 관절 33개의 x
    y = data[:, 1::4]
    z = data[:, 2::4]
    v = data[:, 3::4]
    return x, y, z, v


def video_resolution(video_path):
    """영상의 실제 프레임 해상도 (width, height) 를 반환한다.

    회전 메타데이터가 있는 폰 영상 등에서 CAP_PROP 값이 실제 디코딩 프레임과
    어긋날 수 있어, 첫 프레임을 직접 읽어 shape 로 해상도를 확정한다.
    (keypoint_extractor 도 같은 방식으로 프레임을 읽으므로 종횡비가 일치한다.)
    """
    cap = cv2.VideoCapture(video_path)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise IOError(f"영상을 읽을 수 없습니다: {video_path}")
    h, w = frame.shape[:2]
    return w, h


def normalize(data, width, height, flip_side=False):
    """스무딩된 (N,132) 데이터를 골반 중심·상체 길이 기준으로 정규화한다.

    Args:
        data      : shape (N_frames, 132). 컬럼 순서 관절당 x,y,z,v 반복.
        width,    : 관절 좌표를 뽑은 영상의 실제 해상도 (종횡비 보정용). 하드코딩 금지 —
        height      video_resolution() 으로 각 영상에서 읽어 넘긴다.
        flip_side : 측면 영상일 때 True → 발끝이 +x 향하도록 좌우 통일.

    Returns:
        정규화된 (N_frames, 132) 배열. v 컬럼은 원본 유지.
    """
    x, y, z, v = _xyz(data)

    # 1. 픽셀 환산 (종횡비 보정). z 는 MediaPipe 관례상 x 처럼 너비 스케일.
    xp = x * width
    yp = y * height
    zp = z * width

    # 2. 골반 중심 (원점) — 매 프레임
    pelvis_x = (xp[:, L_HIP] + xp[:, R_HIP]) / 2
    pelvis_y = (yp[:, L_HIP] + yp[:, R_HIP]) / 2
    pelvis_z = (zp[:, L_HIP] + zp[:, R_HIP]) / 2

    # 3. 상체 길이 스케일 — 어깨중심~골반중심 거리의 영상 전체 median (상수 1개)
    sh_x = (xp[:, L_SHOULDER] + xp[:, R_SHOULDER]) / 2
    sh_y = (yp[:, L_SHOULDER] + yp[:, R_SHOULDER]) / 2
    torso_per_frame = np.sqrt((sh_x - pelvis_x) ** 2 + (sh_y - pelvis_y) ** 2)
    torso_scale = np.nanmedian(torso_per_frame)

    # 4. 정규화: (joint − pelvis) / torso_scale
    nx = (xp - pelvis_x[:, None]) / torso_scale
    ny = (yp - pelvis_y[:, None]) / torso_scale
    nz = (zp - pelvis_z[:, None]) / torso_scale

    # 5. 좌우 반전 (측면 전용): 발끝이 발뒤꿈치보다 +x 에 오도록 통일
    if flip_side:
        toe_x  = (nx[:, L_FOOT] + nx[:, R_FOOT]) / 2
        heel_x = (nx[:, L_HEEL] + nx[:, R_HEEL]) / 2
        facing = np.nanmean(toe_x - heel_x)  # >0 : 발끝이 오른쪽(+x)
        if facing < 0:
            nx = -nx  # 골반 원점 기준이라 x 부호만 뒤집으면 좌우 반전

    # 원래 (N,132) 배치로 되돌리기 (v 는 원본 유지)
    out = data.copy()
    out[:, 0::4] = nx
    out[:, 1::4] = ny
    out[:, 2::4] = nz
    out[:, 3::4] = v
    return out


def normalize_csv(input_csv, output_csv, video_path, flip_side=False):
    """CSV 하나를 정규화한다. 종횡비 보정용 해상도는 video_path 에서 자동으로 읽는다."""
    width, height = video_resolution(video_path)
    frames, data = load_landmarks(input_csv)
    normed = normalize(data, width=width, height=height, flip_side=flip_side)
    save_landmarks(output_csv, frames, normed)
    view = "측면(좌우통일)" if flip_side else "정면"
    print(f"정규화 완료 [{view}] {width}x{height}: {output_csv}")


# ── 실행: 정면 / 측면 정규화 ───────────────────────────────────────────────────
# 해상도는 각 원본 영상에서 자동 감지되므로 하드코딩하지 않는다.
# 사용자 영상도 동일하게 (CSV, 출력, 그 영상 경로) 만 넘기면 된다.
if __name__ == "__main__":
    normalize_csv("data/processed/squat_front_landmarks_smoothed.csv",
                  "data/processed/squat_front_landmarks_normalized.csv",
                  "data/raw/squat_front_raw.mp4", flip_side=False)

    normalize_csv("data/processed/squat_side_landmarks_smoothed.csv",
                  "data/processed/squat_side_landmarks_normalized.csv",
                  "data/raw/squat_side_raw.mp4", flip_side=True)

    print("모든 정규화 완료.")
