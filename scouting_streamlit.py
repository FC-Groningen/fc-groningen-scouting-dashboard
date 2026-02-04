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
    """
    Returns `True` if the user has entered the correct password.
    """

    def password_entered():
        """
        Checks whether a password entered by the user is correct.
        """

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
        st.write("Neem contact met Arno de Jong of Bram van de Water voor toegang.")
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
    """
    Returns an error message if a metric is not defined.
    """

    for pos, keys in profiles.items():
        for key in keys:
            if key not in metrics:
                raise KeyError(f"'{key}' in position '{pos}' is not defined.")

# 1.3 Function to load data stored in Supabase
@st.cache_data(ttl=3600)
def load_data_from_supabase():
    """
    Loads data stored in Supabase using url and key.
    """

    try:

        # Create Supabase client using the url and key
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Create pagination so all data can be fetched
        count_response = supabase.table('player_percentiles').select("id", count='exact').limit(1).execute()
        total_count = count_response.count

        all_data = []
        page_size = 1000

        for offset in range(0, total_count, page_size):
            response = supabase.table('player_percentiles').select("*").range(offset, offset + page_size - 1).execute()
            all_data.extend(response.data)

        df = pd.DataFrame(all_data)

        return df

    except Exception as e:
        st.error(f"Error loading data from Supabase: {str(e)}")
        st.info("Please check your Supabase credentials in .streamlit/secrets.toml")
        st.stop()
        return pd.DataFrame()

# 1.4 Function to load stored player Impect urls in Supabase
@st.cache_data(ttl=36000)
def load_impect_urls_from_supabase():
    """
    Load Impect URLs from player_impect_urls table.
    """

    try:

        # Create Supabase client using the url and key
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Create pagination so all data can be fetched
        count_response = supabase.table('player_impect_urls').select("id", count='exact').limit(1).execute()
        total_count = count_response.count

        all_urls = []
        page_size = 1000

        for offset in range(0, total_count, page_size):
            response = supabase.table('player_impect_urls').select("player_id, player_name, iterationid, position, impect_url").range(offset, offset + page_size - 1).execute()
            all_urls.extend(response.data)

        df = pd.DataFrame(all_urls)

        return df

    except Exception as e:
        st.warning(f"Could not load Impect URLs: {str(e)}")
        return pd.DataFrame()

# 1.5 Get the relevant metrics for a selected position
def get_metrics_for_profile(profile_name):
    """"
    Find relevant metrics per category for a selected position.
    """

    # Get the list of metric keys
    metric_keys = position_profiles.get(profile_name, [])
    
    # Sort them into categories
    categories = {cat.name.lower(): [] for cat in MetricCategory}
    
    for key in metric_keys:
        if key in metrics:
            metric_obj = metrics[key]
            cat_name = metric_obj.category.name.lower()
            if cat_name in categories:
                categories[cat_name].append(key)
            
    return categories

