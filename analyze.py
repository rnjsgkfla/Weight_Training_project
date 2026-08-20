"""
analyze.py — 파이프라인 최종 통합: 사용자 영상 → 자세 피드백

역할:
  사용자의 측면·정면 스쿼트 영상을 받아 전 과정을 자동 실행하고, 반복별로
  기준(표준) 영상과 비교해 자세 피드백을 출력한다.

전체 흐름 (뷰마다):
  raw 영상 → keypoint 추출 → 스무딩 → 정규화 → 특징 추출
           → 반복 분할·슬라이싱 → 기준 템플릿과 DTW 정렬 → 임계값 판정 → 피드백

기준 템플릿:
  data/processed 의 기준 영상 특징(측면/정면 각 1 rep)을 템플릿으로 사용한다.
  (사용자가 5회 하면 5개 반복이 각각 이 템플릿과 비교된다.)

사용자 영상은 측면 세트·정면 세트를 따로 촬영해 2개 파일로 올린다(휴대폰 1대 제약).
"""

import os
import cv2

from keypoint_extractor import extract_keypoints
from smooth_landmarks import smooth_csv
from normalize_landmarks import normalize_csv
from features import extract_and_save
from rep_features import slice_reps
from judge import judge_rep, format_feedback, PHASE_LABELS

# 기준(템플릿) 영상의 특징/스무딩 CSV — 운동·뷰별 1 rep
REFERENCE = {
    'squat': {
        'side':  ("data/processed/squat_side_features.csv",
                  "data/processed/squat_side_landmarks_smoothed.csv"),
        'front': ("data/processed/squat_front_features.csv",
                  "data/processed/squat_front_landmarks_smoothed.csv"),
    },
    'lateral_raise': {
        'front': ("data/processed/sidelateralraise_front_features.csv",
                  "data/processed/sidelateralraise_front_landmarks_smoothed.csv"),
    },
    'lunge': {
        'side':  ("data/processed/lunge_side_features.csv",
                  "data/processed/lunge_side_landmarks_smoothed.csv"),
        'front': ("data/processed/lunge_front_features.csv",
                  "data/processed/lunge_front_landmarks_smoothed.csv"),
    },
}

# 기준 뼈대 영상 (비교 시각화용)
REFERENCE_SKELETON = {
    'squat': {
        'side':  "data/processed/squat_side_skeleton.mp4",
        'front': "data/processed/squat_front_skeleton.mp4",
    },
    'lateral_raise': {
        'front': "data/processed/sidelateralraise_front_skeleton.mp4",
    },
    'lunge': {
        'side':  "data/processed/lunge_side_skeleton.mp4",
        'front': "data/processed/lunge_front_skeleton.mp4",
    },
}

# 운동 이름 (UI 표시용)
EXERCISE_KR = {'squat': '스쿼트', 'lateral_raise': '사이드 레터럴 레이즈', 'lunge': '런지'}

# leg 가 None 일 때(카메라쪽 다리 고정 개념이 없는 운동) 보여줄 대체 라벨
NEUTRAL_LEG_LABEL = {'lateral_raise': '정면(양팔)', 'lunge': '앞다리 자동판별(반복마다 다를 수 있음)'}

# 특징 → 한글 짧은 이름 / 단위 (UI 표시용)
FEATURE_KR = {
    'knee': '무릎 깊이', 'hip': '고관절 깊이', 'hip_depth': '엉덩이 깊이',
    'trunk': '상체 기울기', 'shin': '정강이 각도', 'knee_travel': '무릎 전방이동',
    'valgus': '무릎 모임', 'stance': '스탠스 너비',
    'sym_knee': '좌우 무릎 대칭', 'sym_hip': '골반 수평',
    'arm_L': '왼팔 거상 높이', 'arm_R': '오른팔 거상 높이',
    'elbow_L': '왼쪽 팔꿈치 각도', 'elbow_R': '오른쪽 팔꿈치 각도',
    'wrist_L': '왼쪽 손목 높이', 'wrist_R': '오른쪽 손목 높이',
    'shoulder_height_diff': '좌우 어깨 높이차',
    'back_knee': '뒷다리 무릎 깊이',
}
FEATURE_UNIT = {'knee': '°', 'hip': '°', 'trunk': '°', 'shin': '°', 'sym_knee': '°',
                'arm_L': '°', 'arm_R': '°', 'elbow_L': '°', 'elbow_R': '°',
                'back_knee': '°'}


