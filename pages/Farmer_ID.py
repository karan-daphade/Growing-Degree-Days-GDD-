import streamlit as st
import pandas as pd
from datetime import date, timedelta
from datetime import datetime, date
import logging
import traceback
import sys
import os

# Set page configuration as the first Streamlit command
st.set_page_config(
    page_title="Cotton GDD and Risk Analysis Dashboard",
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
    /* General styling */
    .stApp {
        background-color: #f5f6f5;
        font-family: 'Manrope', sans-serif;
    }
    
    /* Main header */
    .main-header {
        font-size: 2.5rem;
        color: #1a3c34;
        text-align: center;
        margin-bottom: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.6rem;
        color: #2e7d32;
        margin-top: 1.5rem;
        margin-bottom: 0.8rem;
        font-weight: 600;
    }
    
    /* Metric cards */
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
    
    /* Risk cards */
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
    
    /* Phenophase cards */
    .phenophase-card {
        background-color: #e8f0fe;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #1976d2;
        margin: 0.4rem 0;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    
    /* Sidebar styling */
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
    
    /* Button styling */
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
    
    /* Download button */
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
    
    /* Dataframe styling */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #e0e0e0;
    }
    .stDataFrame table {
        border-collapse: collapse;
        width: 100%;
    }
    .stDataFrame th, .stDataFrame td {
        border: 1px solid #e0e0e0;
        padding: 6px;
        text-align: left;
    }
    .stDataFrame th {
        background-color: #e8f5e9;
        font-weight: 600;
    }
    
    /* Text input and date picker */
    .stTextInput input, .stDateInput input {
        border-radius: 6px;
        border: 1px solid #bdbdbd;
        padding: 0.4rem;
    }
    
    /* Footer */
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

# Main title
st.markdown('<h1 class="main-header">🌱 Real time cotton crop status(Based on Heat Units approach)</h1>', unsafe_allow_html=True)

# Sidebar for user inputs
st.sidebar.markdown('<h2 class="sidebar-header">📊 Analysis Parameters</h2>', unsafe_allow_html=True)
farmer_id = st.sidebar.text_input("Farmer ID", value="10811", placeholder="e.g., 10811", help="Enter the unique farmer identification number")
question_date = st.sidebar.date_input("Question Date", value=date.today() - timedelta(days=1), help="Select the date for analysis")
get_result = st.sidebar.button("🔍 Run Analysis", type="primary")


# function for safe harvest window 
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


# Function to validate inputs
def validate_inputs(farmer_id, question_date):
    try:
        farmer_id = float(farmer_id)
        if not isinstance(question_date, date):
            raise ValueError("Invalid date format. Use YYYY-MM-DD.")
        logger.debug(f"Validated inputs: Farmer ID={farmer_id}, Question Date={question_date}")
        return farmer_id, question_date
    except ValueError as e:
        st.error(f"Input error: {e}")
        logger.error(f"Input validation failed: {e}")
        return None, None

# Function to fetch farmer details
def fetch_farmer_details(farmer_id):
    try:
        logger.debug("Attempting to set up database connection")
        engine = updated.setup_database()
        logger.debug("Database connection established")
        query = """
            SELECT "Farmer ID" as farmer_id, "Farmer Name" as farmer_name, "Cluster name" as cluster_name, 
                   "Grid_ID" as grid_id, grid_lat as latitude, grid_lon as longitude, 
                   "Cotton sowing date ( कापसाची पेरणी त" as sowing_date
            FROM farmer_grid_mapping 
            WHERE "Farmer ID" = %s
        """
        logger.debug(f"Executing query for Farmer ID: {farmer_id}")
        df = pd.read_sql(query, engine, params=(farmer_id,))
        if df.empty:
            st.error(f"No data found for Farmer ID: {farmer_id}")
            logger.warning(f"No data found for Farmer ID: {farmer_id}")
            return None
        logger.debug(f"Farmer data retrieved: {df.iloc[0].to_dict()}")
        return df.iloc[0]
    except Exception as e:
        st.error(f"Error fetching farmer details: {e}")
        logger.error(f"Error fetching farmer details: {traceback.format_exc()}")
        return None

# Main dashboard logic
try:
    logger.debug("Testing database connectivity")
    engine = updated.setup_database()
    st.success("✅ Database connection established successfully.")
except Exception as e:
    st.error(f"Failed to connect to database: {e}")
    logger.error(f"Database connection failed: {traceback.format_exc()}")
    st.stop()

if get_result:
    with st.spinner("Processing crop analysis..."):
        try:
            logger.debug("Processing Get Result button click")
            farmer_id_float, question_date_valid = validate_inputs(farmer_id, question_date)
            if farmer_id_float and question_date_valid:
                logger.debug(f"Fetching farmer details for ID: {farmer_id_float}")
                farmer_data = fetch_farmer_details(farmer_id_float)
                if farmer_data is not None:
                    try:
                        sowing_date = pd.to_datetime(farmer_data['sowing_date']).date()
                        lat = farmer_data['latitude']
                        lon = farmer_data['longitude']
                        grid_id = farmer_data['grid_id']
                        farmer_name = farmer_data['farmer_name']
                        cluster_name = farmer_data['cluster_name']
                        logger.debug(f"Processing location: sowing_date={sowing_date}, question_date={question_date_valid}, "
                                    f"lat={lat}, lon={lon}, grid_id={grid_id}")

                        # Call the process_location function from updated.py
                        result = updated.process_location(
                            sowing_date=sowing_date,
                            question_date=question_date_valid,
                            lat=lat,
                            lon=lon,
                            grid_id=grid_id,
                            farmer_id=farmer_id_float,
                            farmer_name=farmer_name,
                            cluster_name=cluster_name,
                            insects_only=False,
                            diseases_only=False,
                            risk_threshold=40
                        )

                        # Parse the result (assuming it's a string with sections)
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

                        # Farmer Information Section
                        st.markdown('<h2 class="section-header">👨‍🌾 Farmer Information</h2>', unsafe_allow_html=True)
                        col1, col2 = st.columns(2)
                        farmer_info = sections['farmer_info']
                        with col1:
                            st.metric("Farmer ID", farmer_info[0].split(': ')[1])
                        with col2:
                            st.metric("Sowing Date", sowing_date.strftime('%Y-%m-%d'))
                        st.markdown(f"**Farmer Name:** {farmer_name}")
                        st.markdown(f"**Cluster:** {cluster_name}")

                        # Harvest Prediction
                        st.markdown('<h2 class="section-header">🚜 Expected date of harvest</h2>', unsafe_allow_html=True)
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
                            avg_temp = current_status[4].split(': ')[1] if current_status[4].startswith('Average Temperature:') else 'N/A'
                            st.metric("Avg Temperature", avg_temp)

                        # Risk Assessment Section
                        st.markdown('<h2 class="section-header">⚠️ Risk Assessment</h2>', unsafe_allow_html=True)

                        # Pink Boll Worm Forecast
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
                            <strong>Weather Risk Score:</strong> {risk_score}
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown("**Management Recommendations:**")
                        for rec in pbw[4:]:
                            if rec.startswith('    -'):
                                st.markdown(f"• {rec[6:]}")

                        # Other Insect Risks
                        st.markdown('<h3>Other Insect Risk Alerts</h3>', unsafe_allow_html=True)
                        if sections['insect_alerts'] and sections['insect_alerts'][0] != '  No significant insect risks detected today.':
                            for alert in sections['insect_alerts']:
                                if alert.startswith('  '):
                                    st.markdown(f"<div class='metric-card risk-medium'>{alert}</div>", unsafe_allow_html=True)
                        else:
                            st.info("No significant insect risks detected today.")

                        # Disease Risk Alerts
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

                        # Historical Analysis Section
                        st.markdown('<h2 class="section-header">📊 Historical Risk Analysis</h2>', unsafe_allow_html=True)

                        # Historical Insects
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
                                    highest_risk, date = risk_part.split(' on ', 1)
                                    current_dict['Highest Risk'] = highest_risk.strip()
                                    current_dict['Date of Highest Risk'] = date.strip()
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

                        # Historical Diseases
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
                                    highest_risk, date = risk_part.split(' on ', 1)
                                    current_dict['Highest Risk'] = highest_risk.strip()
                                    current_dict['Date of Highest Risk'] = date.strip()
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

                        # Phenological Stages Section
                        st.markdown('<h2 class="section-header">🌱 Crop Development Timeline</h2>', unsafe_allow_html=True)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown('<h3>Completed Stages</h3>', unsafe_allow_html=True)
                            logger.debug(f"Raw phenological_stages: {sections['phenological_stages']}")
                            parsed_stages = 0
                            for index, stage in enumerate(sections['phenological_stages'], start=0):
                                stripped_stage = stage.strip()
                                logger.debug(f"Processing completed stage {index}: '{stripped_stage}'")
                                if stripped_stage:
                                    try:
                                        # Split on ' - ' to separate stage code and description
                                        stage_parts = stripped_stage.split(' - ', 1)
                                        if len(stage_parts) != 2:
                                            logger.warning(f"Skipping completed stage {index}: Invalid format in '{stripped_stage}'")
                                            continue
                                        stage_code_desc, date = stage_parts[1].rsplit(': ', 1)
                                        stage_code = stage_parts[0].strip()
                                        stage_desc = stage_code_desc.strip()
                                        date = date.strip()
                                        if stage_code and stage_desc and date:
                                            logger.debug(f"Parsed completed stage: {stage_code} - {stage_desc}, Date: {date}")
                                            st.markdown(f"""
                                            <div class="phenophase-card">
                                                <strong>{stage_code} - {stage_desc}</strong><br>
                                                Date: {date}
                                            </div>
                                            """, unsafe_allow_html=True)
                                            parsed_stages += 1
                                        else:
                                            logger.warning(f"Skipping completed stage {index}: Missing stage_code, stage_desc, or date in '{stripped_stage}'")
                                    except ValueError as e:
                                        logger.warning(f"Failed to parse completed stage {index}: '{stripped_stage}', Error: {e}")
                                else:
                                    logger.warning(f"Skipping empty completed stage {index}")
                            if parsed_stages == 0:
                                st.warning("No completed phenological stages found. Please check the data source.")
                                logger.warning("No valid completed stages parsed from phenological_stages")

                        with col2:
                            st.markdown('<h3>Expected Future Stages</h3>', unsafe_allow_html=True)
                            logger.debug(f"Raw expected_stages: {sections['expected_stages']}")
                            parsed_expected_stages = 0
                            for index, stage in enumerate(sections['expected_stages'], start=0):
                                stripped_stage = stage.strip()
                                logger.debug(f"Processing expected stage {index}: '{stripped_stage}'")
                                if stripped_stage:
                                    try:
                                        # Split on ' - ' to separate stage code and description
                                        stage_parts = stripped_stage.split(' - ', 1)
                                        if len(stage_parts) != 2:
                                            logger.warning(f"Skipping expected stage {index}: Invalid format in '{stripped_stage}'")
                                            continue
                                        stage_code_desc, date = stage_parts[1].rsplit(': ', 1)
                                        stage_code = stage_parts[0].strip()
                                        stage_desc = stage_code_desc.strip()
                                        date = date.strip()
                                        if stage_code and stage_desc and date:
                                            logger.debug(f"Parsed expected stage: {stage_code} - {stage_desc}, Date: {date}")
                                            st.markdown(f"""
                                            <div class="metric-card">
                                                <strong>{stage_code} - {stage_desc}</strong><br>
                                                Expected: {date}
                                            </div>
                                            """, unsafe_allow_html=True)
                                            parsed_expected_stages += 1
                                        else:
                                            logger.warning(f"Skipping expected stage {index}: Missing stage_code, stage_desc, or date in '{stripped_stage}'")
                                    except ValueError as e:
                                        logger.warning(f"Failed to parse expected stage {index}: '{stripped_stage}', Error: {e}")
                                else:
                                    logger.warning(f"Skipping empty expected stage {index}")
                            if parsed_expected_stages == 0:
                                st.warning("No expected future phenological stages found. Please check the data source.")
                                logger.warning("No valid expected stages parsed from expected_stages")

                        # Download button for the report
                        report_filename = f"report_{farmer_id_float}.txt"
                        st.download_button(
                            label=f"📥 Download Report ({report_filename})",
                            data=result,
                            file_name=report_filename,
                            mime="text/plain"
                        )
                    except Exception as e:
                        st.error(f"Error processing analysis: {e}")
                        logger.error(f"Error in process_location: {traceback.format_exc()}")
        except Exception as e:
            st.error(f"Unexpected error during processing: {e}")
            logger.error(f"Unexpected error: {traceback.format_exc()}")
elif get_result:
    st.warning("Please enter both Farmer ID and Question Date to run the analysis.")

# Sidebar information
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