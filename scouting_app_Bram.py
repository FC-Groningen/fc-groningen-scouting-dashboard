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
        # First run, show input for password
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.write("*Please contact FC Groningen scouting team for access.*")
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="FC Groningen Scouting Dashboard", layout="wide")

# Check password before showing anything else
if not check_password():
    st.stop()

# Supabase Configuration
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

# For local development (comment out when using secrets)
# SUPABASE_URL = "YOUR_SUPABASE_URL"
# SUPABASE_KEY = "YOUR_SUPABASE_KEY"

TEAM_LOGOS_DIR = "team_logos"

# Metric groups from Bram's internal analysis template (Dutch)
# Physical (4 metrics), Attack (6 metrics), Defense (5 metrics)
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

# Dutch labels from Bram's template
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

# FC Groningen brand color
FC_GRONINGEN_GREEN = "#3E8C5E"

# Team name mapping for logo files
# Maps team names from database to expected logo filenames (without .png extension)
TEAM_LOGO_MAPPING = {
    '1. FC Saarbrücken': '3. Liga/1._FC_Saarbrücken',
    '1. FC Schweinfurt 05': '3. Liga/1._FC_Schweinfurt_05',
    '1. FC Slovacko': 'Fortuna Liga/1._FC_Slovacko',
    'AC Ajaccio': 'Ligue 2/AC_Ajaccio',
    'AC Sparta Prag': 'Fortuna Liga/AC_Sparta_Prag',
    'AD Ceuta FC': 'LaLiga2/AD_Ceuta_FC',
    'ADO Den Haag': 'Keuken Kampioen Divisie/ADO_Den_Haag',
    'AIK Solna': 'Allsvenskan/AIK_Solna',
    'AS Nancy-Lorraine': 'Championnat National/AS_Nancy-Lorraine',
    'AS Saint-Étienne': 'Ligue 2/AS_Saint-Étienne',
    'AZ Alkmaar': 'Eredivisie/AZ_Alkmaar',
    'AZ Alkmaar II': 'Keuken Kampioen Divisie/AZ_Alkmaar_II',
    'Aalborg BK': 'Superligaen/Aalborg_BK',
    'Aarhus GF': 'Superligaen/Aarhus_GF',
    'Ajax Amsterdam': 'Eredivisie/Ajax_Amsterdam',
    'Ajax Amsterdam II': 'Keuken Kampioen Divisie/Ajax_Amsterdam_II',
    'Albacete Balompié': 'LaLiga2/Albacete_Balompié',
    'Alemannia Aachen': '3. Liga/Alemannia_Aachen',
    'Almere City FC': 'Eredivisie/Almere_City_FC',
    'Amiens SC': 'Ligue 2/Amiens_SC',
    'Arka Gdynia': 'PKO BP Ekstraklasa/Arka_Gdynia',
    'Arminia Bielefeld': '3. Liga/Arminia_Bielefeld',
    'Aubagne FC': 'Championnat National/Aubagne_FC',
    'BK Häcken': 'Allsvenskan/BK_Häcken',
    'Beerschot V.A.': 'Challenger Pro League/Beerschot_V.A.',
    'Bohemians Prag 1905': 'Fortuna Liga/Bohemians_Prag_1905',
    'Borussia Dortmund II': '3. Liga/Borussia_Dortmund_II',
    'Bruk-Bet Termalica Nieciecza': 'PKO BP Ekstraklasa/Bruk-Bet_Termalica_Nieciecza',
    'Bryne FK': 'Eliteserien/Bryne_FK',
    'Burgos CF': 'LaLiga2/Burgos_CF',
    'CD Castellón': 'LaLiga2/CD_Castellón',
    'CD Eldense': 'LaLiga2/CD_Eldense',
    'CD Leganés': 'LaLiga2/CD_Leganés',
    'CD Mirandés': 'LaLiga2/CD_Mirandés',
    'CD Teneriffa': 'LaLiga2/CD_Teneriffa',
    'Clermont Foot 63': 'Ligue 2/Clermont_Foot_63',
    'Club NXT': 'Challenger Pro League/Club_NXT',
    'Cracovia': 'PKO BP Ekstraklasa/Cracovia',
    'Cultural Leonesa': 'LaLiga2/Cultural_Leonesa',
    'De Graafschap Doetinchem': 'Keuken Kampioen Divisie/De_Graafschap_Doetinchem',
    'Degerfors IF': 'Allsvenskan/Degerfors_IF',
    'Deportivo La Coruna': 'LaLiga2/Deportivo_La_Coruna',
    'Dijon FCO': 'Championnat National/Dijon_FCO',
    'Djurgårdens IF': 'Allsvenskan/Djurgårdens_IF',
    'EA Guingamp': 'Ligue 2/EA_Guingamp',
    'ESTAC Troyes': 'Ligue 2/ESTAC_Troyes',
    'Excelsior Rotterdam': 'Keuken Kampioen Divisie/Excelsior_Rotterdam',
    'FC Andorra': 'LaLiga2/FC_Andorra',
    'FC Annecy': 'Ligue 2/FC_Annecy',
    'FC Banik Ostrau': 'Fortuna Liga/FC_Banik_Ostrau',
    'FC Blau-Weiß Linz': 'Bundesliga/FC_Blau-Weiß_Linz',
    'FC Bourg-Péronnas 01': 'Championnat National/FC_Bourg-Péronnas_01',
    'FC Cartagena': 'LaLiga2/FC_Cartagena',
    'FC Cádiz': 'LaLiga2/FC_Cádiz',
    'FC Córdoba': 'LaLiga2/FC_Córdoba',
    'FC Den Bosch': 'Keuken Kampioen Divisie/FC_Den_Bosch',
    'FC Dordrecht': 'Keuken Kampioen Divisie/FC_Dordrecht',
    'FC Eindhoven': 'Keuken Kampioen Divisie/FC_Eindhoven',
    'FC Elche': 'LaLiga2/FC_Elche',
    'FC Emmen': 'Keuken Kampioen Divisie/FC_Emmen',
    'FC Energie Cottbus': '3. Liga/FC_Energie_Cottbus',
    'FC Erzgebirge Aue': '3. Liga/FC_Erzgebirge_Aue',
    'FC Fredericia': 'Superligaen/FC_Fredericia',
    'FC Granada': 'LaLiga2/FC_Granada',
    'FC Groningen': 'Eredivisie/FC_Groningen',
    'FC Hansa Rostock': '3. Liga/FC_Hansa_Rostock',
    'FC Hradec Kralove': 'Fortuna Liga/FC_Hradec_Kralove',
    'FC Ingolstadt 04': '3. Liga/FC_Ingolstadt_04',
    'FC Kopenhagen': 'Superligaen/FC_Kopenhagen',
    'FC Le Mans': 'Championnat National/FC_Le_Mans',
    'FC Lorient': 'Ligue 2/FC_Lorient',
    'FC Martigues': 'Ligue 2/FC_Martigues',
    'FC Metz': 'Ligue 2/FC_Metz',
    'FC Midtjylland': 'Superligaen/FC_Midtjylland',
    'FC Málaga': 'LaLiga2/FC_Málaga',
    'FC Nordsjaelland': 'Superligaen/FC_Nordsjaelland',
    'FC Rouen 1899': 'Championnat National/FC_Rouen_1899',
    'FC Sochaux-Montbéliard': 'Championnat National/FC_Sochaux-Montbéliard',
    'FC Twente Enschede': 'Eredivisie/FC_Twente_Enschede',
    'FC Utrecht': 'Eredivisie/FC_Utrecht',
    'FC Utrecht II': 'Keuken Kampioen Divisie/FC_Utrecht_II',
    'FC Valenciennes': 'Championnat National/FC_Valenciennes',
    'FC Versailles 78': 'Championnat National/FC_Versailles_78',
    'FC Viktoria Köln': '3. Liga/FC_Viktoria_Köln',
    'FC Viktoria Pilsen': 'Fortuna Liga/FC_Viktoria_Pilsen',
    'FC Villefranche-Beaujolais': 'Championnat National/FC_Villefranche-Beaujolais',
    'FC Volendam': 'Keuken Kampioen Divisie/FC_Volendam',
    'FC Zlin': 'Fortuna Liga/FC_Zlin',
    'FK Austria Wien': 'Bundesliga/FK_Austria_Wien',
    'FK Bodø/Glimt': 'Eliteserien/FK_Bodø_Glimt',
    'FK Dukla Prag': 'Fortuna Liga/FK_Dukla_Prag',
    'FK Haugesund': 'Eliteserien/FK_Haugesund',
    'FK Jablonec': 'Fortuna Liga/FK_Jablonec',
    'FK Mlada Boleslav': 'Fortuna Liga/FK_Mlada_Boleslav',
    'FK Pardubice': 'Fortuna Liga/FK_Pardubice',
    'FK Teplice': 'Fortuna Liga/FK_Teplice',
    'Feyenoord Rotterdam': 'Eredivisie/Feyenoord_Rotterdam',
    'Football Club Fleury 91': 'Championnat National/Football_Club_Fleury_91',
    'Fortuna Sittard': 'Eredivisie/Fortuna_Sittard',
    'Fredrikstad FK': 'Eliteserien/Fredrikstad_FK',
    'GAIS Göteborg': 'Allsvenskan/GAIS_Göteborg',
    'GKS Katowice': 'PKO BP Ekstraklasa/GKS_Katowice',
    'Go Ahead Eagles Deventer': 'Eredivisie/Go_Ahead_Eagles_Deventer',
    'Grazer AK 1902': 'Bundesliga/Grazer_AK_1902',
    'Grenoble Foot 38': 'Ligue 2/Grenoble_Foot_38',
    'Górnik Zabrze': 'PKO BP Ekstraklasa/Górnik_Zabrze',
    'HSC Montpellier': 'Ligue 2/HSC_Montpellier',
    'Halmstads BK': 'Allsvenskan/Halmstads_BK',
    'Hamarkameratene': 'Eliteserien/Hamarkameratene',
    'Hammarby IF': 'Allsvenskan/Hammarby_IF',
    'Hannover 96 II': '3. Liga/Hannover_96_II',
    'Helmond Sport': 'Keuken Kampioen Divisie/Helmond_Sport',
    'Heracles Almelo': 'Eredivisie/Heracles_Almelo',
    'IF Brommapojkarna': 'Allsvenskan/IF_Brommapojkarna',
    'IF Elfsborg': 'Allsvenskan/IF_Elfsborg',
    'IFK Göteborg': 'Allsvenskan/IFK_Göteborg',
    'IFK Norrköping': 'Allsvenskan/IFK_Norrköping',
    'IFK Värnamo': 'Allsvenskan/IFK_Värnamo',
    'IK Sirius': 'Allsvenskan/IK_Sirius',
    'Jagiellonia Bialystok': 'PKO BP Ekstraklasa/Jagiellonia_Bialystok',
    'Jong Genk': 'Challenger Pro League/Jong_Genk',
    'KAS Eupen': 'Challenger Pro League/KAS_Eupen',
    'KFUM-Kameratene Oslo': 'Eliteserien/KFUM-Kameratene_Oslo',
    'KMSK Deinze': 'Challenger Pro League/KMSK_Deinze',
    'KSC Lokeren-Temse': 'Challenger Pro League/KSC_Lokeren-Temse',
    'KSK Lierse Kempenzonen': 'Challenger Pro League/KSK_Lierse_Kempenzonen',
    'KV Kortrijk': 'Challenger Pro League/KV_Kortrijk',
    'Korona Kielce': 'PKO BP Ekstraklasa/Korona_Kielce',
    'Kristiansund BK': 'Eliteserien/Kristiansund_BK',
    'LASK': 'Bundesliga/LASK',
    'LB Châteauroux': 'Championnat National/LB_Châteauroux',
    'Le Puy Foot 43 Auvergne': 'Championnat National/Le_Puy_Foot_43_Auvergne',
    'Lech Posen': 'PKO BP Ekstraklasa/Lech_Posen',
    'Lechia Gdansk': 'PKO BP Ekstraklasa/Lechia_Gdansk',
    'Legia Warschau': 'PKO BP Ekstraklasa/Legia_Warschau',
    'Levante UD': 'LaLiga2/Levante_UD',
    'Lommel SK': 'Challenger Pro League/Lommel_SK',
    'Lyngby BK': 'Superligaen/Lyngby_BK',
    'MFK Karvina': 'Fortuna Liga/MFK_Karvina',
    'MSV Duisburg': '3. Liga/MSV_Duisburg',
    'MVV Maastricht': 'Keuken Kampioen Divisie/MVV_Maastricht',
    'Malmö FF': 'Allsvenskan/Malmö_FF',
    'Mjällby AIF': 'Allsvenskan/Mjällby_AIF',
    'Molde FK': 'Eliteserien/Molde_FK',
    'NAC Breda': 'Eredivisie/NAC_Breda',
    'NEC Nijmegen': 'Eredivisie/NEC_Nijmegen',
    'Nîmes Olympique': 'Championnat National/Nîmes_Olympique',
    'Odense Boldklub': 'Superligaen/Odense_Boldklub',
    'PEC Zwolle': 'Eredivisie/PEC_Zwolle',
    'PSV Eindhoven': 'Eredivisie/PSV_Eindhoven',
    'PSV Eindhoven II': 'Keuken Kampioen Divisie/PSV_Eindhoven_II',
    'Paris 13 Atletico': 'Championnat National/Paris_13_Atletico',
    'Paris FC': 'Ligue 2/Paris_FC',
    'Patro Eisden Maasmechelen': 'Challenger Pro League/Patro_Eisden_Maasmechelen',
    'Pau FC': 'Ligue 2/Pau_FC',
    'Piast Gliwice': 'PKO BP Ekstraklasa/Piast_Gliwice',
    'Pogoń Szczecin': 'PKO BP Ekstraklasa/Pogoń_Szczecin',
    'Puszcza Niepolomice': 'PKO BP Ekstraklasa/Puszcza_Niepolomice',
    'Quevilly Rouen Métropole': 'Championnat National/Quevilly_Rouen_Métropole',
    'RAAL La Louvière': 'Challenger Pro League/RAAL_La_Louvière',
    'RFC Lüttich': 'Challenger Pro League/RFC_Lüttich',
    'RFC Seraing': 'Challenger Pro League/RFC_Seraing',
    'RKC Waalwijk': 'Eredivisie/RKC_Waalwijk',
    'RSCA Futures': 'Challenger Pro League/RSCA_Futures',
    'RWD Molenbeek': 'Challenger Pro League/RWD_Molenbeek',
    'Racing Ferrol': 'LaLiga2/Racing_Ferrol',
    'Racing Santander': 'LaLiga2/Racing_Santander',
    'Radomiak Radom': 'PKO BP Ekstraklasa/Radomiak_Radom',
    'Rakow Czestochowa': 'PKO BP Ekstraklasa/Rakow_Czestochowa',
    'Randers FC': 'Superligaen/Randers_FC',
    'Real Oviedo': 'LaLiga2/Real_Oviedo',
    'Real Sociedad B': 'LaLiga2/Real_Sociedad_B',
    'Real Valladolid': 'LaLiga2/Real_Valladolid',
    'Real Zaragoza': 'LaLiga2/Real_Zaragoza',
    'Red Bull Salzburg': 'Bundesliga/Red_Bull_Salzburg',
    'Red Star FC': 'Ligue 2/Red_Star_FC',
    'Roda JC Kerkrade': 'Keuken Kampioen Divisie/Roda_JC_Kerkrade',
    'Rodez AF': 'Ligue 2/Rodez_AF',
    'Rosenborg BK': 'Eliteserien/Rosenborg_BK',
    'Rot-Weiss Essen': '3. Liga/Rot-Weiss_Essen',
    'Royal Francs Borains': 'Challenger Pro League/Royal_Francs_Borains',
    'SC Bastia': 'Ligue 2/SC_Bastia',
    'SC Cambuur Leeuwarden': 'Keuken Kampioen Divisie/SC_Cambuur_Leeuwarden',
    'SC Heerenveen': 'Eredivisie/SC_Heerenveen',
    'SC Telstar': 'Eredivisie/SC_Telstar',
    'SC Verl': '3. Liga/SC_Verl',
    'SCR Altach': 'Bundesliga/SCR_Altach',
    'SD Eibar': 'LaLiga2/SD_Eibar',
    'SD Huesca': 'LaLiga2/SD_Huesca',
    'SG Dynamo Dresden': '3. Liga/SG_Dynamo_Dresden',
    'SK Austria Klagenfurt': 'Bundesliga/SK_Austria_Klagenfurt',
    'SK Beveren': 'Challenger Pro League/SK_Beveren',
    'SK Brann': 'Eliteserien/SK_Brann',
    'SK Dynamo Ceske Budejovice': 'Fortuna Liga/SK_Dynamo_Ceske_Budejovice',
    'SK Rapid Wien': 'Bundesliga/SK_Rapid_Wien',
    'SK Sigma Olmütz': 'Fortuna Liga/SK_Sigma_Olmütz',
    'SK Slavia Prag': 'Fortuna Liga/SK_Slavia_Prag',
    'SK Sturm Graz': 'Bundesliga/SK_Sturm_Graz',
    'SM Caen': 'Championnat National/SM_Caen',
    'SSV Jahn Regensburg': '3. Liga/SSV_Jahn_Regensburg',
    'SSV Ulm 1846': '3. Liga/SSV_Ulm_1846',
    'SV Ried': 'Bundesliga/SV_Ried',
    'SV Sandhausen': '3. Liga/SV_Sandhausen',
    'SV Waldhof Mannheim': '3. Liga/SV_Waldhof_Mannheim',
    'SV Wehen Wiesbaden': '3. Liga/SV_Wehen_Wiesbaden',
    'SV Zulte Waregem': 'Challenger Pro League/SV_Zulte_Waregem',
    'Sandefjord Fotball': 'Eliteserien/Sandefjord_Fotball',
    'Sarpsborg 08 FF': 'Eliteserien/Sarpsborg_08_FF',
    'Silkeborg IF': 'Superligaen/Silkeborg_IF',
    'SpVgg Unterhaching': '3. Liga/SpVgg_Unterhaching',
    'Sparta Rotterdam': 'Eredivisie/Sparta_Rotterdam',
    'Sporting Gijón': 'LaLiga2/Sporting_Gijón',
    'Stade Briochin': 'Championnat National/Stade_Briochin',
    'Stade Laval': 'Ligue 2/Stade_Laval',
    'Stade Reims': 'Ligue 2/Stade_Reims',
    'Stal Mielec': 'PKO BP Ekstraklasa/Stal_Mielec',
    'Strømsgodset IF': 'Eliteserien/Strømsgodset_IF',
    'SönderjyskE': 'Superligaen/SönderjyskE',
    'TOP Oss': 'Keuken Kampioen Divisie/TOP_Oss',
    'TSG 1899 Hoffenheim II': '3. Liga/TSG_1899_Hoffenheim_II',
    'TSV 1860 München': '3. Liga/TSV_1860_München',
    'TSV Hartberg': 'Bundesliga/TSV_Hartberg',
    'TSV Havelse': '3. Liga/TSV_Havelse',
    'Tromsø IL': 'Eliteserien/Tromsø_IL',
    'UD Almería': 'LaLiga2/UD_Almería',
    'UD Las Palmas': 'LaLiga2/UD_Las_Palmas',
    'US Boulogne': 'Championnat National/US_Boulogne',
    'US Concarneau': 'Championnat National/US_Concarneau',
    'US Orléans': 'Championnat National/US_Orléans',
    'USL Dunkerque': 'Ligue 2/USL_Dunkerque',
    'VVV-Venlo': 'Keuken Kampioen Divisie/VVV-Venlo',
    'Vejle Boldklub': 'Superligaen/Vejle_Boldklub',
    'VfB Stuttgart II': '3. Liga/VfB_Stuttgart_II',
    'VfL Osnabrück': '3. Liga/VfL_Osnabrück',
    'Viborg FF': 'Superligaen/Viborg_FF',
    'Viking FK': 'Eliteserien/Viking_FK',
    'Vitesse Arnheim': 'Keuken Kampioen Divisie/Vitesse_Arnheim',
    'Vålerenga Fotball': 'Eliteserien/Vålerenga_Fotball',
    'WSG Tirol': 'Bundesliga/WSG_Tirol',
    'Widzew Łódź': 'PKO BP Ekstraklasa/Widzew_Łódź',
    'Willem II Tilburg': 'Eredivisie/Willem_II_Tilburg',
    'Wisla Plock': 'PKO BP Ekstraklasa/Wisla_Plock',
    'Wolfsberger AC': 'Bundesliga/Wolfsberger_AC',
    'Zaglebie Lubin': 'PKO BP Ekstraklasa/Zaglebie_Lubin',
    'Östers IF': 'Allsvenskan/Östers_IF',
    'Śląsk Wrocław': 'PKO BP Ekstraklasa/Śląsk_Wrocław',
}


