import os
import sys
import streamlit as st
from utils import get_ajustes_app
from supabase import create_client
from datetime import datetime
import pandas as pd
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# =========================
# Configuración
# =========================
st.set_page_config(
    page_title="Gestor de Formación",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀",
    menu_items=None
)

# =========================
# CSS DISEÑO SAAS PROFESIONAL
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Ocultar elementos Streamlit */
#MainMenu, footer, .stDeployButton, header[data-testid="stHeader"],
button[kind="header"], [data-testid="stToolbar"] {
    display: none !important;
}

/* Reset */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Background global limpio */
.stApp {
    background: #f8fafc !important;
}

/* SIDEBAR CON COLOR DE CONTRASTE */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
    border-right: 1px solid #334155 !important;
    padding-top: 80px !important; /* Espacio para header */
}

section[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
    padding: 0.625rem 1rem !important;
    font-size: 0.9rem !important;
    transition: all 0.2s ease !important;
}

section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255, 255, 255, 0.1) !important;
    border-color: rgba(255, 255, 255, 0.2) !important;
    transform: translateX(4px) !important;
}

section[data-testid="stSidebar"] h4 {
    color: #94a3b8 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin: 1.5rem 0 0.5rem 0 !important;
}

section[data-testid="stSidebar"] hr {
    border-color: #334155 !important;
    margin: 1rem 0 !important;
}

/* ÁREA PRINCIPAL CLARA */
.main .block-container {
    padding: 100px 2rem 80px 2rem !important;
    max-width: 1400px !important;
    background: #ffffff !important;
    min-height: calc(100vh - 180px) !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
}

/* LOGIN - diseño especial */
.login-mode .stApp {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
}

.login-mode .main .block-container {
    background: transparent !important;
    box-shadow: none !important;
    padding-top: 2rem !important;
}

.login-container {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    padding: 3rem;
    box-shadow: 0 20px 40px rgba(0,0,0,0.2);
    max-width: 480px;
    margin: 2rem auto;
}

.login-logo {
    width: 80px;
    height: 80px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border-radius: 20px;
    margin: 0 auto 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    color: white;
}

/* Inputs */
.stTextInput > div > div > input {
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    padding: 0.75rem 1rem !important;
    font-size: 0.95rem !important;
}

.stTextInput > div > div > input:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1) !important;
}

/* Botones principales */
.stButton > button[kind="primary"],
.stButton > button:not([kind]) {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.75rem 1.5rem !important;
    font-weight: 600 !important;
}

.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(59,130,246,0.3) !important;
}

/* Métricas modernas */
[data-testid="stMetric"] {
    background: #ffffff !important;
    padding: 1.5rem !important;
    border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}

[data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: #1e293b !important;
}

[data-testid="stMetricLabel"] {
    font-size: 0.875rem !important;
    color: #64748b !important;
    font-weight: 500 !important;
}

/* Alertas */
.stAlert {
    border-radius: 8px !important;
    border-left: 4px solid !important;
}

/* Títulos */
h1 {
    color: #1e293b !important;
    font-weight: 700 !important;
    margin-bottom: 1rem !important;
}

h2, h3 {
    color: #334155 !important;
    font-weight: 600 !important;
}
/* DISEÑO SAAS - Header y Footer fijos */
.app-header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 70px;
    background: white;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    align-items: center;
    padding: 0 2rem;
    z-index: 999;
}

.app-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 50px;
    background: #f8fafc;
    border-top: 1px solid #e2e8f0;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 998;
}

/* Sidebar oscuro */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
    padding-top: 80px !important;
}

