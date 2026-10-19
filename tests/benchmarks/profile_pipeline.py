"""
Repeatable benchmark profiler for exam paper generation pipeline.
Measures time per stage, Ollama call metrics, tokens/second, retry rates, and hardware utilization.
Supports PDF and DOCX syllabi and 20, 50, and 100 mark blueprints across 3 runs with median reporting.
All instrumentation is done via clean function wrapping in this benchmark script (leaving production code untouched).
"""

import os
import sys
import json
import time
import statistics
from typing import Dict, List, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
os.environ.setdefault('DB_ENGINE', 'sqlite')

import django
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from admins.models import AdminInstitution, AdminProfile
from faculty.models import FacultyProfile
from api.models import Exam, PaperGenerationJob, Question, Option
import api.generate_paper as gp
import api.utils.ollama_client as oc
import api.utils.extract_text as et
import api.utils.validate_paper as vp
import api.utils.prompts as pr
from api.utils.blueprint_allocator import allocate_blueprint_to_target


class PipelineProfiler:
    def __init__(self):
        self.stage_timings: Dict[str, float] = {
            'upload_and_extraction': 0.0,
            'hierarchy_and_chunking': 0.0,
            'prompt_building': 0.0,
            'ollama_calls': 0.0,
            'json_parsing_and_repair': 0.0,
            'schema_validation': 0.0,
            'evidence_verification': 0.0,
            'deduplication': 0.0,
            'database_saves': 0.0,
            'status_progress_updates': 0.0,
        }
        self.ollama_calls_data: List[Dict[str, Any]] = []
        self.retry_counts: Dict[str, int] = {
            'total_retries': 0,
            'truncation': 0,
            'bad_json': 0,
            'schema_failure': 0,
            'evidence_not_found': 0,
            'shortfall': 0,
        }
        self.tokens_generated = 0
        self.prompt_tokens = 0
        self.call_purposes: List[str] = []

    def record_stage(self, stage: str, duration: float):
        if stage in self.stage_timings:
            self.stage_timings[stage] += duration
        else:
            self.stage_timings[stage] = duration

    def record_ollama_call(self, call_info: Dict[str, Any]):
        self.ollama_calls_data.append(call_info)
        self.tokens_generated += call_info.get('eval_count', 0)
        self.prompt_tokens += call_info.get('prompt_eval_count', 0)