# 1.6 Create player radars
def build_radar_3_shapes(row, profile_name):
    """
    Builds a tri-colored radar chart using structured metric definitions.
    """

    # Create figure
    fig = go.Figure()

    # Get categorized metrics
    categorized_metrics = get_metrics_for_profile(profile_name)

    # 2. Internal helper to add each category shape
    def add_group(metric_keys, name, line_color, fill_rgba):
        """"
        Internal helper to add each category shape.
        """

        if not metric_keys:
            return

        r_vals = []
        theta = []

        for m in metric_keys:
            # Get value from row, default to 0 if NaN
            val = row.get(m, 0)
            r_vals.append(float(val) if pd.notna(val) else 0)
            
            # Get label from our Metric objects, remove newlines for the chart
            if m in metrics:
                display_label = metrics[m].label.replace('\n', ' ')
            else:
                display_label = m.replace('_', ' ').title()
            
            theta.append(display_label)

        # Close the radar loop
        r_vals.append(r_vals[0])
        theta.append(theta[0])

        fig.add_trace(go.Scatterpolar(
            r=r_vals,
            theta=theta,
            fill='toself',
            fillcolor=fill_rgba,
            line=dict(color=line_color, width=2),
            name=name,
            hovertemplate="<b>%{theta}</b><br>Percentile: %{r:.1f}<extra></extra>"
        ))

    # Add the three specific layers with  color scheme
    layers = [
        ('physical', "Fysiek", "#3E8C5E", "rgba(62, 140, 94, 0.25)"),
        ('attacking',   "Aanval",  "#E83F2A", "rgba(232, 63, 42, 0.25)"),
        ('defending',  "Verdediging", "#F2B533", "rgba(242, 181, 51, 0.25)")
    ]

    for key, label, line_col, fill_col in layers:
        add_group(categorized_metrics.get(key, []), label, line_col, fill_col)

    # Final layout styling
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True, 
                range=[0, 100], 
                tickfont=dict(size=10, color="gray"),
                gridcolor="rgba(200, 200, 200, 0.2)"
            ),
            angularaxis=dict(
                tickfont=dict(size=10, fontfamily="Arial Black"),
                rotation=90,
                direction="clockwise"
            )
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        height=500,
        margin=dict(l=80, r=80, t=40, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    return fig

# 1.7 Function to clean teamnames based on how they can be saved
def sanitize_filename(name):
    """"
    Clean team names for how these can be saved.
    """

    return (
        name.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )

# 1.8 Encode save team logo's      
def encode_image_to_base64(logo_path):
    """
    Helper to convert an image file to a base64 string.
    """

    img = Image.open(logo_path)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

# 1.9 Get team logo's
@st.cache_data
def get_team_logo_base64(team_name, competition_name):
    """"
    Get team logo's based on team_name and competition name.
    """
    
    if not team_name:
        return None

    try:
        # Look if a teamname has a different name in the dictionary        
        logo_filename = TEAM_LOGO_MAPPING.get(team_name, team_name)
        safe_filename = sanitize_filename(logo_filename)
        paths_to_try = []

        # Look for teamname within competition folder
        if competition_name:
            safe_comp = competition_name.replace("/", "_").replace("\\", "_")
            comp_folder = Path(TEAM_LOGOS_DIR) / safe_comp
            
            if comp_folder.exists():
                # Try exact matches in the comp folder first
                paths_to_try.append(comp_folder / f"{safe_filename}.png")
                
                # Add Fuzzy search results
                for file in comp_folder.glob("*.png"):
                    if safe_filename.lower() in file.stem.lower():
                        paths_to_try.append(file)

        # Fallback to general folder
        paths_to_try.append(Path(TEAM_LOGOS_DIR) / f"{safe_filename}.png")
        
        # Add original team name if mapping was used
        if logo_filename != team_name:
            paths_to_try.append(Path(TEAM_LOGOS_DIR) / f"{sanitize_filename(team_name)}.png")

        # Execute search and encode logo
        for logo_path in paths_to_try:
            if logo_path.exists():
                return encode_image_to_base64(logo_path)

    except Exception:
        pass
    return None

# 1.10 Get the Impect player url
def get_player_url(row):
    """"
    Finds the related player Impect url.
    """

    if pd.notna(row.get('impect_url')) and row.get('impect_url'):
        return row['impect_url']
    
    # If not found, return None (nothing)
    return None

# 1.11
def create_team_html_with_logo(row):
    """"
    Create column that combines team logo with name.
    """

    # Find the logo based on the team and competition
    team_name = row['team_name']
    competition = row.get('competition_name')
    logo_b64 = get_team_logo_base64(team_name, competition)

    # Format column
    if logo_b64:
        return f'<img src="{logo_b64}" height="20" style="vertical-align: middle; margin-right: 8px;">{team_name}'
    return team_name

# X. METRICS AND POSITION_PROFILES
# Enumeration of metric categories
class MetricCategory(str, Enum):
    PHYSICAL = "physical"
    ATTACK = "attacking"
    DEFENSE = "defending"

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
    "original_rank": "#",
    "player_name": "Speler",
    "team_with_logo_html": "Club",
    "country": "Nationaliteit",
    "age": "Leeftijd",
    "position_profile": "Positie",
    "total_minutes": "Alle minuten",
    "position_minutes": "Minuten",
    "competition_name": "Competitie",
    "season_name": "Seizoen",
    "physical": "Fysiek",
    "attacking": "Aanvallend",
    "defending": "Verdedigend",
    "total": "Totaal",
}

FC_GRONINGEN_GREEN = "#3E8C5E"
TEAM_LOGOS_DIR = "team_logos"

TEAM_LOGO_MAPPING = {
}

# X. SET UP DASHBOARD
# Configure page and set layout
st.set_page_config(page_title="FC Groningen Scouting Dashboard", layout="wide")

# Stop the code if password is incorrect
if not check_password():
    st.stop()

# Get Supabase URL and KEY 
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

