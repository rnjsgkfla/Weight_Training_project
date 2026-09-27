"""
issues.py — 회차별 결함 목록을 '문제별 카드'로 묶고, 모범 vs 내 동작 비교 프레임을 만든다.

  - 같은 뷰·같은 특징의 결함은 회차가 달라도 카드 하나로 묶는다 ("5회 중 3회").
  - 더 많은 비율의 회차에서 반복된 문제 → 더 심한 문제 순으로 정렬한다.
  - 카드마다 가장 심했던 순간의 썸네일과, 그 결함 구간을 DTW 대응쌍으로 맞춘
    짧은 비교 프레임 묶음(모범 프레임, 내 프레임)을 만든다 → 두 화면이 항상 같은 국면을 보여준다.
  - 비교 프레임에는 문제 관절을 표시한다 (내 자세 빨강, 모범 초록).

이미지 인코딩(render_jpeg)은 분석과 분리해, 분석 결과에는 '어느 영상의 몇 번 프레임'만 담는다.
"""

import cv2
import numpy as np

from judge import FAULT_RULES_BY_EXERCISE, _phase
from smooth_landmarks import load_landmarks

MAX_CLIP_ISSUES = 3      # 비교 재생 프레임은 상위 몇 개 문제까지 만들지 (응답·저장 용량 제한)
CLIP_FRAMES = 12         # 문제 하나당 비교 프레임 수
CLIP_PAD_SEC = 0.3       # 결함 구간 앞뒤로 더 보여줄 시간
CLIP_MIN_SEC = 1.0       # 비교 구간 최소 길이
IMAGE_WIDTH = 360        # 전송용 이미지 가로 크기

# 판정 특징 → 표시할 관절 (MediaPipe 번호)
FEATURE_JOINTS = {
    'knee': [25, 26], 'back_knee': [25, 26], 'valgus': [25, 26], 'sym_knee': [25, 26],
    'knee_travel': [25, 26, 31, 32],
    'hip_depth': [23, 24], 'sym_hip': [23, 24],
    'trunk': [11, 12, 23, 24],
    'stance': [27, 28],
    'arm_L': [11, 13], 'arm_R': [12, 14], 'shoulder_height_diff': [11, 12],
    'elbow_L': [13], 'elbow_R': [14], 'wrist_L': [15], 'wrist_R': [16],
}

VIEW_KR = {'side': '측면', 'front': '정면'}


def _split_message(message):
    """'문제 — 할 일' 형태의 교정 문구를 (문제, 할 일)로 나눈다."""
    head, sep, advice = message.partition(' — ')
    return (head, advice) if sep else (message, None)


def _clip_pairs(fault, path, user_rep, fps):
    """결함 구간(앞뒤 여유 포함)에 해당하는 DTW 대응쌍을 CLIP_FRAMES 개로 고른다."""
    start_f = user_rep['start_f']
    s, e = fault['frame_start'] - start_f, fault['frame_end'] - start_f
    pad = int(round(CLIP_PAD_SEC * fps))
    s, e = s - pad, e + pad
    min_len = int(round(CLIP_MIN_SEC * fps))
    if e - s < min_len:  # 너무 짧으면 가운데를 기준으로 늘린다
        mid = (s + e) // 2
        s, e = mid - min_len // 2, mid + min_len // 2
    s, e = max(s, 0), min(e, user_rep['length'] - 1)

    pairs, seen = [], set()
    for i, j in path:  # 사용자 프레임마다 대응하는 첫 모범 프레임
        if s <= j <= e and j not in seen:
            seen.add(j)
            pairs.append((i, j))
    if len(pairs) > CLIP_FRAMES:
        pick = np.linspace(0, len(pairs) - 1, CLIP_FRAMES).round().astype(int)
        pairs = [pairs[k] for k in pick]
    return pairs


def build_issues(exercise, fault_log, views, names, units):
    """결함 기록을 문제별 카드 데이터로 만든다.

    Args:
        fault_log : [{'view', 'rep'(1-based 회차), 'fault'(judge 결과), 'ref_rep', 'user_rep', 'path'}]
        views     : {view: {'total_reps', 'fps', 'ref_video', 'user_video',
                            'ref_landmarks', 'user_landmarks'}}  (landmarks = 스무딩 CSV 경로)
        names, units : 특징 → 한글 이름 / 단위
    Returns:
        issues : 정렬된 문제 목록. 이미지는 '영상·프레임·표시 관절'로만 담는다
                 (thumb / clip[k] = {'ref': Frame, 'user': Frame, 'phase'},
                  Frame = {'video', 'frame', 'landmarks', 'joints'})
    """
    rules = FAULT_RULES_BY_EXERCISE[exercise]
    groups = {}
    for rec in fault_log:
        f = rec['fault']
        tol = rules[f['feature']][1]
        severity = abs(f['max_dev']) / tol
        g = groups.setdefault((rec['view'], f['feature']), {'reps': set(), 'worst': None, 'severity': 0.0})
        g['reps'].add(rec['rep'])
        if severity > g['severity']:
            g['severity'], g['worst'] = severity, rec

    # 반복 비율(뷰마다 반복 수가 다를 수 있음) → 심각도 순
    ordered = sorted(groups.items(),
                     key=lambda kv: (-len(kv[1]['reps']) / views[kv[0][0]]['total_reps'],
                                     -kv[1]['severity']))
    issues = []
    for rank, ((view, feature), g) in enumerate(ordered):
        rec = g['worst']
        f, ctx = rec['fault'], views[view]
        headline, advice = _split_message(f['message'])
        joints = FEATURE_JOINTS.get(feature, [])

        def frame(side, number):
            return {'video': ctx[f'{side}_video'], 'frame': int(number),
                    'landmarks': ctx[f'{side}_landmarks'], 'joints': joints,
                    'color': (60, 60, 230) if side == 'user' else (80, 200, 80)}  # BGR 빨강 / 초록

        clip = []
        if rank < MAX_CLIP_ISSUES:
            ref_rep, user_rep = rec['ref_rep'], rec['user_rep']
            n_ref = len(ref_rep['align_signal'])
            for i, j in _clip_pairs(f, rec['path'], user_rep, ctx['fps']):
                clip.append({'ref': frame('ref', ref_rep['start_f'] + i),
                             'user': frame('user', user_rep['start_f'] + j),
                             'phase': _phase(i, ref_rep['bottom_rel'], n_ref, exercise)})

        issues.append({
            'key': f"{view}.{feature}", 'view': view, 'view_kr': VIEW_KR[view],
            'feature': feature, 'name': names.get(feature, feature), 'unit': units.get(feature, ''),
            'headline': headline, 'advice': advice,
            'reps': sorted(g['reps']), 'total_reps': ctx['total_reps'],
            'severity': round(g['severity'], 2),
            'rep': rec['rep'], 'phase': f['phase'],
            'time_sec': round((f['user_frame'] - 1) / ctx['fps'], 1),
            'ref_val': round(float(f['ref_val']), 1), 'user_val': round(float(f['user_val']), 1),
            'thumb': {'ref': frame('ref', f['ref_frame']), 'user': frame('user', f['user_frame'])},
            'clip': clip,
        })
    return issues


