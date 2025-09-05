import os, sys
import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Gestor de Formación",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

if "page" not in st.session_state:
    st.session_state.page = "home"
if "role" not in st.session_state:
    st.session_state.role = None
if "user" not in st.session_state:
    st.session_state.user = {}
if "auth_session" not in st.session_state:
    st.session_state.auth_session = None

def set_user_role_from_db(email: str):
    try:
        res = supabase_public.table("usuarios").select("*").eq("email", email).limit(1).execute()
        if res.data:
            row = res.data[0]
            st.session_state.role = row.get("rol") or "alumno"
            st.session_state.user = {
                "auth_id": row.get("auth_id"),
                "email": row.get("email"),
                "nombre": row.get("nombre"),
                "empresa_id": row.get("empresa_id")
            }
        else:
            st.session_state.role = "alumno"
            st.session_state.user = {"email": email}
    except Exception as e:
        st.error(f"No se pudo obtener el rol del usuario: {e}")
        st.session_state.role = "alumno"
        st.session_state.user = {"email": email}

def do_logout():
    try:
        supabase_public.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.experimental_rerun()

def login_view():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap');
            html, body, [class*="css"] {
                font-family: 'Roboto', sans-serif;
                background-color: #f5f5f5;
            }
            .login-title {
                font-size: 32px;
                font-weight: 500;
                color: #202124;
                margin-bottom: 0.5em;
            }
            .module-card {
                background-color: white;
                padding: 1em;
                border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 1em;
            }
            .module-card h4 {
                margin: 0;
                color: #4285F4;
            }
            .module-card p {
                margin: 0.5em 0 0;
                color: #5f6368;
            }
        </style>
        <div class="login-title">Bienvenido a la plataforma</div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="module-card"><h4>📚 Formación Bonificada</h4><p>Gestión de acciones formativas y documentos FUNDAE.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="module-card"><h4>📋 ISO 9001</h4><p>Auditorías, informes y seguimiento de calidad.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="module-card"><h4>🔐 RGPD</h4><p>Consentimientos, documentación legal y trazabilidad.</p></div>', unsafe_allow_html=True)

    st.markdown("### 🔐 Iniciar sesión")
    st.caption("Accede al gestor con tus credenciales.")

    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", autocomplete="email")
        password = st.text_input("Contraseña", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        if not email or not password:
            st.warning("Introduce email y contraseña.")
            return
        try:
            auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
            if not auth or not auth.user:
                st.error("Credenciales inválidas.")
                return
            st.session_state.auth_session = auth
            set_user_role_from_db(auth.user.email)
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error al iniciar sesión: {e}")


def route():
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email")
    st.sidebar.markdown(f"### 👋 Bienvenido, **{nombre_usuario}**")

    if st.sidebar.button("🚪 Cerrar sesión"):
        do_logout()

    menu_iso = {
        "No Conformidades": "no_conformidades",
        "Acciones Correctivas": "acciones_correctivas",
        "Auditorías": "auditorias",
        "Indicadores": "indicadores",
        "Dashboard Calidad": "dashboard_calidad",
        "Objetivos de Calidad": "objetivos_calidad",
        "Informe Auditoría": "informe_auditoria"
    }

    if st.session_state.role == "admin":
        st.sidebar.markdown("#### 🧭 Navegación")
        menu_admin = {
            "Panel de Alertas": "panel_admin",
            "Usuarios y Empresas": "usuarios_empresas",
            "Empresas": "empresas",
            "Acciones Formativas": "acciones_formativas",
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Documentos": "documentos",
            "Tutores": "tutores"
        }
        for label, page_key in menu_admin.items():
            if st.sidebar.button(label):
                st.session_state.page = page_key

        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📏 Gestión ISO 9001")
        for label, page_key in menu_iso.items():
            if st.sidebar.button(label):
                st.session_state.page = page_key

    elif st.session_state.role == "gestor":
        st.sidebar.markdown("#### 🧭 Navegación")
        menu_gestor = {
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Documentos": "documentos"
        }
        for label, page_key in menu_gestor.items():
            if st.sidebar.button(label):
                st.session_state.page = page_key

        empresa_id = st.session_state.user.get("empresa_id")
        empresa_res = supabase_admin.table("empresas").select("iso_activo", "iso_inicio", "iso_fin").eq("id", empresa_id).execute()
        empresa = empresa_res.data[0] if empresa_res.data else {}
        hoy = datetime.today().date()

        iso_permitido = (
            empresa.get("iso_activo") and
            (empresa.get("iso_inicio") is None or pd.to_datetime(empresa["iso_inicio"]).date() <= hoy) and
            (empresa.get("iso_fin") is None or pd.to_datetime(empresa["iso_fin"]).date() >= hoy)
        )

        if iso_permitido:
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📏 Gestión ISO 9001")
            for label, page_key in menu_iso.items():
                if st.sidebar.button(label):
                    st.session_state.page = page_key

        rgpd_res = supabase_admin.table("rgpd_empresas").select("rgpd_activo", "rgpd_inicio", "rgpd_fin").eq("empresa_id", empresa_id).execute()
        rgpd = rgpd_res.data[0] if rgpd_res.data else {}

        rgpd_permitido = (
            rgpd.get("rgpd_activo") and
            (rgpd.get("rgpd_inicio") is None or pd.to_datetime(rgpd["rgpd_inicio"]).date() <= hoy) and
            (rgpd.get("rgpd_fin") is None or pd.to_datetime(rgpd["rgpd_fin"]).date() >= hoy)
        )

        if rgpd_permitido:
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 🛡️ Gestión RGPD")
            rgpd_menu = {
                "Panel RGPD": "rgpd_panel",
                "Diagnóstico Inicial": "rgpd_inicio",
                "Tratamientos": "rgpd_tratamientos",
                "Cláusulas y Consentimientos": "rgpd_consentimientos",
                "Encargados del Tratamiento": "rgpd_encargados",
                "Derechos de los Interesados": "rgpd_derechos",
                "Evaluación de Impacto": "rgpd_evaluacion",
                "Medidas de Seguridad": "rgpd_medidas",
                "Incidencias": "rgpd_incidencias"
            }
            for label, page_key in rgpd_menu.items():
                if st.sidebar.button(label):
                    st.session_state.page = page_key

    elif st.session_state.role == "alumno":
        st.sidebar.markdown("#### 🎓 Área del Alumno")
        if st.sidebar.button("Mis Grupos y Diplomas"):
            st.session_state.page = "mis_grupos"

    st.sidebar.markdown("---")
    st.sidebar.caption("© 2025 Gestor de Formación · ISO 9001 · RGPD · Streamlit + Supabase")

page = st.session_state.page

try:
    if page == "usuarios_empresas":
        from pages.usuarios_empresas import main as usuarios_empresas_page
        usuarios_empresas_page(supabase_admin, st.session_state)
    elif page == "panel_admin":
        from pages.panel_admin import main as panel_admin_page
        panel_admin_page(supabase_admin, st.session_state)
    elif page == "empresas":
        from pages.empresas import main as empresas_page
        empresas_page(supabase_admin, st.session_state)
    elif page == "acciones_formativas":
        from pages.acciones_formativas import main as acciones_page
        acciones_page(supabase_admin, st.session_state)
    elif page == "grupos":
        from pages.grupos import main as grupos_page
        grupos_page(supabase_admin, st.session_state)
    elif page == "participantes":
        from pages.participantes import main as participantes_page
        participantes_page(supabase_admin, st.session_state)
    elif page == "documentos":
        from pages.documentos import main as documentos_page
        documentos_page(supabase_admin, st.session_state)
    elif page == "rgpd_panel":
        from pages.rgpd_panel import main as rgpd_panel_page
        rgpd_panel_page(supabase_admin, st.session_state)
    elif page == "rgpd_inicio":
        from pages.rgpd_inicio import main as rgpd_inicio_page
        rgpd_inicio_page(supabase_admin, st.session_state)
    elif page == "rgpd_tratamientos":
        from pages.rgpd_tratamientos import main as rgpd_tratamientos_page
        rgpd_tratamientos_page(supabase_admin, st.session_state)
    elif page == "rgpd_consentimientos":
        from pages.rgpd_consentimientos import main as rgpd_consentimientos_page
        rgpd_consentimientos_page(supabase_admin, st.session_state)
    elif page == "rgpd_encargados":
        from pages.rgpd_encargados import main as rgpd_encargados_page
        rgpd_encargados_page(supabase_admin, st.session_state)
    elif page == "rgpd_derechos":
        from pages.rgpd_derechos import main as rgpd_derechos_page
        rgpd_derechos_page(supabase_admin, st.session_state)
    elif page == "rgpd_evaluacion":
        from pages.rgpd_evaluacion import main as rgpd_evaluacion_page
        rgpd_evaluacion_page(supabase_admin, st.session_state)
    elif page == "rgpd_medidas":
        from pages.rgpd_medidas import main as rgpd_medidas_page
        rgpd_medidas_page(supabase_admin, st.session_state)
    elif page == "rgpd_incidencias":
        from pages.rgpd_incidencias import main as rgpd_incidencias_page
        rgpd_incidencias_page(supabase_admin, st.session_state)
    elif page == "mis_grupos":
        from pages.mis_grupos import main as mis_grupos_page
        mis_grupos_page(supabase_public, st.session_state)
    else:
        st.title("🏠 Bienvenido al Gestor de Formación")
        st.caption("Usa el menú lateral para navegar por las secciones disponibles según tu rol.")
except Exception as e:
    st.error(f"❌ Error al cargar la página '{page}': {e}")

# =========================
# Ejecución principal
# =========================
if not st.session_state.role:
    login_view()
else:
    route()
