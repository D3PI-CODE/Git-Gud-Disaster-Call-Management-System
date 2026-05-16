#!/usr/bin/env python3
"""Apply supabase_schema.sql when DATABASE_URL or SUPABASE_DB_PASSWORD is set."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "supabase_schema.sql"


def main() -> int:
    db_url = os.getenv("DATABASE_URL")
    db_password = os.getenv("SUPABASE_DB_PASSWORD")
    ref = os.getenv("SUPABASE_PROJECT_REF", "tarcmqosxnfrdwumbzmq")

    if not db_url and db_password:
        db_url = (
            f"postgresql://postgres.{ref}:{db_password}"
            f"@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
        )

    if not db_url:
        print(
            "Set DATABASE_URL or SUPABASE_DB_PASSWORD in Backend/.env,\n"
            "or paste supabase_schema.sql into Supabase Dashboard → SQL Editor."
        )
        return 1

    try:
        import psycopg2
    except ImportError:
        print("Install psycopg2-binary: pip install psycopg2-binary")
        return 1

    sql = SCHEMA_PATH.read_text()
    print(f"Applying schema from {SCHEMA_PATH} ...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    cur.close()
    conn.close()
    print("Schema applied successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
