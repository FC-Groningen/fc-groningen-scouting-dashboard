import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from PIL import Image
import base64
from io import BytesIO
from pathlib import Path
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

PHYSICAL_METRICS = [
    "total_distance_p90_percentile",
    "running_distance_p90_percentile",
    "hsr_distance_p90_percentile",
    "sprint_distance_p90_percentile"
]

ATTACK_METRICS = [
    "bypass_midfield_defense_tip_p30_percentile",
    "bypass_opponents_rec_tip_p30_percentile",
    "off_ball_runs_total_tip_p30_percentile",
    "involvement_chances_tip_p30_percentile",
    "ball_loss_removed_teammates_tip_p30_percentile",
    "ball_loss_added_opponents_tip_p30_percentile"
]

DEFENSE_METRICS = [
    "ball_win_removed_opponents_otip_p30_percentile",
    "ball_win_added_teammates_otip_p30_percentile",
    "ground_duels_won_percentage_percentile",
    "aerial_duels_won_percentage_percentile",
    "press_total_stop_danger_otip_p30_percentile"
]



# =============================================================================
# DM/CM POSITION PROFILE RADAR METRICS (match scouting_model_* profile weights)
# These are ONLY used for the radar chart variable set (Top-20 ranking stays the same).
# =============================================================================
DMCM_PROFILE_PHYSICAL_METRICS = [
    "total_distance_p90_percentile",
    "running_distance_p90_percentile",
    "hi_distance_p90_percentile",
    "total_minutes_percentile"
]

DMCM_PROFILE_ATTACK_METRICS = [
    "bypass_midfield_defense_pass_tip_p30_percentile",
    "bypass_midfield_defense_dribble_tip_p30_percentile",
    "bypass_opponents_rec_tip_p30_percentile",
    "off_ball_runs_total_tip_p30_percentile",
    "involvement_chances_tip_p30_percentile"
]

DMCM_PROFILE_DEFENSE_METRICS = [
    "ball_win_removed_opponents_otip_p30_percentile",
    "ball_win_added_teammates_otip_p30_percentile",
    "ground_duels_won_p90_percentile",
    "aerial_duels_won_p90_percentile",
    "press_total_count_otip_p30_percentile"
]
LABELS = {
    "total_distance_p90_percentile": "Totale\nafstand",
    "running_distance_p90_percentile": "15-20km/u\nafstand",
    "hsr_distance_p90_percentile": "20-25km/u\nafstand",
    "sprint_distance_p90_percentile": "25+km/u\nafstand",
    "bypass_midfield_defense_tip_p30_percentile": "Uitgespeelde\ntegenstanders",
    "bypass_opponents_rec_tip_p30_percentile": "Uitgespeelde\ntegenstanders\nals ontvanger",
    "off_ball_runs_total_tip_p30_percentile": "Loopacties\nzonder bal",
    "involvement_chances_tip_p30_percentile": "Betrokkenheid\nkansen",
    "ball_loss_removed_teammates_tip_p30_percentile": "Balverlies\nverwijderde\nteamgenoten",
    "ball_loss_added_opponents_tip_p30_percentile": "Balverlies\ntoegevoegde\ntegenstanders",
    "ball_win_removed_opponents_otip_p30_percentile": "Aanvallende\nveroveringen",
    "ball_win_added_teammates_otip_p30_percentile": "Verdedigende\nveroveringen",
    "ground_duels_won_percentage_percentile": "Winstpercentage\ngrondduels",
    "aerial_duels_won_percentage_percentile": "Winstpercentage\nluchtduels",
    "press_total_stop_danger_otip_p30_percentile": "Gestopt gevaar\nmet verdedigende actie",

    "hi_distance_p90_percentile": "20+km/u\nafstand",
    "total_minutes_percentile": "Totale\nspeeltijd",
    "bypass_midfield_defense_pass_tip_p30_percentile": "Uitgespeelde\ntegenstanders\n(pass)",
    "bypass_midfield_defense_dribble_tip_p30_percentile": "Uitgespeelde\ntegenstanders\n(dribbel)",
    "ground_duels_won_p90_percentile": "Gewonnen\ngrondduels",
    "aerial_duels_won_p90_percentile": "Gewonnen\nluchtduels",
    "press_total_count_otip_p30_percentile": "Druk\nzetten",
}

DISPLAY_COLS = {
    "player_name": "Player Name",
    "team_name": "Team",
    "country": "Nationality",
    "age": "Age",
    "display_position": "Position",
    "total_minutes": "Minutes",
    "competition_name": "Competition",
    "season_name": "Season",
    "physical": "Physical",
    "attack": "Attack",
    "defense": "Defense",
    "total": "Total",
}

