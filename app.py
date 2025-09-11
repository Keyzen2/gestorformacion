import os
import sys
import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
import pandas as pd
from utils import get_ajustes_app

# =========================
# Configuración de la aplicación
# =========================
st.set_page_config(
    page_title="Gestor de Formación",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# Configuración de Supabase
# =========================
supabase_public: Client = create_client(
    st.secrets["SUPABASE_URL"], 
    st.secrets["SUPABASE_ANON_KEY"]
)

supabase_admin: Client = create_client(
    st.secrets["SUPABASE_URL"], 
    st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
)

# =========================
# Funciones auxiliares optimizadas (SIN CACHE PROBLEMÁTICO)
# =========================

def get_metricas_admin():
    """Obtiene métricas del admin de forma optimizada."""
    try:
        # Usar COUNT en lugar de SELECT *
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
        # Fallback a método anterior si no existe la función RPC
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
        st.error(f"❌ Error al cargar métricas: {e}")
        return {"grupos": 0, "participantes": 0, "documentos": 0}

def set_user_role_from_db(email: str):
    """
    Obtiene el rol y datos básicos del usuario desde la base de datos
    y los guarda en session_state.
    """
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
            # Guardar comercial_id si es comercial
            if rol == "comercial":
                com_res = supabase_public.table("comerciales").select("id").eq("usuario_id", row.get("id")).execute()
                if com_res.data:
                    st.session_state.user["comercial_id"] = com_res.data[0]["id"]
        else:
            # Usuario no encontrado: rol por defecto alumno
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
    # Limpiar cache
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

def login_view():
    """Pantalla de login con tarjetas de módulos."""

    # ✅ Obtener mensaje de login desde ajustes (CORREGIDO)
    ajustes = get_ajustes_app(supabase_admin, campos=["mensaje_login"])
    mensaje_login = ajustes.get("mensaje_login", "Accede al gestor con tus credenciales.")

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; background-color: #f5f5f5'; }
    .module-card { background-color: white; padding: 1em; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 1em; }
    .module-card h4 { margin: 0; color: #4285F4; }
    .module-card p { margin: 0.5em 0 0; color: #5f6368; }
    </style>
    <div class="module-card"><h4>📚 Formación</h4><p>Gestión de acciones formativas, grupos, participantes y documentos.</p></div>
    <div class="module-card"><h4>📋 ISO 9001</h4><p>Auditorías, informes y seguimiento de calidad.</p></div>
    <div class="module-card"><h4>🔐 RGPD</h4><p>Consentimientos, documentación legal y trazabilidad.</p></div>
    <div class="module-card"><h4>📈 CRM</h4><p>Gestión de clientes, oportunidades y tareas comerciales.</p></div>
    """, unsafe_allow_html=True)

    st.markdown("### 🔐 Iniciar sesión")
    st.caption(mensaje_login)

    with st.form("form_login_acceso", clear_on_submit=False):
        email = st.text_input("Email", autocomplete="email")
        password = st.text_input("Contraseña", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        if not email or not password:
            st.warning("Introduce email y contraseña.")
        else:
            with st.spinner("Iniciando sesión..."):
                try:
                    auth = supabase_public.auth.sign_in_with_password({"email": email, "password": password})
                    if not auth or not auth.user:
                        st.error("Credenciales inválidas.")
                    else:
                        st.session_state.auth_session = auth
                        set_user_role_from_db(auth.user.email)
                        st.success("✅ Sesión iniciada correctamente")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al iniciar sesión: {e}")

# =========================
# Función de verificación de módulo activo
# =========================
def is_module_active(empresa, empresa_crm, key, hoy, role):
    """
    Comprueba si un módulo está activo para la empresa del usuario.
    Admin y gestor (admin_empresa) pueden ver módulos activos de su empresa.
    Comercial solo CRM. Alumno nunca ve módulos.
    """
    if role == "admin":
        return True  # Admin ve todos los módulos

    if role == "alumno":
        return False  # Alumno no ve módulos empresariales

    if role == "comercial":
        return key == "crm"  # Comercial solo ve CRM

    # Para gestores
    if not empresa:
        return False

    if key == "crm":
        # CRM requiere verificación especial
        if not empresa_crm:
            return False
        crm_activo = empresa_crm.get("crm_activo", False)
        if not crm_activo:
            return False
        # Verificar fechas si existen
        inicio = empresa_crm.get("crm_inicio")
        fin = empresa_crm.get("crm_fin")
        if inicio:
            try:
                fecha_inicio = datetime.strptime(inicio, "%Y-%m-%d").date()
                if hoy < fecha_inicio:
                    return False
            except (ValueError, TypeError):
                pass
        if fin:
            try:
                fecha_fin = datetime.strptime(fin, "%Y-%m-%d").date()
                if hoy > fecha_fin:
                    return False
            except (ValueError, TypeError):
                pass
        return True
    else:
        # Otros módulos verifican directamente en empresa
        return empresa.get(f"{key}_activo", False)

# =========================
# Función principal de navegación
# =========================
def main_app():
    """Función principal de la aplicación."""
    
    # Verificar autenticación
    if "auth_session" not in st.session_state or not st.session_state.auth_session:
        login_view()
        return

    # Configurar sidebar
    with st.sidebar:
        st.markdown("### 👤 Usuario")
        user_email = st.session_state.user.get("email", "Sin email")
        user_role = st.session_state.role
        st.write(f"**Email:** {user_email}")
        st.write(f"**Rol:** {user_role.title()}")
        
        if st.button("🚪 Cerrar sesión"):
            do_logout()
            return

        st.markdown("---")

    # Obtener datos del usuario y empresa
    rol = st.session_state.role
    user_id = st.session_state.user.get("id")
    empresa_id = st.session_state.user.get("empresa_id")
    
    # Cargar datos de empresa si es gestor
    empresa = {}
    empresa_crm = {}
    if rol == "gestor" and empresa_id:
        try:
            empresa_res = supabase_admin.table("empresas").select("*").eq("id", empresa_id).single().execute()
            empresa = empresa_res.data or {}
            
            crm_res = supabase_admin.table("crm_empresas").select("*").eq("empresa_id", empresa_id).single().execute()
            empresa_crm = crm_res.data or {}
        except Exception:
            pass

    # Navegación por páginas
    if "page" not in st.session_state:
        st.session_state.page = "home"

    # --- Sidebar de navegación ---
    with st.sidebar:
        st.markdown("### 🧭 Navegación")

        # Página de inicio
        if st.button("🏠 Inicio", key="nav_home"):
            st.session_state.page = "home"

    # --- Panel de Administración (solo admin) ---
    if rol == "admin":
        with st.sidebar:
            st.markdown("---")
            st.markdown("#### ⚙️ Administración")
            admin_menu = {
                "Panel de Admin": "panel_admin",
                "Usuarios y Empresas": "usuarios_empresas",
                "Empresas": "empresas",
                "Ajustes de la App": "ajustes_app"
            }
            for label, page_key in admin_menu.items():
                if st.button(label, key=f"admin_{page_key}_{rol}"):
                    st.session_state.page = page_key

    elif rol == "alumno":
        with st.sidebar:
            st.markdown("#### 🎓 Área del Alumno")
            if st.button("Mis Grupos y Diplomas", key="alumno_mis_grupos"):
                st.session_state.page = "mis_grupos"
            
    # --- Panel del Gestor (solo gestores con formación activa) ---
    if rol == "gestor" and is_module_active(empresa, empresa_crm, "formacion", date.today(), rol):
        with st.sidebar:
            st.markdown("---")
            st.markdown("#### 📊 Panel de Formación")
            panel_menu = {
                "Panel del Gestor": "panel_gestor"
            }
            for label, page_key in panel_menu.items():
                if st.button(label, key=f"panel_{page_key}_{rol}"):
                    st.session_state.page = page_key

    # --- Módulo Formación ---
    hoy = date.today()
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "formacion", hoy, rol):
        with st.sidebar:
            st.markdown("---")
            st.markdown("#### 📚 Gestión de Formación")
            formacion_menu = {
                "Acciones Formativas": "acciones_formativas",
                "Grupos": "grupos",
                "Participantes": "participantes",
                "Tutores": "tutores",
                "Documentos": "documentos"
            }
            for label, page_key in formacion_menu.items():
                if st.button(label, key=f"formacion_{page_key}_{rol}"):
                    st.session_state.page = page_key

    # --- Módulo ISO ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "iso", hoy, rol):
        with st.sidebar:
            st.markdown("---")
            st.markdown("#### 📋 ISO 9001")
            iso_menu = {
                "Auditorías": "auditorias",
                "Indicadores": "indicadores", 
                "Informes": "informes_iso"
            }
            for label, page_key in iso_menu.items():
                if st.button(label, key=f"iso_{page_key}_{rol}"):
                    st.session_state.page = page_key

    # --- Módulo RGPD ---
    if rol in ["admin", "gestor"] and is_module_active(empresa, empresa_crm, "rgpd", hoy, rol):
        with st.sidebar:
            st.markdown("---")
            st.markdown("#### 🔐 RGPD")
            rgpd_menu = {
                "Consentimientos": "consentimientos",
                "Tratamientos": "tratamientos",
                "Registro de Actividades": "registro_actividades"
            }
            for label, page_key in rgpd_menu.items():
                if st.button(label, key=f"rgpd_{page_key}_{rol}"):
                    st.session_state.page = page_key

    # --- Módulo CRM ---
    if rol in ["admin", "gestor", "comercial"] and is_module_active(empresa, empresa_crm, "crm", hoy, rol):
        with st.sidebar:
            st.markdown("---")
            st.markdown("#### 📈 CRM")
            crm_menu = {
                "Clientes": "clientes",
                "Oportunidades": "oportunidades",
                "Tareas": "tareas"
            }
            for label, page_key in crm_menu.items():
                if st.button(label, key=f"crm_{page_key}_{rol}"):
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

    # --- Footer dinámico desde ajustes_app (caché segura) ---
    ajustes = get_ajustes_app(["mensaje_footer"])
    mensaje_footer = ajustes.get("mensaje_footer", "© 2025 Gestor de Formación · ISO 9001 · RGPD · CRM · Formación · Streamlit + Supabase")

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
            # Mostrar spinner mientras carga la página
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

            ajustes = get_ajustes_app([
                "bienvenida_admin", "bienvenida_gestor", "bienvenida_alumno", "bienvenida_comercial",
                "tarjeta_admin_usuarios", "tarjeta_admin_empresas", "tarjeta_admin_ajustes",
                "tarjeta_gestor_grupos", "tarjeta_gestor_documentos", "tarjeta_gestor_docu_avanzada",
                "tarjeta_alumno_grupos", "tarjeta_alumno_diplomas", "tarjeta_alumno_seguimiento",
                "tarjeta_comercial_clientes", "tarjeta_comercial_oportunidades", "tarjeta_comercial_tareas"
            ])

            bienvenida_por_rol = {
                "admin": ajustes.get("bienvenida_admin", "Panel de Administración SaaS"),
                "gestor": ajustes.get("bienvenida_gestor", "Panel del Gestor"),
                "alumno": ajustes.get("bienvenida_alumno", "Área del Alumno"),
                "comercial": ajustes.get("bienvenida_comercial", "Área Comercial - CRM")
            }

            st.title("👋 Bienvenido al Gestor de Formación")
            st.subheader(bienvenida_por_rol.get(rol, "Bienvenido"))

            # ===============================
            # MÉTRICAS DINÁMICAS POR ROL OPTIMIZADAS
            # ===============================
            if rol == "admin":
                with st.spinner("Cargando métricas del sistema..."):
                    metricas = get_metricas_admin()
                
                st.subheader("📊 Métricas globales del sistema")
                col1, col2, col3 = st.columns(3)
                col1.markdown(tarjeta("🏢", "Empresas", f"{metricas['empresas']} registradas<br><small>{ajustes.get('tarjeta_admin_empresas', 'Empresas del sistema')}</small>"), unsafe_allow_html=True)
                col2.markdown(tarjeta("👥", "Usuarios", f"{metricas['usuarios']} activos<br><small>{ajustes.get('tarjeta_admin_usuarios', 'Usuarios registrados')}</small>"), unsafe_allow_html=True)
                col3.markdown(tarjeta("📚", "Cursos", f"{metricas['cursos']} disponibles<br><small>Acciones formativas activas</small>"), unsafe_allow_html=True)
                st.markdown(tarjeta("⚙️", "Ajustes", f"<small>{ajustes.get('tarjeta_admin_ajustes', 'Configuración global')}</small>"), unsafe_allow_html=True)

            elif rol == "gestor":
                empresa_id = st.session_state.user.get("empresa_id")
                if empresa_id:
                    with st.spinner("Cargando actividad de tu empresa..."):
                        metricas = get_metricas_gestor(empresa_id)

                    st.subheader("📊 Actividad de tu empresa")
                    col1, col2, col3 = st.columns(3)
                    col1.markdown(tarjeta("👥", "Grupos", f"{metricas['grupos']} creados<br><small>{ajustes.get('tarjeta_gestor_grupos', 'Grupos formativos')}</small>"), unsafe_allow_html=True)
                    col2.markdown(tarjeta("🧑‍🎓", "Participantes", f"{metricas['participantes']} registrados<br><small>Alumnos en formación</small>"), unsafe_allow_html=True)
                    col3.markdown(tarjeta("📄", "Documentos", f"{metricas['documentos']} subidos<br><small>{ajustes.get('tarjeta_gestor_documentos', 'Archivos gestionados')}</small>"), unsafe_allow_html=True)

                    if is_module_active(empresa, empresa_crm, "docu_avanzada", hoy, rol):
                        st.markdown(tarjeta("📁", "Documentación Avanzada", f"<small>{ajustes.get('tarjeta_gestor_docu_avanzada', 'Gestión documental avanzada')}</small>", activo=True), unsafe_allow_html=True)

            elif rol == "alumno":
                st.subheader("📋 Área del Alumno")
                st.markdown(tarjeta("👥", "Mis grupos", ajustes.get("tarjeta_alumno_grupos", "Consulta tus grupos formativos")), unsafe_allow_html=True)
                st.markdown(tarjeta("📜", "Diplomas", ajustes.get("tarjeta_alumno_diplomas", "Descarga tus certificados")), unsafe_allow_html=True)
                st.markdown(tarjeta("📊", "Seguimiento", ajustes.get("tarjeta_alumno_seguimiento", "Revisa tu progreso formativo")), unsafe_allow_html=True)

            elif rol == "comercial":
                st.subheader("📋 Área Comercial")
                st.markdown(tarjeta("👤", "Clientes", ajustes.get("tarjeta_comercial_clientes", "Gestiona tu cartera de clientes")), unsafe_allow_html=True)
                st.markdown(tarjeta("📝", "Oportunidades", ajustes.get("tarjeta_comercial_oportunidades", "Seguimiento de ventas")), unsafe_allow_html=True)
                st.markdown(tarjeta("📅", "Tareas", ajustes.get("tarjeta_comercial_tareas", "Organiza tu actividad comercial")), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Error al cargar la página '{page or 'inicio'}': {e}")
        st.exception(e)  # Para debugging en desarrollo
