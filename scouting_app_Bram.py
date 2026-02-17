import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from PIL import Image
import base64
from io import BytesIO
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from supabase import create_client, Client


# =========================
# PASSWORD PROTECTION
# =========================
def check_password():
    """Returns `True` if the user has entered the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        # Get password from Streamlit secrets (no fallback for security)
        if "APP_PASSWORD" not in st.secrets:
            st.error("⚠️ APP_PASSWORD not configured. Please contact the administrator.")
            return
        
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.write("*Please contact FC Groningen scouting team for access.*")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="FC Groningen Scouting Dashboard", layout="wide")

if not check_password():
    st.stop()

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
TEAM_LOGOS_DIR = "team_logos"

FC_GRONINGEN_GREEN = "#3E8C5E"


# =========================
# METRICS & POSITION PROFILES (matching Bram's scouting_streamlit.py)
# =========================
class MetricCategory(str, Enum):
    PHYSICAL = "physical"
    ATTACK = "attacking"
    DEFENSE = "defending"


@dataclass(frozen=True)
class Metric:
    category: MetricCategory
    label: str
    tooltip: str


# Full metric definitions
metrics = {
    # Physical metrics
    "total_distance_p90_percentile": Metric(
        category=MetricCategory.PHYSICAL,
        label="Totale\nafstand",
        tooltip="De totale afgelegde afstand per 90 minuten."
    ),
    "running_distance_p90_percentile": Metric(
        category=MetricCategory.PHYSICAL,
        label="15–20km/u\nafstand",
        tooltip="De totale afgelegde afstand tussen de 15-20km/u per 90 minuten."
    ),
    "hsr_distance_p90_percentile": Metric(
        category=MetricCategory.PHYSICAL,
        label="20-25km/u\nafstand",
        tooltip="De totale afgelegde afstand tussen de 20-25km/u per 90 minuten."
    ),
    "sprint_distance_p90_percentile": Metric(
        category=MetricCategory.PHYSICAL,
        label="25+km/u\nafstand",
        tooltip="De totale afgelegde afstand boven de 25km/u per 90 minuten."
    ),
    "hi_distance_p90_percentile": Metric(
        category=MetricCategory.PHYSICAL,
        label="20+km/u\nafstand",
        tooltip="De totale afgelegde afstand boven de 20km/u per 90 minuten."
    ),
    "total_minutes_percentile": Metric(
        category=MetricCategory.PHYSICAL,
        label="Totale\nspeeltijd",
        tooltip="Het totaal aan gespeelde minuten op alle posities."
    ),

    # Attacking metrics
    "bypass_midfield_defense_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Uitgespeelde\ntegenstanders",
        tooltip="Uitgespeelde middenvelders en verdedigers met alle acties, geschaald naar balbezit."
    ),
    "bypass_midfield_defense_pass_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Uitgespeelde\ntegenstanders\nmet passes",
        tooltip="Uitgespeelde middenvelders en verdedigers met passes over de grond, geschaald naar balbezit."
    ),
    "bypass_midfield_defense_dribble_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Uitgespeelde\ntegenstanders\nmet dribbels",
        tooltip="Uitgespeelde middenvelders en verdedigers met dribbels, geschaald naar balbezit."
    ),
    "bypass_opponents_rec_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Uitgespeelde\ntegenstanders\nals ontvanger",
        tooltip="Uitgespeelde tegenstanders als ontvanger van een pass, geschaald naar balbezit."
    ),
    "off_ball_runs_total_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Loopacties\nzonder bal",
        tooltip="Totale hoeveelheid loopacties zonder bal, geschaald naar balbezit."
    ),
    "involvement_chances_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Betrokkenheid\nkansen",
        tooltip="Betrokkenheid bij kansen via een doelpoging, een assist of een voorassist op de doelpoging, geschaald naar balbezit."
    ),
    "chance_created_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Gecreëerde\nkansen",
        tooltip="Totale hoeveelheid gecreëerde kansen, geschaald naar balbezit."
    ),
    "pxt_pass_absolute_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Gecreëerd gevaar\nmet passes",
        tooltip="Gecreëerd gevaar met passes over de grond, geschaald naar balbezit."
    ),
    "pxt_dribble_absolute_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Gecreëerd gevaar\nmet dribbels",
        tooltip="Gecreëerd gevaar met dribbels, geschaald naar balbezit."
    ),
    "pxt_rec_absolute_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Gecreëerd gevaar\nals ontvanger",
        tooltip="Gecreëerd gevaar als pass ontvanger, geschaald naar balbezit."
    ),
    "goals_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Doelpunten",
        tooltip="Doelpunten (zonder penalties), geschaald naar balbezit"
    ),
    "shot_xg_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Verwachte\ndoelpunten",
        tooltip="Verwachte doelpunten (zonder penalties), geschaald naar balbezit"
    ),
    "postshot_xg_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Verwachte\ndoelpunten\nna schot",
        tooltip="Verwachte doelpunten na schot (zonder penalties), geschaald naar balbezit"
    ),
    "ball_loss_removed_teammates_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Balverlies\nverwijderde\nteamgenoten",
        tooltip="Balverlies verwijderde teamgenoten, geschaald naar balbezit."
    ),
    "ball_loss_added_opponents_tip_p30_percentile": Metric(
        category=MetricCategory.ATTACK,
        label="Balverlies\ntoegevoegde\ntegenstanders",
        tooltip="Balverlies toegevoegde tegenstanders, geschaald naar balbezit."
    ),

    # Defending metrics
    "ball_win_removed_opponents_otip_p30_percentile": Metric(
        category=MetricCategory.DEFENSE,
        label="Aanvallende\nveroveringen",
        tooltip="Het totaal aantal verwijderde tegenstanders, die niet meer in staat zijn om te verdedigen, door balveroveringen hoog op het veld."
    ),
    "ball_win_added_teammates_otip_p30_percentile": Metric(
        category=MetricCategory.DEFENSE,
        label="Verdedigende\nveroveringen",
        tooltip="Het totaal aantal toevoegde teamgenoten, die weer in staat zijn deel te nemen aan het spel, door balveroveringen laag op het veld."
    ),
    "ground_duels_won_p90_percentile": Metric(
        category=MetricCategory.DEFENSE,
        label="Gewonnen\ngrondduels",
        tooltip="Het totaal aantal gewonnen grondduels per 90 minuten."
    ),
    "ground_duels_won_percentage_percentile": Metric(
        category=MetricCategory.DEFENSE,
        label="Winstpercentage\ngrondduels",
        tooltip="Het winstpercentage van grondduels."
    ),
    "aerial_duels_won_p90_percentile": Metric(
        category=MetricCategory.DEFENSE,
        label="Gewonnen\nluchtduels",
        tooltip="Het totaal aantal gewonnen luchtduels per 90 minuten."
    ),
    "aerial_duels_won_percentage_percentile": Metric(
        category=MetricCategory.DEFENSE,
        label="Winstpercentage\nluchtduels",
        tooltip="Het winstpercentage van luchtduels."
    ),
    "press_total_count_otip_p30_percentile": Metric(
        category=MetricCategory.DEFENSE,
        label="Druk\nzetten",
        tooltip="Het totaal aantal momenten van drukzetten, geschaald naar balbezit."
    ),
    "press_total_stop_danger_otip_p30_percentile": Metric(
        category=MetricCategory.DEFENSE,
        label="Gestopt gevaar\nmet verdedigende acties",
        tooltip="Het totaal aantal momenten van drukzetten waarbij het gevaar is gestopt, geschaald naar balbezit."
    ),
}

# Position profiles: which metrics to show per position (matches scouting_streamlit.py)
position_profiles = {
    'LB': [
        'total_distance_p90_percentile',
        'running_distance_p90_percentile',
        'hi_distance_p90_percentile',
        'total_minutes_percentile',
        'bypass_midfield_defense_pass_tip_p30_percentile',
        'bypass_midfield_defense_dribble_tip_p30_percentile',
        'bypass_opponents_rec_tip_p30_percentile',
        'off_ball_runs_total_tip_p30_percentile',
        'involvement_chances_tip_p30_percentile',
        'ball_win_removed_opponents_otip_p30_percentile',
        'ball_win_added_teammates_otip_p30_percentile',
        'ground_duels_won_p90_percentile',
        'aerial_duels_won_p90_percentile',
    ],
    'RB': [
        'total_distance_p90_percentile',
        'running_distance_p90_percentile',
        'hi_distance_p90_percentile',
        'total_minutes_percentile',
        'bypass_midfield_defense_pass_tip_p30_percentile',
        'bypass_midfield_defense_dribble_tip_p30_percentile',
        'bypass_opponents_rec_tip_p30_percentile',
        'off_ball_runs_total_tip_p30_percentile',
        'involvement_chances_tip_p30_percentile',
        'ball_win_removed_opponents_otip_p30_percentile',
        'ball_win_added_teammates_otip_p30_percentile',
        'ground_duels_won_p90_percentile',
        'aerial_duels_won_p90_percentile',
    ],
    'CB': [
        'total_distance_p90_percentile',
        'running_distance_p90_percentile',
        'hi_distance_p90_percentile',
        'total_minutes_percentile',
        'bypass_midfield_defense_pass_tip_p30_percentile',
        'bypass_midfield_defense_dribble_tip_p30_percentile',
        'ball_win_removed_opponents_otip_p30_percentile',
        'ball_win_added_teammates_otip_p30_percentile',
        'ground_duels_won_p90_percentile',
        'aerial_duels_won_p90_percentile',
    ],
    'DM/CM': [
        'total_distance_p90_percentile',
        'running_distance_p90_percentile',
        'hi_distance_p90_percentile',
        'total_minutes_percentile',
        'bypass_midfield_defense_pass_tip_p30_percentile',
        'bypass_midfield_defense_dribble_tip_p30_percentile',
        'bypass_opponents_rec_tip_p30_percentile',
        'off_ball_runs_total_tip_p30_percentile',
        'involvement_chances_tip_p30_percentile',
        'ball_win_removed_opponents_otip_p30_percentile',
        'ball_win_added_teammates_otip_p30_percentile',
        'ground_duels_won_p90_percentile',
        'aerial_duels_won_p90_percentile',
    ],
    'CAM': [
        'total_distance_p90_percentile',
        'running_distance_p90_percentile',
        'hi_distance_p90_percentile',
        'total_minutes_percentile',
        'pxt_pass_absolute_tip_p30_percentile',
        'pxt_dribble_absolute_tip_p30_percentile',
        'pxt_rec_absolute_tip_p30_percentile',
        'off_ball_runs_total_tip_p30_percentile',
        'shot_xg_tip_p30_percentile',
        'chance_created_tip_p30_percentile',
        'ball_win_removed_opponents_otip_p30_percentile',
        'ball_win_added_teammates_otip_p30_percentile',
        'ground_duels_won_p90_percentile',
        'aerial_duels_won_p90_percentile',
    ],
    'LW': [
        'total_distance_p90_percentile',
        'running_distance_p90_percentile',
        'hi_distance_p90_percentile',
        'total_minutes_percentile',
        'pxt_pass_absolute_tip_p30_percentile',
        'pxt_dribble_absolute_tip_p30_percentile',
        'pxt_rec_absolute_tip_p30_percentile',
        'off_ball_runs_total_tip_p30_percentile',
        'shot_xg_tip_p30_percentile',
        'chance_created_tip_p30_percentile',
        'ball_win_removed_opponents_otip_p30_percentile',
        'ball_win_added_teammates_otip_p30_percentile',
        'ground_duels_won_p90_percentile',
        'aerial_duels_won_p90_percentile',
    ],
    'RW': [
        'total_distance_p90_percentile',
        'running_distance_p90_percentile',
        'hi_distance_p90_percentile',
        'total_minutes_percentile',
        'pxt_pass_absolute_tip_p30_percentile',
        'pxt_dribble_absolute_tip_p30_percentile',
        'pxt_rec_absolute_tip_p30_percentile',
        'off_ball_runs_total_tip_p30_percentile',
        'shot_xg_tip_p30_percentile',
        'chance_created_tip_p30_percentile',
        'ball_win_removed_opponents_otip_p30_percentile',
        'ball_win_added_teammates_otip_p30_percentile',
        'ground_duels_won_p90_percentile',
        'aerial_duels_won_p90_percentile',
    ],
    'ST': [
        'total_distance_p90_percentile',
        'running_distance_p90_percentile',
        'hi_distance_p90_percentile',
        'total_minutes_percentile',
        'pxt_pass_absolute_tip_p30_percentile',
        'pxt_dribble_absolute_tip_p30_percentile',
        'pxt_rec_absolute_tip_p30_percentile',
        'off_ball_runs_total_tip_p30_percentile',
        'goals_tip_p30_percentile',
        'shot_xg_tip_p30_percentile',
        'postshot_xg_tip_p30_percentile',
        'ball_win_removed_opponents_otip_p30_percentile',
        'ball_win_added_teammates_otip_p30_percentile',
        'ground_duels_won_p90_percentile',
        'aerial_duels_won_p90_percentile',
    ]
}


# Table columns (matching Bram's layout)
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

# Custom position ordering
CUSTOM_POSITION_ORDER = [
    "LB (AANV)", "LB (VERD)", "RB (AANV)", "RB (VERD)", "CB (AANV)", "CB (VERD)",
    "DM/CM (DEF)", "DM/CM (BTB)", "DM/CM (CREA)", "CAM (CREA)", "CAM (LOP)",
    "LW (BIN)", "LW (BUI)", "RW (BIN)", "RW (BUI)", "ST (DYN)", "ST (TARG)", "ST (DIEP)"
]

# ✅ Paste your existing huge TEAM_LOGO_MAPPING here unchanged
TEAM_LOGO_MAPPING = {
    # ... keep your full mapping exactly as-is ...
}

# =========================
# CSS with FC Groningen styling
# =========================
st.markdown(
    f"""
    <style>
      @import url('https://fonts.cdnfonts.com/css/proxima-nova-2');

      html, body, [class*="css"], .stApp {{
        font-family: 'Proxima Nova', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
      }}

      section[data-testid="stSidebar"] {{
        background-color: #E9F4ED;
        overflow-y: auto !important;
      }}

      section[data-testid="stSidebar"] > div {{
        overflow-y: visible !important;
      }}

      section[data-testid="stSidebar"] > div:first-child {{
        padding-top: 0 !important;
      }}

      section[data-testid="stSidebar"] div[style*="text-align: center"] {{
        margin-bottom: 50px !important;
      }}

      section[data-testid="stSidebar"] .block-container {{
        padding-top: 0.2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 0.5rem !important;
      }}

      section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div {{
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
      }}

      div[data-testid="stVerticalBlock"] > div {{
        padding-top: 0.05rem;
        padding-bottom: 0.05rem;
      }}

      section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
        font-size: 16px !important;
        color: #000000 !important;
      }}

      section[data-testid="stSidebar"] div[data-baseweb="select"] {{
        margin-bottom: 0.3rem !important;
      }}

      section[data-testid="stSidebar"] div[data-testid="stSlider"] {{
        padding-top: 0rem !important;
        padding-bottom: 0.3rem !important;
      }}

      section[data-testid="stSidebar"] .element-container {{
        margin-bottom: 0.2rem !important;
      }}

      .sb-title {{
        font-size: 24px;
        font-weight: 700;
        margin: 0 0 4px 0;
        padding: 0;
        font-family: 'Proxima Nova', sans-serif !important;
      }}
      .sb-rule {{
        height: 1px;
        background: rgba(0,0,0,0.12);
        margin: 0 0 8px 0;
      }}

      section[data-testid="stSidebar"] div[data-testid="stSlider"] label {{
        color: #000000 !important;
      }}

      section[data-testid="stSidebar"] .stSlider > label {{
        padding-bottom: 10px !important;
      }}

      [data-testid="stAppViewBlockContainer"] {{
        padding-top: 1rem !important;
        margin-top: 0px !important;
      }}

      h1 {{
        margin-top: -30px !important;
        padding-top: 0px !important;
      }}

      .stSubheader {{
        margin-top: -10px !important;
      }}

      [data-testid="stSidebar"] {{
        width: 250px !important;
      }}

      [data-testid="stAppViewMain"] {{
        margin-left: 0px !important;
      }}

      [data-testid="stMainViewContainer"] {{
        width: 100% !important;
      }}

      .custom-info-box {{
        background-color: #E9F4ED;
        color: #000000;
        padding: 12px 20px;
        border-radius: 8px;
        font-size: 1rem;
        margin-bottom: 10px;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# HELPER FUNCTIONS
# =========================
def get_metrics_for_profile(profile_name):
    """Find relevant metrics per category for a selected position."""
    metric_keys = position_profiles.get(profile_name, [])

    categories = {cat.name.lower(): [] for cat in MetricCategory}

    for key in metric_keys:
        if key in metrics:
            metric_obj = metrics[key]
            cat_name = metric_obj.category.name.lower()
            if cat_name in categories:
                categories[cat_name].append(key)

    return categories


def get_gradient_color(score, base_hex):
    """Returns gradient of the main color based on its value."""
    norm = max(0, min(1, score / 100))
    base = [int(base_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)]
    return f'rgb({int(255-(255-base[0])*norm)}, {int(255-(255-base[1])*norm)}, {int(255-(255-base[2])*norm)})'


# =========================
# CHARTS
# =========================
def create_polarized_bar_chart(player_data):
    """
    Create a polarized bar chart (circular bar chart) for a player.
    Uses position_profiles to determine which metrics to show for each position.
    """
    # Get the base position from the player data
    profile_key = player_data.get('position')

    # Get the metrics for this position from position_profiles
    active_metric_keys = position_profiles.get(profile_key, [])

    # Sort into categories
    physical_keys = [k for k in active_metric_keys if metrics[k].category == MetricCategory.PHYSICAL]
    attack_keys = [k for k in active_metric_keys if metrics[k].category == MetricCategory.ATTACK]
    defense_keys = [k for k in active_metric_keys if metrics[k].category == MetricCategory.DEFENSE]

    all_keys = physical_keys + attack_keys + defense_keys

    # Get hover descriptions
    hover_descriptions = [metrics[m].tooltip for m in all_keys]

    # Get percentile scores and labels
    percentile_values = [float(player_data.get(k, 0) if pd.notna(player_data.get(k, 0)) else 0) for k in all_keys]
    metric_labels = [metrics[k].label.replace('\n', '<br>') for k in all_keys]

    # Get the category and total scores
    physical_avg = float(player_data.get('physical', 0) if pd.notna(player_data.get('physical', 0)) else 0)
    attack_avg = float(player_data.get('attacking', 0) if pd.notna(player_data.get('attacking', 0)) else 0)
    defense_avg = float(player_data.get('defending', 0) if pd.notna(player_data.get('defending', 0)) else 0)
    overall_avg = float(player_data.get('total', np.mean([physical_avg, attack_avg, defense_avg])))

    # Set colors
    colors = (
        [get_gradient_color(v, '#3E8C5E') for v in percentile_values[:len(physical_keys)]] +
        [get_gradient_color(v, '#E83F2A') for v in percentile_values[len(physical_keys):len(physical_keys)+len(attack_keys)]] +
        [get_gradient_color(v, '#F2B533') for v in percentile_values[-len(defense_keys):]]
    )

    # Build Figure
    fig = go.Figure()

    fig.add_trace(go.Barpolar(
        r=percentile_values,
        theta=metric_labels,
        marker=dict(color=colors, line=dict(color='white', width=1.5)),
        customdata=hover_descriptions,
        hovertemplate=(
            "<span style='color:black;'><b>Score: %{r:.1f}</b></span><br>"
            "%{customdata}"
            "<extra></extra>"
        )
    ))

    fig.update_layout(
        polar=dict(
            bgcolor='white',
            radialaxis=dict(
                range=[-25, 100],
                visible=True,
                showticklabels=False,
                gridcolor='rgba(0,0,0,0.1)',
                tickvals=[-0.35, 25, 50, 75, 100],
                showline=False,
                ticks=''
            ),
            angularaxis=dict(
                tickfont=dict(size=10, family='Proxima Nova', color='black'),
                rotation=90,
                direction='clockwise',
                showgrid=False,
                showline=True,
                linecolor='black',
                ticks='outside',
                ticklen=8,
                tickwidth=1,
                tickcolor='black'
            )
        ),
        annotations=[
            dict(
                text=f"<b>{overall_avg:.1f}</b>",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=28, color='black', family="ProximaNova-Bold, sans-serif"),
                xref="paper", yref="paper"
            )
        ],
        showlegend=False,
        height=500,
        margin=dict(l=50, r=50, t=100, b=50),
        title=dict(
            text=(
                f"<span style='color:#3E8C5E; font-size:18px; vertical-align: middle;'>●</span> Fysiek: {physical_avg:.1f} | "
                f"<span style='color:#E83F2A; font-size:18px; vertical-align: middle;'>●</span> Aanvallend: {attack_avg:.1f} | "
                f"<span style='color:#F2B533; font-size:18px; vertical-align: middle;'>●</span> Verdedigend: {defense_avg:.1f}"
            ),
            x=0.5, y=0.98, xanchor='center',
            font=dict(family='Proxima Nova', size=16, color='black')
        )
    )

    return fig


def build_radar_3_shapes(row, profile_name):
    """Builds a tri-colored radar chart using structured metric definitions."""
    fig = go.Figure()

    categorized_metrics = get_metrics_for_profile(profile_name)

    def add_group(metric_keys, name, line_color, fill_rgba):
        if not metric_keys:
            return

        r_vals = []
        theta = []

        for m in metric_keys:
            val = row.get(m, 0)
            r_vals.append(float(val) if pd.notna(val) else 0)

            if m in metrics:
                display_label = metrics[m].label.replace('\n', ' ')
            else:
                display_label = m.replace('_', ' ').title()

            theta.append(display_label)

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

    layers = [
        ('physical', "Fysiek", "#3E8C5E", "rgba(62, 140, 94, 0.25)"),
        ('attacking', "Aanval", "#E83F2A", "rgba(232, 63, 42, 0.25)"),
        ('defending', "Verdediging", "#F2B533", "rgba(242, 181, 51, 0.25)")
    ]

    for key, label, line_col, fill_col in layers:
        add_group(categorized_metrics.get(key, []), label, line_col, fill_col)

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


# =========================
# Data
# =========================
@st.cache_data(ttl=3600)
def load_data_from_supabase() -> pd.DataFrame:
    """Load ALL data from Supabase database (handles pagination for >1000 rows)"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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


@st.cache_data(ttl=36000)
def load_impect_urls_from_supabase() -> pd.DataFrame:
    """Load Impect URLs from player_impect_urls table"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        count_response = supabase.table('player_impect_urls').select("id", count='exact').limit(1).execute()
        total_count = count_response.count

        all_urls = []
        page_size = 1000

        for offset in range(0, total_count, page_size):
            response = supabase.table('player_impect_urls').select(
                "player_id, player_name, iterationid, position, impect_url"
            ).range(offset, offset + page_size - 1).execute()
            all_urls.extend(response.data)

        df_urls = pd.DataFrame(all_urls)
        return df_urls

    except Exception as e:
        st.warning(f"Could not load Impect URLs: {str(e)}")
        return pd.DataFrame()


def sanitize_filename(name):
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


def encode_image_to_base64(logo_path):
    """Helper to convert an image file to a base64 string."""
    img = Image.open(logo_path)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


@st.cache_data
def get_team_logo_base64(team_name: str, competition_name: str = None) -> str:
    if not team_name:
        return None

    try:
        logo_filename = TEAM_LOGO_MAPPING.get(team_name, team_name)
        safe_filename = sanitize_filename(logo_filename)
        paths_to_try = []

        if competition_name:
            safe_comp = competition_name.replace("/", "_").replace("\\", "_")
            comp_folder = Path(TEAM_LOGOS_DIR) / safe_comp

            if comp_folder.exists():
                paths_to_try.append(comp_folder / f"{safe_filename}.png")

                for file in comp_folder.glob("*.png"):
                    if safe_filename.lower() in file.stem.lower():
                        paths_to_try.append(file)

        paths_to_try.append(Path(TEAM_LOGOS_DIR) / f"{safe_filename}.png")

        if logo_filename != team_name:
            paths_to_try.append(Path(TEAM_LOGOS_DIR) / f"{sanitize_filename(team_name)}.png")

        for logo_path in paths_to_try:
            if logo_path.exists():
                return encode_image_to_base64(logo_path)

    except Exception:
        pass

    return None


def get_player_url(row):
    """Finds the related player Impect url."""
    if pd.notna(row.get('impect_url')) and row.get('impect_url'):
        return row['impect_url']
    return None


def create_team_html_with_logo(row):
    """Create column that combines team logo with name."""
    team_name = row['team_name']
    competition = row.get('competition_name')
    logo_b64 = get_team_logo_base64(team_name, competition)
    if logo_b64:
        return f'<img src="{logo_b64}" height="20" style="vertical-align: middle; margin-right: 8px;">{team_name}'
    return team_name


# =========================
# LOAD DATA
# =========================
with st.spinner('Ophalen van de data...'):
    df_player_data = load_data_from_supabase()

with st.spinner('Creëeren van Impect connectie...'):
    df_impect_urls = load_impect_urls_from_supabase()

# Merge Impect URLs
if not df_impect_urls.empty:
    url_lookup = df_impect_urls[['player_id', 'position', 'impect_url']].drop_duplicates(
        subset=['player_id', 'position']
    )
    df_player_data = df_player_data.merge(
        url_lookup,
        on=['player_id', 'position'],
        how='left'
    )


# =========================
# SIDEBAR & FILTERS
# =========================
with st.sidebar:
    try:
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

    st.markdown('<div class="sb-title">Filters</div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-rule"></div>', unsafe_allow_html=True)

st.title("Scouting dashboard")

# Add title and divider for first table
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


# Build position and filter options
competitions = sorted(df_player_data["competition_name"].dropna().unique())
seasons = sorted(df_player_data["season_name"].dropna().unique())
raw_positions = df_player_data["position_profile"].dropna().unique()
positions = sorted(raw_positions, key=lambda x: CUSTOM_POSITION_ORDER.index(x) if x in CUSTOM_POSITION_ORDER else 999)

default_competitions = ["Eredivisie"] if "Eredivisie" in competitions else competitions
default_seasons = ["2025/2026"] if "2025/2026" in seasons else seasons

dropdown_competition = st.sidebar.multiselect("Competitie", competitions, default=default_competitions)
dropdown_season = st.sidebar.multiselect("Seizoen", seasons, default=default_seasons)
dropdown_positions = st.sidebar.multiselect("Positie (profiel)", positions, default=positions)

# Dynamic teams dropdown
teams = sorted(df_player_data[
    df_player_data["competition_name"].isin(dropdown_competition) &
    df_player_data["season_name"].isin(dropdown_season)
]["team_name"].dropna().unique())

dropdown_teams = st.sidebar.multiselect("Club (optioneel)", teams, default=[])

age_min = int(np.nanmin(df_player_data["age"].values))
age_max = int(np.nanmax(df_player_data["age"].values))
age_range = st.sidebar.slider(
    "Leeftijd range",
    min_value=age_min,
    max_value=age_max,
    value=(age_min, age_max),
    step=1,
)

show_eu_only = st.sidebar.checkbox(
    "Alleen EU spelers",
    value=False,
    help="Selecteer alleen spelers die een EU paspoort hebben"
)


# Apply filters
mask = (
    df_player_data["competition_name"].isin(dropdown_competition)
    & df_player_data["season_name"].isin(dropdown_season)
    & df_player_data["age"].between(age_range[0], age_range[1])
    & df_player_data["position_profile"].isin(dropdown_positions)
)

if dropdown_teams:
    mask &= df_player_data["team_name"].isin(dropdown_teams)

if show_eu_only and 'european' in df_player_data.columns:
    mask &= (df_player_data["european"] == True)

df_filtered = df_player_data.loc[mask].copy()

df_filtered.sort_values("total", ascending=False, inplace=True, na_position="last")
df_filtered["original_rank"] = range(1, len(df_filtered) + 1)

df_top = df_filtered.head(int(top_n)).copy()

df_top = df_top[
    (df_top["physical"] >= min_physical) &
    (df_top["attacking"] >= min_attack) &
    (df_top["defending"] >= min_defense)
]

if len(df_top) == 0:
    st.info("No players match the current filters.")
    st.stop()


# =========================
# TOP TABLE
# =========================
df_show = df_top.copy()

# Round numeric columns
numeric_columns = ["age", "total_minutes", "position_minutes", "physical", "attacking", "defending", "total"]
for col in numeric_columns:
    if col in df_show.columns:
        decimals = 0 if col in ["total_minutes", "position_minutes"] else 1
        df_show[col] = df_show[col].round(decimals)

# Create dynamic columns
df_show["player_url"] = df_show.apply(get_player_url, axis=1)
df_show["team_with_logo_html"] = df_show.apply(create_team_html_with_logo, axis=1)
df_show["_original_index"] = df_top.index

# Reorder and rename columns
df_show = df_show[list(table_columns.keys()) + ["player_url", "_original_index"]]
df_show = df_show.rename(columns=table_columns)

# JS Renderers
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

number_dot_formatter = JsCode("""
function(params) {
    if (params.value == null) return '';
    return params.value.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ".");
}
""")

# Conditional formatting (gradient green for high scores)
COLOR_THRESHOLD = 30
gradient_js = JsCode(f"""
function(params) {{
    if (params.value == null || isNaN(params.value)) return {{}};
    
    let val = params.value;
    let threshold = {COLOR_THRESHOLD};
    
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
    
    let factor = (val - threshold) / (100 - threshold); 
    factor = Math.min(1, Math.max(0, factor)); 
    
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


# Build AgGrid for top table
gb = GridOptionsBuilder.from_dataframe(df_show)

gb.configure_column(table_columns["original_rank"], width=80, pinned="left", sortable=True, type=["numericColumn"])
gb.configure_column(table_columns["player_name"], width=180, pinned="left", cellRenderer=player_link_renderer)
gb.configure_column(table_columns["team_with_logo_html"], width=200, cellRenderer=team_logo_renderer)

for key, label in table_columns.items():
    if key not in ["original_rank", "player_name", "team_with_logo_html", "position_profile"]:
        is_numeric = key in ["age", "total_minutes", "position_minutes", "physical", "attacking", "defending", "total"]

        col_config = {
            "width": 140,
            "type": ["numericColumn"] if is_numeric else [],
            "sortingOrder": ["desc", "asc", None]
        }

        if key in ["total_minutes", "position_minutes"]:
            col_config["valueFormatter"] = number_dot_formatter

        if key in ["physical", "attacking", "defending"]:
            col_config["cellStyle"] = gradient_js

        gb.configure_column(label, **col_config)

gb.configure_column("player_url", hide=True)
gb.configure_column("_original_index", hide=True)
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

# Check which players are selected from top table
selected_from_top_table = []
selected_from_top_table_full_data = []

if top_grid_response and top_grid_response.get('selected_rows') is not None:
    selected_rows = top_grid_response['selected_rows']

    if isinstance(selected_rows, pd.DataFrame):
        rows = selected_rows.to_dict('records')
    else:
        rows = selected_rows

    for row in rows:
        name_col = table_columns.get('player_name', 'player_name')
        selected_from_top_table.append(row.get(name_col))

        idx = row.get('_original_index')
        if idx is not None and idx in df_top.index:
            selected_from_top_table_full_data.append(df_top.loc[idx])


# =========================
# RADAR PLOT CONTAINER
# =========================
st.subheader("Radarplots")
st.markdown('<div class="sb-rule"></div>', unsafe_allow_html=True)
radar_plot_container = st.container()


# =========================
# PLAYER SEARCH (Bottom Table)
# =========================
st.subheader("Zoekopdracht")
st.markdown('<div class="sb-rule"></div>', unsafe_allow_html=True)

available_players = sorted(df_player_data["player_name"].unique().tolist())

search_selected_players = st.multiselect(
    "Selecteer speler(s) en zie alle beschikbare data.",
    options=available_players,
    default=[],
    help="Een speler kan er niet tussen staan als we geen data van die competitie afnemen of als hij onvoldoende minuten op een specifieke positie heeft gemaakt"
)

# Filter and sort data
df_selected_players = df_player_data[df_player_data['player_name'].isin(search_selected_players)].copy().sort_values(by='total', ascending=False)

# Create master index
df_selected_players["_original_index"] = df_selected_players.index

# Reset the index
df_selected_players.reset_index(drop=True, inplace=True)

# Add helper columns
df_selected_players['original_rank'] = df_selected_players.index + 1
df_selected_players["player_url"] = df_selected_players.apply(get_player_url, axis=1)
df_selected_players["team_with_logo_html"] = df_selected_players.apply(create_team_html_with_logo, axis=1)

# Round numeric columns
for col in numeric_columns:
    if col in df_selected_players.columns:
        decimals = 0 if col in ["total_minutes", "position_minutes"] else 1
        df_selected_players[col] = df_selected_players[col].round(decimals)

# Reorder and rename columns
all_needed_cols = list(table_columns.keys()) + ["player_url", "_original_index"]
df_selected_players = df_selected_players[[c for c in all_needed_cols if c in df_selected_players.columns]]
df_selected_players = df_selected_players.rename(columns=table_columns)

# Create search table grid
gb_search = GridOptionsBuilder.from_dataframe(df_selected_players)

gb_search.configure_column(table_columns["original_rank"], width=80, pinned="left", sortable=True, type=["numericColumn"])
gb_search.configure_column(table_columns["player_name"], width=180, pinned="left", cellRenderer=player_link_renderer)
gb_search.configure_column(table_columns["team_with_logo_html"], width=200, cellRenderer=team_logo_renderer)

for key, label in table_columns.items():
    if key not in ["original_rank", "player_name", "team_with_logo_html", "position_profile"]:
        is_numeric = key in ["age", "total_minutes", "position_minutes", "physical", "attacking", "defending", "total"]

        col_config = {
            "width": 140,
            "type": ["numericColumn"] if is_numeric else [],
            "sortingOrder": ["desc", "asc", None]
        }

        if key in ["total_minutes", "position_minutes"]:
            col_config["valueFormatter"] = number_dot_formatter

        if key in ["physical", "attacking", "defending"]:
            col_config["cellStyle"] = gradient_js

        gb_search.configure_column(label, **col_config)

gb_search.configure_column("player_url", hide=True)
gb_search.configure_column("_original_index", hide=True)
gb_search.configure_column("::auto_unique_id::", hide=True)
gb_search.configure_default_column(sortable=True, filterable=False, resizable=True)
gb_search.configure_selection(selection_mode='multiple', use_checkbox=True)

gridOptions_search = gb_search.build()

search_grid_response = None

if not df_selected_players.empty:
    search_grid_response = AgGrid(
        df_selected_players,
        gridOptions=gridOptions_search,
        enable_enterprise_modules=False,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=min(615, 34.5 + len(df_selected_players) * 29.1),
        fit_columns_on_grid_load=False,
        theme='streamlit'
    )

# Check which boxes are checked in search table
selected_from_search_table = []
selected_from_search_table_full_data = []

selected_rows = []
if 'search_grid_response' in locals() and search_grid_response is not None:
    selected_rows = search_grid_response.get('selected_rows', [])

if isinstance(selected_rows, pd.DataFrame):
    selected_rows = selected_rows.to_dict('records')

if isinstance(selected_rows, list) and len(selected_rows) > 0:
    for row in selected_rows:
        name_label = table_columns.get('player_name', 'Speler')
        p_name = row.get(name_label)
        idx = row.get('_original_index') or row.get('_search_original_index')

        if idx is not None and idx in df_player_data.index:
            selected_from_search_table.append(p_name)
            selected_from_search_table_full_data.append(df_player_data.loc[idx])


# ========================================
# FILL RADAR PLOT CONTAINER
# ========================================
with radar_plot_container:

    # Combine the selections from both tables
    all_selected_names = selected_from_top_table + selected_from_search_table
    all_selected_data = selected_from_top_table_full_data + selected_from_search_table_full_data

    total_selected = len(all_selected_names)

    if total_selected > 0:
        if total_selected > 2:
            st.warning(f"Je hebt {total_selected} spelers geselecteerd, alleen de eerste 2 worden getoond.")

        players_to_compare = all_selected_names[:2]
        players_data_to_compare = all_selected_data[:2]

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
            player_data = players_data_to_compare[i]

            with cols[i]:

                # Create title with position profile
                pos_profile = player_data.get('position_profile', '')
                title_text = f"{player_name}  |  {pos_profile}"

                st.markdown(
                    f"<p style='font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem; text-align: center;'>{title_text}</p>",
                    unsafe_allow_html=True
                )

                # Get information for subtitles
                team_name = player_data['team_name']
                competition = player_data.get('competition_name')
                season = player_data.get('season_name')
                team_logo_b64 = get_team_logo_base64(team_name, competition)

                # Format the numbers with a thousand separator
                total_minutes = f"{int(player_data['total_minutes']):,}".replace(',', '.')
                position_minutes_val = player_data.get('position_minutes', 0)
                position_minutes = f"{int(position_minutes_val):,}".replace(',', '.') if pd.notna(position_minutes_val) else "0"

                line1 = f"{team_name} | {competition} | {season}"
                line2 = f"{int(player_data['age'])} jaar · Nationaliteit: {player_data['country']} · Totale minuten: {total_minutes} · Minuten op positie: {position_minutes}"

                logo_html = f'<img src="{team_logo_b64}" height="30" style="vertical-align: middle; margin-right: 8px;">' if team_logo_b64 else ""
                st.markdown(
                    f"""<div style="font-size: 1.1rem; margin-bottom: 1rem; line-height: 1.4; text-align: center;">
                        {logo_html} <b>{line1}</b><br>
                        <span style="font-size: 0.95rem; color: #666;">{line2}</span>
                    </div>""",
                    unsafe_allow_html=True
                )

                # Create the chart
                fig = create_polarized_bar_chart(player_data)

                chart_key = f"comparison_chart_{i}_{player_name.replace(' ', '_')}"
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=chart_key)

                # Add information at the bottom
                st.markdown(
                    """<p style='text-align: center; font-family: "Proxima Nova", sans-serif; 
                    font-size: 0.8rem; color: #888; margin-top: -15px;'>
                    Een score van 50 is het gemiddelde op die positie binnen die competitie <br>
                    Data is een combinatie van Impect en SkillCorner
                    </p>""",
                    unsafe_allow_html=True
                )
    else:
        st.markdown(
            """
            <div class="custom-info-box">
                Selecteer spelers in de ranglijst en/of zoekopdracht tabellen om hun radarplots te zien.
            </div>
            """,
            unsafe_allow_html=True
        )
