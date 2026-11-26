
import csv
import hashlib
from datetime import datetime
from pathlib import Path

import psycopg
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "rossmann"
ENV = dotenv_values(Path(__file__).resolve().parent / ".env")

SOURCE_URL = (
    "https://www.kaggle.com/competitions/rossmann-store-sales/data"
)


def sha256_file(path):
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def count_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        return sum(1 for _ in csv.DictReader(file))


def optional_int(value):
    if value is None or value.strip() == "":
        return None
    return int(float(value))


def connect():
    password = ENV.get("DB_PASSWORD")

    if not password or password == "YOUR_POSTGRES_PASSWORD":
        raise RuntimeError(
            "Set the real DB_PASSWORD in backend/.env first."
        )

    return psycopg.connect(
        host=ENV.get("DB_HOST", "localhost"),
        port=ENV.get("DB_PORT", "5432"),
        dbname="flashcore_rossmann",
        user=ENV.get("DB_USER", "postgres"),
        password=password,
    )


def create_import_record(cursor, filename, split, path, row_count):
    cursor.execute(
        """
        INSERT INTO dataset_imports (
            source_name,
            source_url,
            source_file,
            source_split,
            checksum_sha256,
            total_rows,
            status
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, 'running'
        )
        RETURNING id
        """,
        (
            "Rossmann Store Sales",
            SOURCE_URL,
            filename,
            split,
            sha256_file(path),
            row_count,
        ),
    )

    return cursor.fetchone()[0]


def import_stores(cursor, path):
    row_count = count_csv_rows(path)

    import_id = create_import_record(
        cursor, path.name, "store", path, row_count
    )

    sql = """
        COPY stores (
            store_id,
            store_type,
            assortment,
            competition_distance,
            competition_open_since_month,
            competition_open_since_year,
            promo2,
            promo2_since_week,
            promo2_since_year,
            promo_interval,
            metadata_import_id
        ) FROM STDIN
    """

    imported = 0

    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        with cursor.copy(sql) as copy:
            for row in reader:
                copy.write_row((
                    int(row["Store"]),
                    row["StoreType"] or None,
                    row["Assortment"] or None,
                    optional_int(row["CompetitionDistance"]),
                    optional_int(row["CompetitionOpenSinceMonth"]),
                    optional_int(row["CompetitionOpenSinceYear"]),
                    bool(int(row["Promo2"])),
                    optional_int(row["Promo2SinceWeek"]),
                    optional_int(row["Promo2SinceYear"]),
                    row["PromoInterval"] or None,
                    import_id,
                ))
                imported += 1

    cursor.execute(
        """
        UPDATE dataset_imports
        SET successful_rows = %s,
            rejected_rows = 0,
            status = 'completed'
        WHERE id = %s
        """,
        (imported, import_id),
    )

    return imported


def import_sales(cursor, path):
    row_count = count_csv_rows(path)

    import_id = create_import_record(
        cursor, path.name, "train", path, row_count
    )

    sql = """
        COPY daily_store_sales (
            store_id,
            sales_date,
            day_of_week,
            sales,
            customers,
            is_open,
            promo,
            state_holiday,
            school_holiday,
            import_id,
            source_row_number
        ) FROM STDIN
    """

    imported = 0

    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        with cursor.copy(sql) as copy:
            for row_number, row in enumerate(reader, start=2):
                copy.write_row((
                    int(row["Store"]),
                    datetime.strptime(
                        row["Date"], "%Y-%m-%d"
                    ).date(),
                    int(row["DayOfWeek"]),
                    int(row["Sales"]),
                    int(row["Customers"]),
                    bool(int(row["Open"])),
                    bool(int(row["Promo"])),
                    str(row["StateHoliday"]),
                    bool(int(row["SchoolHoliday"])),
                    import_id,
                    row_number,
                ))
                imported += 1

    cursor.execute(
        """
        UPDATE dataset_imports
        SET successful_rows = %s,
            rejected_rows = 0,
            status = 'completed'
        WHERE id = %s
        """,
        (imported, import_id),
    )

    return imported


def main():
    store_file = DATA_DIR / "store.csv"
    train_file = DATA_DIR / "train.csv"

    if not store_file.exists() or not train_file.exists():
        raise FileNotFoundError(
            f"Expected store.csv and train.csv inside {DATA_DIR}"
        )

    expected_stores = count_csv_rows(store_file)
    expected_sales = count_csv_rows(train_file)

    print("ROSSMANN DATA IMPORT")
    print("--------------------")
    print("Database: flashcore_rossmann")
    print("Store rows in source:", expected_stores)
    print("Training rows in source:", expected_sales)

    with connect() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT COUNT(*) FROM stores"
            )
            existing_stores = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM daily_store_sales"
            )
            existing_sales = cursor.fetchone()[0]

            if existing_stores or existing_sales:
                raise RuntimeError(
                    "Target tables are not empty. "
                    "Import cancelled to prevent duplicate data."
                )

            store_count = import_stores(cursor, store_file)
            print("Stores imported:", store_count)

            sales_count = import_sales(cursor, train_file)
            print("Historical sales imported:", sales_count)

            if store_count != expected_stores:
                raise RuntimeError("Store row count mismatch.")

            if sales_count != expected_sales:
                raise RuntimeError("Sales row count mismatch.")

    print("--------------------")
    print("IMPORT COMPLETED")
    print("All imported rows committed successfully.")


if __name__ == "__main__":
    main()
