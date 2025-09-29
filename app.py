import os
import sys
import streamlit as st
from utils import get_ajustes_app
from supabase import create_client
from datetime import datetime
import pandas as pd
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# =========================
# Configuración de la página
# =========================
st.set_page_config(
    page_title="Gestor de Formación",
    layout="wide",
    initial_sidebar_state="auto",
    page_icon="📚",
    menu_items=None
)

# =========================
# CSS MODERNO Y LIMPIO
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

#MainMenu, footer, .stDeployButton, header[data-testid="stHeader"] {
    display: none !important;
}
[data-testid="stToolbar"] {
    display: none !important;
}

.login-mode section[data-testid="stSidebar"],
.login-mode button[data-testid="collapsedControl"] {
    display: none !important;
}
.app-mode section[data-testid="stSidebar"] {
    display: flex !important;
    background: #f8fafc !important;
    border-right: 1px solid #e2e8f0 !important;
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.stApp { background: #ffffff; }
.login-mode .stApp {
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    min-height: 100vh;
}

.block-container {
    padding-top: 2rem !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
    max-width: 1400px !important;
}

.login-container {
    background: white;
    border-radius: 16px;
    padding: 3rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    max-width: 420px;
    margin: 4rem auto;
}
.login-header { text-align: center; margin-bottom: 2rem; }
.login-logo {
    width: 64px; height: 64px;
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
    border-radius: 12px;
    margin: 0 auto 1.5rem;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.75rem; color: white;
}
.login-title {
    font-size: 1.75rem; font-weight: 700;
    color: #1e293b; margin-bottom: 0.5rem;
}
.login-subtitle { color: #64748b; font-size: 0.95rem; }

.stTextInput > div > div > input {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 0.75rem 1rem;
    font-size: 0.95rem; transition: all 0.2s ease;
}
.stTextInput > div > div > input:focus {
    border-color: #3b82f6; background: white;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.stButton > button {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white; border: none; border-radius: 8px;
    padding: 0.75rem 1.5rem; font-weight: 600;
    font-size: 0.95rem; transition: all 0.2s ease;
    width: 100%; margin-top: 0.5rem;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.metric-card {
    background: white; border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 1.5rem;
    transition: all 0.2s ease;
}
.metric-card:hover {
    border-color: #cbd5e1;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
.metric-icon {
    width: 48px; height: 48px;
    background: #eff6ff; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem; margin-bottom: 1rem;
}
.metric-label { font-size: 0.875rem; color: #64748b; font-weight: 500; margin-bottom: 0.5rem; }
.metric-value { font-size: 2rem; font-weight: 700; color: #1e293b; }

.stAlert { border-radius: 8px; border-left: 4px solid; }
.stSuccess { border-left-color: #10b981; background: #ecfdf5; }
.stError { border-left-color: #ef4444; background: #fef2f2; }
.stInfo { border-left-color: #3b82f6; background: #eff6ff; }
.stWarning { border-left-color: #f59e0b; background: #fffbeb; }

@media (max-width: 768px) {
    .login-container { margin: 2rem 1rem; padding: 2rem; }
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.fade-in { animation: fadeIn 0.4s ease-out; }
</style>
""", unsafe_allow_html=True)
# =========================
# Claves Supabase
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("⚠️ Error: Variables de Supabase no configuradas correctamente")
    st.stop()

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else None

# =========================
# Estado inicial
# =========================
for key, default in {
    "page": "home",
    "role": None,
    "user": {},
    "auth_session": None,
    "login_loading": False
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =========================
# CSS Dinámico según estado de login
# =========================
if st.session_state.get("auth_session"):
    st.markdown('<div class="app-mode">', unsafe_allow_html=True)
else:
    st.markdown('<div class="login-mode">', unsafe_allow_html=True)

# =========================
# Funciones auxiliares
# =========================
@st.cache_data(ttl=300)
def get_metricas_admin():
    """Obtiene métricas del admin de forma optimizada."""
    try:
        total_empresas = supabase_admin.rpc('count_table_rows', {'table_name': 'empresas'}).execute().data or 0
        total_usuarios = supabase_admin.rpc('count_table_rows', {'table_name': 'usuarios'}).execute().data or 0
        total_cursos = supabase_admin.rpc('count_table_rows', {'table_name': 'acciones_formativas'}).execute().data or 0
        total_grupos = supabase_admin.rpc('count_table_rows', {'table_name': 'grupos'}).execute().data or 0
        
        return {
            "empresas": total_empresas,
            "usuarios": total_usuarios,
            "cursos": total_cursos,
            "grupos": total_grupos
        }
    except Exception:
        empresas_res = supabase_admin.table("empresas").select("id", count="exact").execute()
        usuarios_res = supabase_admin.table("usuarios").select("id", count="exact").execute()
        cursos_res = supabase_admin.table("acciones_formativas").select("id", count="exact").execute()
        grupos_res = supabase_admin.table("grupos").select("id", count="exact").execute()
        
        return {
            "empresas": empresas_res.count or 0,
            "usuarios": usuarios_res.count or 0,
            "cursos": cursos_res.count or 0,
            "grupos": grupos_res.count or 0
        }

@st.cache_data(ttl=300)
def get_metricas_gestor(empresa_id):
    """Obtiene métricas del gestor de forma optimizada."""
    try:
        grupos_res = supabase_admin.table("grupos").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        participantes_res = supabase_admin.table("participantes").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        documentos_res = supabase_admin.table("documentos").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        
        return {
            "grupos": grupos_res.count or 0,
            "participantes": participantes_res.count or 0,
            "documentos": documentos_res.count or 0
        }
    except Exception:
        return {"grupos": 0, "participantes": 0, "documentos": 0}

def set_user_role_from_db(email: str):
    """Obtiene el rol y datos básicos del usuario desde la base de datos."""
    try:
        clean_email = email.strip().lower()
        res = supabase_public.table("usuarios").select("*").eq("email", clean_email).limit(1).execute()
        if res.data:
            row = res.data[0]
            rol = row.get("rol") or "alumno"
            st.session_state.role = rol
            st.session_state.user = {
                "id": row.get("id"),
                "auth_id": row.get("auth_id"),
                "email": row.get("email"),
                "nombre": row.get("nombre"),
                "empresa_id": row.get("empresa_id")
            }
            if rol == "comercial":
                com_res = supabase_public.table("comerciales").select("id").eq("usuario_id", row.get("id")).execute()
                if com_res.data:
                    st.session_state.user["comercial_id"] = com_res.data[0]["id"]
        else:
            st.session_state.role = "alumno"
            st.session_state.user = {"email": clean_email, "empresa_id": None}
    except Exception as e:
        st.error(f"No se pudo obtener el rol del usuario: {e}")
        st.session_state.role = "alumno"
        st.session_state.user = {"email": email, "empresa_id": None}

def do_logout():
    """Cierra la sesión y limpia el estado."""
    try:
        supabase_public.auth.sign_out()
    except Exception:
        pass
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()
# =========================
# Vista de login LIMPIA Y MODERNA
# =========================
def login_view():
    """Pantalla de login minimalista con logo de empresa, barra de progreso y sidebar oculto."""

    ajustes = get_ajustes_app(supabase_public, campos=[
        "mensaje_login", "nombre_app", "logo_url"
    ])

    mensaje_login = ajustes.get("mensaje_login", "Sistema integral de gestión FUNDAE")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    # ✅ Logo original (recuperado del backup)
    logo_display = (
        f'<img src="{ajustes.get("logo_url")}" width="64" height="64" style="border-radius: 12px;">'
        if ajustes.get("logo_url")
        else "📚"
    )

    # Container principal
    st.markdown(f"""
    <div class="login-container fade-in">
        <div class="login-header">
            <div class="login-logo">{logo_display}</div>
            <h1 class="login-title">{nombre_app}</h1>
            <p class="login-subtitle">{mensaje_login}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Formulario de login centrado
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.form("form_login", clear_on_submit=False):
            st.markdown("#### Iniciar sesión")

            email = st.text_input(
                "Email",
                placeholder="tu@empresa.com",
                label_visibility="collapsed"
            )

            password = st.text_input(
                "Contraseña",
                type="password",
                placeholder="••••••••",
                label_visibility="collapsed"
            )

            submitted = st.form_submit_button(
                "Iniciar sesión" if not st.session_state.get("login_loading") else "Iniciando...",
                disabled=st.session_state.get("login_loading", False),
                use_container_width=True
            )

    # ✅ Barra de progreso mientras intenta login
    if st.session_state.get("login_loading", False):
        st.progress(50, "Verificando credenciales...")

    if submitted:
        if not email or not password:
            st.warning("Por favor, introduce email y contraseña")
        else:
            st.session_state.login_loading = True

            try:
                auth = supabase_public.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })

                if not auth or not auth.user:
                    st.error("Credenciales incorrectas")
                    st.session_state.login_loading = False
                else:
                    st.session_state.auth_session = auth
                    set_user_role_from_db(auth.user.email)
                    st.success("✅ Sesión iniciada correctamente")
                    time.sleep(0.5)
                    st.session_state.login_loading = False
                    st.rerun()   # 👈 fuerza a recargar app ya logueado

            except Exception as e:
                st.error(f"Error al iniciar sesión: {e}")
                st.session_state.login_loading = False

# =========================
# Verificación de módulo activo
# =========================
def is_module_active(empresa, empresa_crm, key, hoy, role):
    """Comprueba si un módulo está activo."""
    if role == "alumno":
        return False

    if key == "formacion":
        return empresa.get("formacion_activo") and (not empresa.get("formacion_inicio") or pd.to_datetime(empresa.get("formacion_inicio")).date() <= hoy)

    if key == "iso":
        return empresa.get("iso_activo") and (not empresa.get("iso_inicio") or pd.to_datetime(empresa.get("iso_inicio")).date() <= hoy)

    if key == "rgpd":
        return empresa.get("rgpd_activo") and (not empresa.get("rgpd_inicio") or pd.to_datetime(empresa.get("rgpd_inicio")).date() <= hoy)

    if key == "crm":
        return empresa_crm.get("crm_activo") and (not empresa_crm.get("crm_inicio") or pd.to_datetime(empresa_crm.get("crm_inicio")).date() <= hoy)

    if key == "docu_avanzada":
        return empresa.get("docu_avanzada_activo") and (not empresa.get("docu_avanzada_inicio") or pd.to_datetime(empresa.get("docu_avanzada_inicio")).date() <= hoy)

    return False

# =========================
# Sidebar y navegación
# =========================
def route():
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")
    
    # Header del sidebar limpio
    st.sidebar.markdown(f"""
    <div style="padding: 1rem 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 1rem;">
        <p style="margin: 0; font-size: 0.875rem; color: #64748b;">Bienvenido</p>
        <p style="margin: 0.25rem 0 0; font-weight: 600; color: #1e293b;">{nombre_usuario}</p>
    </div>
    """, unsafe_allow_html=True)

    # Botón de logout
    if st.sidebar.button("Cerrar sesión", key="logout", type="secondary", use_container_width=True):
        do_logout()

    # Cargar configuración empresa
    empresa_id = st.session_state.user.get("empresa_id")
    empresa = {}
    empresa_crm = {}
    hoy = datetime.today().date()
    
    if empresa_id:
        try:
            empresa_res = supabase_admin.table("empresas").select(
                "formacion_activo, formacion_inicio, formacion_fin, "
                "iso_activo, iso_inicio, iso_fin, "
                "rgpd_activo, rgpd_inicio, rgpd_fin, "
                "docu_avanzada_activo, docu_avanzada_inicio, docu_avanzada_fin"
            ).eq("id", empresa_id).execute()
            empresa = empresa_res.data[0] if empresa_res.data else {}
            
            crm_res = supabase_admin.table("crm_empresas").select(
                "crm_activo, crm_inicio, crm_fin"
            ).eq("empresa_id", empresa_id).execute()
            empresa_crm = crm_res.data[0] if crm_res.data else {}
        except Exception:
            st.sidebar.error("Error al cargar configuración")

    st.session_state.empresa = empresa
    st.session_state.empresa_crm = empresa_crm
    rol = st.session_state.role

    # Menús dinámicos
    if rol == "admin":
        st.sidebar.markdown("**Administración**")
        base_menu = {
            "Panel Admin": "panel_admin",
            "Usuarios y Empresas": "usuarios_empresas",
            "Empresas": "empresas",
            "Ajustes": "ajustes_app"
        }
        for label, page_key in base_menu.items():
            if st.sidebar.button(label, key=f"admin_{page_key}", type="secondary", use_container_width=True):
                st.session_state.page = page_key

    elif rol == "alumno":
        st.sidebar.markdown("**Área del Alumno**")
        if st.sidebar.button("Mis Grupos", key="alumno_grupos", type="secondary", use_container_width=True):
            st.session_state.page = "area_alumno"

    if rol == "gestor" and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Panel de Formación**")
        if st.sidebar.button("Panel del Gestor", key="panel_gestor", type="secondary", use_container_width=True):
            st.session_state.page = "panel_gestor"

    # Módulos condicionales
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Gestión de Formación**")
        formacion_menu = {
            "Acciones Formativas": "acciones_formativas",
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Tutores": "tutores",
            "Aulas": "aulas",
            "Gestión Clases": "gestion_clases",
            "Proyectos": "proyectos",
            "Documentos": "documentos"
        }
        if rol == "gestor":
            formacion_menu = {"Empresas": "empresas", **formacion_menu}
        
        for label, page_key in formacion_menu.items():
            if st.sidebar.button(label, key=f"form_{page_key}", type="secondary", use_container_width=True):
                st.session_state.page = page_key
    # --- Módulo ISO ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "iso", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📋 Gestión ISO 9001")
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
            if st.sidebar.button(label, key=f"iso_{page_key}_{rol}"):
                st.session_state.page = page_key

    # --- Módulo RGPD ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "rgpd", hoy, rol):
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
            if st.sidebar.button(label, key=f"rgpd_{page_key}_{rol}"):
                st.session_state.page = page_key

    # --- Módulo CRM ---
    if (rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "crm", hoy, rol)) or rol == "comercial":
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
            if st.sidebar.button(label, key=f"crm_{page_key}_{rol}"):
                st.session_state.page = page_key

    # --- Módulo Documentación Avanzada ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "docu_avanzada", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📁 Documentación Avanzada")
        docu_menu = {
            "Gestión Documental": "documentacion_avanzada"
        }
        for label, page_key in docu_menu.items():
            if st.sidebar.button(label, key=f"docu_{page_key}_{rol}"):
                st.session_state.page = page_key

    # Footer dinámico
    ajustes = get_ajustes_app(supabase_admin, campos=["mensaje_footer"])
    mensaje_footer = ajustes.get("mensaje_footer", "© 2025 Gestor de Formación")
    
    st.sidebar.markdown("---")
    st.sidebar.caption(mensaje_footer)
# =========================
# Ejecución principal
# =========================
if not st.session_state.role:
    login_view()
else:
    try:
        route()
        page = st.session_state.get("page", None)

        if page and page != "home":
            with st.spinner(f"Cargando {page}..."):
                if page == "panel_gestor" and st.session_state.role == "gestor":
                    from pages.panel_gestor import main as panel_gestor_main
                    panel_gestor_main(supabase_admin, st.session_state)
                else:
                    mod = page.replace("-", "_")
                    mod_path = f"pages.{mod}"
                    mod_import = __import__(mod_path, fromlist=["main"])
                    mod_import.main(supabase_admin, st.session_state)

        else:
            # Dashboard principal según rol
            rol = st.session_state.role

            if rol == "admin":
                st.title("Panel de Administración")
                
                # Métricas en cards modernas
                with st.spinner("Cargando métricas..."):
                    metricas = get_metricas_admin()
                
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Empresas", metricas['empresas'])
                with col2: st.metric("Usuarios", metricas['usuarios'])
                with col3: st.metric("Cursos", metricas['cursos'])
                with col4: st.metric("Grupos", metricas['grupos'])
                
                # Accesos rápidos
                st.markdown("---")
                st.subheader("Accesos Rápidos")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("Gestión de Empresas", use_container_width=True):
                        st.session_state.page = "empresas"
                        st.rerun()
                with col2:
                    if st.button("Gestión de Usuarios", use_container_width=True):
                        st.session_state.page = "usuarios_empresas"
                        st.rerun()
                with col3:
                    if st.button("Configuración", use_container_width=True):
                        st.session_state.page = "ajustes_app"
                        st.rerun()

            elif rol == "gestor":
                st.title("Panel del Gestor")
                empresa_id = st.session_state.user.get("empresa_id")
                if empresa_id:
                    with st.spinner("Cargando métricas..."):
                        metricas = get_metricas_gestor(empresa_id)
                    col1, col2, col3 = st.columns(3)
                    with col1: st.metric("Grupos", metricas['grupos'])
                    with col2: st.metric("Participantes", metricas['participantes'])
                    with col3: st.metric("Documentos", metricas['documentos'])

            elif rol == "alumno":
                st.title("Área del Alumno")
                ajustes = get_ajustes_app(supabase_admin, campos=["bienvenida_alumno"])
                bienvenida = ajustes.get("bienvenida_alumno", "Accede a tus grupos y diplomas desde el menú lateral")
                st.info(bienvenida)

            elif rol == "comercial":
                st.title("Área Comercial")
                st.info("Gestiona tu cartera de clientes desde el menú lateral")

    except Exception as e:
        st.error(f"Error al cargar la página: {e}")
        st.exception(e)

# Cerrar div de clase CSS dinámico
st.markdown('</div>', unsafe_allow_html=True)
