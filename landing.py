import streamlit as st
from supabase import create_client
from utils import get_ajustes_app

st.cache_data.clear()
st.cache_resource.clear()

# =========================
# Configuración de la página
# =========================
st.set_page_config(
    page_title="Gestor de Formación - Plataforma SaaS ERP",
    layout="wide",
    initial_sidebar_state="collapsed",
    page_icon="🚀",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

def crear_estilos_seguros():
    """Crea los estilos CSS de forma segura sin exposición"""
    estilos = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        margin: 0; padding: 0;
    }
    header[data-testid="stHeader"], footer {
        display: none;
    }

    .navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 2rem;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid #e5e5e5;
        position: fixed;
        top: 0; left: 0; right: 0;
        z-index: 1000;
    }
    .navbar .logo {
        display: flex;
        align-items: center;
        font-weight: 600;
        font-size: 1.2rem;
        color: #1a202c;
        gap: 0.5rem;
    }

    .hero {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6rem 2rem 4rem;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        flex-wrap: wrap;
        min-height: 60vh;
    }
    .hero-text {
        flex: 1;
        min-width: 280px;
        padding: 1rem;
    }
    .hero-text h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
        line-height: 1.2;
    }
    .hero-text p {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-bottom: 2rem;
        line-height: 1.6;
    }
    .hero-img {
        flex: 1;
        min-width: 280px;
        text-align: center;
    }
    .hero-img img {
        max-width: 100%;
        border-radius: 12px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }

    .section {
        padding: 4rem 2rem;
        max-width: 1100px;
        margin: auto;
    }
    .section h2 {
        text-align: center;
        font-size: 1.9rem;
        margin-bottom: 2.5rem;
        color: #1a202c;
        font-weight: 600;
    }
    .features {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 2rem;
    }
    .feature {
        background: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
        border: 1px solid #f1f5f9;
        transition: transform 0.3s ease;
    }
    .feature:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }
    .feature-icon {
        width: 60px;
        height: 60px;
        margin: 0 auto 1rem;
        background: linear-gradient(135deg, #667eea20, #764ba220);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
    }
    .feature h4 {
        font-size: 1.1rem;
        margin: 0 0 0.75rem 0;
        color: #2d3748;
        font-weight: 600;
    }
    .feature p {
        color: #4a5568;
        font-size: 0.95rem;
        line-height: 1.5;
        margin: 0;
    }

    .cta-section {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 3rem 2rem;
        text-align: center;
        margin-top: 2rem;
    }
    .cta-section h3 {
        font-size: 1.8rem;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    .cta-section p {
        font-size: 1rem;
        opacity: 0.9;
        margin-bottom: 2rem;
        max-width: 500px;
        margin-left: auto;
        margin-right: auto;
    }

    .footer {
        background: #1a202c;
        color: #e2e8f0;
        text-align: center;
        padding: 2rem;
        margin: 0;
    }
    .footer-content {
        max-width: 800px;
        margin: 0 auto;
    }
    .footer h4 {
        color: white;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    .footer p {
        color: #a0aec0;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
    }

    @media (max-width: 768px) {
        .hero {
            padding: 5rem 1rem 3rem;
            text-align: center;
        }
        .hero-text h1 {
            font-size: 2rem;
        }
        .features {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """
    return estilos

def landing_page():
    """Landing page segura sin exposición de código"""
    
    # Aplicar estilos de forma controlada
    st.markdown(crear_estilos_seguros(), unsafe_allow_html=True)

    # Contenido HTML seguro - dividido en secciones pequeñas
    navbar_html = """
    <div class="navbar">
        <div class="logo">🚀 Gestor de Formación</div>
        <div id="login-placeholder"></div>
    </div>
    """
    st.markdown(navbar_html, unsafe_allow_html=True)

    # Hero section
    hero_html = """
    <div class="hero">
        <div class="hero-text">
            <h1>Gestiona la formación de tu empresa</h1>
            <p>Plataforma SaaS integral para FUNDAE, ISO 9001, RGPD y CRM. Digitaliza tu gestión empresarial de forma segura.</p>
        </div>
        <div class="hero-img">
            <img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/hero_mockup.png" 
                 alt="Dashboard del sistema" 
                 style="max-width:100%; height:auto;" />
        </div>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

    # Botón de login usando componente nativo de Streamlit
    col1, col2, col3 = st.columns([5, 1, 1])
    with col2:
        if st.button("Acceder", key="btn_login", type="primary", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()

    # Sección de características usando componentes nativos
    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.markdown("## Características principales")
    
    # Grid de características usando columnas nativas
    col1, col2, col3, col4 = st.columns(4)
    
    caracteristicas = [
        {
            "icono": "📚",
            "titulo": "Formación FUNDAE",
            "descripcion": "Gestión completa de bonificaciones y documentos XML oficiales"
        },
        {
            "icono": "📋", 
            "titulo": "ISO 9001",
            "descripcion": "Sistema de calidad con auditorías y no conformidades"
        },
        {
            "icono": "🛡️",
            "titulo": "RGPD",
            "descripcion": "Cumplimiento automático y gestión de consentimientos"
        },
        {
            "icono": "📈",
            "titulo": "CRM",
            "descripcion": "Gestión integral de clientes y oportunidades"
        }
    ]
    
    columnas = [col1, col2, col3, col4]
    
    for i, caracteristica in enumerate(caracteristicas):
        with columnas[i]:
            # Crear tarjeta usando HTML seguro mínimo
            tarjeta_html = f"""
            <div class="feature">
                <div class="feature-icon">{caracteristica['icono']}</div>
                <h4>{caracteristica['titulo']}</h4>
                <p>{caracteristica['descripcion']}</p>
            </div>
            """
            st.markdown(tarjeta_html, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Call to action usando componentes mixtos
    cta_html = """
    <div class="cta-section">
        <h3>¿Listo para transformar tu gestión?</h3>
        <p>Únete a las empresas que ya confían en nuestra plataforma</p>
    </div>
    """
    st.markdown(cta_html, unsafe_allow_html=True)
    
    # Botón CTA nativo
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("Comenzar ahora", key="btn_cta", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()

    # Footer seguro
    footer_html = """
    <div class="footer">
        <div class="footer-content">
            <h4>Gestor de Formación</h4>
            <p>Plataforma SaaS empresarial</p>
            <p>© 2025 Todos los derechos reservados</p>
        </div>
    </div>
    """
    st.markdown(footer_html, unsafe_allow_html=True)

# Función alternativa completamente nativa
def landing_page_nativa():
    """Landing completamente con componentes nativos de Streamlit"""
    
    # CSS mínimo solo para ocultar elementos
    st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none; }
    .stAppViewContainer > .main .block-container { padding-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)

    # Header con logo y botón
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("# 🚀 Gestor de Formación")
    with col2:
        if st.button("Acceder", key="nav_login", type="primary"):
            st.session_state.show_login = True
            st.rerun()

    # Hero section nativo
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("## Gestiona la formación de tu empresa")
        st.markdown("""
        **Plataforma SaaS integral** para FUNDAE, ISO 9001, RGPD y CRM. 
        Todo lo que necesitas para digitalizar tu gestión empresarial.
        """)
        
        if st.button("✨ Prueba gratuita", key="hero_cta", type="primary", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()
    
    with col2:
        st.image(
            "https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/hero_mockup.png",
            caption="Dashboard del sistema",
            use_column_width=True
        )

    # Características con métricas nativas
    st.markdown("---")
    st.markdown("## Características principales")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📚 Formación FUNDAE", "Completo", help="Gestión integral de bonificaciones")
    
    with col2:
        st.metric("📋 ISO 9001", "Certificado", help="Sistema de calidad completo")
    
    with col3:
        st.metric("🛡️ RGPD", "Compliance", help="Cumplimiento automático")
    
    with col4:
        st.metric("📈 CRM", "Integrado", help="Gestión de clientes")

    # Footer nativo
    st.markdown("---")
    st.markdown("**© 2025 Gestor de Formación** - Plataforma SaaS empresarial")

if __name__ == "__main__":
    # Usar la versión segura por defecto
    landing_page()
