import os
import sys
import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils import get_ajustes_app

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# CONFIGURACIÓN PÁGINA
# =============================================================================
st.set_page_config(
    page_title="Gestor Formación SaaS",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🎓",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': None}
)

# =============================================================================
# OCULTAR MENÚS STREAMLIT
# =============================================================================
def hide_streamlit_elements():
    st.markdown("""
    <style>
    /* Ocultar elementos nativos Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {visibility: hidden;}
    div[data-testid="stDecoration"] {visibility: hidden;}
    [data-testid="stStatusWidget"] {visibility: hidden;}

    /* Sidebar expandido */
    section[data-testid="stSidebar"][aria-expanded="true"] {
        background: #FFFFFF !important;
        border-right: 1px solid #E5E7EB !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
        transition: all 0.3s ease !important;
    }

    /* Sidebar colapsado: dejamos un ancho mínimo para que la flecha aparezca */
    section[data-testid="stSidebar"][aria-expanded="false"] {
        width: 1.5rem !important;
        min-width: 1.5rem !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        transition: all 0.3s ease !important;
    }

    /* Botón de colapso / expansión */
    button[kind="header"] {
        background: #3B82F6 !important;
        color: white !important;
        border-radius: 0 8px 8px 0 !important;
        padding: 0.5rem 0.75rem !important;
        border: none !important;
        transition: all 0.3s ease !important;
    }
    
    button[kind="header"]:hover {
        background: #2563EB !important;
    }
    
    button[kind="header"] svg {
        color: white !important;
        fill: white !important;
    }

    /* MAIN - expansión fluida cuando cambia el sidebar */
    [data-testid="stAppViewContainer"] {
        transition: margin-left 0.3s ease !important;
    }

    .main .block-container {
        transition: max-width 0.3s ease !important;
    }
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# CSS TAILADMIN LIGHT THEME
# =============================================================================
def load_tailadmin_light_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    :root {
        --primary: #3B82F6;
        --primary-dark: #2563EB;
        --primary-light: #60A5FA;
        --secondary: #80CAEE;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
        --info: #3B82F6;
        
        --white: #FFFFFF;
        --gray-50: #F9FAFB;
        --gray-100: #F3F4F6;
        --gray-200: #E5E7EB;
        --gray-300: #D1D5DB;
        --gray-400: #9CA3AF;
        --gray-500: #6B7280;
        --gray-600: #4B5563;
        --gray-700: #374151;
        --gray-800: #1F2937;
        --gray-900: #111827;
        
        --text-primary: #1F2937;
        --text-secondary: #6B7280;
        --text-tertiary: #9CA3AF;
        
        --border-color: #E5E7EB;
        --bg-page: #F9FAFB;
        --bg-card: #FFFFFF;
        --bg-sidebar: #FFFFFF;
        
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        
        --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--text-primary);
    }

    .stApp { background: var(--bg-page) !important; }
    .main .block-container {
        background: transparent !important;
        padding: 1.5rem !important;
        max-width: 1600px !important;
    }

    /* ============================= */
    /* SIDEBAR                       */
    /* ============================= */
    section[data-testid="stSidebar"][aria-expanded="true"] {
        background: #FFFFFF !important;
        border-right: 1px solid #E5E7EB !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
        transition: all 0.3s ease !important;
    }
    
    section[data-testid="stSidebar"][aria-expanded="false"] {
        width: 1.5rem !important;
        min-width: 1.5rem !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        transition: all 0.3s ease !important;
    }
    
    section[data-testid="stSidebar"] * { color: var(--text-primary) !important; }
    
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4 {
        color: var(--text-secondary) !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em;
        margin: 1.5rem 0 0.75rem 0 !important;
    }
    
    section[data-testid="stSidebar"] hr {
        border: none;
        border-top: 1px solid var(--border-color) !important;
        margin: 1rem 0 !important;
    }
    
    /* ============================= */
    /* BOTONES EN EL SIDEBAR         */
    /* ============================= */
    section[data-testid="stSidebar"] .stButton > button {
        background: #F3F4F6 !important;
        border: 1px solid #E5E7EB !important;
        color: #374151 !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        width: 100% !important;
        text-align: left !important;
        transition: var(--transition) !important;
        margin-bottom: 0.5rem !important;
        box-shadow: none !important;
    }
    
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: #3B82F6 !important;
        color: #FFFFFF !important;
        border-color: #3B82F6 !important;
        transform: translateX(4px);
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2) !important;
    }
    
    section[data-testid="stSidebar"] > div:last-child .stButton > button {
        background: #FEE2E2 !important;
        border-color: #FECACA !important;
        color: #DC2626 !important;
    }
    
    section[data-testid="stSidebar"] > div:last-child .stButton > button:hover {
        background: #EF4444 !important;
        color: #FFFFFF !important;
        border-color: #EF4444 !important;
    }
    
    /* ============================= */
    /* BOTÓN DE COLAPSO/EXPANSIÓN    */
    /* ============================= */
    button[kind="header"] {
        background: #3B82F6 !important;
        color: white !important;
        border-radius: 0 8px 8px 0 !important;
        padding: 0.5rem 0.75rem !important;
        border: none !important;
        transition: all 0.3s ease !important;
        position: relative;
        z-index: 999; /* asegura que siempre quede visible */
    }
    
    button[kind="header"]:hover {
        background: #2563EB !important;
    }
    
    button[kind="header"] svg {
        color: white !important;
        fill: white !important;
    }


    /* TÍTULOS */
    h1 {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
        font-size: 2rem !important;
        margin-bottom: 1.5rem !important;
        line-height: 1.2;
    }
    
    h2 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        font-size: 1.5rem !important;
        margin-bottom: 1rem !important;
    }
    
    h3 {
        color: var(--text-secondary) !important;
        font-weight: 600 !important;
        font-size: 1.25rem !important;
        margin-bottom: 0.75rem !important;
    }

    /* CARDS */
    .stat-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: var(--shadow);
        transition: var(--transition);
        margin-bottom: 1rem;
    }
    
    .stat-card:hover {
        box-shadow: var(--shadow-lg);
        transform: translateY(-2px);
    }

    /* INPUTS - TODOS LOS TIPOS */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input {
        background: #F9FAFB !important;
        border: 2px solid #D1D5DB !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-size: 0.875rem !important;
        color: var(--text-primary) !important;
        transition: var(--transition) !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus,
    .stTimeInput > div > div > input:focus {
        border-color: var(--primary) !important;
        background: #FFFFFF !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
        outline: none !important;
    }

    /* SELECTBOX */
    .stSelectbox > div > div,
    .stSelectbox [data-baseweb="select"] {
        background: #F9FAFB !important;
        border: 2px solid #D1D5DB !important;
        border-radius: 8px !important;
    }
    
    .stSelectbox [data-baseweb="select"]:focus-within {
        border-color: var(--primary) !important;
        background: #FFFFFF !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }
    
    /* MULTISELECT */
    .stMultiSelect > div > div,
    .stMultiSelect [data-baseweb="select"] {
        background: #F9FAFB !important;
        border: 2px solid #D1D5DB !important;
        border-radius: 8px !important;
    }
    
    .stMultiSelect [data-baseweb="select"]:focus-within {
        border-color: var(--primary) !important;
        background: #FFFFFF !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }
    
    .stMultiSelect [data-baseweb="tag"] {
        background: var(--primary) !important;
        color: white !important;
        border-radius: 6px !important;
    }
    
    /* RADIO BUTTONS */
    .stRadio > div {
        background: #F9FAFB !important;
        border: 2px solid #D1D5DB !important;
        border-radius: 8px !important;
        padding: 0.75rem !important;
    }
    
    /* CHECKBOX */
    .stCheckbox {
        background: #F9FAFB !important;
        border: 2px solid #D1D5DB !important;
        border-radius: 8px !important;
        padding: 0.5rem !important;
    }
    
    /* FILE UPLOADER */
    .stFileUploader > div {
        background: #F9FAFB !important;
        border: 2px dashed #D1D5DB !important;
        border-radius: 8px !important;
        padding: 1.5rem !important;
    }
    
    .stFileUploader:hover > div {
        border-color: var(--primary) !important;
        background: #EFF6FF !important;
    }
    
    /* SLIDER */
    .stSlider > div > div {
        background: #F9FAFB !important;
        border: 2px solid #D1D5DB !important;
        border-radius: 8px !important;
        padding: 1rem !important;
    }

    /* BOTONES PRINCIPALES */
    .stButton > button {
        background: #3B82F6 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        transition: var(--transition) !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
    }
    
    .stButton > button:hover {
        background: #2563EB !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3) !important;
    }

    /* ALERTAS */
    .stAlert { border-radius: 8px !important; border-left: 4px solid !important; padding: 1rem !important; }
    .stSuccess { background: #ECFDF5 !important; border-left-color: var(--success) !important; color: #065F46 !important; }
    .stError { background: #FEF2F2 !important; border-left-color: var(--danger) !important; color: #991B1B !important; }
    .stWarning { background: #FFFBEB !important; border-left-color: var(--warning) !important; color: #92400E !important; }
    .stInfo { background: #EFF6FF !important; border-left-color: var(--info) !important; color: #1E40AF !important; }

    /* TABLAS */
    [data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; box-shadow: var(--shadow); }
    [data-testid="stDataFrame"] thead th {
        background: var(--gray-50) !important;
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        padding: 1rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stDataFrame"] tbody tr:hover { background: var(--gray-50) !important; }

    /* TABS */
    [data-testid="stTabs"] {
        background: var(--bg-card);
        border-radius: 8px;
        padding: 0.5rem;
        border: 1px solid var(--border-color);
    }
    [data-testid="stTabs"] button {
        background: transparent !important;
        border-radius: 6px !important;
        padding: 0.75rem 1.5rem !important;
        transition: var(--transition) !important;
    }
    [data-testid="stTabs"] button:hover {
        background: var(--gray-50) !important;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        background: var(--primary) !important;
        color: var(--white) !important;
        font-weight: 600 !important;
    }

    /* LOGIN FORM */
    form[data-testid="form"] { max-width: 400px; margin: 0 auto; }
    form[data-testid="form"] .stTextInput > div > div > input {
        background: var(--white) !important;
        border: 1.5px solid var(--border-color) !important;
    }
    form[data-testid="form"] .stButton > button {
        width: 100%;
        padding: 1rem !important;
        font-size: 1rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# COMPONENTES TAILADMIN
# =============================================================================
class TailAdminComponents:
    @staticmethod
    def stat_card(title: str, value: str, icon: str = "📊", change: str = None, 
                  change_type: str = "positive", color: str = "primary"):
        color_map = {
            "primary": {"bg": "#EFF6FF", "icon_bg": "#DBEAFE", "icon_color": "#1E40AF"},
            "success": {"bg": "#ECFDF5", "icon_bg": "#D1FAE5", "icon_color": "#059669"},
            "warning": {"bg": "#FFFBEB", "icon_bg": "#FEF3C7", "icon_color": "#D97706"},
            "danger": {"bg": "#FEF2F2", "icon_bg": "#FEE2E2", "icon_color": "#DC2626"}
        }
        colors = color_map.get(color, color_map["primary"])
        
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(f"""
            <div style="background: {colors['icon_bg']}; color: {colors['icon_color']};
                width: 56px; height: 56px; border-radius: 12px; display: flex;
                align-items: center; justify-content: center; font-size: 1.75rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);">{icon}</div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="padding-top: 0.25rem;">
                <div style="font-size: 2rem; font-weight: 700; color: #1F2937; margin-bottom: 0.25rem;">{value}</div>
                <div style="font-size: 0.875rem; color: #6B7280; font-weight: 500;">{title}</div>
            </div>
            """, unsafe_allow_html=True)
        
        if change:
            arrow = "↑" if change_type == "positive" else "↓"
            bg = "#DCFCE7" if change_type == "positive" else "#FEE2E2"
            color_text = "#059669" if change_type == "positive" else "#DC2626"
            st.markdown(f"""
            <div style="display: inline-flex; align-items: center; gap: 0.25rem; background: {bg};
                color: {color_text}; padding: 0.25rem 0.75rem; border-radius: 6px;
                font-size: 0.75rem; font-weight: 600; margin-top: 0.5rem;">
                <span>{arrow}</span><span>{change}</span>
            </div>
            """, unsafe_allow_html=True)
    
    @staticmethod
    def breadcrumb(items):
        breadcrumb_html = []
        for i, item in enumerate(items):
            if i == len(items) - 1:
                breadcrumb_html.append(f'<span style="color: #3B82F6; font-weight: 600;">{item}</span>')
            else:
                breadcrumb_html.append(f'<span style="color: #6B7280;">{item}</span>')
                breadcrumb_html.append('<span style="color: #9CA3AF;"> / </span>')
        
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 1rem;
            background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px;
            font-size: 0.875rem; margin-bottom: 1.5rem;">
            {''.join(breadcrumb_html)}
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def welcome_header(user_name: str, company: str = "FUNDAE", subtitle: str = None):
        if subtitle is None:
            meses = {
                1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
                5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
                9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
            }
            dias = {
                0: 'lunes', 1: 'martes', 2: 'miércoles', 3: 'jueves',
                4: 'viernes', 5: 'sábado', 6: 'domingo'
            }
            now = datetime.now()
            dia_semana = dias[now.weekday()]
            mes = meses[now.month]
            subtitle = f"{dia_semana.capitalize()}, {now.day} de {mes} {now.year}"
        
        st.markdown(f"""
        <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px;
            padding: 2rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="display: flex; align-items: center; gap: 1.5rem;">
                <div style="width: 72px; height: 72px; border-radius: 12px;
                    background: linear-gradient(135deg, #3B82F6 0%, #80CAEE 100%);
                    display: flex; align-items: center; justify-content: center;
                    color: white; font-size: 2rem; font-weight: 700;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    {user_name[0].upper() if user_name else "U"}
                </div>
                <div>
                    <h1 style="margin: 0 0 0.5rem 0 !important; font-size: 1.75rem !important;">
                        ¡Bienvenido, {user_name}!
                    </h1>
                    <p style="margin: 0; color: #6B7280; font-size: 0.875rem;">
                        {company} • {subtitle}
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# =============================================================================
# CONFIGURACIÓN SUPABASE
# =============================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("⚠️ Error: Variables de Supabase no configuradas")
    st.stop()

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else None

# =============================================================================
# ESTADO INICIAL
# =============================================================================
for key, default in {
    "page": "home", "rol": None, "role": None, "user": {},
    "auth_session": None, "authenticated": False
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================
@st.cache_data(ttl=300)
def get_metricas_admin():
    try:
        if not supabase_admin:
            return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}
        total_empresas = supabase_admin.table("empresas").select("id", count="exact").execute().count or 0
        total_usuarios = supabase_admin.table("usuarios").select("id", count="exact").execute().count or 0
        total_cursos = supabase_admin.table("acciones_formativas").select("id", count="exact").execute().count or 0
        total_grupos = supabase_admin.table("grupos").select("id", count="exact").execute().count or 0
        return {"empresas": total_empresas, "usuarios": total_usuarios, "cursos": total_cursos, "grupos": total_grupos}
    except Exception as e:
        print(f"Error métricas admin: {e}")
        return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}

