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

    html, body, [class*="css"] {font-family: 'Inter', sans-serif;}
    header[data-testid="stHeader"], footer {display: none;}

    /* Navbar */
    .navbar {
        display:flex;justify-content:space-between;align-items:center;
        padding:1rem 2rem;background:white;border-bottom:1px solid #eee;
        position:fixed;top:0;left:0;right:0;z-index:1000;
    }
    .navbar .logo {font-weight:700;font-size:1.2rem;display:flex;align-items:center;gap:.5rem;color:#333;}

    /* Hero */
    .hero {
        display:flex;align-items:center;justify-content:space-between;
        padding:8rem 2rem 6rem;background:linear-gradient(135deg,#667eea,#764ba2);
        color:white;flex-wrap:wrap;
    }
    .hero-text {flex:1;min-width:300px;padding:1rem;}
    .hero-text h1 {font-size:2.5rem;font-weight:700;margin-bottom:1rem;}
    .hero-text p {font-size:1.1rem;opacity:.9;margin-bottom:2rem;}
    .hero-img {flex:1;min-width:300px;text-align:center;}
    .hero-img img {max-width:100%;border-radius:12px;box-shadow:0 8px 25px rgba(0,0,0,.2);}

    /* Features */
    .section {padding:5rem 2rem;max-width:1100px;margin:auto;}
    .section h2 {text-align:center;font-size:2rem;margin-bottom:3rem;}
    .cards {display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:2rem;}
    .card {background:white;border-radius:12px;padding:2rem;text-align:center;box-shadow:0 4px 8px rgba(0,0,0,.05);}
    .card img {width:60px;margin-bottom:1rem;}

    /* CTA Final */
    .cta {
        background:linear-gradient(135deg,#667eea,#764ba2);
        padding:3rem 2rem;border-radius:20px;text-align:center;color:white;
        margin:4rem auto;max-width:900px;
    }
    .cta h3 {font-size:2rem;margin-bottom:1rem;}
    .cta p {font-size:1.1rem;margin-bottom:2rem;opacity:.9;}

    /* Footer */
    .footer {background:#1a202c;color:#ddd;text-align:center;padding:2rem;margin-top:4rem;}
    .footer img {width:40px;display:block;margin:0 auto 1rem;}
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
            <img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/hero_mockup.png" alt="Hero Gestor"/>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Botón de login en navbar
    with st.container():
        btn_placeholder = st.empty()
        if btn_placeholder.button("🔐 Acceder", key="landing_login", help="Acceder al sistema"):
            st.session_state.show_login = True
            st.rerun()

    # Features con iconos propios
    st.markdown("""
    <div class="section">
        <h2>Características principales</h2>
        <div class="cards">
            <div class="card"><img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/icon_fundae.svg"/><h4>Formación FUNDAE</h4></div>
            <div class="card"><img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/icon_iso.svg"/><h4>ISO 9001</h4></div>
            <div class="card"><img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/icon_rgpd.svg"/><h4>Cumplimiento RGPD</h4></div>
            <div class="card"><img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/icon_crm.svg"/><h4>CRM Integrado</h4></div>
        </div>
    </div>

    <!-- CTA Final -->
    <div class="cta">
        <h3>¿Listo para transformar tu gestión empresarial?</h3>
        <p>Únete a las empresas que ya confían en nuestra plataforma</p>
    </div>

    <!-- Footer -->
    <div class="footer">
        <img src="https://jjeiyuixhxtgsujgsiky.supabase.co/storage/v1/object/public/documentos/logo_footer.svg" alt="Logo footer"/>
        © 2025 Gestor de Formación · Powered by Streamlit
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    landing_page()
