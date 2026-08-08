"""
app.py — 운동 자세 피드백 웹 UI (Gradio)

운동을 고르고 영상을 올리면 기준 자세와 비교해 반복별 '피드백 항목'을 만들고,
항목을 클릭하면 모범 영상과 내 영상의 해당 순간을 나란히 비교해 보여준다.

지원 운동:
  - 스쿼트           : 측면·정면 영상 사용
  - 사이드 레터럴 레이즈 : 정면 영상만 사용

실행:  ./venv/bin/python app.py   → 브라우저에서 http://127.0.0.1:7860 접속
"""

import gradio as gr
from analyze import analyze_for_ui, frame_at, REFERENCE, EXERCISE_KR

EMPTY_DETAIL = "왼쪽에서 피드백 항목을 선택하면 여기에 비교가 표시됩니다."

EXERCISE_LABELS = {ex_key: kr for ex_key, kr in EXERCISE_KR.items()}
LABEL_TO_EXERCISE = {kr: ex_key for ex_key, kr in EXERCISE_KR.items()}
DEFAULT_LABEL = EXERCISE_KR['squat']


def run(exercise_label, side_video, front_video):
    """분석 실행 → 요약, 항목 선택지, 상태, 그리고 첫 항목 비교를 반환."""
    exercise = LABEL_TO_EXERCISE[exercise_label]
    views = REFERENCE[exercise]
    if 'side' not in views:
        side_video = None  # 이 운동은 측면을 쓰지 않음
    if not side_video and not front_video:
        return ("⚠️ 영상을 하나 이상 올려주세요.",
                gr.update(choices=[], value=None), [], None, None, EMPTY_DETAIL)

    items, summary = analyze_for_ui(exercise, side_video, front_video)
    # 선택지는 (표시 라벨, 내부 key) 쌍으로 준다 — 라벨 문구가 우연히 같아도
    # Radio 가 실제로 고르는 값은 항상 고유한 key 라 선택이 절대 겹치지 않는다.
    choices = [(it['label'], it['key']) for it in items]
    if not items:
        return summary, gr.update(choices=[], value=None), [], None, None, EMPTY_DETAIL

    first = items[0]
    ref_img = frame_at(first['ref_video'], first['ref_frame'])
    user_img = frame_at(first['user_video'], first['user_frame'])
    return (summary,
            gr.update(choices=choices, value=first['key']),
            items, ref_img, user_img, first['detail'])


def show_item(key, items):
    """선택된 항목의 모범/내 영상 프레임과 상세를 표시."""
    it = next((x for x in (items or []) if x['key'] == key), None)
    if not it:
        return None, None, EMPTY_DETAIL
    ref_img = frame_at(it['ref_video'], it['ref_frame'])
    user_img = frame_at(it['user_video'], it['user_frame'])
    return ref_img, user_img, it['detail']


def on_exercise_change(exercise_label):
    """운동 선택에 따라 측면 영상 입력을 보여줄지 결정 (사이드레터럴레이즈는 정면만)."""
    exercise = LABEL_TO_EXERCISE[exercise_label]
    show_side = 'side' in REFERENCE[exercise]
    return gr.update(visible=show_side)


with gr.Blocks(title="운동 자세 피드백") as demo:
    gr.Markdown("# 🏋️ 운동 자세 피드백\n"
                "운동을 고르고 영상을 올리면 기준 자세와 비교해 피드백을 줍니다.")

    exercise_select = gr.Radio(label="운동 선택", choices=list(EXERCISE_KR.values()),
                                value=DEFAULT_LABEL)
    gr.Markdown("측면·정면 세트를 따로 찍어 각각 올리세요(휴대폰 1대라면). "
                "사이드 레터럴 레이즈는 정면 영상만 사용합니다.")

    with gr.Row():
        side_in = gr.Video(label="측면 영상")
        front_in = gr.Video(label="정면 영상")
    run_btn = gr.Button("분석하기", variant="primary")

    summary_md = gr.Markdown()

    with gr.Row():
        with gr.Column(scale=1):
            selector = gr.Radio(label="피드백 항목 (클릭해서 비교)", choices=[])
        with gr.Column(scale=2):
            with gr.Row():
                ref_img = gr.Image(label="✅ 모범 자세", height=360)
                user_img = gr.Image(label="🙋 내 자세", height=360)
            detail_md = gr.Markdown(EMPTY_DETAIL)

    items_state = gr.State([])

    exercise_select.change(
        on_exercise_change,
        inputs=[exercise_select],
        outputs=[side_in],
    )
    run_btn.click(
        run,
        inputs=[exercise_select, side_in, front_in],
        outputs=[summary_md, selector, items_state, ref_img, user_img, detail_md],
    )
    selector.change(
        show_item,
        inputs=[selector, items_state],
        outputs=[ref_img, user_img, detail_md],
    )


if __name__ == "__main__":
    demo.launch()
