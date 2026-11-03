import os
import psycopg2
from psycopg2 import Error
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Build connection string from DB_URL or individual environment variables
db_url = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
if db_url:
    # psycopg2 requires 'postgresql://' scheme rather than 'postgresql+psycopg2://'
    if db_url.startswith("postgresql+psycopg2://"):
        conn_string = db_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    else:
        conn_string = db_url
else:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "gdd_model")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASS", "")
    conn_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

cur = None
conn = None

try:
    # Connect to the database
    conn = psycopg2.connect(conn_string)
    conn.autocommit = False
    cur = conn.cursor()

    # Fetch distinct farmers (one consistent row per Farmer ID)
    select_query = """
    SELECT DISTINCT ON ("Farmer ID")
        "Farmer ID",
        "Farmer Name",
        "Cluster name"
    FROM farmer_grid_mapping
    WHERE "Farmer ID" IS NOT NULL 
      AND "Farmer Name" IS NOT NULL 
      AND TRIM("Farmer Name") != ''
    ORDER BY "Farmer ID", "fid" ASC;
    """
    cur.execute(select_query)
    rows = cur.fetchall()

    # Prepare batch data
    data_to_insert = []
    skipped_count = 0

    for row in rows:
        farmer_id_float = row[0]
        farmer_name = row[1].strip()
        cluster_name = row[2].strip() if row[2] else None

        try:
            farmer_id = int(float(farmer_id_float))
        except (ValueError, TypeError):
            skipped_count += 1
            print(f"Skipping invalid Farmer ID: {farmer_id_float}")
            continue

        name_parts = farmer_name.split()
        if not name_parts:
            skipped_count += 1
            continue

        first_name = name_parts[0]
        last_name = name_parts[-1] if len(name_parts) > 1 else first_name

        username = f"materra{farmer_id}"
        password = f"{first_name}{farmer_id}"  # Plain text – strongly recommend hashing!

        language = 'Marathi'
        listed = True
        district = cluster_name

        data_to_insert.append((
            farmer_id, first_name, last_name, username, password,
            language, listed, district
        ))

    if data_to_insert:
        # Batch UPSERT query
        upsert_query = """
        INSERT INTO gdd_users_table 
            (farmer_id, first_name, last_name, username, password, language, listed, district)
        VALUES %s
        ON CONFLICT (farmer_id) 
        DO UPDATE SET
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            username = EXCLUDED.username,
            password = EXCLUDED.password,
            language = EXCLUDED.language,
            listed = EXCLUDED.listed,
            district = EXCLUDED.district;
        """

        try:
            execute_values(cur, upsert_query, data_to_insert)
            conn.commit()
            print(f"Successfully processed (inserted/updated) {len(data_to_insert)} farmers.")
            print(f"Skipped {skipped_count} invalid entries.")

        except Error as e:
            print(f"Batch UPSERT failed: {e}")
            conn.rollback()
            print("No changes applied.")

    else:
        print("No valid farmer data found.")

except Error as e:
    print(f"Database connection or query error: {e}")
    if conn:
        conn.rollback()
finally:
    if cur:
        cur.close()
    if conn:
        conn.close()
