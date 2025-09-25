import streamlit as st
from supabase import create_client
from utils import get_ajustes_app

# =========================
# Configuración de la página
# =========================
st.set_page_config(
    page_title="Gestor de Formación - Plataforma SaaS",
    layout="wide",
    initial_sidebar_state="collapsed",
    page_icon="🚀",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

def landing_page():
    """Landing page comercial inspirada en Google Classroom"""
    
    # CSS moderno para landing startup
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
    
    /* Navegación superior */
    .navbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        padding: 1rem 0;
        z-index: 1000;
    }
    
    .navbar-container {
        max-width: 1200px;
        margin: 0 auto;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 2rem;
    }
    
    .logo {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a202c;
        text-decoration: none;
    }
    
    .logo-icon {
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
    
    .nav-links {
        display: flex;
        gap: 2rem;
        align-items: center;
    }
    
    .nav-link {
        color: #4a5568;
        text-decoration: none;
        font-weight: 500;
        transition: color 0.3s ease;
    }
    
    .nav-link:hover {
        color: #667eea;
    }
    
    .login-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        transition: all 0.3s ease;
        border: none;
        cursor: pointer;
    }
    
    .login-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
        color: white;
    }
    
    /* Hero section */
    .hero {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 8rem 0 6rem;
        margin-top: 80px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    
    .hero::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M30 30c0-11.046-8.954-20-20-20s-20 8.954-20 20 8.954 20 20 20 20-8.954 20-20zm0 0c0-11.046 8.954-20 20-20s20 8.954 20 20-8.954 20-20 20-20-8.954-20-20z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
        opacity: 0.5;
    }
    
    .hero-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 2rem;
        position: relative;
        z-index: 1;
    }
    
    .hero-title {
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 1.5rem;
        line-height: 1.1;
    }
    
    .hero-subtitle {
        font-size: 1.25rem;
        font-weight: 400;
        margin-bottom: 3rem;
        opacity: 0.9;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    
    .hero-cta {
        display: flex;
        gap: 1rem;
        justify-content: center;
        flex-wrap: wrap;
    }
    
    .cta-primary {
        background: white;
        color: #667eea;
        padding: 1rem 2rem;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        font-size: 1.1rem;
        transition: all 0.3s ease;
        border: none;
        cursor: pointer;
    }
    
    .cta-primary:hover {
        transform: translateY(-2px);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.15);
        color: #667eea;
    }
    
    .cta-secondary {
        background: transparent;
        color: white;
        padding: 1rem 2rem;
        border: 2px solid rgba(255, 255, 255, 0.3);
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        font-size: 1.1rem;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .cta-secondary:hover {
        background: rgba(255, 255, 255, 0.1);
        border-color: white;
        color: white;
    }
    
    /* Features section */
    .features {
        padding: 6rem 0;
        background: #f8fafc;
    }
    
    .container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 2rem;
    }
    
    .section-title {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a202c;
        margin-bottom: 1rem;
    }
    
    .section-subtitle {
        text-align: center;
        font-size: 1.1rem;
        color: #4a5568;
        margin-bottom: 4rem;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    
    .features-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 2rem;
        margin-bottom: 4rem;
    }
    
    .feature-card {
        background: white;
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
        border: 1px solid rgba(0, 0, 0, 0.05);
    }
    
    .feature-card:hover {
        transform: translateY(-8px);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
    }
    
    .feature-icon {
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
    
    .feature-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #1a202c;
        margin-bottom: 0.75rem;
    }
    
    .feature-desc {
        color: #4a5568;
        line-height: 1.6;
    }
    
    /* Modules showcase */
    .modules {
        padding: 6rem 0;
        background: white;
    }
    
    .modules-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.5rem;
        margin-top: 3rem;
    }
    
    .module-card {
        background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        transition: all 0.3s ease;
        border: 2px solid transparent;
    }
    
    .module-card:hover {
        border-color: #667eea;
        transform: translateY(-4px);
    }
    
    .module-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        display: block;
    }
    
    .module-name {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a202c;
        margin-bottom: 0.5rem;
    }
    
    .module-desc {
        color: #4a5568;
        font-size: 0.9rem;
    }
    
    /* Footer */
    .footer {
        background: #1a202c;
        color: white;
        padding: 3rem 0 2rem;
        text-align: center;
    }
    
    .footer-content {
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 2rem;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .hero-title {
            font-size: 2.5rem;
        }
        
        .hero-cta {
            flex-direction: column;
            align-items: center;
        }
        
        .nav-links {
            display: none;
        }
        
        .features-grid {
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

    # Navbar
    st.markdown("""
    <div class="navbar">
        <div class="navbar-container">
            <div class="logo">
                <div class="logo-icon">🚀</div>
                <span>Gestor de Formación</span>
            </div>
            <div class="nav-links">
                <a href="#features" class="nav-link">Características</a>
                <a href="#modules" class="nav-link">Módulos</a>
                <a href="#pricing" class="nav-link">Precios</a>
                <a href="#contact" class="nav-link">Contacto</a>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Botón de login en la esquina superior derecha
    col1, col2 = st.columns([8, 1])
    with col2:
        if st.button("🔐 Acceder", key="header_login", help="Acceder al sistema"):
            st.session_state.show_login = True
            st.rerun()

    # Hero Section
    st.markdown("""
    <div class="hero">
        <div class="hero-container">
            <h1 class="hero-title fade-in-up">
                Gestiona la formación de tu empresa como nunca antes
            </h1>
            <p class="hero-subtitle fade-in-up-delay-1">
                Plataforma integral SaaS para formación FUNDAE, ISO 9001, RGPD y CRM. 
                Todo lo que necesitas para digitalizar tu gestión empresarial.
            </p>
            <div class="hero-cta fade-in-up-delay-2">
                <button class="cta-primary" onclick="document.querySelector('#features').scrollIntoView({behavior: 'smooth'})">
                    ✨ Prueba gratuita
                </button>
                <button class="cta-secondary" onclick="document.querySelector('#modules').scrollIntoView({behavior: 'smooth'})">
                    📋 Ver módulos
                </button>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Features Section
    st.markdown("""
    <div class="features" id="features">
        <div class="container">
            <h2 class="section-title">¿Por qué elegir nuestra plataforma?</h2>
            <p class="section-subtitle">
                Diseñada específicamente para empresas que buscan digitalizar 
                y optimizar su gestión de formación y calidad
            </p>
            
            <div class="features-grid">
                <div class="feature-card fade-in-up">
                    <div class="feature-icon">📚</div>
                    <h3 class="feature-title">Formación FUNDAE</h3>
                    <p class="feature-desc">
                        Gestión completa de bonificaciones, documentos XML oficiales, 
                        seguimiento de participantes y diplomas automatizados.
                    </p>
                </div>
                
                <div class="feature-card fade-in-up-delay-1">
                    <div class="feature-icon">📋</div>
                    <h3 class="feature-title">ISO 9001</h3>
                    <p class="feature-desc">
                        Sistema de calidad integral con auditorías, no conformidades, 
                        acciones correctivas e indicadores en tiempo real.
                    </p>
                </div>
                
                <div class="feature-card fade-in-up-delay-2">
                    <div class="feature-icon">🛡️</div>
                    <h3 class="feature-title">RGPD Compliance</h3>
                    <p class="feature-desc">
                        Cumplimiento automático del RGPD con gestión de consentimientos, 
                        tratamientos y derechos de los interesados.
                    </p>
                </div>
                
                <div class="feature-card fade-in-up">
                    <div class="feature-icon">📈</div>
                    <h3 class="feature-title">CRM Integrado</h3>
                    <p class="feature-desc">
                        Gestión de clientes, oportunidades comerciales y seguimiento 
                        de tareas en una plataforma unificada.
                    </p>
                </div>
                
                <div class="feature-card fade-in-up-delay-1">
                    <div class="feature-icon">☁️</div>
                    <h3 class="feature-title">100% SaaS</h3>
                    <p class="feature-desc">
                        Sin instalación, actualizaciones automáticas, acceso desde 
                        cualquier dispositivo y backup en la nube.
                    </p>
                </div>
                
                <div class="feature-card fade-in-up-delay-2">
                    <div class="feature-icon">⚡</div>
                    <h3 class="feature-title">Fácil de usar</h3>
                    <p class="feature-desc">
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
    <div class="modules" id="modules">
        <div class="container">
            <h2 class="section-title">Módulos disponibles</h2>
            <p class="section-subtitle">
                Cada módulo está diseñado para cubrir todas las necesidades 
                específicas de tu área empresarial
            </p>
            
            <div class="modules-grid">
                <div class="module-card">
                    <span class="module-icon">📚</span>
                    <h4 class="module-name">Formación</h4>
                    <p class="module-desc">
                        Acciones formativas, grupos, participantes, 
                        tutores, documentos XML FUNDAE
                    </p>
                </div>
                
                <div class="module-card">
                    <span class="module-icon">📋</span>
                    <h4 class="module-name">ISO 9001</h4>
                    <p class="module-desc">
                        Auditorías, no conformidades, acciones correctivas,
                        indicadores de calidad
                    </p>
                </div>
                
                <div class="module-card">
                    <span class="module-icon">🛡️</span>
                    <h4 class="module-name">RGPD</h4>
                    <p class="module-desc">
                        Tratamientos, consentimientos, derechos,
                        evaluación de impacto
                    </p>
                </div>
                
                <div class="module-card">
                    <span class="module-icon">📈</span>
                    <h4 class="module-name">CRM</h4>
                    <p class="module-desc">
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
    <div class="footer">
        <div class="footer-content">
            <div class="logo" style="justify-content: center; margin-bottom: 2rem;">
                <div class="logo-icon">🚀</div>
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

if __name__ == "__main__":
    landing_page()
