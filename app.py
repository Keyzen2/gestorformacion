import os
import sys
import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import time

from utils import get_ajustes_app

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# =========================
# Configuración de la página
# =========================
st.set_page_config(
    page_title="Gestor de Formación",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📚",
    menu_items=None
)

# =========================
# CSS GLOBAL - ESTILO TAILADMIN
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Reset */
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Ocultar menús nativos Streamlit */
#MainMenu, footer, .stDeployButton, header[data-testid="stHeader"],
button[kind="header"], [data-testid="stToolbar"] {
    display: none !important;
}

/* Sidebar fijo tipo TailAdmin */
section[data-testid="stSidebar"] {
    background: #1f2937 !important; /* gris oscuro */
    padding-top: 2rem !important;
    min-width: 250px !important;
    max-width: 250px !important;
}
section[data-testid="stSidebar"] * { color: #e5e7eb !important; }
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    text-align: left !important;
    width: 100% !important;
    padding: 0.75rem 1rem !important;
    font-weight: 500 !important;
    font-size: 0.95rem !important;
    border-radius: 8px !important;
    display: flex !important;
    align-items: center !important;
    gap: 0.75rem !important;
    transition: background 0.2s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.1) !important;
}
section[data-testid="stSidebar"] h4 {
    font-size: 0.75rem !important;
    color: #9ca3af !important;
    text-transform: uppercase !important;
    margin: 1rem 1rem 0.5rem !important;
}

/* Main content */
.main .block-container {
    padding: 2rem !important;
    max-width: 1400px !important;
}