# ── 저장·응답용 변환 ───────────────────────────────────────────────────────────
def collect_frames(issues):
    """issues 안의 모든 Frame 과 그 이미지 이름을 같은 순서로 모은다.

    이미지 이름: issue{n}_thumb_{ref|user}, issue{n}_clip{k}_{ref|user}
    """
    frames, image_names = [], []
    for n, issue in enumerate(issues):
        for side in ('ref', 'user'):
            frames.append(issue['thumb'][side])
            image_names.append(f"issue{n}_thumb_{side}")
        for k, c in enumerate(issue['clip']):
            for side in ('ref', 'user'):
                frames.append(c[side])
                image_names.append(f"issue{n}_clip{k}_{side}")
    return frames, image_names


def issue_meta(issues):
    """영상·프레임 정보를 뺀 저장용 문제 목록 (비교 프레임은 국면 라벨만 남긴다)."""
    out = []
    for issue in issues:
        meta = {k: v for k, v in issue.items() if k not in ('thumb', 'clip')}
        meta['clip_phases'] = [c['phase'] for c in issue['clip']]
        out.append(meta)
    return out


def with_images(meta_issues, image_uri):
    """저장용 문제 목록에 이미지(data URI)를 붙여 응답 모양으로 만든다. image_uri(name) → str|None"""
    out = []
    for n, meta in enumerate(meta_issues):
        issue = {k: v for k, v in meta.items() if k != 'clip_phases'}
        issue['thumb_ref'] = image_uri(f"issue{n}_thumb_ref")
        issue['thumb_user'] = image_uri(f"issue{n}_thumb_user")
        issue['clip'] = [{'phase': phase,
                          'ref_image': image_uri(f"issue{n}_clip{k}_ref"),
                          'user_image': image_uri(f"issue{n}_clip{k}_user")}
                         for k, phase in enumerate(meta['clip_phases'])]
        out.append(issue)
    return out


# ── 이미지 렌더링 ──────────────────────────────────────────────────────────────


def render_frames(frames):
    """Frame 목록을 JPEG 바이트 목록(같은 순서, 실패하면 None)으로 그린다.

    영상마다 필요한 프레임만 처음부터 순서대로 한 번에 읽는다.
    """
    by_video = {}
    for fr in frames:
        by_video.setdefault(fr['video'], set()).add(fr['frame'])

    images, landmark_cache = {}, {}
    for video, numbers in by_video.items():
        cap = cv2.VideoCapture(video)
        wanted, n = sorted(numbers), 0
        for target in wanted:
            while n < target:  # 순차 읽기 (mp4v 는 임의 탐색이 느리고 부정확할 수 있음)
                ok, img = cap.read()
                n += 1
                if not ok:
                    img = None
                    break
            images[(video, target)] = img
        cap.release()

    out = []
    for fr in frames:
        img = images.get((fr['video'], fr['frame']))
        if img is None:
            out.append(None)
            continue
        img = img.copy()
        h, w = img.shape[:2]
        if fr['joints']:
            if fr['landmarks'] not in landmark_cache:
                nums, data = load_landmarks(fr['landmarks'])
                landmark_cache[fr['landmarks']] = dict(zip(nums.tolist(), data))
            row = landmark_cache[fr['landmarks']].get(fr['frame'])
            if row is not None:
                for jnt in fr['joints']:
                    x, y = row[4 * jnt], row[4 * jnt + 1]
                    if not (np.isnan(x) or np.isnan(y)):
                        cv2.circle(img, (int(x * w), int(y * h)), 11, fr['color'], 3, cv2.LINE_AA)
        scale = IMAGE_WIDTH / w
        img = cv2.resize(img, (IMAGE_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 72])
        out.append(buf.tobytes() if ok else None)
    return out


def good_points(stats_reps, names):
    """모든 회차에서 한 번도 지적되지 않은 항목 이름 (뷰 구분 없이 중복 제거)."""
    by_feature = {}
    for r in stats_reps:
        for m in r['metrics']:
            key = (r['view'], m['feature'])
            by_feature[key] = by_feature.get(key, True) and not m['fault']
    seen, out = set(), []
    for (_view, feature), ok in by_feature.items():
        name = names.get(feature, feature)
        if ok and name not in seen:
            seen.add(name)
            out.append(name)
    return out

