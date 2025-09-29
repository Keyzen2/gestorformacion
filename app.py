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
# Configuración
# =========================
st.set_page_config(
    page_title="Gestor de Formación",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀",
    menu_items=None
)

# =========================
# CSS DISEÑO SAAS PROFESIONAL
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Ocultar elementos Streamlit */
#MainMenu, footer, .stDeployButton, header[data-testid="stHeader"],
button[kind="header"], [data-testid="stToolbar"] {
    display: none !important;
}

/* Reset */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Background global limpio */
.stApp {
    background: #f8fafc !important;
}

/* SIDEBAR CON COLOR DE CONTRASTE */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
    border-right: 1px solid #334155 !important;
    padding-top: 80px !important; /* Espacio para header */
}

section[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
    padding: 0.625rem 1rem !important;
    font-size: 0.9rem !important;
    transition: all 0.2s ease !important;
}

section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255, 255, 255, 0.1) !important;
    border-color: rgba(255, 255, 255, 0.2) !important;
    transform: translateX(4px) !important;
}

section[data-testid="stSidebar"] h4 {
    color: #94a3b8 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin: 1.5rem 0 0.5rem 0 !important;
}

section[data-testid="stSidebar"] hr {
    border-color: #334155 !important;
    margin: 1rem 0 !important;
}

/* ÁREA PRINCIPAL CLARA */
.main .block-container {
    padding: 100px 2rem 80px 2rem !important;
    max-width: 1400px !important;
    background: #ffffff !important;
    min-height: calc(100vh - 180px) !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
}

/* LOGIN - diseño especial */
.login-mode .stApp {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
}

.login-mode .main .block-container {
    background: transparent !important;
    box-shadow: none !important;
    padding-top: 2rem !important;
}

.login-container {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    padding: 3rem;
    box-shadow: 0 20px 40px rgba(0,0,0,0.2);
    max-width: 480px;
    margin: 2rem auto;
}

.login-logo {
    width: 80px;
    height: 80px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border-radius: 20px;
    margin: 0 auto 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    color: white;
}

/* Inputs */
.stTextInput > div > div > input {
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    padding: 0.75rem 1rem !important;
    font-size: 0.95rem !important;
}

.stTextInput > div > div > input:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1) !important;
}

/* Botones principales */
.stButton > button[kind="primary"],
.stButton > button:not([kind]) {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.75rem 1.5rem !important;
    font-weight: 600 !important;
}

.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(59,130,246,0.3) !important;
}

/* Métricas modernas */
[data-testid="stMetric"] {
    background: #ffffff !important;
    padding: 1.5rem !important;
    border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}

[data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: #1e293b !important;
}

[data-testid="stMetricLabel"] {
    font-size: 0.875rem !important;
    color: #64748b !important;
    font-weight: 500 !important;
}

/* Alertas */
.stAlert {
    border-radius: 8px !important;
    border-left: 4px solid !important;
}

/* Títulos */
h1 {
    color: #1e293b !important;
    font-weight: 700 !important;
    margin-bottom: 1rem !important;
}

