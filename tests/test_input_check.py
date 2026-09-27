"""사람이 아니거나 전신이 안 보이는 영상을 분석 전에 거르는지 확인."""
import csv

import cv2
import numpy as np
import pytest

from conftest import require_reference
from analyze import PoseInputError, analyze_for_ui, check_pose_input, REFERENCE


def write_landmarks(path, frames):
    """frames: 프레임마다 33개 관절의 visibility 리스트(None 이면 미검출 프레임)."""
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['frame_number'] + [f'{c}{j}' for j in range(33) for c in 'xyzv'])
        for i, vis in enumerate(frames, 1):
            if vis is None:
                w.writerow([i] + [''] * (33 * 4))
            else:
                w.writerow([i] + [v for j in range(33) for v in (0.5, 0.5, 0.0, vis[j])])


def test_no_person_is_rejected(tmp_path):
    p = tmp_path / 'lm.csv'
    write_landmarks(p, [None] * 8 + [[0.9] * 33] * 2)  # 인식률 20%
    with pytest.raises(PoseInputError, match='사람을 찾지 못했어요'):
        check_pose_input(p, 'squat')


def test_missing_legs_is_rejected(tmp_path):
    vis = [0.95] * 33
    for j in (27, 28):  # 양쪽 발목이 화면 밖
        vis[j] = 0.05
    p = tmp_path / 'lm.csv'
    write_landmarks(p, [vis] * 10)
    with pytest.raises(PoseInputError, match='몸이 화면에 다 나오지 않았어요'):
        check_pose_input(p, 'squat')


def test_one_side_hidden_is_ok(tmp_path):
    # 측면 촬영: 반대쪽 팔다리(짝수 번호 쪽)가 가려져도 통과해야 한다
    vis = [0.95] * 33
    for j in (12, 14, 16, 24, 26, 28):
        vis[j] = 0.1
    p = tmp_path / 'lm.csv'
    write_landmarks(p, [vis] * 10)
    check_pose_input(p, 'squat')


def test_lateral_raise_does_not_need_legs(tmp_path):
    vis = [0.95] * 33
    for j in (25, 26, 27, 28):  # 무릎·발목 없이 상체만
        vis[j] = 0.05
    p = tmp_path / 'lm.csv'
    write_landmarks(p, [vis] * 10)
    check_pose_input(p, 'lateral_raise')


def test_upper_body_only_video_gets_no_score(tmp_path):
    """상반신만 찍힌 영상: 예전엔 다리를 지어내 반복 6회·75점이 나왔다."""
    require_reference(*REFERENCE['squat']['side'])
    cap = cv2.VideoCapture('data/raw/user_squat_side_raw.mp4')
    fps = cap.get(cv2.CAP_PROP_FPS)
    video = str(tmp_path / 'upper.mp4')
    out = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.resize(frame, (960, 540))[:243]  # 위쪽 45% (상반신)
        if out is None:
            out = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*'mp4v'), fps,
                                  (frame.shape[1], frame.shape[0]))
        out.write(frame)
    out.release()

    items, summary, stats = analyze_for_ui('squat', video, None, workdir=str(tmp_path / 'work'))
    assert items == []
    assert stats['score'] is None
    assert '몸이 화면에 다 나오지 않았어요' in summary
    assert stats['warnings'] == [
        '측면: 몸이 화면에 다 나오지 않았어요. 머리부터 발끝까지 모두 보이게 찍어주세요.']


def test_no_person_video_message(tmp_path):
    require_reference(*REFERENCE['squat']['side'])
    video = str(tmp_path / 'circle.mp4')
    out = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*'mp4v'), 30, (640, 360))
    for i in range(90):
        img = np.full((360, 640, 3), 200, np.uint8)
        cv2.circle(img, (320 + int(150 * np.sin(i / 10)), 180), 50, (40, 120, 220), -1)
        out.write(img)
    out.release()

    items, summary, stats = analyze_for_ui('squat', video, None, workdir=str(tmp_path / 'work'))
    assert items == [] and stats['score'] is None
    assert '사람을 찾지 못했어요' in summary
