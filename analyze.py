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
from judge import judge_rep, format_feedback

# 기준(템플릿) 영상의 특징/스무딩 CSV — 뷰별 1 rep
REFERENCE = {
    'side':  ("data/processed/squat_side_features.csv",
              "data/processed/squat_side_landmarks_smoothed.csv"),
    'front': ("data/processed/squat_front_features.csv",
              "data/processed/squat_front_landmarks_smoothed.csv"),
}

# 기준 뼈대 영상 (비교 시각화용)
REFERENCE_SKELETON = {
    'side':  "data/processed/squat_side_skeleton.mp4",
    'front': "data/processed/squat_front_skeleton.mp4",
}

# 특징 → 한글 짧은 이름 / 단위 (UI 표시용)
FEATURE_KR = {
    'knee': '무릎 깊이', 'hip': '고관절 깊이', 'hip_depth': '엉덩이 깊이',
    'trunk': '상체 기울기', 'shin': '정강이 각도', 'knee_travel': '무릎 전방이동',
    'valgus': '무릎 모임', 'stance': '스탠스 너비',
    'sym_knee': '좌우 무릎 대칭', 'sym_hip': '골반 수평',
}
FEATURE_UNIT = {'knee': '°', 'hip': '°', 'trunk': '°', 'shin': '°', 'sym_knee': '°'}


def get_fps(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps if fps and fps > 0 else 24.0


def load_reference_rep(view):
    """기준 영상에서 템플릿 반복 1개를 로드한다."""
    feat_csv, sm_csv = REFERENCE[view]
    reps, _leg = slice_reps(feat_csv, sm_csv)
    if not reps:
        raise RuntimeError(f"기준 영상({view})에서 반복을 찾지 못했습니다.")
    return reps[0]


def process_user_video(video_path, view, workdir):
    """사용자 영상 하나(한 뷰)를 파이프라인에 태워 반복별 특징까지 만든다."""
    os.makedirs(workdir, exist_ok=True)
    base = os.path.join(workdir, view)
    lm = base + "_landmarks.csv"
    sm = base + "_smoothed.csv"
    nm = base + "_normalized.csv"
    ft = base + "_features.csv"
    sk = base + "_skeleton.mp4"

    extract_keypoints(video_path, lm, sk)
    smooth_csv(lm, sm)
    normalize_csv(sm, nm, video_path, flip_side=(view == 'side'))
    extract_and_save('squat', view, nm, ft)
    user_reps, leg = slice_reps(ft, sm)
    return user_reps, leg


def analyze_view(video_path, view, workdir="data/processed/_user"):
    """한 뷰 영상을 분석해 반복별 피드백을 출력한다."""
    ref_rep = load_reference_rep(view)
    user_reps, leg = process_user_video(video_path, view, workdir)
    fps = get_fps(video_path)

    print(f"\n===== [{view.upper()}] 카메라쪽 다리={leg} | 반복 {len(user_reps)}회 =====")
    total_faults = 0
    for k, rep in enumerate(user_reps, 1):
        faults, _meta = judge_rep(ref_rep, rep)
        total_faults += len(faults)
        t0 = (rep['start_f'] - 1) / fps
        t1 = (rep['end_f'] - 1) / fps
        print(f"[{k}회차 {t0:.1f}~{t1:.1f}초]")
        print(format_feedback(faults, fps=fps))
    return total_faults


def run_analysis(video_path, view, workdir="data/processed/_user"):
    """한 뷰 영상을 분석해 피드백을 '문자열'로 반환한다 (UI 용)."""
    ref_rep = load_reference_rep(view)
    user_reps, leg = process_user_video(video_path, view, workdir)
    fps = get_fps(video_path)

    view_kr = '측면' if view == 'side' else '정면'
    lines = [f"### [{view_kr}] 카메라쪽 다리={leg} · 반복 {len(user_reps)}회"]
    for k, rep in enumerate(user_reps, 1):
        faults, _meta = judge_rep(ref_rep, rep)
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


def analyze_for_ui(side_video=None, front_video=None, workdir="data/processed/_user"):
    """UI용 구조화 분석. 클릭 가능한 피드백 항목 리스트와 요약을 반환한다.

    각 항목:
      label       : 선택 목록에 뜨는 이름
      detail      : 상세 설명(markdown)
      ref_video   : 모범 뼈대 영상 경로,  ref_frame : 그 안의 비교 프레임
      user_video  : 사용자 뼈대 영상 경로, user_frame: 그 안의 비교 프레임
      ok          : 결함 없이 '양호'한 항목이면 True
    """
    items = []
    summary = []
    for view, video in [('side', side_video), ('front', front_video)]:
        if not video:
            continue
        ref_rep = load_reference_rep(view)
        user_reps, leg = process_user_video(video, view, workdir)
        fps = get_fps(video)
        view_kr = '측면' if view == 'side' else '정면'
        ref_skel = REFERENCE_SKELETON[view]
        user_skel = os.path.join(workdir, f"{view}_skeleton.mp4")

        n_fault = 0
        for k, rep in enumerate(user_reps, 1):
            faults, _meta = judge_rep(ref_rep, rep)
            if not faults:
                # 양호한 반복: 최저점끼리 비교를 보여준다
                items.append({
                    'label': f"✅ {view_kr} · {k}회차 · 양호",
                    'detail': f"### {view_kr} {k}회차 — 기준과 큰 차이 없음 👍\n최저 자세를 비교해 보세요.",
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
                    'label': f"⚠️ {view_kr} · {k}회차 · {name}",
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


def analyze(side_video=None, front_video=None, workdir="data/processed/_user"):
    """사용자 측면·정면 영상을 받아 전체 분석·피드백을 실행한다."""
    print("스쿼트 자세 분석 시작...")
    if side_video:
        analyze_view(side_video, 'side', workdir)
    if front_video:
        analyze_view(front_video, 'front', workdir)
    print("\n분석 완료.")


# ── 실행: 데모 (기준 원본 영상을 '사용자'로 넣어 전체 파이프라인 점검) ─────────
if __name__ == "__main__":
    # 실제 사용자 영상이 없으므로 기준 원본을 사용자로 넣어본다.
    # 사용자=기준이므로 '결함 없음(좋은 스쿼트)'이 나오면 전 과정이 정상.
    analyze(side_video="data/raw/squat_side_raw.mp4",
            front_video="data/raw/squat_front_raw.mp4")
