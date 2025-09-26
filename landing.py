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
    .navbar .btn-login {
        padding: 0.5rem 1rem;
        background: #667eea;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
    }

    .hero {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 4rem 2rem; /* reducido */
        margin-top: 60px;   /* compensa navbar fija */
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
        padding: 3rem 2rem; /* reducido */
        max-width: 1100px;
        margin: auto;
    }
    .section h2 {
        text-align: center;
        font-size: 1.9rem;
        margin-bottom: 2rem;
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
    
    # Aplicar estilos
    st.markdown(crear_estilos_seguros(), unsafe_allow_html=True)

    # Navbar con botón Acceder alineado a la derecha
    navbar_html = """
    <div class="navbar">
        <div class="logo">🚀 Gestor de Formación</div>
        <form action="#" method="post">
            <button class="btn-login">Acceder</button>
        </form>
    </div>
    """
    st.markdown(navbar_html, unsafe_allow_html=True)

    # Hero section
    hero_html = """
    <div class="hero">
        <div class="hero-text">
            <h1>Gestiona la formación de tu empresa</h1>
            <p>Plataforma SaaS integral para FUNDAE, ISO 9001, RGPD y CRM. 
            Digitaliza tu gestión empresarial de forma segura.</p>
        </div>
        <div class="hero-img">
            <img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/hero_mockup.png" 
                 alt="Dashboard del sistema" />
        </div>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

    # Sección de características
    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.markdown("## Características principales")
    
    col1, col2, col3, col4 = st.columns(4)
    
    caracteristicas = [
        {"icono": "📚","titulo": "Formación FUNDAE","descripcion": "Gestión completa de bonificaciones y documentos XML oficiales"},
        {"icono": "📋","titulo": "ISO 9001","descripcion": "Sistema de calidad con auditorías y no conformidades"},
        {"icono": "🛡️","titulo": "RGPD","descripcion": "Cumplimiento automático y gestión de consentimientos"},
        {"icono": "📈","titulo": "CRM","descripcion": "Gestión integral de clientes y oportunidades"}
    ]
    
    columnas = [col1, col2, col3, col4]
    
    for i, c in enumerate(caracteristicas):
        with columnas[i]:
            st.markdown(f"""
            <div class="feature">
                <div class="feature-icon">{c['icono']}</div>
                <h4>{c['titulo']}</h4>
                <p>{c['descripcion']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Footer
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

if __name__ == "__main__":
    landing_page()
