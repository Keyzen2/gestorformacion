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
# CONFIGURACIÓN PÁGINA
# =======================
st.set_page_config(
    page_title="Gestor de Formación",
    page_icon="🚀",
    layout="wide"
)

# =======================
# ESTILOS PERSONALIZADOS
# =======================
st.markdown("""
    <style>
    .main { background-color: #f9f9f9; padding: 0; }
    .title { font-size: 2.2rem; font-weight: bold; text-align: center; margin-top: 0.5rem; color: #222; }
    .subtitle { font-size: 1.1rem; text-align: center; color: #555; margin-bottom: 1.5rem; }
    .feature-title { font-size: 1rem; font-weight: bold; color: #333; margin-top: 0.5rem; text-align: center; }
    .feature-desc { font-size: 0.9rem; color: #555; text-align: center; }
    .stButton>button {
        display: block; margin: 0 auto;
        background-color: #4CAF50; color: white;
        padding: 0.6rem 1.5rem; font-size: 1rem;
        border-radius: 8px; border: none; cursor: pointer;
    }
    .stButton>button:hover { background-color: #45a049; }
    </style>
""", unsafe_allow_html=True)

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
# LOGIN + LANDING
# =======================
if not st.session_state.logged_in:
    st.sidebar.title("ℹ️ Información de la App")
    st.sidebar.markdown("""
    **Usuarios y Empresas**  
    Gestiona usuarios y empresas asociadas.

    **Acciones Formativas**  
    Crea y administra cursos y formaciones.

    **Grupos**  
    Organiza grupos de alumnos y tutores.

    **Participantes**  
    Alta y seguimiento de alumnos.

    **Documentos**  
    Genera PDFs y XML oficiales.

    **Tutores**  
    Gestiona tutores internos y externos.
    """)

    col_central = st.container()
    with col_central:
        st.markdown('<div class="title">Bienvenido al Gestor de Formación</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtitle">Gestiona usuarios, cursos, grupos y documentos de forma profesional</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Usuario (email/CIF)")
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
                        st.error("Usuario no registrado en la tabla interna")
                else:
                    st.error("Usuario o contraseña incorrectos")
            except Exception as e:
                st.error(f"Error de login: {e}")

        st.markdown("---")
        st.markdown("### Ventajas de nuestra plataforma")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=60)
            st.markdown('<div class="feature-title">Gestión Integral</div>', unsafe_allow_html=True)
            st.markdown('<div class="feature-desc">Administra usuarios, empresas, cursos y documentos desde un único lugar.</div>', unsafe_allow_html=True)

        with col2:
            st.image("https://cdn-icons-png.flaticon.com/512/1828/1828640.png", width=60)
            st.markdown('<div class="feature-title">Automatización</div>', unsafe_allow_html=True)
            st.markdown('<div class="feature-desc">Genera PDFs y XML oficiales en segundos, sin errores manuales.</div>', unsafe_allow_html=True)

        with col3:
            st.image("https://cdn-icons-png.flaticon.com/512/992/992651.png", width=60)
            st.markdown('<div class="feature-title">Acceso Seguro</div>', unsafe_allow_html=True)
            st.markdown('<div class="feature-desc">Protege la información con autenticación y roles personalizados.</div>', unsafe_allow_html=True)

# =======================
# APP PRINCIPAL
# =======================
if st.session_state.get("logged_in"):
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email") or "Usuario"
    st.sidebar.title(f"Bienvenido {nombre_usuario}")
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

    menu = st.sidebar.radio("Menú", opciones)

    # Panel según rol
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


