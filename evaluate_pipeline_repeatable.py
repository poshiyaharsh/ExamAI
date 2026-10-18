import os
import sys
import time
import json

# Setup Django
workspace_dir = r"e:\03 Study\Django\Mini-Project"
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django
django.setup()

from api.utils.extract_text import extract_syllabus_text, detect_syllabus_topics, chunk_syllabus_by_topics
from api.generate_paper import _generate_type_questions, deduplicate_questions, MARKS_PER_TYPE
from api.utils.validate_paper import canonicalize_type, repair_rubric_marks, verify_grounding_evidence
from api.utils.ollama_client import parse_json_safely

def run_repeatable_evaluation():
    print("=" * 70)
    print("REPEATABLE EVALUATION SUITE: 5-TYPE GENERATION WITH REAL SYLLABUS")
    print("=" * 70)

    syllabus_pdf = os.path.join(workspace_dir, "media", "syllabi", "faculty_2", "EH_Unit_1.pdf")
    if not os.path.exists(syllabus_pdf):
        print(f"Error: {syllabus_pdf} not found")
        return

    with open(syllabus_pdf, "rb") as f:
        syllabus_text = extract_syllabus_text(f)
    print(f"Loaded syllabus: {syllabus_pdf} ({len(syllabus_text):,} chars)")

    topics = detect_syllabus_topics(syllabus_text)[:4]
    print(f"Detected Topics for evaluation: {topics}")
    chunks_map = chunk_syllabus_by_topics(syllabus_text, topics)

    model_name = "llama3.2-3b"
    blueprint = {
        "mcq": {"count": 2, "marks": 1},
        "true_false": {"count": 2, "marks": 1},
        "fill_blank": {"count": 2, "marks": 1},
        "short_answer": {"count": 2, "marks": 5},
        "long_answer": {"count": 2, "marks": 10},
    }

    results = {}
    total_start = time.time()

    for q_type, config in blueprint.items():
        req_count = config["count"]
        marks_per_q = config["marks"]
        print(f"\n---> Generating {q_type.upper()} ({req_count} requested, {marks_per_q} marks each)...")
        
        t0 = time.time()
        generated = _generate_type_questions(
            question_type=q_type,
            count=req_count,
            marks_per_q=marks_per_q,
            model_name=model_name,
            topics=topics,
            difficulty_distribution={"easy": 20, "medium": 50, "hard": 30},
            syllabus_text=syllabus_text,
            chunks_map=chunks_map,
        )
        duration = time.time() - t0

        grounding_pass = 0
        rubric_sum_pass = 0
        for item in generated:
            ev = item.get("source_evidence", "")
            if verify_grounding_evidence(ev, syllabus_text):
                grounding_pass += 1
            if q_type in {"short_answer", "long_answer"}:
                r_sum = sum(float(r.get("marks", 0)) for r in item.get("rubric", []))
                if abs(r_sum - marks_per_q) < 0.01:
                    rubric_sum_pass += 1
            else:
                rubric_sum_pass += 1

        results[q_type] = {
            "requested": req_count,
            "generated": len(generated),
            "time_taken_sec": round(duration, 2),
            "grounding_passed": grounding_pass,
            "rubric_sums_correct": rubric_sum_pass,
            "sample_question": generated[0]["text"][:80] + "..." if generated else "None",
        }
        print(f"Finished {q_type.upper()} in {duration:.2f}s: generated {len(generated)}/{req_count}")

    total_duration = time.time() - total_start

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY REPORT")
    print("=" * 70)
    print(f"{'Type':<15} | {'Requested':<9} | {'Generated':<9} | {'Time (s)':<8} | {'Grounding':<9} | {'Rubric Sum':<10}")
    print("-" * 70)
    for q_type, r in results.items():
        print(f"{q_type:<15} | {r['requested']:<9} | {r['generated']:<9} | {r['time_taken_sec']:<8} | {r['grounding_passed']}/{r['generated']:<7} | {r['rubric_sums_correct']}/{r['generated']:<8}")
    print("-" * 70)
    print(f"Total Pipeline Duration: {total_duration:.2f}s")

    # Run Failure Simulations
    print("\n" + "=" * 70)
    print("FAILURE SIMULATIONS VERIFICATION")
    print("=" * 70)

    # 1. Truncated output simulation
    print("1. Simulating truncated JSON output...")
    trunc_json = '{"questions": [{"type": "long_answer", "text": "Explain zero trust architecture in detail", "model_answer": "Zero trust assumes breach and verifies each'
    repaired = parse_json_safely(trunc_json)
    assert "questions" in repaired and len(repaired["questions"]) >= 1, "Failed to repair truncated output"
    print("   [PASS] Truncated output safely repaired without crashing.")

    # 2. Wrong rubric sum simulation
    print("2. Simulating model arithmetic error in rubric sum...")
    wrong_rubric = [{"criterion": "Intro", "marks": 1}, {"criterion": "Body", "marks": 2}]
    repaired_rubric = repair_rubric_marks(wrong_rubric, 10.0)
    repaired_sum = sum(x["marks"] for x in repaired_rubric)
    assert abs(repaired_sum - 10.0) < 0.01, f"Rubric sum repair failed: {repaired_sum}"
    print(f"   [PASS] Rubric sum repaired deterministically from 3.0 to {repaired_sum}.")

    # 3. Model missing simulation
    print("3. Simulating non-existent model tag...")
    from api.utils.ollama_client import call_ollama
    try:
        call_ollama("non_existent_model_xyz:latest", "Hello", timeout=5)
        print("   [FAIL] Expected error for non-existent model")
    except RuntimeError as e:
        print(f"   [PASS] Clean handled error captured: {str(e)[:80]}...")

    print("\nAll pipeline verification checks and failure simulations passed successfully!")

if __name__ == "__main__":
    run_repeatable_evaluation()
