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
        if st.session_state["password"] == st.secrets.get("APP_PASSWORD", "fcgroningen2024"):
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
    "ball_win_removed_opponents_otip_p30_percentile": "Balverovering\nverwijderde\ntegenstanders",
    "ball_win_added_teammates_otip_p30_percentile": "Balverovering\ntoegevoegde\nteamgenoten",
    "ground_duels_won_percentage_percentile": "Winstpercentage\ngrondduels",
    "aerial_duels_won_percentage_percentile": "Winstpercentage\nluchtduels",
    "press_total_stop_danger_otip_p30_percentile": "Gestopt gevaar\nmet verdedigende actie"
}

DISPLAY_COLS = {
    "player_name": "Player Name",
    "team_name": "Team",
    "country": "Nationality",
    "age": "Age",
    "position": "Position",
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
    Uses Bram's exact color scheme with gradients based on percentile scores.

    FIX:
    - Overall is ALWAYS computed as mean(physical, attack, defense)
      (not taken from player_data['total'], which can drift or refer to a different value).
    - Bar heights treat missing metrics as 0 only for plotting,
      but category/overall calculations use the precomputed category columns.
    """
    # Bram's exact color scheme
    green = '#3E8C5E'      # Physical (FC Groningen green) - Fysiek
    red = '#E83F2A'        # Attack - Aanvallen
    yellow = '#F2B533'     # Defense - Verdedigen

    def lighten_color(hex_color, amount=0.6):
        """Lighten a hex color by interpolating towards white."""
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(r + (255 - r) * amount)
        g = int(g + (255 - g) * amount)
        b = int(b + (255 - b) * amount)
        return f'#{r:02x}{g:02x}{b:02x}'

    def get_gradient_color(base_color, score, min_score=0, max_score=100):
        """Get color from gradient based on score (0-100 percentile)."""
        # Handle NaN safely
        if score is None or (isinstance(score, float) and np.isnan(score)):
            score = 0.0

        normalized = (score - min_score) / (max_score - min_score) if max_score > min_score else 0
        normalized = max(0, min(1, normalized))

        light_color = lighten_color(base_color, amount=0.6)
        light_rgb = tuple(int(light_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        dark_rgb = tuple(int(base_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))

        r = int(light_rgb[0] + (dark_rgb[0] - light_rgb[0]) * normalized)
        g = int(light_rgb[1] + (dark_rgb[1] - light_rgb[1]) * normalized)
        b = int(light_rgb[2] + (dark_rgb[2] - light_rgb[2]) * normalized)

        return f'rgb({r},{g},{b})'

    def to_float(x, default=np.nan):
        try:
            if pd.isna(x):
                return default
            return float(x)
        except Exception:
            return default

    # Metrics to plot (15 total)
    plot_columns = PHYSICAL_METRICS + ATTACK_METRICS + DEFENSE_METRICS

    # Raw metric percentiles (keep NaN as NaN; only convert to 0 for plotting)
    percentile_values_raw = [to_float(player_data.get(col, np.nan), default=np.nan) for col in plot_columns]
    percentile_values_plot = [0.0 if pd.isna(v) else float(v) for v in percentile_values_raw]

    # Category mapping (1=Physical, 2=Attack, 3=Defense)
    category_mapping = (
        [1] * len(PHYSICAL_METRICS) +
        [2] * len(ATTACK_METRICS) +
        [3] * len(DEFENSE_METRICS)
    )

    category_colors = {1: green, 2: red, 3: yellow}

    # Gradient colors based on plotted values (0 if missing)
    colors = []
    for score, category_id in zip(percentile_values_plot, category_mapping):
        base_color = category_colors[category_id]
        colors.append(get_gradient_color(base_color, score))

    # --- IMPORTANT FIX: category + overall values are taken from the precomputed columns ---
    physical_avg = to_float(player_data.get("physical", np.nan), default=np.nan)
    attack_avg   = to_float(player_data.get("attack", np.nan), default=np.nan)
    defense_avg  = to_float(player_data.get("defense", np.nan), default=np.nan)

    # If for any reason those are missing, fallback to computing from raw metrics (skipping NaNs)
    if pd.isna(physical_avg):
        physical_block = [v for v in percentile_values_raw[:len(PHYSICAL_METRICS)] if not pd.isna(v)]
        physical_avg = float(np.mean(physical_block)) if physical_block else 0.0

    if pd.isna(attack_avg):
        start = len(PHYSICAL_METRICS)
        end = start + len(ATTACK_METRICS)
        attack_block = [v for v in percentile_values_raw[start:end] if not pd.isna(v)]
        attack_avg = float(np.mean(attack_block)) if attack_block else 0.0

    if pd.isna(defense_avg):
        start = len(PHYSICAL_METRICS) + len(ATTACK_METRICS)
        defense_block = [v for v in percentile_values_raw[start:] if not pd.isna(v)]
        defense_avg = float(np.mean(defense_block)) if defense_block else 0.0

    # Overall must be the mean of the 3 displayed category scores
    overall_avg = float((physical_avg + attack_avg + defense_avg) / 3.0)

    # Labels
    metric_labels = [LABELS.get(col, col).replace('\n', '<br>') for col in plot_columns]

    fig = go.Figure()

    fig.add_trace(go.Barpolar(
        r=percentile_values_plot,
        theta=metric_labels,
        marker=dict(
            color=colors,
            line=dict(color='white', width=2)
        ),
        opacity=1.0,
        name='',
        text=[f'{v:.0f}' for v in percentile_values_plot],
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
                f"<span style='font-size:14px'>🟢 Fysiek: {physical_avg:.1f} | "
                f"🔴 Aanvallen: {attack_avg:.1f} | "
                f"🟡 Verdedigen: {defense_avg:.1f}</span><br>"
                f"<span style='font-size:11px; color:#666'>{competition_name} | {season_name}</span>"
            ),
            x=0.5,
            y=0.95,
            xanchor='center',
            yanchor='top',
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

        numeric_cols = ["age", "total_minutes"] + PHYSICAL_METRICS + ATTACK_METRICS + DEFENSE_METRICS
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # Calculate aggregate scores for display
        df['physical'] = df[PHYSICAL_METRICS].mean(axis=1)
        df['attack'] = df[ATTACK_METRICS].mean(axis=1)
        df['defense'] = df[DEFENSE_METRICS].mean(axis=1)

        # Calculate aggregate scores for display (explicit numeric + skipna behavior)
        df['physical'] = df[PHYSICAL_METRICS].mean(axis=1, skipna=True)
        df['attack'] = df[ATTACK_METRICS].mean(axis=1, skipna=True)
        df['defense'] = df[DEFENSE_METRICS].mean(axis=1, skipna=True)
        # Total MUST be mean of the three category scores
        df['total'] = (df['physical'] + df['attack'] + df['defense']) / 3.0


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
    relevant = {
        'physical': PHYSICAL_METRICS,
        'attack': ATTACK_METRICS,
        'defense': DEFENSE_METRICS
    }
    return relevant


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
    df = df.merge(
        df_impect_urls[['player_id', 'iterationid', 'position', 'impect_url']],
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
positions = sorted(df["position"].dropna().unique())

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

selected_pos = st.sidebar.multiselect("Position (optional)", positions, default=positions)

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

mask = (
    df["competition_name"].isin(selected_comp)
    & df["season_name"].isin(selected_season)
    & df["age"].between(age_range[0], age_range[1])
    & df["position"].isin(selected_pos)
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
gb.configure_column("Position", width=90)
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
                    (df_top['position'] == position) &
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
                        (df_top['position'] == position) &
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

if search_selected_players:
    search_df = df_search_pool[df_search_pool["player_name"].isin(search_selected_players)].copy()

    search_cols = ["player_name", "team_name", "position", "competition_name", "season_name", "total_minutes",
                   "physical", "attack", "defense", "total"]
    if 'impect_url' in search_df.columns:
        search_cols.append('impect_url')

    search_display = search_df[search_cols].copy()

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

    display_cols = ["player_name", "team_with_logo_html", "position", "competition_name", "season_name",
                    "total_minutes", "physical", "attack", "defense", "total"]
    search_display = search_display[display_cols + ["player_url"]]

    search_display = search_display.rename(columns={
        "player_name": "Player Name",
        "team_with_logo_html": "Team",
        "position": "Position",
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
    gb_search.configure_column("Position", width=90)
    gb_search.configure_column("Competition", width=110)
    gb_search.configure_column("Season", width=110)
    gb_search.configure_column("Minutes", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Physical", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Attack", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Defense", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Total", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("player_url", hide=True)
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
    if search_grid_response and 'selected_rows' in search_grid_response:
        search_selected_rows = search_grid_response['selected_rows']
        if search_selected_rows is not None and len(search_selected_rows) > 0:
            if isinstance(search_selected_rows, pd.DataFrame):
                selected_from_bottom_table = search_selected_rows['Player Name'].tolist()[:2]
            elif isinstance(search_selected_rows, list) and len(search_selected_rows) > 0:
                if isinstance(search_selected_rows[0], dict):
                    selected_from_bottom_table = [row['Player Name'] for row in search_selected_rows[:2]]
                else:
                    selected_from_bottom_table = search_selected_rows[:2]
else:
    st.info("Type player names above to search across all positions and seasons.")
    selected_from_bottom_table = []

# ========================================
# COMPARISON CHARTS
# ========================================
with comparison_placeholder.container():
    st.subheader("Player Comparison Charts")

    if selected_from_bottom_table:
        players_to_compare = selected_from_bottom_table
        players_data_to_compare = []
        source_message = "from search table below"
        use_exact_data = False
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
                    f"{player_data['position']}",
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
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Select players from the top table or search table below (using checkboxes) to view comparison charts.")
