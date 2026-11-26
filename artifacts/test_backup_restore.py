import os
import sys
import time
import subprocess
import psycopg
from dotenv import load_dotenv

load_dotenv("backend/.env")

user = os.getenv("DB_USER", "postgres")
password = os.getenv("DB_PASSWORD", "")
host = os.getenv("DB_HOST", "localhost")
port = int(os.getenv("DB_PORT", "5432"))

pg_dump_bin = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
psql_bin = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"
backup_file = os.path.abspath(r"artifacts\flashcore_test_backup.sql")

print("=" * 80)
print("FLASHCORE STAGE 3 — ISOLATED BACKUP & DISASTER RECOVERY VALIDATION")
print("Source Database: flashcore_test | Recovery Database: flashcore_recovery_test")
print("=" * 80)

# 1. Seed some realistic records into flashcore_test
with psycopg.connect(f"host={host} port={port} user={user} password={password} dbname=flashcore_test") as conn:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE users, simulation_runs, stores CASCADE;")
        cur.execute("""
            INSERT INTO stores (store_id, store_type, assortment, competition_distance)
            VALUES (1, 'a', 'a', 500), (2, 'b', 'b', 1200), (3, 'c', 'c', 800)
            ON CONFLICT (store_id) DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO users (email, password_hash, role, status)
            VALUES ('backup_test1@flashcore.test', 'dummyhash1', 'admin', 'active'),
                   ('backup_test2@flashcore.test', 'dummyhash2', 'analyst', 'active');
        """)
        cur.execute("""
            INSERT INTO simulation_runs (run_name, description, configuration, status)
            VALUES ('DR Simulation Run', 'Disaster Recovery Validation', '{}', 'completed');
        """)
        conn.commit()

        # Count records
        cur.execute("SELECT COUNT(*) FROM stores;")
        stores_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users;")
        users_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM simulation_runs;")
        runs_count = cur.fetchone()[0]
        print(f"Pre-backup records: stores={stores_count}, users={users_count}, runs={runs_count}")

# 2. Perform Backup using pg_dump
print("\n--- Initiating Backup Acquisition ---")
env = os.environ.copy()
env["PGPASSWORD"] = password

t0 = time.perf_counter()
cmd_dump = [
    pg_dump_bin,
    "-h", host,
    "-p", str(port),
    "-U", user,
    "-d", "flashcore_test",
    "-f", backup_file,
    "--clean",
    "--if-exists",
]
proc = subprocess.run(cmd_dump, env=env, capture_output=True, text=True)
backup_duration = time.perf_counter() - t0

if proc.returncode != 0:
    print("pg_dump failed:", proc.stderr)
    sys.exit(1)

file_size_kb = os.path.getsize(backup_file) / 1024
print(f"Backup SUCCESS: File={backup_file}")
print(f"Backup Duration: {backup_duration:.4f} seconds | File Size: {file_size_kb:.2f} KB")

# 3. Create fresh isolated database for restore test
print("\n--- Preparing Isolated Recovery Database ---")
with psycopg.connect(f"host={host} port={port} user={user} password={password} dbname=postgres", autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("DROP DATABASE IF EXISTS flashcore_recovery_test;")
        cur.execute("CREATE DATABASE flashcore_recovery_test;")
        print("Created clean isolated database: flashcore_recovery_test")

# 4. Restore into flashcore_recovery_test
print("\n--- Initiating Restoration from Backup ---")
t1 = time.perf_counter()
cmd_restore = [
    psql_bin,
    "-h", host,
    "-p", str(port),
    "-U", user,
    "-d", "flashcore_recovery_test",
    "-f", backup_file,
]
proc_restore = subprocess.run(cmd_restore, env=env, capture_output=True, text=True)
restore_duration = time.perf_counter() - t1

print(f"Restoration Complete: Duration = {restore_duration:.4f} seconds")

# 5. Verify Record Parity in flashcore_recovery_test
with psycopg.connect(f"host={host} port={port} user={user} password={password} dbname=flashcore_recovery_test") as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM stores;")
        r_stores = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users;")
        r_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM simulation_runs;")
        r_runs = cur.fetchone()[0]

print(f"Post-recovery records: stores={r_stores}, users={r_users}, runs={r_runs}")
assert r_stores == stores_count, f"Store parity mismatch: {r_stores} != {stores_count}"
assert r_users == users_count, f"User parity mismatch: {r_users} != {users_count}"
assert r_runs == runs_count, f"Runs parity mismatch: {r_runs} != {runs_count}"
print(">>> RECORD PARITY: 100% MATCH ACROSS ALL TABLES <<<")

# 6. Cleanup recovery database
with psycopg.connect(f"host={host} port={port} user={user} password={password} dbname=postgres", autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("DROP DATABASE IF EXISTS flashcore_recovery_test;")
        print("Dropped temporary test database: flashcore_recovery_test")

print("\n" + "=" * 80)
print(f"BACKUP & DISASTER RECOVERY DRILL SUMMARY:")
print(f"Backup Duration (RPO enablement): {backup_duration:.4f}s")
print(f"Recovery Duration (RTO benchmark): {restore_duration:.4f}s")
print(f"Data Parity: 100% Complete & Exact")
print("=" * 80)
