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


# ── 특징별 판정 규칙 (운동별) ──────────────────────────────────────────────────
# 이름: (나쁜_방향, 허용오차, 피드백문구)
#   나쁜_방향: 'high_bad'  = 기준보다 값이 커지면 나쁨 / 'low_bad' = 작아지면 나쁨
#              'two_sided' = 양쪽 어느 쪽으로든 벗어나면 나쁨
#              'asym'      = 특징 자체가 '왼쪽−오른쪽' 부호 있는 차이일 때 쓴다.
#                            |사용자 값| 이 허용오차(절대 기준)를 넘으면 결함(어느 쪽이
#                            더 큰지는 안 따짐 — 좌우가 바뀌어도 똑같이 나쁨).
#                            기준 영상과 비교하지 않고 절대값으로 보는 이유: 이 신호는
#                            같은 '좋은' 기준 반복 안에서도 국면(예: 내리는 도중 양팔이
#                            완전히 같은 타이밍으로 안 움직임)에 따라 자연스럽게 흔들려서,
#                            '그 순간의 기준값 + 허용오차'로 비교하면 기준이 흔들리는
#                            국면에서 사용자가 진짜 심하게 틀어져도 안 잡히는 사각지대가
#                            생긴다(실측: 기준 자체가 하강 후반에 최대 0.12까지 흔들림).
#   허용오차 : 판정에 쓰는 편차가 이만큼을 넘어야 결함. 각도는 도(°), 비율·위치는 그 단위.
#              'asym'은 절대 기준이라 기준 영상의 자연스러운 최대 흔들림보다 커야 한다.
#   피드백문구 : 보통은 고정 문자열. 방향에 따라 해야 할 행동이 달라지는 경우엔
#               (dev, user_val, features, j) 를 받아 문구를 만드는 함수를 대신 넣는다
#               (아래 _*_msg 참고).
#                 dev      : 판정에 쓰인 편차(방향 판단용, 나쁜_방향과 같은 정의)
#                 user_val : 사용자의 원래 특징값(그 순간의 실측치 — 'asym'에서 왼쪽/
#                            오른쪽 중 어디가 낮은지처럼 dev 만으론 알 수 없는 정보에 씀)
#                 features : user_rep['features'] 전체(그 순간 다른 특징도 참고하고 싶을 때 씀)
#                 j        : features 에서 그 순간을 가리키는 인덱스(사용자 쪽)
#               "기준과 다릅니다"/"비대칭입니다" 같은 모호한 문구 대신 "펴세요"/
#               "왼팔을 더 들어올리세요"처럼 방향이 있는 지시를 준다.
def _stance_msg(dev, user_val=None, features=None, j=None):
    return ('발 간격이 기준보다 넓습니다 — 살짝 좁혀보세요' if dev > 0 else
            '발 간격이 기준보다 좁습니다 — 살짝 넓혀보세요')


def _elbow_msg(side):
    def msg(dev, user_val=None, features=None, j=None):
        # elbow 각도: 180°=완전히 폄, 작을수록 굽음. dev<0 → 기준보다 더 굽힘 → 펴야 함.
        if dev < 0:
            return f'{side} 팔꿈치를 기준보다 많이 굽혔습니다 — 조금 더 펴보세요'
        return f'{side} 팔꿈치가 기준보다 많이 펴져 있습니다 — 살짝 구부려보세요'
    return msg


def _wrist_height_msg(side):
    """손목 y 좌표를 기준 영상의 같은 순간(DTW 정렬) 값과 직접 비교한 결과용 문구.
    좌우를 서로 비교하는 게 아니라 '그 손목이 기준보다 낮은지/높은지'를 바로 말해준다
    — 한쪽만 기준보다 과도하게 높이 들려도(반대쪽은 정상) 곧바로 잡힌다.
    """
    def msg(dev, user_val=None, features=None, j=None):
        # y 는 아래로 갈수록 커짐. dev>0 → 사용자 y 가 기준보다 큼 → 더 아래(낮게 듦).
        if dev > 0:
            return f'{side} 손목이 모범 영상보다 낮습니다 — 조금 더 들어올려 보세요'
        return f'{side} 손목이 모범 영상보다 높습니다 — 살짝 내려보세요'
    return msg


def _height_diff_msg(part):
    def msg(dev, user_val, features=None, j=None):
        # user_val = 왼쪽y − 오른쪽y. 정규화 좌표는 아래로 갈수록 커지므로
        # 양수면 왼쪽이 더 아래(덜 든 것) → 왼쪽을 더 올려야 함.
        side = '왼쪽' if user_val > 0 else '오른쪽'
        return f'{side} {part}이 반대쪽보다 낮습니다 — {side}을 조금 더 들어올려 보세요'
    return msg


