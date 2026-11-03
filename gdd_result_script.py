import os
import sys
import logging
import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

# Import from updated.py (assumes it's in the same directory)
from updated import (
    get_db_url, mask_db_url, setup_database, phenophase_thresholds, phenophase_descriptions,
    insect_risks, disease_risks, pbw_weather_conditions, fetch_weather_data, calculate_gdd,
    calculate_rainy_days, predict_harvest_dates, evaluate_pbw_risk, evaluate_insect_risks,
    evaluate_disease_risks, determine_sowing_window, get_current_phenophase, update_gdd,
    calculate_historical_insect_risks, calculate_historical_disease_risks, process_location
)

# Logging setup (same as updated.py)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

load_dotenv()

# Override process_location to return a dict instead of string (for storage), but keep computations identical
def process_location_dict(*args, **kwargs):
    # Call original to get string, then parse to dict (simple way to keep identical without full refactor)
    result_str = process_location(*args, **kwargs)
    if "Error" in result_str:
        return None  # Skip errors

    # Parse the string to extract dict (based on known format)
    lines = result_str.split("\n")
    result_dict = {
        "farmer_id": float(lines[0].split(": ")[1]),
        "farmer_name": lines[1].split(": ")[1],
        "cluster_name": lines[2].split(": ")[1],
    }
    
    # Extract other fields (this is parsing logic; in production, refactor updated.py to return dict directly)
    for line in lines:
        if "Sowing Date=" in line:
            result_dict["sowing_date"] = datetime.strptime(line.split("Sowing Date=")[1].split(",")[0], "%Y-%m-%d").date()
        elif "Current Phenophase:" in line:
            parts = line.split(": ")[1]
            result_dict["current_phenophase"] = parts.split(" - ")[0]
            result_dict["current_phenophase_desc"] = parts.split(" - ")[1]
        elif "Cumulative GDD:" in line:
            result_dict["cumulative_gdd"] = float(line.split(": ")[1])
        elif "Total Rainfall" in line:
            result_dict["total_rainfall"] = float(line.split(": ")[1].split(" ")[0])
        elif "Average Temperature" in line:
            if "N/A" not in line:
                result_dict["avg_temp"] = float(line.split(": ")[1].split("°")[0])
        elif "PBW) Forecast:" in line:
            i = lines.index(line)
            result_dict["pbw_stage"] = lines[i+1].split(": ")[1]
            result_dict["pbw_generation"] = lines[i+2].split(": ")[1]
            result_dict["pbw_adjusted_severity"] = lines[i+3].split(": ")[1]
            result_dict["pbw_risk_percentage"] = float(lines[i+4].split(": ")[1].split("%")[0])
            recs = []
            j = i+6
            while j < len(lines) and "- " in lines[j]:
                recs.append(lines[j].strip("    - "))
                j += 1
            result_dict["pbw_recommendations"] = recs
        elif "Insect Risk Alerts" in line and "PBW" in line:
            i = lines.index(line)
            j = i + 1
            while j < len(lines) and ("Aphids" in lines[j] or "Whitefly" in lines[j]):
                if "Aphids" in lines[j]:
                    result_dict["aphid_risk_percentage"] = float(lines[j].split("Risk Score: ")[1].split("%")[0])
                    adv = []
                    k = j + 1
                    while k < len(lines) and "- " in lines[k]:
                        adv.append(lines[k].strip("    - "))
                        k += 1
                    result_dict["aphid_advisory"] = adv
                    j = k
                elif "Whitefly" in lines[j]:
                    result_dict["whitefly_risk_percentage"] = float(lines[j].split("Risk Score: ")[1].split("%")[0])
                    adv = []
                    k = j + 1
                    while k < len(lines) and "- " in lines[k]:
                        adv.append(lines[k].strip("    - "))
                        k += 1
                    result_dict["whitefly_advisory"] = adv
                    j = k
        elif "Disease Risk Alerts:" in line:
            i = lines.index(line)
            j = i + 1
            while j < len(lines) and ("Bacterial Blight" in lines[j] or "Fusarium Wilt" in lines[j]):
                if "Bacterial Blight" in lines[j]:
                    result_dict["bacterial_blight_risk_percentage"] = float(lines[j].split("Risk Score: ")[1].split("%")[0])
                    adv = []
                    k = j + 1
                    while k < len(lines) and "- " in lines[k]:
                        adv.append(lines[k].strip("    - "))
                        k += 1
                    result_dict["bacterial_blight_advisory"] = adv
                    j = k
                elif "Fusarium Wilt" in lines[j]:
                    result_dict["fusarium_wilt_risk_percentage"] = float(lines[j].split("Risk Score: ")[1].split("%")[0])
                    adv = []
                    k = j + 1
                    while k < len(lines) and "- " in lines[k]:
                        adv.append(lines[k].strip("    - "))
                        k += 1
                    result_dict["fusarium_wilt_advisory"] = adv
                    j = k
        elif "Historical Insect Risk Summary" in line:
            i = lines.index(line)
            j = i + 1
            while j < len(lines) and ( "Aphids:" in lines[j] or "Whitefly:" in lines[j] or "Pink Boll Worm:" in lines[j] ):
                if "Aphids:" in lines[j]:
                    result_dict["aphid_first_conducive_date"] = datetime.strptime(lines[j+1].split(": ")[1], "%Y-%m-%d").date()
                    result_dict["aphid_conducive_days"] = int(lines[j+2].split(": ")[1])
                    result_dict["aphid_highest_risk"] = float(lines[j+3].split(": ")[1].split("%")[0])
                    result_dict["aphid_highest_risk_date"] = datetime.strptime(lines[j+3].split(" on ")[1], "%Y-%m-%d").date()
                    j += 4
                elif "Whitefly:" in lines[j]:
                    result_dict["whitefly_first_conducive_date"] = datetime.strptime(lines[j+1].split(": ")[1], "%Y-%m-%d").date()
                    result_dict["whitefly_conducive_days"] = int(lines[j+2].split(": ")[1])
                    result_dict["whitefly_highest_risk"] = float(lines[j+3].split(": ")[1].split("%")[0])
                    result_dict["whitefly_highest_risk_date"] = datetime.strptime(lines[j+3].split(" on ")[1], "%Y-%m-%d").date()
                    j += 4
                elif "Pink Boll Worm:" in lines[j]:
                    result_dict["pbw_first_conducive_date"] = datetime.strptime(lines[j+1].split(": ")[1], "%Y-%m-%d").date()
                    result_dict["pbw_conducive_days"] = int(lines[j+2].split(": ")[1])
                    result_dict["pbw_highest_risk"] = float(lines[j+3].split(": ")[1].split("%")[0])
                    result_dict["pbw_highest_risk_date"] = datetime.strptime(lines[j+3].split(" on ")[1], "%Y-%m-%d").date()
                    j += 4
        elif "Historical Disease Risk Summary" in line:
            i = lines.index(line)
            j = i + 1
            while j < len(lines) and ("Bacterial Blight:" in lines[j] or "Fusarium Wilt:" in lines[j]):
                if "Bacterial Blight:" in lines[j]:
                    result_dict["bacterial_blight_first_conducive_date"] = datetime.strptime(lines[j+1].split(": ")[1], "%Y-%m-%d").date()
                    result_dict["bacterial_blight_conducive_days"] = int(lines[j+2].split(": ")[1])
                    result_dict["bacterial_blight_highest_risk"] = float(lines[j+3].split(": ")[1].split("%")[0])
                    result_dict["bacterial_blight_highest_risk_date"] = datetime.strptime(lines[j+3].split(" on ")[1], "%Y-%m-%d").date()
                    j += 4
                elif "Fusarium Wilt:" in lines[j]:
                    result_dict["fusarium_wilt_first_conducive_date"] = datetime.strptime(lines[j+1].split(": ")[1], "%Y-%m-%d").date()
                    result_dict["fusarium_wilt_conducive_days"] = int(lines[j+2].split(": ")[1])
                    result_dict["fusarium_wilt_highest_risk"] = float(lines[j+3].split(": ")[1].split("%")[0])
                    result_dict["fusarium_wilt_highest_risk_date"] = datetime.strptime(lines[j+3].split(" on ")[1], "%Y-%m-%d").date()
                    j += 4
        elif "Phenological Stage Start Dates:" in line:
            i = lines.index(line)
            j = i + 1
            while j < len(lines) and "- " in lines[j]:
                parts = lines[j].strip("  ").split(" - ")
                phase = parts[0]
                desc = parts[1].split(": ")[0]  # not used
                date_str = parts[1].split(": ")[1]
                result_dict[f"{phase.lower()}_actual_date"] = datetime.strptime(date_str, "%Y-%m-%d").date()
                j += 1
        elif "Expected Phenophase Dates" in line:
            i = lines.index(line)
            j = i + 1
            while j < len(lines) and "- " in lines[j]:
                parts = lines[j].strip("  ").split(" - ")
                phase = parts[0]
                desc = parts[1].split(": ")[0]
                date_str = parts[1].split(": ")[1]
                result_dict[f"{phase.lower()}_expected_date"] = datetime.strptime(date_str, "%Y-%m-%d").date()
                j += 1
        elif "Harvest Prediction" in line or "Crop is harvest-ready" in line:
            result_dict["harvest_prediction_text"] = line
            if "to" in line:
                dates = line.split(": ")[1].split(" to ")
                result_dict["harvest_earliest"] = datetime.strptime(dates[0], "%Y-%m-%d").date()
                result_dict["harvest_latest"] = datetime.strptime(dates[1], "%Y-%m-%d").date()

    return result_dict