# =========================
# CSS with FC Groningen styling
# =========================
st.markdown(
    f"""
    <style>
      /* Import Proxima Nova font (using system fallback if not available) */
      @import url('https://fonts.cdnfonts.com/css/proxima-nova-2');
      
      /* Apply Proxima Nova globally */
      html, body, [class*="css"], .stApp {{
        font-family: 'Proxima Nova', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
      }}
      
      /* Sidebar background */
      section[data-testid="stSidebar"] {{
        background-color: #F4F6F8;
        overflow-y: auto !important;
      }}
      
      /* Prevent sidebar from being scrollable if content fits */
      section[data-testid="stSidebar"] > div {{
        overflow-y: visible !important;
      }}
      
      /* CRITICAL: Remove ALL top padding from sidebar */
      section[data-testid="stSidebar"] > div:first-child {{
        padding-top: 0 !important;
      }}
      
      /* Remove padding from sidebar's main block container */
      section[data-testid="stSidebar"] .block-container {{
        padding-top: 0.2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 0.5rem !important;
      }}
      
      /* Tighter spacing for sidebar blocks */
      section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div {{
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
      }}

      /* Reduce global vertical padding between blocks */
      div[data-testid="stVerticalBlock"] > div {{
        padding-top: 0.05rem;
        padding-bottom: 0.05rem;
      }}
      
      /* Reduce spacing for sidebar labels and inputs */
      section[data-testid="stSidebar"] label {{
        margin-bottom: 0.2rem !important;
        font-size: 14px !important;
      }}
      
      /* Reduce spacing around multiselect */
      section[data-testid="stSidebar"] div[data-baseweb="select"] {{
        margin-bottom: 0.3rem !important;
      }}
      
      /* Reduce slider spacing */
      section[data-testid="stSidebar"] div[data-testid="stSlider"] {{
        padding-top: 0rem !important;
        padding-bottom: 0.3rem !important;
      }}
      
      /* Reduce markdown spacing in sidebar */
      section[data-testid="stSidebar"] .element-container {{
        margin-bottom: 0.2rem !important;
      }}

      /* Custom sidebar title styling */
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

      /* Force all slider text to black */
      div[data-testid="stSlider"] * {{ color: #111111 !important; }}
      section[data-testid="stSidebar"] div[data-testid="stSlider"] * {{ color: #111111 !important; }}
      div[data-baseweb="slider"] * {{ color: #111111 !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def create_polarized_bar_chart(player_data: pd.Series, competition_name: str, season_name: str) -> go.Figure:
    """
    Create a polarized bar chart (circular bar chart) for a player.
    Shows 15 metrics in 3 categories: Physical (4), Attack (6), Defense (5).
    Uses Bram's exact color scheme with gradients based on percentile scores.
    FIXED: Removed gridlines in the middle of the hole by adjusting tick values.
    """
    # Bram's exact color scheme
    green = '#3E8C5E'      # Physical (FC Groningen green) - Fysiek
    red = '#E83F2A'        # Attack - Aanvallen
    yellow = '#F2B533'     # Defense - Verdedigen
    bg_color = '#E9F4ED'   # Light green background
    
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
        # Normalize score to 0-1
        normalized = (score - min_score) / (max_score - min_score) if max_score > min_score else 0
        normalized = max(0, min(1, normalized))  # Clamp to [0, 1]
        
        # Create light version
        light_color = lighten_color(base_color, amount=0.6)
        
        # Interpolate between light and dark
        light_rgb = tuple(int(light_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        dark_rgb = tuple(int(base_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        
        r = int(light_rgb[0] + (dark_rgb[0] - light_rgb[0]) * normalized)
        g = int(light_rgb[1] + (dark_rgb[1] - light_rgb[1]) * normalized)
        b = int(light_rgb[2] + (dark_rgb[2] - light_rgb[2]) * normalized)
        
        return f'rgb({r},{g},{b})'
    
    # Define the metrics to plot (15 total from Bram's template)
    plot_columns = PHYSICAL_METRICS + ATTACK_METRICS + DEFENSE_METRICS
    
    # Get percentile values
    percentile_values = [player_data[col] if col in player_data.index else 0 for col in plot_columns]
    
    # Create category mapping (1=Physical, 2=Attack, 3=Defense)
    category_mapping = (
        [1] * len(PHYSICAL_METRICS) + 
        [2] * len(ATTACK_METRICS) + 
        [3] * len(DEFENSE_METRICS)
    )
    
    # Map categories to base colors
    category_colors = {
        1: green,   # Fysiek
        2: red,     # Aanvallen
        3: yellow   # Verdedigen
    }
    
    # Create gradient colors for each bar based on its percentile score
    colors = []
    for score, category_id in zip(percentile_values, category_mapping):
        base_color = category_colors[category_id]
        gradient_color = get_gradient_color(base_color, score)
        colors.append(gradient_color)
    
    # Calculate category averages
    physical_avg = np.mean(percentile_values[0:len(PHYSICAL_METRICS)])
    attack_avg = np.mean(percentile_values[len(PHYSICAL_METRICS):len(PHYSICAL_METRICS)+len(ATTACK_METRICS)])
    defense_avg = np.mean(percentile_values[len(PHYSICAL_METRICS)+len(ATTACK_METRICS):])
    
    # Create metric labels using Dutch labels with line breaks
    metric_labels = [LABELS.get(col, col).replace('\n', '<br>') for col in plot_columns]
    
    # Create the figure
    fig = go.Figure()
    
    # Add individual bars for each metric with gradient colors
    fig.add_trace(go.Barpolar(
        r=percentile_values,
        theta=metric_labels,
        marker=dict(
            color=colors,
            line=dict(color='white', width=2)  # White edge color
        ),
        opacity=1.0,
        name='',
        text=[f'{v:.0f}' for v in percentile_values],
        hovertemplate='%{theta}<br>Percentile: %{r:.1f}<extra></extra>'
    ))
    
    # Calculate overall average
    #overall_avg = np.mean(percentile_values)
    # Calculate overall average (should match 'total' column: average of the 3 category averages)
    overall_avg = np.mean([physical_avg, attack_avg, defense_avg])
    
    # Update layout with colored category labels and competition/season info
    # FIXED: Changed tickvals to start at 25 instead of 0 to remove gridlines in the hole
    fig.update_layout(
        polar=dict(
            domain=dict(x=[0.02, 0.98], y=[0.0, 0.88]),  # Larger plot area for better visibility
            radialaxis=dict(
                visible=True,
                range=[-20, 100],  # Set to -20 to create hole in the middle
                showticklabels=False,  # Hide percentile labels
                ticks='',
                showline=False,
                showgrid=True,  # Enable grid lines
                gridcolor='rgba(0, 0, 0, 0.2)',  # Light black/gray grid lines
                gridwidth=1,
                tickvals=[25, 50, 75, 100],  # FIXED: Start at 25 to avoid gridlines in hole
                layer='above traces'  # Force grid lines and tick labels to appear above bars
            ),
            angularaxis=dict(
                tickfont=dict(size=10, family='Proxima Nova', color='#000000'),
                rotation=90,
                direction='clockwise',
                showgrid=False,  # FIXED: Disable radial grid lines from center
                gridcolor='rgba(0, 0, 0, 0.2)',
                gridwidth=1,
                layer='above traces'
            ),
            bgcolor='rgba(255, 255, 255, 1)'  # White background
        ),
        showlegend=False,
        height=500,
        margin=dict(l=80, r=80, t=120, b=80),  # Increased top margin for subtitle
        title=dict(
            text=f"<b>Overall: {overall_avg:.1f}</b><br><span style='font-size:14px'>🟢 Fysiek: {physical_avg:.1f} | 🔴 Aanvallen: {attack_avg:.1f} | 🟡 Verdedigen: {defense_avg:.1f}</span><br><span style='font-size:11px; color:#666'>{competition_name} | {season_name}</span>",
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
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data_from_supabase() -> pd.DataFrame:
    """Load ALL data from Supabase database (handles pagination for >1000 rows)"""
    try:
        # Create Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Get total count first
        count_response = supabase.table('player_percentiles').select("*", count='exact').limit(1).execute()
        total_count = count_response.count
        
        # Fetch all data with pagination
        all_data = []
        page_size = 1000
        
        for offset in range(0, total_count, page_size):
            response = supabase.table('player_percentiles').select("*").range(offset, offset + page_size - 1).execute()
            all_data.extend(response.data)
        
        # Convert to DataFrame
        df = pd.DataFrame(all_data)
        
        # Ensure numeric types for key columns
        numeric_cols = ["age", "total_minutes"] + PHYSICAL_METRICS + ATTACK_METRICS + DEFENSE_METRICS
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        
        # Calculate aggregate scores for display
        df['physical'] = df[PHYSICAL_METRICS].mean(axis=1)
        df['attack'] = df[ATTACK_METRICS].mean(axis=1)
        df['defense'] = df[DEFENSE_METRICS].mean(axis=1)
        df['total'] = df[['physical', 'attack', 'defense']].mean(axis=1)
        
        return df
        
    except Exception as e:
        st.error(f"Error loading data from Supabase: {str(e)}")
        st.info("Please check your Supabase credentials in .streamlit/secrets.toml")
        st.stop()
        return pd.DataFrame()


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_impect_urls_from_supabase() -> pd.DataFrame:
    """Load Impect URLs from player_impect_urls table"""
    try:
        # Create Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Fetch all URLs with pagination
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
        
        # Convert to DataFrame
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
    """
    Returns only the metrics that are relevant (non-zero/non-null) for the player's position.
    Returns a dict with keys: 'physical', 'attack', 'defense', each containing list of relevant metrics.
    Since we're using pre-calculated percentiles, all metrics are always relevant.
    """
    relevant = {
        'physical': PHYSICAL_METRICS,
        'attack': ATTACK_METRICS,
        'defense': DEFENSE_METRICS
    }
    
    return relevant


def build_radar_3_shapes(row: pd.Series, cohort: pd.DataFrame) -> go.Figure:
    """
    3 separate category shapes (Physical/Attack/Defense),
    using pre-calculated percentiles from the CSV.
    """
    fig = go.Figure()
    
    # Get relevant metrics for this position
    relevant_metrics = get_relevant_metrics_for_position(row, cohort)

    def add_group(metrics, name, line_color, fill_rgba):
        if not metrics:
            return

        r_vals, theta = [], []
        for m in metrics:
            # Use pre-calculated percentile values directly from the CSV
            r_vals.append(float(row[m]) if m in row.index and pd.notna(row[m]) else 0)
            theta.append(LABELS.get(m, m).replace('\n', ' '))  # Replace newlines with spaces for radar

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

    # Physical (green)
    add_group(
        relevant_metrics['physical'],
        "Physical",
        "#3E8C5E",
        "rgba(62, 140, 94, 0.25)"
    )

    # Attack (red)
    add_group(
        relevant_metrics['attack'],
        "Attack",
        "#E83F2A",
        "rgba(232, 63, 42, 0.25)"
    )

    # Defense (yellow)
    add_group(
        relevant_metrics['defense'],
        "Defense",
        "#F2B533",
        "rgba(242, 181, 51, 0.25)"
    )

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
    """Convert team logo to base64 for inline display.
    
    Now searches in competition-specific subfolders first, then falls back to root folder.
    Uses flexible matching to find logos even with slight name variations.
    FIXED: Competition folder names match download script (only replace / and \, keep spaces)
    """
    if not team_name:
        return None
        
    try:
        # Use mapping to get the correct logo filename
        logo_filename = TEAM_LOGO_MAPPING.get(team_name, team_name)
        
        # Sanitize FILENAME (for files inside folders)
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
        
        # Sanitize COMPETITION FOLDER NAME (match download script - only replace / and \)
        def sanitize_competition_folder(name):
            return name.replace("/", "_").replace("\\", "_")
        
        safe_filename = sanitize_filename(logo_filename)
        
        # List of paths to try in order
        paths_to_try = []
        
        # Try competition-specific folder first if competition provided
        if competition_name:
            # Use minimal sanitization for folder name (matching download script)
            safe_comp = sanitize_competition_folder(competition_name)
            comp_folder = Path(TEAM_LOGOS_DIR) / safe_comp
            
            # Try exact match
            paths_to_try.append(comp_folder / f"{safe_filename}.png")
            
            # Try original team name if mapping was used
            if logo_filename != team_name:
                paths_to_try.append(comp_folder / f"{sanitize_filename(team_name)}.png")
        
        # Try root folder
        paths_to_try.append(Path(TEAM_LOGOS_DIR) / f"{safe_filename}.png")
        
        # Try original team name in root if mapping was used
        if logo_filename != team_name:
            paths_to_try.append(Path(TEAM_LOGOS_DIR) / f"{sanitize_filename(team_name)}.png")
        
        # If still not found, try searching competition subfolder for fuzzy match
        if competition_name:
            safe_comp = sanitize_competition_folder(competition_name)
            comp_folder = Path(TEAM_LOGOS_DIR) / safe_comp
            if comp_folder.exists():
                # Try finding any file that contains the safe_filename
                for file in comp_folder.glob("*.png"):
                    if safe_filename.lower() in file.stem.lower():
                        paths_to_try.insert(0, file)  # Prioritize this match
        
        # Try each path
        for logo_path in paths_to_try:
            if logo_path.exists():
                img = Image.open(logo_path)
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                return f"data:image/png;base64,{img_str}"
            
    except Exception as e:
        pass
    return None


def get_team_fbref_google_search(team_name: str) -> str:
    """Create Google search URL for team on FBRef."""
    query = f"{team_name} site:fbref.com"
    return f"https://www.google.com/search?q={query.replace(' ', '+')}"


# =========================
# LOAD DATA
# =========================
with st.spinner('Loading player data...'):
    df = load_data_from_supabase()

# Load Impect URLs
with st.spinner('Loading player profiles...'):
    df_impect_urls = load_impect_urls_from_supabase()

# Merge Impect URLs with main data
# Match on player_id, iterationid, and position to get the right URL for each player-competition-position combo
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
    # Add FC Groningen logo at the top with custom styling
    try:
        logo = Image.open("FC_Groningen.png")
        
        # Convert to base64 for embedding
        buffered = BytesIO()
        logo.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        # Direct HTML rendering with precise control - minimal spacing
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
        pass  # If logo not found, continue without it
    
    st.markdown('<div class="sb-title">Filters</div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-rule"></div>', unsafe_allow_html=True)

# Main title
st.title("FC Groningen Scouting Dashboard")

competitions = sorted(df["competition_name"].dropna().unique())
seasons = sorted(df["season_name"].dropna().unique())
positions = sorted(df["position"].dropna().unique())

# Set default to only Eredivisie 2025/2026 season
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

# European players filter
show_european_only = st.sidebar.checkbox("European players only", value=False, 
                                          help="Filter to show only players from European countries")

selected_pos = st.sidebar.multiselect("Position (optional)", positions, default=positions)

# -------- Ranking and filtering controls (moved to main area) --------
st.subheader("Ranking & Filtering")

col1, col2, col3, col4 = st.columns(4)

with col1:
    top_n = st.number_input("Top N Players", min_value=1, max_value=500, value=20, step=1)

with col2:
    min_physical = st.slider(
        "Physical minimum",
        min_value=0,
        max_value=100,
        value=0,
        step=1,
    )

with col3:
    min_attack = st.slider(
        "Attack minimum",
        min_value=0,
        max_value=100,
        value=0,
        step=1,
    )

with col4:
    min_defense = st.slider(
        "Defense minimum",
        min_value=0,
        max_value=100,
        value=0,
        step=1,
    )

# -------- Filter with minimum score thresholds --------
mask = (
    df["competition_name"].isin(selected_comp)
    & df["season_name"].isin(selected_season)
    & df["age"].between(age_range[0], age_range[1])
    & df["position"].isin(selected_pos)
)

# Apply European filter if checkbox is checked
if show_european_only and 'european' in df.columns:
    mask = mask & (df["european"] == True)

df_f = df.loc[mask].copy()
# Sort by total score and get top N FIRST before applying minimum score filters
df_f.sort_values("total", ascending=False, inplace=True, na_position="last")
df_f["original_rank"] = range(1, len(df_f) + 1)
df_top = df_f.head(int(top_n)).copy()

# NOW apply minimum score filters to the top N (keeps original rank locked)
df_top = df_top[
    (df_top["physical"] >= min_physical) &
    (df_top["attack"] >= min_attack) &
    (df_top["defense"] >= min_defense)
]

# Also update df_f to respect minimum score filters for consistency with other features
df_f = df_f[
    (df_f["physical"] >= min_physical) &
    (df_f["attack"] >= min_attack) &
    (df_f["defense"] >= min_defense)
]

if len(df_top) == 0:
    st.info("No players match the current filters.")
    st.stop()

st.subheader("Top Players Table")

# -------- Table with rank, clickable player names, team logos and rounded decimals --------
table_cols = list(DISPLAY_COLS.keys())
# Include impect_url if it exists in df_top
cols_to_copy = table_cols + ["original_rank"]
if 'impect_url' in df_top.columns:
    cols_to_copy.append('impect_url')
df_show = df_top[cols_to_copy].copy()

# Round all numeric columns to 1 decimal place (except minutes to 0)
numeric_display_cols = ["age", "total_minutes", "physical", "attack", "defense", "total"]
for col in numeric_display_cols:
    if col in df_show.columns:
        if col == "total_minutes":
            df_show[col] = df_show[col].round(0)  # Round minutes to 0 decimals
        else:
            df_show[col] = df_show[col].round(1)

# Create player URL column - use Impect URL if available, otherwise fall back to Google search
def get_player_url(row):
    if pd.notna(row.get('impect_url')) and row.get('impect_url'):
        return row['impect_url']
    else:
        # Fallback to Google search of team on FBRef
        return get_team_fbref_google_search(row['team_name'])

df_show["player_url"] = df_show.apply(get_player_url, axis=1)

# Create team column with embedded base64 logos
def create_team_html_with_logo(row):
    team_name = row['team_name']
    competition = row.get('competition_name')
    logo_b64 = get_team_logo_base64(team_name, competition)
    if logo_b64:
        return f'<img src="{logo_b64}" height="20" style="vertical-align: middle; margin-right: 8px;">{team_name}'
    return team_name

df_show["team_with_logo_html"] = df_show.apply(create_team_html_with_logo, axis=1)

# Reorder columns: rank first, then player name, team with logo, then rest
cols_order = ["original_rank", "player_name", "team_with_logo_html"] + [c for c in table_cols if c not in ["player_name", "team_name"]]
df_show = df_show[cols_order + ["player_url"]]

# Rename columns
rename_dict = {k: v for k, v in DISPLAY_COLS.items() if k != "team_name"}
rename_dict["original_rank"] = "#"
rename_dict["team_with_logo_html"] = "Team"
df_show = df_show.rename(columns=rename_dict)

# JavaScript code for rendering clickable player names
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

# JavaScript code for rendering team with embedded logo HTML
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

# Configure AgGrid
gb = GridOptionsBuilder.from_dataframe(df_show)

# Configure rank column (width increased to prevent cutoff)
gb.configure_column("#", width=70, pinned="left", sortable=True, type=["numericColumn"])

# Configure player name with custom renderer
gb.configure_column("Player Name", width=180, pinned="left", cellRenderer=player_link_renderer)

# Configure team with logo renderer
gb.configure_column("Team", width=200, cellRenderer=team_logo_renderer)

# Configure other columns
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

# Hide the helper column
gb.configure_column("player_url", hide=True)

# Set default column properties
gb.configure_default_column(sortable=True, filterable=False, resizable=True)

# Enable row selection (single or multiple rows, max 2 for comparison)
gb.configure_selection(selection_mode='multiple', use_checkbox=True, pre_selected_rows=[])

gridOptions = gb.build()

# Display AgGrid with row selection
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

# Extract selected players from grid - store full row data
selected_from_grid = []
selected_from_grid_full_data = []  # Store full data to match exact rows
if grid_response and 'selected_rows' in grid_response:
    selected_rows = grid_response['selected_rows']
    if selected_rows is not None and len(selected_rows) > 0:
        # Convert to DataFrame if it's not already
        if isinstance(selected_rows, pd.DataFrame):
            selected_from_grid = selected_rows['Player Name'].tolist()[:2]
            # Store the full row data with original column names
            for idx in selected_rows.index[:2]:
                row_data = df_top.loc[df_top.index == idx]
                if not row_data.empty:
                    selected_from_grid_full_data.append(row_data.iloc[0])
        elif isinstance(selected_rows, list) and len(selected_rows) > 0:
            # Handle if it's a list of dicts
            if isinstance(selected_rows[0], dict):
                selected_from_grid = [row['Player Name'] for row in selected_rows[:2]]
                # Try to match back to df_top using player name, team, position, competition, season
                for row_dict in selected_rows[:2]:
                    player_name = row_dict.get('Player Name')
                    team_name = row_dict.get('Team', '').split('>')[-1] if '>' in str(row_dict.get('Team', '')) else row_dict.get('Team', '')
                    position = row_dict.get('Position')
                    competition = row_dict.get('Competition')
                    season = row_dict.get('Season')
                    
                    # Match in df_top
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
                # If it's already a list of player names
                selected_from_grid = selected_rows[:2]

# ========================================
# DEFINE SEARCH POOL (used by both comparison charts and player search)
# ========================================
# Get all unique player names from FULL dataset (independent of sidebar filters)
# Only apply competition, season, and age filters to be consistent
mask_search = (
    df["competition_name"].isin(selected_comp)
    & df["season_name"].isin(selected_season)
    & df["age"].between(age_range[0], age_range[1])
)
df_search_pool = df.loc[mask_search].copy()

# Create a placeholder for comparison charts that will be filled later
st.markdown("---")
comparison_placeholder = st.empty()

# ========================================
# PLAYER SEARCH (Bottom Table)
# ========================================
st.markdown("---")
st.subheader("Player Search")
st.markdown("Search for specific players to compare their performance across different positions and seasons.")

# df_search_pool already defined earlier for use by both comparison charts and player search
available_players = sorted(df_search_pool["player_name"].unique().tolist())

# Multi-select search box
search_selected_players = st.multiselect(
    "Search and select players",
    options=available_players,
    default=[],
    help="Type to search and select multiple players. Search is independent of position and minimum score filters."
)

# Initialize variable to hold selections from bottom table
selected_from_bottom_table = []

if search_selected_players:
    # Filter data for selected players from the independent search pool
    search_df = df_search_pool[df_search_pool["player_name"].isin(search_selected_players)].copy()
    
    # Select and order columns for display (added competition_name and impect_url if available)
    search_cols = ["player_name", "team_name", "position", "competition_name", "season_name", "total_minutes", 
                   "physical", "attack", "defense", "total"]
    if 'impect_url' in search_df.columns:
        search_cols.append('impect_url')
    
    search_display = search_df[search_cols].copy()
    
    # Round numeric columns (minutes to 0 decimals, others to 1)
    for col in ["total_minutes", "physical", "attack", "defense", "total"]:
        if col in search_display.columns:
            if col == "total_minutes":
                search_display[col] = search_display[col].round(0)
            else:
                search_display[col] = search_display[col].round(1)
    
    # Sort by player name, then total score descending
    search_display = search_display.sort_values(["player_name", "total"], ascending=[True, False])
    
    # Create team column with logos
    def create_search_team_html(row):
        team_name = row['team_name']
        competition = row.get('competition_name')
        logo_b64 = get_team_logo_base64(team_name, competition)
        if logo_b64:
            return f'<img src="{logo_b64}" height="20" style="vertical-align: middle; margin-right: 8px;">{team_name}'
        return team_name
    
    search_display["team_with_logo_html"] = search_display.apply(create_search_team_html, axis=1)
    
    # Create player URL column - use Impect URL if available, otherwise fall back to Google search
    def get_search_player_url(row):
        if 'impect_url' in row.index and pd.notna(row.get('impect_url')) and row.get('impect_url'):
            return row['impect_url']
        else:
            # Fallback to Google search of team on FBRef
            return get_team_fbref_google_search(row['team_name'])
    
    search_display["player_url"] = search_display.apply(get_search_player_url, axis=1)
    
    # Reorder for display (added competition_name)
    display_cols = ["player_name", "team_with_logo_html", "position", "competition_name", "season_name", 
                    "total_minutes", "physical", "attack", "defense", "total"]
    search_display = search_display[display_cols + ["player_url"]]
    
    # Rename columns
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
    
    # Configure AgGrid for search results
    gb_search = GridOptionsBuilder.from_dataframe(search_display)
    
    # Player name with clickable link
    gb_search.configure_column("Player Name", width=180, pinned="left", cellRenderer=player_link_renderer)
    
    # Team with logo
    gb_search.configure_column("Team", width=200, cellRenderer=team_logo_renderer)
    
    # Other columns
    gb_search.configure_column("Position", width=90)
    gb_search.configure_column("Competition", width=110)
    gb_search.configure_column("Season", width=110)
    gb_search.configure_column("Minutes", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Physical", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Attack", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Defense", width=100, type=["numericColumn"], sortable=True)
    gb_search.configure_column("Total", width=100, type=["numericColumn"], sortable=True)
    
    # Hide helper column
    gb_search.configure_column("player_url", hide=True)
    
    gb_search.configure_default_column(sortable=True, filterable=False, resizable=True)
    
    # Enable row selection for search table too
    gb_search.configure_selection(selection_mode='multiple', use_checkbox=True, pre_selected_rows=[])
    
    gridOptions_search = gb_search.build()
    
    # Display results with helper text
    st.markdown(f"**Found {len(search_display)} record(s) for {len(search_selected_players)} player(s)**")
    st.info("💡 **Tip:** Select up to 2 players using the checkboxes to view their comparison charts above.")
    
    search_grid_response = AgGrid(
        search_display,
        gridOptions=gridOptions_search,
        enable_enterprise_modules=False,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=min(400, 50 + len(search_display) * 35),  # Dynamic height based on rows
        fit_columns_on_grid_load=False,
        theme='streamlit'
    )
    
    # Extract selections from bottom table (checkbox selections)
    selected_from_bottom_table = []
    if search_grid_response and 'selected_rows' in search_grid_response:
        search_selected_rows = search_grid_response['selected_rows']
        if search_selected_rows is not None and len(search_selected_rows) > 0:
            # Handle DataFrame or list format
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
# NOW POPULATE THE COMPARISON CHARTS (using the placeholder from earlier)
# ========================================
with comparison_placeholder.container():
    st.subheader("Player Comparison Charts")
    
    # Determine which players to show: bottom table selections take priority over top table selections
    if selected_from_bottom_table:
        players_to_compare = selected_from_bottom_table
        players_data_to_compare = []  # Will be populated from search pool
        source_message = "from search table below"
        use_exact_data = False
    elif selected_from_grid and selected_from_grid_full_data:
        players_to_compare = selected_from_grid
        players_data_to_compare = selected_from_grid_full_data  # Use exact data from top table
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
        
        # Add CSS for smooth fade-in animation
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
            # Use exact data if available from top table, otherwise search
            if use_exact_data and i < len(players_data_to_compare):
                player_data = players_data_to_compare[i]
            else:
                # Get player data from search pool (allows finding players from bottom table)
                player_rows = df_search_pool[df_search_pool["player_name"] == player_name]
                
                if player_rows.empty:
                    # Fallback to main df if not in search pool
                    player_rows = df[df["player_name"] == player_name]
                
                if player_rows.empty:
                    st.warning(f"No data found for {player_name}")
                    continue
                
                # Take first row for basic info
                player_data = player_rows.iloc[0]
            
            with cols[i]:
                # Player name with larger font
                st.markdown(f"<p style='font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem;'>{player_name}</p>", unsafe_allow_html=True)
                
                # Create caption with team logo and larger font
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
                
                # Create and display polarized bar chart
                fig = create_polarized_bar_chart(
                    player_data, 
                    player_data['competition_name'],
                    player_data['season_name']
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Select players from the top table or search table below (using checkboxes) to view comparison charts.")