def get_fps(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps if fps and fps > 0 else 24.0


def load_reference_rep(exercise, view):
    """기준 영상에서 템플릿 반복 1개를 로드한다."""
    feat_csv, sm_csv = REFERENCE[exercise][view]
    reps, _leg = slice_reps(feat_csv, sm_csv, exercise=exercise)
    if not reps:
        raise RuntimeError(f"기준 영상({exercise}/{view})에서 반복을 찾지 못했습니다.")
    return reps[0]


def process_user_video(video_path, exercise, view, workdir):
    """사용자 영상 하나(한 운동·뷰)를 파이프라인에 태워 반복별 특징까지 만든다."""
    os.makedirs(workdir, exist_ok=True)
    base = os.path.join(workdir, f"{exercise}_{view}")
    lm = base + "_landmarks.csv"
    sm = base + "_smoothed.csv"
    nm = base + "_normalized.csv"
    ft = base + "_features.csv"
    sk = base + "_skeleton.mp4"

    extract_keypoints(video_path, lm, sk)
    smooth_csv(lm, sm)
    normalize_csv(sm, nm, video_path, flip_side=(view == 'side'))
    extract_and_save(exercise, view, nm, ft)
    user_reps, leg = slice_reps(ft, sm, exercise=exercise)
    return user_reps, leg


def analyze_view(video_path, exercise, view, workdir="data/processed/_user"):
    """한 운동·뷰 영상을 분석해 반복별 피드백을 출력한다."""
    ref_rep = load_reference_rep(exercise, view)
    user_reps, leg = process_user_video(video_path, exercise, view, workdir)
    fps = get_fps(video_path)
    leg_label = leg if leg else NEUTRAL_LEG_LABEL.get(exercise, "정면")

    print(f"\n===== [{EXERCISE_KR[exercise]}/{view.upper()}] {leg_label} | 반복 {len(user_reps)}회 =====")
    total_faults = 0
    for k, rep in enumerate(user_reps, 1):
        faults, _meta = judge_rep(ref_rep, rep, exercise=exercise)
        total_faults += len(faults)
        t0 = (rep['start_f'] - 1) / fps
        t1 = (rep['end_f'] - 1) / fps
        print(f"[{k}회차 {t0:.1f}~{t1:.1f}초]")
        print(format_feedback(faults, fps=fps))
    return total_faults


def run_analysis(video_path, exercise, view, workdir="data/processed/_user"):
    """한 운동·뷰 영상을 분석해 피드백을 '문자열'로 반환한다 (UI 용)."""
    ref_rep = load_reference_rep(exercise, view)
    user_reps, leg = process_user_video(video_path, exercise, view, workdir)
    fps = get_fps(video_path)
    leg_label = leg if leg else NEUTRAL_LEG_LABEL.get(exercise, "정면")

    view_kr = '측면' if view == 'side' else '정면'
    lines = [f"### [{view_kr}] {leg_label} · 반복 {len(user_reps)}회"]
    for k, rep in enumerate(user_reps, 1):
        faults, _meta = judge_rep(ref_rep, rep, exercise=exercise)
        t0 = (rep['start_f'] - 1) / fps
        t1 = (rep['end_f'] - 1) / fps
        lines.append(f"\n**{k}회차 ({t0:.1f}–{t1:.1f}초)**")
        lines.append(format_feedback(faults, fps=fps))
    return "\n".join(lines)


def frame_at(video_path, frame_number):
    """영상에서 특정 frame_number(1-based)의 프레임을 RGB 이미지로 반환한다."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_number - 1))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def analyze_for_ui(exercise='squat', side_video=None, front_video=None, workdir="data/processed/_user"):
    """UI용 구조화 분석. 클릭 가능한 피드백 항목 리스트와 요약을 반환한다.

    exercise 가 지원하지 않는 뷰(예: lateral_raise 의 side_video)는 무시한다.

    각 항목:
      key         : 항목을 고르는 내부 식별자. 리스트 내 순번 기반이라 항상 고유하다
                    (label 은 사람이 읽는 문구라 같은 회차·같은 특징이 서로 다른 시점에
                    두 번 걸리면 같은 문구가 나올 수 있음 — 선택은 반드시 key 로 한다)
      label       : 선택 목록에 뜨는 이름
      detail      : 상세 설명(markdown)
      ref_video   : 모범 뼈대 영상 경로,  ref_frame : 그 안의 비교 프레임
      user_video  : 사용자 뼈대 영상 경로, user_frame: 그 안의 비교 프레임
      ok          : 결함 없이 '양호'한 항목이면 True
    """
    items = []
    summary = []
    videos = {'side': side_video, 'front': front_video}
    for view in REFERENCE[exercise]:
        video = videos.get(view)
        if not video:
            continue
        ref_rep = load_reference_rep(exercise, view)
        user_reps, leg = process_user_video(video, exercise, view, workdir)
        fps = get_fps(video)
        view_kr = '측면' if view == 'side' else '정면'
        ref_skel = REFERENCE_SKELETON[exercise][view]
        user_skel = os.path.join(workdir, f"{exercise}_{view}_skeleton.mp4")

        peak_label = PHASE_LABELS.get(exercise, PHASE_LABELS['squat'])[1]
        n_fault = 0
        for k, rep in enumerate(user_reps, 1):
            faults, _meta = judge_rep(ref_rep, rep, exercise=exercise)
            if not faults:
                # 양호한 반복: 극점끼리 비교를 보여준다
                items.append({
                    'key': f"item{len(items)}",
                    'label': f"✅ {view_kr} · {k}회차 · 양호",
                    'detail': f"### {view_kr} {k}회차 — 기준과 큰 차이 없음 👍\n{peak_label} 자세를 비교해 보세요.",
                    'ref_video': ref_skel, 'ref_frame': ref_rep['bottom_f'],
                    'user_video': user_skel, 'user_frame': rep['bottom_f'],
                    'ok': True,
                })
                continue
            for f in faults:
                n_fault += 1
                name = FEATURE_KR.get(f['feature'], f['feature'])
                unit = FEATURE_UNIT.get(f['feature'], '')
                t = (f['user_frame'] - 1) / fps
                detail = (
                    f"### {view_kr} {k}회차 · {name}\n"
                    f"**{f['phase']} 국면 · {t:.1f}초 지점**\n\n"
                    f"- 모범: **{f['ref_val']:.1f}{unit}**\n"
                    f"- 내 자세: **{f['user_val']:.1f}{unit}**  (차이 {f['max_dev']:+.1f}{unit})\n\n"
                    f"➡️ {f['message']}"
                )
                items.append({
                    'key': f"item{len(items)}",
                    'label': f"⚠️ {view_kr} · {k}회차 · {name} ({t:.1f}s)",
                    'detail': detail,
                    'ref_video': ref_skel, 'ref_frame': f['ref_frame'],
                    'user_video': user_skel, 'user_frame': f['user_frame'],
                    'ok': False,
                })
        summary.append(f"**{view_kr}**: {len(user_reps)}회 · 지적 {n_fault}건")

    summary_md = "### 분석 결과\n" + " / ".join(summary) + \
                 "\n\n아래 항목을 클릭하면 모범 자세와 내 자세를 비교할 수 있어요."
    if not items:
        summary_md = "⚠️ 영상을 하나 이상 올려주세요."
    return items, summary_md


def analyze(exercise='squat', side_video=None, front_video=None, workdir="data/processed/_user"):
    """사용자 영상을 받아 전체 분석·피드백을 실행한다. exercise 가 지원하지 않는
    뷰(예: lateral_raise 의 side_video)는 무시한다."""
    print(f"{EXERCISE_KR[exercise]} 자세 분석 시작...")
    videos = {'side': side_video, 'front': front_video}
    for view in REFERENCE[exercise]:
        video = videos.get(view)
        if video:
            analyze_view(video, exercise, view, workdir)
    print("\n분석 완료.")


# ── 실행: 데모 (기준 원본 영상을 '사용자'로 넣어 전체 파이프라인 점검) ─────────
if __name__ == "__main__":
    # 실제 사용자 영상이 없으므로 기준 원본을 사용자로 넣어본다.
    # 사용자=기준이므로 '결함 없음(좋은 자세)'이 나오면 전 과정이 정상.
    analyze(exercise='squat',
            side_video="data/raw/squat_side_raw.mp4",
            front_video="data/raw/squat_front_raw.mp4")
    analyze(exercise='lateral_raise',
            front_video="data/raw/sidelateralraise_front_raw.mov")
    analyze(exercise='lunge',
            side_video="data/raw/lunge_side_raw.mp4",
            front_video="data/raw/lunge_front_raw.mp4")