FC_GRONINGEN_GREEN = "#3E8C5E"

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
        background-color: #F4F6F8;
        overflow-y: auto !important;
      }}

      section[data-testid="stSidebar"] > div {{
        overflow-y: visible !important;
      }}

      section[data-testid="stSidebar"] > div:first-child {{
        padding-top: 0 !important;
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

      section[data-testid="stSidebar"] label {{
        margin-bottom: 0.2rem !important;
        font-size: 14px !important;
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

      div[data-testid="stSlider"] * {{ color: #111111 !important; }}
      section[data-testid="stSidebar"] div[data-testid="stSlider"] * {{ color: #111111 !important; }}
      div[data-baseweb="slider"] * {{ color: #111111 !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# CHARTS
# =========================
def create_polarized_bar_chart(player_data: pd.Series, competition_name: str, season_name: str) -> go.Figure:
    """
    Create a polarized bar chart (circular bar chart) for a player.
    Shows 15 metrics in 3 categories: Physical (4), Attack (6), Defense (5).

    ✅ FIX: Overall score is taken from player_data['total'] (same as the table Total column) when available;
           fallback is the mean of physical/attack/defense if 'total' is missing.
    """
    # -----------------------------------------------------------------
    # Select metric set for the radar chart.
    # DM/CM profiles use the updated profile metrics (pass/dribble split, press count, etc.)
    # All other positions keep the original metric set.
    # -----------------------------------------------------------------
    display_pos = None
    if isinstance(player_data, pd.Series):
        # Prefer display_position if it exists; otherwise use position_profile/position
        if 'display_position' in player_data.index and pd.notna(player_data.get('display_position')):
            display_pos = str(player_data.get('display_position'))
        elif 'position_profile' in player_data.index and pd.notna(player_data.get('position_profile')):
            display_pos = str(player_data.get('position_profile'))
        elif 'position' in player_data.index and pd.notna(player_data.get('position')):
            display_pos = str(player_data.get('position'))

    is_dmcm_profile = bool(display_pos) and display_pos.startswith("DM/CM (") and display_pos.endswith(")")

    # Use profile label in the chart caption when available
    position_caption = display_pos if display_pos else (str(player_data.get('position')) if 'position' in player_data.index else "")

    physical_metrics = DMCM_PROFILE_PHYSICAL_METRICS if is_dmcm_profile else PHYSICAL_METRICS
    attack_metrics   = DMCM_PROFILE_ATTACK_METRICS   if is_dmcm_profile else ATTACK_METRICS
    defense_metrics  = DMCM_PROFILE_DEFENSE_METRICS  if is_dmcm_profile else DEFENSE_METRICS

    green = '#3E8C5E'
    red = '#E83F2A'
    yellow = '#F2B533'

    def lighten_color(hex_color, amount=0.6):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(r + (255 - r) * amount)
        g = int(g + (255 - g) * amount)
        b = int(b + (255 - b) * amount)
        return f'#{r:02x}{g:02x}{b:02x}'

    def get_gradient_color(base_color, score, min_score=0, max_score=100):
        normalized = (score - min_score) / (max_score - min_score) if max_score > min_score else 0
        normalized = max(0, min(1, normalized))
        light_color = lighten_color(base_color, amount=0.6)
        light_rgb = tuple(int(light_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        dark_rgb = tuple(int(base_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        r = int(light_rgb[0] + (dark_rgb[0] - light_rgb[0]) * normalized)
        g = int(light_rgb[1] + (dark_rgb[1] - light_rgb[1]) * normalized)
        b = int(light_rgb[2] + (dark_rgb[2] - light_rgb[2]) * normalized)
        return f'rgb({r},{g},{b})'

    plot_columns = physical_metrics + attack_metrics + defense_metrics
    percentile_values = [player_data[col] if col in player_data.index else 0 for col in plot_columns]

    category_mapping = (
        [1] * len(physical_metrics) +
        [2] * len(attack_metrics) +
        [3] * len(defense_metrics)
    )

    category_colors = {1: green, 2: red, 3: yellow}

    colors = []
    for score, category_id in zip(percentile_values, category_mapping):
        base_color = category_colors[category_id]
        colors.append(get_gradient_color(base_color, score))

    # ✅ Category averages
    if all(k in player_data.index for k in ['physical', 'attack', 'defense']):
        physical_avg = float(player_data['physical'])
        attack_avg   = float(player_data['attack'])
        defense_avg  = float(player_data['defense'])
    else:
        physical_avg = float(np.mean(percentile_values[0:len(physical_metrics)]))
        attack_avg   = float(np.mean(percentile_values[len(physical_metrics):len(physical_metrics)+len(attack_metrics)]))
        defense_avg  = float(np.mean(percentile_values[len(physical_metrics)+len(attack_metrics):]))

    # ✅ FIX: Overall score should match the table's Total column.
    # Prefer the stored 'total' value (already weighted/defined by the model); fallback to mean of category scores.
    if 'total' in player_data.index and pd.notna(player_data.get('total')):
        overall_avg = float(player_data['total'])
    else:
        overall_avg = float(np.mean([physical_avg, attack_avg, defense_avg]))

    metric_labels = [LABELS.get(col, col).replace('\n', '<br>') for col in plot_columns]

    fig = go.Figure()
    fig.add_trace(go.Barpolar(
        r=percentile_values,
        theta=metric_labels,
        marker=dict(color=colors, line=dict(color='white', width=2)),
        opacity=1.0,
        name='',
        text=[f'{v:.0f}' for v in percentile_values],
        hovertemplate='%{theta}<br>Percentile: %{r:.1f}<extra></extra>'
    ))

    fig.update_layout(
        polar=dict(
            domain=dict(x=[0.02, 0.98], y=[0.0, 0.88]),
            radialaxis=dict(
                visible=True,
                range=[-20, 100],
                showticklabels=False,
                ticks='',
                showline=False,
                showgrid=True,
                gridcolor='rgba(0, 0, 0, 0.2)',
                gridwidth=1,
                tickvals=[25, 50, 75, 100],
                layer='above traces'
            ),
            angularaxis=dict(
                tickfont=dict(size=10, family='Proxima Nova', color='#000000'),
                rotation=90,
                direction='clockwise',
                showgrid=False,
                gridcolor='rgba(0, 0, 0, 0.2)',
                gridwidth=1,
                layer='above traces'
            ),
            bgcolor='rgba(255, 255, 255, 1)'
        ),
        showlegend=False,
        height=500,
        margin=dict(l=80, r=80, t=120, b=80),
        title=dict(
            text=(
                f"<b>Overall: {overall_avg:.1f}</b><br>"
                f"<span style='font-size:14px'>🟢 Fysiek: {physical_avg:.1f} | 🔴 Aanvallen: {attack_avg:.1f} | 🟡 Verdedigen: {defense_avg:.1f}</span><br>"
                f"<span style='font-size:11px; color:#666'>{competition_name} | {season_name}</span>"
            ),
            x=0.5, y=0.95, xanchor='center', yanchor='top',
            font=dict(size=16, family='Proxima Nova', color='black')
        ),
        paper_bgcolor='rgba(255, 255, 255, 1)',
        plot_bgcolor='rgba(255, 255, 255, 1)'
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

        count_response = supabase.table('player_percentiles').select("*", count='exact').limit(1).execute()
        total_count = count_response.count

        all_data = []
        page_size = 1000

        for offset in range(0, total_count, page_size):
            response = supabase.table('player_percentiles').select("*").range(offset, offset + page_size - 1).execute()
            all_data.extend(response.data)

        df = pd.DataFrame(all_data)

        # ✅ FIX 3: Include category columns in numeric conversion
        numeric_cols = (
            ["age", "total_minutes", "physical", "attacking", "defending", "total"] +
            PHYSICAL_METRICS + ATTACK_METRICS + DEFENSE_METRICS
        )
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # ✅ FIX 2: Rename database columns to match app expectations
        if 'attacking' in df.columns:
            df['attack'] = df['attacking']
        if 'defending' in df.columns:
            df['defense'] = df['defending']

        # ✅ FIX 1: Use database scores (correctly weighted for position profiles)
        # Only calculate if database values are missing
        if 'physical' not in df.columns or df['physical'].isna().all():
            df['physical'] = df[PHYSICAL_METRICS].mean(axis=1)
        if 'attack' not in df.columns or df['attack'].isna().all():
            df['attack'] = df[ATTACK_METRICS].mean(axis=1)
        if 'defense' not in df.columns or df['defense'].isna().all():
            df['defense'] = df[DEFENSE_METRICS].mean(axis=1)
        if 'total' not in df.columns or df['total'].isna().all():
            df['total'] = df[['physical', 'attack', 'defense']].mean(axis=1)

        # ✅ FIX 4: Calculate category scores for rows missing them (non-DM/CM players)
        # The scouting model only calculates scores for DM/CM, so other positions have NaN
        mask_missing_scores = (
            df['physical'].isna() | 
            df['attack'].isna() | 
            df['defense'].isna()
        )
        
        if mask_missing_scores.any():
            # Calculate simple averages (equal weights) for missing scores
            df.loc[mask_missing_scores, 'physical'] = df.loc[mask_missing_scores, PHYSICAL_METRICS].mean(axis=1)
            df.loc[mask_missing_scores, 'attack'] = df.loc[mask_missing_scores, ATTACK_METRICS].mean(axis=1)
            df.loc[mask_missing_scores, 'defense'] = df.loc[mask_missing_scores, DEFENSE_METRICS].mean(axis=1)
            df.loc[mask_missing_scores, 'total'] = df.loc[mask_missing_scores, ['physical', 'attack', 'defense']].mean(axis=1)

        return df

    except Exception as e:
        st.error(f"Error loading data from Supabase: {str(e)}")
        st.info("Please check your Supabase credentials in .streamlit/secrets.toml")
        st.stop()
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_impect_urls_from_supabase() -> pd.DataFrame:
    """Load Impect URLs from player_impect_urls table"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        all_urls = []
        page_size = 1000
        offset = 0

        while True:
            response = supabase.table('player_impect_urls').select(
                "player_id, player_name, iterationid, position, impect_url"
            ).range(offset, offset + page_size - 1).execute()

            if not response.data:
                break

            all_urls.extend(response.data)

            if len(response.data) < page_size:
                break

            offset += page_size

        df_urls = pd.DataFrame(all_urls)
        return df_urls

    except Exception as e:
        st.warning(f"Could not load Impect URLs: {str(e)}")
        return pd.DataFrame()


def percentile_0_100(series: pd.Series) -> pd.Series:
    s = series.copy()
    if s.notna().sum() == 0:
        return pd.Series([np.nan] * len(s), index=s.index)
    if s.nunique(dropna=True) <= 1:
        return pd.Series([50.0] * len(s), index=s.index)
    return s.rank(pct=True) * 100.0


def get_relevant_metrics_for_position(row: pd.Series, cohort: pd.DataFrame) -> dict:
    # Default metric sets (legacy radar)
    physical = PHYSICAL_METRICS
    attack   = ATTACK_METRICS
    defense  = DEFENSE_METRICS

    # If this row is a DM/CM position profile, use the profile-specific metric set
    # to match how the model defines DM/CM (DEF/CRE/BTB).
    pos_label = str(row.get("display_position", row.get("position_profile", row.get("position", ""))))
    if pos_label.startswith("DM/CM ("):
        physical = DMCM_PROFILE_PHYSICAL_METRICS
        attack   = DMCM_PROFILE_ATTACK_METRICS
        defense  = DMCM_PROFILE_DEFENSE_METRICS

    return {'physical': physical, 'attack': attack, 'defense': defense}


def build_radar_3_shapes(row: pd.Series, cohort: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    relevant_metrics = get_relevant_metrics_for_position(row, cohort)

    def add_group(metrics, name, line_color, fill_rgba):
        if not metrics:
            return

        r_vals, theta = [], []
        for m in metrics:
            r_vals.append(float(row[m]) if m in row.index and pd.notna(row[m]) else 0)
            theta.append(LABELS.get(m, m).replace('\n', ' '))

        r_vals = r_vals + [r_vals[0]]
        theta  = theta + [theta[0]]

        fig.add_trace(go.Scatterpolar(
            r=r_vals,
            theta=theta,
            fill='toself',
            fillcolor=fill_rgba,
            line=dict(color=line_color, width=2),
            name=name,
            hovertemplate="%{theta}<br>Percentile: %{r:.1f}<extra></extra>"
        ))

    add_group(relevant_metrics['physical'], "Physical", "#3E8C5E", "rgba(62, 140, 94, 0.25)")
    add_group(relevant_metrics['attack'], "Attack", "#E83F2A", "rgba(232, 63, 42, 0.25)")
    add_group(relevant_metrics['defense'], "Defense", "#F2B533", "rgba(242, 181, 51, 0.25)")

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=9))
        ),
        showlegend=True,
        height=400,
        margin=dict(l=60, r=60, t=60, b=60),
    )

    return fig


@st.cache_data
def get_team_logo_base64(team_name: str, competition_name: str = None) -> str:
    if not team_name:
        return None

    try:
        logo_filename = TEAM_LOGO_MAPPING.get(team_name, team_name)

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

        def sanitize_competition_folder(name):
            return name.replace("/", "_").replace("\\", "_")

        safe_filename = sanitize_filename(logo_filename)

        paths_to_try = []

        if competition_name:
            safe_comp = sanitize_competition_folder(competition_name)
            comp_folder = Path(TEAM_LOGOS_DIR) / safe_comp
            paths_to_try.append(comp_folder / f"{safe_filename}.png")

            if logo_filename != team_name:
                paths_to_try.append(comp_folder / f"{sanitize_filename(team_name)}.png")

        paths_to_try.append(Path(TEAM_LOGOS_DIR) / f"{safe_filename}.png")

        if logo_filename != team_name:
            paths_to_try.append(Path(TEAM_LOGOS_DIR) / f"{sanitize_filename(team_name)}.png")

        if competition_name:
            safe_comp = sanitize_competition_folder(competition_name)
            comp_folder = Path(TEAM_LOGOS_DIR) / safe_comp
            if comp_folder.exists():
                for file in comp_folder.glob("*.png"):
                    if safe_filename.lower() in file.stem.lower():
                        paths_to_try.insert(0, file)

        for logo_path in paths_to_try:
            if logo_path.exists():
                img = Image.open(logo_path)
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                return f"data:image/png;base64,{img_str}"

    except Exception:
        pass

    return None


def get_team_fbref_google_search(team_name: str) -> str:
    query = f"{team_name} site:fbref.com"
    return f"https://www.google.com/search?q={query.replace(' ', '+')}"


# =========================
# LOAD DATA
# =========================
with st.spinner('Loading player data...'):
    df = load_data_from_supabase()

with st.spinner('Loading player profiles...'):
    df_impect_urls = load_impect_urls_from_supabase()

if not df_impect_urls.empty:
    # Deduplicate: keep one URL per player/iteration/position to avoid row multiplication on merge
    df_impect_urls_deduped = (
        df_impect_urls[['player_id', 'iterationid', 'position', 'impect_url']]
        .dropna(subset=['impect_url'])
        .drop_duplicates(subset=['player_id', 'iterationid', 'position'], keep='first')
    )
    df = df.merge(
        df_impect_urls_deduped,
        on=['player_id', 'iterationid', 'position'],
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

st.title("FC Groningen Scouting Dashboard")

competitions = sorted(df["competition_name"].dropna().unique())
seasons = sorted(df["season_name"].dropna().unique())

# Build position list that includes position profiles for DM/CM
positions = []
for pos in sorted(df["position"].dropna().unique()):
    if pos == "DM/CM":
        # For DM/CM, add the specific profiles instead of generic position
        if 'position_profile' in df.columns:
            profiles = df[df["position"] == "DM/CM"]["position_profile"].dropna().unique()
            dm_cm_profiles = sorted([p for p in profiles if p and p.startswith("DM/CM")])
            if len(dm_cm_profiles) > 0:
                # Add the specific profiles
                positions.extend(dm_cm_profiles)
            else:
                # Fallback: no profiles exist yet, add generic DM/CM
                positions.append(pos)
        else:
            positions.append(pos)
    else:
        positions.append(pos)

default_competitions = ["Eredivisie"] if "Eredivisie" in competitions else competitions
default_seasons = ["2025/2026"] if "2025/2026" in seasons else seasons

selected_comp = st.sidebar.multiselect("Competition", competitions, default=default_competitions)
selected_season = st.sidebar.multiselect("Season", seasons, default=default_seasons)

age_min = int(np.nanmin(df["age"].values))
age_max = int(np.nanmax(df["age"].values))
age_range = st.sidebar.slider(
    "Age range",
    min_value=age_min,
    max_value=age_max,
    value=(age_min, age_max),
    step=1,
)

show_european_only = st.sidebar.checkbox(
    "European players only",
    value=False,
    help="Filter to show only players from European countries"
)

# Default selection: show DM/CM profiles first (Bram request)
dmcm_default_positions = [p for p in ["DM/CM (DEF)", "DM/CM (CRE)", "DM/CM (BTB)"] if p in positions]
default_positions = dmcm_default_positions if dmcm_default_positions else positions

selected_pos = st.sidebar.multiselect("Position (optional)", positions, default=default_positions)

# Workaround: enforce minimum minutes played IN the selected position for DM/CM profile rows
# (prevents players with low DM/CM minutes from ranking as DM/CM profiles when they mostly played elsewhere)
DMCM_PROFILE_MIN_POSITION_MINUTES = st.sidebar.number_input(
    "DM/CM profile min position minutes",
    min_value=0,
    max_value=5000,
    value=400,
    step=25,
    help="Applies only to DM/CM (DEF/CRE/BTB). Set to 0 to disable."
)


st.subheader("Ranking & Filtering")

col1, col2, col3, col4 = st.columns(4)

with col1:
    top_n = st.number_input("Top N Players", min_value=1, max_value=500, value=20, step=1)

with col2:
    min_physical = st.slider("Physical minimum", min_value=0, max_value=100, value=0, step=1)

with col3:
    min_attack = st.slider("Attack minimum", min_value=0, max_value=100, value=0, step=1)

with col4:
    min_defense = st.slider("Defense minimum", min_value=0, max_value=100, value=0, step=1)

# Build position filter that handles both regular positions and profiles
position_mask = pd.Series([False] * len(df), index=df.index)

for selected in selected_pos:
    if selected.startswith("DM/CM ("):
        # This is a position profile - filter by position_profile column
        if "position_profile" in df.columns:
            dmcm_mask = (df["position_profile"] == selected)
            # Workaround: require sufficient minutes played in DM/CM (position_minutes) for profile rows
            if DMCM_PROFILE_MIN_POSITION_MINUTES and ("position_minutes" in df.columns):
                dmcm_mask &= (df["position_minutes"].fillna(0) >= float(DMCM_PROFILE_MIN_POSITION_MINUTES))
            position_mask |= dmcm_mask

    else:
        # Regular position - filter by position column
        position_mask |= (df["position"] == selected)

mask = (
    df["competition_name"].isin(selected_comp)
    & df["season_name"].isin(selected_season)
    & df["age"].between(age_range[0], age_range[1])
    & position_mask
)

if show_european_only and 'european' in df.columns:
    mask = mask & (df["european"] == True)

df_f = df.loc[mask].copy()
df_f.sort_values("total", ascending=False, inplace=True, na_position="last")
df_f["original_rank"] = range(1, len(df_f) + 1)
df_top = df_f.head(int(top_n)).copy()

df_top = df_top[
    (df_top["physical"] >= min_physical) &
    (df_top["attack"] >= min_attack) &
    (df_top["defense"] >= min_defense)
]

df_f = df_f[
    (df_f["physical"] >= min_physical) &
    (df_f["attack"] >= min_attack) &
    (df_f["defense"] >= min_defense)
]

if len(df_top) == 0:
    st.info("No players match the current filters.")
    st.stop()

# Add display_position column that shows position_profile when available
if 'position_profile' in df_top.columns:
    df_top['display_position'] = df_top.apply(
        lambda row: row['position_profile'] if pd.notna(row.get('position_profile')) and row.get('position_profile') else row['position'],
        axis=1
    )
else:
    df_top['display_position'] = df_top['position']

st.subheader("Top Players Table")

table_cols = list(DISPLAY_COLS.keys())
cols_to_copy = table_cols + ["original_rank"]
if 'impect_url' in df_top.columns:
    cols_to_copy.append('impect_url')
df_show = df_top[cols_to_copy].copy()

df_show['_original_index'] = df_top.index

numeric_display_cols = ["age", "total_minutes", "physical", "attack", "defense", "total"]
for col in numeric_display_cols:
    if col in df_show.columns:
        if col == "total_minutes":
            df_show[col] = df_show[col].round(0)
        else:
            df_show[col] = df_show[col].round(1)

def get_player_url(row):
    if pd.notna(row.get('impect_url')) and row.get('impect_url'):
        return row['impect_url']
    else:
        return get_team_fbref_google_search(row['team_name'])

df_show["player_url"] = df_show.apply(get_player_url, axis=1)

def create_team_html_with_logo(row):
    team_name = row['team_name']
    competition = row.get('competition_name')
    logo_b64 = get_team_logo_base64(team_name, competition)
    if logo_b64:
        return f'<img src="{logo_b64}" height="20" style="vertical-align: middle; margin-right: 8px;">{team_name}'
    return team_name

df_show["team_with_logo_html"] = df_show.apply(create_team_html_with_logo, axis=1)

cols_order = ["original_rank", "player_name", "team_with_logo_html"] + [c for c in table_cols if c not in ["player_name", "team_name"]]
df_show = df_show[cols_order + ["player_url", "_original_index"]]

rename_dict = {k: v for k, v in DISPLAY_COLS.items() if k != "team_name"}
rename_dict["original_rank"] = "#"
rename_dict["team_with_logo_html"] = "Team"
df_show = df_show.rename(columns=rename_dict)

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

gb = GridOptionsBuilder.from_dataframe(df_show)
gb.configure_column("#", width=70, pinned="left", sortable=True, type=["numericColumn"])
gb.configure_column("Player Name", width=180, pinned="left", cellRenderer=player_link_renderer)
gb.configure_column("Team", width=200, cellRenderer=team_logo_renderer)
gb.configure_column("Nationality", width=110)
gb.configure_column("Age", width=80, type=["numericColumn"], sortable=True)
gb.configure_column("Position", width=130)  # Increased width for position profiles
gb.configure_column("Minutes", width=100, type=["numericColumn"], sortable=True)
gb.configure_column("Competition", width=110)
gb.configure_column("Season", width=110)
gb.configure_column("Physical", width=100, type=["numericColumn"], sortable=True)
gb.configure_column("Attack", width=100, type=["numericColumn"], sortable=True)
gb.configure_column("Defense", width=100, type=["numericColumn"], sortable=True)
gb.configure_column("Total", width=100, type=["numericColumn"], sortable=True)

gb.configure_column("player_url", hide=True)
gb.configure_column("_original_index", hide=True)
gb.configure_default_column(sortable=True, filterable=False, resizable=True)
gb.configure_selection(selection_mode='multiple', use_checkbox=True, pre_selected_rows=[])

gridOptions = gb.build()

grid_response = AgGrid(
    df_show,
    gridOptions=gridOptions,
    enable_enterprise_modules=False,
    allow_unsafe_jscode=True,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    height=450,
    fit_columns_on_grid_load=False,
    theme='streamlit'
)

selected_from_grid = []
selected_from_grid_full_data = []
if grid_response and 'selected_rows' in grid_response:
    selected_rows = grid_response['selected_rows']
    if selected_rows is not None and len(selected_rows) > 0:
        if isinstance(selected_rows, pd.DataFrame):
            selected_from_grid = selected_rows['Player Name'].tolist()[:2]
            for _, row_dict in selected_rows.iterrows():
                if len(selected_from_grid_full_data) >= 2:
                    break
                if '_original_index' in row_dict.index:
                    orig_idx = row_dict['_original_index']
                    if orig_idx in df_top.index:
                        selected_from_grid_full_data.append(df_top.loc[orig_idx])
                        continue
                import re
                player_name = row_dict['Player Name']
                team_name = row_dict['Team']
                if isinstance(team_name, str) and '<img' in team_name:
                    match = re.search(r'margin-right: 8px;">(.+?)(?:<|$)', team_name)
                    if match:
                        team_name = match.group(1).strip()
                position = row_dict['Position']
                competition = row_dict['Competition']
                season = row_dict['Season']
                matched_row = df_top[
                    (df_top['player_name'] == player_name) &
                    (df_top['team_name'] == team_name) &
                    (df_top['display_position'] == position) &  # Use display_position for matching
                    (df_top['competition_name'] == competition) &
                    (df_top['season_name'] == season)
                ]
                if not matched_row.empty:
                    selected_from_grid_full_data.append(matched_row.iloc[0])
        elif isinstance(selected_rows, list) and len(selected_rows) > 0:
            if isinstance(selected_rows[0], dict):
                selected_from_grid = [row['Player Name'] for row in selected_rows[:2]]
                for row_dict in selected_rows[:2]:
                    if '_original_index' in row_dict:
                        orig_idx = row_dict['_original_index']
                        if orig_idx in df_top.index:
                            selected_from_grid_full_data.append(df_top.loc[orig_idx])
                            continue
                    import re
                    player_name = row_dict.get('Player Name')
                    team_name = row_dict.get('Team', '')
                    if isinstance(team_name, str) and '<img' in team_name:
                        match = re.search(r'margin-right: 8px;">(.+?)(?:<|$)', team_name)
                        if match:
                            team_name = match.group(1).strip()
                    position = row_dict.get('Position')
                    competition = row_dict.get('Competition')
                    season = row_dict.get('Season')
                    matched_row = df_top[
                        (df_top['player_name'] == player_name) &
                        (df_top['team_name'] == team_name.strip()) &
                        (df_top['display_position'] == position) &  # Use display_position for matching
                        (df_top['competition_name'] == competition) &
                        (df_top['season_name'] == season)
                    ]
                    if not matched_row.empty:
                        selected_from_grid_full_data.append(matched_row.iloc[0])
            else:
                selected_from_grid = selected_rows[:2]

# ========================================
# DEFINE SEARCH POOL
# ========================================
mask_search = (
    df["competition_name"].isin(selected_comp)
    & df["season_name"].isin(selected_season)
    & df["age"].between(age_range[0], age_range[1])
)
df_search_pool = df.loc[mask_search].copy()

st.markdown("---")
comparison_placeholder = st.empty()

# ========================================
# PLAYER SEARCH (Bottom Table)
# ========================================
st.markdown("---")
st.subheader("Player Search")
st.markdown("Search for specific players to compare their performance across different positions and seasons.")

available_players = sorted(df_search_pool["player_name"].unique().tolist())

search_selected_players = st.multiselect(
    "Search and select players",
    options=available_players,
    default=[],
    help="Type to search and select multiple players. Search is independent of position and minimum score filters."
)

selected_from_bottom_table = []
selected_from_bottom_table_full_data = []

if search_selected_players:
    search_df = df_search_pool[df_search_pool["player_name"].isin(search_selected_players)].copy()
    
    # Add display_position for search results
    if 'position_profile' in search_df.columns:
        search_df['display_position'] = search_df.apply(
            lambda row: row['position_profile'] if pd.notna(row.get('position_profile')) and row.get('position_profile') else row['position'],
            axis=1
        )
    else:
        search_df['display_position'] = search_df['position']

    search_cols = ["player_name", "team_name", "display_position", "competition_name", "season_name", "total_minutes",
                   "physical", "attack", "defense", "total"]
    if 'impect_url' in search_df.columns:
        search_cols.append('impect_url')

    search_display = search_df[search_cols].copy()
    
    # Store original index to match back to full data later
    search_display['_search_original_index'] = search_df.index

    for col in ["total_minutes", "physical", "attack", "defense", "total"]:
        if col in search_display.columns:
            if col == "total_minutes":
                search_display[col] = search_display[col].round(0)
            else:
                search_display[col] = search_display[col].round(1)

    search_display = search_display.sort_values(["player_name", "total"], ascending=[True, False])

    def create_search_team_html(row):
        team_name = row['team_name']
        competition = row.get('competition_name')
        logo_b64 = get_team_logo_base64(team_name, competition)
        if logo_b64:
            return f'<img src="{logo_b64}" height="20" style="vertical-align: middle; margin-right: 8px;">{team_name}'
        return team_name

    search_display["team_with_logo_html"] = search_display.apply(create_search_team_html, axis=1)

    def get_search_player_url(row):
        if 'impect_url' in row.index and pd.notna(row.get('impect_url')) and row.get('impect_url'):
            return row['impect_url']
        else:
            return get_team_fbref_google_search(row['team_name'])

    search_display["player_url"] = search_display.apply(get_search_player_url, axis=1)

    display_cols = ["player_name", "team_with_logo_html", "display_position", "competition_name", "season_name",
                    "total_minutes", "physical", "attack", "defense", "total"]
    search_display = search_display[display_cols + ["player_url", "_search_original_index"]]

    search_display = search_display.rename(columns={
        "player_name": "Player Name",
        "team_with_logo_html": "Team",
        "display_position": "Position",
        "competition_name": "Competition",
        "season_name": "Season",
        "total_minutes": "Minutes",
        "physical": "Physical",
        "attack": "Attack",
        "defense": "Defense",
        "total": "Total"
    })

    gb_search = GridOptionsBuilder.from_dataframe(search_display)
    gb_search.configure_column("Player Name", width=180, pinned="left", cellRenderer=player_link_renderer)
    gb_search.configure_column("Team", width=200, cellRenderer=team_logo_renderer)
    gb_search.configure_column("Position", width=130)  # Increased width for position profiles
    gb_search.configure_column("Competition", width=110)
    gb_search.configure_column("Season", width=110)
    gb_search.configure_column("Minutes", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Physical", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Attack", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Defense", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Total", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("player_url", hide=True)
    gb_search.configure_column("_search_original_index", hide=True)
    gb_search.configure_default_column(sortable=True, filterable=False, resizable=True)
    gb_search.configure_selection(selection_mode='multiple', use_checkbox=True, pre_selected_rows=[])

    gridOptions_search = gb_search.build()

    st.markdown(f"**Found {len(search_display)} record(s) for {len(search_selected_players)} player(s)**")
    st.info("💡 **Tip:** Select up to 2 players using the checkboxes to view their comparison charts above.")

    search_grid_response = AgGrid(
        search_display,
        gridOptions=gridOptions_search,
        enable_enterprise_modules=False,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=min(400, 50 + len(search_display) * 35),
        fit_columns_on_grid_load=False,
        theme='streamlit'
    )

    selected_from_bottom_table = []
    selected_from_bottom_table_full_data = []
    if search_grid_response and 'selected_rows' in search_grid_response:
        search_selected_rows = search_grid_response['selected_rows']
        if search_selected_rows is not None and len(search_selected_rows) > 0:
            if isinstance(search_selected_rows, pd.DataFrame):
                selected_from_bottom_table = search_selected_rows['Player Name'].tolist()[:2]
                # Get full data using the original index
                for idx in search_selected_rows['_search_original_index'].tolist()[:2]:
                    if idx in search_df.index:
                        selected_from_bottom_table_full_data.append(search_df.loc[idx])
            elif isinstance(search_selected_rows, list) and len(search_selected_rows) > 0:
                if isinstance(search_selected_rows[0], dict):
                    selected_from_bottom_table = [row['Player Name'] for row in search_selected_rows[:2]]
                    # Get full data using the original index
                    for row in search_selected_rows[:2]:
                        if '_search_original_index' in row:
                            idx = row['_search_original_index']
                            if idx in search_df.index:
                                selected_from_bottom_table_full_data.append(search_df.loc[idx])
                else:
                    selected_from_bottom_table = search_selected_rows[:2]
else:
    st.info("Type player names above to search across all positions and seasons.")
    selected_from_bottom_table = []
    selected_from_bottom_table_full_data = []

# ========================================
# COMPARISON CHARTS
# ========================================
with comparison_placeholder.container():
    st.subheader("Player Comparison Charts")

    if selected_from_bottom_table:
        players_to_compare = selected_from_bottom_table
        players_data_to_compare = selected_from_bottom_table_full_data
        source_message = "from search table below"
        use_exact_data = len(selected_from_bottom_table_full_data) > 0
    elif selected_from_grid and selected_from_grid_full_data:
        players_to_compare = selected_from_grid
        players_data_to_compare = selected_from_grid_full_data
        source_message = "from top table"
        use_exact_data = True
    else:
        players_to_compare = []
        players_data_to_compare = []
        source_message = ""
        use_exact_data = False

    if len(players_to_compare) > 0:
        if len(players_to_compare) > 2:
            st.warning("Please select at most 2 players for comparison.")
            players_to_compare = players_to_compare[:2]
            players_data_to_compare = players_data_to_compare[:2] if use_exact_data else []

        st.info(f"Comparing {len(players_to_compare)} player(s) selected {source_message}")

        st.markdown("""
        <style>
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .stPlotlyChart {
            animation: fadeIn 0.5s ease-in-out;
        }
        </style>
        """, unsafe_allow_html=True)

        cols = st.columns(2)

        for i, player_name in enumerate(players_to_compare):
            if use_exact_data and i < len(players_data_to_compare):
                player_data = players_data_to_compare[i]
            else:
                player_rows = df_search_pool[df_search_pool["player_name"] == player_name]
                if player_rows.empty:
                    player_rows = df[df["player_name"] == player_name]
                if player_rows.empty:
                    st.warning(f"No data found for {player_name}")
                    continue
                player_data = player_rows.iloc[0]

            with cols[i]:
                st.markdown(
                    f"<p style='font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem;'>{player_name}</p>",
                    unsafe_allow_html=True
                )

                team_name = player_data['team_name']
                competition = player_data.get('competition_name')
                team_logo_b64 = get_team_logo_base64(team_name, competition)

                caption_parts = [
                    f"{team_name}",
                    f"{player_data['country']}",
                    f"Age {int(player_data['age'])}",
                    f"{str(player_data.get('display_position') if 'display_position' in player_data.index and pd.notna(player_data.get('display_position')) else (player_data.get('position_profile') if 'position_profile' in player_data.index and pd.notna(player_data.get('position_profile')) else player_data.get('position', '')))}",
                    f"{int(player_data['total_minutes'])} mins"
                ]

                if team_logo_b64:
                    caption_html = f"""
                    <div style="font-size: 1.1rem; margin-bottom: 1rem; line-height: 1.6;">
                        <img src="{team_logo_b64}" height="30" style="vertical-align: middle; margin-right: 8px;">
                        {' · '.join(caption_parts)}
                    </div>
                    """
                    st.markdown(caption_html, unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<div style='font-size: 1.1rem; margin-bottom: 1rem;'>{' · '.join(caption_parts)}</div>",
                        unsafe_allow_html=True
                    )

                fig = create_polarized_bar_chart(
                    player_data,
                    player_data['competition_name'],
                    player_data['season_name']
                )
                # Add unique key to prevent duplicate element ID error
                chart_key = f"comparison_chart_{i}_{player_name.replace(' ', '_')}"
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=chart_key)
    else:
        st.info("Select players from the top table or search table below (using checkboxes) to view comparison charts.")
