# Real Ollama Speed Benchmark Baseline

**Timestamp**: 2026-10-24 18:45:17
**Ollama Host**: `http://127.0.0.1:11434`

| Model | Workload | Prompt Tokens | Prompt Speed (tok/s) | Eval Tokens | Eval Speed (tok/s) | Load Time (s) | Total Time (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `qwen2.5:3b-instruct` | 5 MCQ Batch | 247 | 485.55 | 277 | 17.76 | 4.99s | 21.14s |
| `qwen2.5:3b-instruct` | 3 Short Answer Batch | 236 | 589.47 | 197 | 17.8 | 0.02s | 11.54s |
| `qwen2.5:3b-instruct` | 10-Mark Subjective Model Answer | 347 | 477.34 | 600 | 17.67 | 0.02s | 34.76s |
| `llama3.2:3b` | 5 MCQ Batch | 243 | 490.56 | 227 | 18.86 | 4.82s | 17.38s |
| `llama3.2:3b` | 3 Short Answer Batch | 232 | 437.27 | 169 | 18.9 | 0.04s | 9.58s |
| `llama3.2:3b` | 10-Mark Subjective Model Answer | 343 | 462.32 | 502 | 18.74 | 0.02s | 27.62s |
| `phi3:mini` | 5 MCQ Batch | 259 | 25.64 | 480 | 9.64 | 4.4s | 64.34s |
| `phi3:mini` | 3 Short Answer Batch | 250 | 441.75 | 213 | 9.76 | 0.02s | 22.57s |
| `phi3:mini` | 10-Mark Subjective Model Answer | 379 | 392.55 | 600 | 9.02 | 0.01s | 67.57s |