import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection

def check_db_health():
    print("=" * 60)
    print("ExamAI DATABASE HEALTH CHECK")
    print("=" * 60)

    engine = connection.settings_dict.get('ENGINE', '')
    print(f"Configured Engine    : {engine}")

    try:
        with connection.cursor() as cursor:
            # 1. Connection check
            cursor.execute("SELECT 1;")
            one = cursor.fetchone()[0]
            print(f"Basic Connectivity   : {'PASS (1=1)' if one == 1 else 'FAIL'}")

            if 'mysql' in engine:
                # 2. Version
                cursor.execute("SELECT VERSION();")
                version = cursor.fetchone()[0]
                print(f"MySQL Server Version : {version}")

                # 3. Charset & Collation
                cursor.execute("SELECT @@character_set_database, @@collation_database;")
                charset, collation = cursor.fetchone()
                print(f"Database Charset     : {charset} (Expected: utf8mb4)")
                print(f"Database Collation   : {collation} (Expected: utf8mb4_0900_ai_ci)")

                # 4. Transaction Isolation Level
                cursor.execute("SELECT @@transaction_isolation;")
                isolation = cursor.fetchone()[0]
                print(f"Transaction Isolation: {isolation} (Expected: READ-COMMITTED)")

                # 5. SQL Mode
                cursor.execute("SELECT @@sql_mode;")
                sql_mode = cursor.fetchone()[0]
                print(f"SQL Mode (Strict)    : {sql_mode}")

                # 6. Threads / Connections
                cursor.execute("SHOW STATUS LIKE 'Threads_connected';")
                threads = cursor.fetchone()
                print(f"Active DB Threads    : {threads[1] if threads else 'N/A'}")

            # Count core records
            cursor.execute("SELECT COUNT(*) FROM api_exam;")
            exams_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM api_question;")
            questions_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM auth_user;")
            users_count = cursor.fetchone()[0]

            print("-" * 60)
            print(f"Current Row Counts   : Users={users_count}, Exams={exams_count}, Questions={questions_count}")
            print("-" * 60)
            print("STATUS: HEALTHY - Database is operational and responsive.")
            print("=" * 60)
            return 0
    except Exception as exc:
        print(f"ERROR: Database health check failed: {exc}")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(check_db_health())
