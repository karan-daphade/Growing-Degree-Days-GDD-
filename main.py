import streamlit as st
import logging
import sys
import os

# Set page configuration
st.set_page_config(
    page_title="Cotton Crop Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# Import Google Fonts
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">',
    unsafe_allow_html=True
)

# Custom CSS (aligned with cluster_grid_page.py)
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
    .stSelectbox div[data-baseweb="select"] > div {
        border-radius: 6px;
        border: 1px solid #bdbdbd;
        padding: 0.4rem;
    }
    .welcome-message {
        font-size: 1.2rem;
        color: #616161;
        text-align: center;
        margin-top: 2rem;
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

# Initialize session state
if 'analysis_mode' not in st.session_state:
    st.session_state.analysis_mode = "Farmer ID wise"

# Main title
st.markdown('<h1 class="main-header">🌱 Real-time Cotton Crop Status (Based on Heat Units Approach)</h1>', unsafe_allow_html=True)

# Sidebar for mode selection
st.sidebar.markdown('<h2 class="sidebar-header">📊 Analysis Mode</h2>', unsafe_allow_html=True)
st.session_state.analysis_mode = st.sidebar.selectbox(
    "Select Analysis Mode",
    ["Farmer ID wise", "Cluster + Grid ID wise"],
    index=0 if st.session_state.analysis_mode == "Cluster + Grid ID wise" else 1,
    key="mode_select"
)

# Sidebar information
st.sidebar.markdown("---")
st.sidebar.markdown('<h2 class="sidebar-header">ℹ️ About</h2>', unsafe_allow_html=True)
st.sidebar.info("""
Welcome to the Cotton Crop Dashboard! Choose an analysis mode:
- **Farmer ID wise**: Analyze crop status for individual farmers.
- **Cluster + Grid ID wise**: Analyze crop status for groups of farmers in specific clusters and grids.
""")

# Redirect to the selected page
try:
    if st.session_state.analysis_mode == "Farmer ID wise":
        if os.path.exists("pages/Farmer_ID.py"):
            logger.debug("Switching to Farmer_ID.py")
            st.switch_page("pages/Farmer_ID.py")
        else:
            st.error("Error: Farmer_ID.py not found in the pages directory.")
            logger.error("Farmer_ID.py not found")
    else:
        if os.path.exists("pages/Cluster_grid_page.py"):
            logger.debug("Switching to Cluster_grid_page.py")
            st.switch_page("pages/Cluster_grid_page.py")
        else:
            st.error("Error: Cluster_grid_page.py not found in the pages directory.")
            logger.error("Cluster_grid_page.py not found")
except Exception as e:
    st.error(f"Error switching page: {e}")
    logger.error(f"Page switch error: {e}")

# Placeholder content (shown only if page switch fails)
st.markdown('<div class="welcome-message">Welcome! Select an analysis mode from the sidebar to begin analyzing cotton crop data.</div>', unsafe_allow_html=True)

# Footer
st.markdown('<div class="footer">Cotton Crop Analysis Dashboard - Built with Streamlit 🌱</div>', unsafe_allow_html=True)