def _arm_msg(side):
    def msg(dev, user_val=None, features=None, j=None):
        # arm 거상각: 클수록 높이 든 것. dev<0 → 기준보다 덜 들어올림 / dev>0 → 기준보다
        # 더 높이 들어올림 (사이드레터럴레이즈는 어깨 높이 이상 넘기면 안 됨 — 어깨 충돌
        # 위험·승모근 개입 증가. 너무 낮은 것만큼이나 명확한 결함이라 two_sided 로 잡는다).
        if dev < 0:
            return f'{side}을 어깨 높이까지 충분히 들어올리지 못했습니다 — 조금 더 들어올려 보세요'
        return f'{side}을 기준보다 높이 들어올렸습니다 — 어깨 높이 정도까지만 들어올려 보세요'
    return msg


SQUAT_FAULT_RULES = {
    # 측면
    'knee':        ('high_bad', 15.0, '무릎을 더 굽혀 깊이 앉으세요 (스쿼트가 얕습니다)'),
    'hip_depth':   ('high_bad', 0.15, '엉덩이를 더 낮추세요 (평행까지 못 내려갔습니다)'),
    'trunk':       ('high_bad', 12.0, '상체가 과도하게 앞으로 숙여집니다'),
    'knee_travel': ('high_bad', 0.15, '무릎이 발끝을 너무 넘어갑니다'),
    # 정면
    'valgus':      ('low_bad',  0.15, '무릎이 안쪽으로 모입니다 (무릎을 바깥으로 미세요)'),
    'stance':      ('two_sided', 0.20, _stance_msg),
    'sym_knee':    ('high_bad', 8.0,  '좌우 무릎 굽힘이 비대칭입니다'),
    'sym_hip':     ('high_bad', 0.08, '골반이 한쪽으로 기웁니다'),
}

LATERAL_RAISE_FAULT_RULES = {
    'arm_L':               ('two_sided', 15.0, _arm_msg('왼팔')),
    'arm_R':               ('two_sided', 15.0, _arm_msg('오른팔')),
    'elbow_L':              ('two_sided', 15.0, _elbow_msg('왼쪽')),
    'elbow_R':              ('two_sided', 15.0, _elbow_msg('오른쪽')),
    'trunk':                ('high_bad',  10.0, '몸통을 옆으로 기울이며 반동을 사용하고 있습니다'),
    # 손목 높이: 좌우를 서로 비교하지 않고 각각 기준 영상의 같은 순간(DTW 정렬) 손목
    # 높이와 직접 비교한다. 낮은 쪽도, 기준보다 과도하게 높이 든 쪽도 이 하나로 잡힌다.
    'wrist_L':              ('two_sided', 0.15, _wrist_height_msg('왼쪽')),
    'wrist_R':              ('two_sided', 0.15, _wrist_height_msg('오른쪽')),
    # 어깨 높이차는 좌우 비교(절대 기준, 위 'asym' 설명 참고) — 기준 영상 자체가
    # 자연스럽게 흔들리는 최대폭(0.044)보다 여유를 두고 잡았다. 손목과 달리 어깨는
    # '기준 높이'라는 목표 개념이 없어(그냥 몸에 붙어있는 지점) 좌우 비교가 더 맞다.
    'shoulder_height_diff': ('asym',      0.06, _height_diff_msg('어깨')),
}

LUNGE_FAULT_RULES = {
    # 측면 (앞다리/뒷다리 역할 기반 — features.py 참고)
    # knee/hip_depth/knee_travel 허용오차는 스쿼트보다 넉넉하다: 기준 측면 영상이
    # 카메라 반대쪽(먼 쪽) 다리의 MediaPipe 인식률이 낮아(무릎 visibility 0.81,
    # 스쿼트급 0.98 대비) 그 다리가 앞다리로 잡히는 반복마다 편차가 커지는 걸
    # 확인했다(자체검증: 최대 knee +43°, knee_travel +1.00). 카메라를 정면(양다리
    # 사이) 쪽으로 옮겨 재촬영하면 더 좁혀도 된다.
    'knee':        ('high_bad', 25.0, '앞무릎을 더 굽혀 깊이 앉으세요 (런지가 얕습니다)'),
    'back_knee':   ('high_bad', 20.0, '뒷다리를 충분히 낮추지 않았습니다 (뒷무릎을 더 굽히세요)'),
    'hip_depth':   ('high_bad', 0.45, '엉덩이를 더 낮추세요 (앞허벅지가 바닥과 평행이 되도록)'),
    'trunk':       ('high_bad', 12.0, '상체가 과도하게 앞/옆으로 기울어집니다'),
    'knee_travel': ('high_bad', 0.65, '앞무릎이 앞발끝을 너무 넘어갑니다'),
    # 정면
    'valgus':      ('high_bad', 0.12, '앞무릎이 안쪽으로 모입니다 (무릎을 발끝 방향으로 미세요)'),
    'sym_hip':     ('high_bad', 0.12, '골반이 한쪽으로 기웁니다'),
}

