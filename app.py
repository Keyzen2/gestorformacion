import os
import sys
import streamlit as st
from supabase import create_client
import pandas as pd
from utils import get_ajustes_app
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# =========================
# Configuración de la página
# =========================
st.set_page_config(
    page_title="Gestor de Formación",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# Conexión Supabase
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

st.session_state.supabase_public = supabase_public
st.session_state.supabase_admin = supabase_admin

# =========================
# Inicialización segura del estado
# =========================
for key, default in {
    "page": "home",
    "role": None,
    "user": {},
    "auth_session": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =========================
# Función para obtener rol desde la base de datos
# =========================
def set_user_role_from_db(email):
    try:
        res = supabase_admin.table("usuarios").select("*").eq("email", email.strip().lower()).limit(1).execute()
        if res.data:
            user = res.data[0]
            st.session_state.role = user.get("rol", "alumno")
            st.session_state.user = {
                "id": user.get("id"),
                "auth_id": user.get("auth_id"),
                "email": user.get("email"),
                "nombre": user.get("nombre"),
                "empresa_id": user.get("empresa_id"),
                "comercial_id": user.get("comercial_id")
            }
        else:
            st.session_state.role = "alumno"
            st.session_state.user = {"email": email}
    except Exception as e:
        st.error(f"❌ Error al obtener rol: {e}")
        st.session_state.role = "alumno"
        st.session_state.user = {"email": email}

# =========================
# Función de login
# =========================
def login_view():
    ajustes = get_ajustes_app(["mensaje_login"])
    st.title("🔐 Iniciar sesión")
    st.caption(ajustes.get("mensaje_login", "Accede con tus credenciales."))

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar")

    if submit:
        if not email or not password:
            st.warning("⚠️ Introduce email y contraseña.")
            return
        try:
            auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
            if not auth.user:
                st.error("❌ Credenciales inválidas.")
                return
            st.session_state.auth_session = auth
            set_user_role_from_db(auth.user.email)
            st.success("✅ Sesión iniciada correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al iniciar sesión: {e}")

# =========================
# Cierre de sesión
# =========================
def do_logout():
    try:
        supabase_public.auth.sign_out()
    except Exception:
        pass
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

# =========================
# Métricas por rol
# =========================
def get_metricas_admin():
    try:
        empresas = supabase_admin.table("empresas").select("id").execute().data or []
        usuarios = supabase_admin.table("usuarios").select("id").execute().data or []
        grupos = supabase_admin.table("grupos").select("id").execute().data or []
        return {
            "Empresas": len(empresas),
            "Usuarios": len(usuarios),
            "Grupos": len(grupos)
        }
    except Exception:
        return {}

def get_metricas_gestor(empresa_id):
    try:
        grupos = supabase_admin.table("grupos").select("id").eq("empresa_id", empresa_id).execute().data or []
        usuarios = supabase_admin.table("usuarios").select("id").eq("empresa_id", empresa_id).execute().data or []
        return {
            "Grupos": len(grupos),
            "Usuarios": len(usuarios)
        }
    except Exception:
        return {}

# =========================
# Tarjetas visuales
# =========================
def tarjeta(titulo, valor, icono="📦"):
    st.metric(f"{icono} {titulo}", valor)

# =========================
# Render de pantalla principal
# =========================
def render_home():
    st.title("🏠 Bienvenido al Gestor de Formación")
    rol = st.session_state.role
    empresa_id = st.session_state.user.get("empresa_id")

    if rol == "admin":
        metricas = get_metricas_admin()
        col1, col2, col3 = st.columns(3)
        tarjeta("Empresas", metricas.get("Empresas", 0), "🏢")
        tarjeta("Usuarios", metricas.get("Usuarios", 0), "👥")
        tarjeta("Grupos", metricas.get("Grupos", 0), "📦")

    elif rol == "gestor" and empresa_id:
        metricas = get_metricas_gestor(empresa_id)
        col1, col2 = st.columns(2)
        tarjeta("Grupos", metricas.get("Grupos", 0), "📦")
        tarjeta("Usuarios", metricas.get("Usuarios", 0), "👥")

    elif rol == "alumno":
        st.info("🎓 Accede a tus diplomas y grupos desde el menú lateral.")

    elif rol == "comercial":
        st.info("💼 Accede a tus clientes y oportunidades desde el menú lateral.")

# =========================
# Menú lateral por rol
# =========================
def route():
    nombre = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")
    st.sidebar.markdown(f"### 👋 Hola, **{nombre}**")

    if st.sidebar.button("🚪 Cerrar sesión"):
        do_logout()

    rol = st.session_state.role
    menu = {
        "admin": {
            "Inicio": "home",
            "Empresas": "empresas",
            "Usuarios": "usuarios_empresas",
            "Grupos": "grupos",
            "Formaciones": "formaciones",
            "Diplomas": "diplomas",
            "Ajustes": "ajustes_app"
        },
        "gestor": {
            "Inicio": "home",
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Diplomas": "diplomas"
        },
        "alumno": {
            "Inicio": "home",
            "Mis Grupos": "mis_grupos",
            "Diplomas": "diplomas"
        },
        "comercial": {
            "Inicio": "home",
            "Clientes": "crm_clientes",
            "Oportunidades": "crm_oportunidades"
        }
    }

    opciones = menu.get(rol, {})
    seleccion = st.sidebar.radio("📚 Navegación", list(opciones.keys()))
    st.session_state.page = opciones.get(seleccion, "home")

# =========================
# Ejecución principal
# =========================
if not st.session_state.role:
    login_view()
else:
    route()
    page = st.session_state.get("page", "home")

    if page == "home":
        render_home()
    else:
        try:
            mod_path = f"{page.replace('-', '_')}"
            mod_import = __import__(mod_path, fromlist=["main"])
            mod_import.main(supabase_admin, st.session_state)
        except ModuleNotFoundError:
            st.error(f"⚠️ La página '{page}' no está disponible.")
        except Exception as e:
            st.error(f"❌ Error al cargar la página '{page}': {e}")
            st.exception(e)