@st.cache_data(ttl=300)
def get_metricas_gestor(empresa_id):
    try:
        if not supabase_admin or not empresa_id:
            return {"grupos": 0, "participantes": 0, "documentos": 0}
        grupos = supabase_admin.table("grupos").select("id", count="exact").eq("empresa_id", empresa_id).execute().count or 0
        participantes = supabase_admin.table("participantes").select("id", count="exact").eq("empresa_id", empresa_id).execute().count or 0
        documentos = supabase_admin.table("documentos").select("id", count="exact").eq("empresa_id", empresa_id).execute().count or 0
        return {"grupos": grupos, "participantes": participantes, "documentos": documentos}
    except Exception as e:
        print(f"Error métricas gestor: {e}")
        return {"grupos": 0, "participantes": 0, "documentos": 0}

def set_user_role_from_db(email: str):
    try:
        clean_email = email.strip().lower()
        res = supabase_public.table("usuarios").select("*").eq("email", clean_email).limit(1).execute()
        if res.data:
            row = res.data[0]
            rol = row.get("rol") or "alumno"
            st.session_state.rol = rol
            st.session_state.role = rol
            st.session_state.user = {
                "id": row.get("id"), "auth_id": row.get("auth_id"),
                "email": row.get("email"), "nombre": row.get("nombre"),
                "empresa_id": row.get("empresa_id")
            }
        else:
            st.session_state.rol = "alumno"
            st.session_state.role = "alumno"
            st.session_state.user = {"email": clean_email, "empresa_id": None}
    except Exception as e:
        print(f"Error obteniendo rol: {e}")
        st.session_state.rol = "alumno"
        st.session_state.role = "alumno"