FAULT_RULES_BY_EXERCISE = {
    'squat':         SQUAT_FAULT_RULES,
    'lateral_raise': LATERAL_RAISE_FAULT_RULES,
    'lunge':         LUNGE_FAULT_RULES,
}

# 이전 코드 호환용 별칭 (기본값 = 스쿼트 규칙)
FAULT_RULES = SQUAT_FAULT_RULES

# 운동별 국면 라벨: (하강/올리기, 극점, 상승/내리기)
PHASE_LABELS = {
    'squat':         ('하강', '최저', '상승'),
    'lateral_raise': ('올리기', '최고점', '내리기'),
    'lunge':         ('하강', '최저', '상승'),
}


def _phase(i_ref, bottom_rel, n_ref, exercise='squat'):
    """기준 인덱스가 하강/극점/상승 중 어디인지 한글 라벨로 (운동별 라벨 사용)."""
    down_label, mid_label, up_label = PHASE_LABELS.get(exercise, PHASE_LABELS['squat'])
    if abs(i_ref - bottom_rel) <= max(2, n_ref // 12):
        return mid_label
    return down_label if i_ref < bottom_rel else up_label


def judge_rep(ref_rep, user_rep, exercise='squat', rules=None, min_len=5):
    """정렬된 두 반복을 전 구간 비교하여 결함 목록을 반환한다.

    Args:
        exercise : 'squat' 또는 'lateral_raise'. rules 를 명시하지 않으면 이 값으로
                   FAULT_RULES_BY_EXERCISE 에서 규칙을 고른다.
        rules    : 판정 규칙을 직접 지정하고 싶을 때만 넘긴다(기본은 exercise 로 자동 선택).

    Returns:
        faults : [{feature, message, phase, frame_start, frame_end, max_dev}, ...]
        meta   : {'path', 'norm_dist', 'user_bottom'}
    """
    if rules is None:
        rules = FAULT_RULES_BY_EXERCISE.get(exercise, SQUAT_FAULT_RULES)
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
            if direction == 'asym':
                # 특징 자체가 부호 있는 좌우 차이 → 기준값과 비교하지 않고 사용자
                # 자신의 비대칭 크기(절대값)만으로 판정한다 (이유는 위 주석 참고 —
                # 기준의 그 순간 값과 비교하면 기준이 자연스레 흔들리는 국면에서
                # 사각지대가 생긴다).
                dev = abs(uvals[j])
                bad = dev > tol
            else:
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
                    worst_dev = float(seg_devs[np.argmax(np.abs(seg_devs))])
                    faults.append({
                        'feature': feat,
                        'message': msg(worst_dev, float(uvals[j_w]), user_rep['features'], j_w) if callable(msg) else msg,
                        'phase': _phase(irefs[mid], bottom_rel, n_ref, exercise),
                        'frame_start': user_start_f + min(seg_js),
                        'frame_end':   user_start_f + max(seg_js),
                        'max_dev': worst_dev,
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
        return "  ✅ 기준 자세와 큰 차이 없음 — 좋은 자세입니다."
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

    # ⑤ 사이드레터럴레이즈: 정상 사용자 (기준 그대로) → 결함 없어야 함
    lr_reps, _ = slice_reps("data/processed/sidelateralraise_front_features.csv",
                            "data/processed/sidelateralraise_front_landmarks_smoothed.csv",
                            exercise='lateral_raise')
    lref = lr_reps[0]
    print("\n⑤ 사이드레터럴레이즈 정상 사용자 (기준과 동일):")
    faults, _ = judge_rep(lref, copy.deepcopy(lref), exercise='lateral_raise')
    print(format_feedback(faults))

    # ⑥ 왼팔을 충분히 못 든 경우: arm_L 을 30% 낮춤 (정렬 신호는 그대로 둬 위상만 비교)
    print("\n⑥ 왼팔 낮은 거상 주입 (arm_L 30% 감소):")
    lbad = copy.deepcopy(lref)
    lbad['features']['arm_L'] = lbad['features']['arm_L'].copy() * 0.7
    faults, _ = judge_rep(lref, lbad, exercise='lateral_raise')
    print(format_feedback(faults))

    # ⑥-2 왼팔을 기준보다 너무 높이 든 경우: 최고점 부근 arm_L 을 +25° 키움
    #      (사이드레터럴레이즈는 어깨 높이 넘겨 들면 안 되므로 이것도 결함으로 잡혀야 함)
    print("\n⑥-2 왼팔 과도한 거상 주입 (최고점 구간 arm_L +25°, '높이 들어올렸습니다' 나와야 함):")
    lbad = copy.deepcopy(lref)
    b = lbad['bottom_rel']
    lbad['features']['arm_L'] = lbad['features']['arm_L'].copy()
    lbad['features']['arm_L'][max(0, b - 10):b + 10] += 25.0
    faults, _ = judge_rep(lref, lbad, exercise='lateral_raise')
    print(format_feedback(faults))

    # ⑦ 몸통 반동 주입: 최고점 부근 trunk 를 +15° 키움 (옆으로 기울며 반동 사용)
    print("\n⑦ 몸통 반동 주입 (최고점 구간 trunk +15°):")
    lbad = copy.deepcopy(lref)
    b = lbad['bottom_rel']
    lbad['features']['trunk'] = lbad['features']['trunk'].copy()
    lbad['features']['trunk'][max(0, b - 10):b + 10] += 15.0
    faults, _ = judge_rep(lref, lbad, exercise='lateral_raise')
    print(format_feedback(faults))

    # ⑧ 방향별 문구 확인: 왼쪽 팔꿈치를 많이 굽힘(−20°) vs 많이 폄(+20°)
    print("\n⑧-1 왼쪽 팔꿈치 과도하게 굽힘 주입 (elbow_L −20°, '펴세요' 나와야 함):")
    lbad = copy.deepcopy(lref)
    lbad['features']['elbow_L'] = lbad['features']['elbow_L'].copy() - 20.0
    faults, _ = judge_rep(lref, lbad, exercise='lateral_raise')
    print(format_feedback(faults))

    print("\n⑧-2 왼쪽 팔꿈치 과도하게 폄 주입 (elbow_L +20°, '구부려보세요' 나와야 함):")
    lbad = copy.deepcopy(lref)
    lbad['features']['elbow_L'] = lbad['features']['elbow_L'].copy() + 20.0
    faults, _ = judge_rep(lref, lbad, exercise='lateral_raise')
    print(format_feedback(faults))

    # ⑨ 손목 높이 vs 기준 직접 비교: 왼쪽 손목이 기준보다 처짐(y +0.3, 더 아래)
    #    → "왼쪽 손목이 모범 영상보다 낮습니다"
    print("\n⑨-1 왼쪽 손목 기준보다 처짐 주입 (wrist_L y +0.3, '낮습니다' 나와야 함):")
    lbad = copy.deepcopy(lref)
    b = lbad['bottom_rel']
    lbad['features']['wrist_L'] = lbad['features']['wrist_L'].copy()
    lbad['features']['wrist_L'][max(0, b - 10):b + 10] += 0.3
    faults, _ = judge_rep(lref, lbad, exercise='lateral_raise')
    print(format_feedback(faults))

    # ⑩ 오른쪽 손목만 기준보다 훨씬 높이 올라간 경우(왼쪽은 정상)
    #    → 이전엔(좌우 차이 기반) 반대쪽을 올리라고 잘못 나갈 수 있었지만, 이제는
    #      오른쪽 손목 자체를 기준과 비교하므로 곧바로 "오른쪽 손목이 높습니다"가 나와야 함.
    print("\n⑩ 오른쪽 손목만 기준보다 훨씬 높이 든 경우 주입 (wrist_R y −0.3, '높습니다' 나와야 함):")
    lbad = copy.deepcopy(lref)
    b = lbad['bottom_rel']
    lbad['features']['wrist_R'] = lbad['features']['wrist_R'].copy()
    lbad['features']['wrist_R'][max(0, b - 10):b + 10] -= 0.3
    faults, _ = judge_rep(lref, lbad, exercise='lateral_raise')
    print(format_feedback(faults))

    # ── 런지: 정상 사용자 + 규칙별 인위적 나쁜 자세 주입 (규칙이 실제로 발동하는지 확인) ──
    lg_side_reps, _ = slice_reps("data/processed/lunge_side_features.csv",
                                  "data/processed/lunge_side_landmarks_smoothed.csv",
                                  exercise='lunge')
    lg_ref = lg_side_reps[0]
    lg_front_reps, _ = slice_reps("data/processed/lunge_front_features.csv",
                                   "data/processed/lunge_front_landmarks_smoothed.csv",
                                   exercise='lunge')
    lg_fref = lg_front_reps[0]

    print("\n⑪ 런지 정상 사용자 (기준과 동일, 측면) → 결함 없어야 함:")
    faults, _ = judge_rep(lg_ref, copy.deepcopy(lg_ref), exercise='lunge')
    print(format_feedback(faults))

    print("\n⑫ 앞무릎 얕음 주입 (최저점 구간 knee +30°, '깊이 앉으세요' 나와야 함):")
    bad = copy.deepcopy(lg_ref)
    b = bad['bottom_rel']
    bad['features']['knee'] = bad['features']['knee'].copy()
    bad['features']['knee'][max(0, b - 8):b + 8] += 30.0
    faults, _ = judge_rep(lg_ref, bad, exercise='lunge')
    print(format_feedback(faults))

    print("\n⑬ 뒷다리 안 낮춤 주입 (최저점 구간 back_knee +30°, '뒷무릎을 더 굽히세요' 나와야 함):")
    bad = copy.deepcopy(lg_ref)
    b = bad['bottom_rel']
    bad['features']['back_knee'] = bad['features']['back_knee'].copy()
    bad['features']['back_knee'][max(0, b - 8):b + 8] += 30.0
    faults, _ = judge_rep(lg_ref, bad, exercise='lunge')
    print(format_feedback(faults))

    print("\n⑭ 엉덩이 얕음 주입 (최저점 구간 hip_depth +0.5, '엉덩이를 더 낮추세요' 나와야 함):")
    bad = copy.deepcopy(lg_ref)
    b = bad['bottom_rel']
    bad['features']['hip_depth'] = bad['features']['hip_depth'].copy()
    bad['features']['hip_depth'][max(0, b - 8):b + 8] += 0.5
    faults, _ = judge_rep(lg_ref, bad, exercise='lunge')
    print(format_feedback(faults))

    print("\n⑮ 상체 과숙임 주입 (상승 구간 trunk +20°, '앞/옆으로 기울어집니다' 나와야 함):")
    bad = copy.deepcopy(lg_ref)
    b = bad['bottom_rel']
    bad['features']['trunk'] = bad['features']['trunk'].copy()
    bad['features']['trunk'][b:] += 20.0
    faults, _ = judge_rep(lg_ref, bad, exercise='lunge')
    print(format_feedback(faults))

    print("\n⑯ 무릎 전방이동 과다 주입 (최저점 구간 knee_travel +0.8, '앞발끝을 너무 넘어갑니다' 나와야 함):")
    bad = copy.deepcopy(lg_ref)
    b = bad['bottom_rel']
    bad['features']['knee_travel'] = bad['features']['knee_travel'].copy()
    bad['features']['knee_travel'][max(0, b - 8):b + 8] += 0.8
    faults, _ = judge_rep(lg_ref, bad, exercise='lunge')
    print(format_feedback(faults))

    print("\n⑰ 런지 정면 정상 사용자 (기준과 동일) → 결함 없어야 함:")
    faults, _ = judge_rep(lg_fref, copy.deepcopy(lg_fref), exercise='lunge')
    print(format_feedback(faults))

    print("\n⑱ 정면 무릎 모임(valgus) 주입 (최저점 구간 valgus +0.3, '안쪽으로 모입니다' 나와야 함):")
    bad = copy.deepcopy(lg_fref)
    b = bad['bottom_rel']
    bad['features']['valgus'] = bad['features']['valgus'].copy()
    bad['features']['valgus'][max(0, b - 8):b + 8] += 0.3
    faults, _ = judge_rep(lg_fref, bad, exercise='lunge')
    print(format_feedback(faults))

    print("\n⑲ 정면 골반 기울임 주입 (최저점 구간 sym_hip +0.2, '골반이 한쪽으로 기웁니다' 나와야 함):")
    bad = copy.deepcopy(lg_fref)
    b = bad['bottom_rel']
    bad['features']['sym_hip'] = bad['features']['sym_hip'].copy()
    bad['features']['sym_hip'][max(0, b - 8):b + 8] += 0.2
    faults, _ = judge_rep(lg_fref, bad, exercise='lunge')
    print(format_feedback(faults))