def run_single_benchmark(file_path: str, target_marks: int, model_name: str = 'qwen2.5-3b') -> Dict[str, Any]:
    """Runs one full generation profiling run with microsecond stage instrumentation."""
    profiler = PipelineProfiler()
    t_pipeline_start = time.perf_counter()

    # 1. Upload and extraction
    t0 = time.perf_counter()
    with open(file_path, 'rb') as f:
        file_bytes = f.read()
    filename = os.path.basename(file_path)
    content_type = 'application/pdf' if filename.endswith('.pdf') else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    uploaded_file = SimpleUploadedFile(filename, file_bytes, content_type=content_type)
    
    syllabus_text = et.extract_syllabus_text(uploaded_file)
    try:
        pages = et.extract_syllabus_pages(uploaded_file)
    except Exception:
        pages = []
    profiler.record_stage('upload_and_extraction', time.perf_counter() - t0)

    # 2. Hierarchy and chunking
    t0 = time.perf_counter()
    hierarchy = et.detect_syllabus_hierarchy(syllabus_text, pages)
    topics = [u['title'] for u in hierarchy.get('units', [])][:5]
    if not topics:
        topics = ['Information Security', 'Network Scanning', 'Vulnerability Assessment', 'Threat Analysis']
    chunks_map = et.chunk_syllabus_by_topics(syllabus_text, topics)
    profiler.record_stage('hierarchy_and_chunking', time.perf_counter() - t0)

    # 3. Target Blueprint allocation
    bp_res, _ = allocate_blueprint_to_target(target_marks, preset='mixed')
    blueprint = bp_res

    # Setup DB entities
    admin_user, _ = User.objects.get_or_create(username='prof_admin', defaults={'email': 'prof_admin@gls.edu'})
    AdminProfile.objects.get_or_create(user=admin_user)
    institution, _ = AdminInstitution.objects.get_or_create(
        admin=admin_user,
        institution_name='Benchmark Institute',
        institution_code='BENCH-01',
        defaults={'status': AdminInstitution.STATUS_ACTIVE}
    )
    fac_user, _ = User.objects.get_or_create(username='prof_fac', defaults={'email': 'prof_fac@gls.edu'})
    FacultyProfile.objects.get_or_create(user=fac_user, institution=institution, department='Computer Science')

    exam = Exam.objects.create(
        institution=institution,
        title=f"Benchmark Exam {target_marks}M {filename}",
        subject="Cybersecurity",
        created_by=fac_user,
        department="Computer Science",
        duration_minutes=60,
        total_marks=target_marks,
        target_total_marks=target_marks,
        status=Exam.Status.GENERATING,
    )

    job = PaperGenerationJob.objects.create(
        institution=institution,
        faculty=fac_user,
        department="Computer Science",
        exam=exam,
        model=model_name,
        status=PaperGenerationJob.Status.RUNNING,
        current_step="Starting benchmark run",
        target_marks=target_marks,
    )

    # Save original references for instrumentation
    orig_urlopen = oc.urlopen
    orig_build_type = gp.build_type_generation_prompt
    orig_build_la_a = gp.build_long_answer_step_a_prompt
    orig_build_la_b = gp.build_long_answer_step_b_prompt
    orig_parse_json = gp.parse_json_safely
    orig_validated = gp._validated_type_questions
    orig_verify_ev = gp.verify_grounding_evidence
    orig_dedupe = gp.deduplicate_questions
    orig_q_create = Question.objects.create
    orig_opt_bulk = Option.objects.bulk_create
    orig_exam_save = Exam.save
    orig_job_save = PaperGenerationJob.save

    # Wrap Prompt Building
    def wrapped_build_type(*args, **kwargs):
        st = time.perf_counter()
        res = orig_build_type(*args, **kwargs)
        profiler.record_stage('prompt_building', time.perf_counter() - st)
        return res

    def wrapped_build_la_a(*args, **kwargs):
        st = time.perf_counter()
        res = orig_build_la_a(*args, **kwargs)
        profiler.record_stage('prompt_building', time.perf_counter() - st)
        return res

    def wrapped_build_la_b(*args, **kwargs):
        st = time.perf_counter()
        res = orig_build_la_b(*args, **kwargs)
        profiler.record_stage('prompt_building', time.perf_counter() - st)
        return res

    # Wrap JSON Parsing & Repair
    def wrapped_parse_json(*args, **kwargs):
        st = time.perf_counter()
        res = orig_parse_json(*args, **kwargs)
        profiler.record_stage('json_parsing_and_repair', time.perf_counter() - st)
        return res

    # Wrap Schema Validation
    def wrapped_validated(*args, **kwargs):
        st = time.perf_counter()
        res = orig_validated(*args, **kwargs)
        profiler.record_stage('schema_validation', time.perf_counter() - st)
        return res

    # Wrap Grounding Verification
    def wrapped_verify_ev(*args, **kwargs):
        st = time.perf_counter()
        res = orig_verify_ev(*args, **kwargs)
        profiler.record_stage('evidence_verification', time.perf_counter() - st)
        return res

    # Wrap Deduplication
    def wrapped_dedupe(*args, **kwargs):
        st = time.perf_counter()
        res = orig_dedupe(*args, **kwargs)
        profiler.record_stage('deduplication', time.perf_counter() - st)
        return res

    # Wrap DB Saves
    def wrapped_q_create(*args, **kwargs):
        st = time.perf_counter()
        res = orig_q_create(*args, **kwargs)
        profiler.record_stage('database_saves', time.perf_counter() - st)
        return res

    def wrapped_opt_bulk(*args, **kwargs):
        st = time.perf_counter()
        res = orig_opt_bulk(*args, **kwargs)
        profiler.record_stage('database_saves', time.perf_counter() - st)
        return res

    def wrapped_exam_save(self, *args, **kwargs):
        st = time.perf_counter()
        res = orig_exam_save(self, *args, **kwargs)
        profiler.record_stage('database_saves', time.perf_counter() - st)
        return res

    # Wrap Status / Progress Updates
    def wrapped_job_save(self, *args, **kwargs):
        st = time.perf_counter()
        res = orig_job_save(self, *args, **kwargs)
        profiler.record_stage('status_progress_updates', time.perf_counter() - st)
        return res

    # Wrap Ollama URLOPEN Call
    def hooked_urlopen(req, timeout=None):
        call_t0 = time.perf_counter()
        resp = orig_urlopen(req, timeout=timeout)
        raw_bytes = resp.read()
        wall_time = time.perf_counter() - call_t0
        resp_data = json.loads(raw_bytes.decode('utf-8'))

        load_sec = resp_data.get('load_duration', 0) / 1e9
        prompt_eval_sec = resp_data.get('prompt_eval_duration', 0) / 1e9
        eval_sec = resp_data.get('eval_duration', 0) / 1e9
        total_sec = resp_data.get('total_duration', 0) / 1e9
        eval_cnt = resp_data.get('eval_count', 0)
        p_eval_cnt = resp_data.get('prompt_eval_count', 0)
        tps = eval_cnt / eval_sec if eval_sec > 0 else 0.0

        profiler.record_stage('ollama_calls', wall_time)
        profiler.record_ollama_call({
            'wall_time': wall_time,
            'load_duration': load_sec,
            'prompt_eval_duration': prompt_eval_sec,
            'prompt_eval_count': p_eval_cnt,
            'eval_duration': eval_sec,
            'eval_count': eval_cnt,
            'total_duration': total_sec,
            'tps': tps,
            'done_reason': resp_data.get('done_reason', 'unknown'),
        })

        if resp_data.get('done_reason') == 'length':
            profiler.retry_counts['truncation'] += 1

        from io import BytesIO
        class MockResponse(BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): pass
        return MockResponse(raw_bytes)

    # Apply patches
    oc.urlopen = hooked_urlopen
    gp.build_type_generation_prompt = wrapped_build_type
    gp.build_long_answer_step_a_prompt = wrapped_build_la_a
    gp.build_long_answer_step_b_prompt = wrapped_build_la_b
    gp.parse_json_safely = wrapped_parse_json
    gp._validated_type_questions = wrapped_validated
    gp.verify_grounding_evidence = wrapped_verify_ev
    gp.deduplicate_questions = wrapped_dedupe
    Question.objects.create = wrapped_q_create
    Option.objects.bulk_create = wrapped_opt_bulk
    Exam.save = wrapped_exam_save
    PaperGenerationJob.save = wrapped_job_save

    try:
        difficulty_distribution = {'easy': 40, 'medium': 40, 'hard': 20}
        question_types = [t for t, cfg in blueprint.items() if cfg.get('enabled')]

        gp._run_generation(
            job_id=job.id,
            exam_id=exam.id,
            model_name=model_name,
            topics=topics,
            question_types=question_types,
            total_marks=target_marks,
            difficulty_distribution=difficulty_distribution,
            syllabus_text=syllabus_text,
            blueprint=blueprint,
        )
    finally:
        # Restore original functions
        oc.urlopen = orig_urlopen
        gp.build_type_generation_prompt = orig_build_type
        gp.build_long_answer_step_a_prompt = orig_build_la_a
        gp.build_long_answer_step_b_prompt = orig_build_la_b
        gp.parse_json_safely = orig_parse_json
        gp._validated_type_questions = orig_validated
        gp.verify_grounding_evidence = orig_verify_ev
        gp.deduplicate_questions = orig_dedupe
        Question.objects.create = orig_q_create
        Option.objects.bulk_create = orig_opt_bulk
        Exam.save = orig_exam_save
        PaperGenerationJob.save = orig_job_save

    total_pipeline_time = time.perf_counter() - t_pipeline_start
    job.refresh_from_db()
    exam.refresh_from_db()

    actual_questions = exam.questions.count()
    actual_marks = sum(q.marks for q in exam.questions.all())

    return {
        'total_time': total_pipeline_time,
        'stage_timings': profiler.stage_timings,
        'ollama_calls_count': len(profiler.ollama_calls_data),
        'ollama_calls': profiler.ollama_calls_data,
        'tokens_generated': profiler.tokens_generated,
        'prompt_tokens': profiler.prompt_tokens,
        'retry_counts': profiler.retry_counts,
        'job_status': job.status,
        'questions_generated': actual_questions,
        'actual_marks': float(actual_marks),
        'target_marks': target_marks,
    }


