"""
keypoint_extractor.py — 스쿼트 자세 분석 파이프라인 2단계: 뼈대 좌표 추출

역할:
  스쿼트 기준 영상(정면/측면, data/raw)에서 MediaPipe Pose 로 매 프레임마다
  33개 신체 관절(keypoint)의 x·y·z 좌표와 인식 신뢰도(visibility)를 CSV 로 저장하고,
  동시에 뼈대가 그려진 결과 영상도 함께 생성한다.

  → 골프 스윙 프로젝트의 MediaPipe 추출 코드를 재사용했다.

출력 (정면/측면 각각):
  - data/processed/squat_front_landmarks.csv  : 관절 좌표 데이터 (후속 분석에 사용)
  - data/processed/squat_front_skeleton.mp4   : 뼈대 오버레이 영상 (시각적 검증용)

MediaPipe 관절 번호 참고 (스쿼트 분석 핵심 관절):
  11=왼어깨, 12=오른어깨, 23=왼골반, 24=오른골반,
  25=왼무릎, 26=오른무릎, 27=왼발목, 28=오른발목
  (전체 목록: https://google.github.io/mediapipe/solutions/pose.html)
"""

import cv2
import mediapipe as mp
import os
import csv


# ── MediaPipe 초기화 ───────────────────────────────────────────────────────────
# static_image_mode=False: 영상 모드(프레임 간 연속성 추적) → 이미지 모드보다 빠름
# min_detection_confidence: 처음 관절을 탐지할 때 최소 신뢰도 (0.5 = 50%)
# min_tracking_confidence : 이미 탐지된 관절을 추적할 때 최소 신뢰도
mp_pose    = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils


def extract_keypoints(video_path, csv_path, output_video_path):
    """
    한 영상에서 프레임별 33개 관절 좌표를 CSV 로 저장하고 뼈대 영상을 생성한다.

    Args:
        video_path        : 전처리된 입력 영상 경로
        csv_path          : 관절 좌표를 저장할 CSV 경로
        output_video_path : 뼈대가 그려진 결과 영상 저장 경로
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"에러: '{video_path}' 영상을 불러올 수 없습니다.")
        return

    # 원본 FPS 를 그대로 사용하여 결과 영상 재생 속도를 입력과 동일하게 유지한다.
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 24  # FPS 정보가 없는 영상에 대한 안전 기본값

    # CSV 헤더: frame_number, x0,y0,z0,v0, ..., x32,y32,z32,v32 (총 1 + 33*4 = 133 컬럼)
    landmarks_header = ['frame_number']
    for i in range(33):
        landmarks_header.extend([f'x{i}', f'y{i}', f'z{i}', f'v{i}'])

    # 영상마다 별도의 Pose 인스턴스를 사용하여 프레임 간 추적 상태가 섞이지 않도록 한다.
    pose = mp_pose.Pose(static_image_mode=False,
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5)

    with open(csv_path, mode='w', newline='') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(landmarks_header)

        frame_count = 0
        out = None  # VideoWriter 는 첫 프레임 크기 확인 후 초기화

        print(f"분석 시작: {os.path.basename(video_path)} → '{csv_path}'")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # 화면에 맞게 리사이즈 (원본 비율 유지). 정규화 좌표라 CSV 값에는 영향 없음.
            h, w, c = frame.shape
            target_width  = 600
            scale_factor  = target_width / w
            target_height = int(h * scale_factor)
            frame_resized = cv2.resize(frame, (target_width, target_height),
                                       interpolation=cv2.INTER_AREA)

            # 첫 프레임에서 리사이즈된 크기를 확인한 뒤 VideoWriter 를 초기화한다.
            if out is None:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # mp4v 코덱 (macOS/Windows 호환)
                out = cv2.VideoWriter(output_video_path, fourcc, fps,
                                      (target_width, target_height))

            # MediaPipe 는 BGR 이 아닌 RGB 이미지를 입력받는다.
            image_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            results   = pose.process(image_rgb)

            if results.pose_landmarks:
                # 33개 관절 좌표를 한 행으로 평탄화하여 CSV 에 저장
                frame_data = [frame_count]
                for landmark in results.pose_landmarks.landmark:
                    frame_data.extend([landmark.x, landmark.y, landmark.z, landmark.visibility])

                # 뼈대 시각화: 관절은 빨간색 원, 연결선은 초록색
                mp_drawing.draw_landmarks(
                    frame_resized,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=1, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=1, circle_radius=1)
                )
            else:
                # 관절을 인식하지 못한 프레임은 빈 값('')으로 채워 행 수를 유지한다.
                frame_data = [frame_count] + [''] * (33 * 4)

            csv_writer.writerow(frame_data)
            out.write(frame_resized)

    cap.release()
    if out is not None:
        out.release()
    pose.close()
    print(f"분석 완료: 좌표 → '{csv_path}', 뼈대 영상 → '{output_video_path}'\n")


# ── 실행: 정면 / 측면 전처리 영상에서 관절 추출 ────────────────────────────────
if __name__ == "__main__":
    jobs = [
        ("data/raw/squat_front_raw.mp4",
         "data/processed/squat_front_landmarks.csv",
         "data/processed/squat_front_skeleton.mp4"),
        ("data/raw/squat_side_raw.mp4",
         "data/processed/squat_side_landmarks.csv",
         "data/processed/squat_side_skeleton.mp4"),
    ]

    for video_path, csv_path, output_video_path in jobs:
        extract_keypoints(video_path, csv_path, output_video_path)

    print("모든 관절 추출 완료.")