section[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

/* Contenido principal con espacio para header/footer */
.main .block-container {
    padding-top: 100px !important;
    padding-bottom: 80px !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# HEADER Y FOOTER DINÁMICOS
# =========================
def render_header():
    """Header fijo profesional con logo y nombre de la app"""
    ajustes = get_ajustes_app(supabase_admin if supabase_admin else supabase_public, 
                               campos=["nombre_app", "logo_url", "color_primario"])
    
    logo_url = ajustes.get("logo_url", "")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    color = ajustes.get("color_primario", "#3b82f6")
    
    logo_html = f'<img src="{logo_url}" style="height: 40px; width: 40px; border-radius: 8px;">' if logo_url else "🚀"
    
    st.markdown(f"""
    <div style="
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 70px;
        background: white;
        border-bottom: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        padding: 0 2rem;
        z-index: 999;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    ">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 2rem;">{logo_html}</div>
            <div>
                <h2 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: #1e293b;">
                    {nombre_app}
                </h2>
                <p style="margin: 0; font-size: 0.75rem; color: #64748b;">
                    Sistema de Gestión Empresarial
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_footer():
    """Footer fijo profesional"""
    ajustes = get_ajustes_app(supabase_admin if supabase_admin else supabase_public, 
                               campos=["mensaje_footer"])
    
    mensaje = ajustes.get("mensaje_footer", "© 2025 Gestor de Formación")
    
    st.markdown(f"""
    <div style="
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 60px;
        background: #f8fafc;
        border-top: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 2rem;
        z-index: 998;
    ">
        <p style="margin: 0; font-size: 0.875rem; color: #64748b; text-align: center;">
            {mensaje}
        </p>
    </div>
    """, unsafe_allow_html=True)

# =========================
# Supabase
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("Variables de Supabase no configuradas")
    st.stop()

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else None

# =========================
# Estado
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
# Funciones (mantener las mismas de antes)
# =========================
@st.cache_data(ttl=300)
def get_metricas_admin():
    try:
        empresas = supabase_admin.table("empresas").select("id", count="exact").execute().count or 0
        usuarios = supabase_admin.table("usuarios").select("id", count="exact").execute().count or 0
        cursos = supabase_admin.table("acciones_formativas").select("id", count="exact").execute().count or 0
        grupos = supabase_admin.table("grupos").select("id", count="exact").execute().count or 0
        return {"empresas": empresas, "usuarios": usuarios, "cursos": cursos, "grupos": grupos}
    except:
        return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}
        
def render_header():
    """Header fijo con logo"""
    ajustes = get_ajustes_app(supabase_admin if supabase_admin else supabase_public, 
                               campos=["nombre_app", "logo_url"])
    
    logo = ajustes.get("logo_url", "")
    nombre = ajustes.get("nombre_app", "Gestor de Formación")
    
    logo_html = f'<img src="{logo}" style="height: 40px; border-radius: 8px;">' if logo else "🚀"
    
    st.markdown(f"""
    <div class="app-header">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 2rem;">{logo_html}</div>
            <h2 style="margin: 0; font-size: 1.25rem; color: #1e293b;">{nombre}</h2>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_footer():
    """Footer fijo"""
    ajustes = get_ajustes_app(supabase_admin if supabase_admin else supabase_public, 
                               campos=["mensaje_footer"])
    mensaje = ajustes.get("mensaje_footer", "© 2025 Gestor de Formación")
    
    st.markdown(f"""
    <div class="app-footer">
        <p style="margin: 0; font-size: 0.875rem; color: #64748b;">{mensaje}</p>
    </div>
    """, unsafe_allow_html=True)
    
@st.cache_data(ttl=300)
def get_metricas_gestor(empresa_id):
    try:
        grupos = supabase_admin.table("grupos").select("id", count="exact").eq("empresa_id", empresa_id).execute().count or 0
        participantes = supabase_admin.table("participantes").select("id", count="exact").eq("empresa_id", empresa_id).execute().count or 0
        documentos = supabase_admin.table("documentos").select("id", count="exact").eq("empresa_id", empresa_id).execute().count or 0
        return {"grupos": grupos, "participantes": participantes, "documentos": documentos}
    except:
        return {"grupos": 0, "participantes": 0, "documentos": 0}

def set_user_role_from_db(email: str):
    """Obtiene el rol y datos básicos del usuario desde la base de datos."""
    try:
        clean_email = email.strip().lower()
        res = supabase_public.table("usuarios").select("*").eq("email", clean_email).limit(1).execute()
        if res.data:
            row = res.data[0]
            rol = row.get("rol") or "alumno"
            st.session_state.role = rol
            st.session_state.user = {
                "id": row.get("id"),
                "auth_id": row.get("auth_id"),
                "email": row.get("email"),
                "nombre": row.get("nombre"),
                "empresa_id": row.get("empresa_id")
            }
            if rol == "comercial":
                com_res = supabase_public.table("comerciales").select("id").eq("usuario_id", row.get("id")).execute()
                if com_res.data:
                    st.session_state.user["comercial_id"] = com_res.data[0]["id"]
        else:
            st.session_state.role = "alumno"
            st.session_state.user = {"email": clean_email, "empresa_id": None}
    except Exception as e:
        st.error(f"No se pudo obtener el rol del usuario: {e}")
        st.session_state.role = "alumno"
        st.session_state.user = {"email": email, "empresa_id": None}

def do_logout():
    try:
        supabase_public.auth.sign_out()
    except:
        pass
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

def is_module_active(empresa, empresa_crm, key, hoy, rol):
    if rol == "alumno":
        return False
    if key == "formacion":
        return empresa.get("formacion_activo", False)
    if key == "iso":
        return empresa.get("iso_activo", False)
    if key == "rgpd":
        return empresa.get("rgpd_activo", False)
    if key == "crm":
        return empresa_crm.get("crm_activo", False)
    return False

# =========================
# Login
# =========================
def login_view():
    ajustes = get_ajustes_app(supabase_public, campos=[
        "mensaje_login", "nombre_app", "logo_url"
    ])

    mensaje_login = ajustes.get("mensaje_login", "Accede con tus credenciales")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    logo_display = "📚" if not ajustes.get("logo_url") else f'<img src="{ajustes.get("logo_url")}" width="64" height="64" style="border-radius: 12px;">'

    st.markdown(f"""
    <div class="login-container fade-in">
        <div class="login-header">
            <div class="login-logo">{logo_display}</div>
            <h1 class="login-title">{nombre_app}</h1>
            <p class="login-subtitle">{mensaje_login}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("form_login", clear_on_submit=False):
            st.markdown("#### Iniciar sesión")

            email = st.text_input("Email", placeholder="tu@empresa.com", label_visibility="collapsed")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••", label_visibility="collapsed")

            submitted = st.form_submit_button(
                "Iniciar sesión" if not st.session_state.get("login_loading") else "Iniciando...",
                disabled=st.session_state.get("login_loading", False),
                use_container_width=True
            )

    if submitted:
        if not email or not password:
            st.warning("Introduce email y contraseña")
        else:
            st.session_state.login_loading = True
            try:
                auth = supabase_public.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                if not auth or not auth.user:
                    st.error("Credenciales incorrectas")
                    st.session_state.login_loading = False
                else:
                    st.session_state.auth_session = auth
                    set_user_role_from_db(auth.user.email)
                    st.success("Sesión iniciada correctamente")
                    time.sleep(0.5)
                    st.session_state.login_loading = False
                    st.rerun()
            except Exception as e:
                st.error(f"Error al iniciar sesión: {e}")
                st.session_state.login_loading = False

# =========================
# Sidebar y navegación
# =========================
def route():
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")

    # Header del sidebar
    st.sidebar.markdown(f"""
    <div style="padding: 1rem 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 1rem;">
        <p style="margin: 0; font-size: 0.875rem; color: #64748b;">Bienvenido</p>
        <p style="margin: 0.25rem 0 0; font-weight: 600; color: #1e293b;">{nombre_usuario}</p>
    </div>
    """, unsafe_allow_html=True)

    # Botón de logout
    if st.sidebar.button("Cerrar sesión", key="logout", type="secondary", use_container_width=True):
        do_logout()

    # Variables de empresa / rol
    empresa_id = st.session_state.user.get("empresa_id")
    empresa = {}
    empresa_crm = {}
    hoy = datetime.today().date()

    if empresa_id:
        try:
            empresa_res = supabase_admin.table("empresas").select(
                "formacion_activo, formacion_inicio, formacion_fin,"
                "iso_activo, iso_inicio, iso_fin,"
                "rgpd_activo, rgpd_inicio, rgpd_fin,"
                "docu_avanzada_activo, docu_avanzada_inicio, docu_avanzada_fin"
            ).eq("id", empresa_id).execute()
            empresa = empresa_res.data[0] if empresa_res.data else {}

            crm_res = supabase_admin.table("crm_empresas").select(
                "crm_activo, crm_inicio, crm_fin"
            ).eq("empresa_id", empresa_id).execute()
            empresa_crm = crm_res.data[0] if crm_res.data else {}
        except Exception:
            st.sidebar.error("Error al cargar configuración de la empresa")

    st.session_state.empresa = empresa
    st.session_state.empresa_crm = empresa_crm
    rol = st.session_state.rol

    # =========================
    # Menús según rol
    # =========================

    # --- Admin ---
    if rol == "admin":
        st.sidebar.markdown("### ⚙️ Administración")
        admin_menu = {
            "Panel Admin": "panel_admin",
            "Usuarios y Empresas": "usuarios_empresas",
            "Empresas": "empresas",
            "Ajustes": "ajustes_app"
        }
        for label, page_key in admin_menu.items():
            if st.sidebar.button(label, key=f"admin_{page_key}", type="secondary", use_container_width=True):
                st.session_state.page = page_key

    # --- Alumno ---
    if rol == "alumno":
        st.sidebar.markdown("### 🎓 Área del Alumno")
        alumno_menu = {
            "Mis Grupos": "area_alumno",
            "Mis Diplomas": "area_alumno",  # mismo módulo, diferente tab interna
        }
        for label, page_key in alumno_menu.items():
            if st.sidebar.button(label, key=f"alumno_{page_key}", type="secondary", use_container_width=True):
                st.session_state.page = page_key

    # --- Panel Gestor ---
    if rol == "gestor" and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("### 📋 Panel del Gestor")
        if st.sidebar.button("Panel Gestor", key="panel_gestor", type="secondary", use_container_width=True):
            st.session_state.page = "panel_gestor"

    # --- Módulo Formación ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("### 📚 Formación")
        formacion_menu = {
            "Acciones Formativas": "acciones_formativas",
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Tutores": "tutores",
            "Aulas": "aulas",
            "Gestión Clases": "gestion_clases",
            "Proyectos": "proyectos",
            "Documentos": "documentos"
        }
        if rol == "gestor":
            formacion_menu = {"Empresas": "empresas", **formacion_menu}
        for label, page_key in formacion_menu.items():
            if st.sidebar.button(label, key=f"form_{page_key}", type="secondary", use_container_width=True):
                st.session_state.page = page_key

    # --- Módulo ISO ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "iso", hoy, rol):
        st.sidebar.markdown("### 📑 ISO 9001")
        iso_menu = {
            "No Conformidades": "no_conformidades",
            "Acciones Correctivas": "acciones_correctivas",
            "Auditorías": "auditorias",
            "Indicadores": "indicadores",
            "Dashboard Calidad": "dashboard_calidad",
            "Objetivos de Calidad": "objetivos_calidad",
            "Informe Auditoría": "informe_auditoria"
        }
        for label, page_key in iso_menu.items():
            if st.sidebar.button(label, key=f"iso_{page_key}", type="secondary", use_container_width=True):
                st.session_state.page = page_key

    # --- Módulo RGPD ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "rgpd", hoy, rol):
        st.sidebar.markdown("### 🛡️ RGPD")
        rgpd_menu = {
            "Panel RGPD": "rgpd_panel",
            "Tareas RGPD": "rgpd_planner",
            "Diagnóstico Inicial": "rgpd_inicio",
            "Tratamientos": "rgpd_tratamientos",
            "Cláusulas y Consentimientos": "rgpd_consentimientos",
            "Encargados": "rgpd_encargados",
            "Derechos": "rgpd_derechos",
            "Evaluación de Impacto": "rgpd_evaluacion",
            "Medidas de Seguridad": "rgpd_medidas",
            "Incidencias": "rgpd_incidencias"
        }
        for label, page_key in rgpd_menu.items():
            if st.sidebar.button(label, key=f"rgpd_{page_key}", type="secondary", use_container_width=True):
                st.session_state.page = page_key

    # --- Módulo CRM ---
    if (rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "crm", hoy, rol)) or rol == "comercial":
        st.sidebar.markdown("### 📈 CRM")
        crm_menu = {
            "Panel CRM": "crm_panel",
            "Clientes": "crm_clientes",
            "Oportunidades": "crm_oportunidades",
            "Tareas": "crm_tareas",
            "Comunicaciones": "crm_comunicaciones",
            "Estadísticas": "crm_estadisticas"
        }
        for label, page_key in crm_menu.items():
            if st.sidebar.button(label, key=f"crm_{page_key}", type="secondary", use_container_width=True):
                st.session_state.page = page_key

    # --- Módulo Docu Avanzada ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "docu_avanzada", hoy, rol):
        st.sidebar.markdown("### 📁 Documentación Avanzada")
        if st.sidebar.button("Gestión Documental", key="docu_avanzada", type="secondary", use_container_width=True):
            st.session_state.page = "documentacion_avanzada"

    # Footer dinámico
    ajustes = get_ajustes_app(supabase_admin, campos=["mensaje_footer"])
    st.sidebar.markdown("---")
    st.sidebar.caption(ajustes.get("mensaje_footer", "© 2025 Gestor de Formación"))

        
# =========================
# Ejecución principal
# =========================
if not st.session_state.get("role"):
    # 👤 Usuario no logueado → mostrar login
    st.markdown('<div class="login-mode">', unsafe_allow_html=True)
    login_view()
else:
    render_header() 
    render_footer()
    # 👤 Usuario logueado → mostrar sidebar dinámico
    st.markdown('<div class="app-mode">', unsafe_allow_html=True)
    try:
        route()
        page = st.session_state.get("page", None)

        if page and page != "home":
            with st.spinner("Cargando..."):
                try:
                    # =========================
                    # MAPEO DE PÁGINAS → VIEWS
                    # =========================
                    page_map = {
                        # --- Admin ---
                        "panel_admin": "panel_admin",
                        "usuarios_empresas": "usuarios_empresas",
                        "empresas": "empresas",
                        "ajustes_app": "ajustes_app",

                        # --- Gestor ---
                        "panel_gestor": "panel_gestor",
                        "acciones_formativas": "acciones_formativas",
                        "grupos": "grupos",
                        "participantes": "participantes",
                        "tutores": "tutores",
                        "aulas": "aulas",
                        "gestion_clases": "gestion_clases",
                        "proyectos": "proyectos",
                        "documentos": "documentos",

                        # --- Alumno ---
                        "area_alumno": "area_alumno",

                        # --- ISO ---
                        "no_conformidades": "no_conformidades",
                        "acciones_correctivas": "acciones_correctivas",
                        "auditorias": "auditorias",
                        "indicadores": "indicadores",
                        "dashboard_calidad": "dashboard_calidad",
                        "objetivos_calidad": "objetivos_calidad",
                        "informe_auditoria": "informe_auditoria",

                        # --- RGPD ---
                        "rgpd_panel": "rgpd_panel",
                        "rgpd_planner": "rgpd_planner",
                        "rgpd_inicio": "rgpd_inicio",
                        "rgpd_tratamientos": "rgpd_tratamientos",
                        "rgpd_consentimientos": "rgpd_consentimientos",
                        "rgpd_encargados": "rgpd_encargados",
                        "rgpd_derechos": "rgpd_derechos",
                        "rgpd_evaluacion": "rgpd_evaluacion",
                        "rgpd_medidas": "rgpd_medidas",
                        "rgpd_incidencias": "rgpd_incidencias",

                        # --- CRM ---
                        "crm_panel": "crm_panel",
                        "crm_clientes": "crm_clientes",
                        "crm_oportunidades": "crm_oportunidades",
                        "crm_tareas": "crm_tareas",
                        "crm_comunicaciones": "crm_comunicaciones",
                        "crm_estadisticas": "crm_estadisticas",

                        # --- Documentación Avanzada ---
                        "documentacion_avanzada": "documentacion_avanzada"
                    }

                    if page in page_map:
                        view_module = __import__(f"views.{page_map[page]}", fromlist=["render"])
                        view_module.render(supabase_admin, st.session_state)
                    else:
                        st.error(f"❌ Página '{page}' no encontrada")

                except Exception as e:
                    st.error(f"❌ Error al cargar página '{page}': {e}")
                    st.exception(e)

        else:
            # =========================
            # Dashboards de bienvenida
            # =========================
            rol = st.session_state.role
            ajustes = get_ajustes_app(supabase_admin, campos=[
                "bienvenida_admin", "bienvenida_gestor", "bienvenida_alumno",
                "bienvenida_comercial", "tarjeta_admin_usuarios", "tarjeta_admin_empresas",
                "tarjeta_admin_ajustes", "tarjeta_gestor_grupos", "tarjeta_gestor_documentos",
                "tarjeta_gestor_docu_avanzada", "tarjeta_alumno_grupos", "tarjeta_alumno_diplomas",
                "tarjeta_alumno_seguimiento", "tarjeta_comercial_clientes",
                "tarjeta_comercial_oportunidades", "tarjeta_comercial_tareas"
            ])

            if rol == "admin":
                with st.spinner("Cargando métricas..."):
                    metricas = get_metricas_admin()
                mostrar_dashboard_admin(ajustes, metricas)

            elif rol == "gestor":
                empresa_id = st.session_state.user.get("empresa_id")
                metricas = get_metricas_gestor(empresa_id) if empresa_id else {"grupos": 0, "participantes": 0, "documentos": 0}
                mostrar_dashboard_gestor(ajustes, metricas)

            elif rol == "alumno":
                mostrar_dashboard_alumno(ajustes)

            elif rol == "comercial":
                mostrar_dashboard_comercial(ajustes)

    except Exception as e:
        st.error(f"❌ Error al cargar la aplicación: {e}")
        st.exception(e)


