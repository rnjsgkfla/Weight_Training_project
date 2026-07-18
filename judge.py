"""
judge.py — 파이프라인 8단계: 임계값 판정 + 피드백 생성

역할:
  DTW 로 정렬된 기준(템플릿) 반복과 사용자 반복을 '전 구간'에서 비교하여,
  특징별로 기준을 벗어난 구간을 찾아 사람이 읽는 피드백으로 만든다.

방식:
  - 정렬 경로를 따라 매 대응쌍에서 (사용자값 − 기준값) 편차를 계산.
  - 특징마다 '나쁜 방향'과 '허용오차'가 다르므로 규칙(FAULT_RULES)으로 선언.
  - 허용오차를 벗어난 상태가 '최소 지속 길이' 이상 이어질 때만 결함으로 확정(잡음 억제).
  - 결함 구간을 사용자 프레임 범위로 매핑하고, 하강/최저/상승 국면도 함께 표시.

판정 기준:
  기본은 '기준 영상 대비'(정렬된 같은 국면에서 사용자가 기준보다 얼마나 나쁜가).
  기준 영상이 표준이므로, 기준보다 허용오차 이상 나빠지면 결함으로 본다.
"""

import numpy as np
from dtw import align_reps, warp_index


# ── 특징별 판정 규칙 ───────────────────────────────────────────────────────────
# 이름: (나쁜_방향, 허용오차, 피드백문구)
#   나쁜_방향: 'high_bad' = 기준보다 값이 커지면 나쁨 / 'low_bad' = 작아지면 나쁨
#              'two_sided' = 양쪽 어느 쪽으로든 벗어나면 나쁨
#   허용오차 : 편차(사용자−기준)가 이만큼을 넘어야 결함. 각도는 도(°), 비율·위치는 그 단위.
FAULT_RULES = {
    # 측면
    'knee':        ('high_bad', 15.0, '무릎을 더 굽혀 깊이 앉으세요 (스쿼트가 얕습니다)'),
    'hip_depth':   ('high_bad', 0.15, '엉덩이를 더 낮추세요 (평행까지 못 내려갔습니다)'),
    'trunk':       ('high_bad', 12.0, '상체가 과도하게 앞으로 숙여집니다'),
    'knee_travel': ('high_bad', 0.15, '무릎이 발끝을 너무 넘어갑니다'),
    # 정면
    'valgus':      ('low_bad',  0.15, '무릎이 안쪽으로 모입니다 (무릎을 바깥으로 미세요)'),
    'stance':      ('two_sided', 0.20, '발 간격이 기준과 다릅니다'),
    'sym_knee':    ('high_bad', 8.0,  '좌우 무릎 굽힘이 비대칭입니다'),
    'sym_hip':     ('high_bad', 0.08, '골반이 한쪽으로 기웁니다'),
}


