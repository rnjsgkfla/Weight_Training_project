"""
build_references.py — 운동별 기준(모범) 데이터 일괄 재생성

원본 영상(data/raw) → keypoint 추출 → 스무딩 → 정규화 → 특징 추출을 운동·뷰마다
실행해, analyze.py 가 템플릿으로 쓰는 data/processed 의
  {접두사}_{뷰}_features.csv, {접두사}_{뷰}_landmarks_smoothed.csv, {접두사}_{뷰}_skeleton.mp4
를 한 번에 만든다.

흩어져 있던 각 파이프라인 스크립트의 __main__ 을 여기로 통일한다.
원본 영상만 있으면 누구나 클론 후 `python build_references.py` 로 기준 데이터를 복원할 수 있다.
(data/processed 는 .gitignore 대상 — 이 스크립트가 그 재현 수단이다.)

주의:
  운동 키(lateral_raise)와 파일 접두사(sidelateralraise)가 달라 매핑으로 흡수한다.
  원본이 없는 운동/뷰는 경고만 남기고 건너뛴다(예: 사이드레터럴레이즈 .mov 미포함 상태).
"""

import os
from keypoint_extractor import extract_keypoints
from smooth_landmarks import smooth_csv
from normalize_landmarks import normalize_csv
from features import extract_and_save

PROCESSED = "data/processed"

# 운동 키 → (파일 접두사, {뷰: 원본 영상 경로})
EXERCISES = {
    'squat': ('squat', {
        'side':  'data/raw/squat_side_raw.mp4',
        'front': 'data/raw/squat_front_raw.mp4',
    }),
    'lunge': ('lunge', {
        'side':  'data/raw/lunge_side_raw.mp4',
        'front': 'data/raw/lunge_front_raw.mp4',
    }),
    'lateral_raise': ('sidelateralraise', {
        'front': 'data/raw/sidelateralraise_front_raw.mov',
    }),
}


def build_one(exercise, prefix, view, raw_video):
    """한 운동·뷰의 기준 데이터를 원본에서 생성한다."""
    base = os.path.join(PROCESSED, f"{prefix}_{view}")
    lm = base + "_landmarks.csv"
    sm = base + "_landmarks_smoothed.csv"
    nm = base + "_landmarks_normalized.csv"
    ft = base + "_features.csv"
    sk = base + "_skeleton.mp4"

    extract_keypoints(raw_video, lm, sk)                       # 1. 관절 추출 + 뼈대 영상
    smooth_csv(lm, sm)                                         # 2. 스무딩
    normalize_csv(sm, nm, raw_video, flip_side=(view == 'side'))  # 3. 정규화 (측면은 좌우통일)
    extract_and_save(exercise, view, nm, ft)                  # 4. 특징 추출(운동 키로 디스패치)


def main():
    os.makedirs(PROCESSED, exist_ok=True)
    built, skipped = 0, 0
    for exercise, (prefix, views) in EXERCISES.items():
        for view, raw in views.items():
            if not os.path.exists(raw):
                print(f"⚠️  건너뜀 [{exercise}/{view}]: 원본 없음 → {raw}")
                skipped += 1
                continue
            print(f"\n▶ 생성 [{exercise}/{view}] ← {raw}")
            build_one(exercise, prefix, view, raw)
            built += 1
    print(f"\n기준 데이터 생성 완료: {built}건 생성, {skipped}건 건너뜀.")


if __name__ == "__main__":
    main()
