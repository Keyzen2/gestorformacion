import os
import sys
import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# =========================
# Configuración de la página
# =========================
st.set_page_config(
    page_title="Gestor de Formación",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

# =========================
# Claves Supabase
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# =========================
# Estado inicial
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
    st.rerun()


def login_view():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; background-color: #f5f5f5'; }
    .module-card { background-color: white; padding: 1em; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 1em; }
    .module-card h4 { margin: 0; color: #4285F4; }
    .module-card p { margin: 0.5em 0 0; color: #5f6368; }
    </style>
    <div class="module-card"><h4>📚 Formación Bonificada</h4><p>Gestión de acciones formativas y documentos FUNDAE.</p></div>
    <div class="module-card"><h4>📋 ISO 9001</h4><p>Auditorías, informes y seguimiento de calidad.</p></div>
    <div class="module-card"><h4>🔐 RGPD</h4><p>Consentimientos, documentación legal y trazabilidad.</p></div>
    <div class="module-card"><h4>📈 CRM</h4><p>Gestión de clientes, oportunidades y tareas comerciales.</p></div>
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
                    st.rerun()
            except Exception as e:
                st.error(f"Error al iniciar sesión: {e}")


# =========================
# Función de verificación de módulo activo (revisada)
# =========================
def is_module_active(empresa, empresa_crm, key, hoy, role):
    # Los alumnos nunca ven módulos
    if role == "alumno":
        return False

    if key == "iso":
        if not empresa.get("iso_activo"):
            return False
        inicio = empresa.get("iso_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        # Si quieres que la fecha fin bloquee, descomenta:
        # fin = empresa.get("iso_fin")
        # if fin and pd.to_datetime(fin).date() < hoy:
        #     return False
        return True

    elif key == "rgpd":
        if not empresa.get("rgpd_activo"):
            return False
        inicio = empresa.get("rgpd_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        # fin = empresa.get("rgpd_fin")
        # if fin and pd.to_datetime(fin).date() < hoy:
        #     return False
        return True

    elif key == "crm":
        if not empresa_crm.get("crm_activo"):
            return False
        inicio = empresa_crm.get("crm_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        # fin = empresa_crm.get("crm_fin")
        # if fin and pd.to_datetime(fin).date() < hoy:
        #     return False
        return True

    return False

# =========================
# Función de tarjetas para dashboard
# =========================
def tarjeta(icono, titulo, descripcion, activo=True, color_activo="#d1fae5"):
    color = color_activo if activo else "#f3f4f6"  # verde si activo, gris si no
    return f"""
    <div style="
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 15px;
        background-color: {color};
        box-shadow: 0px 2px 6px rgba(0,0,0,0.1);
    ">
        <h3 style="margin:0;">{icono} {titulo}</h3>
        <p style="margin:0; color:#374151;">{descripcion}</p>
    </div>
    """

# =========================
# Sidebar y navegación
# =========================
def route():
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email")
    st.sidebar.markdown(f"### 👋 Bienvenido, **{nombre_usuario}**")

    if st.sidebar.button("🚪 Cerrar sesión", key="logout"):
        do_logout()

    empresa_id = st.session_state.user.get("empresa_id")
    empresa = {}
    empresa_crm = {}
    hoy = datetime.today().date()
    if empresa_id:
        empresa_res = supabase_admin.table(
            "empresas"
        ).select("iso_activo", "iso_inicio", "iso_fin", "rgpd_activo", "rgpd_inicio", "rgpd_fin").eq("id", empresa_id).execute()
        empresa = empresa_res.data[0] if empresa_res.data else {}
        crm_res = supabase_admin.table(
            "crm_empresas"
        ).select("crm_activo", "crm_inicio", "crm_fin").eq("empresa_id", empresa_id).execute()
        empresa_crm = crm_res.data[0] if crm_res.data else {}

    role = st.session_state.role

    # --- Menú base por rol ---
    if role == "admin":
        st.sidebar.markdown("#### 🧭 Navegación")
        base_menu = {
            "Panel de Alertas": "panel_admin",
            "Usuarios y Empresas": "usuarios_empresas",
            "Empresas": "empresas",
            "Acciones Formativas": "acciones_formativas",
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Documentos": "documentos",
            "Tutores": "tutores"
        }
        for label, page_key in base_menu.items():
            if st.sidebar.button(label, key=f"{page_key}_{role}"):
                st.session_state.page = page_key

    elif role == "gestor":
        st.sidebar.markdown("#### 🧭 Navegación")
        base_menu = {
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Documentos": "documentos"
        }
        for label, page_key in base_menu.items():
            if st.sidebar.button(label, key=f"{page_key}_{role}"):
                st.session_state.page = page_key

    elif role == "alumno":
        st.sidebar.markdown("#### 🎓 Área del Alumno")
        if st.sidebar.button("Mis Grupos y Diplomas", key="mis_grupos"):
            st.session_state.page = "mis_grupos"

    elif role == "comercial":
        pass  # CRM se añade más abajo

    # --- Módulos activos ---
    if role in ["admin", "gestor"]:
        if is_module_active(empresa, empresa_crm, "iso", hoy, role):
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📏 Gestión ISO 9001")
            iso_menu = {
                "No Conformidades": "no_conformidades",
                "Acciones Correctivas": "acciones_correctivas",
                "Auditorías": "auditorias",
                "Indicadores": "indicadores",
                "Dashboard Calidad": "dashboard_calidad",
                "Objetivos de Calidad": "objetivos_calidad",
                "Informe Auditoría": "informe_auditoria"
            }
            for label, page_key in iso_menu.items():
                if st.sidebar.button(label, key=f"{page_key}_{role}"):
                    st.session_state.page = page_key

        if is_module_active(empresa, empresa_crm, "rgpd", hoy, role):
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 🛡️ Gestión RGPD")
            rgpd_menu = {
                "Panel RGPD": "rgpd_panel",
                "Tareas RGPD": "rgpd_planner",
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
                if st.sidebar.button(label, key=f"{page_key}_{role}"):
                    st.session_state.page = page_key

    # CRM para admin, gestor y comercial si está activo
    if is_module_active(empresa, empresa_crm, "crm", hoy, role) or role in ["comercial", "admin", "gestor"]:
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📈 Gestión CRM")
        crm_menu = {
            "Panel CRM": "crm_panel",
            "Clientes": "crm_clientes",
            "Oportunidades": "crm_oportunidades",
            "Tareas y Seguimiento": "crm_tareas",
            "Comunicaciones": "crm_comunicaciones",
            "Estadísticas": "crm_estadisticas"
        }
        for label, page_key in crm_menu.items():
            if st.sidebar.button(label, key=f"{page_key}_{role}"):
                st.session_state.page = page_key

    st.sidebar.markdown("---")
    st.sidebar.caption("© 2025 Gestor de Formación · ISO 9001 · RGPD · CRM · Streamlit + Supabase")

# =========================
# Ejecución principal
# =========================
if not st.session_state.role:
    login_view()
else:
    route()
    page = st.session_state.get("page", None)

    try:
        if page and page != "home":
            mod = page.replace("-", "_")
            mod_path = f"pages.{mod}"
            mod_import = __import__(mod_path, fromlist=["main"])
            mod_import.main(supabase_admin, st.session_state)
        else:
            rol = st.session_state.role
            hoy = datetime.today().date()
            st.title("👋 Bienvenido al Gestor de Formación")

            # ===============================
            # MÉTRICAS DINÁMICAS PARA ADMIN Y GESTOR
            # ===============================
            if rol in ["admin", "gestor"]:
                try:
                    total_empresas = supabase_admin.table("empresas").select("*").execute().count or 0
                    total_usuarios = supabase_admin.table("usuarios").select("*").execute().count or 0
                    total_cursos = supabase_admin.table("acciones_formativas").select("*").execute().count or 0
                except:
                    total_empresas = total_usuarios = total_cursos = 0

                st.subheader("📊 Métricas del sistema")
                col1, col2, col3 = st.columns(3)
                col1.markdown(tarjeta("🏢", "Empresas", f"Número total de empresas: {total_empresas}"), unsafe_allow_html=True)
                col2.markdown(tarjeta("👤", "Usuarios", f"Número total de usuarios: {total_usuarios}"), unsafe_allow_html=True)
                col3.markdown(tarjeta("📚", "Cursos activos", f"Número total de cursos/acciones formativas: {total_cursos}"), unsafe_allow_html=True)

            # ===============================
            # BIENVENIDA SEGÚN ROL
            # ===============================
            if rol == "admin":
                st.subheader("🛠 Panel de Administración")
                st.markdown(tarjeta("👤", "Usuarios", "Alta, gestión y permisos de usuarios."), unsafe_allow_html=True)
                st.markdown(tarjeta("🏢", "Empresas", "Gestión de empresas y sus módulos."), unsafe_allow_html=True)
                st.markdown(tarjeta("⚙️", "Módulos avanzados", "ISO, RGPD, CRM y configuración general."), unsafe_allow_html=True)

            elif rol == "gestor":
                st.subheader("📚 Panel del Gestor")
                st.markdown(tarjeta("👥", "Grupos y participantes", "Crea y gestiona grupos de alumnos."), unsafe_allow_html=True)
                st.markdown(tarjeta("📄", "Documentación", "Sube y organiza la documentación de formación."), unsafe_allow_html=True)

                st.subheader("📦 Módulos disponibles")
                st.markdown(tarjeta("✅", "ISO", "Gestión documental ISO y auditorías.", activo=is_module_active(empresa, empresa_crm, "iso", hoy)), unsafe_allow_html=True)
                st.markdown(tarjeta("🔒", "RGPD", "Control de protección de datos y consentimientos.", activo=is_module_active(empresa, empresa_crm, "rgpd", hoy)), unsafe_allow_html=True)
                st.markdown(tarjeta("📈", "CRM", "Gestión de clientes y oportunidades comerciales.", activo=is_module_active(empresa, empresa_crm, "crm", hoy)), unsafe_allow_html=True)

            elif rol == "alumno":
                st.subheader("🎓 Área del Alumno")
                st.markdown(tarjeta("👥", "Mis grupos", "Consulta a qué grupos perteneces."), unsafe_allow_html=True)
                st.markdown(tarjeta("📜", "Diplomas", "Descarga tus diplomas disponibles."), unsafe_allow_html=True)
                st.markdown(tarjeta("📊", "Seguimiento", "Accede al progreso de tu formación."), unsafe_allow_html=True)

            elif rol == "comercial":
                st.subheader("📈 Área Comercial - CRM")
                st.markdown(tarjeta("👤", "Clientes", "Consulta y gestiona tu cartera de clientes."), unsafe_allow_html=True)
                st.markdown(tarjeta("📝", "Oportunidades", "Registra y da seguimiento a nuevas oportunidades."), unsafe_allow_html=True)
                st.markdown(tarjeta("📅", "Tareas", "Organiza tus visitas y recordatorios."), unsafe_allow_html=True)

            else:
                st.subheader("🏠 Inicio")
                st.markdown("Usa el menú lateral para navegar por las secciones disponibles.")

    except Exception as e:
        st.error(f"❌ Error al cargar la página '{page or 'inicio'}': {e}")
