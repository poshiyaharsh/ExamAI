"""
Benchmark script to measure real Ollama inference performance across installed models.
Measures:
1. Cold load time
2. Prompt evaluation speed (tokens/sec)
3. Generation speed (eval tokens/sec)
Across 3 real workloads:
- 5-MCQ JSON batch
- 3-question short-answer batch
- 10-mark subjective question
"""
import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')

SAMPLE_PASSAGE = (
    "Object-Oriented Programming (OOP) is a programming paradigm based on the concept of objects, "
    "which can contain data in the form of fields (attributes) and code in the form of procedures (methods). "
    "The four fundamental pillars of OOP are Encapsulation, Abstraction, Inheritance, and Polymorphism. "
    "Encapsulation binds data and functions together into a single unit and hides the internal representation. "
    "Inheritance allows a new class to inherit attributes and methods from an existing class, promoting reusability. "
    "Polymorphism enables one interface to be used for a general class of actions, taking forms like method overloading "
    "and method overriding. Abstraction focuses on showing only essential features of an object and hiding background details."
)

WORKLOADS = {
    '5_mcq_batch': {
        'name': '5 MCQ Batch',
        'prompt': f"""Generate exactly 5 distinct multiple choice questions based ONLY on this text:
{SAMPLE_PASSAGE}

Return JSON shape:
{{
  "questions": [
    {{
      "text": "Question text?",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "A",
      "marks": 2
    }}
  ]
}}
Return JSON only.""",
        'format': 'json',
        'options': {'temperature': 0.2, 'num_predict': 700, 'num_ctx': 2048},
    },
    '3_short_answer_batch': {
        'name': '3 Short Answer Batch',
        'prompt': f"""Generate exactly 3 short-answer questions based ONLY on this text:
{SAMPLE_PASSAGE}

Return JSON shape:
{{
  "questions": [
    {{
      "text": "Question text?",
      "model_answer": "Brief 2-3 sentence answer.",
      "marks": 5
    }}
  ]
}}
Return JSON only.""",
        'format': 'json',
        'options': {'temperature': 0.2, 'num_predict': 500, 'num_ctx': 2048},
    },
    '10_mark_subjective': {
        'name': '10-Mark Subjective Model Answer',
        'prompt': f"""Explain in detail the four pillars of Object-Oriented Programming based on this text:
{SAMPLE_PASSAGE}

Provide a structured, comprehensive answer with definitions, key points, and architectural significance.
Return JSON shape:
{{
  "question": "Explain the four pillars of OOP.",
  "model_answer": "Detailed explanation...",
  "key_points": ["Point 1", "Point 2", "Point 3", "Point 4"],
  "marking_scheme": [
    {{"criterion": "Encapsulation explanation", "marks": 2.5}},
    {{"criterion": "Inheritance explanation", "marks": 2.5}},
    {{"criterion": "Polymorphism explanation", "marks": 2.5}},
    {{"criterion": "Abstraction explanation", "marks": 2.5}}
  ]
}}
Return JSON only.""",
        'format': 'json',
        'options': {'temperature': 0.2, 'num_predict': 600, 'num_ctx': 2048},
    },
}


def get_installed_tags():
    try:
        req = Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return [m['name'] for m in data.get('models', [])]
    except Exception as e:
        print(f"Error querying Ollama /api/tags: {e}")
        return []


