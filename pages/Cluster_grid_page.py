import streamlit as st
from datetime import date, timedelta
import pandas as pd
from datetime import datetime, date
import logging
import traceback
import sys
import os
import uuid

# Set page configuration as the first Streamlit command
st.set_page_config(
    page_title="Cotton GDD and Risk Analysis Dashboard - Cluster Grid Mode",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import Google Fonts
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">',
    unsafe_allow_html=True
)

# Ensure updated.py is in the same directory
try:
    import updated
except ImportError as e:
    st.error(f"Failed to import updated.py: {e}")
    st.error("Ensure updated.py is in the same directory as this script.")
    st.stop()

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Log initial setup
logger.debug(f"Python version: {sys.version}")
logger.debug(f"Current working directory: {os.getcwd()}")
logger.debug(f"Streamlit version: {st.__version__}")
logger.debug("Streamlit page configuration set")

# Custom CSS for enhanced UI
st.markdown("""
<style>
    .stApp {
        background-color: #f5f6f5;
        font-family: 'Manrope', sans-serif;
    }
    .main-header {
        font-size: 2.5rem;
        color: #1a3c34;
        text-align: center;
        margin-bottom: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .section-header {
        font-size: 1.6rem;
        color: #2e7d32;
        margin-top: 1.5rem;
        margin-bottom: 0.8rem;
        font-weight: 600;
    }
    .metric-card {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #4caf50;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        margin: 0.4rem 0;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
    }
    .risk-high {
        background-color: #fff1f0;
        border-left-color: #d32f2f;
    }
    .risk-medium {
        background-color: #fff3e0;
        border-left-color: #f57c00;
    }
    .risk-low {
        background-color: #e8f5e9;
        border-left-color: #388e3c;
    }
    .phenophase-card {
        background-color: #e8f0fe;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #1976d2;
        margin: 0.4rem 0;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    .sidebar .sidebar-content {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
        padding: 1.2rem;
    }
    .sidebar-header {
        font-size: 1.4rem;
        color: #1a3c34;
        font-weight: 600;
        margin-bottom: 1.2rem;
    }
    .stButton>button {
        background-color: #4caf50;
        color: white;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: background-color 0.2s;
    }
    .stButton>button:hover {
        background-color: #388e3c;
    }
    .stDownloadButton>button {
        background-color: #0288d1;
        color: white;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    .stDownloadButton>button:hover {
        background-color: #0277bd;
    }
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #e0e0e0;
    }
    .stDataFrame th {
        background-color: #e8f5e9;
        font-weight: 600;
    }
    .stTextInput input, .stDateInput input {
        border-radius: 6px;
        border: 1px solid #bdbdbd;
        padding: 0.4rem;
    }
    .footer {
        text-align: center;
        color: #616161;
        font-size: 0.85rem;
        margin-top: 1.5rem;
        padding: 0.8rem 0;
        border-top: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Session State ----------
if 'selected_cluster' not in st.session_state:
    st.session_state.selected_cluster = None
if 'selected_grid' not in st.session_state:
    st.session_state.selected_grid = None
if 'selected_sowing_option' not in st.session_state:
    st.session_state.selected_sowing_option = None
if 'question_date' not in st.session_state:
    st.session_state.question_date = date.today() - timedelta(days=1)
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False
if 'sowing_options' not in st.session_state:
    st.session_state.sowing_options = []
if 'selected_sowing_date' not in st.session_state:
    st.session_state.selected_sowing_date = None
if 'farmer_count' not in st.session_state:
    st.session_state.farmer_count = 0

# ---------- Title ----------
st.markdown('<h1 class="main-header">🌱 Real-time Cotton Crop Status (Based on Heat Units Approach) - Cluster Grid Mode</h1>', unsafe_allow_html=True)

# ---------- Sidebar ----------
st.sidebar.markdown('<h2 class="sidebar-header">📊 Analysis Parameters</h2>', unsafe_allow_html=True)

# Fetch clusters
try:
    engine = updated.setup_database()
    query_clusters = """
        SELECT DISTINCT "Cluster name" as cluster_name
        FROM farmer_grid_mapping
        ORDER BY cluster_name
    """
    df_clusters = pd.read_sql(query_clusters, engine)
    clusters = df_clusters['cluster_name'].dropna().unique().tolist()
except Exception as e:
    st.error(f"Error fetching clusters: {e}")
    logger.error(f"Error fetching clusters: {traceback.format_exc()}")
    clusters = []

# Cluster selection
if not clusters:
    st.warning("No clusters found in the database.")
else:
    st.session_state.selected_cluster = st.sidebar.selectbox(
        "Select Cluster",
        clusters,
        index=clusters.index(st.session_state.selected_cluster) if st.session_state.selected_cluster in clusters else 0,
        key="cluster_select"
    )

    # Fetch grids for selected cluster
    try:
        query_grids = """
            SELECT DISTINCT "Grid_ID" as grid_id
            FROM farmer_grid_mapping
            WHERE "Cluster name" = %s
            ORDER BY grid_id
        """
        df_grids = pd.read_sql(query_grids, engine, params=(st.session_state.selected_cluster,))
        grids = df_grids['grid_id'].dropna().unique().tolist()
    except Exception as e:
        st.error(f"Error fetching grids for cluster {st.session_state.selected_cluster}: {e}")
        logger.error(f"Error fetching grids: {traceback.format_exc()}")
        grids = []

    # Grid selection
    if not grids:
        st.warning(f"No grids found for cluster {st.session_state.selected_cluster}.")
    else:
        st.session_state.selected_grid = st.sidebar.selectbox(
            "Select Grid ID",
            grids,
            index=grids.index(st.session_state.selected_grid) if st.session_state.selected_grid in grids else 0,
            key="grid_select"
        )

# Date input
st.session_state.question_date = st.sidebar.date_input(
    "Question Date",
    value=st.session_state.question_date,
    help="Select the date for analysis",
    key="date_input"
)

# Run analysis button
if st.sidebar.button("🔍 Run Analysis", type="primary"):
    st.session_state.run_analysis = True
    st.session_state.selected_sowing_option = None  # reset
    st.session_state.selected_sowing_date = None
    st.session_state.farmer_count = 0

# Validate inputs
def validate_inputs(question_date):
    try:
        if not isinstance(question_date, date):
            raise ValueError("Invalid date format. Use YYYY-MM-DD.")
        logger.debug(f"Validated inputs: Question Date={question_date}")
        return question_date
    except ValueError as e:
        st.error(f"Input error: {e}")
        logger.error(f"Input validation failed: {e}")
        return None

# ---------- MAIN ----------
try:
    engine = updated.setup_database()
    st.success("✅ Database connection established successfully.")
except Exception as e:
    st.error(f"Failed to connect to database: {e}")
    logger.error(f"Database connection failed: {traceback.format_exc()}")
    st.stop()

def _safe_harvest_window_from_prediction(pred_list):
    """
    updated.predict_harvest_dates returns a list of strings like:
    'Harvest Prediction (25°C avg temp, 9.4 GDD/day): YYYY-MM-DD to YYYY-MM-DD'
    Return the date window string, or the whole string if parsing is uncertain.
    """
    if not pred_list:
        return "NA"
    s = pred_list[0]
    if ": " in s:
        return s.split(": ", 1)[1].strip()
    return s

if st.session_state.run_analysis and st.session_state.selected_grid:
    with st.spinner("Processing crop analysis..."):
        try:
            question_date_valid = validate_inputs(st.session_state.question_date)
            if question_date_valid:
                # --- Fetch sowing dates + farmer counts for the whole grid
                query_sowings = """
                    SELECT "Cotton sowing date ( कापसाची पेरणी त" as sowing_date, 
                           COUNT(DISTINCT "Farmer ID") as farmer_count
                    FROM farmer_grid_mapping
                    WHERE "Grid_ID" = %s
                    GROUP BY sowing_date
                    ORDER BY sowing_date
                """
                df_sowings = pd.read_sql(query_sowings, engine, params=(st.session_state.selected_grid,))
                df_sowings = df_sowings.dropna(subset=['sowing_date'])

                if df_sowings.empty:
                    st.error("No sowing dates found for this grid.")
                else:
                    # Get single lat/lon for grid
                    query_latlon = """
                        SELECT grid_lat as latitude, grid_lon as longitude
                        FROM farmer_grid_mapping
                        WHERE "Grid_ID" = %s
                        LIMIT 1
                    """
                    df_latlon = pd.read_sql(query_latlon, engine, params=(st.session_state.selected_grid,))
                    if df_latlon.empty:
                        st.error("No location data found for this grid.")
                        st.stop()
                    lat = df_latlon['latitude'].iloc[0]
                    lon = df_latlon['longitude'].iloc[0]

                    # ---------- GRID SUMMARY (TOP TABLE) ----------
                    # Build one row per sowing date: Sowing date | Number of farmers | Current crop stage | Harvest date
                    summary_rows = []
                    for _, row in df_sowings.iterrows():
                        sow_date = pd.to_datetime(row['sowing_date']).date()
                        n_farmers = int(row['farmer_count'])

                        # Determine sowing window & phenophase thresholds
                        sowing_window = updated.determine_sowing_window(sow_date)
                        if not sowing_window:
                            current_stage_str = "Outside sowing window"
                            harvest_str = "NA"
                        else:
                            p4_gdd_threshold = updated.phenophase_thresholds[sowing_window]['P4'][0]
                            # Update GDD up to the chosen question date
                            cumulative_gdd, p4_start_date, pbw_gdd, total_rainfall, avg_temp, weather_data, phenophase_dates = \
                                updated.update_gdd(sow_date, question_date_valid, p4_gdd_threshold, st.session_state.selected_grid, sowing_window)

                            # Current phenophase
                            phen_code, phen_desc = updated.get_current_phenophase(cumulative_gdd, sow_date)
                            if phen_code is None:
                                current_stage_str = "Unknown"
                            else:
                                current_stage_str = f"{phen_code} - {phen_desc}"

                            # Harvest window (based on 25°C assumption)
                            harvest_list = updated.predict_harvest_dates(cumulative_gdd, sowing_window, question_date_valid)
                            harvest_str = _safe_harvest_window_from_prediction(harvest_list)

                        summary_rows.append({
                            "Sowing date": sow_date.strftime("%Y-%m-%d"),
                            "Number of farmers": n_farmers,
                            "Current crop stage": current_stage_str,
                            "Harvest date": harvest_str
                        })

                    df_summary = pd.DataFrame(summary_rows, columns=["Sowing date", "Number of farmers", "Current crop stage", "Harvest date"])

                    st.markdown('<h2 class="section-header">🧭 Grid Summary</h2>', unsafe_allow_html=True)
                    st.dataframe(df_summary, use_container_width=True)

                    # ---------- Continue with existing per-sowing-date analysis flow ----------
                    st.session_state.sowing_options = [
                        f"{pd.to_datetime(r['sowing_date']).strftime('%Y-%m-%d')} ({int(r['farmer_count'])} farmers)"
                        for _, r in df_sowings.iterrows()
                    ]

                    st.session_state.selected_sowing_option = st.selectbox(
                        "Select Sowing Date",
                        st.session_state.sowing_options,
                        index=st.session_state.sowing_options.index(st.session_state.selected_sowing_option) if st.session_state.selected_sowing_option in st.session_state.sowing_options else 0,
                        key="sowing_select"
                    )

                    if st.session_state.selected_sowing_option:
                        # Extract sowing date and farmer count
                        selected_sowing_str = st.session_state.selected_sowing_option.split(' (')[0]
                        st.session_state.selected_sowing_date = datetime.strptime(selected_sowing_str, '%Y-%m-%d').date()
                        st.session_state.farmer_count = int(st.session_state.selected_sowing_option.split('(')[1].split(' ')[0])

                        # Dummy farmer_id and name
                        farmer_id_float = 0.0
                        farmer_name = f"Grid Analysis for {st.session_state.selected_grid}"

                        # Call process_location from updated.py
                        result = updated.process_location(
                            sowing_date=st.session_state.selected_sowing_date,
                            question_date=question_date_valid,
                            lat=lat,
                            lon=lon,
                            grid_id=st.session_state.selected_grid,
                            farmer_id=farmer_id_float,
                            farmer_name=farmer_name,
                            cluster_name=st.session_state.selected_cluster,
                            insects_only=False,
                            diseases_only=False,
                            risk_threshold=40
                        )

                        # Parse the result
                        sections = {
                            'farmer_info': [],
                            'current_status': [],
                            'pbw_forecast': [],
                            'insect_alerts': [],
                            'disease_alerts': [],
                            'historical_insects': [],
                            'historical_diseases': [],
                            'phenological_stages': [],
                            'expected_stages': [],
                            'harvest_prediction': []
                        }
                        current_section = None
                        for line in result.split('\n'):
                            line = line.strip()
                            if line.startswith('Farmer ID:') or line.startswith('Farmer Name:') or line.startswith('Cluster Name:') or line.startswith('Grid ID:'):
                                sections['farmer_info'].append(line)
                            elif line.startswith('Analysis for Lat=') or line.startswith('Current Phenophase:') or line.startswith('Cumulative GDD:') or line.startswith('Total Rainfall since Sowing:') or line.startswith('Average Temperature'):
                                sections['current_status'].append(line)
                            elif line.startswith('Pink Boll Worm (PBW) Forecast:'):
                                current_section = 'pbw_forecast'
                            elif line.startswith('Insect Risk Alerts (Excluding PBW):'):
                                current_section = 'insect_alerts'
                            elif line.startswith('Disease Risk Alerts:'):
                                current_section = 'disease_alerts'
                            elif line.startswith('Historical Insect Risk Summary'):
                                current_section = 'historical_insects'
                            elif line.startswith('Historical Disease Risk Summary'):
                                current_section = 'historical_diseases'
                            elif line.startswith('Phenological Stage Start Dates:'):
                                current_section = 'phenological_stages'
                            elif line.startswith('Expected Phenophase Dates'):
                                current_section = 'expected_stages'
                            elif line.startswith('Harvest Prediction'):
                                sections['harvest_prediction'].append(line)
                            elif current_section and line:
                                sections[current_section].append(line)

                        # Grid Information Section
                        st.markdown('<h2 class="section-header">📍 Grid Information</h2>', unsafe_allow_html=True)
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Cluster", st.session_state.selected_cluster)
                        with col2:
                            st.metric("Grid ID", st.session_state.selected_grid)
                        with col3:
                            st.metric("Sowing Date", st.session_state.selected_sowing_date.strftime('%Y-%m-%d'))
                        st.metric("Number of Farmers", st.session_state.farmer_count)

                        # Fetch and display farmers table
                        query_farmers = """
                            SELECT "Farmer ID" as farmer_id, "Farmer Name" as farmer_name
                            FROM farmer_grid_mapping
                            WHERE "Grid_ID" = %s AND "Cotton sowing date ( कापसाची पेरणी त" = %s
                            ORDER BY farmer_id
                        """
                        df_farmers = pd.read_sql(query_farmers, engine, params=(st.session_state.selected_grid, st.session_state.selected_sowing_date))
                        st.markdown("**Farmers in this Grid and Sowing Date:**")
                        st.dataframe(df_farmers, use_container_width=True)

                        # Harvest Prediction
                        st.markdown('<h2 class="section-header">🚜 Expected Date of Harvest</h2>', unsafe_allow_html=True)
                        st.markdown(f"""
                        <div class="metric-card" style="border-left-color: #ff6b35; background-color: #fff8e1;">
                            <h3>🗓️ Harvest Window</h3>
                            <strong>{_safe_harvest_window_from_prediction(sections.get('harvest_prediction', []))}</strong>
                            <br><small>Based on 25°C average temperature and 9.4 GDD/day</small>
                        </div>
                        """, unsafe_allow_html=True)

                        # Current Status Section
                        st.markdown('<h2 class="section-header">📈 Current Crop Status</h2>', unsafe_allow_html=True)
                        col1, col2, col3, col4 = st.columns(4)
                        current_status = sections['current_status']
                        with col1:
                            st.metric("Current Phenophase", current_status[1].split(': ')[1])
                        with col2:
                            st.metric("Cumulative GDD", current_status[2].split(': ')[1])
                        with col3:
                            st.metric("Total Rainfall", current_status[3].split(': ')[1])
                        with col4:
                            avg_temp = current_status[4].split(': ')[1] if len(current_status) > 4 and current_status[4].startswith('Average Temperature:') else 'N/A'
                            st.metric("Avg Temperature", avg_temp)

                        # Risk Assessment
                        st.markdown('<h2 class="section-header">⚠️ Risk Assessment</h2>', unsafe_allow_html=True)

                        # PBW
                        st.markdown('<h3>Pink Boll Worm (PBW) Forecast</h3>', unsafe_allow_html=True)
                        pbw = sections['pbw_forecast']
                        risk_level = next((line.split(': ')[1] for line in pbw if line.startswith('  Risk Level:')), 'Low')
                        risk_score = next((line.split(': ')[1] for line in pbw if line.startswith('  Weather-Based Risk Score:')), '0.0%')
                        risk_class = "risk-low" if risk_level == 'Low' else "risk-medium" if risk_level == 'Medium' else "risk-high"
                        st.markdown(f"""
                        <div class="metric-card {risk_class}">
                            <strong>Stage:</strong> {pbw[1].split(': ')[1]}<br>
                            <strong>Generation:</strong> {pbw[2].split(': ')[1]}<br>
                            <strong>Risk Level:</strong> {risk_level}<br>
                            <strong>Weather-Based Risk Score:</strong> {risk_score}
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown("**Management Recommendations:**")
                        for rec in pbw[4:]:
                            if rec.startswith('    -'):
                                st.markdown(f"• {rec[6:]}")

                        # Other Insects
                        st.markdown('<h3>Other Insect Risk Alerts</h3>', unsafe_allow_html=True)
                        if sections['insect_alerts'] and sections['insect_alerts'][0] != '  No significant insect risks detected today.':
                            for alert in sections['insect_alerts']:
                                if alert.startswith('  '):
                                    st.markdown(f"<div class='metric-card risk-medium'>{alert}</div>", unsafe_allow_html=True)
                        else:
                            st.info("No significant insect risks detected today.")

                        # Diseases
                        st.markdown('<h3>Disease Risk Alerts</h3>', unsafe_allow_html=True)
                        if sections['disease_alerts'] and sections['disease_alerts'][0] != '  No significant disease risks detected today.':
                            for alert in sections['disease_alerts']:
                                if alert.startswith('  ') and '(Risk Score:' in alert:
                                    disease_name = alert.split(' (')[0][2:]
                                    risk_score = alert.split('Risk Score: ')[1].split('%)')[0]
                                    risk_class = "risk-high" if float(risk_score) >= 70 else "risk-medium" if float(risk_score) >= 40 else "risk-low"
                                    st.markdown(f"""
                                    <div class="metric-card {risk_class}">
                                        <strong>{disease_name}</strong> (Risk Score: {risk_score}%)
                                    </div>
                                    """, unsafe_allow_html=True)
                                elif alert.startswith('    -'):
                                    st.markdown(f"• {alert[6:]}")
                        else:
                            st.info("No significant disease risks detected today.")

                        # Historical
                        st.markdown('<h2 class="section-header">📊 Historical Risk Analysis</h2>', unsafe_allow_html=True)

                        # Historical insects
                        st.markdown('<h3>Historical Insect Risks</h3>', unsafe_allow_html=True)
                        insect_data = []
                        current_insect = None
                        current_dict = {}
                        for line in sections['historical_insects']:
                            stripped_line = line.strip()
                            if stripped_line.startswith('Historical Insect Risk Summary'):
                                continue
                            if not stripped_line.startswith('First Conducive Date:') and not stripped_line.startswith('Conducive Days:') and not stripped_line.startswith('Highest Risk:'):
                                if current_insect and current_dict and 'Conducive Days' in current_dict:
                                    insect_data.append(current_dict)
                                current_insect = stripped_line[:-1].strip() if stripped_line.endswith(':') else stripped_line.strip()
                                if current_insect.startswith('No '):
                                    current_insect = None
                                    continue
                                current_dict = {'Insect': current_insect}
                            elif stripped_line.startswith('First Conducive Date:'):
                                current_dict['First Conducive Date'] = stripped_line.split(': ', 1)[1].strip()
                            elif stripped_line.startswith('Conducive Days:'):
                                current_dict['Conducive Days'] = stripped_line.split(': ', 1)[1].strip()
                            elif stripped_line.startswith('Highest Risk:'):
                                risk_part = stripped_line.split(': ', 1)[1].strip()
                                if ' on ' in risk_part:
                                    highest_risk, dte = risk_part.split(' on ', 1)
                                    current_dict['Highest Risk'] = highest_risk.strip()
                                    current_dict['Date of Highest Risk'] = dte.strip()
                                else:
                                    current_dict['Highest Risk'] = risk_part
                                    current_dict['Date of Highest Risk'] = ''
                        if current_insect and current_dict and 'Conducive Days' in current_dict:
                            insect_data.append(current_dict)
                        if insect_data:
                            df_insects = pd.DataFrame(insect_data, columns=['Insect', 'First Conducive Date', 'Conducive Days', 'Highest Risk', 'Date of Highest Risk'])
                            st.dataframe(df_insects, use_container_width=True)
                        else:
                            st.info("No historical insect risks above 40% threshold.")

                        # Historical diseases
                        st.markdown('<h3>Historical Disease Risks</h3>', unsafe_allow_html=True)
                        disease_data = []
                        current_disease = None
                        current_dict = {}
                        for line in sections['historical_diseases']:
                            stripped_line = line.strip()
                            if stripped_line.startswith('Historical Disease Risk Summary'):
                                continue
                            if not stripped_line.startswith('First Conducive Date:') and not stripped_line.startswith('Conducive Days:') and not stripped_line.startswith('Highest Risk:'):
                                if current_disease and current_dict and 'Conducive Days' in current_dict:
                                    disease_data.append(current_dict)
                                current_disease = stripped_line[:-1].strip() if stripped_line.endswith(':') else stripped_line.strip()
                                if current_disease.startswith('No '):
                                    current_disease = None
                                    continue
                                current_dict = {'Disease': current_disease}
                            elif stripped_line.startswith('First Conducive Date:'):
                                current_dict['First Conducive Date'] = stripped_line.split(': ', 1)[1].strip()
                            elif stripped_line.startswith('Conducive Days:'):
                                current_dict['Conducive Days'] = stripped_line.split(': ', 1)[1].strip()
                            elif stripped_line.startswith('Highest Risk:'):
                                risk_part = stripped_line.split(': ', 1)[1].strip()
                                if ' on ' in risk_part:
                                    highest_risk, dte = risk_part.split(' on ', 1)
                                    current_dict['Highest Risk'] = highest_risk.strip()
                                    current_dict['Date of Highest Risk'] = dte.strip()
                                else:
                                    current_dict['Highest Risk'] = risk_part
                                    current_dict['Date of Highest Risk'] = ''
                        if current_disease and current_dict and 'Conducive Days' in current_dict:
                            disease_data.append(current_dict)
                        if disease_data:
                            df_diseases = pd.DataFrame(disease_data, columns=['Disease', 'First Conducive Date', 'Conducive Days', 'Highest Risk', 'Date of Highest Risk'])
                            st.dataframe(df_diseases, use_container_width=True)
                        else:
                            st.info("No historical disease risks above 40% threshold.")

                        # Phenology
                        st.markdown('<h2 class="section-header">🌱 Crop Development Timeline</h2>', unsafe_allow_html=True)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown('<h3>Completed Stages</h3>', unsafe_allow_html=True)
                            parsed_stages = 0
                            for stage in sections['phenological_stages']:
                                stripped_stage = stage.strip()
                                if stripped_stage:
                                    try:
                                        stage_parts = stripped_stage.split(' - ', 1)
                                        if len(stage_parts) != 2:
                                            continue
                                        stage_code_desc, dte = stage_parts[1].rsplit(': ', 1)
                                        stage_code = stage_parts[0].strip()
                                        stage_desc = stage_code_desc.strip()
                                        dte = dte.strip()
                                        if stage_code and stage_desc and dte:
                                            st.markdown(f"""
                                            <div class="phenophase-card">
                                                <strong>{stage_code} - {stage_desc}</strong><br>
                                                Date: {dte}
                                            </div>
                                            """, unsafe_allow_html=True)
                                            parsed_stages += 1
                                    except ValueError:
                                        pass
                            if parsed_stages == 0:
                                st.warning("No completed phenological stages found.")

                        with col2:
                            st.markdown('<h3>Expected Future Stages</h3>', unsafe_allow_html=True)
                            parsed_expected_stages = 0
                            for stage in sections['expected_stages']:
                                stripped_stage = stage.strip()
                                if stripped_stage:
                                    try:
                                        stage_parts = stripped_stage.split(' - ', 1)
                                        if len(stage_parts) != 2:
                                            continue
                                        stage_code_desc, dte = stage_parts[1].rsplit(': ', 1)
                                        stage_code = stage_parts[0].strip()
                                        stage_desc = stage_code_desc.strip()
                                        dte = dte.strip()
                                        if stage_code and stage_desc and dte:
                                            st.markdown(f"""
                                            <div class="metric-card">
                                                <strong>{stage_code} - {stage_desc}</strong><br>
                                                Expected: {dte}
                                            </div>
                                            """, unsafe_allow_html=True)
                                            parsed_expected_stages += 1
                                    except ValueError:
                                        pass
                            if parsed_expected_stages == 0:
                                st.warning("No expected future phenological stages found.")

                        # Download button
                        report_filename = f"report_grid_{st.session_state.selected_grid}_sowing_{st.session_state.selected_sowing_date.strftime('%Y-%m-%d')}.txt"
                        st.download_button(
                            label=f"📥 Download Report ({report_filename})",
                            data=result,
                            file_name=report_filename,
                            mime="text/plain"
                        )
        except Exception as e:
            st.error(f"Unexpected error during processing: {e}")
            logger.error(f"Unexpected error: {traceback.format_exc()}")

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.markdown('<h2 class="sidebar-header">ℹ️ About</h2>', unsafe_allow_html=True)
st.sidebar.info("""
This dashboard provides comprehensive cotton crop analysis including:
- Current crop status and phenophase
- Pest and disease risk assessments
- Historical risk summaries
- Phenological stage tracking
- Harvest predictions
""")

# Footer
st.markdown('<div class="footer">Cotton Crop Analysis Dashboard - Built with Streamlit 🌱</div>', unsafe_allow_html=True)