# Set general CSS formatting
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
            background-color: #E9F4ED;
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

    /* Create space underneath logo */
        section[data-testid="stSidebar"] div[style*="text-align: center"] {{
            margin-bottom: 50px !important;
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

    /* Set label size and color for dropdown titles */
        section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
            font-size: 16px !important;
            color: #000000 !important;
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

    /* Set fontcolor for slider  */   
        section[data-testid="stSidebar"] div[data-testid="stSlider"] label {{
            color: #000000 !important;
            }}

    /* Set padding for all vertical blocks */
        div[data-testid="stVerticalBlock"] > div {{
            padding-top: 0.05rem;
            padding-bottom: 0.05rem;
            }}

    /* Add some spacing between slider header */
        section[data-testid="stSidebar"] .stSlider > label {{
            padding-bottom: 10px !important;
            }}

    /* 1. Target the main content container specifically */
        [data-testid="stAppViewBlockContainer"] {{
            padding-top: 1rem !important; /* Reduces the 6rem default to 1rem */
            margin-top: 0px !important;
            }}

    /* 2. Pull the Title (h1) up even further if needed */
        h1 {{
            margin-top: -30px !important;
            padding-top: 0px !important;
            }}

    /* 3. Reduce the gap between the Ranking headers and the column inputs */
        .stSubheader {{
            margin-top: -10px !important;
            }}

    /* 1. Adjust the sidebar width */
        [data-testid="stSidebar"] {{
            width: 250px !important; /* Default is usually ~336px */
            }}

    /* 2. Adjust the main content margin to match the new sidebar width */
        [data-testid="stAppViewMain"] {{
            margin-left: 0px !important;
            }}

    /* 3. Ensure the main container expands to fill the freed-up space */
        [data-testid="stMainViewContainer"] {{
            width: 100% !important;
            }}
    
    </style>
    """,

    # Make sure it is able to process HTML
    unsafe_allow_html=True,
)

# Add elements to sidebar
with st.sidebar:
    try:
        # Add logo at the top of the sidebar
        logo = Image.open("FC_Groningen.png")
        buffered = BytesIO()
        logo.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        st.markdown(
            f"""
            <div style="margin: 0; padding: 0 0 4px 0; line-height: 0; text-align: center;">
                <img src="data:image/png;base64,{img_str}"
                     style="width: 140px; height: auto; display: inline-block; margin: 0; padding: 0;
                            image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges;" />
            </div>
            """,
            unsafe_allow_html=True
        )
    except:
        pass

    # Add subtitle and horizontal bar underneath logo
    st.markdown('<div class="sb-title">Filters</div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-rule"></div>', unsafe_allow_html=True) 

# Add title
st.title("Scouting dashboard")
st.subheader("Ranglijst")
st.markdown('<div class="sb-rule"></div>', unsafe_allow_html=True)

# Create selection options for first table
col1, col2, col3, col4 = st.columns(4, gap="large")

with col1:
    top_n = st.number_input("Aantal spelers", min_value=1, max_value=500, value=20, step=1)

with col2:
    min_physical = st.slider("Fysieke benchmark", min_value=0, max_value=100, value=0, step=1)

with col3:
    min_attack = st.slider("Aanvallende benchmark", min_value=0, max_value=100, value=0, step=1)

with col4:
    min_defense = st.slider("Defensieve benchmark", min_value=0, max_value=100, value=0, step=1)

# X. GET DATA
# Get percentile data
with st.spinner('Ophalen van de data...'):
    df_player_data = load_data_from_supabase()

# Get Impect urls
with st.spinner('Creëeren van Impect connectie...'):
    df_impect_urls = load_impect_urls_from_supabase()

# Merge Impect url to the players data
if not df_impect_urls.empty:
    # Create a unique lookup table from the URL data
    url_lookup = df_impect_urls[['player_id', 'position', 'impect_url']].drop_duplicates(
        subset=['player_id', 'position']
    )

    # Merge onto  main data
    df_player_data = df_player_data.merge(
        url_lookup,
        on=['player_id', 'position'],
        how='left'
    )

# Find unique variables to show in the dropdowns
competitions = sorted(df_player_data["competition_name"].dropna().unique())
seasons = sorted(df_player_data["season_name"].dropna().unique())
positions = sorted(df_player_data["position_profile"].dropna().unique())

# Set default in the selection
default_competitions = ["Eredivisie"] if "Eredivisie" in competitions else competitions
default_seasons = ["2025/2026"] if "2025/2026" in seasons else seasons
default_positions = [p for p in ["DM/CM (DEF)", "DM/CM (CRE)", "DM/CM (BTB)"] if p in positions]    

# Create dropdowns
dropdown_competition = st.sidebar.multiselect("Competitie", competitions, default=default_competitions)
dropdown_season = st.sidebar.multiselect("Seizoen", seasons, default=default_seasons)
dropdown_positions = st.sidebar.multiselect("Positie (profiel)", positions, default=positions)

# Make the teams dropdown dynamic for the selected competition and season
teams = sorted(df_player_data[
    df_player_data["competition_name"].isin(dropdown_competition) & 
    df_player_data["season_name"].isin(dropdown_season)
]["team_name"].dropna().unique())

dropdown_teams = st.sidebar.multiselect("Club", teams, default=[])

# Create age range slider
age_min = int(np.nanmin(df_player_data["age"].values))
age_max = int(np.nanmax(df_player_data["age"].values))
age_range_slider = st.sidebar.slider(
    "Leeftijd range",
    min_value=age_min,
    max_value=age_max,
    value=(age_min, age_max),
    step=1,
)

# Create EU player selection
show_eu_only = st.sidebar.checkbox(
    "Alleen EU spelers",
    value=False,
    help="Selecteer alleen spelers die een EU paspoort hebben"
)

# Create a filter mask based on the dropdowns
mask = (
    df_player_data["competition_name"].isin(dropdown_competition)
    & df_player_data["season_name"].isin(dropdown_season)
    & df_player_data["age"].between(age_range_slider[0], age_range_slider[1])
    & df_player_data["position_profile"].isin(dropdown_positions)
)

if dropdown_teams:
    mask &= df_player_data["team_name"].isin(dropdown_teams)

if show_eu_only and 'european' in df_player_data.columns:
    mask &= (df_player_data["european"] == True)

# Filter the data based on the mask
df_filtered = df_player_data.loc[mask].copy()

# Sort the data based on the total count and add original rank
df_filtered.sort_values("total", ascending=False, inplace=True, na_position="last")
df_filtered["original_rank"] = range(1, len(df_filtered) + 1)

# Get the top X players
df_top = df_filtered.head(int(top_n)).copy()

# Filter the data based on the benchmarks at the top
df_top = df_top[
    (df_top["physical"] >= min_physical) &
    (df_top["attacking"] >= min_attack) &
    (df_top["defending"] >= min_defense)
]

# If no players meet the criteria, return info message
if len(df_top) == 0:
    st.info("No players match the current filters.")
    st.stop()

# TEMP: Not sure if this is needed
df_filtered = df_filtered[
    (df_filtered["physical"] >= min_physical) &
    (df_filtered["attacking"] >= min_attack) &
    (df_filtered["defending"] >= min_defense)
]

# Add technical columns you need for the logic but don't want to show
technical_cols = ["team_name", "impect_url"] 

# Create dataframe that will be shown in the table
df_show = df_top.copy()

# Round numeric columns
numeric_columns = ["age", "total_minutes", "position_minutes", "physical", "attacking", "defending", "total"]
for col in numeric_columns:
    if col in df_show.columns:
        decimals = 0 if col in ["total_minutes", "position_minutes"] else 1
        df_show[col] = df_show[col].round(decimals)

# Create dynamic url and team logo columns
df_show["player_url"] = df_show.apply(get_player_url, axis=1)
df_show["team_with_logo_html"] = df_show.apply(create_team_html_with_logo, axis=1)
df_show["_original_index"] = df_top.index

# Reorder and rename columns
df_show = df_show[list(table_columns.keys()) + ["player_url", "_original_index"]]
df_show = df_show.rename(columns=table_columns)

# Render the player url
player_link_renderer = JsCode("""
class PlayerLinkRenderer {
    init(params) {
        this.eGui = document.createElement('a');
        this.eGui.innerText = params.value;
        this.eGui.href = params.data.player_url;
        this.eGui.target = '_blank';
        this.eGui.style.color = '#1a73e8';
        this.eGui.style.textDecoration = 'none';
    }
    getGui() {
        return this.eGui;
    }
}
""")

# Render the team logo
team_logo_renderer = JsCode("""
class TeamLogoRenderer {
    init(params) {
        this.eGui = document.createElement('div');
        this.eGui.innerHTML = params.value;
    }
    getGui() {
        return this.eGui;
    }
}
""")

# Add thousand seperator
number_dot_formatter = JsCode("""
function(params) {
    if (params.value == null) return '';
    return params.value.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ".");
}
""")

# Create conditional formatting
COLOR_THRESHOLD = 30
gradient_js = JsCode(f"""
function(params) {{
    if (params.value == null || isNaN(params.value)) return {{}};
    
    let val = params.value;
    let threshold = {COLOR_THRESHOLD};
    
    // If the value is below the threshold, keep it white/neutral
    if (val < threshold) {{
        return {{
            'backgroundColor': '#FFFFFF',
            'color': 'black',
            'display': 'flex',
            'alignItems': 'center',
            'justifyContent': 'center',
            'textAlign': 'center'
        }};
    }}
    
    // Scale the score
    let factor = (val - threshold) / (100 - threshold); 
    factor = Math.min(1, Math.max(0, factor)); 
    
    // Get RGB score of FC Groningen green
    let r = Math.round(255 - (factor * (255 - 62)));
    let g = Math.round(255 - (factor * (255 - 140)));
    let b = Math.round(255 - (factor * (255 - 94)));
    
    let backgroundColor = 'rgb(' + r + ',' + g + ',' + b + ')';
    let textColor = factor > 0.6 ? 'white' : 'black';
    
    return {{
        'backgroundColor': backgroundColor,
        'color': textColor,
        'fontWeight': 'normal',
        'border': '3px solid #FFFFFF',
        'borderRadius': '8px',
        'display': 'flex',
        'alignItems': 'center',
        'justifyContent': 'center',
        'textAlign': 'center'
    }};
}}
""")

# Create first table
gb = GridOptionsBuilder.from_dataframe(df_show)

# Set the width of specific columns
gb.configure_column(table_columns["original_rank"], width=80, pinned="left", sortable=True, type=["numericColumn"])
gb.configure_column(table_columns["player_name"], width=180, pinned="left", cellRenderer=player_link_renderer)
gb.configure_column(table_columns["team_with_logo_html"], width=200, cellRenderer=team_logo_renderer)

# Automatically configure the rest of the columns from the dictionary
for key, label in table_columns.items():
    if key not in ["original_rank", "player_name", "team_with_logo_html", "position_profile"]:
        is_numeric = key in ["age", "total_minutes", "position_minutes", "physical", "attacking", "defending", "total"]
        
        col_config = {
                "width": 140, 
                "type": ["numericColumn"] if is_numeric else [],
                "sortingOrder": ["desc", "asc", None]
            }
        
        # Keep the thousand separator for minutes
        if key in ["total_minutes", "position_minutes"]:
            col_config["valueFormatter"] = number_dot_formatter
            
        # Apply the dynamic gradient to metrics
        if key in ["physical", "attacking", "defending"]:
            col_config["cellStyle"] = gradient_js
            
        gb.configure_column(label, **col_config)

# Hide the technical helper columns
gb.configure_column("player_url", hide=True)
gb.configure_column("_original_index", hide=True)

# Final settings
gb.configure_default_column(sortable=True, filterable=False, resizable=True)
gb.configure_selection(selection_mode='multiple', use_checkbox=True)

gridOptions = gb.build()

top_grid_response = AgGrid(
    df_show,
    gridOptions=gridOptions,
    enable_enterprise_modules=False,
    allow_unsafe_jscode=True,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    height=615,
    fit_columns_on_grid_load=False,
    theme='streamlit'
)

# Check which boxes are checked
selected_from_top_table = []
selected_from_top_table_full_data = []

# Ensure grid_response isn't empty and has selected rows
if top_grid_response and top_grid_response.get('selected_rows') is not None:
    selected_rows = top_grid_response['selected_rows']
    
    # Standardize AgGrid's output
    if isinstance(selected_rows, pd.DataFrame):
        rows = selected_rows.to_dict('records')
    else:
        rows = selected_rows

    # Process up to 2 selected players
    for row in rows[:2]:
        # Get the human-readable name for display
        name_col = table_columns.get('player_name', 'player_name')
        selected_from_top_table.append(row.get(name_col))

        idx = row.get('_original_index')
        if idx is not None and idx in df_top.index:
            selected_from_top_table_full_data.append(df_top.loc[idx])

# Create plot section
st.subheader("Radarplots")
st.markdown('<div class="sb-rule"></div>', unsafe_allow_html=True)









# X. Create player search
# Add title
st.subheader("Zoekopdracht")
st.markdown('<div class="sb-rule"></div>', unsafe_allow_html=True)

# Create list with all available players
available_players = sorted(df_player_data["player_name"].unique().tolist())

# Create search field
search_selected_players = st.multiselect(
    "Selecteer speler(s) en zie alle beschikbare data.",
    options=available_players,
    default=[],
    help="Een speler kan er niet tussen staan als we geen data van die competitie afnemen of als hij onvoldoende minuten op een specifieke positie heeft gemaakt"
)

# Filter and sort data
df_selected_players = df_player_data[df_player_data['player_name'].isin(search_selected_players)].copy().sort_values(by='total', ascending=False).reset_index(drop=True)

# Add helper columns
df_selected_players['original_rank'] = df_selected_players.index + 1
df_selected_players["player_url"] = df_selected_players.apply(get_player_url, axis=1)
df_selected_players["team_with_logo_html"] = df_selected_players.apply(create_team_html_with_logo, axis=1)

# Round numeric columns
numeric_columns = ["age", "total_minutes", "position_minutes", "physical", "attacking", "defending", "total"]
for col in numeric_columns:
    if col in df_selected_players.columns:
        decimals = 0 if col in ["total_minutes", "position_minutes"] else 1
        df_selected_players[col] = df_selected_players[col].round(decimals)

# Reorder and rename columns
all_needed_cols = list(table_columns.keys()) + ["player_url"]
df_selected_players = df_selected_players[[c for c in all_needed_cols if c in df_selected_players.columns]]
df_selected_players = df_selected_players.rename(columns=table_columns)

# Create third table
gb = GridOptionsBuilder.from_dataframe(df_selected_players)

# Set the width of specific columns
gb.configure_column(table_columns["original_rank"], width=80, pinned="left", sortable=True, type=["numericColumn"])
gb.configure_column(table_columns["player_name"], width=180, pinned="left", cellRenderer=player_link_renderer)
gb.configure_column(table_columns["team_with_logo_html"], width=200, cellRenderer=team_logo_renderer)

# Automatically configure the rest of the columns from the dictionary
for key, label in table_columns.items():
    if key not in ["original_rank", "player_name", "team_with_logo_html", "position_profile"]:
        is_numeric = key in ["age", "total_minutes", "position_minutes", "physical", "attacking", "defending", "total"]
        
        col_config = {
                "width": 140, 
                "type": ["numericColumn"] if is_numeric else [],
                "sortingOrder": ["desc", "asc", None]
            }
        
        # Keep the thousand separator for minutes
        if key in ["total_minutes", "position_minutes"]:
            col_config["valueFormatter"] = number_dot_formatter
            
        # Apply the dynamic gradient to metrics
        if key in ["physical", "attacking", "defending"]:
            col_config["cellStyle"] = gradient_js
            
        gb.configure_column(label, **col_config)

# Hide the technical helper columns
gb.configure_column("player_url", hide=True)
gb.configure_column("_original_index", hide=True)
gb.configure_column("::auto_unique_id::", hide=True)

# Final settings
gb.configure_default_column(sortable=True, filterable=False, resizable=True)
gb.configure_selection(selection_mode='multiple', use_checkbox=True)

gridOptions = gb.build()

if not df_selected_players.empty:
    search_grid_response = AgGrid(
        df_selected_players,
        gridOptions=gridOptions,
        enable_enterprise_modules=False,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height= min(615, 34.5 + len(df_selected_players) * 29.1),
        fit_columns_on_grid_load=False,
        theme='streamlit'
    )

# Check which boxes are checked
selected_from_search_table = []
selected_from_search_table_full_data = []

# Get the human-readable label for "Player Name"
name_col = table_columns.get('player_name', 'Player Name')

# Process only if rows are selected
if search_grid_response and search_grid_response.get('selected_rows') is not None:
    search_selected_rows = search_grid_response['selected_rows']
    
    # Standardize AgGrid output to a list of dictionaries
    rows = (search_selected_rows.to_dict('records') 
            if isinstance(search_selected_rows, pd.DataFrame) 
            else search_selected_rows)

    # Extract data for the first 2 selected players
    for row in rows[:2]:
        selected_from_search_table.append(row.get(name_col))
        
        # Pull full data from search_df using the hidden unique index
        idx = row.get('_search_original_index')
        if idx is not None and idx in df_selected_players.index:
            selected_from_search_table_full_data.append(df_selected_players.loc[idx])

# Create plot section
st.subheader("Radarplots")
st.markdown('<div class="sb-rule"></div>', unsafe_allow_html=True)

def create_polarized_bar_chart(player_data: pd.Series, competition_name: str, season_name: str) -> go.Figure:
    # 1. Determine the profile key (e.g., "DMCM")
    # We strip extra info to match your position_profiles keys
    raw_pos = str(player_data.get('position_profile', '')).split(' (')[0]
    profile_key = raw_pos if raw_pos in position_profiles else "DMCM" # Fallback to DMCM

    # 2. Automatically sort metrics into categories based on your metrics dict
    active_metric_keys = position_profiles.get(profile_key, [])
    
    physical_keys = [k for k in active_metric_keys if metrics[k].category == MetricCategory.PHYSICAL]
    attack_keys   = [k for k in active_metric_keys if metrics[k].category == MetricCategory.ATTACK]
    defense_keys  = [k for k in active_metric_keys if metrics[k].category == MetricCategory.DEFENSE]
    
    all_keys = physical_keys + attack_keys + defense_keys

    # 3. Pull values and labels
    percentile_values = [float(player_data.get(k, 0)) for k in all_keys]
    # Uses the .label property from your Metric dataclass
    metric_labels = [metrics[k].label.replace('\n', '<br>') for k in all_keys]

    # 4. Averages (using original keys for group scores)
    physical_avg = float(player_data.get('physical', 0))
    attack_avg   = float(player_data.get('attacking', 0))
    defense_avg  = float(player_data.get('defending', 0))
    overall_avg  = float(player_data.get('total', np.mean([physical_avg, attack_avg, defense_avg])))

    # 5. Styling
    green, red, yellow = '#3E8C5E', '#E83F2A', '#F2B533'
    
    def get_color(score, base_hex):
        norm = max(0, min(1, score / 100))
        base = [int(base_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)]
        return f'rgb({int(255-(255-base[0])*norm)}, {int(255-(255-base[1])*norm)}, {int(255-(255-base[2])*norm)})'

    colors = ([get_color(v, green) for v in percentile_values[:len(physical_keys)]] +
              [get_color(v, red) for v in percentile_values[len(physical_keys):len(physical_keys)+len(attack_keys)]] +
              [get_color(v, yellow) for v in percentile_values[-len(defense_keys):]])

    # 6. Build Figure
    fig = go.Figure()

    # --- LAYER 1: THE RADIAL SPOKES (Manual Grid) ---
    # We build these first so they are naturally behind the bars
    r_coords = []
    theta_coords = []
    for label in metric_labels:
        # This tells Plotly: Start at 0, go to 100, then stop drawing
        r_coords.extend([0, 100, None]) 
        theta_coords.extend([label, label, None])

    fig.add_trace(go.Scatterpolar(
        r=r_coords,
        theta=theta_coords,
        mode='lines',
        line=dict(color='rgba(0,0,0,0.1)', width=1),
        hoverinfo='skip',
        showlegend=False
    ))

    # --- LAYER 2: THE BARS ---
    fig.add_trace(go.Barpolar(
        r=percentile_values,
        theta=metric_labels,
        marker=dict(color=colors, line=dict(color='white', width=1.5)),
        text=[f'{v:.0f}' for v in percentile_values],
        hovertemplate='<b>%{theta}</b><br>Score: %{r:.1f}<extra></extra>'
    ))

    # --- THE LAYOUT ---
    fig.update_layout(
        renderers="svg",
        polar=dict(
            bgcolor='white',
            radialaxis=dict(
                range=[-25, 100], 
                visible=True, 
                showticklabels=False, 
                gridcolor='rgba(0,0,0,0.1)', 
                tickvals=[25, 50, 75, 100], # Circular rings
                ticks='', 
                showline=False
            ),
            angularaxis=dict(
                tickfont=dict(size=10, color='black'), 
                rotation=90, 
                direction='clockwise', 
                showgrid=False,           # <--- WE HIDE BUILT-IN GRID
                ticks='', 
                showline=True,            # <--- THE OUTER BORDER
                linecolor='rgba(0,0,0,0.2)'
            )
        ),
        annotations=[
            dict(
                text=f"<b>{overall_avg:.1f}</b>", 
                x=0.5, y=0.5, # Adjusted for visual centering
                showarrow=False,
                font=dict(size=28, color='black'), 
                xref="paper", yref="paper"
            )
        ],
        showlegend=False,
        height=500,
        margin=dict(l=50, r=50, t=100, b=50),
        title=dict(
            text=(f"<b>{player_data.get('player_name', 'Speler')}</b><br>"
                  f"<span style='font-size:13px'>🟢 Fysiek: {physical_avg:.1f} | 🔴 Aanval: {attack_avg:.1f} | 🟡 Defensie: {defense_avg:.1f}</span>"),
            x=0.5, y=0.98, xanchor='center'
        )
    )

    return fig

# 1. Combine the selections from both tables
players_to_compare = (selected_from_top_table + selected_from_search_table)[:2]
players_data_to_compare = (selected_from_top_table_full_data + selected_from_search_table_full_data)[:2]

# 2. Determine the source message for the UI
if selected_from_top_table and selected_from_search_table:
    source_message = "from both tables"
elif selected_from_top_table:
    source_message = "from search table"
else:
    source_message = "from top table"

# 3. Execution Block
if len(players_to_compare) > 0:
    # Warning if the user gets click-happy
    total_selected = len(selected_from_top_table) + len(selected_from_search_table)
    if total_selected > 2:
        st.warning("Je hebt meer dan 2 spelers geselecteerd, alleen de eerste 2 worden getoond.")

    # --- Animation & Column Layout ---
    st.markdown("""
    <style>
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .stPlotlyChart { animation: fadeIn 0.5s ease-in-out; }
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(2)

    for i, player_name in enumerate(players_to_compare):
        # We can now rely 100% on players_data_to_compare 
        # because our new retrieval logic is so robust
        player_data = players_data_to_compare[i]

        with cols[i]:
            st.markdown(
                f"<p style='font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem;'>{player_name}</p>",
                unsafe_allow_html=True
            )

            # Metadata Retrieval
            team_name = player_data['team_name']
            competition = player_data.get('competition_name')
            team_logo_b64 = get_team_logo_base64(team_name, competition)

            # Build Clean Caption
            pos = player_data.get('display_position') or player_data.get('position_profile') or player_data.get('position', '')
            caption_parts = [
                f"{team_name}",
                f"{player_data['country']}",
                f"Age {int(player_data['age'])}",
                f"{pos}",
                f"{int(player_data['total_minutes'])} mins"
            ]

            # Display Logo and Caption
            logo_html = f'<img src="{team_logo_b64}" height="30" style="vertical-align: middle; margin-right: 8px;">' if team_logo_b64 else ""
            st.markdown(
                f"""<div style="font-size: 1.1rem; margin-bottom: 1rem; line-height: 1.6;">
                    {logo_html} {' · '.join(caption_parts)}
                </div>""", 
                unsafe_allow_html=True
            )

            # Render Chart
            fig = create_polarized_bar_chart(
                player_data,
                player_data['competition_name'],
                player_data['season_name']
            )
            
            chart_key = f"comparison_chart_{i}_{player_name.replace(' ', '_')}"
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=chart_key)













