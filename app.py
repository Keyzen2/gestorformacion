import os
import sys
import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import time
import plotly.express as px
import plotly.graph_objects as go

from utils import get_ajustes_app

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# CONFIGURACIÓN PÁGINA + OCULTAR MENÚS STREAMLIT
# =============================================================================
st.set_page_config(
    page_title="Gestor Formación SaaS",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🎓",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# =============================================================================
# OCULTAR MENÚS Y ELEMENTOS STREAMLIT EN PRODUCCIÓN
# =============================================================================
def hide_streamlit_elements():
    """Oculta elementos de Streamlit no deseados en producción"""
    st.markdown("""
    <style>
    /* Ocultar menú hamburguesa */
    #MainMenu {visibility: hidden;}
    
    /* Ocultar footer "Made with Streamlit" */
    footer {visibility: hidden;}
    
    /* Ocultar header de Streamlit */
    header {visibility: hidden;}
    
    /* Ocultar botón de deploy */
    .stDeployButton {visibility: hidden;}
    
    /* Ocultar "Running" indicator */
    .stAppRunning {visibility: hidden;}
    
    /* Ocultar toolbar superior */
    .stToolbar {visibility: hidden;}
    
    /* Ocultar decoración superior */
    div[data-testid="stDecoration"] {visibility: hidden;}
    
    /* Ocultar viewerBadge_container */
    .viewerBadge_container__1QSob {visibility: hidden;}
    
    /* Ocultar elemento que dice "Rerun" */
    [data-testid="stStatusWidget"] {visibility: hidden;}
    
    /* === ARREGLAR PARPADEOS DE LOGIN === */
    .stSpinner {display: none !important;}
    .stProgress {display: none !important;}
    
    /* Evitar flash de colores al rerun */
    [data-testid="stAppViewContainer"] {
        background: #f1f5f9 !important;
        transition: none !important;
    }
    
    .main {
        background: #f1f5f9 !important;
        transition: none !important;
    }
    
    /* Suavizar transiciones globales */
    * {
        transition: none !important;
        animation: none !important;
    }
    
    /* Espaciado superior mejorado */
    .main > div {
        padding-top: 0rem;
    }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# CSS TAILADMIN COMPLETO
# =============================================================================
def load_tailadmin_css():
    """CSS TailAdmin completo integrado con tu sistema FUNDAE"""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* === VARIABLES TAILADMIN === */
    :root {
        --tailadmin-primary: #3c50e0;
        --tailadmin-secondary: #80caee;
        --tailadmin-success: #10b981;
        --tailadmin-warning: #fbbf24;
        --tailadmin-danger: #f87171;
        --tailadmin-dark: #1c2434;
        --tailadmin-body: #64748b;
        --tailadmin-border: #e2e8f0;
        --tailadmin-gray-2: #f7f9fc;
        --tailadmin-sidebar: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
    }

    /* === RESET GLOBAL === */
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

    /* === APP BACKGROUND === */
    .stApp {
        background: #f1f5f9 !important;
    }

    /* === SIDEBAR SIEMPRE VISIBLE CON SCROLL === */
    section[data-testid="stSidebar"] {
        background: var(--tailadmin-sidebar) !important;
        border-right: 1px solid #334155 !important;
        padding-top: 0 !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        position: relative !important;
        transform: translateX(0) !important;
        width: auto !important;
        min-width: 244px !important;
        overflow-y: auto !important;
        height: 100vh !important;
    }

    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
        font-size: 0.9rem;
    }

    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4 {
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        color: #94a3b8 !important;
        margin: 1rem 0 0.5rem 0 !important;
        font-weight: 600 !important;
    }

    section[data-testid="stSidebar"] hr {
        border-color: #334155 !important;
        margin: 1rem 0 !important;
    }

    /* === BOTONES SIDEBAR LOGOUT ESPECÍFICO === */
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(239, 68, 68, 0.1) !important;  /* Fondo rojo suave */
        border: 1px solid rgba(239, 68, 68, 0.3) !important;
        color: #ef4444 !important;  /* Texto rojo claro */
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-weight: 600 !important;
        width: 100% !important;
        text-align: left !important;
        transition: all 0.3s ease !important;
        margin-bottom: 0.25rem !important;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(239, 68, 68, 0.2) !important;
        border-color: #ef4444 !important;
        color: white !important;
        transform: translateX(4px);
        box-shadow: 0 4px 6px -1px rgba(239, 68, 68, 0.3);
    }

    section[data-testid="stSidebar"] .stButton > button:active,
    section[data-testid="stSidebar"] .stButton > button:focus {
        background: rgba(239, 68, 68, 0.3) !important;
        color: white !important;
        border-color: #ef4444 !important;
    }

    /* === BOTONES NAVEGACIÓN SIDEBAR (no logout) === */
    section[data-testid="stSidebar"] .stButton:not([title*="logout"]) > button {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        color: #f1f5f9 !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-weight: 500 !important;
        width: 100% !important;
        text-align: left !important;
        transition: all 0.3s ease !important;
        margin-bottom: 0.25rem !important;
    }

    section[data-testid="stSidebar"] .stButton:not([title*="logout"]) > button:hover {
        background: rgba(60, 80, 224, 0.25) !important;
        border-color: var(--tailadmin-primary) !important;
        color: white !important;
        transform: translateX(4px);
        box-shadow: 0 4px 6px -1px rgba(60, 80, 224, 0.3);
    }

    /* === MAIN CONTENT === */
    .main .block-container {
        background: #ffffff !important;
        padding: 2rem !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1) !important;
        max-width: 1600px !important;
        margin: 1rem auto !important;
    }

    /* === TÍTULOS TAILADMIN === */
    h1 {
        color: var(--tailadmin-dark) !important;
        font-weight: 700 !important;
        margin-bottom: 1.5rem !important;
        font-size: 2rem !important;
    }

    h2, h3 {
        color: #334155 !important;
        font-weight: 600 !important;
    }

    /* === CARDS / MÉTRICAS TAILADMIN === */
    .tailadmin-metric {
        background: linear-gradient(135deg, var(--tailadmin-primary) 0%, #6366f1 100%);
        color: white;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(60, 80, 224, 0.3);
        transition: all 0.3s ease;
        margin-bottom: 1rem;
    }

    .tailadmin-metric:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 12px -1px rgba(60, 80, 224, 0.4);
    }

    .tailadmin-metric h3 {
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
        color: white !important;
    }

    .tailadmin-metric p {
        font-size: 0.875rem !important;
        margin: 0.5rem 0 0 !important;
        opacity: 0.9;
        color: white !important;
    }

    /* === CARD GENÉRICA === */
    .tailadmin-card {
        background: white;
        border: 1px solid var(--tailadmin-border);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
        transition: all 0.3s ease;
    }

    .tailadmin-card:hover {
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }

    /* === INPUTS TAILADMIN === */
    .stTextInput > div > div > input,
    .stSelectbox select,
    .stTextArea textarea,
    .stNumberInput > div > div > input {
        background: #f8fafc !important;
        border: 1.5px solid var(--tailadmin-border) !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-size: 0.95rem !important;
        transition: all 0.3s ease !important;
    }

    .stTextInput > div > div > input:focus,
    .stSelectbox select:focus,
    .stTextArea textarea:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--tailadmin-primary) !important;
        box-shadow: 0 0 0 3px rgba(60, 80, 224, 0.1) !important;
        background: #fff !important;
    }

    /* === BOTONES TAILADMIN === */
    .stButton > button {
        background: linear-gradient(135deg, var(--tailadmin-primary) 0%, #6366f1 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        font-size: 0.875rem !important;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, var(--tailadmin-primary) 100%) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(60, 80, 224, 0.4) !important;
    }

    /* === ALERTAS TAILADMIN === */
    .stAlert {
        border-radius: 8px !important;
        border-left: 4px solid !important;
        font-weight: 500 !important;
    }

    .stSuccess {
        border-left-color: var(--tailadmin-success) !important;
        background: #f0fdf4 !important;
        color: #166534 !important;
    }

    .stError {
        border-left-color: var(--tailadmin-danger) !important;
        background: #fef2f2 !important;
        color: #991b1b !important;
    }

    .stInfo {
        border-left-color: var(--tailadmin-primary) !important;
        background: #eff6ff !important;
        color: #1e40af !important;
    }

    .stWarning {
        border-left-color: var(--tailadmin-warning) !important;
        background: #fffbeb !important;
        color: #92400e !important;
    }

    /* === TABLAS TAILADMIN === */
    [data-testid="stDataFrame"] table {
        border: 1px solid var(--tailadmin-border) !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }

    [data-testid="stDataFrame"] th {
        background: var(--tailadmin-gray-2) !important;
        color: var(--tailadmin-dark) !important;
        font-weight: 600 !important;
        padding: 1rem !important;
    }

    [data-testid="stDataFrame"] td {
        padding: 0.75rem 1rem !important;
        border-bottom: 1px solid var(--tailadmin-border) !important;
    }

    /* === TABS TAILADMIN === */
    [data-testid="stTabs"] button {
        background: #f1f5f9 !important;
        border-radius: 8px 8px 0 0 !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 500 !important;
        border: 1px solid var(--tailadmin-border) !important;
        border-bottom: none !important;
        color: var(--tailadmin-body) !important;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        background: #fff !important;
        border-bottom: 2px solid var(--tailadmin-primary) !important;
        color: var(--tailadmin-dark) !important;
        font-weight: 600 !important;
    }

    /* === HEADER BIENVENIDA === */
    .tailadmin-header {
        background: white;
        border: 1px solid var(--tailadmin-border);
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
    }

    /* === FORMULARIO LOGIN PERSONALIZADO === */
    .login-container {
        display: none !important; /* Ocultar contenedor vacío */
    }
    
    /* Estilos para inputs del formulario */
    form[data-testid="form"] .stTextInput > div > div > input {
        max-width: 300px !important;
        margin: 0 auto !important;
        background: rgba(255, 255, 255, 0.9) !important;
        border: 1.5px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-size: 0.95rem !important;
        backdrop-filter: blur(5px) !important;
    }

    form[data-testid="form"] .stTextInput > div > div > input:focus {
        border-color: #3c50e0 !important;
        box-shadow: 0 0 0 3px rgba(60, 80, 224, 0.2) !important;
        background: rgba(255, 255, 255, 0.95) !important;
    }

    /* Botón del formulario de login */
    form[data-testid="form"] .stButton > button {
        max-width: 300px !important;
        margin: 1.5rem auto !important;
        display: block !important;
        padding: 0.8rem 1.5rem !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        background: linear-gradient(135deg, #3c50e0 0%, #6366f1 100%) !important;
        border: none !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 10px rgba(60, 80, 224, 0.3) !important;
    }

    form[data-testid="form"] .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 15px rgba(60, 80, 224, 0.4) !important;
    }

    /* === BREADCRUMB === */
    .tailadmin-breadcrumb {
        background: var(--tailadmin-gray-2);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 1.5rem;
        font-size: 0.875rem;
        color: var(--tailadmin-body);
        border: 1px solid var(--tailadmin-border);
    }

    /* === ELIMINAR COMPLETAMENTE EFECTOS DE LOGIN === */
    /* Ocultar TODOS los elementos que causan overlay */
    .stSpinner, .stProgress, [data-testid="stSpinner"], 
    [data-testid="stProgressBar"], .stAlert > div[data-baseweb="notification"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
    }
    
    /* Evitar overlay transparente en login */
    [data-testid="stAppViewContainer"]::before,
    [data-testid="stAppViewContainer"]::after {
        display: none !important;
    }
    
    /* Evitar barras de progreso y hovers */
    .stProgress > div, .element-container .stProgress {
        display: none !important;
    }
    
    /* Eliminar transiciones que causan efectos */
    body, html, .main, .stApp, [data-testid="stAppViewContainer"] {
        transition: none !important;
        animation: none !important;
        backdrop-filter: none !important;
        background-attachment: fixed !important;
    }
    
    /* Asegurar que el fondo se mantenga estable */
    .main {
        background: #f1f5f9 !important;
        transition: none !important;
    }

    /* === BOTÓN EXPANDIR SIDEBAR === */
    button[kind="header"] {
        display: block !important;
        visibility: visible !important;
        background: var(--tailadmin-sidebar) !important;
        color: white !important;
        border: 1px solid #334155 !important;
        border-radius: 0 8px 8px 0 !important;
        padding: 0.5rem !important;
        position: fixed !important;
        top: 1rem !important;
        left: 0 !important;
        z-index: 999 !important;
        box-shadow: 2px 2px 4px rgba(0,0,0,0.2) !important;
    }

    button[kind="header"]:hover {
        background: var(--tailadmin-primary) !important;
        border-color: var(--tailadmin-primary) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# COMPONENTES TAILADMIN
# =============================================================================
class TailAdminComponents:
    """Componentes TailAdmin adaptados para FUNDAE"""
    
    @staticmethod
    def metric_card(title: str, value: str, icon: str = "📊", gradient: str = "primary"):
        """Métrica estilo TailAdmin"""
        gradients = {
            "primary": "linear-gradient(135deg, #3c50e0 0%, #6366f1 100%)",
            "success": "linear-gradient(135deg, #10b981 0%, #059669 100%)",
            "warning": "linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)",
            "danger": "linear-gradient(135deg, #f87171 0%, #ef4444 100%)"
        }
        
        st.markdown(f"""
        <div style="
            background: {gradients.get(gradient, gradients['primary'])};
            color: white;
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 4px 6px -1px rgba(60, 80, 224, 0.3);
            transition: all 0.3s ease;
            margin-bottom: 1rem;
        ">
            <div style="font-size: 2.5rem; margin-bottom: 0.5rem; opacity: 0.8;">{icon}</div>
            <h3 style="font-size: 2.5rem; font-weight: 700; margin: 0; color: white;">{value}</h3>
            <p style="font-size: 0.875rem; margin: 0.5rem 0 0; opacity: 0.9; color: white;">{title}</p>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def breadcrumb(items):
        """Breadcrumb de navegación"""
        breadcrumb_items = " > ".join([
            f"<span style='color: #3c50e0; font-weight: 600;'>{item}</span>" 
            if i == len(items)-1 else item 
            for i, item in enumerate(items)
        ])
        
        st.markdown(f"""
        <div class="tailadmin-breadcrumb">
            🏠 {breadcrumb_items}
        </div>
        """, unsafe_allow_html=True)

    @staticmethod
    def header_welcome(user_name: str, company: str = "FUNDAE"):
        """Header de bienvenida estilo TailAdmin"""
        st.markdown(f"""
        <div class="tailadmin-header">
            <div style="display: flex; align-items: center; gap: 1.5rem;">
                <div style="
                    width: 64px; height: 64px; 
                    background: linear-gradient(135deg, #3c50e0 0%, #6366f1 100%);
                    border-radius: 50%;
                    display: flex; align-items: center; justify-content: center;
                    color: white; font-weight: bold; font-size: 1.5rem;
                    box-shadow: 0 4px 6px -1px rgba(60, 80, 224, 0.3);
                ">
                    {user_name[0].upper()}
                </div>
                <div>
                    <h1 style="margin: 0; color: #1c2434; font-size: 2rem;">¡Bienvenido, {user_name}!</h1>
                    <p style="margin: 0; color: #64748b; font-size: 1rem;">
                        {company} • {datetime.now().strftime('%d de %B, %Y')}
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    @staticmethod
    def info_card(title: str, content: str, icon: str = "📊"):
        """Card informativa estilo TailAdmin"""
        st.markdown(f"""
        <div class="tailadmin-card">
            <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                <div style="font-size: 2rem;">{icon}</div>
                <h3 style="margin: 0; color: #1c2434; font-size: 1.25rem;">{title}</h3>
            </div>
            <div style="color: #64748b; line-height: 1.6; white-space: pre-line;">
                {content}
            </div>
        </div>
        """, unsafe_allow_html=True)
    @staticmethod
    def status_badge(status: str, text: str = ""):
        """Crea badges de estado estilo TailAdmin"""
        status_config = {
            "ACTIVO": {"bg": "#dcfce7", "color": "#166534", "icon": "✅"},
            "INACTIVO": {"bg": "#fee2e2", "color": "#991b1b", "icon": "❌"},
            "PENDIENTE": {"bg": "#fef3c7", "color": "#92400e", "icon": "⏳"},
            "FINALIZADO": {"bg": "#dbeafe", "color": "#1e40af", "icon": "🏁"}
        }
        
        config = status_config.get(status.upper(), {"bg": "#f3f4f6", "color": "#374151", "icon": "📝"})
        display_text = text or status
        
        return f"""
        <span class="tailadmin-badge" style="
            background: {config['bg']}; 
            color: {config['color']};
        ">
            {config['icon']} {display_text}
        </span>
        """
# =============================================================================
# CONFIGURACIÓN SUPABASE (RAILWAY COMPATIBLE)
# =============================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("⚠️ Error: Variables de Supabase no configuradas correctamente")
    st.stop()

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else None

# =============================================================================
# ESTADO INICIAL - CON BANDERA DE AUTENTICACIÓN CLARA
# =============================================================================
for key, default in {
    "page": "home",
    "rol": None,
    "role": None,  # Para compatibilidad con archivos que usan 'role'
    "user": {},
    "auth_session": None,
    "login_loading": False,
    "authenticated": False  # 🔑 BANDERA CLARA de autenticación
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =============================================================================
# FUNCIONES AUXILIARES (MISMA LÓGICA, MEJORADO MANEJO ERRORES)
# =============================================================================
@st.cache_data(ttl=300)
def get_metricas_admin():
    """Obtiene métricas admin con manejo robusto de errores"""
    try:
        if not supabase_admin:
            return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}
            
        total_empresas = supabase_admin.table("empresas").select("id", count="exact").execute().count or 0
        total_usuarios = supabase_admin.table("usuarios").select("id", count="exact").execute().count or 0
        total_cursos = supabase_admin.table("acciones_formativas").select("id", count="exact").execute().count or 0
        total_grupos = supabase_admin.table("grupos").select("id", count="exact").execute().count or 0
        
        return {
            "empresas": total_empresas,
            "usuarios": total_usuarios, 
            "cursos": total_cursos,
            "grupos": total_grupos
        }
    except Exception as e:
        print(f"Error obteniendo métricas admin: {e}")
        return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}

@st.cache_data(ttl=300)
def get_metricas_gestor(empresa_id):
    """Obtiene métricas del gestor"""
    try:
        if not supabase_admin or not empresa_id:
            return {"grupos": 0, "participantes": 0, "documentos": 0}
            
        grupos_res = supabase_admin.table("grupos").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        participantes_res = supabase_admin.table("participantes").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        documentos_res = supabase_admin.table("documentos").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        
        return {
            "grupos": grupos_res.count or 0,
            "participantes": participantes_res.count or 0,
            "documentos": documentos_res.count or 0
        }
    except Exception as e:
        print(f"Error obteniendo métricas gestor: {e}")
        return {"grupos": 0, "participantes": 0, "documentos": 0}

def set_user_role_from_db(email: str):
    """Obtiene rol de usuario desde BD y sincroniza ambas variables"""
    try:
        clean_email = email.strip().lower()
        res = supabase_public.table("usuarios").select("*").eq("email", clean_email).limit(1).execute()
        if res.data:
            row = res.data[0]
            rol = row.get("rol") or "alumno"
            
            # CRÍTICO: Sincronizar ambas variables para compatibilidad
            st.session_state.rol = rol
            st.session_state.role = rol  # ← Para archivos que usan 'role'
            
            st.session_state.user = {
                "id": row.get("id"),
                "auth_id": row.get("auth_id"),
                "email": row.get("email"),
                "nombre": row.get("nombre"),
                "empresa_id": row.get("empresa_id")
            }
        else:
            st.session_state.rol = "alumno"
            st.session_state.role = "alumno"  # ← Sincronizar
            st.session_state.user = {"email": clean_email, "empresa_id": None}
    except Exception as e:
        print(f"Error obteniendo rol: {e}")
        st.session_state.rol = "alumno"
        st.session_state.role = "alumno"  # ← Sincronizar
        st.session_state.user = {"email": email, "empresa_id": None}

def do_logout():
    """Logout con limpieza completa y reinicialización"""
    try:
        supabase_public.auth.sign_out()
    except Exception:
        pass
    
    # Limpiar todo el estado
    st.cache_data.clear()
    st.session_state.clear()
    
    # Reinicializar variables críticas inmediatamente
    st.session_state.authenticated = False  # ← Bandera clara
    st.session_state.rol = None
    st.session_state.role = None
    st.session_state.user = {}
    st.session_state.page = "home"
    st.session_state.auth_session = None
    
    st.rerun()

# =============================================================================
# LOGIN TAILADMIN MEJORADO
# =============================================================================
def login_view_tailadmin():
    """Login limpio SIN rectángulos blancos ni overlays"""
    
    # Logo fijo de DataFor
    logo_datafor = "https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/datafor-logo.png"

    # Fondo de pantalla
    st.markdown("""
    <div style="
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        z-index: -1;
    "></div>
    """, unsafe_allow_html=True)

    # Spacer pequeño
    st.markdown('<div style="height: 1vh;"></div>', unsafe_allow_html=True)

    # Logo grande centrado
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 1.5rem;">
        <img src="{logo_datafor}" style="
            width: 200px; 
            height: auto; 
            object-fit: contain;
            background: white;
            padding: 25px;
            border-radius: 20px;
            box-shadow: 0 15px 30px -8px rgba(0, 0, 0, 0.25);
            border: 2px solid rgba(255, 255, 255, 0.4);
        " alt="DataFor Logo">
    </div>
    """, unsafe_allow_html=True)

    # Formulario DIRECTO sin contenedores adicionales
    st.markdown("### 🔐 Iniciar Sesión")
    
    with st.form("form_login", clear_on_submit=False):
        email = st.text_input(
            "Email", 
            placeholder="usuario@empresa.com"
        )
        
        password = st.text_input(
            "Contraseña", 
            type="password",
            placeholder="••••••••"
        )
        
        # Botón de login
        submitted = st.form_submit_button(
            "🚀 Iniciar Sesión",
            use_container_width=True
        )

    # Lógica de autenticación CON BANDERA CLARA
    if submitted:
        if not email or not password:
            st.error("⚠️ Por favor, completa todos los campos")
        else:
            try:
                auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
                
                if auth and auth.user:
                    # 🔑 BANDERA CLARA DE AUTENTICACIÓN
                    st.session_state.auth_session = auth
                    st.session_state.authenticated = True  # ← Marca inequívoca
                    set_user_role_from_db(auth.user.email)
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas")
                    
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # Footer fijo
    st.markdown("""
    <div style="
        margin-top: 3rem;
        padding: 1.5rem 1rem;
        text-align: center;
        background: rgba(0, 0, 0, 0.05);
        border-top: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 12px;
    ">
        <p style="color: #374151; font-size: 0.85rem; margin: 0; font-weight: 500;">
            © 2025 DataFor Solutions - Gestor Formación SaaS
        </p>
        <p style="color: #6b7280; font-size: 0.75rem; margin: 0.25rem 0 0;">
            Todos los derechos reservados • Versión 2.1.0
        </p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# DASHBOARDS TAILADMIN POR ROL
# =============================================================================
def mostrar_dashboard_admin_tailadmin(ajustes, metricas):
    """Dashboard admin con métricas visibles"""
    components = TailAdminComponents()
    
    # Header de bienvenida
    user_name = st.session_state.user.get("nombre", "Administrador")
    components.header_welcome(user_name, "Sistema FUNDAE")
    
    # Breadcrumb
    components.breadcrumb(["Dashboard", "Panel de Administración"])
    
    # Título principal
    st.markdown(f"## {ajustes.get('bienvenida_admin', 'Panel de Administración')}")
    
    # Métricas principales - ESTAS SON LAS QUE FALTABAN
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        components.metric_card("Empresas", str(metricas['empresas']), "🏢", "primary")
    
    with col2:
        components.metric_card("Usuarios", str(metricas['usuarios']), "👥", "success")
    
    with col3:
        components.metric_card("Cursos", str(metricas['cursos']), "📚", "warning")
    
    with col4:
        components.metric_card("Grupos", str(metricas['grupos']), "👨‍🎓", "danger")
    
    # Información adicional con info_card (ahora definida)
    st.markdown("### 📊 Información del Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        components.info_card(
            "Estado del Sistema", 
            "✅ Sistema funcionando correctamente\n🔄 Última sincronización: " + datetime.now().strftime('%H:%M'),
            "⚙️"
        )
    
    with col2:
        components.info_card(
            "Estadísticas Generales",
            f"📈 Total entidades: {sum(metricas.values())}\n📅 Última actualización: Hoy",
            "📊"
        )

def mostrar_dashboard_gestor_tailadmin(ajustes, metricas):
    """Dashboard gestor con diseño TailAdmin"""
    components = TailAdminComponents()
    
    # Header de bienvenida
    user_name = st.session_state.user.get("nombre", "Gestor")
    components.header_welcome(user_name, "Gestión de Formación")
    
    # Breadcrumb
    components.breadcrumb(["Dashboard", "Panel del Gestor"])
    
    # Título
    st.markdown(f"## {ajustes.get('bienvenida_gestor', 'Panel del Gestor')}")
    
    # Métricas del gestor
    col1, col2, col3 = st.columns(3)
    
    with col1:
        components.metric_card("Grupos", str(metricas.get('grupos', 0)), "👨‍🎓", "primary")
        st.caption(ajustes.get("tarjeta_gestor_grupos", "Crea y gestiona grupos formativos"))
    
    with col2:
        components.metric_card("Participantes", str(metricas.get('participantes', 0)), "🧑‍🎓", "success")
        st.caption("Alumnos inscritos en tus grupos")
    
    with col3:
        components.metric_card("Documentos", str(metricas.get('documentos', 0)), "📂", "warning")
        st.caption(ajustes.get("tarjeta_gestor_documentos", "Documentación y certificados"))

def mostrar_dashboard_alumno_tailadmin(ajustes):
    """Dashboard alumno con diseño TailAdmin"""
    components = TailAdminComponents()
    
    # Header
    user_name = st.session_state.user.get("nombre", "Alumno")
    components.header_welcome(user_name, "Área del Estudiante")
    
    # Breadcrumb
    components.breadcrumb(["Dashboard", "Área del Alumno"])
    
    # Título
    st.markdown(f"## {ajustes.get('bienvenida_alumno', 'Área del Alumno')}")
    
    # Cards informativas
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="tailadmin-card" style="text-align: center; padding: 2rem;">', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size: 3rem; margin-bottom: 1rem;">📘</div>
        <h3 style="color: #1c2434; margin: 0;">Mis Grupos</h3>
        <p style="color: #64748b; margin: 0.5rem 0 0;">Consulta tus grupos activos</p>
        """, unsafe_allow_html=True)
        if st.button("Ver Mis Grupos", key="btn_grupos_alumno"):
            st.session_state.page = "area_alumno"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="tailadmin-card" style="text-align: center; padding: 2rem;">', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size: 3rem; margin-bottom: 1rem;">🎓</div>
        <h3 style="color: #1c2434; margin: 0;">Mis Certificados</h3>
        <p style="color: #64748b; margin: 0.5rem 0 0;">Descarga tus diplomas</p>
        """, unsafe_allow_html=True)
        if st.button("Ver Certificados", key="btn_certificados_alumno"):
            st.info("Funcionalidad en desarrollo")
        st.markdown('</div>', unsafe_allow_html=True)

def mostrar_dashboard_comercial_tailadmin(ajustes):
    """Dashboard comercial con diseño TailAdmin"""
    components = TailAdminComponents()
    
    # Header
    user_name = st.session_state.user.get("nombre", "Comercial")
    components.header_welcome(user_name, "Área Comercial CRM")
    
    # Breadcrumb
    components.breadcrumb(["Dashboard", "Área Comercial"])
    
    # Título
    st.markdown(f"## {ajustes.get('bienvenida_comercial', 'Área Comercial')}")
    
    # Métricas CRM
    col1, col2, col3 = st.columns(3)
    
    with col1:
        components.metric_card("Clientes", "45", "👥", "primary")
        st.caption(ajustes.get("tarjeta_comercial_clientes", "Gestiona tu cartera"))
    
    with col2:
        components.metric_card("Oportunidades", "12", "💡", "success")
        st.caption(ajustes.get("tarjeta_comercial_oportunidades", "Nuevas oportunidades"))
    
    with col3:
        components.metric_card("Tareas", "8", "📝", "warning")
        st.caption(ajustes.get("tarjeta_comercial_tareas", "Tus recordatorios"))

# =============================================================================
# SIDEBAR TAILADMIN
# =============================================================================
def render_sidebar_tailadmin():
    """Sidebar con logo DataFor personalizado + Control de módulos activos"""
    
    rol = st.session_state.get("rol")
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")
    empresa_id = st.session_state.user.get("empresa_id")

    # Logo DataFor fijo
    logo_datafor = "https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/datafor-logo.png"

    # Header del sidebar con logo DataFor + avatar usuario
    st.sidebar.markdown(f"""
    <div style="
        padding: 1rem 1rem 1.5rem; 
        border-bottom: 1px solid #334155; 
        margin-bottom: 1.5rem;
        text-align: center;
    ">
        <!-- Logo DataFor -->
        <div style="
            width: 50px; 
            height: 50px;
            margin: 0 auto 1rem;
            border-radius: 8px;
            overflow: hidden;
            background: white;
            padding: 6px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        ">
            <img src="{logo_datafor}" style="
                width: 100%; 
                height: 100%; 
                object-fit: contain;
            " alt="DataFor">
        </div>
        
        <!-- Info del usuario -->
        <p style="margin: 0; font-weight: 600; color: #f1f5f9; font-size: 0.85rem;">{nombre_usuario}</p>
        <p style="margin: 0.25rem 0 0; font-size: 0.7rem; color: #94a3b8; text-transform: uppercase;">
            {rol.title() if rol else 'Usuario'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # VERIFICAR MÓDULOS ACTIVOS PARA ROLES HABILITADOS
    modulos_empresa = {}
    modulos_crm = {}
    
    if rol in ["admin", "gestor", "comercial"] and empresa_id:
        try:
            # Obtener estado de módulos de empresa
            empresa_res = supabase_admin.table("empresas").select(
                "formacion_activo", "formacion_inicio", "formacion_fin",
                "iso_activo", "iso_inicio", "iso_fin", 
                "rgpd_activo", "rgpd_inicio", "rgpd_fin",
                "docu_avanzada_activo", "docu_avanzada_inicio", "docu_avanzada_fin"
            ).eq("id", empresa_id).execute()
            
            if empresa_res.data:
                modulos_empresa = empresa_res.data[0]
                
            # Obtener módulos CRM
            crm_res = supabase_admin.table("crm_empresas").select(
                "crm_activo", "crm_inicio", "crm_fin"
            ).eq("empresa_id", empresa_id).execute()
            
            if crm_res.data:
                modulos_crm = crm_res.data[0]
                
        except Exception as e:
            print(f"Error obteniendo módulos activos: {e}")

    # Función auxiliar para verificar si un módulo está activo
    def esta_modulo_activo(modulo_key, modulos_dict):
        if not modulos_dict:
            return True  # Si no hay datos, permitir acceso (para admin)
        return modulos_dict.get(f"{modulo_key}_activo", False)

    # Menú por roles CON verificación de módulos activos
    if rol == "admin":
        # Bloque Administración SaaS
        st.sidebar.markdown("#### ⚙️ Administración SaaS")
        st.sidebar.markdown("---")
        admin_menu = {
            "📊 Panel Admin": "panel_admin",
            "👥 Usuarios": "usuarios_empresas", 
            "🏢 Empresas": "empresas",
            "⚙️ Ajustes": "ajustes_app"
        }
        for label, page_key in admin_menu.items():
            if st.sidebar.button(label, use_container_width=True, key=f"nav_{page_key}"):
                st.session_state.page = page_key
                st.rerun()
        
        # Además mostrar TODOS los módulos como si fuera gestor + comercial
        render_modulos_empresa(modulos_empresa, modulos_crm)
        
    elif rol == "gestor":
        st.sidebar.markdown("#### 🎓 Gestión de Formación")
        menu = {}
        
        # Módulo de formación
        if esta_modulo_activo("formacion", modulos_empresa):
            menu.update({
                "📊 Panel Gestor": "panel_gestor",
                "🏢 Empresas": "empresas",
                "📚 Acciones Formativas": "acciones_formativas",
                "👨‍🎓 Grupos": "grupos",
                "🧑‍🎓 Participantes": "participantes", 
                "👩‍🏫 Tutores": "tutores",
                "🏫 Aulas": "aulas",
                "📅 Gestión Clases": "gestion_clases",
                "📂 Documentos": "documentos"
            })
        
        # Módulo ISO (si está activo)
        if esta_modulo_activo("iso", modulos_empresa):
            st.sidebar.markdown("#### 🏅 ISO 9001")
            menu.update({
                "📊 Dashboard Calidad": "dashboard_calidad",
                "❌ No Conformidades": "no_conformidades",
                "🔧 Acciones Correctivas": "acciones_correctivas",
                "🔍 Auditorías": "auditorias",
                "📈 Indicadores": "indicadores",
                "🎯 Objetivos Calidad": "objetivos_calidad"
            })
        
        # Módulo RGPD (si está activo)
        if esta_modulo_activo("rgpd", modulos_empresa):
            st.sidebar.markdown("#### 🔒 RGPD")
            menu.update({
                "🛡️ Panel RGPD": "rgpd_panel",
                "📋 Tratamientos": "rgpd_tratamientos",
                "✅ Consentimientos": "rgpd_consentimientos"
            })
        
        # Módulo Documentación Avanzada (si está activo)
        if esta_modulo_activo("docu_avanzada", modulos_empresa):
            st.sidebar.markdown("#### 📚 Documentación Avanzada")
            menu.update({
                "📖 Gestión Documental": "documentacion_avanzada"
            })
            
        # Si no hay módulos activos, mostrar mensaje
        if not menu:
            st.sidebar.warning("⚠️ No tienes módulos activos")
        
    elif rol == "comercial":
        st.sidebar.markdown("#### 💼 CRM Comercial")
        menu = {}
        
        # Verificar si CRM está activo
        if esta_modulo_activo("crm", modulos_crm):
            menu = {
                "📊 Panel CRM": "crm_panel",
                "👥 Clientes": "crm_clientes", 
                "💡 Oportunidades": "crm_oportunidades",
                "📝 Tareas": "crm_tareas",
                "📞 Comunicaciones": "crm_comunicaciones",
                "📈 Estadísticas": "crm_estadisticas"
            }
        else:
            st.sidebar.warning("⚠️ Módulo CRM no activo")
            menu = {}
        
    elif rol == "alumno":
        st.sidebar.markdown("#### 🎓 Área Estudiante")
        # Los alumnos siempre tienen acceso a su área
        menu = {
            "📘 Mis Grupos": "area_alumno"
        }
    else:
        menu = {}

    # Renderizar menú solo si hay opciones disponibles
    if menu:
        for label, page_key in menu.items():
            if st.sidebar.button(label, use_container_width=True, key=f"nav_{page_key}"):
                st.session_state.page = page_key
                st.rerun()
    
    # Botón logout diferenciado
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True, key="logout_btn", help="Cerrar sesión"):
        do_logout()

    # Info adicional con branding DataFor
    st.sidebar.markdown("---")
    st.sidebar.markdown("**DataFor**: Gestor Formación SaaS")
    st.sidebar.markdown("**Versión**: v2.1.0 TailAdmin")

# =============================================================================
# NAVEGACIÓN - COMPATIBLE CON RAILWAY (FUNCIONES render())
# =============================================================================
def render_page():
    """Renderiza páginas - Compatible con Railway donde usamos render()"""
    page = st.session_state.get("page", "home")

    if page and page != "home":
        with st.spinner(f"⏳ Cargando {page.replace('_', ' ').title()}..."):
            try:
                # Mapeo de páginas a módulos - MISMO QUE TIENES
                page_map = {
                    "panel_admin": "panel_admin",
                    "usuarios_empresas": "usuarios_empresas",
                    "empresas": "empresas",
                    "ajustes_app": "ajustes_app",
                    "panel_gestor": "panel_gestor",
                    "acciones_formativas": "acciones_formativas",
                    "grupos": "grupos",
                    "participantes": "participantes",
                    "tutores": "tutores",
                    "aulas": "aulas",
                    "gestion_clases": "gestion_clases",
                    "proyectos": "proyectos",
                    "documentos": "documentos",
                    "area_alumno": "area_alumno",
                    "no_conformidades": "no_conformidades",
                    "acciones_correctivas": "acciones_correctivas",
                    "auditorias": "auditorias",
                    "indicadores": "indicadores",
                    "dashboard_calidad": "dashboard_calidad",
                    "objetivos_calidad": "objetivos_calidad",
                    "informe_auditoria": "informe_auditoria",
                    "rgpd_panel": "rgpd_panel",
                    "rgpd_tratamientos": "rgpd_tratamientos",
                    "rgpd_consentimientos": "rgpd_consentimientos",
                    "crm_panel": "crm_panel",
                    "crm_clientes": "crm_clientes",
                    "crm_oportunidades": "crm_oportunidades",
                    "crm_tareas": "crm_tareas",
                    "crm_comunicaciones": "crm_comunicaciones",
                    "crm_estadisticas": "crm_estadisticas",
                    "documentacion_avanzada": "documentacion_avanzada"
                }

                if page in page_map:
                    # CLAVE: Importa el módulo y llama render() (no main())
                    view_module = __import__(f"views.{page_map[page]}", fromlist=["render"])
                    view_module.render(supabase_admin, st.session_state)
                else:
                    st.error(f"❌ Página '{page}' no encontrada")
                    st.info("🏠 Volviendo al dashboard principal...")
                    if st.button("Ir al Dashboard"):
                        st.session_state.page = "home"
                        st.rerun()

            except Exception as e:
                st.error(f"❌ Error al cargar página: {e}")
                st.exception(e)
                
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("🔄 Reintentar", use_container_width=True):
                        st.rerun()

# =============================================================================
# FUNCIONES HEADER Y FOOTER - REMOVIDOS (SIN HEADER/FOOTER FIJO)
# =============================================================================
def render_header():
    """Header removido - sin header fijo para mejor estética"""
    pass

def render_footer():
    """Footer removido - sin footer fijo para mejor estética"""  
    pass

# =============================================================================
# ⚡ FUNCIÓN PRINCIPAL - ENTRY POINT PARA RAILWAY
# =============================================================================
def main():
    """Función principal que ejecuta toda la aplicación"""
    
    # 1. Cargar estilos y ocultar elementos PRIMERO
    hide_streamlit_elements()
    load_tailadmin_css()
    
    # 2. Verificar autenticación - CORREGIDO
    usuario_autenticado = st.session_state.get("authenticated", False)
    
    if not usuario_autenticado:
        # ============= MODO LOGIN =============
        login_view_tailadmin()
        
    else:
        # ============= MODO APLICACIÓN =============
        
        try:
            # Header y footer (opcional - están vacíos)
            render_header()
            render_footer()

            # CRÍTICO: Asegurar que el sidebar se muestre
            st.set_option('client.showSidebarNavigation', True)
            
            # Sidebar TailAdmin
            render_sidebar_tailadmin()

            # Contenido principal
            page = st.session_state.get("page", "home")

            if page and page != "home":
                render_page()
            else:
                # ============= DASHBOARDS DE BIENVENIDA =============
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
                    mostrar_dashboard_admin_tailadmin(ajustes, metricas)

                elif rol == "gestor":
                    empresa_id = st.session_state.user.get("empresa_id")
                    metricas = get_metricas_gestor(empresa_id) if empresa_id else {}
                    mostrar_dashboard_gestor_tailadmin(ajustes, metricas)

                elif rol == "alumno":
                    mostrar_dashboard_alumno_tailadmin(ajustes)

                elif rol == "comercial":
                    mostrar_dashboard_comercial_tailadmin(ajustes)

        except Exception as e:
            st.error(f"❌ Error al cargar la aplicación: {e}")
            
            # DEBUG - Mostrar información del estado
            if st.session_state.get("rol") == "admin":
                with st.expander("🔧 Información de Debug (Solo Admin)"):
                    st.write("**Estado de sesión:**")
                    st.write(f"- Authenticated: {st.session_state.get('authenticated')}")
                    st.write(f"- Rol: {st.session_state.get('rol')}")
                    st.write(f"- Usuario: {st.session_state.get('user', {}).get('nombre')}")
            
            # Botón de recuperación
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("🔄 Reiniciar Aplicación", use_container_width=True):
                    st.cache_data.clear()
                    st.rerun()

# =============================================================================
# 🎯 ENTRY POINT - EJECUTAR LA APLICACIÓN
# =============================================================================
if __name__ == "__main__":
    main()
