import os
import MySQLdb

host = os.getenv('DB_HOST', '127.0.0.1')
user = os.getenv('DB_USER', 'examai_user')
password = os.getenv('DB_PASSWORD', 'ExamAI_Secure_Pass2026!')
db_name = os.getenv('DB_NAME', 'examai')
port = int(os.getenv('DB_PORT', 3306))

conn = MySQLdb.connect(host=host, user=user, passwd=password, db=db_name, port=port)
c = conn.cursor()

c.execute("SHOW TABLES;")
tables = [row[0] for row in c.fetchall()]

print("Resetting AUTO_INCREMENT for tables...")
for table in tables:
    try:
        c.execute(f"SELECT MAX(id) FROM `{table}`;")
        res = c.fetchone()
        max_id = res[0] if res and res[0] is not None else 0
        next_id = max_id + 1
        c.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = {next_id};")
        print(f"  {table:<35}: max_id={max_id:<5} -> AUTO_INCREMENT set to {next_id}")
    except Exception as exc:
        # Tables without an 'id' primary key column (e.g. many-to-many or composite)
        print(f"  {table:<35}: skipped ({exc})")

conn.close()
print("All tables processed successfully.")
