import streamlit as st
import os
from supabase import create_client, Client
from datetime import datetime

# =======================
# CONFIGURACIÓN PÁGINA
# =======================
st.set_page_config(page_title="Gestor de Formación", page_icon="📚", layout="wide")

# =======================
# CONFIGURACIÓN SUPABASE
# =======================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =======================
# SESIÓN
# =======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None

def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.experimental_rerun()

# =======================
# LOGIN
# =======================
if not st.session_state.logged_in:
    st.title("🔐 Acceso al Gestor de Formación")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        try:
            auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if auth_res.user:
                res = supabase.table("usuarios").select("*").eq("email", email).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.user = res.data[0]
                    st.session_state.role = res.data[0]["rol"]
                    st.experimental_rerun()
                else:
                    st.error("Usuario no registrado en la tabla interna.")
            else:
                st.error("Credenciales incorrectas.")
        except Exception as e:
            st.error(f"Error de login: {e}")

# =======================
# APP PRINCIPAL
# =======================
if st.session_state.logged_in:
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email")
    st.sidebar.title(f"👋 Bienvenido {nombre_usuario}")
    st.sidebar.button("Cerrar sesión", on_click=logout)

    # Menú dinámico según rol
    if st.session_state.role == "admin":
        opciones = [
            "Usuarios y Empresas",
            "Empresas",
            "Acciones Formativas",
            "Grupos",
            "Participantes",
            "Documentos",
            "Tutores",
            "Gestión de Alumnos"
        ]
    elif st.session_state.role == "gestor":
        opciones = ["Grupos", "Participantes", "Documentos"]
    elif st.session_state.role == "alumno":
        opciones = ["Mis Grupos y Diplomas"]

    menu = st.sidebar.radio("📂 Menú", opciones)

    # Carga de páginas
    if st.session_state.role == "admin":
        if menu == "Usuarios y Empresas":
            from pages.usuarios_empresas import main as usuarios_empresas_page
            usuarios_empresas_page(supabase, st.session_state)
        elif menu == "Empresas":
            from pages.empresas import main as empresas_page
            empresas_page(supabase, st.session_state)
        elif menu == "Acciones Formativas":
            from pages.acciones_formativas import main as acciones_page
            acciones_page(supabase, st.session_state)
        elif menu == "Grupos":
            from pages.grupos import main as grupos_page
            grupos_page(supabase, st.session_state)
        elif menu == "Participantes":
            from pages.participantes import main as participantes_page
            participantes_page(supabase, st.session_state)
        elif menu == "Documentos":
            from pages.documentos import main as documentos_page
            documentos_page(supabase, st.session_state)
        elif menu == "Tutores":
            from pages.tutores import main as tutores_page
            tutores_page(supabase, st.session_state)
        elif menu == "Gestión de Alumnos":
            from pages.participantes import main as participantes_page
            participantes_page(supabase, st.session_state)

    elif st.session_state.role == "gestor":
        if menu == "Grupos":
            from pages.grupos import main as grupos_page
            grupos_page(supabase, st.session_state)
        elif menu == "Participantes":
            from pages.participantes import main as participantes_page
            participantes_page(supabase, st.session_state)
        elif menu == "Documentos":
            from pages.documentos import main as documentos_page
            documentos_page(supabase, st.session_state)

    elif st.session_state.role == "alumno":
        if menu == "Mis Grupos y Diplomas":
            from pages.alumno import main as alumno_page
            alumno_page(supabase, st.session_state)
