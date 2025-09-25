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
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Ocultar barra Streamlit */
    header[data-testid="stHeader"], footer {display: none;}

    .navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 2rem;
        background: white;
        border-bottom: 1px solid #eee;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 1000;
    }

    .navbar .logo {
        font-weight: 700;
        font-size: 1.2rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #333;
    }

    .hero {
        text-align: center;
        padding: 8rem 2rem 6rem;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
    }
    .hero h1 {
        font-size: 3rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    .hero p {
        font-size: 1.2rem;
        opacity: 0.9;
        margin-bottom: 2rem;
    }

    .section {
        padding: 5rem 2rem;
        max-width: 1100px;
        margin: auto;
    }
    .section h2 {
        text-align: center;
        font-size: 2rem;
        margin-bottom: 3rem;
    }
    .cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 2rem;
    }
    .card {
        background: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        text-align: center;
    }
    .card span {
        font-size: 2rem;
        display: block;
        margin-bottom: 1rem;
    }

    .footer {
        background: #1a202c;
        color: #ddd;
        text-align: center;
        padding: 2rem;
        margin-top: 4rem;
    }
    </style>

    <div class="navbar">
        <div class="logo">🚀 Gestor de Formación</div>
        <div id="login-btn"></div>
    </div>

    <div class="hero">
        <h1>Gestiona la formación de tu empresa</h1>
        <p>Plataforma SaaS integral para FUNDAE, ISO 9001, RGPD y CRM.</p>
    </div>
    """, unsafe_allow_html=True)

    # Renderiza botón de login dentro del header
    with st.container():
        btn_placeholder = st.empty()
        if btn_placeholder.button("🔐 Acceder", key="landing_login", help="Acceder al sistema"):
            st.session_state.show_login = True
            st.rerun()

    # Sección características
    st.markdown("""
    <div class="section">
        <h2>Características principales</h2>
        <div class="cards">
            <div class="card"><span>📚</span> Formación FUNDAE simplificada</div>
            <div class="card"><span>📋</span> ISO 9001 con indicadores en tiempo real</div>
            <div class="card"><span>🛡️</span> Cumplimiento RGPD automático</div>
            <div class="card"><span>📈</span> CRM integrado y oportunidades</div>
        </div>
    </div>

    <div class="footer">
        © 2025 Gestor de Formación · Powered by Streamlit + Supabase
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    landing_page()
