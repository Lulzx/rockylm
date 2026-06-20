---
license: mit
language:
  - en
tags:
  - character
  - tiny-llm
  - text-generation
  - from-scratch
  - project-hail-mary
pipeline_tag: text-generation
---

# RockyLM — ~9M parameter character model

A tiny transformer trained from scratch that talks like **Rocky**, the Eridian
alien from *Project Hail Mary*. Forked from
[GuppyLM](https://github.com/arman-bd/guppylm) — same recipe, different soul.

Rocky's voice: tags questions with the literal word **"question?"**, repeats
words three times for emotion (**"good good good"**), refers to himself as
**"rocky"** and to you as **"grace"**, drops articles, and reasons about science
in blunt cause→effect clauses. He is a blind engineer, not a simpleton.

```
You> hi rocky
Rocky> hello grace friend. rocky happy you here. good good good.

You> what is astrophage
Rocky> astrophage eat star heat. star get cold. star sick.

You> let's make peace
Rocky> what mean make peace. question. rocky understand science. rocky not understand this.

You> you don't have to do this
Rocky> grace say grace will die. rocky fix. grace go home. no argue. rocky decide.
```

## Architecture

| | |
|---|---|
| Parameters | ~8.7M |
| Layers / dim / heads | 6 / 384 / 6 |
| FFN | 768 (ReLU) |
| Vocab | 4,096 (BPE) |
| Max sequence | 128 tokens |

Vanilla transformer. The character is in the data, not the architecture.

## Usage

```python
from rockylm.inference import RockyInference
engine = RockyInference('checkpoints/best_model.pt', 'data/tokenizer.json')
r = engine.chat_completion([{'role': 'user', 'content': 'hi rocky'}])
print(r['choices'][0]['message']['content'])
```

Optional TTS speaks replies in Rocky's recorded/cloned voice — see the repo.

## Links

- **Repo:** [github.com/arman-bd/guppylm](https://github.com/arman-bd/guppylm) (base recipe)
- **Style spec:** STYLE.md in the project
- Rocky is Andy Weir's character; this is a non-commercial fan project.
