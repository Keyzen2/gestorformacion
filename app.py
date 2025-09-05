import sys, os
import streamlit as st
from supabase import create_client

# 🔹 Forzar inclusión de la carpeta raíz en el path de Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# =========================
# Configuración de página
# =========================
st.set_page_config(page_title="Gestor de Formación", layout="wide")

# =========================
# Conexión a Supabase
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# =========================
# Estado de sesión
# =========================
if "page" not in st.session_state:
    st.session_state.page = "home"
if "role" not in st.session_state:
    st.session_state.role = None
if "user" not in st.session_state:
    st.session_state.user = {}
if "auth_session" not in st.session_state:
    st.session_state.auth_session = None

# =========================
# Funciones auxiliares
# =========================
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
    st.title("🔐 Iniciar sesión")
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

# =========================
# Enrutamiento principal
# =========================
def route():
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email")
    st.sidebar.markdown(f"### 👋 Bienvenido, **{nombre_usuario}**")

    # Botón de logout
    if st.sidebar.button("🚪 Cerrar sesión"):
        do_logout()

    # Menú por rol
    if st.session_state.role == "admin":
        st.sidebar.markdown("#### 🧭 Navegación")
        menu_admin = {
            "Usuarios y Empresas": "usuarios_empresas",
            "Empresas": "empresas",
            "Acciones Formativas": "acciones_formativas",
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Documentos": "documentos",
            "Tutores": "tutores",
            "Gestión de Alumnos": "participantes"
        }
        for label, page_key in menu_admin.items():
            if st.sidebar.button(label):
                st.session_state.page = page_key

        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📏 Gestión ISO 9001")
        menu_iso = {
            "No Conformidades": "no_conformidades",
            "Acciones Correctivas": "acciones_correctivas",
            "Auditorías": "auditorias",
            "Indicadores": "indicadores",
            "Dashboard Calidad": "dashboard_calidad",
            "Objetivos de Calidad": "objetivos_calidad"
        }
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

        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📏 Gestión ISO 9001")
        for label, page_key in menu_iso.items():
            if st.sidebar.button(label):
                st.session_state.page = page_key

    elif st.session_state.role == "alumno":
        st.sidebar.markdown("#### 🎓 Área del Alumno")
        if st.sidebar.button("Mis Grupos y Diplomas"):
            st.session_state.page = "mis_grupos"

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.caption("© 2025 Gestor de Formación · ISO 9001 · Streamlit + Supabase")

    # Enrutamiento por página
    page = st.session_state.page
    try:
        if page == "usuarios_empresas":
            from pages.usuarios_empresas import main as usuarios_empresas_page
            usuarios_empresas_page(supabase_admin, st.session_state)
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
        elif page == "tutores":
            from pages.tutores import main as tutores_page
            tutores_page(supabase_admin, st.session_state)
        elif page == "no_conformidades":
            from pages.no_conformidades import main as nc_page
            nc_page(supabase_admin, st.session_state)
        elif page == "acciones_correctivas":
            from pages.acciones_correctivas import main as ac_page
            ac_page(supabase_admin, st.session_state)
        elif page == "auditorias":
            from pages.auditorias import main as auditorias_page
            auditorias_page(supabase_admin, st.session_state)
        elif page == "indicadores":
            from pages.indicadores import main as indicadores_page
            indicadores_page(supabase_admin, st.session_state)
        elif page == "dashboard_calidad":
            from pages.dashboard_calidad import main as dashboard_calidad_page
            dashboard_calidad_page(supabase_admin, st.session_state)
        elif page == "objetivos_calidad":
            from pages.objetivos_calidad import main as objetivos_page
            objetivos_page(supabase_admin, st.session_state)
        elif page == "mis_grupos":
            from pages.mis_grupos import main as mis_grupos_page
            mis_grupos_page(supabase_public, st.session_state)
        else:
            st.title("🏠 Bienvenido al Gestor de Formación")
            st.caption("Usa el menú lateral para navegar por las secciones disponibles según tu rol.")
    except Exception as e:
        st.error(f"❌ Error al cargar la página '{page}': {e}")
