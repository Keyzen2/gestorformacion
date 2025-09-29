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
# Configuración de la página con tema moderno
# =========================
st.set_page_config(
    page_title="Gestor de Formación",
    layout="wide",
    initial_sidebar_state="collapsed",  # Ocultar sidebar en login
    page_icon="🚀",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "# Gestor de Formación\n### Sistema integral de gestión empresarial"
    }
)

# CSS moderno para startup look + OCULTAR ELEMENTOS STREAMLIT
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ========================================
   OCULTAR ELEMENTOS DE STREAMLIT
   ======================================== */

/* Ocultar menú hamburguesa completamente */
#MainMenu {
    visibility: hidden !important;
    display: none !important;
}

/* Ocultar footer "Made with Streamlit" */
footer {
    visibility: hidden !important;
    display: none !important;
}

/* Ocultar botón "Deploy" */
.stDeployButton {
    visibility: hidden !important;
    display: none !important;
}

/* Ocultar header completo (arriba derecha) */
header[data-testid="stHeader"] {
    visibility: hidden !important;
    display: none !important;
}

/* CRÍTICO: Ocultar sidebar de páginas automático */
section[data-testid="stSidebar"] {
    display: none !important;
}

/* Ocultar el botón de ">" para expandir sidebar */
button[kind="header"] {
    display: none !important;
}

/* Ajustar espacio al ocultar header */
.block-container {
    padding-top: 1rem !important;
}

/* Prevenir que aparezca el sidebar al hacer hover */
.css-1d391kg {
    display: none !important;
}

/* ========================================
   TU DISEÑO ORIGINAL (mantener igual)
   ======================================== */

/* Reset y base */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}

/* Ocultar elementos de Streamlit en login */
.login-mode header[data-testid="stHeader"] {
    display: none;
}

.login-mode .stAppViewContainer > .main .block-container {
    padding-top: 2rem;
}

/* Container principal de login */
.login-container {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    padding: 3rem;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    max-width: 480px;
    margin: 2rem auto;
    border: 1px solid rgba(255, 255, 255, 0.3);
}

/* Logo y título */
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
    background-clip: text;
}

.login-subtitle {
    color: #4a5568;
    font-size: 1rem;
    font-weight: 400;
}

/* Módulos grid */
.modules-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin: 2rem 0;
}

.module-card {
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(10px);
    border-radius: 16px;
    padding: 1.5rem;
    border: 1px solid rgba(255, 255, 255, 0.3);
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.module-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
}

.module-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.15);
    background: rgba(255, 255, 255, 0.95);
}

.module-icon {
    font-size: 2rem;
    margin-bottom: 0.5rem;
    display: block;
}

.module-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #2d3748;
    margin-bottom: 0.5rem;
}

.module-desc {
    font-size: 0.9rem;
    color: #4a5568;
    line-height: 1.4;
}

/* Formulario de login mejorado */
.stTextInput > div > div > input {
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 12px;
    padding: 0.75rem 1rem;
    font-size: 1rem;
    transition: all 0.3s ease;
}

.stTextInput > div > div > input:focus {
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    background: white;
}

.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 0.75rem 2rem;
    font-weight: 600;
    font-size: 1rem;
    transition: all 0.3s ease;
    width: 100%;
    margin-top: 1rem;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
}

