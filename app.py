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
    initial_sidebar_state="expanded",  # Siempre visible
    page_icon="🚀",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "# Gestor de Formación\n### Sistema integral de gestión empresarial"
    }
)

# =========================
# CSS moderno para startup look
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Ocultar elementos Streamlit */
#MainMenu, footer, .stDeployButton, header[data-testid="stHeader"] {
    display: none !important;
}

/* Reset y base */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}

/* Container principal de login */
.login-container {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    padding: 3rem;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    max-width: 480px;
    margin: 2rem auto;
    border: 1px solid rgba(255, 255, 255, 0.3);
}

.login-header {
    text-align: center;
    margin-bottom: 2rem;
}

.login-logo {
    width: 80px;
    height: 80px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 20px;
    margin: 0 auto 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    color: white;
    box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
}

.login-title {
    font-size: 2rem;
    font-weight: 700;
    color: #1a202c;
    margin-bottom: 0.5rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.login-subtitle {
    color: #4a5568;
    font-size: 1rem;
}

/* Inputs */
.stTextInput > div > div > input {
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 12px;
    padding: 0.75rem 1rem;
    font-size: 1rem;
}

.stTextInput > div > div > input:focus {
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    background: white;
}

/* Botones */
.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 0.75rem 2rem;
    font-weight: 600;
    font-size: 1rem;
    width: 100%;
    margin-top: 1rem;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(30px); }
    to { opacity: 1; transform: translateY(0); }
}

