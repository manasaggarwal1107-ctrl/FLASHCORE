from sqlalchemy import text
from app.core.database import engine

with engine.connect() as db:
    name = db.execute(text("SELECT current_database()")).scalar_one()
    print(f"DATABASE: {name}")

    tables = db.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)).scalars().all()

    output = [f"DATABASE: {name}", "", "TABLES AND ROW COUNTS"]

    for table in tables:
        count = db.execute(
            text(f'SELECT COUNT(*) FROM public."{table}"')
        ).scalar_one()
        output.append(f"\n[{table}] rows={count}")

        columns = db.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table
            ORDER BY ordinal_position
        """), {"table": table}).all()

        for c in columns:
            output.append(
                f"  {c.column_name} | {c.data_type} | "
                f"nullable={c.is_nullable} | default={c.column_default}"
            )

    with open("../FLASHCORE_DATABASE_AUDIT.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))

    print(f"\nAudit complete: {len(tables)} tables")
    print("Saved: FLASHCORE_DATABASE_AUDIT.txt")
