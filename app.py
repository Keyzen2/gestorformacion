import os
import sys
import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import time

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
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# =============================================================================
# OCULTAR MENÚS STREAMLIT
# =============================================================================
def hide_streamlit_elements():
    """Oculta elementos de Streamlit no deseados"""
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {visibility: hidden;}
    div[data-testid="stDecoration"] {visibility: hidden;}
    [data-testid="stStatusWidget"] {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# CSS TAILADMIN LIGHT THEME COMPLETO
# =============================================================================
def load_tailadmin_light_css():
    """CSS TailAdmin Light Theme + Componentes Avanzados"""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ============================================
       VARIABLES TAILADMIN LIGHT THEME
    ============================================ */
    :root {
        /* Colores principales */
        --primary: #3C50E0;
        --primary-dark: #2E40C0;
        --secondary: #80CAEE;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
        --info: #3B82F6;
        
        /* Tonos de gris/blanco */
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
        
        /* Textos */
        --text-primary: #1F2937;
        --text-secondary: #6B7280;
        --text-tertiary: #9CA3AF;
        
        /* Bordes y fondos */
        --border-color: #E5E7EB;
        --bg-page: #F9FAFB;
        --bg-card: #FFFFFF;
        --bg-sidebar: #FFFFFF;
        
        /* Sombras */
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        
        /* Transiciones */
        --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* ============================================
       RESET Y BASE
    ============================================ */
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--text-primary);
    }

    /* ============================================
       APP BACKGROUND
    ============================================ */
    .stApp {
        background: var(--bg-page) !important;
    }
    
    .main .block-container {
        background: transparent !important;
        padding: 1.5rem !important;
        max-width: 1600px !important;
    }

    /* ============================================
       SIDEBAR LIGHT THEME
    ============================================ */
    section[data-testid="stSidebar"] {
        background: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border-color) !important;
        box-shadow: var(--shadow-md) !important;
        padding: 0 !important;
    }
    
    /* Header del sidebar con logo */
    section[data-testid="stSidebar"] > div:first-child {
        padding: 1.5rem 1rem !important;
        border-bottom: 1px solid var(--border-color);
        background: linear-gradient(180deg, var(--white) 0%, var(--gray-50) 100%);
    }
    
    /* Texto del sidebar */
    section[data-testid="stSidebar"] * {
        color: var(--text-primary) !important;
    }
    
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

    /* ============================================
       BOTONES SIDEBAR - NAVEGACIÓN
    ============================================ */
    section[data-testid="stSidebar"] .stButton > button {
        background: var(--white) !important;
        border: 1px solid var(--border-color) !important;
        color: var(--text-primary) !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        width: 100% !important;
        text-align: left !important;
        transition: var(--transition) !important;
        margin-bottom: 0.5rem !important;
        box-shadow: var(--shadow-sm) !important;
    }
    
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: var(--primary) !important;
        color: var(--white) !important;
        border-color: var(--primary) !important;
        transform: translateX(4px);
        box-shadow: var(--shadow-md) !important;
    }
    
    /* Botón Logout específico */
    section[data-testid="stSidebar"] .stButton:last-child > button {
        background: #FEE2E2 !important;
        border-color: #FECACA !important;
        color: var(--danger) !important;
    }
    
    section[data-testid="stSidebar"] .stButton:last-child > button:hover {
        background: var(--danger) !important;
        color: var(--white) !important;
        border-color: var(--danger) !important;
    }

    /* ============================================
       TÍTULOS Y TEXTOS
    ============================================ */
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
    
    p {
        color: var(--text-secondary);
        line-height: 1.6;
    }

    /* ============================================
       CARDS Y CONTENEDORES
    ============================================ */
    .tailadmin-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: var(--shadow);
        transition: var(--transition);
        margin-bottom: 1.5rem;
    }
    
    .tailadmin-card:hover {
        box-shadow: var(--shadow-lg);
        transform: translateY(-2px);
    }
    
    /* Header de cards */
    .tailadmin-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 1rem;
        margin-bottom: 1rem;
        border-bottom: 1px solid var(--border-color);
    }
    
    .tailadmin-card-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* ============================================
       MÉTRICAS / STATS CARDS
    ============================================ */
    .stat-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: var(--shadow);
        transition: var(--transition);
        position: relative;
        overflow: hidden;
    }
    
    .stat-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
    }
    
    .stat-card:hover {
        box-shadow: var(--shadow-lg);
        transform: translateY(-4px);
    }
    
    .stat-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        margin-bottom: 1rem;
    }
    
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 0.25rem;
    }
    
    .stat-label {
        font-size: 0.875rem;
        color: var(--text-secondary);
        font-weight: 500;
    }
    
    .stat-change {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        margin-top: 0.5rem;
    }
    
    .stat-change.positive {
        background: #DCFCE7;
        color: #059669;
    }
    
    .stat-change.negative {
        background: #FEE2E2;
        color: #DC2626;
    }

    /* ============================================
       INPUTS Y FORMULARIOS
    ============================================ */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {
        background: var(--white) !important;
        border: 1.5px solid var(--border-color) !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-size: 0.875rem !important;
        color: var(--text-primary) !important;
        transition: var(--transition) !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > select:focus,
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(60, 80, 224, 0.1) !important;
        outline: none !important;
    }
    
    /* Labels */
    .stTextInput > label,
    .stTextArea > label,
    .stSelectbox > label,
    .stNumberInput > label,
    .stDateInput > label {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        margin-bottom: 0.5rem !important;
    }

    /* ============================================
       BOTONES
    ============================================ */
    .stButton > button {
        background: var(--primary) !important;
        color: var(--white) !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        transition: var(--transition) !important;
        box-shadow: var(--shadow) !important;
    }
    
    .stButton > button:hover {
        background: var(--primary-dark) !important;
        transform: translateY(-1px);
        box-shadow: var(--shadow-md) !important;
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* Botones secundarios */
    .stButton[data-baseweb="button"][kind="secondary"] > button {
        background: var(--white) !important;
        color: var(--primary) !important;
        border: 1.5px solid var(--primary) !important;
    }
    
    .stButton[data-baseweb="button"][kind="secondary"] > button:hover {
        background: var(--gray-50) !important;
    }

    /* ============================================
       ALERTAS Y NOTIFICACIONES
    ============================================ */
    .stAlert {
        border-radius: 8px !important;
        border-left: 4px solid !important;
        padding: 1rem !important;
        margin: 1rem 0 !important;
    }
    
    /* Success */
    div[data-baseweb="notification"][kind="success"],
    .stSuccess {
        background: #ECFDF5 !important;
        border-left-color: var(--success) !important;
        color: #065F46 !important;
    }
    
    /* Error */
    div[data-baseweb="notification"][kind="error"],
    .stError {
        background: #FEF2F2 !important;
        border-left-color: var(--danger) !important;
        color: #991B1B !important;
    }
    
    /* Warning */
    div[data-baseweb="notification"][kind="warning"],
    .stWarning {
        background: #FFFBEB !important;
        border-left-color: var(--warning) !important;
        color: #92400E !important;
    }
    
    /* Info */
    div[data-baseweb="notification"][kind="info"],
    .stInfo {
        background: #EFF6FF !important;
        border-left-color: var(--info) !important;
        color: #1E40AF !important;
    }

    /* ============================================
       TABLAS
    ============================================ */
    [data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: var(--shadow);
    }
    
    [data-testid="stDataFrame"] table {
        border: 1px solid var(--border-color) !important;
    }
    
    [data-testid="stDataFrame"] thead th {
        background: var(--gray-50) !important;
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        padding: 1rem !important;
        border-bottom: 2px solid var(--border-color) !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    [data-testid="stDataFrame"] tbody td {
        padding: 0.875rem 1rem !important;
        color: var(--text-secondary) !important;
        font-size: 0.875rem !important;
        border-bottom: 1px solid var(--border-color) !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:hover {
        background: var(--gray-50) !important;
    }

    /* ============================================
       TABS
    ============================================ */
    [data-testid="stTabs"] {
        background: var(--bg-card);
        border-radius: 8px;
        padding: 0.5rem;
        border: 1px solid var(--border-color);
    }
    
    [data-testid="stTabs"] button {
        background: transparent !important;
        color: var(--text-secondary) !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        transition: var(--transition) !important;
    }
    
    [data-testid="stTabs"] button:hover {
        background: var(--gray-50) !important;
        color: var(--text-primary) !important;
    }
    
    [data-testid="stTabs"] button[aria-selected="true"] {
        background: var(--primary) !important;
        color: var(--white) !important;
        font-weight: 600 !important;
    }

    /* ============================================
       BREADCRUMB
    ============================================ */
    .breadcrumb {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem 1rem;
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        font-size: 0.875rem;
        margin-bottom: 1.5rem;
    }
    
    .breadcrumb-item {
        color: var(--text-secondary);
    }
    
    .breadcrumb-item.active {
        color: var(--primary);
        font-weight: 600;
    }
    
    .breadcrumb-separator {
        color: var(--text-tertiary);
    }

    /* ============================================
       BADGES
    ============================================ */
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.25rem 0.75rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        line-height: 1;
    }
    
    .badge-primary {
        background: #DBEAFE;
        color: #1E40AF;
    }
    
    .badge-success {
        background: #DCFCE7;
        color: #059669;
    }
    
    .badge-warning {
        background: #FEF3C7;
        color: #B45309;
    }
    
    .badge-danger {
        background: #FEE2E2;
        color: #DC2626;
    }
    
    .badge-info {
        background: #E0E7FF;
        color: #4F46E5;
    }

    /* ============================================
       PROGRESS BAR
    ============================================ */
    .progress-container {
        width: 100%;
        height: 8px;
        background: var(--gray-200);
        border-radius: 999px;
        overflow: hidden;
    }
    
    .progress-bar {
        height: 100%;
        background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
        border-radius: 999px;
        transition: width 0.3s ease;
    }

    /* ============================================
       HEADER WELCOME
    ============================================ */
    .welcome-header {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: var(--shadow);
    }
    
    .welcome-content {
        display: flex;
        align-items: center;
        gap: 1.5rem;
    }
    
    .welcome-avatar {
        width: 72px;
        height: 72px;
        border-radius: 12px;
        background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--white);
        font-size: 2rem;
        font-weight: 700;
        box-shadow: var(--shadow-md);
    }
    
    .welcome-text h1 {
        margin: 0 0 0.5rem 0 !important;
        font-size: 1.75rem !important;
    }
    
    .welcome-text p {
        margin: 0;
        color: var(--text-secondary);
        font-size: 0.875rem;
    }

    /* ============================================
       LOGIN FORM
    ============================================ */
    form[data-testid="form"] {
        max-width: 400px;
        margin: 0 auto;
    }
    
    form[data-testid="form"] .stTextInput > div > div > input {
        background: var(--white) !important;
        border: 1.5px solid var(--border-color) !important;
    }
    
    form[data-testid="form"] .stButton > button {
        width: 100%;
        padding: 1rem !important;
        font-size: 1rem !important;
    }

    /* ============================================
       RESPONSIVE
    ============================================ */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem !important;
        }
        
        .stat-card {
            padding: 1rem;
        }
        
        .welcome-header {
            padding: 1.5rem;
        }
        
        .welcome-avatar {
            width: 56px;
            height: 56px;
            font-size: 1.5rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# COMPONENTES TAILADMIN AVANZADOS
# =============================================================================
class TailAdminComponents:
    """Componentes TailAdmin Light Theme Avanzados"""
    
    @staticmethod
    def stat_card(title: str, value: str, icon: str = "📊", change: str = None, 
                  change_type: str = "positive", color: str = "primary"):
        """Tarjeta de estadística avanzada con cambio porcentual"""
        
        color_map = {
            "primary": {"bg": "#EFF6FF", "icon_bg": "#DBEAFE", "icon_color": "#1E40AF"},
            "success": {"bg": "#ECFDF5", "icon_bg": "#D1FAE5", "icon_color": "#059669"},
            "warning": {"bg": "#FFFBEB", "icon_bg": "#FEF3C7", "icon_color": "#D97706"},
            "danger": {"bg": "#FEF2F2", "icon_bg": "#FEE2E2", "icon_color": "#DC2626"}
        }
        
        colors = color_map.get(color, color_map["primary"])
        
        change_html = ""
        if change:
            arrow = "↑" if change_type == "positive" else "↓"
            change_html = f"""
            <div class="stat-change {change_type}">
                <span>{arrow}</span>
                <span>{change}</span>
            </div>
            """
        
        st.markdown(f"""
        <div class="stat-card">
            <div style="background: {colors['bg']}; padding: 0.75rem; border-radius: 8px; width: fit-content; margin-bottom: 1rem;">
                <div class="stat-icon" style="background: {colors['icon_bg']}; color: {colors['icon_color']}; width: 40px; height: 40px; margin: 0;">
                    {icon}
                </div>
            </div>
            <div class="stat-value">{value}</div>
            <div class="stat-label">{title}</div>
            {change_html}
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def info_card(title: str, content: str, icon: str = "ℹ️"):
        """Card informativa"""
        st.markdown(f"""
        <div class="tailadmin-card">
            <div class="tailadmin-card-header">
                <div class="tailadmin-card-title">
                    <span style="font-size: 1.5rem;">{icon}</span>
                    <span>{title}</span>
                </div>
            </div>
            <div style="color: var(--text-secondary); line-height: 1.8;">
                {content}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def breadcrumb(items):
        """Breadcrumb de navegación"""
        breadcrumb_html = []
        for i, item in enumerate(items):
            if i == len(items) - 1:
                breadcrumb_html.append(f'<span class="breadcrumb-item active">{item}</span>')
            else:
                breadcrumb_html.append(f'<span class="breadcrumb-item">{item}</span>')
                breadcrumb_html.append('<span class="breadcrumb-separator">/</span>')
        
        st.markdown(f"""
        <div class="breadcrumb">
            <span style="font-size: 1.125rem;">🏠</span>
            {''.join(breadcrumb_html)}
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def welcome_header(user_name: str, company: str = "FUNDAE", subtitle: str = None):
        """Header de bienvenida"""
        if subtitle is None:
            subtitle = datetime.now().strftime('%A, %d de %B %Y')
        
        st.markdown(f"""
        <div class="welcome-header">
            <div class="welcome-content">
                <div class="welcome-avatar">
                    {user_name[0].upper() if user_name else "U"}
                </div>
                <div class="welcome-text">
                    <h1>¡Bienvenido, {user_name}!</h1>
                    <p>{company} • {subtitle}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def badge(text: str, type: str = "primary"):
        """Badge/etiqueta"""
        return f'<span class="badge badge-{type}">{text}</span>'
    
    @staticmethod
    def progress_bar(value: int, max_value: int = 100):
        """Barra de progreso"""
        percentage = (value / max_value) * 100
        st.markdown(f"""
        <div class="progress-container">
            <div class="progress-bar" style="width: {percentage}%;"></div>
        </div>
        <div style="margin-top: 0.5rem; font-size: 0.75rem; color: var(--text-secondary);">
            {value} / {max_value} ({percentage:.1f}%)
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
    "page": "home",
    "rol": None,
    "role": None,
    "user": {},
    "auth_session": None,
    "authenticated": False
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================
@st.cache_data(ttl=300)
def get_metricas_admin():
    """Obtiene métricas del administrador"""
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
    """Obtiene rol de usuario desde BD"""
    try:
        clean_email = email.strip().lower()
        res = supabase_public.table("usuarios").select("*").eq("email", clean_email).limit(1).execute()
        if res.data:
            row = res.data[0]
            rol = row.get("rol") or "alumno"
            
            st.session_state.rol = rol
            st.session_state.role = rol
            
            st.session_state.user = {
                "id": row.get("id"),
                "auth_id": row.get("auth_id"),
                "email": row.get("email"),
                "nombre": row.get("nombre"),
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
        st.session_state.user = {"email": email, "empresa_id": None}

def do_logout():
    """Cierra sesión y limpia estado"""
    try:
        supabase_public.auth.sign_out()
    except Exception:
        pass
    
    st.cache_data.clear()
    st.session_state.clear()
    
    st.session_state.authenticated = False
    st.session_state.rol = None
    st.session_state.role = None
    st.session_state.user = {}
    st.session_state.page = "home"
    st.session_state.auth_session = None
    
    st.rerun()

# =============================================================================
# LOGIN LIGHT THEME
# =============================================================================
def login_view_light():
    """Vista de login con tema claro"""
    
    logo_datafor = "https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/datafor-logo.png"

    # Fondo gradiente suave
    st.markdown("""
    <div style="
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        z-index: -1;
    "></div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height: 2vh;"></div>', unsafe_allow_html=True)

    # Logo centrado
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 2rem;">
        <img src="{logo_datafor}" style="
            width: 180px;
            height: auto;
            background: white;
            padding: 20px;
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
        " alt="DataFor Logo">
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<h3 style='text-align: center; color: white; margin-bottom: 1.5rem;'>🔐 Iniciar Sesión</h3>", unsafe_allow_html=True)
    
    with st.form("form_login", clear_on_submit=False):
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

    # Footer
    st.markdown("""
    <div style="
        margin-top: 3rem;
        padding: 1.5rem;
        text-align: center;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        backdrop-filter: blur(10px);
    ">
        <p style="color: white; font-size: 0.875rem; margin: 0; font-weight: 500;">
            © 2025 DataFor Solutions - Gestor Formación SaaS
        </p>
        <p style="color: rgba(255,255,255,0.8); font-size: 0.75rem; margin: 0.25rem 0 0;">
            Versión 2.2.0 Light Theme
        </p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# DASHBOARDS POR ROL
# =============================================================================
def mostrar_dashboard_admin(ajustes, metricas):
    """Dashboard administrador Light Theme"""
    components = TailAdminComponents()
    
    user_name = st.session_state.user.get("nombre", "Administrador")
    components.welcome_header(user_name, "Sistema FUNDAE")
    components.breadcrumb(["Dashboard", "Panel de Administración"])
    
    st.markdown("## 📊 Panel de Control")
    
    # Métricas en cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        components.stat_card(
            "Total Empresas", 
            str(metricas['empresas']), 
            "🏢",
            change="+12%",
            change_type="positive",
            color="primary"
        )
    
    with col2:
        components.stat_card(
            "Usuarios Activos",
            str(metricas['usuarios']),
            "👥",
            change="+8%",
            change_type="positive",
            color="success"
        )
    
    with col3:
        components.stat_card(
            "Cursos Disponibles",
            str(metricas['cursos']),
            "📚",
            change="+5%",
            change_type="positive",
            color="warning"
        )
    
    with col4:
        components.stat_card(
            "Grupos Activos",
            str(metricas['grupos']),
            "👨‍🎓",
            change="-3%",
            change_type="negative",
            color="danger"
        )
    
    # Información adicional
    st.markdown("---")
    st.markdown("### 📈 Información del Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        components.info_card(
            "Estado del Sistema",
            """
            ✅ Todos los servicios funcionando correctamente<br>
            🔄 Última sincronización: """ + datetime.now().strftime('%H:%M') + """<br>
            💾 Base de datos: Operativa<br>
            🌐 Conectividad: Excelente
            """,
            "⚙️"
        )
    
    with col2:
        components.info_card(
            "Estadísticas Generales",
            f"""
            📊 Total entidades: {sum(metricas.values())}<br>
            📅 Última actualización: Hoy<br>
            👤 Sesiones activas: En tiempo real<br>
            🔐 Seguridad: Activa
            """,
            "📋"
        )

def mostrar_dashboard_gestor(ajustes, metricas):
    """Dashboard gestor Light Theme"""
    components = TailAdminComponents()
    
    user_name = st.session_state.user.get("nombre", "Gestor")
    components.welcome_header(user_name, "Gestión de Formación")
    components.breadcrumb(["Dashboard", "Panel del Gestor"])
    
    st.markdown("## 🎓 Panel de Gestión")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        components.stat_card(
            "Mis Grupos",
            str(metricas.get('grupos', 0)),
            "👨‍🎓",
            color="primary"
        )
    
    with col2:
        components.stat_card(
            "Participantes",
            str(metricas.get('participantes', 0)),
            "🧑‍🎓",
            color="success"
        )
    
    with col3:
        components.stat_card(
            "Documentos",
            str(metricas.get('documentos', 0)),
            "📂",
            color="warning"
        )

def mostrar_dashboard_alumno(ajustes):
    """Dashboard alumno Light Theme"""
    components = TailAdminComponents()
    
    user_name = st.session_state.user.get("nombre", "Alumno")
    components.welcome_header(user_name, "Área del Estudiante")
    components.breadcrumb(["Dashboard", "Área del Alumno"])
    
    st.markdown("## 📘 Mi Área de Formación")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="tailadmin-card" style="text-align: center; padding: 2.5rem;">
            <div style="font-size: 3.5rem; margin-bottom: 1rem;">📘</div>
            <h3 style="color: var(--text-primary); margin: 0 0 0.5rem 0;">Mis Grupos</h3>
            <p style="color: var(--text-secondary); margin: 0 0 1.5rem 0;">Consulta tus grupos formativos activos</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Ver Mis Grupos", key="btn_grupos", use_container_width=True):
            st.session_state.page = "area_alumno"
            st.rerun()
    
    with col2:
        st.markdown("""
        <div class="tailadmin-card" style="text-align: center; padding: 2.5rem;">
            <div style="font-size: 3.5rem; margin-bottom: 1rem;">🎓</div>
            <h3 style="color: var(--text-primary); margin: 0 0 0.5rem 0;">Mis Certificados</h3>
            <p style="color: var(--text-secondary); margin: 0 0 1.5rem 0;">Descarga tus diplomas acreditativos</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Ver Certificados", key="btn_cert", use_container_width=True):
            st.info("Funcionalidad en desarrollo")

# =============================================================================
# SIDEBAR LIGHT THEME
# =============================================================================
def render_sidebar_light():
    """Sidebar con tema claro"""
    
    rol = st.session_state.get("rol")
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")
    
    logo_datafor = "https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/datafor-logo.png"

    # Header sidebar
    st.sidebar.markdown(f"""
    <div style="
        padding: 1.5rem;
        border-bottom: 1px solid var(--border-color);
        text-align: center;
        background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
    ">
        <div style="
            width: 60px;
            height: 60px;
            margin: 0 auto 1rem;
            border-radius: 12px;
            overflow: hidden;
            background: white;
            padding: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        ">
            <img src="{logo_datafor}" style="width: 100%; height: 100%; object-fit: contain;" alt="DataFor">
        </div>
        <p style="margin: 0; font-weight: 600; color: var(--text-primary); font-size: 0.9rem;">{nombre_usuario}</p>
        <p style="margin: 0.25rem 0 0; font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em;">
            {rol.title() if rol else 'Usuario'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Menú por roles
    if rol == "admin":
        st.sidebar.markdown("#### ⚙️ Administración")
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
        
    elif rol == "gestor":
        st.sidebar.markdown("#### 🎓 Gestión")
        menu = {
            "📊 Dashboard": "panel_gestor",
            "🏢 Empresas": "empresas",
            "📚 Acciones Formativas": "acciones_formativas",
            "👨‍🎓 Grupos": "grupos",
            "🧑‍🎓 Participantes": "participantes",
            "👩‍🏫 Tutores": "tutores",
            "🏫 Aulas": "aulas",
            "📅 Gestión Clases": "gestion_clases",
            "📂 Documentos": "documentos"
        }
        for label, page_key in menu.items():
            if st.sidebar.button(label, use_container_width=True, key=f"nav_{page_key}"):
                st.session_state.page = page_key
                st.rerun()
        
    elif rol == "alumno":
        st.sidebar.markdown("#### 🎓 Mi Área")
        if st.sidebar.button("📘 Mis Grupos", use_container_width=True, key="nav_area_alumno"):
            st.session_state.page = "area_alumno"
            st.rerun()
    
    # Logout
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True, key="logout"):
        do_logout()

    # Info
    st.sidebar.markdown("---")
    st.sidebar.markdown("**DataFor** Gestor Formación")
    st.sidebar.markdown("*v2.2.0 Light Theme*")

# =============================================================================
# NAVEGACIÓN
# =============================================================================
def render_page():
    """Renderiza páginas"""
    page = st.session_state.get("page", "home")

    if page and page != "home":
        try:
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
                "documentos": "documentos",
                "area_alumno": "area_alumno"
            }

            if page in page_map:
                view_module = __import__(f"views.{page_map[page]}", fromlist=["render"])
                view_module.render(supabase_admin, st.session_state)
            else:
                st.error(f"❌ Página '{page}' no encontrada")

        except Exception as e:
            st.error(f"❌ Error: {e}")
            if st.button("🔄 Reintentar"):
                st.rerun()

# =============================================================================
# MAIN
# =============================================================================
def main():
    """Función principal"""
    
    hide_streamlit_elements()
    load_tailadmin_light_css()
    
    usuario_autenticado = st.session_state.get("authenticated", False)
    
    if not usuario_autenticado:
        login_view_light()
    else:
        render_sidebar_light()

        page = st.session_state.get("page", "home")

        if page and page != "home":
            render_page()
        else:
            rol = st.session_state.get("rol")
            ajustes = get_ajustes_app(
                supabase_admin if supabase_admin else supabase_public,
                campos=["bienvenida_admin", "bienvenida_gestor", "bienvenida_alumno"]
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

if __name__ == "__main__":
    main()
