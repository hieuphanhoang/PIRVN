"""
Export fine-tuned model to GGUF format for Ollama.
Run this on Colab after fine-tuning, or locally if you have the merged model.

Usage on Colab (after fine-tuning notebook):
    !python export_gguf.py --model_path ./pirvn-pricer-merged --output ./pirvn-pricer.gguf

Usage locally:
    uv run phase4_finetune/export_gguf.py --model_path ./merged_model --output ./pirvn-pricer.gguf
"""
import argparse
import subprocess
import sys


def export(model_path: str, output: str, quantization: str = "q4_k_m"):
    print(f"Converting {model_path} to GGUF format ({quantization})...")

    try:
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(model_path)
        model.save_pretrained_gguf(output, tokenizer, quantization_method=quantization)
        print(f"Saved GGUF to {output}")
    except ImportError:
        print("Unsloth not available. Trying llama.cpp conversion...")
        cmd = [
            sys.executable, "-m", "llama_cpp.convert",
            "--outfile", output,
            "--outtype", quantization,
            model_path,
        ]
        subprocess.run(cmd, check=True)
        print(f"Saved GGUF to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--output", default="pirvn-pricer.gguf")
    parser.add_argument("--quantization", default="q4_k_m")
    args = parser.parse_args()
    export(args.model_path, args.output, args.quantization)