# Old CSS code
    # /* 1. Target the CSS variables AgGrid uses for the theme */
    #     .ag-theme-streamlit {{
    #         --ag-header-background-color: #3E8C5E !important;
    #         --ag-header-foreground-color: #FFFFFF !important;
    #         }}

    # /* 2. Target the specific header container */
    #     .ag-header {{
    #         background-color: #3E8C5E !important;
    #         border-bottom: 1px solid #2d6a47 !important;
    #         }}

    # /* 3. Force the text color on all header labels */
    #     .ag-header-cell-label, .ag-header-cell-text {{
    #         color: #FFFFFF !important;
    #         }}

    # /* 4. Fix the pinned left header background */
    #     .ag-pinned-left-header {{
    #         background-color: #3E8C5E !important;
    #         border-right: 1px solid #2d6a47 !important;
    #         }}

    # /* 1. Force the colors at the root level */
    #     .ag-theme-streamlit {{
    #         --ag-header-background-color: #3E8C5E !important;
    #         --ag-header-foreground-color: #FFFFFF !important;
    #         --ag-secondary-foreground-color: #FFFFFF !important;
    #         --ag-border-color: #2d6a47 !important;
    #         }}

    #     /* 2. Target the actual header row to ensure green background */
    #         .ag-theme-streamlit .ag-header {{
    #             background-color: #3E8C5E !important;
    #         }}

    #     /* 3. Force the white lines (separators) */
    #     /* We target the 'side-bar' of the cell which AgGrid uses for the divider */
    #         .ag-theme-streamlit .ag-header-cell::after, 
    #         .ag-theme-streamlit .ag-header-group-cell::after {{
    #             content: "" !important;
    #             position: absolute !important;
    #             right: 0 !important;
    #             height: 60% !important;
    #             top: 20% !important;
    #             width: 1.5px !important;
    #             background-color: rgba(255, 255, 255, 0.4) !important;
    #             display: block !important;
    #             opacity: 1 !important;
    #             }}

    #     /* 4. Fix for the Pinned Column (Player Name) specifically */
    #         .ag-theme-streamlit .ag-pinned-left-header {{
    #             background-color: #3E8C5E !important;
    #             background: #3E8C5E !important;
    #             }}

    #     /* 5. Clean up the text labels to ensure they stay white */
    #         .ag-theme-streamlit .ag-header-cell-text {{
    #             color: #FFFFFF !important;
    #             font-weight: 600 !important;
    #             }}