/* Cards TailAdmin */
.metric-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.5rem;
    transition: all 0.2s ease;
    text-align: center;
}
.metric-card:hover { border-color: #d1d5db; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.metric-icon {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
    color: #3b82f6;
}
.metric-value { font-size: 1.75rem; font-weight: 700; color: #111827; }
.metric-label { font-size: 0.875rem; color: #6b7280; }

/* Login box */
.login-container {
    background: white;
    border-radius: 16px;
    padding: 2.5rem;
    max-width: 420px;
    margin: 4rem auto;
    box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    text-align: center;
}
.login-logo {
    width: 64px; height: 64px;
    border-radius: 12px;
    background: #3b82f6;
    display: flex; align-items: center; justify-content: center;
    color: white; font-size: 1.5rem;
    margin: 0 auto 1.5rem;
}
</style>
""", unsafe_allow_html=True)

# =========================
# Claves Supabase
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("⚠️ Error: Variables de Supabase no configuradas correctamente")
    st.stop()

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else None

# =========================
# Estado inicial
# =========================
for key, default in {
    "page": "home",
    "rol": None,
    "user": {},
    "auth_session": None,
    "login_loading": False
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =========================
# Funciones auxiliares
# =========================
@st.cache_data(ttl=300)
def get_metricas_admin():
    try:
        total_empresas = supabase_admin.table("empresas").select("id", count="exact").execute().count
        total_usuarios = supabase_admin.table("usuarios").select("id", count="exact").execute().count
        total_cursos = supabase_admin.table("acciones_formativas").select("id", count="exact").execute().count
        total_grupos = supabase_admin.table("grupos").select("id", count="exact").execute().count
        return {"empresas": total_empresas, "usuarios": total_usuarios, "cursos": total_cursos, "grupos": total_grupos}
    except Exception:
        return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}

@st.cache_data(ttl=300)
def get_metricas_gestor(empresa_id):
    try:
        grupos_res = supabase_admin.table("grupos").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        participantes_res = supabase_admin.table("participantes").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        documentos_res = supabase_admin.table("documentos").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        return {"grupos": grupos_res.count or 0, "participantes": participantes_res.count or 0, "documentos": documentos_res.count or 0}
    except Exception:
        return {"grupos": 0, "participantes": 0, "documentos": 0}

def set_user_role_from_db(email: str):
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
        st.error(f"No se pudo obtener el rol del usuario: {e}")
        st.session_state.rol = "alumno"
        st.session_state.user = {"email": email, "empresa_id": None}

def do_logout():
    try:
        supabase_public.auth.sign_out()
    except Exception:
        pass
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()
# =========================
# LOGIN VIEW - TAILADMIN
# =========================
def login_view():
    ajustes = get_ajustes_app(supabase_public, campos=["mensaje_login", "nombre_app", "logo_url"])
    mensaje_login = ajustes.get("mensaje_login", "Sistema integral de gestión FUNDAE")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    logo_url = ajustes.get("logo_url", "")

    logo_display = (
        f'<img src="{logo_url}" style="width:64px;height:64px;border-radius:12px;">'
        if logo_url else "🚀"
    )

    st.markdown(f"""
    <div class="login-container">
        <div class="login-logo">{logo_display}</div>
        <h2 style="margin-bottom:0.5rem;color:#111827;">{nombre_app}</h2>
        <p style="margin-bottom:2rem;color:#6b7280;">{mensaje_login}</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("form_login", clear_on_submit=False):
        email = st.text_input("📧 Email", placeholder="tu@empresa.com")
        password = st.text_input("🔑 Contraseña", type="password", placeholder="••••••••")
        submitted = st.form_submit_button(
            "Iniciar Sesión",
            disabled=st.session_state.get("login_loading", False),
            use_container_width=True
        )

    if submitted:
        if not email or not password:
            st.warning("Por favor, introduce email y contraseña")
        else:
            st.session_state.login_loading = True
            try:
                auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
                if not auth or not auth.user:
                    st.error("Credenciales incorrectas")
                    st.session_state.login_loading = False
                else:
                    st.session_state.auth_session = auth
                    set_user_role_from_db(auth.user.email)
                    st.success("✅ Sesión iniciada correctamente")
                    time.sleep(0.5)
                    st.session_state.login_loading = False
                    st.rerun()
            except Exception as e:
                st.error(f"Error al iniciar sesión: {e}")
                st.session_state.login_loading = False


# =========================
# DASHBOARDS DE BIENVENIDA
# =========================
def mostrar_dashboard_admin(ajustes, metricas):
    st.title(ajustes.get("bienvenida_admin", "Panel de Administración"))
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">🏢</div>
            <div class="metric-value">{metricas['empresas']}</div>
            <div class="metric-label">Empresas</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">👥</div>
            <div class="metric-value">{metricas['usuarios']}</div>
            <div class="metric-label">Usuarios</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">📚</div>
            <div class="metric-value">{metricas['cursos']}</div>
            <div class="metric-label">Cursos</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">👨‍🎓</div>
            <div class="metric-value">{metricas['grupos']}</div>
            <div class="metric-label">Grupos</div>
        </div>
        """, unsafe_allow_html=True)


def mostrar_dashboard_gestor(ajustes, metricas):
    st.title(ajustes.get("bienvenida_gestor", "Panel del Gestor"))
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">👨‍🎓</div>
            <div class="metric-value">{metricas.get('grupos',0)}</div>
            <div class="metric-label">Grupos</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(ajustes.get("tarjeta_gestor_grupos", "Crea y gestiona grupos."))
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">📂</div>
            <div class="metric-value">{metricas.get('documentos',0)}</div>
            <div class="metric-label">Documentos</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(ajustes.get("tarjeta_gestor_documentos", "Sube y organiza documentación."))
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">🧑‍🎓</div>
            <div class="metric-value">{metricas.get('participantes',0)}</div>
            <div class="metric-label">Participantes</div>
        </div>
        """, unsafe_allow_html=True)


def mostrar_dashboard_alumno(ajustes):
    st.title(ajustes.get("bienvenida_alumno", "Área del Alumno"))
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">📘</div>
            <div class="metric-value">Mis Grupos</div>
            <div class="metric-label">{ajustes.get("tarjeta_alumno_grupos","Consulta tus grupos.")}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">🏅</div>
            <div class="metric-value">Mis Diplomas</div>
            <div class="metric-label">{ajustes.get("tarjeta_alumno_diplomas","Descarga tus diplomas.")}</div>
        </div>
        """, unsafe_allow_html=True)


def mostrar_dashboard_comercial(ajustes):
    st.title(ajustes.get("bienvenida_comercial", "Área Comercial"))
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">👥</div>
            <div class="metric-value">Clientes</div>
            <div class="metric-label">{ajustes.get("tarjeta_comercial_clientes","Gestiona tu cartera.")}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">💡</div>
            <div class="metric-value">Oportunidades</div>
            <div class="metric-label">{ajustes.get("tarjeta_comercial_oportunidades","Sigue nuevas oportunidades.")}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">📝</div>
            <div class="metric-value">Tareas</div>
            <div class="metric-label">{ajustes.get("tarjeta_comercial_tareas","Organiza tus recordatorios.")}</div>
        </div>
        """, unsafe_allow_html=True)
