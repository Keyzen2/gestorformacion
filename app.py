import os
import sys
import streamlit as st
from utils import get_ajustes_app, is_module_active  # ✅ Mantener imports existentes
from services.data_service import get_data_service  # ✅ NUEVO: Añadir DataService
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
# ✅ OPTIMIZACIÓN: Eliminar funciones duplicadas
# Las funciones get_metricas_admin() y get_metricas_gestor() 
# ya existen en DataService, por lo que se eliminan de aquí
# =========================

# =========================
# Función de login
# =========================
def login_view():
    """Vista de login optimizada."""
    ajustes = get_ajustes_app(supabase_admin, campos=["mensaje_login", "nombre_app", "color_primario"])
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown(f"""
        <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-bottom: 2rem;">
            <h1 style="color: white; margin: 0;">{ajustes.get('nombre_app', 'Gestor de Formación')}</h1>
            <p style="color: white; margin: 0.5rem 0 0 0;">{ajustes.get('mensaje_login', 'Accede al gestor con tus credenciales')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.subheader("🔐 Iniciar Sesión")
            email = st.text_input("📧 Email", placeholder="usuario@empresa.com")
            password = st.text_input("🔑 Contraseña", type="password")
            login_btn = st.form_submit_button("🚀 Entrar", use_container_width=True)
            
            if login_btn and email and password:
                try:
                    # Autenticación
                    response = supabase_public.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    
                    if response.user:
                        # Obtener datos del usuario
                        user_data = supabase_admin.table("usuarios").select(
                            "id, email, rol, empresa_id, nombre, apellidos"
                        ).eq("id", response.user.id).execute()
                        
                        if user_data.data:
                            user_info = user_data.data[0]
                            st.session_state.auth_session = response
                            st.session_state.role = user_info["rol"]
                            st.session_state.user = user_info
                            st.success("✅ Login exitoso")
                            st.rerun()
                        else:
                            st.error("❌ Usuario no encontrado en la base de datos")
                    
                except Exception as e:
                    st.error(f"❌ Error de login: {e}")

def do_logout():
    """Cierra sesión y limpia estado."""
    try:
        if st.session_state.get("auth_session"):
            supabase_public.auth.sign_out()
    except:
        pass
    
    # Limpiar estado
    for key in ["role", "user", "auth_session", "page", "empresa", "empresa_crm"]:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()

# =========================
# ✅ OPTIMIZACIÓN: Función de tarjetas con cache
# =========================
@st.cache_data(ttl=3600)  # Cache por 1 hora - es solo HTML
def tarjeta(icono, titulo, descripcion, activo=True, color_activo="#d1fae5"):
    """Genera HTML para tarjetas del dashboard con cache optimizado."""
    color = color_activo if activo else "#f3f4f6"
    return f"""
    <div style="
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 15px;
        background-color: {color};
        box-shadow: 0px 2px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s ease;
    ">
        <h3 style="margin:0; font-size: 1.2em;">{icono} {titulo}</h3>
        <p style="margin:0; color:#374151; font-size: 0.9em;">{descripcion}</p>
    </div>
    """

# =========================
# ✅ OPTIMIZACIÓN: Métricas usando DataService
# =========================
def mostrar_metricas_dashboard(supabase, session_state, rol, empresa_id=None):
    """Muestra métricas optimizadas usando DataService."""
    try:
        # ✅ Usar DataService en lugar de funciones duplicadas
        data_service = get_data_service(supabase, session_state)
        
        if rol == "admin":
            # Métricas globales para admin
            with st.spinner("Cargando métricas administrativas..."):
                metricas = data_service.get_metricas_admin()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🏢 Empresas", metricas.get("total_empresas", 0))
            with col2:
                st.metric("👥 Usuarios", metricas.get("total_usuarios", 0))
            with col3:
                st.metric("📚 Cursos", metricas.get("total_cursos", 0))
            with col4:
                st.metric("🎯 Grupos", metricas.get("total_grupos", 0))
                
        elif rol == "gestor" and empresa_id:
            # Métricas específicas para gestor
            with st.spinner("Cargando métricas de empresa..."):
                metricas = data_service.get_metricas_empresa(empresa_id)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("👥 Grupos", metricas.get("total_grupos", 0))
            with col2:
                st.metric("🧑‍🎓 Participantes", metricas.get("total_participantes", 0))
            with col3:
                st.metric("📄 Documentos", metricas.get("total_documentos", 0))
            with col4:
                st.metric("🎯 Acciones", metricas.get("total_acciones", 0))
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error al cargar métricas: {e}")
        return False

# =========================
# Sidebar y navegación + Bienvenida
# =========================
def route():
    nombre_usuario = st.session_state.user.get("nombre") or st.session_state.user.get("email", "Usuario")
    st.sidebar.markdown(f"### 👋 Bienvenido, **{nombre_usuario}**")

    # Botón de logout mejorado
    if st.sidebar.button("🚪 Cerrar sesión", key="logout", help="Cerrar sesión y limpiar datos"):
        do_logout()

    # --- Obtener empresa y módulos ---
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

    # --- Administración SaaS (solo admin) ---
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
            st.session_state.page = "mis_grupos"
            
    # --- Panel del Gestor (solo gestores con formación activa) ---
    if rol == "gestor" and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📊 Panel de Formación")
        panel_menu = {
            "Panel del Gestor": "panel_gestor"
        }
        for label, page_key in panel_menu.items():
            if st.sidebar.button(label, key=f"panel_{page_key}_{rol}"):
                st.session_state.page = page_key

    # --- Módulo Formación ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📚 Gestión de Formación")
        formacion_menu = {
            "Acciones Formativas": "acciones_formativas",
            "Grupos": "grupos",
            "Participantes": "participantes",
            "Tutores": "tutores",
            "Documentos": "documentos"
        }
        for label, page_key in formacion_menu.items():
            if st.sidebar.button(label, key=f"formacion_{page_key}_{rol}"):
                st.session_state.page = page_key

    # --- Módulo ISO ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "iso", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📋 Gestión ISO 9001")
        iso_menu = {
            "Procesos": "iso_procesos",
            "Documentación": "iso_documentacion",
            "Auditorías": "iso_auditorias",
            "No Conformidades": "iso_no_conformidades",
            "Mejora Continua": "iso_mejora_continua"
        }
        for label, page_key in iso_menu.items():
            if st.sidebar.button(label, key=f"iso_{page_key}_{rol}"):
                st.session_state.page = page_key

    # --- Módulo RGPD ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "rgpd", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 🔒 Gestión RGPD")
        rgpd_menu = {
            "Registro de Actividades": "rgpd_registro",
            "Evaluaciones de Impacto": "rgpd_evaluaciones",
            "Brechas de Seguridad": "rgpd_brechas",
            "Derechos ARCO": "rgpd_derechos"
        }
        for label, page_key in rgpd_menu.items():
            if st.sidebar.button(label, key=f"rgpd_{page_key}_{rol}"):
                st.session_state.page = page_key

    # --- Módulo CRM ---
    if rol in ["admin", "gestor", "comercial"] and is_module_active(empresa, empresa_crm, "crm", hoy, rol):
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📈 CRM Comercial")
        crm_menu = {
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

    # --- Footer dinámico desde ajustes_app ---
    ajustes = get_ajustes_app(supabase_admin, campos=["mensaje_footer"])
    mensaje_footer = ajustes.get("mensaje_footer", "© 2025 Gestor de Formación · ISO 9001 · RGPD · CRM · Formación · Streamlit + Supabase")

    st.sidebar.markdown("---")
    st.sidebar.caption(mensaje_footer)

# =========================
# ✅ OPTIMIZACIÓN: Dashboard principal con DataService
# =========================
def mostrar_dashboard():
    """Dashboard principal optimizado."""
    try:
        # Cargar ajustes con manejo de errores
        try:
            ajustes = get_ajustes_app(supabase_admin)
        except Exception as e:
            st.error(f"⚠️ Error al cargar ajustes: {e}")
            # Fallback con ajustes por defecto
            ajustes = {
                "bienvenida_admin": "Panel de Administración SaaS",
                "bienvenida_gestor": "Panel del Gestor", 
                "bienvenida_alumno": "Área del Alumno",
                "bienvenida_comercial": "Área Comercial - CRM"
            }
        
        rol = st.session_state.role
        empresa_id = st.session_state.user.get("empresa_id")
        empresa = st.session_state.get("empresa", {})
        empresa_crm = st.session_state.get("empresa_crm", {})
        hoy = datetime.today().date()

        # === Bienvenida personalizada ===
        if rol == "admin":
            st.title(ajustes.get("bienvenida_admin", "Panel de Administración SaaS"))
            st.markdown("Gestiona empresas, usuarios y configuración global del sistema.")
            
            # ✅ Métricas usando DataService
            mostrar_metricas_dashboard(supabase_admin, st.session_state, rol)

        elif rol == "gestor":
            st.title(ajustes.get("bienvenida_gestor", "Panel del Gestor"))
            st.markdown("Gestiona la formación y calidad de tu empresa.")
            
            # ✅ Métricas usando DataService
            if empresa_id:
                mostrar_metricas_dashboard(supabase_admin, st.session_state, rol, empresa_id)

            # Tarjetas de módulos activos
            st.divider()
            if is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
                st.markdown(tarjeta("📚", "Formación", ajustes.get('tarjeta_gestor_formacion', 'Gestión completa de acciones formativas')), unsafe_allow_html=True)

            if is_module_active(empresa, empresa_crm, "docu_avanzada", hoy, rol):
                st.markdown(tarjeta("📁", "Documentación Avanzada", f"<small>{ajustes.get('tarjeta_gestor_docu_avanzada', 'Gestión documental avanzada')}</small>", activo=True), unsafe_allow_html=True)

        elif rol == "alumno":
            st.title(ajustes.get("bienvenida_alumno", "Área del Alumno"))
            st.markdown(tarjeta("👥", "Mis grupos", ajustes.get("tarjeta_alumno_grupos", "Consulta tus grupos formativos")), unsafe_allow_html=True)
            st.markdown(tarjeta("📜", "Diplomas", ajustes.get("tarjeta_alumno_diplomas", "Descarga tus certificados")), unsafe_allow_html=True)
            st.markdown(tarjeta("📊", "Seguimiento", ajustes.get("tarjeta_alumno_seguimiento", "Revisa tu progreso formativo")), unsafe_allow_html=True)

        elif rol == "comercial":
            st.title(ajustes.get("bienvenida_comercial", "Área Comercial - CRM"))
            st.markdown(tarjeta("👤", "Clientes", ajustes.get("tarjeta_comercial_clientes", "Gestiona tu cartera de clientes")), unsafe_allow_html=True)
            st.markdown(tarjeta("📝", "Oportunidades", ajustes.get("tarjeta_comercial_oportunidades", "Seguimiento de ventas")), unsafe_allow_html=True)
            st.markdown(tarjeta("📅", "Tareas", ajustes.get("tarjeta_comercial_tareas", "Organiza tu actividad comercial")), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Error al cargar dashboard: {e}")

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
            # Mostrar spinner mientras carga la página
            with st.spinner(f"Cargando {page}..."):
                if page == "panel_gestor" and st.session_state.role == "gestor":
                    from pages.panel_gestor import main as panel_gestor_main
                    panel_gestor_main(supabase_admin, st.session_state)
                else:
                    mod = page.replace("-", "_")
                    mod_path = f"pages.{mod}"
                    
                    try:
                        module = __import__(mod_path, fromlist=[mod])
                        module.main(supabase_admin, st.session_state)
                    except ImportError:
                        st.error(f"❌ Página '{page}' no encontrada")
                        st.session_state.page = "home"
                        st.rerun()
        else:
            # Dashboard principal
            mostrar_dashboard()

    except Exception as e:
        st.error(f"❌ Error al cargar la página '{page or 'inicio'}': {e}")
        if st.session_state.role == "admin":  # Solo mostrar detalles a admin
            st.exception(e)