# Way to change the header background to green using custom_css=custom_css
# custom_css = {
#     ".ag-header-cell": {"background-color": "#3E8C5E !important"},
#     ".ag-header-cell-text": {"color": "#FFFFFF !important"},
#     ".ag-pinned-left-header": {"background-color": "#3E8C5E !important"}
# }


# Extended player selection code
# selected_from_grid = []
# selected_from_grid_full_data = []

# # Map the labels from the dictionary
# labels_to_keys = {v: k for k, v in table_columns.items()}

# if grid_response and 'selected_rows' in grid_response:
#     selected_rows = grid_response['selected_rows']
    
#     if selected_rows is not None and len(selected_rows) > 0:
#         if isinstance(selected_rows, pd.DataFrame):
#             rows_to_process = selected_rows.to_dict('records')
#         else:
#             rows_to_process = selected_rows

#         # Limit to 2 players for the radar plot
#         for row_dict in rows_to_process[:2]:
#             name_label = table_columns.get('player_name', 'player_name')
#             team_label = table_columns.get('team_with_logo_html', 'team_with_logo_html')
#             pos_label  = table_columns.get('display_position', 'display_position')
#             comp_label = table_columns.get('competition_name', 'competition_name')
#             season_label = table_columns.get('season_name', 'season_name')

#             selected_from_grid.append(row_dict.get(name_label))

#             # Use the hidden index
#             if '_original_index' in row_dict:
#                 orig_idx = row_dict['_original_index']
#                 if orig_idx in df_top.index:
#                     selected_from_grid_full_data.append(df_top.loc[orig_idx])
#                     continue

#             # Fallback if hidden index does not work
#             import re
#             player_name = row_dict.get(name_label)
            
#             # Clean HTML from team name
#             raw_team = str(row_dict.get(team_label, ''))
#             team_name = raw_team
#             if '<img' in raw_team:
#                 match = re.search(r'margin-right: 8px;">(.+?)(?:<|$)', raw_team)
#                 if match:
#                     team_name = match.group(1).strip()

#             # Match against df_top using original keys
#             matched_row = df_top[
#                 (df_top['player_name'] == player_name) &
#                 (df_top['team_name'] == team_name) &
#                 (df_top['display_position'] == row_dict.get(pos_label)) &
#                 (df_top['competition_name'] == row_dict.get(comp_label)) &
#                 (df_top['season_name'] == row_dict.get(season_label))
#             ]

#             if not matched_row.empty:
#                 selected_from_grid_full_data.append(matched_row.iloc[0])