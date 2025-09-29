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
# CONFIGURACIÓN DE PÁGINA + TAILADMIN INTEGRATION
# =============================================================================
st.set_page_config(
    page_title="Sistema FUNDAE - TailAdmin",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🎓",
    menu_items=None
)

# =============================================================================
# CSS TAILADMIN COMPLETO - REEMPLAZA TU CSS ACTUAL
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

    /* === BOTONES SIDEBAR === */
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
        font-weight: 500 !important;
        width: 100% !important;
        text-align: left !important;
        transition: all 0.3s ease !important;
        margin-bottom: 0.25rem !important;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(60, 80, 224, 0.2) !important;
        border-color: var(--tailadmin-primary) !important;
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
        margin-top: 1rem !important;
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

    .tailadmin-metric-icon {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        opacity: 0.8;
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

    /* === LOGIN TAILADMIN === */
    .login-container {
        max-width: 420px;
        margin: 5rem auto;
        padding: 2.5rem;
        background: white;
        border-radius: 16px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        border: 1px solid var(--tailadmin-border);
    }

    .login-logo {
        width: 80px;
        height: 80px;
        background: linear-gradient(135deg, var(--tailadmin-primary) 0%, #6366f1 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 2rem;
        font-weight: bold;
        margin: 0 auto 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(60, 80, 224, 0.3);
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
        
        .tailadmin-metric {
            padding: 1rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# COMPONENTES TAILADMIN PARA FUNDAE
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
    def info_card(title: str, content: str, icon: str = "ℹ️"):
        """Tarjeta informativa"""
        st.markdown(f"""
        <div class="tailadmin-card">
            <div style="display: flex; align-items: flex-start; gap: 1rem;">
                <span style="font-size: 1.5rem;">{icon}</span>
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 0.5rem; color: #1c2434; font-weight: 600;">{title}</h4>
                    <p style="margin: 0; color: #64748b; line-height: 1.5;">{content}</p>
                </div>
            </div>
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
# CONEXIÓN SUPABASE (MANTIENE TU CONFIGURACIÓN)
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
# ESTADO INICIAL (MANTIENE TU LÓGICA)
# =============================================================================
for key, default in {
    "page": "home",
    "rol": None,
    "user": {},
    "auth_session": None,
    "login_loading": False
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =============================================================================
# FUNCIONES AUXILIARES (MANTIENE TUS FUNCIONES + MEJORAS TAILADMIN)
# =============================================================================
@st.cache_data(ttl=300)
def get_metricas_admin():
    """Obtiene métricas con manejo de errores mejorado"""
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
        st.error(f"Error obteniendo métricas admin: {e}")
        return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}

@st.cache_data(ttl=300)
def get_metricas_gestor(empresa_id):
    """Obtiene métricas del gestor con manejo de errores"""
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
        st.error(f"Error obteniendo métricas gestor: {e}")
        return {"grupos": 0, "participantes": 0, "documentos": 0}

def set_user_role_from_db(email: str):
    """Obtiene rol de usuario (mantiene tu lógica)"""
    try:
        clean_email = email.strip().lower()
        res = supabase_public.table("usuarios").select("*").eq("email", clean_email).limit(1).execute()
        if res.data:
            row = res.data[0]
            rol = row.get("rol") or "alumno"
            st.session_state.rol = rol
            st.session_state.user = {
                "id": row.get("id"),
                "auth_id": row.get("auth_id"),
                "email": row.get("email"),
                "nombre": row.get("nombre"),
                "empresa_id": row.get("empresa_id")
            }
        else:
            st.session_state.rol = "alumno"
            st.session_state.user = {"email": clean_email, "empresa_id": None}
    except Exception as e:
        st.error(f"Error obteniendo rol: {e}")
        st.session_state.rol = "alumno"
        st.session_state.user = {"email": email, "empresa_id": None}

def do_logout():
    """Logout con limpieza completa"""
    try:
        supabase_public.auth.sign_out()
    except Exception:
        pass
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

# =============================================================================
# LOGIN TAILADMIN (REEMPLAZA TU LOGIN_VIEW)
# =============================================================================
def login_view_tailadmin():
    """Login con diseño TailAdmin completo"""
    
    # Obtener ajustes (mantiene tu lógica)
    ajustes = get_ajustes_app(supabase_public, campos=["mensaje_login", "nombre_app", "logo_url"])
    mensaje_login = ajustes.get("mensaje_login", "Sistema integral de gestión FUNDAE")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    logo_url = ajustes.get("logo_url", "")

    # Fondo de pantalla de login
    st.markdown("""
    <div style="
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        z-index: -1;
    "></div>
    """, unsafe_allow_html=True)

    # Logo dinámico
    logo_display = (
        f'<img src="{logo_url}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;">'
        if logo_url else "🎓"
    )

    # Formulario de login TailAdmin
    st.markdown(f"""
    <div class="login-container">
        <div style="text-align: center; margin-bottom: 2rem;">
            <div class="login-logo">{logo_display}</div>
            <h1 style="margin: 0; color: #1c2434; font-size: 1.75rem; font-weight: 700;">{nombre_app}</h1>
            <p style="margin: 0.5rem 0 0; color: #64748b; font-size: 0.95rem;">{mensaje_login}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Formulario (mantiene tu lógica)
    with st.form("form_login", clear_on_submit=False):
        st.markdown("#### 🔐 Iniciar Sesión")
        
        email = st.text_input(
            "📧 Email", 
            placeholder="usuario@empresa.com",
            help="Introduce tu email corporativo"
        )
        
        password = st.text_input(
            "🔑 Contraseña", 
            type="password",
            placeholder="••••••••",
            help="Tu contraseña segura"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            remember_me = st.checkbox("Recordarme")
        with col2:
            st.markdown("""
            <div style="text-align: right;">
                <a href="#" style="color: #3c50e0; text-decoration: none; font-size: 0.875rem;">
                    ¿Olvidaste tu contraseña?
                </a>
            </div>
            """, unsafe_allow_html=True)
        
        submitted = st.form_submit_button(
            "🚀 Iniciar Sesión",
            disabled=st.session_state.get("login_loading", False),
            use_container_width=True
        )

    # Lógica de autenticación (mantiene tu lógica)
    if submitted:
        if not email or not password:
            st.warning("⚠️ Por favor, completa todos los campos")
        else:
            st.session_state.login_loading = True
            try:
                auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
                if not auth or not auth.user:
                    st.error("❌ Credenciales incorrectas")
                    st.session_state.login_loading = False
                else:
                    st.session_state.auth_session = auth
                    set_user_role_from_db(auth.user.email)
                    st.success("✅ Sesión iniciada correctamente")
                    time.sleep(0.5)
                    st.session_state.login_loading = False
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error al iniciar sesión: {e}")
                st.session_state.login_loading = False

    # Pie del formulario
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid #e2e8f0;">
        <p style="color: #64748b; font-size: 0.875rem; margin: 0;">
            ¿No tienes cuenta? 
            <a href="#" style="color: #3c50e0; text-decoration: none;">Contacta con tu administrador</a>
        </p>
        <p style="color: #9ca3af; font-size: 0.75rem; margin: 0.5rem 0 0;">
            © 2025 Sistema FUNDAE. Todos los derechos reservados.
        </p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# DASHBOARDS TAILADMIN (REEMPLAZA TUS DASHBOARDS ACTUALES)  
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
