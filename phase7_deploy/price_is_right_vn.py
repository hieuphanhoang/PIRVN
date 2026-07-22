"""
PIRVN — "Gia Dung Roi" Vietnamese Deal Hunter
Main Gradio application.

    cd PIRVN && uv run phase7_deploy/price_is_right_vn.py
"""
import sys
import logging
import queue
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gradio as gr
import plotly.graph_objects as go
from dotenv import load_dotenv

from phase7_deploy.deal_agent_framework import DealAgentFramework
from phase7_deploy.log_utils import reformat
from shared.currency import format_vnd

load_dotenv(override=True)


class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


def html_for(log_data):
    output = "<br>".join(log_data[-18:])
    return f"""
    <div id="scrollContent" style="height: 400px; overflow-y: auto; border: 1px solid #ccc; background-color: #222229; padding: 10px;">
    {output}
    </div>
    """


def setup_logging(log_queue):
    handler = QueueHandler(log_queue)
    formatter = logging.Formatter(
        "[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class App:
    def __init__(self):
        self.agent_framework = None

    def get_agent_framework(self):
        if not self.agent_framework:
            self.agent_framework = DealAgentFramework()
        return self.agent_framework

    def run(self):
        with gr.Blocks(title="Price Is Right- PIRVN", fill_width=True) as ui:
            log_data = gr.State([])

            def table_for(opps):
                return [
                    [
                        opp.deal.product_description,
                        format_vnd(opp.deal.price),
                        format_vnd(opp.estimate),
                        format_vnd(opp.discount),
                        opp.deal.url,
                    ]
                    for opp in opps
                ]

            def update_output(log_data, log_queue, result_queue):
                initial_result = table_for(self.get_agent_framework().memory)
                final_result = None
                while True:
                    try:
                        message = log_queue.get_nowait()
                        log_data.append(reformat(message))
                        yield log_data, html_for(log_data), final_result or initial_result
                    except queue.Empty:
                        try:
                            final_result = result_queue.get_nowait()
                            yield log_data, html_for(log_data), final_result or initial_result
                        except queue.Empty:
                            if final_result is not None:
                                break
                            time.sleep(0.1)

            def get_plot():
                try:
                    documents, vectors, colors = DealAgentFramework.get_plot_data(max_datapoints=800)
                    fig = go.Figure(
                        data=[
                            go.Scatter3d(
                                x=vectors[:, 0],
                                y=vectors[:, 1],
                                z=vectors[:, 2],
                                mode="markers",
                                marker=dict(size=2, color=colors, opacity=0.7),
                            )
                        ]
                    )
                    fig.update_layout(
                        scene=dict(
                            xaxis_title="x", yaxis_title="y", zaxis_title="z",
                            aspectmode="manual",
                            aspectratio=dict(x=2.2, y=2.2, z=1),
                            camera=dict(eye=dict(x=1.6, y=1.6, z=0.8)),
                        ),
                        height=400,
                        margin=dict(r=5, b=1, l=5, t=2),
                    )
                    return fig
                except Exception:
                    fig = go.Figure()
                    fig.update_layout(title="Vector DB loading...", height=400)
                    return fig

            def do_run():
                new_opportunities = self.get_agent_framework().run()
                return table_for(new_opportunities)

            def run_with_logging(initial_log_data):
                log_queue = queue.Queue()
                result_queue = queue.Queue()
                setup_logging(log_queue)

                def worker():
                    result = do_run()
                    result_queue.put(result)

                thread = threading.Thread(target=worker)
                thread.start()

                for ld, output, final_result in update_output(
                    initial_log_data, log_queue, result_queue
                ):
                    yield ld, output, final_result

            with gr.Row():
                gr.Markdown(
                    '<div style="text-align: center;font-size:24px">'
                    '<strong>Gia Dung Roi</strong> — Vietnamese Deal Hunter (PIRVN)'
                    '</div>'
                )
            with gr.Row():
                gr.Markdown(
                    '<div style="text-align: center;font-size:14px">'
                    'Autonomous agent framework: fine-tuned LLM on HuggingFace Spaces + RAG pipeline with ChromaDB'
                    '</div>'
                )
            with gr.Row():
                scan_btn = gr.Button("Scan Now", variant="primary", scale=0)
            with gr.Row():
                opportunities_dataframe = gr.Dataframe(
                    headers=["Mo ta san pham", "Gia ban (VND)", "Gia uoc tinh (VND)", "Giam (VND)", "URL"],
                    wrap=True,
                    column_widths=[6, 1, 1, 1, 3],
                    row_count=10,
                    col_count=5,
                    max_height=400,
                )
            with gr.Row():
                with gr.Column(scale=1):
                    logs = gr.HTML()
                with gr.Column(scale=1):
                    plot = gr.Plot(value=get_plot(), show_label=False)

            ui.load(
                run_with_logging,
                inputs=[log_data],
                outputs=[log_data, logs, opportunities_dataframe],
            )

            scan_btn.click(
                run_with_logging,
                inputs=[log_data],
                outputs=[log_data, logs, opportunities_dataframe],
            )

        ui.launch(share=False, inbrowser=True)


if __name__ == "__main__":
    App().run()
