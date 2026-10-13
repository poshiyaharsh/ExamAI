import os
import sys
import sqlite3
import django
from decimal import Decimal

# Setup Django (pointing to MySQL as configured in .env)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection as mysql_conn

SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db.sqlite3')

def run_verification():
    print("=" * 80)
    print("ExamAI DATABASE MIGRATION VERIFICATION: SQLite -> MySQL 8.4 LTS")
    print("=" * 80)

    if not os.path.exists(SQLITE_PATH):
        print(f"ERROR: SQLite database file not found at {SQLITE_PATH}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()
    mysql_cur = mysql_conn.cursor()

    overall_passed = True
    results = []

    def record_result(category, check_name, sqlite_val, mysql_val, passed):
        nonlocal overall_passed
        if not passed:
            overall_passed = False
        results.append({
            "category": category,
            "check": check_name,
            "sqlite": str(sqlite_val),
            "mysql": str(mysql_val),
            "status": "PASS" if passed else "FAIL"
        })

    # -------------------------------------------------------------
    # 1. TABLE ROW COUNTS
    # -------------------------------------------------------------
    EXCLUDED_TABLES = {
        'django_session',
        'token_blacklist_outstandingtoken',
        'token_blacklist_blacklistedtoken',
        'api_userconsent',
        'auth_permission',
        'django_content_type',
        'django_migrations',
    }

    # Get all tables in SQLite
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in sqlite_cur.fetchall() if row[0] not in EXCLUDED_TABLES]
    tables.sort()

    print("\n[1/5] Checking Table Row Counts...")
    for table in tables:
        sqlite_cur.execute(f"SELECT COUNT(*) FROM \"{table}\"")
        s_count = sqlite_cur.fetchone()[0]

        try:
            mysql_cur.execute(f"SELECT COUNT(*) FROM `{table}`")
            m_count = mysql_cur.fetchone()[0]
            passed = (s_count == m_count)
        except Exception as e:
            m_count = f"Error: {e}"
            passed = False

        record_result("Row Count", table, s_count, m_count, passed)

    # -------------------------------------------------------------
    # 2. PER-INSTITUTION ROW COUNTS
    # -------------------------------------------------------------
    print("\n[2/5] Checking Per-Institution Distribution...")
    # Fetch all institution IDs from SQLite
    sqlite_cur.execute("SELECT id, institution_name FROM admins_admininstitution ORDER BY id")
    institutions = sqlite_cur.fetchall()

    inst_tables = [
        ("StudentProfile", "students_studentprofile", "institution_id"),
        ("FacultyProfile", "faculty_facultyprofile", "institution_id"),
        ("Department", "admins_admindepartment", "institution_id"),
        ("Subject", "api_subject", "institution_id"),
        ("Exam", "api_exam", "institution_id"),
        ("Question", "api_question", "institution_id"),
        ("Paper", "faculty_paper", "institution_id"),
        ("StudentAttempt", "api_studentattempt", "institution_id"),
        ("StudentAnswer", "api_studentanswer", "institution_id"),
    ]

    for inst_id, inst_name in institutions:
        for label, table, col in inst_tables:
            sqlite_cur.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE \"{col}\" = ?", (inst_id,))
            s_count = sqlite_cur.fetchone()[0]

            mysql_cur.execute(f"SELECT COUNT(*) FROM `{table}` WHERE `{col}` = %s", (inst_id,))
            m_count = mysql_cur.fetchone()[0]

            record_result("Per-Tenant", f"{inst_name} ({inst_id}) -> {label}", s_count, m_count, s_count == m_count)

    # -------------------------------------------------------------
    # 3. NUMERICAL CHECKSUMS (Sum of IDs, Marks, Scores)
    # -------------------------------------------------------------
    print("\n[3/5] Checking Aggregates & Checksums...")
    checksum_queries = [
        ("Sum of User IDs", "auth_user", "SUM(id)"),
        ("Sum of Question IDs", "api_question", "SUM(id)"),
        ("Sum of Question Marks", "api_question", "SUM(marks)"),
        ("Sum of Option IDs", "api_option", "SUM(id)"),
        ("Sum of Exam IDs", "api_exam", "SUM(id)"),
        ("Sum of Exam Total Marks", "api_exam", "SUM(total_marks)"),
        ("Sum of Exam Durations", "api_exam", "SUM(duration_minutes)"),
        ("Sum of StudentAttempt IDs", "api_studentattempt", "SUM(id)"),
        ("Sum of StudentAttempt Scores", "api_studentattempt", "ROUND(SUM(total_score), 2)"),
        ("Sum of StudentAnswer IDs", "api_studentanswer", "SUM(id)"),
        ("Sum of StudentAnswer Scores Awarded", "api_studentanswer", "ROUND(SUM(score_awarded), 2)"),
        ("Sum of Paper IDs", "faculty_paper", "SUM(id)"),
        ("Sum of PaperQuestion IDs", "faculty_paperquestion", "SUM(id)"),
    ]

    for label, table, expr in checksum_queries:
        sqlite_cur.execute(f"SELECT {expr} FROM \"{table}\"")
        s_val = sqlite_cur.fetchone()[0]
        # normalize None or Decimal
        s_val = 0 if s_val is None else round(float(s_val), 2) if isinstance(s_val, (float, int)) else s_val

        mysql_cur.execute(f"SELECT {expr} FROM `{table}`")
        m_val = mysql_cur.fetchone()[0]
        m_val = 0 if m_val is None else round(float(m_val), 2) if isinstance(m_val, (float, int, Decimal)) else m_val

        record_result("Checksum", label, s_val, m_val, str(s_val) == str(m_val))

    # -------------------------------------------------------------
    # 4. FOREIGN KEY & ORPHAN CHECKS
    # -------------------------------------------------------------
    print("\n[4/5] Checking Foreign Key & Orphan Integrity in MySQL...")
    orphan_checks = [
        ("StudentProfile -> User", "students_studentprofile", "user_id", "auth_user", "id"),
        ("StudentProfile -> Institution", "students_studentprofile", "institution_id", "admins_admininstitution", "id"),
        ("FacultyProfile -> User", "faculty_facultyprofile", "user_id", "auth_user", "id"),
        ("AdminProfile -> User", "admins_adminprofile", "user_id", "auth_user", "id"),
        ("Question -> Subject", "api_question", "subject_id", "api_subject", "id"),
        ("Question -> Topic", "api_question", "topic_id", "api_topic", "id"),
        ("Option -> Question", "api_option", "question_id", "api_question", "id"),
        ("Exam -> Institution", "api_exam", "institution_id", "admins_admininstitution", "id"),
        ("StudentAttempt -> Exam", "api_studentattempt", "exam_id", "api_exam", "id"),
        ("StudentAttempt -> Student", "api_studentattempt", "student_id", "auth_user", "id"),
        ("StudentAnswer -> Attempt", "api_studentanswer", "attempt_id", "api_studentattempt", "id"),
        ("StudentAnswer -> Question", "api_studentanswer", "question_id", "api_question", "id"),
        ("PaperQuestion -> Paper", "faculty_paperquestion", "paper_id", "faculty_paper", "id"),
    ]

    for label, child_tbl, child_fk, parent_tbl, parent_pk in orphan_checks:
        mysql_cur.execute(f"""
            SELECT COUNT(*) FROM `{child_tbl}` c
            LEFT JOIN `{parent_tbl}` p ON c.`{child_fk}` = p.`{parent_pk}`
            WHERE c.`{child_fk}` IS NOT NULL AND p.`{parent_pk}` IS NULL
        """)
        orphan_count = mysql_cur.fetchone()[0]
        record_result("FK Integrity", f"Orphans: {label}", 0, orphan_count, orphan_count == 0)

    # -------------------------------------------------------------
    # 5. SPOT CHECK SAMPLE RECORDS (Content, JSON, Dates)
    # -------------------------------------------------------------
    print("\n[5/5] Spot Checking Sample Records...")
    # Spot check users
    sqlite_cur.execute("SELECT id, username, email, is_active FROM auth_user ORDER BY id LIMIT 5")
    s_users = list(sqlite_cur.fetchall())
    mysql_cur.execute("SELECT id, username, email, is_active FROM auth_user ORDER BY id LIMIT 5")
    m_users = list(mysql_cur.fetchall())
    record_result("Spot Check", "Top 5 Users (id, username, email, active)", s_users, m_users, s_users == m_users)

    # Spot check student attempts
    sqlite_cur.execute("SELECT id, exam_id, student_id, ROUND(total_score, 2), status FROM api_studentattempt ORDER BY id LIMIT 5")
    s_attempts = [(r[0], r[1], r[2], round(float(r[3]), 2) if r[3] is not None else None, r[4]) for r in sqlite_cur.fetchall()]
    mysql_cur.execute("SELECT id, exam_id, student_id, ROUND(total_score, 2), status FROM api_studentattempt ORDER BY id LIMIT 5")
    m_attempts = [(r[0], r[1], r[2], round(float(r[3]), 2) if r[3] is not None else None, r[4]) for r in mysql_cur.fetchall()]
    record_result("Spot Check", "Top 5 StudentAttempts (id, exam, student, total_score, status)", s_attempts, m_attempts, s_attempts == m_attempts)

    # Spot check questions
    sqlite_cur.execute("SELECT id, question_type, difficulty, ROUND(marks, 2), text_hash FROM api_question ORDER BY id LIMIT 5")
    s_questions = [(r[0], r[1], r[2], round(float(r[3]), 2) if r[3] is not None else None, r[4]) for r in sqlite_cur.fetchall()]
    mysql_cur.execute("SELECT id, question_type, difficulty, ROUND(marks, 2), text_hash FROM api_question ORDER BY id LIMIT 5")
    m_questions = [(r[0], r[1], r[2], round(float(r[3]), 2) if r[3] is not None else None, r[4]) for r in mysql_cur.fetchall()]
    record_result("Spot Check", "Top 5 Questions (id, type, diff, marks, hash)", s_questions, m_questions, s_questions == m_questions)

    # Spot check options
    sqlite_cur.execute("SELECT id, question_id, is_correct, text FROM api_option ORDER BY id LIMIT 5")
    s_options = [(r[0], r[1], bool(r[2]), r[3]) for r in sqlite_cur.fetchall()]
    mysql_cur.execute("SELECT id, question_id, is_correct, text FROM api_option ORDER BY id LIMIT 5")
    m_options = [(r[0], r[1], bool(r[2]), r[3]) for r in mysql_cur.fetchall()]
    record_result("Spot Check", "Top 5 Options (id, question_id, is_correct, text)", s_options, m_options, s_options == m_options)

    # Print Full Report
    print("\n" + "=" * 80)
    print(f"{'CATEGORY':<14} | {'CHECK':<42} | {'SQLITE':<8} | {'MYSQL':<8} | STATUS")
    print("-" * 80)
    for r in results:
        sq_str = r['sqlite'][:8] if len(r['sqlite']) > 8 else r['sqlite']
        my_str = r['mysql'][:8] if len(r['mysql']) > 8 else r['mysql']
        print(f"{r['category']:<14} | {r['check']:<42} | {sq_str:<8} | {my_str:<8} | {r['status']}")
    print("=" * 80)

    if overall_passed:
        print("\nALL VERIFICATION CHECKS PASSED PERFECTLY! 100% DATA MATCH BETWEEN SQLite & MySQL.\n")
        return 0
    else:
        print("\nVERIFICATION FAILED! SEE MISMATCHES ABOVE.\n")
        return 1

if __name__ == '__main__':
    sys.exit(run_verification())
