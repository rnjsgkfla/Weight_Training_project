"""
smooth_landmarks.py — 스쿼트 자세 분석 파이프라인 3단계: 랜드마크 스무딩

역할:
  keypoint_extractor 가 뽑은 관절 좌표 CSV 는 프레임마다 미세하게 떨린다(jitter).
  이 떨림을 그대로 각도로 바꾸면 값이 크게 요동쳐 이후 비교(최저점 검출, DTW)가
  불안정해진다. Savitzky-Golay 필터로 x·y·z 좌표를 시간축으로 부드럽게 만든다.

  Savitzky-Golay 를 쓰는 이유:
    단순 이동평균과 달리 국소 다항식 피팅이라 '스쿼트 최저점' 같은 극값(peak)을
    뭉개지 않고 보존한다. → 이후 최저점 검출 정확도에 유리하다.

입력:  data/processed/squat_{front,side}_landmarks.csv
출력:  data/processed/squat_{front,side}_landmarks_smoothed.csv  (동일한 133컬럼 구조)

주의:
  - visibility(v) 컬럼은 스무딩하지 않고 원본을 유지한다(측면 좌우 선택에 쓰는 신뢰도).
  - 인식 실패로 빈 값이 있던 프레임은 앞뒤 값을 선형 보간하여 채운 뒤 스무딩한다.
"""

import numpy as np
import csv
import os
from scipy.signal import savgol_filter


NUM_LANDMARKS = 33  # MediaPipe Pose 관절 수 (컬럼 구조: 관절당 x, y, z, v)


def _interpolate_nan(col):
    """한 컬럼(시간축 1D 배열)의 결측치(nan)를 선형 보간으로 채운다.

    내부 구간은 앞뒤 값 사이를 선형 보간하고, 양 끝의 결측은 가장 가까운 값으로 채운다.
    컬럼 전체가 nan(해당 관절이 한 번도 인식되지 않음)이면 그대로 둔다.
    """
    valid = ~np.isnan(col)
    if not valid.any():
        return col  # 전부 결측이면 손대지 않음
    idx = np.arange(len(col))
    col[~valid] = np.interp(idx[~valid], idx[valid], col[valid])
    return col


def smooth_landmarks(data, window_length=7, polyorder=2):
    """랜드마크 데이터(프레임 × 132)의 x·y·z 컬럼을 Savitzky-Golay 로 스무딩한다.

    Args:
        data          : shape (N_frames, 132) 배열. 컬럼 순서는 관절당 x, y, z, v 반복.
        window_length : 필터 창 크기(홀수). 프레임 수보다 크면 자동으로 줄인다.
        polyorder     : 국소 다항식 차수 (window_length 보다 작아야 함).

    Returns:
        스무딩된 (N_frames, 132) 배열. v 컬럼은 원본 그대로 유지된다.
    """
    n_frames = data.shape[0]

    # 창 크기 안전 보정: 프레임 수 이하 + 홀수 + polyorder 초과 보장
    win = min(window_length, n_frames if n_frames % 2 == 1 else n_frames - 1)
    if win <= polyorder:
        # 프레임이 너무 적어 스무딩 불가 → 원본 반환
        print(f"  프레임 수({n_frames})가 적어 스무딩을 건너뜁니다.")
        return data.copy()

    smoothed = data.copy()
    for i in range(NUM_LANDMARKS):
        for axis in range(3):  # x=0, y=1, z=2 만 스무딩 (v=3 제외)
            c = 4 * i + axis
            col = _interpolate_nan(smoothed[:, c].astype(float))
            if np.isnan(col).any():
                continue  # 보간 불가(전부 결측)한 컬럼은 건너뜀
            smoothed[:, c] = savgol_filter(col, window_length=win, polyorder=polyorder)
    return smoothed


def load_landmarks(csv_path):
    """랜드마크 CSV 를 (frame_numbers, data) 로 읽는다. 빈 값은 nan 으로 변환."""
    frames, data = [], []
    with open(csv_path, newline='') as f:
        reader = csv.reader(f)
        next(reader)  # 헤더 건너뛰기
        for row in reader:
            frames.append(int(row[0]))
            data.append([np.nan if v == '' else float(v) for v in row[1:]])
    return np.array(frames), np.array(data, dtype=float)


def save_landmarks(csv_path, frames, data):
    """(frame_numbers, data) 를 keypoint_extractor 와 동일한 헤더 구조로 저장한다."""
    header = ['frame_number']
    for i in range(NUM_LANDMARKS):
        header.extend([f'x{i}', f'y{i}', f'z{i}', f'v{i}'])
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for fr, row in zip(frames, data):
            writer.writerow([fr] + list(row))


def smooth_csv(input_csv, output_csv, window_length=7, polyorder=2):
    """CSV 하나를 읽어 스무딩 후 저장한다."""
    frames, data = load_landmarks(input_csv)
    print(f"스무딩 중: {os.path.basename(input_csv)} | {len(frames)}프레임")
    smoothed = smooth_landmarks(data, window_length, polyorder)
    save_landmarks(output_csv, frames, smoothed)
    print(f"스무딩 완료: {output_csv}\n")


# ── 실행: 정면 / 측면 랜드마크 스무딩 ──────────────────────────────────────────
if __name__ == "__main__":
    jobs = [
        ("data/processed/squat_front_landmarks.csv",
         "data/processed/squat_front_landmarks_smoothed.csv"),
        ("data/processed/squat_side_landmarks.csv",
         "data/processed/squat_side_landmarks_smoothed.csv"),
    ]

    for input_csv, output_csv in jobs:
        smooth_csv(input_csv, output_csv)
    print("모든 스무딩 완료.")
