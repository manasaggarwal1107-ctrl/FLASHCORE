import os
import psycopg
from dotenv import load_dotenv

load_dotenv("backend/.env")

user = os.getenv("DB_USER", "postgres")
password = os.getenv("DB_PASSWORD", "")
host = os.getenv("DB_HOST", "localhost")
port = int(os.getenv("DB_PORT", "5432"))

try:
    with psycopg.connect(f"host={host} port={port} user={user} password={password} dbname=postgres", connect_timeout=3) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT datname FROM pg_database WHERE datname in ('flashcore_test', 'flashcore_rossmann');")
            dbs = cur.fetchall()
            print("Successfully connected to local PostgreSQL. Databases:", dbs)
except Exception as e:
    print("Connection error:", type(e), e)
