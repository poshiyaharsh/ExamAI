import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection

queries = [
    (
        "Live Exams Top 6 (Admin Dashboard Widget)",
        """
        EXPLAIN SELECT id, title, starts_at, ends_at, department, institution_id
        FROM api_exam
        WHERE institution_id = 2 AND status = 'published' AND starts_at <= NOW() AND ends_at >= NOW()
        ORDER BY starts_at DESC
        LIMIT 6
        """
    ),
    (
        "Eligible Students Count (Scope by Institution)",
        """
        EXPLAIN SELECT COUNT(*)
        FROM students_studentprofile
        WHERE institution_id = 2 AND department = 'Computer Science'
        """
    ),
    (
        "Question Bank Active Hash Lookup (Scope by Institution & Subject)",
        """
        EXPLAIN SELECT id, text, question_type, difficulty, marks
        FROM api_question
        WHERE institution_id = 2 AND subject_id = 1 AND active_hash = 'some_hash'
        """
    ),
    (
        "Student Attempt Lookup with Lock",
        """
        EXPLAIN SELECT id, total_score, status
        FROM api_studentattempt
        WHERE exam_id = 1 AND student_id = 3
        """
    ),
    (
        "Student Answers Aggregation",
        """
        EXPLAIN SELECT attempt_id, COUNT(*), SUM(score_awarded)
        FROM api_studentanswer
        WHERE attempt_id = 1
        GROUP BY attempt_id
        """
    )
]

with connection.cursor() as cursor:
    for title, sql in queries:
        print("=" * 80)
        print(f"QUERY: {title}")
        print("=" * 80)
        cursor.execute(sql)
        rows = cursor.fetchall()
        # Header from cursor description
        headers = [desc[0] for desc in cursor.description]
        print(f"{headers[0]:<4} | {headers[1]:<12} | {headers[2]:<25} | {headers[3]:<10} | {headers[4]:<15} | {headers[8]:<6} | {headers[9]:<20}")
        print("-" * 80)
        for r in rows:
            # id, select_type, table, partitions, type, possible_keys, key, key_len, ref, rows, filtered, Extra
            print(f"{str(r[0]):<4} | {str(r[1]):<12} | {str(r[2]):<25} | {str(r[4]):<10} | {str(r[6]):<15} | {str(r[9]):<6} | {str(r[11])[:20]}")
        print()
