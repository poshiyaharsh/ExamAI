import json
import time
import urllib.request
import sys
from typing import Dict, Any

# Ensure console supports full Unicode
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

LANGUAGES = [
    {"name": "English", "code": "en", "script": "Latin"},
    {"name": "Hindi", "code": "hi", "script": "Devanagari"},
    {"name": "Gujarati", "code": "gu", "script": "Gujarati"},
    {"name": "Marathi", "code": "mr", "script": "Devanagari"},
    {"name": "Tamil", "code": "ta", "script": "Tamil"},
    {"name": "Bengali", "code": "bn", "script": "Bengali"},
    {"name": "Urdu", "code": "ur", "script": "Arabic"},
    {"name": "Arabic", "code": "ar", "script": "Arabic"},
    {"name": "French", "code": "fr", "script": "Latin"},
    {"name": "Spanish", "code": "es", "script": "Latin"},
    {"name": "German", "code": "de", "script": "Latin"},
    {"name": "Chinese", "code": "zh", "script": "Simplified Chinese"},
    {"name": "Japanese", "code": "ja", "script": "Japanese (Kanji/Kana)"},
]

MODELS = ["qwen3:4b", "gemma3:4b", "llama3.2:3b", "granite3.3:2b"]

def test_prompt(model: str, lang: Dict[str, str]) -> Dict[str, Any]:
    prompt = (
        f"/no_think\n"
        f"Write exactly one multiple-choice question with 4 options and the correct answer about photosynthesis in {lang['name']}. "
        f"You MUST write in {lang['name']} using {lang['script']} script. Do not write in English. "
        f"Return only JSON with keys: question, options, answer."
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": 250,
            "num_ctx": 2048
        }
    }
    t0 = time.time()
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            response_text = data.get("response", "")
            eval_count = data.get("eval_count", 0)
            tps = eval_count / elapsed if elapsed > 0 else 0
            return {
                "success": True,
                "elapsed": elapsed,
                "tps": tps,
                "tokens": eval_count,
                "output": response_text
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

results = {}
for lang in LANGUAGES:
    results[lang["code"]] = {}
    print(f"\n--- Testing Language: {lang['name']} ({lang['code']}) ---")
    for model in MODELS:
        res = test_prompt(model, lang)
        if res.get("success"):
            sample = res["output"].strip().replace("\n", " ")[:90]
            print(f"  [{model:14}] {res['tps']:4.1f} tps | {res['tokens']} tok | {sample}...")
            results[lang["code"]][model] = {
                "tps": round(res["tps"], 1),
                "tokens": res["tokens"],
                "sample": res["output"].strip()
            }
        else:
            print(f"  [{model:14}] FAILED: {res.get('error')}")
            results[lang["code"]][model] = {"error": res.get("error")}

with open("scripts/probe_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nProbe complete! Saved to scripts/probe_results.json")
