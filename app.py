import os, sys
import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Gestor de Formación",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Estado inicial
for key, default in {
    "page": "home",
    "role": None,
    "user": {},
    "auth_session": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

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
            # Si es comercial, buscar su id en la tabla comerciales
            if st.session_state.role == "comercial":
                com_res = supabase_public.table("comerciales").select("id").eq("usuario_id", row.get("id")).execute()
                if com_res.data:
                    st.session_state.user["comercial_id"] = com_res.data[0]["id"]
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
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap');
            html, body, [class*="css"] {
                font-family: 'Roboto', sans-serif;
                background-color: #f5f5f5;
            }
            .module-card {
                background-color: white;
                padding: 1em;
                border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 1em;
            }
            .module-card h4 {
                margin: 0;
                color: #4285F4;
            }
            .module-card p {
                margin: 0.5em 0 0;
                color: #5f6368;
            }
        </style>
        <div class="module-card"><h4>📚 Formación Bonificada</h4><p>Gestión de acciones formativas y documentos FUNDAE.</p></div>
        <div class="module-card"><h4>📋 ISO 9001</h4><p>Auditorías, informes y seguimiento de calidad.</p></div>
        <div class="module-card"><h4>🔐 RGPD</h4><p>Consentimientos, documentación legal y trazabilidad.</p></div>
    """, unsafe_allow_html=True)

    st.markdown("### 🔐 Iniciar sesión")
    st.caption("Accede al gestor con tus credenciales.")

    with st.form("form_login_acceso", clear_on_submit=False):
        email = st.text_input("Email", autocomplete="email")
        password = st.text_input("Contraseña", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        if not email or not password:
            st.warning("Introduce email y contraseña.")
        else:
            try:
                auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
                if not auth or not auth.user:
                    st.error("Credenciales inválidas.")
                else:
                    st.session_state.auth_session = auth
                    set_user_role_from_db(auth.user.email)
                    st.experimental_rerun()
            except Exception as e:
                st.error(f"Error al iniciar sesión: {e}")

# =========================
# Sidebar y navegación
# =========================
def route():
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email")
    st.sidebar.markdown(f"### 👋 Bienvenido, **{nombre_usuario}**")

    if st.sidebar.button("🚪 Cerrar sesión"):
        do_logout()

    menu_iso = {
        "No Conformidades": "no_conformidades",
        "Acciones Correctivas": "acciones_correctivas",
        "Auditorías": "auditorias",
        "Indicadores": "indicadores",
        "Dashboard Calidad": "dashboard_calidad",
        "Objetivos de Calidad": "objetivos_calidad",
        "Informe Auditoría": "informe_auditoria"
    }

    if st.session_state.role == "admin":
        st.sidebar.markdown("#### 🧭 Navegación")
        menu_admin = {
            "Panel de Alertas": "panel_admin",
            "Usuarios y Empresas": "usuarios_empresas",
            "Empresas": "empresas",
            "Acciones Formativas": "acciones_formativas",
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Documentos": "documentos",
            "Tutores": "tutores"
        }
        for label, page_key in menu_admin.items():
            if st.sidebar.button(label):
                st.session_state.page = page_key

        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📏 Gestión ISO 9001")
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

        empresa_id = st.session_state.user.get("empresa_id")
        empresa_res = supabase_admin.table("empresas").select(
            "iso_activo", "iso_inicio", "iso_fin",
            "rgpd_activo", "rgpd_inicio", "rgpd_fin",
            "crm_activo", "crm_inicio", "crm_fin"
        ).eq("id", empresa_id).execute()
        empresa = empresa_res.data[0] if empresa_res.data else {}
        hoy = datetime.today().date()

        # --- ISO ---
        iso_permitido = (
            empresa.get("iso_activo") and
            (empresa.get("iso_inicio") is None or pd.to_datetime(empresa["iso_inicio"]).date() <= hoy) and
            (empresa.get("iso_fin") is None or pd.to_datetime(empresa["iso_fin"]).date() >= hoy)
        )
        if iso_permitido:
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📏 Gestión ISO 9001")
            for label, page_key in menu_iso.items():
                if st.sidebar.button(label):
                    st.session_state.page = page_key

        # --- RGPD ---
        rgpd_permitido = (
            empresa.get("rgpd_activo") and
            (empresa.get("rgpd_inicio") is None or pd.to_datetime(empresa["rgpd_inicio"]).date() <= hoy) and
            (empresa.get("rgpd_fin") is None or pd.to_datetime(empresa["rgpd_fin"]).date() >= hoy)
        )
        if rgpd_permitido:
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 🛡️ Gestión RGPD")
            rgpd_menu = {
                "Panel RGPD": "rgpd_panel",
                "Diagnóstico Inicial": "rgpd_inicio",
                "Tratamientos": "rgpd_tratamientos",
                "Cláusulas y Consentimientos": "rgpd_consentimientos",
                "Encargados del Tratamiento": "rgpd_encargados",
                "Derechos de los Interesados": "rgpd_derechos",
                "Evaluación de Impacto": "rgpd_evaluacion",
                "Medidas de Seguridad": "rgpd_medidas",
                "Incidencias": "rgpd_incidencias"
            }
            for label, page_key in rgpd_menu.items():
                if st.sidebar.button(label):
                    st.session_state.page = page_key

        # --- CRM ---
        crm_permitido = (
            empresa.get("crm_activo") and
            (empresa.get("crm_inicio") is None or pd.to_datetime(empresa["crm_inicio"]).date() <= hoy) and
            (empresa.get("crm_fin") is None or pd.to_datetime(empresa["crm_fin"]).date() >= hoy)
        )
        if crm_permitido:
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📈 Gestión CRM")
            crm_menu = {
                "Panel CRM": "crm_panel",
                "Clientes": "crm_clientes",
                "Oportunidades": "crm_oportunidades",
                "Tareas y Seguimiento": "crm_tareas",
                "Comunicaciones": "crm_comunicaciones",
                "Campañas": "crm_campanas"
            }
            for label, page_key in crm_menu.items():
                if st.sidebar.button(label):
                    st.session_state.page = page_key

    # --- Comercial ---
    elif st.session_state.role == "comercial":
        st.sidebar.markdown("#### 📈 Módulo CRM")
        crm_menu = {
            "Panel CRM": "crm_panel",
            "Mis Clientes": "crm_clientes",
            "Mis Oportunidades": "crm_oportunidades",
            "Mis Tareas": "crm_tareas",
            "Mis Comunicaciones": "crm_comunicaciones",
            "Mis Estadísticas": "crm_estadisticas"
        }
        for label, page_key in crm_menu.items():
            if st.sidebar.button(label):
                st.session_state.page = page_key

    elif st.session_state.role == "alumno":
        st.sidebar.markdown("#### 🎓 Área del Alumno")
        if st.sidebar.button("Mis Grupos y Diplomas"):
            st.session_state.page = "mis_grupos"

    st.sidebar.markdown("---")
    st.sidebar.caption("© 2025 Gestor de Formación · ISO 9001 · RGPD · CRM · Streamlit + Supabase")

# =========================
# Ejecución principal
# =========================
if not st.session_state.role:
    login_view()
else:
    route()
    page = st.session_state.get("page", None)

    try:
        if page == "usuarios_empresas":
            from pages.usuarios_empresas import main as usuarios_empresas_page
            usuarios_empresas_page(supabase_admin, st.session_state)
        elif page == "panel_admin":
            from pages.panel_admin import main as panel_admin_page
            panel_admin_page(supabase_admin, st.session_state)
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
            from pages.no_conformidades import main as no_conformidades_page
            no_conformidades_page(supabase_admin, st.session_state)
        elif page == "acciones_correctivas":
            from pages.acciones_correctivas import main as acciones_correctivas_page
            acciones_correctivas_page(supabase_admin, st.session_state)
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
            from pages.objetivos_calidad import main as objetivos_calidad_page
            objetivos_calidad_page(supabase_admin, st.session_state)
        elif page == "informe_auditoria":
            from pages.informe_auditoria import main as informe_auditoria_page
            informe_auditoria_page(supabase_admin, st.session_state)
        elif page == "rgpd_panel":
            from pages.rgpd_panel import main as rgpd_panel_page
            rgpd_panel_page(supabase_admin, st.session_state)
        elif page == "rgpd_inicio":
            from pages.rgpd_inicio import main as rgpd_inicio_page
            rgpd_inicio_page(supabase_admin, st.session_state)
        elif page == "rgpd_tratamientos":
            from pages.rgpd_tratamientos import main as rgpd_tratamientos_page
            rgpd_tratamientos_page(supabase_admin, st.session_state)
        elif page == "rgpd_consentimientos":
            from pages.rgpd_consentimientos import main as rgpd_consentimientos_page
            rgpd_consentimientos_page(supabase_admin, st.session_state)
        elif page == "rgpd_encargados":
            from pages.rgpd_encargados import main as rgpd_encargados_page
            rgpd_encargados_page(supabase_admin, st.session_state)
        elif page == "rgpd_derechos":
            from pages.rgpd_derechos import main as rgpd_derechos_page
            rgpd_derechos_page(supabase_admin, st.session_state)
        elif page == "rgpd_evaluacion":
            from pages.rgpd_evaluacion import main as rgpd_evaluacion_page
            rgpd_evaluacion_page(supabase_admin, st.session_state)
        elif page == "rgpd_medidas":
            from pages.rgpd_medidas import main as rgpd_medidas_page
            rgpd_medidas_page(supabase_admin, st.session_state)
        elif page == "rgpd_incidencias":
            from pages.rgpd_incidencias import main as rgpd_incidencias_page
            rgpd_incidencias_page(supabase_admin, st.session_state)
        elif page == "crm_panel":
            from pages.crm_panel import main as crm_panel_page
            crm_panel_page(supabase_admin, st.session_state)
        elif page == "crm_clientes":
            from pages.crm_clientes import main as crm_clientes_page
            crm_clientes_page(supabase_admin, st.session_state)
        elif page == "crm_oportunidades":
            from pages.crm_oportunidades import main as crm_oportunidades_page
            crm_oportunidades_page(supabase_admin, st.session_state)
        elif page == "crm_tareas":
            from pages.crm_tareas import main as crm_tareas_page
            crm_tareas_page(supabase_admin, st.session_state)
        elif page == "crm_comunicaciones":
            from pages.crm_comunicaciones import main as crm_comunicaciones_page
            crm_comunicaciones_page(supabase_admin, st.session_state)
        elif page == "crm_estadisticas":
            from pages.crm_estadisticas import main as crm_estadisticas_page
            crm_estadisticas_page(supabase_admin, st.session_state)
        elif page == "crm_campanas":
            from pages.crm_campanas import main as crm_campanas_page
            crm_campanas_page(supabase_admin, st.session_state)
        elif page == "mis_grupos":
            from pages.mis_grupos import main as mis_grupos_page
            mis_grupos_page(supabase_public, st.session_state)
        else:
            rol = st.session_state.role
            if rol == "admin":
                st.title("🛠 Panel de Administración")
                st.caption("Gestiona usuarios, empresas y módulos avanzados.")
            elif rol == "gestor":
                st.title("📚 Panel de Formación Bonificada")
                st.caption("Accede a tus grupos, participantes y documentos.")
            elif rol == "alumno":
                st.title("🎓 Área del Alumno")
                st.caption("Consulta tus grupos, diplomas y seguimiento formativo.")
            elif rol == "comercial":
                st.title("📈 Módulo CRM")
                st.caption("Gestiona tus clientes, oportunidades y tareas asignadas.")
            else:
                st.title("🏠 Bienvenido al Gestor de Formación")
                st.caption("Usa el menú lateral para navegar por las secciones disponibles.")
    except Exception as e:
        st.error(f"❌ Error al cargar la página '{page or 'inicio'}': {e}")
