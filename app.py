import streamlit as st
import os
from supabase import create_client, Client
from datetime import datetime

# =======================
# CONFIGURACIÓN PÁGINA
# =======================
st.set_page_config(page_title="Gestor de Formación", page_icon="📚", layout="wide")

# =======================
# CSS PERSONALIZADO
# =======================
st.markdown("""
<style>
/* Botones más redondeados */
.stButton>button {
    border-radius: 8px;
    font-weight: 600;
}

/* Métricas con sombra ligera */
[data-testid="stMetricValue"] {
    font-size: 1.5rem;
    font-weight: bold;
}

/* Sidebar más ancho y con título destacado */
section[data-testid="stSidebar"] {
    width: 280px !important;
}
section[data-testid="stSidebar"] h1 {
    font-size: 1.2rem;
    font-weight: bold;
    color: #0056b3;
}

/* Tablas con bordes suaves */
.stDataFrame, .stTable {
    border-radius: 6px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

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
            "Gestión de Alumnos",
            "— Gestión ISO 9001 —",
            "No Conformidades (ISO 9001)",
            "Acciones Correctivas (ISO 9001)",
            "Auditorías (ISO 9001)",
            "Indicadores (ISO 9001)",
            "Dashboard Calidad (ISO 9001)"
        ]
    elif st.session_state.role == "gestor":
        opciones = [
            "Grupos",
            "Participantes",
            "Documentos",
            "— Gestión ISO 9001 —",
            "No Conformidades (ISO 9001)",
            "Acciones Correctivas (ISO 9001)",
            "Auditorías (ISO 9001)",
            "Indicadores (ISO 9001)",
            "Dashboard Calidad (ISO 9001)"
        ]
    elif st.session_state.role == "alumno":
        opciones = ["Mis Grupos y Diplomas"]

    menu = st.sidebar.radio("📂 Menú", opciones)

    # Carga de páginas
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

    # =======================
    # Módulos ISO 9001
    # =======================
    elif menu == "No Conformidades (ISO 9001)":
        from pages.no_conformidades import main as nc_page
        st.markdown("### 🚨 Módulo de No Conformidades (ISO 9001)")
        st.caption("Registro, seguimiento y cierre de no conformidades detectadas en procesos, auditorías o inspecciones.")
        nc_page(supabase, st.session_state)

    elif menu == "Acciones Correctivas (ISO 9001)":
        from pages.acciones_correctivas import main as ac_page
        st.markdown("### 🛠️ Módulo de Acciones Correctivas (ISO 9001)")
        st.caption("Planificación, ejecución y seguimiento de acciones correctivas vinculadas a no conformidades.")
        ac_page(supabase, st.session_state)

    elif menu == "Auditorías (ISO 9001)":
        from pages.auditorias import main as auditorias_page
        st.markdown("### 📋 Módulo de Auditorías (ISO 9001)")
        st.caption("Planificación y registro de auditorías internas y externas, con vinculación a hallazgos y no conformidades.")
        auditorias_page(supabase, st.session_state)

    elif menu == "Indicadores (ISO 9001)":
        from pages.indicadores import main as indicadores_page
        st.markdown("### 📈 Módulo de Indicadores de Calidad (ISO 9001)")
        st.caption("Visualización de métricas clave de calidad: NC, acciones correctivas, auditorías y tiempos de resolución.")
        indicadores_page(supabase, st.session_state)

    elif menu == "Dashboard Calidad (ISO 9001)":
        from pages.dashboard_calidad import main as dashboard_calidad_page
        st.markdown("### 📊 Dashboard de Calidad (ISO 9001)")
        st.caption("Panel visual con KPIs y gráficos para el seguimiento global del sistema de gestión de calidad.")
        dashboard_calidad_page(supabase, st.session_state)
