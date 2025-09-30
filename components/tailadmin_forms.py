import streamlit as st

class TailAdminForms:
    """Componentes de formularios estilo TailAdmin usando colores de app.py"""
    
    @staticmethod
    def form_container_start():
        """Inicia un contenedor de formulario"""
        st.markdown('<div class="tailadmin-form-container">', unsafe_allow_html=True)
    
    @staticmethod
    def form_container_end():
        """Cierra el contenedor de formulario"""
        st.markdown('</div>', unsafe_allow_html=True)
    
    @staticmethod
    def form_header(title: str, subtitle: str = None, icon: str = "📝"):
        """Header de sección con título e ícono"""
        subtitle_html = f'<p class="tailadmin-form-subtitle">{subtitle}</p>' if subtitle else ''
        
        st.markdown(f"""
        <div class="tailadmin-form-header">
            <h3 class="tailadmin-form-title">{icon} {title}</h3>
            {subtitle_html}
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def info_box(text: str, tipo: str = "info"):
        """Caja de información contextual"""
        iconos = {
            "info": "ℹ️",
            "warning": "⚠️",
            "success": "✅",
            "danger": "❌"
        }
        
        st.markdown(f"""
        <div class="tailadmin-info-box {tipo}">
            <strong>{iconos.get(tipo, "ℹ️")}</strong> {text}
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def section_divider():
        """Divisor visual entre secciones"""
        st.markdown('<div class="tailadmin-section-divider"></div>', unsafe_allow_html=True)
    
    @staticmethod
    def label(text: str, required: bool = False):
        """Label personalizado con asterisco opcional"""
        class_name = "tailadmin-label-required" if required else "tailadmin-label"
        st.markdown(f'<label class="{class_name}">{text}</label>', unsafe_allow_html=True)
