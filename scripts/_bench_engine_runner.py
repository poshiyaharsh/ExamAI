"""
Subprocess runner for single-engine DB benchmark.
"""
import os
import sys
import time
import json
import threading
import statistics
from decimal import Decimal

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

engine = sys.argv[1] if len(sys.argv) > 1 else 'sqlite'
os.environ['DB_ENGINE'] = engine
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from django.conf import settings
from django.db import connection, transaction, OperationalError
from django.utils import timezone
from api.models import (
    AdminInstitution, User, Exam, Question, Option, 
    StudentAttempt, StudentAnswer, AttemptEvent, PaperGenerationJob
)
from api.utils.blueprint_allocator import to_decimal
from api.validators.question_bank import compute_text_hash

def bench_50m_generation(inst, user):
    """Times 50-mark paper creation and saving, measuring exact DB query time."""
    settings.DEBUG = True
    connection.queries_log.clear()

    start_total = time.perf_counter()
    
    # Simulate LLM inference duration (5-MCQ, 2-Short Answer, 1-Long Answer)
    simulated_llm_time = 14.5  # Typical Tier 2 LLM inference time
    time.sleep(0.05)  # Tiny pause to simulate non-blocking work

    start_db = time.perf_counter()
    with transaction.atomic():
        exam = Exam.objects.create(
            institution=inst,
            title=f"Benchmark 50M Exam ({engine})",
            subject="Cloud Computing",
            created_by=user,
            department="Computer Science",
            duration_minutes=60,
            total_marks=50,
            target_total_marks=50,
            status=Exam.Status.DRAFT,
        )

        # Create 15 questions (10 MCQ @ 1m, 4 Short @ 5m, 2 Long @ 10m -> 50 marks)
        q_specs = (
            [('mcq', 1.0, 4)] * 10 +
            [('short_answer', 5.0, 0)] * 4 +
            [('long_answer', 10.0, 0)] * 2
        )

        questions_to_create = []
        options_to_create = []

        for idx, (q_type, marks_val, num_opts) in enumerate(q_specs, start=1):
            q_obj = Question.objects.create(
                exam=exam,
                institution=inst,
                department=exam.department,
                order=idx,
                question_type=q_type,
                difficulty='medium',
                text=f"Benchmark Question #{idx} for {engine} testing: What is cloud scalability?",
                text_hash=compute_text_hash(f"q_{idx}_{engine}"),
                marks=to_decimal(marks_val),
                status=Question.Status.ACTIVE,
                model_answer="Model answer placeholder" if q_type != 'mcq' else '',
            )
            if num_opts > 0:
                for o_idx in range(1, num_opts + 1):
                    options_to_create.append(Option(
                        question=q_obj,
                        text=f"Option {o_idx} text",
                        is_correct=(o_idx == 1),
                        order=o_idx,
                    ))

        if options_to_create:
            Option.objects.bulk_create(options_to_create, batch_size=500)

        exam.total_marks = to_decimal(50.0)
        exam.save(update_fields=['total_marks', 'updated_at'])

    db_queries = list(connection.queries)
    query_count = len(db_queries)
    total_query_time = sum(float(q.get('time', 0.0)) for q in db_queries)
    settings.DEBUG = False

    end_total = time.perf_counter()
    real_elapsed = (end_total - start_total)
    total_time = real_elapsed + simulated_llm_time
    db_share_pct = (total_query_time / total_time) * 100.0

    return {
        'total_time': total_time,
        'llm_time': simulated_llm_time,
        'db_time': total_query_time,
        'query_count': query_count,
        'db_share_pct': db_share_pct,
        'exam_id': exam.id,
    }

def bench_concurrent_load(inst, user, exam_id):
    """Simulates 20 concurrent students posting heartbeats and answers."""
    exam = Exam.objects.get(id=exam_id)
    questions = list(exam.questions.all())

    # Create 20 attempts
    attempts = []
    for i in range(20):
        student, _ = User.objects.get_or_create(
            username=f"bench_stud_{engine}_{i}",
            defaults={'is_active': True}
        )
        att = StudentAttempt.objects.create(
            institution=inst,
            student=student,
            exam=exam,
            status=StudentAttempt.Status.IN_PROGRESS,
            started_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(minutes=60),
            active_session_token=f"tok_{engine}_{i}",
        )
        attempts.append(att)

    latencies = []
    lock_errors = 0
    errors = 0
    stop_event = threading.Event()

    def student_worker(attempt_idx, attempt):
        nonlocal lock_errors, errors
        q = questions[attempt_idx % len(questions)]
        for req_idx in range(15):
            t0 = time.perf_counter()
            try:
                # 1. Heartbeat check (read)
                att = StudentAttempt.objects.filter(id=attempt.id).select_related('exam').first()
                # 2. Answer update (write)
                with transaction.atomic():
                    StudentAnswer.objects.update_or_create(
                        attempt=attempt,
                        question=q,
                        defaults={
                            'institution': inst,
                            'answer_text': f"Student answer {req_idx}",
                            'selected_option_order': [0, 1, 2, 3],
                        }
                    )
                latency_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(latency_ms)
            except OperationalError as exc:
                if 'locked' in str(exc).lower() or 'busy' in str(exc).lower():
                    lock_errors += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
            time.sleep(0.01)

    threads = []
    for idx, att in enumerate(attempts):
        t = threading.Thread(target=student_worker, args=(idx, att))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Cleanup attempts
    StudentAttempt.objects.filter(id__in=[a.id for a in attempts]).delete()

    latencies.sort()
    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0

    return {
        'total_requests': len(latencies),
        'p50_latency_ms': p50,
        'p95_latency_ms': p95,
        'p99_latency_ms': p99,
        'error_count': errors,
        'lock_errors': lock_errors,
    }

def main():
    inst = AdminInstitution.objects.first()
    if not inst:
        inst = AdminInstitution.objects.create(name="Bench Inst", code="BENCH")
    user = User.objects.filter(is_staff=True).first() or User.objects.first()
    if not user:
        user = User.objects.create(username="bench_fac", is_active=True)

    gen_result = bench_50m_generation(inst, user)
    load_result = bench_concurrent_load(inst, user, gen_result['exam_id'])

    # Cleanup exam
    Exam.objects.filter(id=gen_result['exam_id']).delete()

    result_payload = {
        'engine': engine,
        'gen_50m': gen_result,
        'load_test': load_result,
    }
    print("===JSON_RESULT===")
    print(json.dumps(result_payload))

if __name__ == '__main__':
    main()
