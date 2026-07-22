"""
HuggingFace Spaces app for the PIRVN Specialist Agent.
Serves the fine-tuned price prediction model as a Gradio API.

Deploy by pushing this folder to a HuggingFace Space.
"""
import re
import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

MODEL_NAME = "your-username/pirvn-pricer"

print("Loading model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float16,
    device_map="auto",
)
print("Model loaded.")

SYSTEM_MSG = "You are a Vietnamese product price estimator. Respond with only the price number in VND."


def predict_price(description: str) -> float:
    messages = [
        {"role": "system", "content": SYSTEM_MSG},
        {"role": "user", "content": f"San pham nay gia bao nhieu (VND)?\n\n{description}"},
    ]
    inputs = tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True)
    inputs = inputs.to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            inputs,
            max_new_tokens=32,
            temperature=0.1,
            do_sample=False,
        )

    response = tokenizer.decode(outputs[0][inputs.shape[-1]:], skip_special_tokens=True)
    cleaned = response.replace(",", "").replace(".", "").replace(" ", "")
    cleaned = cleaned.replace("VND", "").replace("₫", "")
    match = re.search(r"\d+", cleaned)
    return float(match.group()) if match else 0.0


iface = gr.Interface(
    fn=predict_price,
    inputs=gr.Textbox(label="Product Description", lines=5, placeholder="Nhap mo ta san pham..."),
    outputs=gr.Number(label="Predicted Price (VND)"),
    title="PIRVN Price Predictor",
    description="Fine-tuned model for Vietnamese product price estimation",
)

if __name__ == "__main__":
    iface.launch()