/* Estados de carga */
.loading-spinner {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid rgba(255,255,255,.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Alertas mejoradas */
.stAlert > div {
    border-radius: 12px;
    backdrop-filter: blur(10px);
}

/* Footer */
.login-footer {
    text-align: center;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid rgba(255, 255, 255, 0.3);
    font-size: 0.85rem;
    color: #4a5568;
}

/* Responsive */
@media (max-width: 768px) {
    .login-container {
        margin: 1rem;
        padding: 2rem;
    }
    
    .modules-grid {
        grid-template-columns: 1fr;
    }
}

/* Animaciones de entrada */
@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.fade-in-up {
    animation: fadeInUp 0.6s ease-out;
}

.fade-in-up-delay {
    animation: fadeInUp 0.6s ease-out 0.2s both;
}
</style>
""", unsafe_allow_html=True)

# =========================
# Claves Supabase
# =========================

# Intentar primero variables de entorno (Railway), luego secrets (Streamlit Cloud)
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Validación de variables críticas
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("⚠️ Error: Variables de Supabase no configuradas correctamente")
    st.error("Por favor, configura SUPABASE_URL y SUPABASE_ANON_KEY en las variables de entorno")
    st.stop()

# Crear clientes Supabase
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
# Funciones auxiliares optimizadas
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
    except Exception as e:
        st.error(f"Error al cargar métricas: {e}")
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
# Vista de login moderna
# =========================
def login_view():
    """Pantalla de login con diseño startup moderno."""
    
    # Añadir clase CSS para ocultar header
    st.markdown('<div class="login-mode">', unsafe_allow_html=True)
    
    # Obtener configuración personalizable - USAR SOLO CAMPOS EXISTENTES
    ajustes = get_ajustes_app(supabase_public, campos=[
        "mensaje_login", "nombre_app", "logo_url", "color_primario"
    ])
    
    mensaje_login = ajustes.get("mensaje_login", "Accede al gestor con tus credenciales")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    # Usar emoji por defecto si no hay logo_url
    logo_display = "🚀" if not ajustes.get("logo_url") else f'<img src="{ajustes.get("logo_url")}" width="80" height="80" style="border-radius: 20px;">'
    
    # Container principal con logo y título
    st.markdown(f"""
    <div class="login-container fade-in-up">
        <div class="login-header">
            <div class="login-logo">{logo_display}</div>
            <h1 class="login-title">{nombre_app}</h1>
            <p class="login-subtitle">{mensaje_login}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # FORMULARIO DE LOGIN PRIMERO
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form("form_login_acceso", clear_on_submit=False):
                st.markdown("### 🔐 Iniciar sesión")
                
                email = st.text_input(
                    "Email", 
                    placeholder="tu@empresa.com",
                    help="Introduce tu email corporativo"
                )
                
                password = st.text_input(
                    "Contraseña", 
                    type="password",
                    placeholder="••••••••",
                    help="Tu contraseña segura"
                )
                
                submitted = st.form_submit_button(
                    "🚀 Entrar al sistema" if not st.session_state.get("login_loading") else "⏳ Iniciando sesión...",
                    disabled=st.session_state.get("login_loading", False)
                )
    
    # Divisor visual
    st.markdown("<div style='margin: 2rem 0;'></div>", unsafe_allow_html=True)
    
    # MÓDULOS DISPONIBLES DESPUÉS DEL LOGIN
    st.markdown("### 🎯 Módulos disponibles")
    st.markdown("""
    <div class="modules-grid fade-in-up-delay">
        <div class="module-card">
            <span class="module-icon">📚</span>
            <h4 class="module-title">Formación</h4>
            <p class="module-desc">Gestión de acciones formativas, grupos, participantes y documentos FUNDAE.</p>
        </div>
        <div class="module-card">
            <span class="module-icon">📋</span>
            <h4 class="module-title">ISO 9001</h4>
            <p class="module-desc">Auditorías, informes y seguimiento de calidad empresarial.</p>
        </div>
        <div class="module-card">
            <span class="module-icon">🛡️</span>
            <h4 class="module-title">RGPD</h4>
            <p class="module-desc">Consentimientos, documentación legal y trazabilidad de datos.</p>
        </div>
        <div class="module-card">
            <span class="module-icon">📈</span>
            <h4 class="module-title">CRM</h4>
            <p class="module-desc">Gestión de clientes, oportunidades y tareas comerciales.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if submitted:
        if not email or not password:
            st.warning("⚠️ Por favor, introduce email y contraseña.")
        else:
            st.session_state.login_loading = True
            
            # Mostrar progreso con barra moderna
            progress_placeholder = st.empty()
            with progress_placeholder.container():
                st.info("🔄 Verificando credenciales...")
                progress_bar = st.progress(0)
                
                # Simular progreso
                for i in range(100):
                    time.sleep(0.01)
                    progress_bar.progress(i + 1)
            
            try:
                auth = supabase_public.auth.sign_in_with_password({
                    "email": email, 
                    "password": password
                })
                
                if not auth or not auth.user:
                    progress_placeholder.error("❌ Credenciales incorrectas. Verifica tu email y contraseña.")
                    st.session_state.login_loading = False
                else:
                    st.session_state.auth_session = auth
                    set_user_role_from_db(auth.user.email)
                    
                    progress_placeholder.success("✅ Sesión iniciada correctamente. Redirigiendo...")
                    time.sleep(1)
                    st.session_state.login_loading = False
                    st.rerun()
                    
            except Exception as e:
                progress_placeholder.error(f"❌ Error al iniciar sesión: {e}")
                st.session_state.login_loading = False
    
    # Footer personalizable
    ajustes_footer = get_ajustes_app(supabase_public, campos=["mensaje_footer"])
    mensaje_footer = ajustes_footer.get("mensaje_footer", "© 2025 Gestor de Formación · Powered by Streamlit")
    
    st.markdown(f"""
    <div class="login-footer">
        {mensaje_footer}
    </div>
    </div>
    """, unsafe_allow_html=True)

# =========================
# Verificación de módulo activo
# =========================
def is_module_active(empresa, empresa_crm, key, hoy, role):
    """Comprueba si un módulo está activo para la empresa del usuario."""
    if role == "alumno":
        return False

    if key == "formacion":
        if not empresa.get("formacion_activo"):
            return False
        inicio = empresa.get("formacion_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True

    if key == "iso":
        if not empresa.get("iso_activo"):
            return False
        inicio = empresa.get("iso_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True

    if key == "rgpd":
        if not empresa.get("rgpd_activo"):
            return False
        inicio = empresa.get("rgpd_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True

    if key == "crm":
        if not empresa_crm.get("crm_activo"):
            return False
        inicio = empresa_crm.get("crm_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True

    if key == "docu_avanzada":
        if not empresa.get("docu_avanzada_activo"):
            return False
        inicio = empresa.get("docu_avanzada_inicio")
        if inicio and pd.to_datetime(inicio).date() > hoy:
            return False
        return True

    return False

# =========================
# Tarjetas optimizadas con mejor diseño
# =========================
def tarjeta_moderna(icono, titulo, descripcion, activo=True, color="#667eea"):
    """Tarjetas con diseño moderno usando nuevas capacidades de Streamlit."""
    color_bg = f"linear-gradient(135deg, {color}15, {color}05)" if activo else "#f8f9fa"
    color_border = color if activo else "#e2e8f0"
    
    return f"""
    <div style="
        background: {color_bg};
        border: 2px solid {color_border};
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
        cursor: pointer;
        position: relative;
        overflow: hidden;
    " 
    onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 20px 25px -5px rgba(0,0,0,0.1)'"
    onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 6px -1px rgba(0,0,0,0.1)'">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="
                font-size: 2.5rem;
                background: {color};
                color: white;
                width: 60px;
                height: 60px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 8px 25px {color}30;
            ">{icono}</div>
            <div>
                <h3 style="margin: 0; font-size: 1.3rem; color: #2d3748; font-weight: 600;">{titulo}</h3>
                <p style="margin: 0.5rem 0 0; color: #4a5568; font-size: 0.95rem; line-height: 1.4;">{descripcion}</p>
            </div>
        </div>
    </div>
    """

# =========================
# Sidebar y navegación mejorada
# =========================
def route():
    # Cambiar estado inicial del sidebar después del login
    if st.session_state.role:
        st.set_page_config(initial_sidebar_state="expanded")
    
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")
    
    # Header del sidebar con estilo
    st.sidebar.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        text-align: center;
    ">
        <h3 style="margin: 0; font-weight: 600;">👋 Bienvenido</h3>
        <p style="margin: 0.5rem 0 0; opacity: 0.9; font-size: 0.9rem;">{nombre_usuario}</p>
    </div>
    """, unsafe_allow_html=True)

    # Botón de logout mejorado
    if st.sidebar.button("🚪 Cerrar sesión", key="logout", help="Cerrar sesión y limpiar datos", type="secondary"):
        do_logout()

    # Resto de la lógica de navegación (sin cambios mayores)
    empresa_id = st.session_state.user.get("empresa_id")
    empresa = {}
    empresa_crm = {}
    hoy = datetime.today().date()
    
    if empresa_id:
        try:
            empresa_res = supabase_admin.table("empresas").select(
                "formacion_activo", "formacion_inicio", "formacion_fin",
                "iso_activo", "iso_inicio", "iso_fin",
                "rgpd_activo", "rgpd_inicio", "rgpd_fin",
                "docu_avanzada_activo", "docu_avanzada_inicio", "docu_avanzada_fin"
            ).eq("id", empresa_id).execute()
            empresa = empresa_res.data[0] if empresa_res.data else {}
            
            crm_res = supabase_admin.table("crm_empresas").select(
                "crm_activo", "crm_inicio", "crm_fin"
            ).eq("empresa_id", empresa_id).execute()
            empresa_crm = crm_res.data[0] if crm_res.data else {}
        except Exception as e:
            st.sidebar.error(f"⚠️ Error al cargar configuración de empresa: {e}")

    st.session_state.empresa = empresa
    st.session_state.empresa_crm = empresa_crm
    rol = st.session_state.role

    # Menús de navegación (mantener lógica existente pero con mejor estilo)
    if rol == "admin":
        st.sidebar.markdown("#### 🧭 Administración SaaS")
        base_menu = {
            "Panel Admin": "panel_admin",
            "Usuarios y Empresas": "usuarios_empresas", 
            "Empresas": "empresas",
            "Ajustes de la App": "ajustes_app"
        }
        for label, page_key in base_menu.items():
            if st.sidebar.button(label, key=f"admin_{page_key}_{rol}"):
                st.session_state.page = page_key

    elif rol == "alumno":
        st.sidebar.markdown("#### 🎓 Área del Alumno")
        if st.sidebar.button("Mis Grupos y Diplomas", key="alumno_mis_grupos"):
            st.session_state.page = "area_alumno"
            
    # Panel del Gestor
    if rol == "gestor" and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📊 Panel de Formación")
        if st.sidebar.button("Panel del Gestor", key=f"panel_gestor_{rol}"):
            st.session_state.page = "panel_gestor"
                    
    # Módulo Formación
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📚 Gestión de Formación")
        
        if rol == "admin":
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
        elif rol == "gestor":
            formacion_menu = {
                "Empresas": "empresas",
                "Acciones Formativas": "acciones_formativas",
                "Grupos": "grupos",
                "Participantes": "participantes",
                "Tutores": "tutores",
                "Aulas": "aulas",
                "Gestión Clases": "gestion_clases",
                "Proyectos": "proyectos",
                "Documentos": "documentos"
            }
        
        for label, page_key in formacion_menu.items():
            if st.sidebar.button(label, key=f"formacion_{page_key}_{rol}"):
                st.session_state.page = page_key

    # Resto de módulos (ISO, RGPD, CRM, etc.) - CÓDIGO COMPLETO RESTAURADO
    
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
            rol = st.session_state.role
            hoy = datetime.today().date()
            empresa = st.session_state.get("empresa", {})
            empresa_crm = st.session_state.get("empresa_crm", {})

            # Dashboard principal con tarjetas modernas
            ajustes = get_ajustes_app(
                supabase_admin,
                campos=[
                    "bienvenida_admin", "bienvenida_gestor", "bienvenida_alumno", "bienvenida_comercial",
                    "tarjeta_admin_usuarios", "tarjeta_admin_empresas", "tarjeta_admin_ajustes",
                    "tarjeta_gestor_grupos", "tarjeta_gestor_documentos", "tarjeta_gestor_docu_avanzada",
                    "tarjeta_alumno_grupos", "tarjeta_alumno_diplomas", "tarjeta_alumno_seguimiento",
                    "tarjeta_comercial_clientes", "tarjeta_comercial_oportunidades", "tarjeta_comercial_tareas",
                    "nombre_app"
                ]
            )

            if rol == "gestor":
                st.title("👋 Bienvenido al Panel del Gestor")
                st.subheader(ajustes.get("bienvenida_gestor", "Panel de Gestión de Formación"))
                
                # Nueva funcionalidad de empresas
                with st.expander("🆕 Nueva Funcionalidad: Gestión de Empresas"):
                    st.markdown("""
                    **Ahora puedes gestionar empresas clientes:**
                    - 🏢 Crear empresas que dependen de la tuya
                    - 📚 Asignar empresas clientes a grupos de formación  
                    - 👥 Gestionar participantes de múltiples empresas
                    - 📄 Organizar diplomas por empresa cliente
                    
                    Accede desde **📚 Gestión de Formación > Empresas**
                    """)
            else:
                bienvenida_por_rol = {
                    "admin": ajustes.get("bienvenida_admin", "Panel de Administración SaaS"),
                    "alumno": ajustes.get("bienvenida_alumno", "Área del Alumno"),
                    "comercial": ajustes.get("bienvenida_comercial", "Área Comercial - CRM")
                }

                titulo_app = ajustes.get("nombre_app", "Gestor de Formación")
                st.title(f"👋 Bienvenido al {titulo_app}")
                st.subheader(bienvenida_por_rol.get(rol, "Bienvenido"))

            # Métricas dinámicas con diseño moderno
            if rol == "admin":
                with st.spinner("Cargando métricas del sistema..."):
                    metricas = get_metricas_admin()
                
                st.subheader("📊 Métricas globales del sistema")
                
                # Usar columnas con métricas nativas de Streamlit 1.49
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        label="🏢 Empresas",
                        value=metricas['empresas'],
                        delta=None,
                        help="Empresas registradas en el sistema"
                    )
                
                with col2:
                    st.metric(
                        label="👥 Usuarios", 
                        value=metricas['usuarios'],
                        delta=None,
                        help="Usuarios activos del sistema"
                    )
                
                with col3:
                    st.metric(
                        label="📚 Cursos",
                        value=metricas['cursos'], 
                        delta=None,
                        help="Acciones formativas disponibles"
                    )
                
                with col4:
                    st.metric(
                        label="👥 Grupos",
                        value=metricas['grupos'],
                        delta=None,
                        help="Grupos formativos creados"
                    )
                
                # Tarjetas adicionales con HTML moderno
                st.markdown(tarjeta_moderna(
                    "⚙️", "Configuración", 
                    ajustes.get('tarjeta_admin_ajustes', 'Configuración global del sistema'),
                    activo=True, color="#667eea"
                ), unsafe_allow_html=True)

            elif rol == "gestor":
                empresa_id = st.session_state.user.get("empresa_id")
                if empresa_id:
                    with st.spinner("Cargando actividad de tu empresa..."):
                        metricas = get_metricas_gestor(empresa_id)

                    st.subheader("📊 Actividad de tu empresa")
                    
                    # Métricas nativas con delta
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            label="👥 Grupos",
                            value=metricas['grupos'],
                            delta=None,
                            help="Grupos formativos de tu empresa"
                        )
                    
                    with col2:
                        st.metric(
                            label="🧑‍🎓 Participantes",
                            value=metricas['participantes'],
                            delta=None,
                            help="Alumnos registrados"
                        )
                    
                    with col3:
                        st.metric(
                            label="📄 Documentos",
                            value=metricas['documentos'],
                            delta=None,
                            help="Archivos gestionados"
                        )

                    # Tarjeta condicional para documentación avanzada
                    if is_module_active(empresa, empresa_crm, "docu_avanzada", hoy, rol):
                        st.markdown(tarjeta_moderna(
                            "📁", "Documentación Avanzada", 
                            ajustes.get('tarjeta_gestor_docu_avanzada', 'Gestión documental avanzada'),
                            activo=True, color="#764ba2"
                        ), unsafe_allow_html=True)

            elif rol == "alumno":
                st.subheader("📋 Área del Alumno")
                
                # Tarjetas específicas para alumno
                tarjetas_alumno = [
                    ("👥", "Mis grupos", ajustes.get("tarjeta_alumno_grupos", "Consulta tus grupos formativos"), "#4CAF50"),
                    ("📜", "Diplomas", ajustes.get("tarjeta_alumno_diplomas", "Descarga tus certificados"), "#FF9800"),
                    ("📊", "Seguimiento", ajustes.get("tarjeta_alumno_seguimiento", "Revisa tu progreso formativo"), "#2196F3")
                ]
                
                for icono, titulo, desc, color in tarjetas_alumno:
                    st.markdown(tarjeta_moderna(icono, titulo, desc, True, color), unsafe_allow_html=True)

            elif rol == "comercial":
                st.subheader("📋 Área Comercial")
                
                # Tarjetas específicas para comercial
                tarjetas_comercial = [
                    ("👤", "Clientes", ajustes.get("tarjeta_comercial_clientes", "Gestiona tu cartera de clientes"), "#E91E63"),
                    ("💼", "Oportunidades", ajustes.get("tarjeta_comercial_oportunidades", "Seguimiento de ventas"), "#9C27B0"),
                    ("📅", "Tareas", ajustes.get("tarjeta_comercial_tareas", "Organiza tu actividad comercial"), "#3F51B5")
                ]
                
                for icono, titulo, desc, color in tarjetas_comercial:
                    st.markdown(tarjeta_moderna(icono, titulo, desc, True, color), unsafe_allow_html=True)

            # Añadir información sobre nuevas funcionalidades de Streamlit 1.49
            with st.expander("🚀 Novedades de la plataforma"):
                st.markdown("""
                **Mejoras implementadas:**
                - ✨ **Diseño moderno**: Interface renovada con gradientes y animaciones
                - 🎯 **Métricas mejoradas**: Componentes nativos de Streamlit 1.49
                - 📱 **Responsive**: Adaptado para móviles y tablets
                - ⚡ **Carga optimizada**: Barras de progreso y feedback visual
                - 🎨 **Personalizable**: Colores y textos configurables desde ajustes
                """)

    except Exception as e:
        st.error(f"❌ Error al cargar la página '{page or 'inicio'}': {e}")
        st.exception(e)