h2, h3 {
    color: #334155 !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# HEADER Y FOOTER DINÁMICOS
# =========================
def render_header():
    """Header fijo profesional con logo y nombre de la app"""
    ajustes = get_ajustes_app(supabase_admin if supabase_admin else supabase_public, 
                               campos=["nombre_app", "logo_url", "color_primario"])
    
    logo_url = ajustes.get("logo_url", "")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    color = ajustes.get("color_primario", "#3b82f6")
    
    logo_html = f'<img src="{logo_url}" style="height: 40px; width: 40px; border-radius: 8px;">' if logo_url else "🚀"
    
    st.markdown(f"""
    <div style="
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 70px;
        background: white;
        border-bottom: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        padding: 0 2rem;
        z-index: 999;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    ">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 2rem;">{logo_html}</div>
            <div>
                <h2 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: #1e293b;">
                    {nombre_app}
                </h2>
                <p style="margin: 0; font-size: 0.75rem; color: #64748b;">
                    Sistema de Gestión Empresarial
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_footer():
    """Footer fijo profesional"""
    ajustes = get_ajustes_app(supabase_admin if supabase_admin else supabase_public, 
                               campos=["mensaje_footer"])
    
    mensaje = ajustes.get("mensaje_footer", "© 2025 Gestor de Formación")
    
    st.markdown(f"""
    <div style="
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 60px;
        background: #f8fafc;
        border-top: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 2rem;
        z-index: 998;
    ">
        <p style="margin: 0; font-size: 0.875rem; color: #64748b; text-align: center;">
            {mensaje}
        </p>
    </div>
    """, unsafe_allow_html=True)

# =========================
# Supabase
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("Variables de Supabase no configuradas")
    st.stop()

supabase_public = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else None

# =========================
# Estado
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
# Funciones (mantener las mismas de antes)
# =========================
@st.cache_data(ttl=300)
def get_metricas_admin():
    try:
        empresas = supabase_admin.table("empresas").select("id", count="exact").execute().count or 0
        usuarios = supabase_admin.table("usuarios").select("id", count="exact").execute().count or 0
        cursos = supabase_admin.table("acciones_formativas").select("id", count="exact").execute().count or 0
        grupos = supabase_admin.table("grupos").select("id", count="exact").execute().count or 0
        return {"empresas": empresas, "usuarios": usuarios, "cursos": cursos, "grupos": grupos}
    except:
        return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}

@st.cache_data(ttl=300)
def get_metricas_gestor(empresa_id):
    try:
        grupos = supabase_admin.table("grupos").select("id", count="exact").eq("empresa_id", empresa_id).execute().count or 0
        participantes = supabase_admin.table("participantes").select("id", count="exact").eq("empresa_id", empresa_id).execute().count or 0
        documentos = supabase_admin.table("documentos").select("id", count="exact").eq("empresa_id", empresa_id).execute().count or 0
        return {"grupos": grupos, "participantes": participantes, "documentos": documentos}
    except:
        return {"grupos": 0, "participantes": 0, "documentos": 0}

def set_user_role_from_db(email: str):
    try:
        res = supabase_public.table("usuarios").select("*").eq("email", email.strip().lower()).limit(1).execute()
        if res.data:
            row = res.data[0]
            st.session_state.role = row.get("rol") or "alumno"
            st.session_state.user = {
                "id": row.get("id"),
                "email": row.get("email"),
                "nombre": row.get("nombre"),
                "empresa_id": row.get("empresa_id")
            }
        else:
            st.session_state.role = "alumno"
    except:
        st.session_state.role = "alumno"

def do_logout():
    try:
        supabase_public.auth.sign_out()
    except:
        pass
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

def is_module_active(empresa, empresa_crm, key, hoy, role):
    if role == "alumno":
        return False
    if key == "formacion":
        return empresa.get("formacion_activo", False)
    if key == "iso":
        return empresa.get("iso_activo", False)
    if key == "rgpd":
        return empresa.get("rgpd_activo", False)
    if key == "crm":
        return empresa_crm.get("crm_activo", False)
    return False

# =========================
# Login
# =========================
def login_view():
    # Clase CSS para estilo login
    st.markdown('<div class="login-mode">', unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 2rem 1rem;">
            <div style="width: 60px; height: 60px; background: rgba(255,255,255,0.1);
                border-radius: 12px; margin: 0 auto 1rem; display: flex; align-items: center; 
                justify-content: center; font-size: 1.5rem;">🚀</div>
            <h3 style="font-size: 1.1rem;">Sistema de Gestión</h3>
            <p style="font-size: 0.875rem; opacity: 0.8;">Inicia sesión para acceder</p>
        </div>
        <hr>
        <div style="padding: 0 1rem; font-size: 0.875rem; opacity: 0.9;">
            <p style="font-weight: 500;">Módulos:</p>
            <div style="line-height: 1.8;">
                <div>📚 Formación FUNDAE</div>
                <div>📋 ISO 9001</div>
                <div>🛡️ RGPD</div>
                <div>📈 CRM</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    ajustes = get_ajustes_app(supabase_public, campos=["mensaje_login", "nombre_app", "logo_url"])
    logo = "🚀" if not ajustes.get("logo_url") else f'<img src="{ajustes["logo_url"]}" width="80" height="80" style="border-radius: 20px;">'
    
    st.markdown(f"""
    <div class="login-container">
        <div style="text-align: center; margin-bottom: 2rem;">
            <div class="login-logo">{logo}</div>
            <h1 style="font-size: 2rem; color: #1a202c; margin: 1rem 0 0.5rem;">{ajustes.get("nombre_app", "Gestor")}</h1>
            <p style="color: #64748b;">{ajustes.get("mensaje_login", "Accede al sistema")}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login"):
            st.markdown("### Iniciar sesión")
            email = st.text_input("Email", placeholder="tu@empresa.com", label_visibility="collapsed")
            password = st.text_input("Contraseña", type="password", placeholder="Contraseña", label_visibility="collapsed")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
    
    if submitted and email and password:
        try:
            auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
            if auth and auth.user:
                st.session_state.auth_session = auth
                set_user_role_from_db(auth.user.email)
                st.success("Sesión iniciada")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        except Exception as e:
            st.error(f"Error: {e}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# Navegación COMPLETA
# =========================
def route():
    nombre = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")
    
    st.sidebar.markdown(f"""
    <div style="padding: 1rem; border-bottom: 1px solid #334155; margin-bottom: 1rem;">
        <p style="margin: 0; font-size: 0.75rem; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.05em;">Bienvenido</p>
        <p style="margin: 0.5rem 0 0; font-size: 1rem; font-weight: 600;">{nombre}</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.sidebar.button("Cerrar sesión", key="logout", use_container_width=True):
        do_logout()
    
    empresa_id = st.session_state.user.get("empresa_id")
    empresa, empresa_crm = {}, {}
    hoy = datetime.today().date()
    
    if empresa_id:
        try:
            e = supabase_admin.table("empresas").select(
                "formacion_activo, formacion_inicio, formacion_fin, "
                "iso_activo, iso_inicio, iso_fin, "
                "rgpd_activo, rgpd_inicio, rgpd_fin, "
                "docu_avanzada_activo, docu_avanzada_inicio, docu_avanzada_fin"
            ).eq("id", empresa_id).execute()
            empresa = e.data[0] if e.data else {}
            
            c = supabase_admin.table("crm_empresas").select(
                "crm_activo, crm_inicio, crm_fin"
            ).eq("empresa_id", empresa_id).execute()
            empresa_crm = c.data[0] if c.data else {}
        except:
            pass
    
    st.session_state.empresa = empresa
    st.session_state.empresa_crm = empresa_crm
    rol = st.session_state.role
    
    # ============================================
    # MENÚ ADMIN
    # ============================================
    if rol == "admin":
        st.sidebar.markdown("#### Administración SaaS")
        admin_menu = {
            "Panel Admin": "panel_admin",
            "Usuarios y Empresas": "usuarios_empresas",
            "Empresas": "empresas",
            "Ajustes de la App": "ajustes_app"
        }
        for label, page in admin_menu.items():
            if st.sidebar.button(label, key=f"admin_{page}", use_container_width=True):
                st.session_state.page = page
    
    # ============================================
    # MENÚ ALUMNO
    # ============================================
    elif rol == "alumno":
        st.sidebar.markdown("#### Área del Alumno")
        if st.sidebar.button("Mis Grupos y Diplomas", key="alumno_grupos", use_container_width=True):
            st.session_state.page = "area_alumno"
    
    # ============================================
    # PANEL GESTOR
    # ============================================
    if rol == "gestor" and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### Panel de Formación")
        if st.sidebar.button("Panel del Gestor", key="panel_gestor", use_container_width=True):
            st.session_state.page = "panel_gestor"
    
    # ============================================
    # MÓDULO FORMACIÓN
    # ============================================
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### Gestión de Formación")
        
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
            # Gestor ve Empresas primero
            formacion_menu = {"Empresas": "empresas", **formacion_menu}
        
        for label, page in formacion_menu.items():
            if st.sidebar.button(label, key=f"form_{page}", use_container_width=True):
                st.session_state.page = page
    
    # ============================================
    # MÓDULO ISO 9001
    # ============================================
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "iso", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### Gestión ISO 9001")
        iso_menu = {
            "No Conformidades": "no_conformidades",
            "Acciones Correctivas": "acciones_correctivas",
            "Auditorías": "auditorias",
            "Indicadores": "indicadores",
            "Dashboard Calidad": "dashboard_calidad",
            "Objetivos de Calidad": "objetivos_calidad",
            "Informe Auditoría": "informe_auditoria"
        }
        for label, page in iso_menu.items():
            if st.sidebar.button(label, key=f"iso_{page}", use_container_width=True):
                st.session_state.page = page
    
    # ============================================
    # MÓDULO RGPD
    # ============================================
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "rgpd", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### Gestión RGPD")
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
        for label, page in rgpd_menu.items():
            if st.sidebar.button(label, key=f"rgpd_{page}", use_container_width=True):
                st.session_state.page = page
    
    # ============================================
    # MÓDULO CRM
    # ============================================
    if (rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "crm", hoy, rol)) or rol == "comercial":
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### Gestión CRM")
        crm_menu = {
            "Panel CRM": "crm_panel",
            "Clientes": "crm_clientes",
            "Oportunidades": "crm_oportunidades",
            "Tareas y Seguimiento": "crm_tareas",
            "Comunicaciones": "crm_comunicaciones",
            "Estadísticas": "crm_estadisticas"
        }
        for label, page in crm_menu.items():
            if st.sidebar.button(label, key=f"crm_{page}", use_container_width=True):
                st.session_state.page = page
    
    # ============================================
    # MÓDULO DOCUMENTACIÓN AVANZADA
    # ============================================
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "docu_avanzada", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### Documentación Avanzada")
        if st.sidebar.button("Gestión Documental", key="docu_avanzada", use_container_width=True):
            st.session_state.page = "documentacion_avanzada"
    
    # ============================================
    # FOOTER SIDEBAR
    # ============================================
    ajustes = get_ajustes_app(supabase_admin, campos=["mensaje_footer"])
    st.sidebar.markdown("---")
    st.sidebar.caption(ajustes.get("mensaje_footer", "© 2025 Gestor de Formación"))

# =========================
# Main
# =========================
if not st.session_state.role:
    login_view()
else:
    # Renderizar header y footer
    render_header()
    render_footer()
    
    route()
    page = st.session_state.get("page")
    
    if page and page != "home":
        with st.spinner("Cargando..."):
            try:
                if page == "panel_gestor":
                    from pages.panel_gestor import main
                    main(supabase_admin, st.session_state)
                else:
                    mod = __import__(f"pages.{page.replace('-', '_')}", fromlist=["main"])
                    mod.main(supabase_admin, st.session_state)
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        ajustes = get_ajustes_app(supabase_admin)
        rol = st.session_state.role
        
        if rol == "admin":
            st.title("Panel de Administración")
            m = get_metricas_admin()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Empresas", m['empresas'])
            c2.metric("Usuarios", m['usuarios'])
            c3.metric("Cursos", m['cursos'])
            c4.metric("Grupos", m['grupos'])
        
        elif rol == "gestor":
            st.title(ajustes.get("bienvenida_gestor", "Panel del Gestor"))
            eid = st.session_state.user.get("empresa_id")
            if eid:
                m = get_metricas_gestor(eid)
                c1, c2, c3 = st.columns(3)
                c1.metric("Grupos", m['grupos'])
                c2.metric("Participantes", m['participantes'])
                c3.metric("Documentos", m['documentos'])
        
        elif rol == "alumno":
            st.title(ajustes.get("bienvenida_alumno", "Área del Alumno"))
            usuario_id = st.session_state.user.get("id")
            
            if usuario_id:
                try:
                    grupos = supabase_admin.table("participantes_grupos").select("grupo:grupos(codigo_grupo, estado)").eq("participante_id", usuario_id).execute()
                    
                    if grupos.data:
                        activos = [g for g in grupos.data if g.get('grupo', {}).get('estado') != 'FINALIZADO']
                        finalizados = [g for g in grupos.data if g.get('grupo', {}).get('estado') == 'FINALIZADO']
                        
                        c1, c2 = st.columns(2)
                        c1.metric("Grupos Activos", len(activos))
                        c2.metric("Grupos Completados", len(finalizados))
                        
                        if activos:
                            st.subheader("Mis Grupos Activos")
                            for item in activos[:5]:
                                g = item.get('grupo', {})
                                st.text(f"🟢 {g.get('codigo_grupo', 'N/A')}")
                        
                        st.markdown("---")
                        if st.button("Ver Todos Mis Grupos y Diplomas", use_container_width=True):
                            st.session_state.page = "area_alumno"
                            st.rerun()
                    else:
                        st.info("No estás inscrito en ningún grupo")
                except:
                    st.warning("No se pudieron cargar tus grupos")
        
        elif rol == "comercial":
            st.title(ajustes.get("bienvenida_comercial", "Área Comercial"))
            st.info("Gestiona tu cartera desde el menú lateral")
