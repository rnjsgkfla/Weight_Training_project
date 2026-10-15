"""
scoring.py — 판정(judge.py) 결과로 운동 자세 점수(0~100)를 계산한다.

점수는 화면의 '양호 / 고칠 점' 판정과 같은 규칙(특징별 나쁜 방향·허용오차·최소 지속 길이)에서
나온다. 그래서 점수와 판정이 어긋나지 않는다:
  80~100 : 모든 회차에서 지적 없음. 허용오차에서 멀수록(모범에 가까울수록) 100 에 가깝다.
  0~79   : 지적된 항목이 있음. 자주·크게 벗어날수록 낮다.

항목(뷰·특징 = 문제 카드 하나)별 점수 S_f:
  b_t = 그 순간 '나쁜 방향'으로 벗어난 정도 / 허용오차  (judge 와 같은 정의, 좋은 방향은 0)
  지적 없음 : S_f = 100 − 20 · m_f
              m_f = 모든 회차 대응쌍의 평균 min(b_t, 1)  (judge metrics 의 closeness)
  지적 있음 : S_f = 79 · (1 − p_f)
              p_f = ½ · (지적된 회차 / 전체 회차) + ½ · min((심각도 − 1) / 2, 1)
              심각도 = 결함 구간에서 가장 크게 벗어난 정도 / 허용오차 (문제 카드 severity 와 같음)
총점 = Σ w_f S_f   (분석한 뷰의 항목만 쓰고, 가중치는 합이 1 이 되게 다시 나눈다)
       지적이 하나라도 있으면 79 를 넘지 않는다.
       FAULT_EMPHASIS 가 있는 운동(런지)은 w_f 대신 w_f · (1 + k · p_f) 를 쓴다
       → 자주·크게 지적된 항목일수록 비중이 커져, 지적 없는 항목이 감점을 메우지 못한다.
         (지적이 없으면 p_f = 0 이라 영향 없음)

입력 rep_results: 회차마다 {'view', 'faults', 'metrics'}  (judge_rep 의 faults, meta['metrics'])
"""

# 운동별 항목 가중치 (뷰.특징 → 가중치, 운동별 합 1.00). 키는 judge 규칙의 특징과 같다.
SCORE_WEIGHTS = {
    'squat': {
        'side.knee': 0.20, 'side.hip_depth': 0.20, 'side.trunk': 0.15, 'side.knee_travel': 0.10,
        'front.valgus': 0.15, 'front.stance': 0.05, 'front.sym_knee': 0.08, 'front.sym_hip': 0.07,
    },
    # 런지는 핵심 실수(깊이·상체 숙임·뒷무릎)가 측면에서만 보여 측면 80% / 정면 20%
    'lunge': {
        'side.knee': 0.22, 'side.back_knee': 0.15, 'side.hip_depth': 0.18, 'side.trunk': 0.13,
        'side.knee_travel': 0.12,
        'front.trunk': 0.03, 'front.valgus': 0.10, 'front.sym_hip': 0.07,
    },
    'lateral_raise': {
        'front.arm_L': 0.15, 'front.arm_R': 0.15, 'front.elbow_L': 0.08, 'front.elbow_R': 0.08,
        'front.wrist_L': 0.12, 'front.wrist_R': 0.12, 'front.trunk': 0.15,
        'front.shoulder_height_diff': 0.15,
    },
}

OK_FLOOR = 80        # 지적 없는 항목·총점의 최저점
FAULT_CEIL = 79      # 지적 있는 항목·총점의 최고점
SEVERITY_SPAN = 2.0  # 심각도가 1 + 이 값(허용오차의 3배) 이상이면 심각도 감점 최대

# 지적 항목 비중 확대 k (운동별). 가장 심한 항목(p_f = 1)은 가중치가 1 + k 배가 된다.
FAULT_EMPHASIS = {'lunge': 2.0}

VIEW_KR = {'side': '측면', 'front': '정면'}


def fault_penalty(fault_reps, total_reps, severity):
    """p_f (0~1): 지적된 회차 비율과 심각도를 반씩. 지적이 없으면 0."""
    if fault_reps == 0:
        return 0.0
    return 0.5 * fault_reps / total_reps + 0.5 * min((severity - 1.0) / SEVERITY_SPAN, 1.0)


def item_score(closeness, fault_reps, total_reps, severity):
    """항목 하나의 점수 S_f (0~100). 지적 없으면 80~100, 있으면 0~79."""
    if fault_reps == 0:
        return 100.0 - (100.0 - OK_FLOOR) * closeness
    return FAULT_CEIL * (1.0 - fault_penalty(fault_reps, total_reps, severity))


def session_score(exercise, rep_results, names=None):
    """모든 회차 판정 결과 → 총점과 항목별 내역.

    Args:
        rep_results : [{'view', 'faults', 'metrics'}]  (회차마다 judge_rep 결과)
        names       : 특징 → 한글 이름 (없으면 특징 식별자를 그대로 쓴다)
    Returns:
        None (채점할 항목이 없을 때) 또는
        {'score': 0~100 실수,
         'items': [{item, view, view_kr, feature, name, weight, score,
                    fault_reps, total_reps, severity, closeness}, ...]}
        weight 는 실제 계산에 쓴 비중(지적 항목 비중 확대 포함, 합 1)이다.
    """
    names = names or {}
    acc = {}
    for r in rep_results:
        fault_sev = {}  # 이 회차에서 지적된 특징 → 가장 심했던 정도
        for f in r['faults']:
            sev = abs(f['max_dev']) / r['metrics'][f['feature']]['tol']
            fault_sev[f['feature']] = max(fault_sev.get(f['feature'], 0.0), sev)
        for feat, m in r['metrics'].items():
            a = acc.setdefault(f"{r['view']}.{feat}", {'close_sum': 0.0, 'n': 0, 'reps': 0,
                                                       'fault_reps': 0, 'severity': None})
            a['close_sum'] += m['closeness'] * m['n']
            a['n'] += m['n']
            a['reps'] += 1
            if feat in fault_sev:
                a['fault_reps'] += 1
                a['severity'] = max(a['severity'] or 0.0, fault_sev[feat])

    emphasis = FAULT_EMPHASIS.get(exercise, 0.0)
    weights = {k: w * (1.0 + emphasis * fault_penalty(acc[k]['fault_reps'], acc[k]['reps'],
                                                      acc[k]['severity']))
               for k, w in SCORE_WEIGHTS[exercise].items() if k in acc}
    total_w = sum(weights.values())
    if not total_w:
        return None

    items, score, any_fault = [], 0.0, False
    for key, w in weights.items():
        a = acc[key]
        view, feat = key.split('.', 1)
        closeness = a['close_sum'] / a['n']
        s = item_score(closeness, a['fault_reps'], a['reps'], a['severity'])
        score += (w / total_w) * s
        any_fault |= a['fault_reps'] > 0
        items.append({'item': key, 'view': view, 'view_kr': VIEW_KR[view], 'feature': feat,
                      'name': names.get(feat, feat), 'weight': round(w / total_w, 4),
                      'score': round(s, 1), 'fault_reps': a['fault_reps'],
                      'total_reps': a['reps'],
                      'severity': round(a['severity'], 2) if a['severity'] is not None else None,
                      'closeness': round(closeness, 4)})
    if any_fault:
        score = min(score, FAULT_CEIL)
    return {'score': min(max(score, 0.0), 100.0), 'items': items}