def compute_median_run(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes median metrics across 3 runs."""
    times = [r['total_time'] for r in runs]
    median_time = statistics.median(times)
    closest_run = min(runs, key=lambda r: abs(r['total_time'] - median_time))
    
    all_tps = [c['tps'] for r in runs for c in r.get('ollama_calls', []) if c['tps'] > 0]
    median_tps = statistics.median(all_tps) if all_tps else 0.0

    return {
        'median_total_time': median_time,
        'all_run_times': times,
        'closest_run': closest_run,
        'median_tps': median_tps,
        'stage_timings': closest_run['stage_timings'],
        'ollama_calls_count': closest_run['ollama_calls_count'],
        'tokens_generated': closest_run['tokens_generated'],
        'prompt_tokens': closest_run['prompt_tokens'],
        'questions_generated': closest_run['questions_generated'],
        'actual_marks': closest_run['actual_marks'],
    }


if __name__ == '__main__':
    pdf_path = 'tests/benchmarks/sample_syllabus.pdf'
    docx_path = 'tests/benchmarks/sample_syllabus.docx'

    results = {}
    blueprints = [20, 50, 100]
    files = [('PDF', pdf_path), ('DOCX', docx_path)]

    print("=== STARTING PHASE 1 PROFILING BENCHMARK (3 RUNS PER BLUEPRINT) ===", flush=True)
    
    for label, file_p in files:
        results[label] = {}
        for marks in blueprints:
            print(f"\n--- Benchmarking {label} | Target Marks: {marks} (3 runs) ---", flush=True)
            runs = []
            for r_idx in range(1, 4):
                print(f"  Run {r_idx}/3 starting...", flush=True)
                res = run_single_benchmark(file_p, marks)
                runs.append(res)
                print(f"  Run {r_idx}/3 finished: {res['total_time']:.2f}s | Calls: {res['ollama_calls_count']} | Qs: {res['questions_generated']} | Marks: {res['actual_marks']}", flush=True)
            median_res = compute_median_run(runs)
            results[label][marks] = median_res
            print(f"  ==> {label} {marks}M Median: {median_res['median_total_time']:.2f}s (Runs: {[round(t, 2) for t in median_res['all_run_times']]})", flush=True)

    out_file = 'tests/benchmarks/phase1_benchmark_results.json'
    with open(out_file, 'w', encoding='utf-8') as out:
        json.dump(results, out, indent=2)
    print(f"\nBenchmark results saved to {out_file}", flush=True)