# =========================
# SIDEBAR FIJO TIPO TAILADMIN
# =========================
def render_sidebar():
    rol = st.session_state.get("rol")
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")

    st.sidebar.markdown(f"""
    <div style="padding: 1rem; border-bottom: 1px solid #334155; margin-bottom: 1rem;">
        <p style="margin:0; font-size:0.8rem; color:#94a3b8;">Bienvenido</p>
        <p style="margin:0; font-weight:600; color:#f1f5f9;">{nombre_usuario}</p>
    </div>
    """, unsafe_allow_html=True)

    # Botón logout
    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        do_logout()

    # Menú por roles
    if rol == "admin":
        st.sidebar.markdown("#### ⚙️ Administración")
        menu = {
            "📊 Panel Admin": "panel_admin",
            "👥 Usuarios": "usuarios_empresas",
            "🏢 Empresas": "empresas",
            "⚙️ Ajustes": "ajustes_app"
        }
    elif rol == "gestor":
        st.sidebar.markdown("#### 🎓 Formación")
        menu = {
            "📊 Panel Gestor": "panel_gestor",
            "🏢 Empresas": "empresas",
            "📚 Acciones Formativas": "acciones_formativas",
            "👨‍🎓 Grupos": "grupos",
            "🧑‍🎓 Participantes": "participantes",
            "👩‍🏫 Tutores": "tutores",
            "🏫 Aulas": "aulas",
            "📆 Gestión Clases": "gestion_clases",
            "📂 Documentos": "documentos"
        }
    elif rol == "alumno":
        st.sidebar.markdown("#### 🎓 Área Alumno")
        menu = {
            "📘 Mis Grupos": "area_alumno"
        }
    elif rol == "comercial":
        st.sidebar.markdown("#### 💼 CRM")
        menu = {
            "📊 Panel CRM": "crm_panel",
            "👥 Clientes": "crm_clientes",
            "💡 Oportunidades": "crm_oportunidades",
            "📝 Tareas": "crm_tareas"
        }
    else:
        menu = {}

    # Render menú
    for label, page_key in menu.items():
        if st.sidebar.button(label, use_container_width=True):
            st.session_state.page = page_key
            st.rerun()


# =========================
# NAVEGACIÓN CON PAGE MAP
# =========================
def render_page():
    page = st.session_state.get("page", "home")

    if page and page != "home":
        with st.spinner(f"Cargando {page}..."):
            try:
                # Mapeo de páginas -> módulos en views/
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
                    view_module = __import__(f"views.{page_map[page]}", fromlist=["render"])
                    view_module.render(supabase_admin, st.session_state)
                else:
                    st.error(f"Página '{page}' no encontrada")

            except Exception as e:
                st.error(f"Error al cargar página: {e}")
                st.exception(e)
# =========================
# EJECUCIÓN PRINCIPAL
# =========================
if not st.session_state.get("rol"):
    # 👤 Usuario no logueado → mostrar login
    st.markdown('<div class="login-mode">', unsafe_allow_html=True)
    login_view()
else:
    # 👤 Usuario logueado → mostrar sidebar fijo y páginas
    st.markdown('<div class="app-mode">', unsafe_allow_html=True)

    try:
        # Sidebar fijo estilo TailAdmin
        render_sidebar()

        # Página seleccionada
        page = st.session_state.get("page", "home")

        if page and page != "home":
            render_page()
        else:
            # =========================
            # Dashboards de bienvenida por rol
            # =========================
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
        st.error(f"Error al cargar la aplicación: {e}")
        st.exception(e)

# =========================
# Cierre de div de layout
# =========================
st.markdown("</div>", unsafe_allow_html=True)