def _phase(i_ref, bottom_rel, n_ref):
    """기준 인덱스가 하강/최저/상승 중 어디인지 한글 라벨로."""
    if abs(i_ref - bottom_rel) <= max(2, n_ref // 12):
        return '최저'
    return '하강' if i_ref < bottom_rel else '상승'


def judge_rep(ref_rep, user_rep, rules=FAULT_RULES, min_len=5):
    """정렬된 두 반복을 전 구간 비교하여 결함 목록을 반환한다.

    Returns:
        faults : [{feature, message, phase, frame_start, frame_end, max_dev}, ...]
        meta   : {'path', 'norm_dist', 'user_bottom'}
    """
    path, distance, norm_dist, user_bottom = align_reps(ref_rep, user_rep)
    n_ref = len(ref_rep['align_signal'])
    bottom_rel = ref_rep['bottom_rel']
    user_start_f = user_rep['start_f']

    faults = []
    for feat, (direction, tol, msg) in rules.items():
        if feat not in ref_rep['features'] or feat not in user_rep['features']:
            continue  # 이 뷰에 없는 특징은 건너뜀

        rvals = ref_rep['features'][feat]
        uvals = user_rep['features'][feat]

        # 정렬 경로를 따라 각 대응쌍의 결함 여부·편차 기록
        bad_flags, devs, js, irefs = [], [], [], []
        for (i, j) in path:
            dev = uvals[j] - rvals[i]
            if direction == 'high_bad':
                bad = dev > tol
            elif direction == 'low_bad':
                bad = dev < -tol
            else:  # two_sided
                bad = abs(dev) > tol
            bad_flags.append(bad); devs.append(dev); js.append(j); irefs.append(i)

        # min_len 이상 연속으로 결함인 구간 추출
        k = 0
        N = len(bad_flags)
        while k < N:
            if bad_flags[k]:
                s = k
                while k < N and bad_flags[k]:
                    k += 1
                if (k - s) >= min_len:
                    seg_js = js[s:k]
                    seg_devs = np.array(devs[s:k])
                    mid = (s + k) // 2  # 결함 구간 중앙의 국면으로 라벨
                    worst = s + int(np.argmax(np.abs(seg_devs)))  # 편차 최대 지점
                    i_w, j_w = irefs[worst], js[worst]
                    faults.append({
                        'feature': feat,
                        'message': msg,
                        'phase': _phase(irefs[mid], bottom_rel, n_ref),
                        'frame_start': user_start_f + min(seg_js),
                        'frame_end':   user_start_f + max(seg_js),
                        'max_dev': float(seg_devs[np.argmax(np.abs(seg_devs))]),
                        # 비교 시각화용: 편차가 가장 큰 순간의 모범/사용자 프레임·값
                        'ref_frame':  ref_rep['start_f'] + i_w,
                        'user_frame': user_start_f + j_w,
                        'ref_val':    float(rvals[i_w]),
                        'user_val':   float(uvals[j_w]),
                    })
            else:
                k += 1

    meta = {'path': path, 'norm_dist': norm_dist, 'user_bottom': user_bottom}
    return faults, meta


def format_feedback(faults, fps=None):
    """결함 목록을 사람이 읽는 문구로. fps 를 주면 프레임을 초 단위로도 표시."""
    if not faults:
        return "  ✅ 기준 자세와 큰 차이 없음 — 좋은 스쿼트입니다."
    lines = []
    for f in faults:
        if fps:
            t0 = (f['frame_start'] - 1) / fps
            t1 = (f['frame_end'] - 1) / fps
            when = f"{t0:.1f}–{t1:.1f}초"
        else:
            when = f"f{f['frame_start']}–f{f['frame_end']}"
        lines.append(f"  ⚠️ [{f['phase']}] {f['message']} ({when}, 편차 {f['max_dev']:+.2f})")
    return "\n".join(lines)


# ── 실행: 합성 사용자로 판정 검증 ──────────────────────────────────────────────
if __name__ == "__main__":
    import copy
    from rep_features import slice_reps

    side_reps, _ = slice_reps("data/processed/squat_side_features.csv",
                              "data/processed/squat_side_landmarks_smoothed.csv")
    ref = side_reps[0]

    # ① 정상 사용자 (기준 그대로) → 결함 없어야 함
    print("① 정상 사용자 (기준과 동일):")
    faults, _ = judge_rep(ref, copy.deepcopy(ref))
    print(format_feedback(faults))

    # ② 상체 과숙임: 상승 구간 trunk +20°
    print("\n② 상체 과숙임 주입 (상승 구간 trunk +20°):")
    bad = copy.deepcopy(ref)
    b = bad['bottom_rel']
    bad['features']['trunk'] = bad['features']['trunk'].copy()
    bad['features']['trunk'][b:] += 20.0
    faults, _ = judge_rep(ref, bad)
    print(format_feedback(faults))

    # ③ 얕은 스쿼트: 서있음은 같고 '바닥 깊이만' 40% 얕게 (현실적)
    print("\n③ 얕은 스쿼트 주입 (깊이 40% 감소):")
    bad = copy.deepcopy(ref)
    top = bad['align_signal'].max()
    bad['features']['knee'] = top - (top - bad['features']['knee']) * 0.6
    bad['align_signal']     = top - (top - bad['align_signal']) * 0.6
    faults, _ = judge_rep(ref, bad)
    print(format_feedback(faults))

    # ④ 정면 무릎 모임(valgus): 상승 구간에서 valgus 를 낮춤 (무릎이 안으로)
    print("\n④ 정면 무릎 모임 주입 (상승 구간 valgus −0.5):")
    front_reps, _ = slice_reps("data/processed/squat_front_features.csv",
                               "data/processed/squat_front_landmarks_smoothed.csv")
    fref = front_reps[0]
    fbad = copy.deepcopy(fref)
    b = fbad['bottom_rel']
    fbad['features']['valgus'] = fbad['features']['valgus'].copy()
    fbad['features']['valgus'][b:] -= 0.5
    faults, _ = judge_rep(fref, fbad)
    print(format_feedback(faults))