def run_benchmark_call(model_tag, workload_cfg):
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        'model': model_tag,
        'prompt': workload_cfg['prompt'],
        'stream': False,
        'format': workload_cfg['format'],
        'options': workload_cfg['options'],
        'keep_alive': '30m',
    }
    req = Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    t0 = time.perf_counter()
    try:
        with urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        return {'error': str(exc)}
    total_duration = time.perf_counter() - t0

    eval_count = data.get('eval_count', 0)
    eval_duration_ns = data.get('eval_duration', 0)
    prompt_eval_count = data.get('prompt_eval_count', 0)
    prompt_eval_duration_ns = data.get('prompt_eval_duration', 0)
    load_duration_ns = data.get('load_duration', 0)

    eval_speed = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0
    prompt_speed = (prompt_eval_count / (prompt_eval_duration_ns / 1e9)) if prompt_eval_duration_ns > 0 else 0.0
    load_sec = load_duration_ns / 1e9

    return {
        'total_time_s': round(total_duration, 2),
        'load_time_s': round(load_sec, 2),
        'prompt_tokens': prompt_eval_count,
        'prompt_speed_tps': round(prompt_speed, 2),
        'eval_tokens': eval_count,
        'eval_speed_tps': round(eval_speed, 2),
    }


def main():
    print(f"=== OLLAMA PERFORMANCE BENCHMARK ===")
    print(f"Host: {OLLAMA_BASE_URL}")
    installed = get_installed_tags()
    print(f"Detected installed models: {installed}")
    if not installed:
        print("No models detected or Ollama unreachable. Exiting.")
        sys.exit(1)

    target_models = ['qwen2.5:3b-instruct', 'llama3.2:3b', 'phi3:mini']
    models_to_test = [m for m in target_models if m in installed]
    if not models_to_test:
        models_to_test = installed[:3]

    results = {}
    for model in models_to_test:
        print(f"\n--- Testing Model: {model} ---")
        results[model] = {}
        for wl_key, wl_cfg in WORKLOADS.items():
            print(f"Running workload: {wl_cfg['name']}...", end=' ', flush=True)
            res = run_benchmark_call(model, wl_cfg)
            if 'error' in res:
                print(f"FAILED ({res['error']})")
            else:
                print(f"Done in {res['total_time_s']}s (Eval: {res['eval_speed_tps']} tok/s, Prompt: {res['prompt_speed_tps']} tok/s)")
            results[model][wl_key] = res

    # Generate Markdown Table
    md_lines = [
        "# Real Ollama Speed Benchmark Baseline",
        f"\n**Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Ollama Host**: `{OLLAMA_BASE_URL}`\n",
        "| Model | Workload | Prompt Tokens | Prompt Speed (tok/s) | Eval Tokens | Eval Speed (tok/s) | Load Time (s) | Total Time (s) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for model, wls in results.items():
        for wl_key, res in wls.items():
            wl_name = WORKLOADS[wl_key]['name']
            if 'error' in res:
                md_lines.append(f"| `{model}` | {wl_name} | ERROR | - | - | - | - | {res.get('error', '')} |")
            else:
                md_lines.append(
                    f"| `{model}` | {wl_name} | {res['prompt_tokens']} | {res['prompt_speed_tps']} | "
                    f"{res['eval_tokens']} | {res['eval_speed_tps']} | {res['load_time_s']}s | {res['total_time_s']}s |"
                )

    report_content = "\n".join(md_lines)
    with open('perf_gen_baseline.md', 'w', encoding='utf-8') as f:
        f.write(report_content)
    print("\nBenchmark completed. Saved to perf_gen_baseline.md")

    # Save calibration speeds JSON for planner
    calibrations = {}
    for model, wls in results.items():
        speeds = [res['eval_speed_tps'] for res in wls.values() if 'eval_speed_tps' in res and res['eval_speed_tps'] > 0]
        prompt_speeds = [res['prompt_speed_tps'] for res in wls.values() if 'prompt_speed_tps' in res and res['prompt_speed_tps'] > 0]
        calibrations[model] = {
            'eval_tokens_per_sec': round(sum(speeds) / len(speeds), 2) if speeds else 15.0,
            'prompt_tokens_per_sec': round(sum(prompt_speeds) / len(prompt_speeds), 2) if prompt_speeds else 40.0,
            'calibrated_at': time.time(),
        }
    with open('model_calibration.json', 'w', encoding='utf-8') as f:
        json.dump(calibrations, f, indent=2)
    print("Saved calibrated model speeds to model_calibration.json")


if __name__ == '__main__':
    main()
