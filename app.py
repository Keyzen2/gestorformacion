import streamlit as st
import os
from supabase import create_client, Client
from datetime import datetime
from utils import (
    importar_participantes_excel,
    generar_pdf,
    validar_xml,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo
)

# =======================
# CONFIGURACIÓN SUPABASE
# =======================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    st.error("Error de conexión a Supabase. Revisa URL y KEY.")
    st.stop()

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
    st.title("Gestor de Formación - Login")
    with st.form("login_form"):
        email = st.text_input("Usuario (email/CIF)")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")
    if submitted:
        try:
            user = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if user.user:
                res = supabase.table("usuarios").select("*").eq("email", email).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.user = res.data[0]
                    st.session_state.role = res.data[0]["rol"]
                    st.experimental_rerun()
        except Exception:
            st.error("Usuario o contraseña incorrectos")

# =======================
# APP PRINCIPAL
# =======================
if st.session_state.get("logged_in"):
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email") or "Usuario"
    st.sidebar.title(f"Bienvenido {nombre_usuario}")
    st.sidebar.button("Cerrar sesión", on_click=logout)

    # =======================
    # MENÚ LATERAL
    # =======================
    opciones = ["Usuarios y Empresas", "Acciones Formativas", "Grupos", "Participantes", "Documentos"]
    menu = st.sidebar.radio("Menú", opciones)

    # =======================
    # PANEL ADMIN / GESTOR
    # =======================
    if st.session_state.role in ["admin", "gestor"]:
        if menu == "Usuarios y Empresas" and st.session_state.role == "admin":
            from pages.usuarios_empresas import main as usuarios_empresas_page
            usuarios_empresas_page(supabase, st.session_state)
        elif menu == "Usuarios y Empresas" and st.session_state.role == "gestor":
            from pages.usuarios_empresas import empresas_only as empresas_page
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
