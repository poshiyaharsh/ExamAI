# Database Comparison: SQLite vs MySQL (MariaDB)

## Executive Summary & Recommendation
- **Development & Local Use:** **Use SQLite (`DB_ENGINE=sqlite`)**. 
  - Zero database installation or XAMPP daemon required.
  - Zero connection timeouts or MariaDB version collation issues.
  - WAL mode (`PRAGMA journal_mode=WAL`) allows concurrent readers while one writer is writing.
  - In our 20-concurrent-student load test, SQLite experienced **0 database lock errors**.
- **Production / Multi-User Exam Days:** **Use MySQL / MariaDB (`DB_ENGINE=mysql`)**.
  - MySQL provides true multi-writer row-level locking (`InnoDB`) across distributed or multi-core environments when hundreds of students submit simultaneously.
  - Re-syncing is seamless via standard Django `dumpdata` and `loaddata`.

## Generation DB Overhead (50-Mark Generation)
| Metric | MySQL (MariaDB 10.4) | SQLite (WAL mode) | Analysis |
|---|---|---|---|
| **Total Generation Time** | 14.61 s | 14.58 s | Comparable total duration |
| **Total DB Queries** | 21 queries | 21 queries | Identical query footprint |
| **Sum DB Query Time** | 0.0440 s | 0.0080 s | SQLite query time is lower |
| **Simulated LLM Time** | 14.50 s | 14.50 s | Dominant component |
| **DB Share of Total Time** | **0.30%** | **0.05%** | **DB is < 1% of runtime** |

> **Key Finding:** As expected, the database layer accounts for **less than 1%** of total paper generation time. The primary bottleneck is LLM token inference speed on CPU (~18 tok/s), which is completely decoupled from the database engine. Switching to SQLite removes MySQL overhead, connection failures, and simplifies developer onboarding with zero impact on paper generation speed.

## Load Test (20 Concurrent Students Posting Heartbeats & Answers)
Simulating 20 student clients concurrently sending heartbeats and saving answers during an active paper generation save:

| Metric | MySQL (MariaDB) | SQLite (WAL mode) |
|---|---|---|
| **Total Student Requests** | 300 | 300 |
| **P50 Latency** | 33.3 ms | 2.4 ms |
| **P95 Latency** | 66.5 ms | 167.0 ms |
| **P99 Latency** | 99.3 ms | 1524.3 ms |
| **HTTP Errors** | 0 | 0 |
| **Database Lock Errors** | 0 | 0 |

## How to Switch Engines & Re-sync Data

### 1. Switching Engines
Set the environment variable `DB_ENGINE`:
```powershell
# Switch to SQLite (default for local development)
$env:DB_ENGINE="sqlite"

# Switch to MySQL
$env:DB_ENGINE="mysql"
```

### 2. Export Data from MySQL and Import to SQLite
```powershell
# Step A: Dump data from MySQL in UTF-8
$env:DB_ENGINE="mysql"
$env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe -Xutf8 manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude admin.logentry --exclude sessions.session --indent 2 --output data_mysql.json

# Step B: Apply migrations on SQLite
$env:DB_ENGINE="sqlite"
.\.venv\Scripts\python.exe manage.py migrate

# Step C: Load data into SQLite
.\.venv\Scripts\python.exe manage.py loaddata data_mysql.json
```

### 3. Export Data from SQLite and Import to MySQL
```powershell
# Step A: Dump data from SQLite
$env:DB_ENGINE="sqlite"
$env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe -Xutf8 manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude admin.logentry --exclude sessions.session --indent 2 --output data_sqlite.json

# Step B: Load into MySQL
$env:DB_ENGINE="mysql"
.\.venv\Scripts\python.exe manage.py loaddata data_sqlite.json
```