def do_logout():
    try:
        supabase_public.auth.sign_out()
    except:
        pass
    st.cache_data.clear()
    st.session_state.clear()
    st.session_state.authenticated = False
    st.session_state.rol = None
    st.session_state.role = None
    st.session_state.user = {}
    st.session_state.page = "home"
    st.rerun()

def is_module_active(empresa, empresa_crm, key, hoy, role):
    """Verifica si un módulo está activo según fechas"""
    if role == "alumno":
        return False
    
    if key == "formacion":
        if not empresa.get("formacion_activo"):
            return False
        inicio = empresa.get("formacion_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True
    
    if key == "iso":
        if not empresa.get("iso_activo"):
            return False
        inicio = empresa.get("iso_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True
    
    if key == "rgpd":
        if not empresa.get("rgpd_activo"):
            return False
        inicio = empresa.get("rgpd_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True
    
    if key == "crm":
        if not empresa_crm.get("crm_activo"):
            return False
        inicio = empresa_crm.get("crm_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True
    
    if key == "docu_avanzada":
        if not empresa.get("docu_avanzada_activo"):
            return False
        inicio = empresa.get("docu_avanzada_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True
    
    return False

# =============================================================================
# LOGIN
# =============================================================================
def login_view_light():
    logo = "https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/datafor-logo.png"
    st.markdown("""
    <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); z-index: -1;"></div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        st.markdown('<div style="height: 2vh;"></div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 2rem;">
            <img src="{logo}" style="width: 150px; background: white; padding: 15px;
                border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.2);" alt="DataFor">
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h3 style='text-align: center; color: white; margin-bottom: 1.5rem;'>🔐 Iniciar Sesión</h3>", unsafe_allow_html=True)
        
        with st.form("form_login"):
            email = st.text_input("Email", placeholder="usuario@empresa.com")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("🚀 Iniciar Sesión", use_container_width=True)
        
        if submitted:
            if not email or not password:
                st.error("⚠️ Completa todos los campos")
            else:
                try:
                    auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
                    if auth and auth.user:
                        st.session_state.auth_session = auth
                        st.session_state.authenticated = True
                        set_user_role_from_db(auth.user.email)
                        st.rerun()
                    else:
                        st.error("❌ Credenciales incorrectas")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        
        st.markdown("""
        <div style="margin-top: 3rem; padding: 1.5rem; text-align: center;
            background: rgba(255,255,255,0.1); border-radius: 12px; backdrop-filter: blur(10px);">
            <p style="color: white; font-size: 0.875rem; margin: 0; font-weight: 500;">
                © 2025 DataFor Solutions
            </p>
            <p style="color: rgba(255,255,255,0.8); font-size: 0.75rem; margin: 0.25rem 0 0;">
                v2.3.0 - Streamlit 1.50
            </p>
        </div>
        """, unsafe_allow_html=True)

# =============================================================================
# DASHBOARDS
# =============================================================================
def mostrar_dashboard_admin(ajustes, metricas):
    components = TailAdminComponents()
    user_name = st.session_state.user.get("nombre", "Administrador")
    components.welcome_header(user_name, "Sistema FUNDAE")
    components.breadcrumb(["Dashboard", "Panel de Administración"])
    st.markdown("## 📊 Panel de Control")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        components.stat_card("Total Empresas", str(metricas['empresas']), "🏢", "+12%", "positive", "primary")
    with col2:
        components.stat_card("Usuarios Activos", str(metricas['usuarios']), "👥", "+8%", "positive", "success")
    with col3:
        components.stat_card("Cursos Disponibles", str(metricas['cursos']), "📚", "+5%", "positive", "warning")
    with col4:
        components.stat_card("Grupos Activos", str(metricas['grupos']), "👨‍🎓", color="danger")
    
    st.markdown("---")
    st.markdown("### 📈 Análisis del Sistema")
    
    col1, col2 = st.columns(2)
    with col1:
        try:
            usuarios_res = supabase_admin.table("usuarios").select("rol").execute()
            if usuarios_res.data:
                df_roles = pd.DataFrame(usuarios_res.data)
                roles_count = df_roles['rol'].value_counts()
                fig_roles = px.pie(values=roles_count.values, names=roles_count.index,
                    title="Distribución de Usuarios por Rol",
                    color_discrete_sequence=['#3B82F6', '#10B981', '#F59E0B', '#EF4444'])
                fig_roles.update_layout(height=350)
                st.plotly_chart(fig_roles, use_container_width=True)
        except Exception:
            st.info("📊 Gráfico de roles en desarrollo")
    
    with col2:
        try:
            grupos_res = supabase_admin.table("grupos").select("estado").execute()
            if grupos_res.data:
                df_grupos = pd.DataFrame(grupos_res.data)
                estados_count = df_grupos['estado'].value_counts()
                fig_grupos = go.Figure(data=[go.Bar(x=estados_count.index, y=estados_count.values,
                    marker_color=['#3B82F6', '#10B981', '#F59E0B'])])
                fig_grupos.update_layout(title="Estado de los Grupos Formativos",
                    xaxis_title="Estado", yaxis_title="Cantidad", height=350)
                st.plotly_chart(fig_grupos, use_container_width=True)
        except Exception:
            st.info("📊 Gráfico de grupos en desarrollo")

def mostrar_dashboard_gestor(ajustes, metricas):
    components = TailAdminComponents()
    user_name = st.session_state.user.get("nombre", "Gestor")
    components.welcome_header(user_name, "Gestión de Formación")
    components.breadcrumb(["Dashboard", "Panel del Gestor"])
    st.markdown("## 🎓 Panel de Gestión")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        components.stat_card("Mis Grupos", str(metricas.get('grupos', 0)), "👨‍🎓", color="primary")
    with col2:
        components.stat_card("Participantes", str(metricas.get('participantes', 0)), "🧑‍🎓", color="success")
    with col3:
        components.stat_card("Documentos", str(metricas.get('documentos', 0)), "📂", color="warning")

def mostrar_dashboard_alumno(ajustes):
    components = TailAdminComponents()
    user_name = st.session_state.user.get("nombre", "Alumno")
    components.welcome_header(user_name, "Área del Estudiante")
    components.breadcrumb(["Dashboard", "Área del Alumno"])
    st.markdown("## 📘 Mi Área de Formación")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px;
            padding: 2.5rem; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="font-size: 3.5rem; margin-bottom: 1rem;">📘</div>
            <h3 style="color: #1F2937; margin: 0 0 0.5rem 0;">Mis Grupos</h3>
            <p style="color: #6B7280; margin: 0 0 1.5rem 0;">Consulta tus grupos formativos activos</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Ver Mis Grupos", key="btn_grupos", use_container_width=True):
            st.session_state.page = "area_alumno"
            st.rerun()
    
    with col2:
        st.markdown("""
        <div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px;
            padding: 2.5rem; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="font-size: 3.5rem; margin-bottom: 1rem;">🎓</div>
            <h3 style="color: #1F2937; margin: 0 0 0.5rem 0;">Mis Certificados</h3>
            <p style="color: #6B7280; margin: 0 0 1.5rem 0;">Descarga tus diplomas acreditativos</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Ver Certificados", key="btn_cert", use_container_width=True):
            st.info("Funcionalidad en desarrollo")

def mostrar_dashboard_comercial(ajustes):
    components = TailAdminComponents()
    user_name = st.session_state.user.get("nombre", "Comercial")
    components.welcome_header(user_name, "Área Comercial CRM")
    components.breadcrumb(["Dashboard", "Área Comercial"])
    st.markdown("## 💼 Panel CRM")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        components.stat_card("Clientes", "45", "👥", color="primary")
    with col2:
        components.stat_card("Oportunidades", "12", "💡", color="success")
    with col3:
        components.stat_card("Tareas", "8", "📋", color="warning")

# =============================================================================
# SIDEBAR COMPLETO
# =============================================================================
def render_sidebar_light():
    rol = st.session_state.get("rol")
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")
    empresa_id = st.session_state.user.get("empresa_id")
    logo = "https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/datafor-logo.png"

    st.sidebar.markdown(f"""
    <div style="padding: 1.5rem; border-bottom: 1px solid #E5E7EB; text-align: center;
        background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);">
        <div style="width: 60px; height: 60px; margin: 0 auto 1rem; border-radius: 12px;
            overflow: hidden; background: white; padding: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <img src="{logo}" style="width: 100%; height: 100%; object-fit: contain;" alt="DataFor">
        </div>
        <p style="margin: 0; font-weight: 600; color: #1F2937; font-size: 0.9rem;">{nombre_usuario}</p>
        <p style="margin: 0.25rem 0 0; font-size: 0.75rem; color: #6B7280; text-transform: uppercase; letter-spacing: 0.05em;">
            {rol.title() if rol else 'Usuario'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    empresa = {}
    empresa_crm = {}
    hoy = datetime.today().date()
    
    if empresa_id:
        try:
            empresa_res = supabase_admin.table("empresas").select(
                "formacion_activo", "formacion_inicio", "formacion_fin",
                "iso_activo", "iso_inicio", "iso_fin",
                "rgpd_activo", "rgpd_inicio", "rgpd_fin",
                "docu_avanzada_activo", "docu_avanzada_inicio", "docu_avanzada_fin"
            ).eq("id", empresa_id).execute()
            empresa = empresa_res.data[0] if empresa_res.data else {}
            
            crm_res = supabase_admin.table("crm_empresas").select(
                "crm_activo", "crm_inicio", "crm_fin"
            ).eq("empresa_id", empresa_id).execute()
            empresa_crm = crm_res.data[0] if crm_res.data else {}
        except Exception as e:
            print(f"Error módulos: {e}")

    if rol == "admin":
        st.sidebar.markdown("#### ⚙️ Administración SaaS")
        for label, page in [("📊 Panel Admin", "panel_admin"), ("👥 Usuarios", "usuarios_empresas"),
                           ("🏢 Empresas", "empresas"), ("⚙️ Ajustes", "ajustes_app")]:
            if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 🎓 Módulo Formación")
        for label, page in [("📚 Acciones Formativas", "acciones_formativas"), ("👨‍🎓 Grupos", "grupos"),
                           ("🧑‍🎓 Participantes", "participantes"), ("👩‍🏫 Tutores", "tutores"),
                           ("🏫 Aulas", "aulas"), ("📅 Gestión Clases", "gestion_clases"),
                           ("📂 Documentos", "documentos"), ("📁 Proyectos", "proyectos")]:
            if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 🏅 Módulo ISO 9001")
        for label, page in [("📊 Dashboard Calidad", "dashboard_calidad"), ("❌ No Conformidades", "no_conformidades"),
                           ("🔧 Acciones Correctivas", "acciones_correctivas"), ("📋 Auditorías", "auditorias"),
                           ("📈 Indicadores", "indicadores"), ("🎯 Objetivos", "objetivos_calidad"),
                           ("📄 Informe Auditoría", "informe_auditoria")]:
            if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 🔒 Módulo RGPD")
        for label, page in [("🛡️ Panel RGPD", "rgpd_panel"), ("📋 Tareas", "rgpd_planner"),
                           ("🔍 Diagnóstico", "rgpd_inicio"), ("📝 Tratamientos", "rgpd_tratamientos"),
                           ("✅ Consentimientos", "rgpd_consentimientos"), ("👔 Encargados", "rgpd_encargados"),
                           ("⚖️ Derechos", "rgpd_derechos"), ("🔬 Evaluación Impacto", "rgpd_evaluacion"),
                           ("🔐 Medidas Seguridad", "rgpd_medidas"), ("⚠️ Incidencias", "rgpd_incidencias")]:
            if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 💼 Módulo CRM")
        for label, page in [("📊 Panel CRM", "crm_panel"), ("👥 Clientes", "crm_clientes"),
                           ("💡 Oportunidades", "crm_oportunidades"), ("📋 Tareas", "crm_tareas"),
                           ("📞 Comunicaciones", "crm_comunicaciones"), ("📈 Estadísticas", "crm_estadisticas")]:
            if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📚 Doc. Avanzada")
        if st.sidebar.button("📖 Gestión Documental", use_container_width=True, key="nav_documentacion_avanzada"):
            st.session_state.page = "documentacion_avanzada"
            st.rerun()
        
    elif rol == "gestor":
        if is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
            st.sidebar.markdown("#### 🎓 Gestión Formación")
            for label, page in [("📊 Dashboard", "panel_gestor"), ("🏢 Empresas", "empresas"),
                               ("📚 Acciones Formativas", "acciones_formativas"), ("👨‍🎓 Grupos", "grupos"),
                               ("🧑‍🎓 Participantes", "participantes"), ("👩‍🏫 Tutores", "tutores"),
                               ("🏫 Aulas", "aulas"), ("📅 Gestión Clases", "gestion_clases"),
                               ("📂 Documentos", "documentos"), ("📁 Proyectos", "proyectos")]:
                if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
                    st.session_state.page = page
                    st.rerun()
        
        if is_module_active(empresa, empresa_crm, "iso", hoy, rol):
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 🏅 ISO 9001")
            for label, page in [("📊 Dashboard", "dashboard_calidad"), ("❌ No Conformidades", "no_conformidades"),
                               ("🔧 Correctivas", "acciones_correctivas"), ("📋 Auditorías", "auditorias"),
                               ("📈 Indicadores", "indicadores"), ("🎯 Objetivos", "objetivos_calidad")]:
                if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
                    st.session_state.page = page
                    st.rerun()
        
        if is_module_active(empresa, empresa_crm, "rgpd", hoy, rol):
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 🔒 RGPD")
            for label, page in [("🛡️ Panel", "rgpd_panel"), ("📋 Tareas", "rgpd_planner"),
                               ("📝 Tratamientos", "rgpd_tratamientos"), ("✅ Consentimientos", "rgpd_consentimientos")]:
                if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
                    st.session_state.page = page
                    st.rerun()
        
        if is_module_active(empresa, empresa_crm, "docu_avanzada", hoy, rol):
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📚 Doc. Avanzada")
            if st.sidebar.button("📖 Gestión", use_container_width=True, key="nav_documentacion_avanzada"):
                st.session_state.page = "documentacion_avanzada"
                st.rerun()
        
    elif rol == "comercial":
        if is_module_active(empresa, empresa_crm, "crm", hoy, rol):
            st.sidebar.markdown("#### 💼 CRM")
            for label, page in [("📊 Panel", "crm_panel"), ("👥 Clientes", "crm_clientes"),
                               ("💡 Oportunidades", "crm_oportunidades"), ("📋 Tareas", "crm_tareas"),
                               ("📞 Comunicaciones", "crm_comunicaciones"), ("📈 Stats", "crm_estadisticas")]:
                if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
                    st.session_state.page = page
                    st.rerun()
        else:
            st.sidebar.warning("Módulo CRM no activo")
        
    elif rol == "alumno":
        st.sidebar.markdown("#### 🎓 Mi Área")
        if st.sidebar.button("📘 Mis Grupos", use_container_width=True, key="nav_area_alumno"):
            st.session_state.page = "area_alumno"
            st.rerun()
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True, key="logout"):
        do_logout()
    st.sidebar.markdown("---")
    st.sidebar.markdown("**DataFor** Gestor Formación")
    st.sidebar.markdown("*v2.3.0 - Streamlit 1.50*")

# =============================================================================
# NAVEGACIÓN
# =============================================================================
def render_page():
    page = st.session_state.get("page", "home")
    if page and page != "home":
        with st.spinner(f"Cargando {page.replace('_', ' ').title()}..."):
            try:
                page_map = {
                    "panel_admin": "panel_admin", "usuarios_empresas": "usuarios_empresas",
                    "empresas": "empresas", "ajustes_app": "ajustes_app", "panel_gestor": "panel_gestor",
                    "acciones_formativas": "acciones_formativas", "grupos": "grupos",
                    "participantes": "participantes", "tutores": "tutores", "aulas": "aulas",
                    "gestion_clases": "gestion_clases", "proyectos": "proyectos", "documentos": "documentos",
                    "area_alumno": "area_alumno", "no_conformidades": "no_conformidades",
                    "acciones_correctivas": "acciones_correctivas", "auditorias": "auditorias",
                    "indicadores": "indicadores", "dashboard_calidad": "dashboard_calidad",
                    "objetivos_calidad": "objetivos_calidad", "informe_auditoria": "informe_auditoria",
                    "rgpd_panel": "rgpd_panel", "rgpd_planner": "rgpd_planner", "rgpd_inicio": "rgpd_inicio",
                    "rgpd_tratamientos": "rgpd_tratamientos", "rgpd_consentimientos": "rgpd_consentimientos",
                    "rgpd_encargados": "rgpd_encargados", "rgpd_derechos": "rgpd_derechos",
                    "rgpd_evaluacion": "rgpd_evaluacion", "rgpd_medidas": "rgpd_medidas",
                    "rgpd_incidencias": "rgpd_incidencias", "crm_panel": "crm_panel",
                    "crm_clientes": "crm_clientes", "crm_oportunidades": "crm_oportunidades",
                    "crm_tareas": "crm_tareas", "crm_comunicaciones": "crm_comunicaciones",
                    "crm_estadisticas": "crm_estadisticas", "documentacion_avanzada": "documentacion_avanzada"
                }
                if page in page_map:
                    view_module = __import__(f"views.{page_map[page]}", fromlist=["render"])
                    view_module.render(supabase_admin, st.session_state)
                else:
                    st.error(f"❌ Página '{page}' no encontrada")
                    if st.button("🏠 Ir al Dashboard"):
                        st.session_state.page = "home"
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Error al cargar página: {e}")
                st.exception(e)
                if st.button("🔄 Reintentar"):
                    st.rerun()

# =============================================================================
# FUNCIONES HEADER Y FOOTER
# =============================================================================
def render_header():
    pass

def render_footer():
    pass

# =============================================================================
# MAIN
# =============================================================================
def main():
    hide_streamlit_elements()
    load_tailadmin_light_css()
    
    usuario_autenticado = st.session_state.get("authenticated", False)
    
    if not usuario_autenticado:
        login_view_light()
    else:
        try:
            render_header()
            render_footer()
            st.set_option('client.showSidebarNavigation', True)
            render_sidebar_light()
            
            page = st.session_state.get("page", "home")
            
            if page and page != "home":
                render_page()
            else:
                rol = st.session_state.get("rol")
                ajustes = get_ajustes_app(
                    supabase_admin if supabase_admin else supabase_public,
                    campos=[
                        "bienvenida_admin", "tarjeta_admin_usuarios", "tarjeta_admin_empresas", "tarjeta_admin_ajustes",
                        "bienvenida_gestor", "tarjeta_gestor_grupos", "tarjeta_gestor_documentos", "tarjeta_gestor_docu_avanzada",
                        "bienvenida_alumno", "tarjeta_alumno_grupos", "tarjeta_alumno_diplomas", "tarjeta_alumno_seguimiento",
                        "bienvenida_comercial", "tarjeta_comercial_clientes", "tarjeta_comercial_oportunidades", "tarjeta_comercial_tareas"
                    ]
                )
                
                if rol == "admin":
                    metricas = get_metricas_admin()
                    mostrar_dashboard_admin(ajustes, metricas)
                elif rol == "gestor":
                    empresa_id = st.session_state.user.get("empresa_id")
                    metricas = get_metricas_gestor(empresa_id) if empresa_id else {}
                    mostrar_dashboard_gestor(ajustes, metricas)
                elif rol == "alumno":
                    mostrar_dashboard_alumno(ajustes)
                elif rol == "comercial":
                    mostrar_dashboard_comercial(ajustes)
        
        except Exception as e:
            st.error(f"❌ Error al cargar la aplicación: {e}")
            
            if st.session_state.get("rol") == "admin":
                with st.expander("🔧 Debug (Solo Admin)"):
                    st.write(f"Authenticated: {st.session_state.get('authenticated')}")
                    st.write(f"Rol: {st.session_state.get('rol')}")
                    st.write(f"Usuario: {st.session_state.get('user', {}).get('nombre')}")
            
            if st.button("🔄 Reiniciar Aplicación"):
                st.cache_data.clear()
                st.rerun()

if __name__ == "__main__":
    main()
