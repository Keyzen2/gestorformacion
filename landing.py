import streamlit as st
from supabase import create_client
from utils import get_ajustes_app

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

def landing_page():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        margin: 0; padding: 0;
    }
    header[data-testid="stHeader"], footer {
        display: none;
    }

    /* Navbar */
    .navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 2rem;
        background: #ffffff;
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

    /* Hero */
    .hero {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6rem 2rem 4rem;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        flex-wrap: wrap;
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
    }
    .hero-text p {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-bottom: 2rem;
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

    /* Características */
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
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 2rem;
        text-align: center;
    }
    .feature {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1rem;
    }
    .feature img {
        width: 64px;
        height: 64px;
    }
    .feature h4 {
        font-size: 1.05rem;
        margin: 0;
        color: #2d3748;
        font-weight: 500;
    }

    /* Footer */
    .footer {
        background: #1a202c;
        color: #e2e8f0;
        text-align: center;
        padding: 1.5rem 2rem;
        margin-top: 3rem;
        font-size: 0.9rem;
    }
    </style>

    <!-- Navbar -->
    <div class="navbar">
        <div class="logo">🚀 Gestor de Formación</div>
        <div id="login-btn"></div>
    </div>

    <!-- Hero -->
    <div class="hero">
        <div class="hero-text">
            <h1>Gestiona la formación de tu empresa</h1>
            <p>Plataforma SaaS integral para FUNDAE, ISO 9001, RGPD y CRM.</p>
        </div>
        <div class="hero-img">
            <img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/hero_mockup.png" alt="Hero ilustración"/>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Botón login real
    with st.container():
        btn = st.empty()
        if btn.button("Acceder", key="landing_login"):
            st.session_state.show_login = True
            st.rerun()

    # Características
    st.markdown("""
    <div class="section">
        <h2>Características principales</h2>
        <div class="features">
            <div class="feature">
                <img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/icon_fundae.png" alt="FUNDAE"/>
                <h4>Formación FUNDAE</h4>
            </div>
            <div class="feature">
                <img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/icon_iso.png" alt="ISO"/>
                <h4>ISO 9001</h4>
            </div>
            <div class="feature">
                <img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/icon_rgpd.png" alt="RGPD"/>
                <h4>Cumplimiento RGPD</h4>
            </div>
            <div class="feature">
                <img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/icon_crm.png" alt="CRM"/>
                <h4>CRM Integrado</h4>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <div class="footer">
        © 2025 Gestor de Formación
    </div>
    """, unsafe_allow_html=True)
