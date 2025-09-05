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
    st.sidebar.title(f"👋 Bienvenido {nombre_usuario}")
    st.sidebar.button("Cerrar sesión", on_click=do_logout)

    # Menú dinámico según rol
    if st.session_state.role == "admin":
        opciones = [
            "👥 Usuarios y Empresas",
            "🏢 Empresas",
            "📚 Acciones Formativas",
            "👨‍🏫 Grupos",
            "🧑‍🎓 Participantes",
            "📄 Documentos",
            "🎓 Tutores",
            "📋 Gestión de Alumnos",
            "— 📏 Gestión ISO 9001 —",
            "🚨 No Conformidades (ISO 9001)",
            "🛠️ Acciones Correctivas (ISO 9001)",
            "📋 Auditorías (ISO 9001)",
            "📈 Indicadores (ISO 9001)",
            "📊 Dashboard Calidad (ISO 9001)",
            "🎯 Objetivos de Calidad (ISO 9001)"
        ]
    elif st.session_state.role == "gestor":
        opciones = [
            "👨‍🏫 Grupos",
            "🧑‍🎓 Participantes",
            "📄 Documentos",
            "— 📏 Gestión ISO 9001 —",
            "🚨 No Conformidades (ISO 9001)",
            "🛠️ Acciones Correctivas (ISO 9001)",
            "📋 Auditorías (ISO 9001)",
            "📈 Indicadores (ISO 9001)",
            "📊 Dashboard Calidad (ISO 9001)",
            "🎯 Objetivos de Calidad (ISO 9001)"
        ]
    elif st.session_state.role == "alumno":
        opciones = ["🎓 Mis Grupos y Diplomas"]
    else:
        opciones = []

    menu = st.sidebar.radio("📂 Menú", opciones)

    # Carga de páginas
    if menu.startswith("👥 Usuarios"):
        from pages.usuarios_empresas import main as usuarios_empresas_page
        usuarios_empresas_page(supabase_admin, st.session_state)

    elif menu.startswith("🏢 Empresas"):
        from pages.empresas import main as empresas_page
        empresas_page(supabase_admin, st.session_state)

    elif menu.startswith("📚 Acciones Formativas"):
        from pages.acciones_formativas import main as acciones_page
        acciones_page(supabase_admin, st.session_state)

    elif menu.startswith("👨‍🏫 Grupos"):
        from pages.grupos import main as grupos_page
        grupos_page(supabase_admin, st.session_state)

    elif menu.startswith("🧑‍🎓 Participantes") or menu.startswith("📋 Gestión de Alumnos"):
        from pages.participantes import main as participantes_page
        participantes_page(supabase_admin, st.session_state)

    elif menu.startswith("📄 Documentos"):
        from pages.documentos import main as documentos_page
        documentos_page(supabase_admin, st.session_state)

    elif menu.startswith("🎓 Tutores"):
        from pages.tutores import main as tutores_page
        tutores_page(supabase_admin, st.session_state)

    elif menu.startswith("🚨 No Conformidades"):
        from pages.no_conformidades import main as nc_page
        nc_page(supabase_admin, st.session_state)

    elif menu.startswith("🛠️ Acciones Correctivas"):
        from pages.acciones_correctivas import main as ac_page
        ac_page(supabase_admin, st.session_state)

    elif menu.startswith("📋 Auditorías"):
        from pages.auditorias import main as auditorias_page
        auditorias_page(supabase_admin, st.session_state)

    elif menu.startswith("📈 Indicadores"):
        from pages.indicadores import main as indicadores_page
        indicadores_page(supabase_admin, st.session_state)

    elif menu.startswith("📊 Dashboard Calidad"):
        from pages.dashboard_calidad import main as dashboard_calidad_page
        dashboard_calidad_page(supabase_admin, st.session_state)

    elif menu.startswith("🎯 Objetivos de Calidad"):
        from pages.objetivos_calidad import main as objetivos_page
        objetivos_page(supabase_admin, st.session_state)

    elif menu.startswith("🎓 Mis Grupos"):
        from pages.mis_grupos import main as mis_grupos_page
        mis_grupos_page(supabase_public, st.session_state)

    # Footer
    st.sidebar.divider()
    st.sidebar.caption("© 2025 Gestor de Formación · ISO 9001 · Streamlit + Supabase")

# =========================
# Ejecución principal
# =========================
if not st.session_state.role:
    login_view()
else:
    route()
        
