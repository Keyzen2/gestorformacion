# components/tailadmin_dashboard.py

import streamlit as st

class TailAdminDashboard:
    """Componentes de dashboard ejecutivo estilo TailAdmin"""
    
    @staticmethod
    def metric_card_primary(titulo: str, valor: str, icono: str = "📊", 
                           cambio: str = None, cambio_positivo: bool = True):
        """Tarjeta de métrica principal con gradiente"""
        
        cambio_color = "#10B981" if cambio_positivo else "#EF4444"
        cambio_icon = "↑" if cambio_positivo else "↓"
        cambio_html = ""
        
        if cambio:
            cambio_html = f'''
            <div style="
                display: inline-flex;
                align-items: center;
                gap: 0.25rem;
                font-size: 0.875rem;
                color: {cambio_color};
                font-weight: 600;
                margin-top: 0.5rem;
            ">
                <span>{cambio_icon}</span>
                <span>{cambio}</span>
            </div>
            '''
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%);
            color: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3);
            transition: transform 0.2s ease;
        ">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <div style="font-size: 0.875rem; opacity: 0.9; margin-bottom: 0.5rem;">{titulo}</div>
                    <div style="font-size: 2rem; font-weight: 700;">{valor}</div>
                    {cambio_html}
                </div>
                <div style="font-size: 2.5rem; opacity: 0.8;">{icono}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def metric_card_secondary(titulo: str, valor: str, icono: str = "📈", color: str = "#10B981"):
        """Tarjeta de métrica secundaria con borde coloreado"""
        
        st.markdown(f"""
        <div style="
            background: white;
            border: 1px solid #E5E7EB;
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: 1.25rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        ">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div style="
                    font-size: 2rem;
                    width: 48px;
                    height: 48px;
                    background: {color}15;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                ">{icono}</div>
                <div>
                    <div style="font-size: 0.875rem; color: #6B7280;">{titulo}</div>
                    <div style="font-size: 1.5rem; font-weight: 700; color: #1F2937;">{valor}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def alert_card(tipo: str, titulo: str, mensaje: str, count: int = None):
        """Tarjeta de alerta estilizada"""
        
        configs = {
            "warning": {"color": "#F59E0B", "bg": "#FFFBEB", "icon": "⚠️"},
            "error": {"color": "#EF4444", "bg": "#FEF2F2", "icon": "❌"},
            "info": {"color": "#3B82F6", "bg": "#EFF6FF", "icon": "ℹ️"},
            "success": {"color": "#10B981", "bg": "#ECFDF5", "icon": "✅"}
        }
        
        config = configs.get(tipo, configs["info"])
        badge = f'<span style="background:{config["color"]};color:white;padding:0.25rem 0.5rem;border-radius:6px;font-size:0.75rem;font-weight:600;">{count}</span>' if count else ""
        
        st.markdown(f"""
        <div style="
            background: {config['bg']};
            border-left: 4px solid {config['color']};
            border-radius: 8px;
            padding: 1rem;
            margin: 0.5rem 0;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; gap: 0.75rem; align-items: center;">
                    <span style="font-size: 1.5rem;">{config['icon']}</span>
                    <div>
                        <div style="font-weight: 600; color: #1F2937;">{titulo}</div>
                        <div style="font-size: 0.875rem; color: #6B7280; margin-top: 0.25rem;">{mensaje}</div>
                    </div>
                </div>
                {badge}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def section_header(titulo: str, subtitulo: str = None, icono: str = "📊"):
        """Header de sección con estilo TailAdmin"""
        
        subtitulo_html = f'<p style="color: #6B7280; font-size: 0.875rem; margin-top: 0.5rem;">{subtitulo}</p>' if subtitulo else ''
        
        st.markdown(f"""
        <div style="
            border-bottom: 2px solid #E5E7EB;
            padding-bottom: 1rem;
            margin: 2rem 0 1.5rem 0;
        ">
            <h2 style="
                font-size: 1.5rem;
                font-weight: 700;
                color: #1F2937;
                margin: 0;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            ">
                <span>{icono}</span>
                <span>{titulo}</span>
            </h2>
            {subtitulo_html}
        </div>
        """, unsafe_allow_html=True)
