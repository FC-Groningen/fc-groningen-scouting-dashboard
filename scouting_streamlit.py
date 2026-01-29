# Scouting app
# 0. Import packages
import base64
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
from PIL import Image
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from supabase import create_client, Client

# 1. HELP FUNCTIONS
# 1.1 Check whether password is incorrect
def check_password():
    """Returns `True` if the user has entered the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if "APP_PASSWORD" not in st.secrets:

            # Password is not stored in secrets
            st.error("Wachtwoord is niet juist opgeslagen. Neem contact op met Arno de Jong of Bram van de Water.")
            return
        
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True

            # Make sure password is not stored
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:

        # Password is not yet created
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.write("Neem contact met Arno de Jong of Bram van de Water voor toegang")
        return False
    
    elif not st.session_state["password_correct"]:

        # Password is incorrect
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("Wachtwoord is onjuist.")
        return False
    else:

        # Password is correct
        return True

# 1.2 Check whether all metrics used for a position are defined correctly    
def validate_profiles(metrics, profiles):
    """Returns an error message if a metric is not defined."""
    for pos, keys in profiles.items():
        for key in keys:
            if key not in metrics:
                raise KeyError(f"'{key}' in position '{pos}' is not defined.")

# X. METRICS AND POSITION_PROFILES
# Enumeration of metric categories
class MetricCategory(str, Enum):
    PHYSICAL = "physical"
    ATTACK = "attack"
    DEFENSE = "defense"

# Single metric definition
@dataclass(frozen=True)
class Metric:
    category: MetricCategory
    label: str

# Set metric variables
metrics = {

    # Physical metrics
    "total_distance_p90_percentile": Metric(category=MetricCategory.PHYSICAL,label="Totale\nafstand"),
    "running_distance_p90_percentile": Metric(category=MetricCategory.PHYSICAL, label="15–20km/u\nafstand"),
    "hsr_distance_p90_percentile": Metric(category=MetricCategory.PHYSICAL,label="20-25km/u\nafstand"),
    "sprint_distance_p90_percentile": Metric(category=MetricCategory.PHYSICAL, label="25+km/u\nafstand"),
    "hi_distance_p90_percentile": Metric(category=MetricCategory.PHYSICAL,label="20+km/u\nafstand"),
    "total_minutes_percentile": Metric(category=MetricCategory.PHYSICAL, label="Totale\nspeeltijd"),

    # Attacking metrics
    "bypass_midfield_defense_tip_p30_percentile": Metric(category=MetricCategory.ATTACK,label="Uitgespeelde\ntegenstanders"),
    "bypass_midfield_defense_pass_tip_p30_percentile": Metric(category=MetricCategory.ATTACK, label="Uitgespeelde\ntegenstanders\n(pass)"),
    "bypass_midfield_defense_dribble_tip_p30_percentile": Metric(category=MetricCategory.ATTACK,label="Uitgespeelde\ntegenstanders\n(dribbel)"),
    "bypass_opponents_rec_tip_p30_percentile": Metric(category=MetricCategory.ATTACK, label="Uitgespeelde\ntegenstanders\nals ontvanger"),
    "involvement_chances_tip_p30_percentile": Metric(category=MetricCategory.ATTACK,label="Betrokkenheid\nkansen"),
    "off_ball_runs_total_tip_p30_percentile": Metric(category=MetricCategory.ATTACK, label="Loopacties\nzonder bal"),

    # Defending metrics
    "ball_win_removed_opponents_otip_p30_percentile": Metric(category=MetricCategory.DEFENSE,label="Aanvallende\nveroveringen"),
    "ball_win_added_teammates_otip_p30_percentile": Metric(category=MetricCategory.DEFENSE, label="Verdedigende\nveroveringen"),
    "ground_duels_won_p90_percentile": Metric(category=MetricCategory.DEFENSE,label="Gewonnen\ngrondduels"),
    "ground_duels_won_percentage_percentile": Metric(category=MetricCategory.DEFENSE, label="Winstpercentage\ngrondduels"),
    "aerial_duels_won_p90_percentile": Metric(category=MetricCategory.DEFENSE, label="Gewonnen\nluchtduels"),
    "aerial_duels_won_percentage_percentile": Metric(category=MetricCategory.DEFENSE, label="Winstpercentage\nluchtduels"),
    "press_total_count_otip_p30_percentile": Metric(category=MetricCategory.DEFENSE,label="Druk\nzetten"),
    "press_total_stop_danger_otip_p30_percentile": Metric(category=MetricCategory.DEFENSE, label="Gestopt gevaar\nmet verdedigende acties"),

}

# Assign metrics per position_profile
position_profiles = {

    "DMCM": [
        "total_distance_p90_percentile",
        "running_distance_p90_percentile",
        "hi_distance_p90_percentile",
        "total_minutes_percentile",
        "bypass_midfield_defense_pass_tip_p30_percentile",
        "bypass_midfield_defense_dribble_tip_p30_percentile",
        "bypass_opponents_rec_tip_p30_percentile",
        "off_ball_runs_total_tip_p30_percentile",
        "involvement_chances_tip_p30_percentile",
        "ball_win_removed_opponents_otip_p30_percentile",
        "ball_win_added_teammates_otip_p30_percentile",
        "ground_duels_won_p90_percentile",
        "aerial_duels_won_p90_percentile",
        "press_total_count_otip_p30_percentile",
    ]

}

# Check whether all metrics assigned to position_profiles are defined correctly
validate_profiles(metrics, position_profiles)

# X. Not sure where to put this yet
table_columns = {
    "player_name": "Player",
    "team_name": "Team",
    "country": "Nationality",
    "age": "Age",
    "display_position": "Position",
    "total_minutes": "Total min.",
    "position_minutes": "Position min.",
    "competition_name": "Competition",
    "season_name": "Season",
    "physical": "Physical",
    "attack": "Attack",
    "defense": "Defense",
    "total": "Total",
}

FC_GRONINGEN_GREEN = "#3E8C5E"

TEAM_LOGOS_DIR = "team_logos"

TEAM_LOGO_MAPPING = {
}

# X. SET UP DASHBOARD
st.set_page_config(page_title="FC Groningen Scouting Dashboard", layout="wide")

# Stop the code if password is incorrect
if not check_password():
    st.stop()

# Get Supabase URL and KEY 
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

# Set CSS formatting
st.markdown(
    f"""
    <style>
    
    /* Import Proxima Nova and create fallback */
      @import url('https://fonts.cdnfonts.com/css/proxima-nova-2');

      html, body, [class*="css"], .stApp {{
        font-family: 'Proxima Nova', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
      }}

    /* Create sidebar, set background color and allow vertical scrolling */ 
      section[data-testid="stSidebar"] {{
        background-color: #94CDAA;
        overflow-y: auto !important;
      }}

    /* Make sure sidebar elements are not cut off */ 
      section[data-testid="stSidebar"] > div {{
        overflow-y: visible !important;
      }}

    /* Remove top padding of first element */ 
      section[data-testid="stSidebar"] > div:first-child {{
        padding-top: 0 !important;
      }}

    /* Set padding for the block containing all dropdowns and sliders */ 
      section[data-testid="stSidebar"] .block-container {{
        padding-top: 0.2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 0.5rem !important;
      }}

    /* Set padding inside block */ 
      section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div {{
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
      }}
    
    /* Set sidebar labels and their margin */    
    section[data-testid="stSidebar"] label {{
        margin-bottom: 0.2rem !important;
        font-size: 14px !important;
      }}

    /* Set margins for dropdowns in the sidebar */  
      section[data-testid="stSidebar"] div[data-baseweb="select"] {{
        margin-bottom: 0.3rem !important;
      }}

    /* Set margins for sliders in the sidebar */  
      section[data-testid="stSidebar"] div[data-testid="stSlider"] {{
        padding-top: 0rem !important;
        padding-bottom: 0.3rem !important;
      }}

    /* Set margins for all other elements */  
      section[data-testid="stSidebar"] .element-container {{
        margin-bottom: 0.2rem !important;
      }}

    /* Set fontstyle for headers in sidebar */    
      .sb-title {{
        font-size: 24px;
        font-weight: 700;
        margin: 0 0 4px 0;
        padding: 0;
        font-family: 'Proxima Nova', sans-serif !important;
      }}

    /* Create small horizontal lines under headers */    
      .sb-rule {{
        height: 1px;
        background: rgba(0,0,0,0.12);
        margin: 0 0 8px 0;
      }}

    /* Set fontcolor for sliderscan  */   
      div[data-testid="stSlider"] * {{ color: #000000 !important; }}

    /* Set padding for all vertical blocks */       
      div[data-testid="stVerticalBlock"] > div {{
        padding-top: 0.05rem;
        padding-bottom: 0.05rem;
      }}

    </style>
    """,

    # Make sure it is able to process HTML
    unsafe_allow_html=True,
)
