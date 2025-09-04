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

# URL directa de la imagen de cabecera
IMAGE_URL = "https://images.unsplash.com/photo-1503264116251-35a269479413?auto=format&fit=crop&w=1600&q=80"

# Estilos CSS personalizados
st.markdown("""
    <style>
    .main {
        background-color: #f9f9f9;
        padding: 0;
    }
    .title {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-top: 1rem;
        color: #222;
    }
    .subtitle {
        font-size: 1.2rem;
        text-align: center;
        color: #555;
        margin-bottom: 2rem;
    }
    .feature-title {
        font-size: 1.1rem;
        font-weight: bold;
        color: #333;
        margin-top: 0.5rem;
    }
    .feature-desc {
        font-size: 0.95rem;
        color: #555;
    }
    .stButton>button {
        display: block;
        margin: 0 auto;
        background-color: #4CAF50;
        color: white;
        padding: 0.8rem 2rem;
        font-size: 1.1rem;
        border-radius: 8px;
        border: none;
        cursor: pointer;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
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
    # Imagen y textos de bienvenida
    st.image(IMAGE_URL, use_column_width=True)
    st.markdown('<div class="title">Bienvenido al Gestor de Formación</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Gestiona usuarios, cursos, grupos y documentos de forma profesional</div>', unsafe_allow_html=True)

    # Menú lateral informativo antes del login
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

    # Formulario de login
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

    # Segunda sección: características destacadas
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
        opciones = ["Usuarios y Empresas", "Acciones Formativas", "Grupos", "Participantes", "Documentos", "Tutores"]
    elif st.session_state.role == "gestor":
        opciones = ["Grupos", "Participantes", "Documentos"]

    menu = st.sidebar.radio("Menú", opciones)

    # Panel según rol
    if st.session_state.role == "admin":
        if menu == "Usuarios y Empresas":
            from pages.usuarios_empresas import main as usuarios_empresas_page
            usuarios_empresas_page(supabase, st.session_state)
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

