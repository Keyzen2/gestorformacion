import streamlit as st
from datetime import datetime
from utils import get_ajustes_app, update_ajustes_app
# ✅ NUEVO: Import para cache monitor (solo se usa si es admin)
try:
    from services.cache_service import render_cache_monitor
except ImportError:
    render_cache_monitor = None  # Fallback si no existe

def main(supabase, session_state):
    st.title("⚙️ Ajustes de la Aplicación")
    st.caption("Personaliza la apariencia y configuración de la aplicación.")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    # Cargar ajustes actuales
    ajustes_actuales = get_ajustes_app(supabase)

    # Crear tabs para organizar la configuración
    tab1, tab2, tab3, tab4 = st.tabs(["🎨 Apariencia", "📝 Mensajes", "🏢 Branding", "⚙️ Avanzado"])

    # ===============================
    # TAB 1: APARIENCIA
    # ===============================
    with tab1:
        st.markdown("### 🎨 Colores de la Aplicación")
        st.caption("Personaliza la paleta de colores del sistema.")

        col1, col2 = st.columns(2)
        
        with col1:
            color_primario = st.color_picker(
                "Color Primario", 
                value=ajustes_actuales.get("color_primario", "#4285F4"),
                help="Color principal usado en botones y elementos destacados"
            )
            
            color_exito = st.color_picker(
                "Color Éxito", 
                value=ajustes_actuales.get("color_exito", "#0F9D58"),
                help="Color usado para mensajes de éxito"
            )
            
            color_error = st.color_picker(
                "Color Error", 
                value=ajustes_actuales.get("color_error", "#F44336"),
                help="Color usado para mensajes de error"
            )

        with col2:
            color_secundario = st.color_picker(
                "Color Secundario", 
                value=ajustes_actuales.get("color_secundario", "#34A853"),
                help="Color secundario usado en elementos de soporte"
            )
            
            color_advertencia = st.color_picker(
                "Color Advertencia", 
                value=ajustes_actuales.get("color_advertencia", "#FF9800"),
                help="Color usado para mensajes de advertencia"
            )

        # Vista previa de colores
        st.markdown("#### 🔍 Vista Previa")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div style="background-color: {color_primario}; color: white; padding: 10px; 
                        border-radius: 5px; text-align: center; margin: 5px 0;">
                Primario
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="background-color: {color_secundario}; color: white; padding: 10px; 
                        border-radius: 5px; text-align: center; margin: 5px 0;">
                Secundario
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style="background-color: {color_exito}; color: white; padding: 10px; 
                        border-radius: 5px; text-align: center; margin: 5px 0;">
                Éxito
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div style="background-color: {color_advertencia}; color: white; padding: 10px; 
                        border-radius: 5px; text-align: center; margin: 5px 0;">
                Advertencia
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            st.markdown(f"""
            <div style="background-color: {color_error}; color: white; padding: 10px; 
                        border-radius: 5px; text-align: center; margin: 5px 0;">
                Error
            </div>
            """, unsafe_allow_html=True)

        # Opciones de tema
        st.markdown("### 🌙 Tema")
        tema_oscuro = st.checkbox(
            "Activar tema oscuro", 
            value=ajustes_actuales.get("tema_oscuro", False),
            help="Aplica un tema oscuro a la aplicación"
        )

    # ===============================
    # TAB 2: MENSAJES PERSONALIZADOS
    # ===============================
    with tab2:
        st.markdown("### 📝 Mensajes por Rol de Usuario")
        st.caption("Personaliza los mensajes que ven los usuarios según su rol.")

        mensaje_login = st.text_area(
            "Mensaje de Login",
            value=ajustes_actuales.get("mensaje_login", "Accede al gestor con tus credenciales."),
            help="Mensaje mostrado en la pantalla de login",
            height=100
        )

        col1, col2 = st.columns(2)
        
        with col1:
            mensaje_admin = st.text_area(
                "Mensaje para Administradores",
                value=ajustes_actuales.get("mensaje_admin", "Panel de administración completo."),
                help="Mensaje de bienvenida para administradores",
                height=80
            )
            
            mensaje_alumno = st.text_area(
                "Mensaje para Alumnos",
                value=ajustes_actuales.get("mensaje_alumno", "Accede a tus cursos y diplomas."),
                help="Mensaje de bienvenida para alumnos",
                height=80
            )

        with col2:
            mensaje_gestor = st.text_area(
                "Mensaje para Gestores",
                value=ajustes_actuales.get("mensaje_gestor", "Gestiona tu empresa de forma eficiente."),
                help="Mensaje de bienvenida para gestores",
                height=80
            )

        # Vista previa de mensajes
        st.markdown("#### 🔍 Vista Previa de Mensajes")
        
        with st.expander("👁️ Ver como aparecerán los mensajes"):
            st.info(f"**Login:** {mensaje_login}")
            st.success(f"**Admin:** {mensaje_admin}")
            st.info(f"**Gestor:** {mensaje_gestor}")
            st.warning(f"**Alumno:** {mensaje_alumno}")

    # ===============================
    # TAB 3: BRANDING
    # ===============================
    with tab3:
        st.markdown("### 🏢 Identidad Corporativa")
        st.caption("Configura logos, favicon y elementos de marca.")

        col1, col2 = st.columns(2)
        
        with col1:
            logo_url = st.text_input(
                "URL del Logo",
                value=ajustes_actuales.get("logo_url", ""),
                help="URL completa del logo de la empresa (opcional)"
            )
            
            if logo_url:
                try:
                    st.image(logo_url, width=200, caption="Vista previa del logo")
                except Exception:
                    st.warning("No se pudo cargar la imagen. Verifica la URL.")

        with col2:
            favicon_url = st.text_input(
                "URL del Favicon",
                value=ajustes_actuales.get("favicon_url", ""),
                help="URL del favicon (.ico o .png de 32x32px)"
            )
            
            if favicon_url:
                try:
                    st.image(favicon_url, width=32, caption="Vista previa del favicon")
                except Exception:
                    st.warning("No se pudo cargar el favicon. Verifica la URL.")

        # Información adicional
        st.markdown("#### ℹ️ Consejos para el Branding")
        st.markdown("""
        - **Logo**: Usa formato PNG o SVG para mejor calidad
        - **Tamaño recomendado**: 200-300px de ancho
        - **Favicon**: Formato ICO o PNG de 32x32 píxeles
        - **URLs**: Deben ser accesibles públicamente (no archivos locales)
        """)

    # ===============================
    # TAB 4: CONFIGURACIÓN AVANZADA
    # ===============================
    with tab4:
        st.markdown("### ⚙️ Configuración Avanzada")
        st.caption("Opciones técnicas y de sistema.")

        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Información del Sistema")
            mostrar_version = st.checkbox(
                "Mostrar versión de la app",
                value=ajustes_actuales.get("mostrar_version", True),
                help="Muestra información de versión en el pie de página"
            )
            
            debug_mode = st.checkbox(
                "Modo debugging",
                value=ajustes_actuales.get("debug_mode", False),
                help="Activa información adicional para desarrolladores"
            )

        with col2:
            st.markdown("#### 🔧 Funcionalidades")
            
            cache_duration = st.number_input(
                "Duración del cache (segundos)",
                min_value=60,
                max_value=3600,
                value=ajustes_actuales.get("cache_duration", 300),
                help="Tiempo que se mantienen los datos en cache"
            )

        # Información del sistema actual
        st.markdown("#### 📈 Estado del Sistema")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Cache activo", "✅" if st.cache_data else "❌")
        with col2:
            st.metric("Sesión actual", session_state.role.upper() if hasattr(session_state, 'role') else "N/A")
        with col3:
            st.metric("Última actualización", datetime.now().strftime("%H:%M:%S"))

        # Herramientas de administración
        st.markdown("#### 🛠️ Herramientas de Administración")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🗑️ Limpiar Cache", help="Limpia toda la cache de la aplicación"):
                st.cache_data.clear()
                st.success("Cache limpiada correctamente")
                st.rerun()

        with col2:
            # Exportar configuración
            if st.button("📥 Exportar Config", help="Descarga la configuración actual"):
                config_json = json.dumps(ajustes_actuales, indent=2, ensure_ascii=False)
                st.download_button(
                    label="💾 Descargar JSON",
                    data=config_json,
                    file_name=f"config_app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

        with col3:
            # Importar configuración
            uploaded_config = st.file_uploader(
                "📤 Importar Config",
                type=['json'],
                help="Sube un archivo de configuración"
            )
            
            if uploaded_config:
                try:
                    config_data = json.load(uploaded_config)
                    if st.button("✅ Aplicar Configuración"):
                        if update_ajustes_app(supabase, config_data):
                            st.success("Configuración importada correctamente")
                            st.rerun()
                        else:
                            st.error("Error al importar configuración")
                except Exception as e:
                    st.error(f"Error al leer archivo: {e}")

    # ===============================
    # GUARDAR CAMBIOS
    # ===============================
    st.divider()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("💾 Guardar Todos los Cambios", use_container_width=True, type="primary"):
            # Recopilar todos los ajustes
            nuevos_ajustes = {
                "color_primario": color_primario,
                "color_secundario": color_secundario,
                "color_exito": color_exito,
                "color_advertencia": color_advertencia,
                "color_error": color_error,
                "tema_oscuro": tema_oscuro,
                "mensaje_login": mensaje_login,
                "mensaje_admin": mensaje_admin,
                "mensaje_gestor": mensaje_gestor,
                "mensaje_alumno": mensaje_alumno,
                "logo_url": logo_url,
                "favicon_url": favicon_url,
                "mostrar_version": mostrar_version,
                "debug_mode": debug_mode,
                "cache_duration": cache_duration,
                "updated_at": datetime.now().isoformat()
            }
            
            # Guardar en base de datos
            if update_ajustes_app(supabase, nuevos_ajustes):
                st.success("✅ Configuración guardada correctamente")
                
                # Aplicar CSS personalizado inmediatamente
                apply_custom_css(nuevos_ajustes)
                
                # Recargar página para aplicar cambios
                st.rerun()
            else:
                st.error("❌ Error al guardar la configuración")
                
     # =========================
    # Monitor de Cache (Solo Admin) - NUEVO
    # =========================
    if session_state.role == "admin":
        from services.cache_service import render_cache_monitor
        
        st.divider()
        st.markdown("## 🔧 Herramientas de Administración")
        
        # ✅ Monitor de cache
        render_cache_monitor()
        
        # ✅ Información adicional del sistema
        with st.expander("ℹ️ Información del Sistema", expanded=False):
            import streamlit as st
            import sys
            import platform
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🐍 Python & Streamlit**")
                st.text(f"Python: {sys.version.split()[0]}")
                st.text(f"Streamlit: {st.__version__}")
                st.text(f"Platform: {platform.system()}")
            
            with col2:
                st.markdown("**📊 Estado de la Aplicación**")
                st.text(f"Páginas activas: {len([k for k in st.session_state.keys() if 'page' in k])}")
                st.text(f"Usuario conectado: {session_state.user.get('email', 'N/A')}")
                st.text(f"Rol actual: {session_state.role}")
        
        # ✅ Acciones administrativas rápidas
        with st.expander("⚡ Acciones Rápidas", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 Refrescar Cache Global"):
                    from services.cache_service import clear_all_cache
                    clear_all_cache()
                    st.success("✅ Cache global limpiado")
                    st.rerun()
            
            with col2:
                if st.button("🧹 Limpiar Session State"):
                    # Mantener datos críticos
                    critical_keys = ['role', 'user', 'auth_session']
                    keys_to_remove = [k for k in st.session_state.keys() if k not in critical_keys]
                    for key in keys_to_remove:
                        del st.session_state[key]
                    st.success(f"✅ Limpiadas {len(keys_to_remove)} variables de sesión")
                    st.rerun()
            
            with col3:
                if st.button("📊 Debug DataService"):
                    from services.data_service import get_data_service
                    data_service = get_data_service(supabase, session_state)
                    st.json({
                        "rol": data_service.rol,
                        "empresa_id": data_service.empresa_id,
                        "user_id": data_service.user_id,
                        "metodos_disponibles": [m for m in dir(data_service) if not m.startswith('_')][:10]
                    })
                    
    # ===============================
    # APLICAR CSS PERSONALIZADO
    # ===============================
    # Aplicar estilos actuales
    apply_custom_css(ajustes_actuales)

def apply_custom_css(ajustes):
    """Aplica CSS personalizado basado en los ajustes."""
    
    # Obtener colores
    color_primario = ajustes.get("color_primario", "#4285F4")
    color_secundario = ajustes.get("color_secundario", "#34A853")
    color_exito = ajustes.get("color_exito", "#0F9D58")
    color_advertencia = ajustes.get("color_advertencia", "#FF9800")
    color_error = ajustes.get("color_error", "#F44336")
    tema_oscuro = ajustes.get("tema_oscuro", False)
    
    # CSS personalizado
    css = f"""
    <style>
    /* Colores personalizados */
    :root {{
        --color-primario: {color_primario};
        --color-secundario: {color_secundario};
        --color-exito: {color_exito};
        --color-advertencia: {color_advertencia};
        --color-error: {color_error};
    }}
    
    /* Botones primarios */
    .stButton > button[kind="primary"] {{
        background-color: {color_primario} !important;
        border-color: {color_primario} !important;
    }}
    
    .stButton > button[kind="primary"]:hover {{
        background-color: {color_primario}dd !important;
        border-color: {color_primario}dd !important;
    }}
    
    /* Elementos de éxito */
    .stSuccess {{
        background-color: {color_exito}20 !important;
        border-left-color: {color_exito} !important;
    }}
    
    /* Elementos de error */
    .stError {{
        background-color: {color_error}20 !important;
        border-left-color: {color_error} !important;
    }}
    
    /* Elementos de advertencia */
    .stWarning {{
        background-color: {color_advertencia}20 !important;
        border-left-color: {color_advertencia} !important;
    }}
    
    /* Sidebar personalizada */
    .css-1d391kg {{
        background-color: {color_primario}10;
    }}
    
    /* Links y elementos interactivos */
    a {{
        color: {color_primario} !important;
    }}
    
    /* Métricas */
    .metric-container {{
        background: linear-gradient(135deg, {color_primario}10, {color_secundario}10);
        border-radius: 10px;
        padding: 1rem;
        border-left: 4px solid {color_primario};
    }}
    
    /* Tema oscuro */
    {get_dark_theme_css() if tema_oscuro else ""}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)

def get_dark_theme_css():
    """Retorna CSS para tema oscuro."""
    return """
    /* Tema oscuro */
    .stApp {{
        background-color: #1e1e1e !important;
        color: #ffffff !important;
    }}
    
    .stSidebar {{
        background-color: #2d2d2d !important;
    }}
    
    .stSelectbox > div > div {{
        background-color: #3d3d3d !important;
        color: #ffffff !important;
    }}
    
    .stTextInput > div > div > input {{
        background-color: #3d3d3d !important;
        color: #ffffff !important;
    }}
    """
