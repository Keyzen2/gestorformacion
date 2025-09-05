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
# Conexión a Supabase usando secrets
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

# Cliente público (operaciones con RLS)
supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
# Cliente admin (operaciones sin RLS, crear usuarios, etc.)
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

def mostrar_menu():
    st.sidebar.title("📋 Menú principal")

    if st.session_state.role == "admin":
        st.sidebar.markdown("### 👥 Gestión de usuarios y empresas")
        if st.sidebar.button("👤 Usuarios y Empresas"):
            st.session_state.page = "usuarios_empresas"
        if st.sidebar.button("🧑‍🎓 Participantes"):
            st.session_state.page = "participantes"
        if st.sidebar.button("👥 Grupos"):
            st.session_state.page = "grupos"
        if st.sidebar.button("📚 Acciones formativas"):
            st.session_state.page = "acciones_formativas"

    if st.session_state.role in ["admin", "gestor"]:
        st.sidebar.markdown("### 🏢 Gestión de empresa")
        if st.sidebar.button("🏢 Mi Empresa"):
            st.session_state.page = "mi_empresa"

    st.sidebar.divider()
    st.sidebar.subheader("📑 Gestión ISO 9001")
    st.sidebar.caption("Sección informativa o futura implementación")

    st.sidebar.divider()
    if st.sidebar.button("🚪 Cerrar sesión"):
        do_logout()

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

def route():
    page = st.session_state.page
    if page == "usuarios_empresas":
        usuarios_empresas.main(supabase_admin, st.session_state)
    elif page == "participantes":
        participantes.main(supabase_admin, st.session_state)
    elif page == "grupos":
        grupos.main(supabase_admin, st.session_state)
    elif page == "acciones_formativas":
        acciones_formativas.main(supabase_admin, st.session_state)
    elif page == "mi_empresa":
        usuarios_empresas.empresas_only(supabase_public, st.session_state)
    else:
        st.title("🏠 Bienvenido al Gestor de Formación")
        if st.session_state.role == "admin":
            st.caption("Usa el menú para gestionar usuarios, participantes, grupos y acciones.")
        elif st.session_state.role == "gestor":
            st.caption("Gestiona tu empresa, grupos y participantes asignados.")
        else:
            st.caption("Consulta tus cursos y tu perfil.")

# =========================
# Ejecución principal
# =========================
if not st.session_state.role:
    login_view()
else:
    mostrar_menu()
    route()
        