.fade-in-up {
    animation: fadeInUp 0.6s ease-out;
}
</style>
""", unsafe_allow_html=True)

# =========================
# Claves Supabase
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("⚠️ Error: Variables de Supabase no configuradas")
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
# Funciones auxiliares
# =========================
@st.cache_data(ttl=300)
def get_metricas_admin():
    try:
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
    except:
        return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}

@st.cache_data(ttl=300)
def get_metricas_gestor(empresa_id):
    try:
        grupos_res = supabase_admin.table("grupos").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        participantes_res = supabase_admin.table("participantes").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        documentos_res = supabase_admin.table("documentos").select("id", count="exact").eq("empresa_id", empresa_id).execute()
        
        return {
            "grupos": grupos_res.count or 0,
            "participantes": participantes_res.count or 0,
            "documentos": documentos_res.count or 0
        }
    except:
        return {"grupos": 0, "participantes": 0, "documentos": 0}

def set_user_role_from_db(email: str):
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
        st.error(f"Error al obtener rol: {e}")
        st.session_state.role = "alumno"

def do_logout():
    try:
        supabase_public.auth.sign_out()
    except:
        pass
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

# =========================
# Vista de login
# =========================
def login_view():
    """Pantalla de login con sidebar informativo."""
    
    # Sidebar con información
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 2rem 1rem;">
            <div style="
                width: 60px; height: 60px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                border-radius: 12px;
                margin: 0 auto 1rem;
                display: flex; align-items: center; justify-content: center;
                font-size: 1.5rem; color: white;
            ">🚀</div>
            <h3 style="color: #667eea; font-size: 1.1rem; margin: 0;">Sistema de Gestión</h3>
            <p style="color: #94a3b8; font-size: 0.875rem; margin-top: 0.5rem;">Inicia sesión para acceder</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        st.markdown("""
        <div style="padding: 0 1rem;">
            <p style="font-size: 0.875rem; color: #64748b; font-weight: 500; margin-bottom: 0.75rem;">
                Módulos disponibles:
            </p>
            <div style="font-size: 0.875rem; color: #94a3b8; line-height: 1.8;">
                <div>📚 Formación FUNDAE</div>
                <div>📋 ISO 9001</div>
                <div>🛡️ RGPD</div>
                <div>📈 CRM</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Obtener ajustes
    ajustes = get_ajustes_app(supabase_public, campos=["mensaje_login", "nombre_app", "logo_url"])
    
    mensaje_login = ajustes.get("mensaje_login", "Accede al gestor con tus credenciales")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    logo_display = "🚀" if not ajustes.get("logo_url") else f'<img src="{ajustes.get("logo_url")}" width="80" height="80" style="border-radius: 20px;">'
    
    # Container de login
    st.markdown(f"""
    <div class="login-container fade-in-up">
        <div class="login-header">
            <div class="login-logo">{logo_display}</div>
            <h1 class="login-title">{nombre_app}</h1>
            <p class="login-subtitle">{mensaje_login}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Formulario
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("form_login", clear_on_submit=False):
            st.markdown("### 🔐 Iniciar sesión")
            
            email = st.text_input("Email", placeholder="tu@empresa.com")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            
            submitted = st.form_submit_button(
                "🚀 Entrar" if not st.session_state.get("login_loading") else "⏳ Iniciando...",
                disabled=st.session_state.get("login_loading", False)
            )
    
    if submitted:
        if not email or not password:
            st.warning("⚠️ Introduce email y contraseña")
        else:
            st.session_state.login_loading = True
            
            try:
                auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
                
                if not auth or not auth.user:
                    st.error("❌ Credenciales incorrectas")
                    st.session_state.login_loading = False
                else:
                    st.session_state.auth_session = auth
                    set_user_role_from_db(auth.user.email)
                    st.success("✅ Sesión iniciada")
                    time.sleep(0.5)
                    st.session_state.login_loading = False
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.session_state.login_loading = False

# =========================
# Verificación módulos
# =========================
def is_module_active(empresa, empresa_crm, key, hoy, role):
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
    
    # Header sidebar
    st.sidebar.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white; padding: 1rem; border-radius: 12px;
        margin-bottom: 1rem; text-align: center;
    ">
        <h3 style="margin: 0; font-weight: 600;">👋 Bienvenido</h3>
        <p style="margin: 0.5rem 0 0; opacity: 0.9; font-size: 0.9rem;">{nombre_usuario}</p>
    </div>
    """, unsafe_allow_html=True)

    # Botón logout
    if st.sidebar.button("🚪 Cerrar sesión", key="logout", type="secondary"):
        do_logout()

    # Cargar empresa
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
        except:
            pass

    st.session_state.empresa = empresa
    st.session_state.empresa_crm = empresa_crm
    rol = st.session_state.role

    # Menús
    if rol == "admin":
        st.sidebar.markdown("#### 🧭 Administración")
        base_menu = {
            "Panel Admin": "panel_admin",
            "Usuarios y Empresas": "usuarios_empresas",
            "Empresas": "empresas",
            "Ajustes": "ajustes_app"
        }
        for label, page_key in base_menu.items():
            if st.sidebar.button(label, key=f"admin_{page_key}"):
                st.session_state.page = page_key

    elif rol == "alumno":
        st.sidebar.markdown("#### 🎓 Área del Alumno")
        if st.sidebar.button("Mis Grupos y Diplomas", key="alumno_grupos"):
            st.session_state.page = "area_alumno"

    # Gestor
    if rol == "gestor" and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📊 Panel de Formación")
        if st.sidebar.button("Panel del Gestor", key="panel_gestor"):
            st.session_state.page = "panel_gestor"

    # Formación
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📚 Gestión de Formación")
        
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
            if st.sidebar.button(label, key=f"form_{page_key}"):
                st.session_state.page = page_key

    # ISO, RGPD, CRM (igual que antes)
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "iso", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📋 ISO 9001")
        iso_menu = {"No Conformidades": "no_conformidades", "Auditorías": "auditorias"}
        for label, page_key in iso_menu.items():
            if st.sidebar.button(label, key=f"iso_{page_key}"):
                st.session_state.page = page_key

    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "rgpd", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 🛡️ RGPD")
        rgpd_menu = {"Panel RGPD": "rgpd_panel", "Tratamientos": "rgpd_tratamientos"}
        for label, page_key in rgpd_menu.items():
            if st.sidebar.button(label, key=f"rgpd_{page_key}"):
                st.session_state.page = page_key

    if (rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "crm", hoy, rol)) or rol == "comercial":
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📈 CRM")
        crm_menu = {"Panel CRM": "crm_panel", "Clientes": "crm_clientes"}
        for label, page_key in crm_menu.items():
            if st.sidebar.button(label, key=f"crm_{page_key}"):
                st.session_state.page = page_key

    # Footer
    ajustes = get_ajustes_app(supabase_admin, campos=["mensaje_footer"])
    st.sidebar.markdown("---")
    st.sidebar.caption(ajustes.get("mensaje_footer", "© 2025 Gestor de Formación"))

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
            # Dashboard simple
            rol = st.session_state.role
            ajustes = get_ajustes_app(supabase_admin)
            
            if rol == "admin":
                st.title("Panel de Administración")
                metricas = get_metricas_admin()
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Empresas", metricas['empresas'])
                col2.metric("Usuarios", metricas['usuarios'])
                col3.metric("Cursos", metricas['cursos'])
                col4.metric("Grupos", metricas['grupos'])

            elif rol == "gestor":
                st.title("Panel del Gestor")
                empresa_id = st.session_state.user.get("empresa_id")
                if empresa_id:
                    metricas = get_metricas_gestor(empresa_id)
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Grupos", metricas['grupos'])
                    col2.metric("Participantes", metricas['participantes'])
                    col3.metric("Documentos", metricas['documentos'])

            elif rol == "alumno":
                st.title("Área del Alumno")
                st.info("Accede a tus grupos desde el menú lateral")

            elif rol == "comercial":
                st.title("Área Comercial")
                st.info("Gestiona clientes desde el menú lateral")

    except Exception as e:
        st.error(f"Error: {e}")
        st.exception(e)
