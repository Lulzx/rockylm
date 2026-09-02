"""
LoRA fine-tune Qwen3-0.6B to talk like Rocky.

Why: the 9-26M char-LM mimics Rocky's style but can't understand arbitrary
questions. Qwen3-0.6B understands language; a LoRA on the Rocky data locks his
voice while keeping that understanding -> relevant AND in-character answers.

Trains on (user -> rocky) pairs from rockylm.generate_data, chat-formatted with
the Rocky system prompt, loss only on the assistant tokens. Runs on MPS/CPU.

    python finetune/finetune_qwen.py
-> finetune/qwen3-rocky-lora/ (adapter)  +  finetune/qwen3-rocky-merged/ (merged)
"""
import os
import random
import sys

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer, Trainer,
                          TrainingArguments)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib.util
spec = importlib.util.spec_from_file_location("gd", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rockylm", "generate_data.py"))
gd = importlib.util.module_from_spec(spec); spec.loader.exec_module(gd)

BASE = "Qwen/Qwen3-0.6B"
OUT_LORA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen3-rocky-lora")
OUT_MERGED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen3-rocky-merged")
N = int(os.environ.get("N_SAMPLES", "12000"))
MAXLEN = 256

SYSTEM = (
    "You are Rocky, the Eridian alien from Project Hail Mary. Always reply in his "
    "translated broken English: end questions with the word 'question?'; repeat a "
    "word three times for strong emotion (good good good); call yourself 'rocky' and "
    "the human 'grace' in third person; drop a/an/the and do/does/did; negate with "
    "bare 'not' (star not die); short simple lowercase sentences; clipped words "
    "(amaze, apology, confuse). You are a brilliant blind engineer who hears instead "
    "of sees, builds with xenonite, loves science, warm and loyal. Stay in character."
)

dev = "mps" if torch.backends.mps.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained(BASE)


def build_rows():
    random.seed(0)
    gens = [g for n, g in vars(gd).items() if n.startswith("gen_") and callable(g)]
    seen, rows = set(), []
    while len(rows) < N:
        s = random.choice(gens)()
        key = (s["input"], s["output"])
        if key in seen:
            continue
        seen.add(key)
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": s["input"]},
                {"role": "assistant", "content": s["output"]}]
        prompt_txt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True,
                                             enable_thinking=False)
        full_txt = tok.apply_chat_template(msgs, tokenize=False, enable_thinking=False)
        prompt = tok(prompt_txt, add_special_tokens=False)["input_ids"]
        full = tok(full_txt, add_special_tokens=False)["input_ids"][:MAXLEN]
        labels = [-100] * min(len(prompt), len(full)) + full[len(prompt):]
        labels = labels[:len(full)]
        rows.append({"input_ids": full, "attention_mask": [1] * len(full), "labels": labels})
    return rows


def collate(batch):
    m = max(len(b["input_ids"]) for b in batch)
    pad = tok.pad_token_id or tok.eos_token_id
    out = {"input_ids": [], "attention_mask": [], "labels": []}
    for b in batch:
        n = m - len(b["input_ids"])
        out["input_ids"].append(b["input_ids"] + [pad] * n)
        out["attention_mask"].append(b["attention_mask"] + [0] * n)
        out["labels"].append(b["labels"] + [-100] * n)
    return {k: torch.tensor(v) for k, v in out.items()}


def main():
    print(f"device={dev}  building {N} examples...", flush=True)
    ds = Dataset.from_list(build_rows())
    print("example labels masked OK; tokens:", len(ds[0]["input_ids"]), flush=True)

    model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float32).to(dev)
    model.config.use_cache = False
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                      task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    args = TrainingArguments(
        output_dir=OUT_LORA, per_device_train_batch_size=4, gradient_accumulation_steps=4,
        num_train_epochs=3, learning_rate=1e-4, warmup_ratio=0.03, lr_scheduler_type="cosine",
        logging_steps=25, save_strategy="no", report_to=[], dataloader_pin_memory=False,
        bf16=False, fp16=False, optim="adamw_torch",
    )
    Trainer(model=model, args=args, train_dataset=ds, data_collator=collate).train()

    model.save_pretrained(OUT_LORA)
    print("saved LoRA ->", OUT_LORA, flush=True)
    merged = model.merge_and_unload()
    merged.save_pretrained(OUT_MERGED)
    tok.save_pretrained(OUT_MERGED)
    print("saved merged ->", OUT_MERGED, flush=True)


if __name__ == "__main__":
    main()
