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
    initial_sidebar_state="collapsed",
    page_icon="🚀",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "# Gestor de Formación\n### Sistema integral de gestión empresarial"
    }
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
    "auth_session": None,
    "login_loading": False,
    "show_login": False  # NUEVO: controla si mostrar login o landing
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =========================
# Importar funciones del código original
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
    # Resetear a landing en lugar de login directo
    st.session_state.show_login = False
    st.rerun()

# =========================
# LANDING PAGE COMERCIAL
# =========================
def landing_page():
    """Landing page comercial inspirada en Google Classroom"""
    
    # CSS moderno para landing startup (mismo que el artefacto anterior)
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* Reset y base */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        margin: 0;
        padding: 0;
    }
    
    /* Ocultar elementos de Streamlit */
    .stAppViewContainer > .main .block-container {
        padding: 0;
        max-width: 100%;
    }
    
    header[data-testid="stHeader"] {
        display: none;
    }
    
    /* Navbar fijo */
    .landing-navbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        padding: 1rem 0;
        z-index: 1000;
        display: flex;
        justify-content: space-between;
        align-items: center;
        max-width: 1200px;
        margin: 0 auto;
        padding: 1rem 2rem;
    }
    
    .landing-logo {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a202c;
    }
    
    .landing-logo-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 1.2rem;
    }
    
    /* Hero section */
    .landing-hero {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 8rem 0 6rem;
        margin-top: 80px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    
    .landing-hero::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M30 30c0-11.046-8.954-20-20-20s-20 8.954-20 20 8.954 20 20 20 20-8.954 20-20zm0 0c0-11.046 8.954-20 20-20s20 8.954 20 20-8.954 20-20 20-20-8.954-20-20z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
        opacity: 0.5;
    }
    
    .landing-hero-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 2rem;
        position: relative;
        z-index: 1;
    }
    
    .landing-hero-title {
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 1.5rem;
        line-height: 1.1;
    }
    
    .landing-hero-subtitle {
        font-size: 1.25rem;
        font-weight: 400;
        margin-bottom: 3rem;
        opacity: 0.9;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    
    /* Features section */
    .landing-features {
        padding: 6rem 0;
        background: #f8fafc;
    }
    
    .landing-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 2rem;
    }
    
    .landing-section-title {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a202c;
        margin-bottom: 1rem;
    }
    
    .landing-section-subtitle {
        text-align: center;
        font-size: 1.1rem;
        color: #4a5568;
        margin-bottom: 4rem;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    
    .landing-features-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 2rem;
        margin-bottom: 4rem;
    }
    
    .landing-feature-card {
        background: white;
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
        border: 1px solid rgba(0, 0, 0, 0.05);
    }
    
    .landing-feature-card:hover {
        transform: translateY(-8px);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
    }
    
    .landing-feature-icon {
        width: 60px;
        height: 60px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        color: white;
        margin-bottom: 1.5rem;
    }
    
    .landing-feature-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #1a202c;
        margin-bottom: 0.75rem;
    }
    
    .landing-feature-desc {
        color: #4a5568;
        line-height: 1.6;
    }
    
    /* Modules showcase */
    .landing-modules {
        padding: 6rem 0;
        background: white;
    }
    
    .landing-modules-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.5rem;
        margin-top: 3rem;
    }
    
    .landing-module-card {
        background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        transition: all 0.3s ease;
        border: 2px solid transparent;
    }
    
    .landing-module-card:hover {
        border-color: #667eea;
        transform: translateY(-4px);
    }
    
    .landing-module-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        display: block;
    }
    
    .landing-module-name {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a202c;
        margin-bottom: 0.5rem;
    }
    
    .landing-module-desc {
        color: #4a5568;
        font-size: 0.9rem;
    }
    
    /* Footer */
    .landing-footer {
        background: #1a202c;
        color: white;
        padding: 3rem 0 2rem;
        text-align: center;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .landing-hero-title {
            font-size: 2.5rem;
        }
        
        .landing-features-grid {
            grid-template-columns: 1fr;
        }
    }
    
    /* Animaciones */
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
        animation: fadeInUp 0.8s ease-out;
    }
    
    .fade-in-up-delay-1 {
        animation: fadeInUp 0.8s ease-out 0.2s both;
    }
    
    .fade-in-up-delay-2 {
        animation: fadeInUp 0.8s ease-out 0.4s both;
    }
    </style>
    """, unsafe_allow_html=True)

    # Navbar con botón de login
    col1, col2 = st.columns([6, 1])
    
    with col1:
        st.markdown("""
        <div class="landing-navbar">
            <div class="landing-logo">
                <div class="landing-logo-icon">🚀</div>
                <span>Gestor de Formación</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("<div style='margin-top: 80px;'></div>", unsafe_allow_html=True)
        if st.button("🔐 Acceder", key="header_login", help="Acceder al sistema", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()

    # Hero Section
    st.markdown("""
    <div class="landing-hero">
        <div class="landing-hero-container">
            <h1 class="landing-hero-title fade-in-up">
                Gestiona la formación de tu empresa como nunca antes
            </h1>
            <p class="landing-hero-subtitle fade-in-up-delay-1">
                Plataforma integral SaaS para formación FUNDAE, ISO 9001, RGPD y CRM. 
                Todo lo que necesitas para digitalizar tu gestión empresarial.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Botones CTA principales
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✨ Prueba gratuita", key="cta_trial", use_container_width=True):
                st.session_state.show_login = True
                st.rerun()
        with col_b:
            if st.button("📋 Ver características", key="cta_features", use_container_width=True, type="secondary"):
                pass  # Scroll to features (implementar con JavaScript si es necesario)

    # Features Section
    st.markdown("""
    <div class="landing-features" id="features">
        <div class="landing-container">
            <h2 class="landing-section-title">¿Por qué elegir nuestra plataforma?</h2>
            <p class="landing-section-subtitle">
                Diseñada específicamente para empresas que buscan digitalizar 
                y optimizar su gestión de formación y calidad
            </p>
            
            <div class="landing-features-grid">
                <div class="landing-feature-card fade-in-up">
                    <div class="landing-feature-icon">📚</div>
                    <h3 class="landing-feature-title">Formación FUNDAE</h3>
                    <p class="landing-feature-desc">
                        Gestión completa de bonificaciones, documentos XML oficiales, 
                        seguimiento de participantes y diplomas automatizados.
                    </p>
                </div>
                
                <div class="landing-feature-card fade-in-up-delay-1">
                    <div class="landing-feature-icon">📋</div>
                    <h3 class="landing-feature-title">ISO 9001</h3>
                    <p class="landing-feature-desc">
                        Sistema de calidad integral con auditorías, no conformidades, 
                        acciones correctivas e indicadores en tiempo real.
                    </p>
                </div>
                
                <div class="landing-feature-card fade-in-up-delay-2">
                    <div class="landing-feature-icon">🛡️</div>
                    <h3 class="landing-feature-title">RGPD Compliance</h3>
                    <p class="landing-feature-desc">
                        Cumplimiento automático del RGPD con gestión de consentimientos, 
                        tratamientos y derechos de los interesados.
                    </p>
                </div>
                
                <div class="landing-feature-card fade-in-up">
                    <div class="landing-feature-icon">📈</div>
                    <h3 class="landing-feature-title">CRM Integrado</h3>
                    <p class="landing-feature-desc">
                        Gestión de clientes, oportunidades comerciales y seguimiento 
                        de tareas en una plataforma unificada.
                    </p>
                </div>
                
                <div class="landing-feature-card fade-in-up-delay-1">
                    <div class="landing-feature-icon">☁️</div>
                    <h3 class="landing-feature-title">100% SaaS</h3>
                    <p class="landing-feature-desc">
                        Sin instalación, actualizaciones automáticas, acceso desde 
                        cualquier dispositivo y backup en la nube.
                    </p>
                </div>
                
                <div class="landing-feature-card fade-in-up-delay-2">
                    <div class="landing-feature-icon">⚡</div>
                    <h3 class="landing-feature-title">Fácil de usar</h3>
                    <p class="landing-feature-desc">
                        Interface intuitiva, onboarding personalizado y soporte 
                        técnico especializado para tu sector.
                    </p>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Modules Section
    st.markdown("""
    <div class="landing-modules" id="modules">
        <div class="landing-container">
            <h2 class="landing-section-title">Módulos disponibles</h2>
            <p class="landing-section-subtitle">
                Cada módulo está diseñado para cubrir todas las necesidades 
                específicas de tu área empresarial
            </p>
            
            <div class="landing-modules-grid">
                <div class="landing-module-card">
                    <span class="landing-module-icon">📚</span>
                    <h4 class="landing-module-name">Formación</h4>
                    <p class="landing-module-desc">
                        Acciones formativas, grupos, participantes, 
                        tutores, documentos XML FUNDAE
                    </p>
                </div>
                
                <div class="landing-module-card">
                    <span class="landing-module-icon">📋</span>
                    <h4 class="landing-module-name">ISO 9001</h4>
                    <p class="landing-module-desc">
                        Auditorías, no conformidades, acciones correctivas,
                        indicadores de calidad
                    </p>
                </div>
                
                <div class="landing-module-card">
                    <span class="landing-module-icon">🛡️</span>
                    <h4 class="landing-module-name">RGPD</h4>
                    <p class="landing-module-desc">
                        Tratamientos, consentimientos, derechos,
                        evaluación de impacto
                    </p>
                </div>
                
                <div class="landing-module-card">
                    <span class="landing-module-icon">📈</span>
                    <h4 class="landing-module-name">CRM</h4>
                    <p class="landing-module-desc">
                        Clientes, oportunidades, tareas,
                        comunicaciones y estadísticas
                    </p>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Call to Action Final
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 3rem 2rem;
            border-radius: 20px;
            text-align: center;
            color: white;
            margin: 4rem 0;
        ">
            <h3 style="font-size: 2rem; margin-bottom: 1rem;">
                ¿Listo para transformar tu gestión empresarial?
            </h3>
            <p style="font-size: 1.1rem; margin-bottom: 2rem; opacity: 0.9;">
                Únete a las empresas que ya confían en nuestra plataforma
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚀 Comenzar ahora", key="final_cta", help="Acceder al sistema", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()

    # Footer
    st.markdown("""
    <div class="landing-footer">
        <div style="max-width: 1200px; margin: 0 auto; padding: 0 2rem;">
            <div class="landing-logo" style="justify-content: center; margin-bottom: 2rem;">
                <div class="landing-logo-icon">🚀</div>
                <span>Gestor de Formación</span>
            </div>
            <p style="opacity: 0.8; margin-bottom: 1rem;">
                Plataforma SaaS integral para la gestión empresarial moderna
            </p>
            <p style="opacity: 0.6; font-size: 0.9rem;">
                © 2025 Gestor de Formación · Powered by Streamlit + Supabase
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================
# Vista de login moderna (del código original pero simplificada)
# =========================
def login_view():
    """Pantalla de login con diseño startup moderno."""
    
    # CSS para el login (reutilizar del código original pero simplificado)
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
    }

    header[data-testid="stHeader"] {
        display: none;
    }

    .stAppViewContainer > .main .block-container {
        padding-top: 2rem;
    }

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

    .back-to-landing {
        text-align: center;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(255, 255, 255, 0.3);
    }

    .back-link {
        color: #4a5568;
        text-decoration: none;
        font-size: 0.9rem;
        transition: color 0.3s ease;
    }

    .back-link:hover {
        color: #667eea;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Botón para volver a la landing
    if st.button("← Volver al inicio", key="back_to_landing", help="Volver a la página principal"):
        st.session_state.show_login = False
        st.rerun()
    
    # Obtener configuración personalizable
    ajustes = get_ajustes_app(supabase_public, campos=[
        "mensaje_login", "nombre_app", "logo_url", "color_primario"
    ])
    
    mensaje_login = ajustes.get("mensaje_login", "Accede al gestor con tus credenciales")
    nombre_app = ajustes.get("nombre_app", "Gestor de Formación")
    
    # Container principal con logo y título
    st.markdown(f"""
    <div class="login-container">
        <div class="login-header">
            <div class="login-logo">🚀</div>
            <h1 class="login-title">{nombre_app}</h1>
            <p class="login-subtitle">{mensaje_login}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Formulario de login
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
    
    if submitted:
        if not email or not password:
            st.warning("⚠️ Por favor, introduce email y contraseña.")
        else:
            st.session_state.login_loading = True
            
            # Mostrar progreso
            progress_placeholder = st.empty()
            with progress_placeholder.container():
                st.info("🔄 Verificando credenciales...")
                progress_bar = st.progress(0)
                
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
                    st.session_state.show_login = False  # Ocultar login después de autenticarse
                    st.rerun()
                    
            except Exception as e:
                progress_placeholder.error(f"❌ Error al iniciar sesión: {e}")
                st.session_state.login_loading = False

# =========================
# Resto de funciones del código original (is_module_active, route, etc.)
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
            st.session_state.page = "mis_grupos"
            
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
    if st.session_state.show_login:
        login_view()
    else:
        landing_page()
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