# Cache for weather data (grid_id -> df)
weather_cache = {}

def fetch_weather_data_cached(start_date, end_date, grid_id, engine):
    key = grid_id
    if key in weather_cache:
        df = weather_cache[key]
        # Subset to requested range
        df = df[(df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))]
        if not df.empty:
            return df

    # Fetch broad range if not in cache (optimize: fetch from min possible to max)
    broad_start = start_date - timedelta(days=30)  # Buffer
    broad_end = end_date + timedelta(days=30)
    df = fetch_weather_data(broad_start, broad_end, grid_id)
    weather_cache[key] = df
    # Subset to exact
    df = df[(df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))]
    return df

# Main batch function
def main_batch():
    engine = setup_database()

    # Ask for question date
    while True:
        try:
            question_date_str = input("Enter question date (YYYY-MM-DD): ")
            question_date = datetime.strptime(question_date_str, "%Y-%m-%d").date()
            break
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD.")

    # Fetch all farmers
    query = """
        SELECT "Farmer ID" as farmer_id, "Farmer Name" as farmer_name, "Cluster name" as cluster_name, 
               "Grid_ID" as grid_id, grid_lat as latitude, grid_lon as longitude, 
               "Cotton sowing date ( कापसाची पेरणी त" as sowing_date
        FROM farmer_grid_mapping
    """
    df_farmers = pd.read_sql(query, engine)
    if df_farmers.empty:
        logging.error("No farmers found in database.")
        sys.exit(1)

    insects_only = False
    diseases_only = False
    risk_threshold = 40.0  # Configurable if needed

    for _, row in df_farmers.iterrows():
        farmer_id = row['farmer_id']
        farmer_name = row['farmer_name']
        cluster_name = row['cluster_name']
        grid_id = row['grid_id']
        lat = row['latitude']
        lon = row['longitude']
        sowing_date = row['sowing_date']

        if not isinstance(sowing_date, date):
            logging.warning(f"Invalid sowing date for farmer {farmer_id}: {sowing_date}")
            continue

        if question_date < sowing_date:
            logging.warning(f"Question date {question_date} before sowing {sowing_date} for farmer {farmer_id}. Skipping.")
            continue

        # Process (use dict version)
        result_dict = process_location_dict(
            sowing_date, question_date, lat, lon, grid_id, farmer_id, farmer_name, cluster_name,
            insects_only, diseases_only, risk_threshold
        )
        if not result_dict:
            continue

        result_dict["question_date"] = question_date
        result_dict["risk_threshold"] = risk_threshold

        # Remove unnecessary fields
        if "latitude" in result_dict:
            del result_dict["latitude"]
        if "longitude" in result_dict:
            del result_dict["longitude"]
        if "grid_id" in result_dict:
            del result_dict["grid_id"]

        # Convert lists to JSON for insertion
        for key in result_dict:
            if isinstance(result_dict[key], list):
                result_dict[key] = json.dumps(result_dict[key])

        # Check if row exists for farmer_id
        with engine.connect() as conn:
            exists_query = text("SELECT 1 FROM cotton_gdd_results WHERE farmer_id = :fid")
            exists = conn.execute(exists_query, {"fid": farmer_id}).fetchone()

            if exists:
                # Update existing row
                set_clause = ", ".join([f"{k} = :{k}" for k in result_dict.keys() if k != "farmer_id"])
                update_query = text(f"UPDATE cotton_gdd_results SET {set_clause} WHERE farmer_id = :farmer_id")
                conn.execute(update_query, result_dict)
                conn.commit()
                logging.info(f"Updated results for farmer {farmer_id} on {question_date}.")
            else:
                # Insert new row
                columns = ", ".join(result_dict.keys())
                placeholders = ", ".join([f":{k}" for k in result_dict.keys()])
                insert_query = text(f"INSERT INTO cotton_gdd_results ({columns}) VALUES ({placeholders})")
                conn.execute(insert_query, result_dict)
                conn.commit()
                logging.info(f"Inserted results for farmer {farmer_id} on {question_date}.")

if __name__ == "__main__":
    main_batch()