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

    /* === SIDEBAR TAILADMIN OSCURO === */
    section[data-testid="stSidebar"] {
        background: var(--tailadmin-sidebar) !important;
        border-right: 1px solid #334155 !important;
        padding-top: 0 !important;
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

    /* === BOTONES SIDEBAR MEJORADOS === */
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        color: #f1f5f9 !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-weight: 500 !important;
        width: 100% !important;
        text-align: left !important;
        transition: all 0.3s ease !important;
        margin-bottom: 0.25rem !important;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(60, 80, 224, 0.3) !important;
        border-color: var(--tailadmin-primary) !important;
        color: white !important;
        transform: translateX(4px);
        box-shadow: 0 4px 6px -1px rgba(60, 80, 224, 0.3);
    }

    section[data-testid="stSidebar"] .stButton > button:active,
    section[data-testid="stSidebar"] .stButton > button:focus {
        background: rgba(60, 80, 224, 0.2) !important;
        color: white !important;
        border-color: var(--tailadmin-primary) !important;
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

    /* === LOGIN TAILADMIN SIMPLIFICADO === */
    .login-container {
        max-width: 380px;
        margin: 2rem auto;
        padding: 2rem;
        background: white;
        border-radius: 16px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        border: 1px solid var(--tailadmin-border);
    }

    .login-logo {
        width: 64px;
        height: 64px;
        background: linear-gradient(135deg, var(--tailadmin-primary) 0%, #6366f1 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 1.5rem;
        font-weight: bold;
        margin: 0 auto 1rem;
        box-shadow: 0 4px 6px -1px rgba(60, 80, 224, 0.3);
    }

    /* === INPUTS LOGIN COMPACTOS === */
    .login-container .stTextInput > div > div > input {
        max-width: 280px !important;
        margin: 0 auto !important;
        background: #f8fafc !important;
        border: 1.5px solid var(--tailadmin-border) !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-size: 0.9rem !important;
    }

    .login-container .stTextInput > div > div > input:focus {
        border-color: var(--tailadmin-primary) !important;
        box-shadow: 0 0 0 3px rgba(60, 80, 224, 0.1) !important;
    }

    /* === BOTÓN LOGIN === */
    .login-container .stButton > button {
        max-width: 280px !important;
        margin: 1rem auto !important;
        display: block !important;
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

    /* === RESPONSIVE === */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem !important;
        }
        
        .tailadmin-card {
            padding: 1rem !important;
        }
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
# ESTADO INICIAL - CORREGIDO PARA EVITAR ERRORES
# =============================================================================
for key, default in {
    "page": "home",
    "rol": None,
    "role": None,  # ← AÑADIDO: Para compatibilidad con archivos que usan 'role'
    "user": {},
    "auth_session": None,
    "login_loading": False
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
    """Login simplificado y centrado - sin scroll"""
    
    # Obtener ajustes
    ajustes = get_ajustes_app(supabase_public, campos=["mensaje_login", "nombre_app", "logo_url"])
    mensaje_login = ajustes.get("mensaje_login", "Sistema integral de gestión FUNDAE")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    logo_url = ajustes.get("logo_url", "")

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

    # Logo dinámico
    logo_display = (
        f'<img src="{logo_url}" style="width:64px;height:64px;border-radius:50%;object-fit:cover;">'
        if logo_url else "🎓"
    )

    # Container del login compacto
    st.markdown(f"""
    <div class="login-container">
        <div style="text-align: center; margin-bottom: 1.5rem;">
            <div class="login-logo">{logo_display}</div>
            <h1 style="margin: 0; color: #1c2434; font-size: 1.5rem; font-weight: 700;">Gestor Formación SaaS</h1>
            <p style="margin: 0.5rem 0 0; color: #64748b; font-size: 0.9rem;">{mensaje_login}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Formulario de login simplificado
    with st.form("form_login", clear_on_submit=False):
        st.markdown("#### 🔐 Iniciar Sesión")
        
        email = st.text_input(
            "📧 Email", 
            placeholder="usuario@empresa.com"
        )
        
        password = st.text_input(
            "🔑 Contraseña", 
            type="password",
            placeholder="••••••••"
        )
        
        # Solo botón de login - funcionalidades pendientes removidas
        submitted = st.form_submit_button(
            "🚀 Iniciar Sesión",
            disabled=st.session_state.get("login_loading", False),
            use_container_width=True
        )

    # Lógica de autenticación (sin cambios)
    if submitted:
        if not email or not password:
            st.warning("⚠️ Por favor, completa todos los campos")
        else:
            st.session_state.login_loading = True
            
            with st.spinner("🔄 Verificando credenciales..."):
                try:
                    auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
                    if not auth or not auth.user:
                        st.error("❌ Credenciales incorrectas")
                        st.session_state.login_loading = False
                    else:
                        st.session_state.auth_session = auth
                        set_user_role_from_db(auth.user.email)
                        st.success("✅ Sesión iniciada correctamente")
                        time.sleep(1)
                        st.session_state.login_loading = False
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al iniciar sesión: {e}")
                    st.session_state.login_loading = False

    # Pie simplificado
    st.markdown("""
    <div style="text-align: center; margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;">
        <p style="color: #9ca3af; font-size: 0.75rem; margin: 0;">
            © 2025 Gestor Formación SaaS
        </p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# DASHBOARDS TAILADMIN POR ROL
# =============================================================================
def mostrar_dashboard_admin_tailadmin(ajustes, metricas):
    """Dashboard admin con diseño TailAdmin"""
    components = TailAdminComponents()
    
    # Header de bienvenida
    user_name = st.session_state.user.get("nombre", "Administrador")
    components.header_welcome(user_name, "Sistema FUNDAE")
    
    # Breadcrumb
    components.breadcrumb(["Dashboard", "Panel de Administración"])
    
    # Título principal
    st.markdown(f"## {ajustes.get('bienvenida_admin', 'Panel de Administración')}")
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        components.metric_card("Empresas", str(metricas['empresas']), "🏢", "primary")
    
    with col2:
        components.metric_card("Usuarios", str(metricas['usuarios']), "👥", "success")
    
    with col3:
        components.metric_card("Cursos", str(metricas['cursos']), "📚", "warning")
    
    with col4:
        components.metric_card("Grupos", str(metricas['grupos']), "👨‍🎓", "danger")
    
    # Sección de gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="tailadmin-card">', unsafe_allow_html=True)
        st.subheader("📈 Evolución Mensual")
        
        # Gráfico de ejemplo con datos simulados
        dates = pd.date_range(start='2024-01-01', periods=12, freq='M')
        usuarios_data = [50, 65, 80, 95, 110, 125, 140, 155, 170, 185, 200, 215]
        
        fig = px.line(
            x=dates, y=usuarios_data,
            title="Usuarios Registrados por Mes",
            color_discrete_sequence=['#3c50e0']
        )
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#64748b'),
            showlegend=False,
            margin=dict(t=40, b=40, l=40, r=40)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="tailadmin-card">', unsafe_allow_html=True)
        st.subheader("📊 Distribución por Roles")
        
        # Gráfico de donut
        labels = ['Administradores', 'Gestores', 'Alumnos', 'Comerciales']
        values = [5, 25, 60, 10]
        colors = ['#3c50e0', '#10b981', '#fbbf24', '#f87171']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.6,
            marker_colors=colors
        )])
        fig.update_layout(
            showlegend=True,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#64748b'),
            margin=dict(t=40, b=40, l=40, r=40)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

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
    """Sidebar con navegación estilo TailAdmin"""
    
    rol = st.session_state.get("rol")
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")
    
    # Header del sidebar con avatar
    st.sidebar.markdown(f"""
    <div style="
        padding: 1.5rem; 
        border-bottom: 1px solid #334155; 
        margin-bottom: 1.5rem;
        text-align: center;
    ">
        <div style="
            width: 48px; height: 48px; 
            background: linear-gradient(135deg, #3c50e0 0%, #6366f1 100%);
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 1.25rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 4px 6px -1px rgba(60, 80, 224, 0.3);
        ">
            {nombre_usuario[0].upper()}
        </div>
        <p style="margin: 0; font-weight: 600; color: #f1f5f9; font-size: 0.9rem;">{nombre_usuario}</p>
        <p style="margin: 0.25rem 0 0; font-size: 0.75rem; color: #94a3b8; text-transform: uppercase;">
            {rol.title() if rol else 'Usuario'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Botón logout
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True, help="Cerrar sesión"):
        do_logout()

    st.sidebar.markdown("---")

    # Menú por roles
    if rol == "admin":
        st.sidebar.markdown("#### ⚙️ Administración SaaS")
        menu = {
            "📊 Panel Admin": "panel_admin",
            "👥 Usuarios": "usuarios_empresas", 
            "🏢 Empresas": "empresas",
            "⚙️ Ajustes": "ajustes_app"
        }
        
    elif rol == "gestor":
        st.sidebar.markdown("#### 🎓 Gestión de Formación")
        menu = {
            "📊 Panel Gestor": "panel_gestor",
            "🏢 Empresas": "empresas",
            "📚 Acciones Formativas": "acciones_formativas",
            "👨‍🎓 Grupos": "grupos",
            "🧑‍🎓 Participantes": "participantes", 
            "👩‍🏫 Tutores": "tutores",
            "🏫 Aulas": "aulas",
            "📅 Gestión Clases": "gestion_clases",
            "📂 Documentos": "documentos"
        }
        
    elif rol == "alumno":
        st.sidebar.markdown("#### 🎓 Área Estudiante")
        menu = {
            "📘 Mis Grupos": "area_alumno"
        }
        
    elif rol == "comercial":
        st.sidebar.markdown("#### 💼 CRM Comercial")
        menu = {
            "📊 Panel CRM": "crm_panel",
            "👥 Clientes": "crm_clientes", 
            "💡 Oportunidades": "crm_oportunidades",
            "📝 Tareas": "crm_tareas"
        }
    else:
        menu = {}

    # Renderizar menú
    for label, page_key in menu.items():
        if st.sidebar.button(label, use_container_width=True, key=f"nav_{page_key}"):
            st.session_state.page = page_key
            st.rerun()

    # Info adicional (sin CSS visible)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Sistema**: Gestor Formación SaaS")
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
    
    # 1. Cargar estilos y ocultar elementos
    hide_streamlit_elements()
    load_tailadmin_css()
    
    # 2. Verificar autenticación
    if not st.session_state.get("rol"):
        # ============= MODO LOGIN =============
        login_view_tailadmin()
        
    else:
        # ============= MODO APLICACIÓN =============
        
        try:
            # Header y footer (opcional)
            render_header()
            render_footer()

            # Sidebar TailAdmin
            render_sidebar_tailadmin()

            # Contenido principal
            page = st.session_state.get("page", "home")

            if page and page != "home":
                render_page()
            else:
                # ============= DASHBOARDS DE BIENVENIDA =============
                rol = st.session_state.rol
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
            st.exception(e)
            
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
