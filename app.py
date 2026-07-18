"""
app.py — 스쿼트 자세 피드백 웹 UI (Gradio)

측면·정면 영상을 올리면 기준 자세와 비교해 반복별 '피드백 항목'을 만들고,
항목을 클릭하면 모범 영상과 내 영상의 해당 순간을 나란히 비교해 보여준다.

실행:  ./venv/bin/python app.py   → 브라우저에서 http://127.0.0.1:7860 접속
"""

import gradio as gr
from analyze import analyze_for_ui, frame_at

EMPTY_DETAIL = "왼쪽에서 피드백 항목을 선택하면 여기에 비교가 표시됩니다."


def run(side_video, front_video):
    """분석 실행 → 요약, 항목 선택지, 상태, 그리고 첫 항목 비교를 반환."""
    if not side_video and not front_video:
        return ("⚠️ 측면 또는 정면 영상을 하나 이상 올려주세요.",
                gr.update(choices=[], value=None), [], None, None, EMPTY_DETAIL)

    items, summary = analyze_for_ui(side_video, front_video)
    labels = [it['label'] for it in items]
    if not items:
        return summary, gr.update(choices=[], value=None), [], None, None, EMPTY_DETAIL

    first = items[0]
    ref_img = frame_at(first['ref_video'], first['ref_frame'])
    user_img = frame_at(first['user_video'], first['user_frame'])
    return (summary,
            gr.update(choices=labels, value=labels[0]),
            items, ref_img, user_img, first['detail'])


def show_item(label, items):
    """선택된 항목의 모범/내 영상 프레임과 상세를 표시."""
    it = next((x for x in (items or []) if x['label'] == label), None)
    if not it:
        return None, None, EMPTY_DETAIL
    ref_img = frame_at(it['ref_video'], it['ref_frame'])
    user_img = frame_at(it['user_video'], it['user_frame'])
    return ref_img, user_img, it['detail']


with gr.Blocks(title="스쿼트 자세 피드백") as demo:
    gr.Markdown("# 🏋️ 스쿼트 자세 피드백\n"
                "측면·정면 스쿼트 영상을 올리면 기준 자세와 비교해 피드백을 줍니다. "
                "(휴대폰 1대라면 측면·정면 세트를 따로 찍어 각각 올리세요. 둘 중 하나만 올려도 됩니다.)")

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

    run_btn.click(
        run,
        inputs=[side_in, front_in],
        outputs=[summary_md, selector, items_state, ref_img, user_img, detail_md],
    )
    selector.change(
        show_item,
        inputs=[selector, items_state],
        outputs=[ref_img, user_img, detail_md],
    )


if __name__ == "__main__":
    demo.launch()
