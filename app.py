import streamlit as st
import os
from supabase import create_client, Client
from datetime import datetime

# =======================
# CONFIGURACIÓN PÁGINA
# =======================
st.set_page_config(
    page_title="Gestor de Formación",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
    # CSS para ocultar menú y centrar login
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;}
    header[data-testid="stHeader"] {display: none;}
    footer {display: none;}
    #MainMenu {visibility: hidden;}
    .main {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
    }
    .login-container {
        width: 100%;
        max-width: 380px;
        padding: 2rem;
        background-color: white;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

    # Contenedor del login
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.title("🔐 Acceso al Gestor de Formación")

    with st.form("login_form"):
        email = st.text_input("📧 Email")
        password = st.text_input("🔑 Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")
    st.markdown('</div>', unsafe_allow_html=True)

    # Footer corporativo
    st.markdown(
        """
        <div style='text-align:center; margin-top: 2rem; font-size: 0.85rem; color: #666;'>
            © 2025 Centro de Formación - Sistema de Gestión de Calidad ISO 9001
        </div>
        """,
        unsafe_allow_html=True
    )

    # Validación y login
    if submitted:
        if not email or not password:
            st.error("⚠️ Por favor, introduce tu email y contraseña.")
        else:
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
                        st.error("❌ Usuario no registrado en la base de datos interna.")
                else:
                    st.error("❌ Credenciales incorrectas.")
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

    menu = st.sidebar.radio("📂 Menú", opciones)

    # Carga de páginas
    if menu.startswith("👥 Usuarios"):
        from pages.usuarios_empresas import main as usuarios_empresas_page
        usuarios_empresas_page(supabase, st.session_state)

    elif menu.startswith("🏢 Empresas"):
        from pages.empresas import main as empresas_page
        empresas_page(supabase, st.session_state)

    elif menu.startswith("📚 Acciones Formativas"):
        from pages.acciones_formativas import main as acciones_page
        acciones_page(supabase, st.session_state)

    elif menu.startswith("👨‍🏫 Grupos"):
        from pages.grupos import main as grupos_page
        grupos_page(supabase, st.session_state)

    elif menu.startswith("🧑‍🎓 Participantes"):
        from pages.participantes import main as participantes_page
        participantes_page(supabase, st.session_state)

    elif menu.startswith("📄 Documentos"):
        from pages.documentos import main as documentos_page
        documentos_page(supabase, st.session_state)

    elif menu.startswith("🎓 Tutores"):
        from pages.tutores import main as tutores_page
        tutores_page(supabase, st.session_state)

    elif menu.startswith("📋 Gestión de Alumnos"):
        from pages.participantes import main as participantes_page
        participantes_page(supabase, st.session_state)

    # Módulos ISO 9001
    elif menu.startswith("🚨 No Conformidades"):
        from pages.no_conformidades import main as nc_page
        st.markdown("### 🚨 Módulo de No Conformidades (ISO 9001)")
        st.caption("Registro, seguimiento y cierre de no conformidades detectadas en procesos, auditorías o inspecciones.")
        nc_page(supabase, st.session_state)

    elif menu.startswith("🛠️ Acciones Correctivas"):
        from pages.acciones_correctivas import main as ac_page
        st.markdown("### 🛠️ Módulo de Acciones Correctivas (ISO 9001)")
        st.caption("Planificación, ejecución y seguimiento de acciones correctivas vinculadas a no conformidades.")
        ac_page(supabase, st.session_state)

    elif menu.startswith("📋 Auditorías"):
        from pages.auditorias import main as auditorias_page
        st.markdown("### 📋 Módulo de Auditorías (ISO 9001)")
        st.caption("Planificación y registro de auditorías internas y externas, con vinculación a hallazgos y no conformidades.")
        auditorias_page(supabase, st.session_state)

    elif menu.startswith("📈 Indicadores"):
        from pages.indicadores import main as indicadores_page
        st.markdown("### 📈 Módulo de Indicadores de Calidad (ISO 9001)")
        st.caption("Visualización de métricas clave de calidad: NC, acciones correctivas, auditorías y tiempos de resolución.")
        indicadores_page(supabase, st.session_state)

    elif menu.startswith("📊 Dashboard Calidad"):
        from pages.dashboard_calidad import main as dashboard_calidad_page
        st.markdown("### 📊 Dashboard de Calidad (ISO 9001)")
        st.caption("Panel visual con KPIs y gráficos para el seguimiento global del sistema de gestión de calidad.")
        dashboard_calidad_page(supabase, st.session_state)

    elif menu.startswith
        elif menu.startswith("🎯 Objetivos de Calidad"):
        from pages.objetivos_calidad import main as objetivos_page
        st.markdown("### 🎯 Objetivos de Calidad (ISO 9001)")
        st.caption("Definición, seguimiento y evaluación de objetivos anuales de calidad para el centro de formación.")
        objetivos_page(supabase, st.session_state)
            
