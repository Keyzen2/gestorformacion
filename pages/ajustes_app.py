import streamlit as st
from datetime import datetime
# ✅ IMPORTACIONES CORREGIDAS - Sin cached_get_ajustes_app
from utils import get_ajustes_app, update_ajustes_app
from services.data_service import get_data_service

def main(supabase, session_state):
    st.title("⚙️ Ajustes de la Aplicación")
    st.caption("Configura los textos, apariencia y comportamiento global de la plataforma.")

    if session_state.role != "admin":
        st.warning("🔒 Solo el administrador global puede acceder a esta sección.")
        return

    # ✅ CARGAR AJUSTES CON FUNCIÓN CORREGIDA
    try:
        ajustes = get_ajustes_app(supabase)
        if not ajustes:
            ajustes = {}
    except Exception as e:
        st.error(f"⚠️ Error al cargar ajustes: {e}")
        ajustes = {}

    # =========================
    # CSS para preview en tiempo real
    # =========================
    st.markdown("""
    <style>
    .preview-card {
        border: 2px solid #e1e5e9;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .color-preview {
        width: 40px;
        height: 20px;
        border-radius: 4px;
        display: inline-block;
        margin-left: 10px;
        border: 1px solid #ccc;
    }
    
    .branding-preview {
        text-align: center;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # Tabs para organizar mejor
    # =========================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎨 Branding", 
        "📝 Textos Generales", 
        "🏷️ Textos por Rol",
        "🔄 Vista Previa"
    ])

    # =========================
    # TAB 1: BRANDING Y APARIENCIA
    # =========================
    with tab1:
        st.subheader("🎨 Branding y Apariencia")
        
        with st.form("branding_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📱 Identidad de marca")
                nombre_app = st.text_input(
                    "Nombre visible de la app", 
                    value=ajustes.get("nombre_app", "Gestor de Formación"),
                    help="Nombre que aparece en el título y en todo el sistema"
                )
                
                logo_url = st.text_input(
                    "URL del logo", 
                    value=ajustes.get("logo_url", ""),
                    help="URL completa del logo (ej: https://ejemplo.com/logo.png)"
                )
                
                favicon_url = st.text_input(
                    "URL del favicon", 
                    value=ajustes.get("favicon_url", ""),
                    help="Icono que aparece en la pestaña del navegador"
                )

            with col2:
                st.markdown("#### 🎨 Colores del sistema")
                color_primario = st.color_picker(
                    "Color primario", 
                    value=ajustes.get("color_primario", "#4285F4"),
                    help="Color principal de la interfaz"
                )
                st.markdown(f'<div class="color-preview" style="background-color: {color_primario};"></div>', unsafe_allow_html=True)
                
                color_secundario = st.color_picker(
                    "Color secundario", 
                    value=ajustes.get("color_secundario", "#5f6368"),
                    help="Color para elementos secundarios"
                )
                st.markdown(f'<div class="color-preview" style="background-color: {color_secundario};"></div>', unsafe_allow_html=True)
                
                color_exito = st.color_picker(
                    "Color de éxito", 
                    value=ajustes.get("color_exito", "#10b981"),
                    help="Color para mensajes de éxito"
                )
                
                color_advertencia = st.color_picker(
                    "Color de advertencia", 
                    value=ajustes.get("color_advertencia", "#f59e0b"),
                    help="Color para advertencias"
                )
                
                color_error = st.color_picker(
                    "Color de error", 
                    value=ajustes.get("color_error", "#ef4444"),
                    help="Color para mensajes de error"
                )

            st.markdown("#### 🌐 Configuración adicional")
            tema_oscuro = st.checkbox(
                "Habilitar tema oscuro por defecto", 
                value=ajustes.get("tema_oscuro", False),
                help="Los usuarios pueden cambiar entre temas claro/oscuro"
            )
            
            mostrar_logo_sidebar = st.checkbox(
                "Mostrar logo en barra lateral", 
                value=ajustes.get("mostrar_logo_sidebar", True),
                help="Mostrar el logo en la barra lateral de navegación"
            )

            guardar_branding = st.form_submit_button("💾 Guardar configuración de marca", use_container_width=True)
            
            if guardar_branding:
                try:
                    branding_data = {
                        "nombre_app": nombre_app,
                        "logo_url": logo_url,
                        "favicon_url": favicon_url,
                        "color_primario": color_primario,
                        "color_secundario": color_secundario,
                        "color_exito": color_exito,
                        "color_advertencia": color_advertencia,
                        "color_error": color_error,
                        "tema_oscuro": tema_oscuro,
                        "mostrar_logo_sidebar": mostrar_logo_sidebar
                    }
                    update_ajustes_app(supabase, branding_data)
                    st.success("✅ Configuración de marca actualizada correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar: {e}")

    # =========================
    # TAB 2: TEXTOS GENERALES
    # =========================
    with tab2:
        st.subheader("📝 Textos Generales del Sistema")
        
        with st.form("textos_generales"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🔐 Pantalla de login")
                mensaje_login = st.text_area(
                    "Mensaje de bienvenida", 
                    value=ajustes.get("mensaje_login", "Accede al gestor con tus credenciales."),
                    height=100,
                    help="Mensaje que aparece en la pantalla de inicio de sesión"
                )
                
                instrucciones_login = st.text_area(
                    "Instrucciones adicionales", 
                    value=ajustes.get("instrucciones_login", ""),
                    height=80,
                    help="Instrucciones extra para el login (opcional)"
                )

            with col2:
                st.markdown("#### 📄 Pie de página y legal")
                mensaje_footer = st.text_area(
                    "Texto del pie de página", 
                    value=ajustes.get("mensaje_footer", "© 2025 Gestor de Formación · Streamlit + Supabase"),
                    height=100,
                    help="Texto que aparece en el pie de todas las páginas"
                )
                
                aviso_legal = st.text_area(
                    "Aviso legal/privacidad", 
                    value=ajustes.get("aviso_legal", ""),
                    height=80,
                    help="Enlace o texto legal (opcional)"
                )

            st.markdown("#### 📧 Configuración de notificaciones")
            email_soporte = st.text_input(
                "Email de soporte", 
                value=ajustes.get("email_soporte", ""),
                help="Email para contacto de soporte técnico"
            )
            
            telefono_soporte = st.text_input(
                "Teléfono de soporte", 
                value=ajustes.get("telefono_soporte", ""),
                help="Teléfono para soporte (opcional)"
            )

            guardar_generales = st.form_submit_button("💾 Guardar textos generales", use_container_width=True)
            
            if guardar_generales:
                try:
                    generales_data = {
                        "mensaje_login": mensaje_login,
                        "instrucciones_login": instrucciones_login,
                        "mensaje_footer": mensaje_footer,
                        "aviso_legal": aviso_legal,
                        "email_soporte": email_soporte,
                        "telefono_soporte": telefono_soporte
                    }
                    update_ajustes_app(supabase, generales_data)
                    st.success("✅ Textos generales actualizados.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar: {e}")

    # =========================
    # TAB 3: TEXTOS POR ROL
    # =========================
    with tab3:
        st.subheader("🏷️ Personalización por Rol de Usuario")
        
        # Sub-tabs para cada rol
        subtab1, subtab2, subtab3, subtab4 = st.tabs([
            "👑 Admin", "🏢 Gestor", "🎓 Alumno", "📊 Comercial"
        ])
        
        with subtab1:
            with st.form("textos_admin"):
                st.markdown("#### 👑 Textos para Administradores")
                
                bienvenida_admin = st.text_area(
                    "Mensaje de bienvenida", 
                    value=ajustes.get("bienvenida_admin", "Panel de Administración SaaS"),
                    help="Título que ve el admin en la página principal"
                )
                
                tarjeta_admin_usuarios = st.text_area(
                    "Descripción - Gestión de Usuarios", 
                    value=ajustes.get("tarjeta_admin_usuarios", "Alta, gestión y permisos de usuarios."),
                    help="Texto explicativo del módulo de usuarios"
                )
                
                tarjeta_admin_empresas = st.text_area(
                    "Descripción - Gestión de Empresas", 
                    value=ajustes.get("tarjeta_admin_empresas", "Gestión de empresas y sus módulos."),
                    help="Texto explicativo del módulo de empresas"
                )
                
                tarjeta_admin_ajustes = st.text_area(
                    "Descripción - Ajustes Globales", 
                    value=ajustes.get("tarjeta_admin_ajustes", "Configuración global de la aplicación."),
                    help="Texto explicativo de los ajustes del sistema"
                )

                guardar_admin = st.form_submit_button("💾 Guardar textos de Admin")
                if guardar_admin:
                    try:
                        admin_data = {
                            "bienvenida_admin": bienvenida_admin,
                            "tarjeta_admin_usuarios": tarjeta_admin_usuarios,
                            "tarjeta_admin_empresas": tarjeta_admin_empresas,
                            "tarjeta_admin_ajustes": tarjeta_admin_ajustes
                        }
                        update_ajustes_app(supabase, admin_data)
                        st.success("✅ Textos de Admin actualizados.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar: {e}")

        with subtab2:
            with st.form("textos_gestor"):
                st.markdown("#### 🏢 Textos para Gestores")
                
                bienvenida_gestor = st.text_area(
                    "Mensaje de bienvenida", 
                    value=ajustes.get("bienvenida_gestor", "Panel del Gestor"),
                    help="Título que ve el gestor en la página principal"
                )
                
                tarjeta_gestor_grupos = st.text_area(
                    "Descripción - Gestión de Grupos", 
                    value=ajustes.get("tarjeta_gestor_grupos", "Crea y gestiona grupos de alumnos."),
                    help="Texto explicativo del módulo de grupos"
                )
                
                tarjeta_gestor_documentos = st.text_area(
                    "Descripción - Documentación Básica", 
                    value=ajustes.get("tarjeta_gestor_documentos", "Sube y organiza la documentación de formación."),
                    help="Texto explicativo del módulo de documentos"
                )
                
                tarjeta_gestor_docu_avanzada = st.text_area(
                    "Descripción - Documentación Avanzada", 
                    value=ajustes.get("tarjeta_gestor_docu_avanzada", "Repositorio documental transversal por empresa, grupo o usuario."),
                    help="Texto explicativo del módulo avanzado de documentos"
                )

                guardar_gestor = st.form_submit_button("💾 Guardar textos de Gestor")
                if guardar_gestor:
                    try:
                        gestor_data = {
                            "bienvenida_gestor": bienvenida_gestor,
                            "tarjeta_gestor_grupos": tarjeta_gestor_grupos,
                            "tarjeta_gestor_documentos": tarjeta_gestor_documentos,
                            "tarjeta_gestor_docu_avanzada": tarjeta_gestor_docu_avanzada
                        }
                        update_ajustes_app(supabase, gestor_data)
                        st.success("✅ Textos de Gestor actualizados.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar: {e}")

        with subtab3:
            with st.form("textos_alumno"):
                st.markdown("#### 🎓 Textos para Alumnos")
                
                bienvenida_alumno = st.text_area(
                    "Mensaje de bienvenida", 
                    value=ajustes.get("bienvenida_alumno", "Área del Alumno"),
                    help="Título que ve el alumno en la página principal"
                )
                
                tarjeta_alumno_grupos = st.text_area(
                    "Descripción - Mis Grupos", 
                    value=ajustes.get("tarjeta_alumno_grupos", "Consulta a qué grupos perteneces."),
                    help="Texto explicativo de la consulta de grupos"
                )
                
                tarjeta_alumno_diplomas = st.text_area(
                    "Descripción - Mis Diplomas", 
                    value=ajustes.get("tarjeta_alumno_diplomas", "Descarga tus diplomas disponibles."),
                    help="Texto explicativo de la descarga de diplomas"
                )
                
                tarjeta_alumno_seguimiento = st.text_area(
                    "Descripción - Mi Seguimiento", 
                    value=ajustes.get("tarjeta_alumno_seguimiento", "Accede al progreso de tu formación."),
                    help="Texto explicativo del seguimiento formativo"
                )

                guardar_alumno = st.form_submit_button("💾 Guardar textos de Alumno")
                if guardar_alumno:
                    try:
                        alumno_data = {
                            "bienvenida_alumno": bienvenida_alumno,
                            "tarjeta_alumno_grupos": tarjeta_alumno_grupos,
                            "tarjeta_alumno_diplomas": tarjeta_alumno_diplomas,
                            "tarjeta_alumno_seguimiento": tarjeta_alumno_seguimiento
                        }
                        update_ajustes_app(supabase, alumno_data)
                        st.success("✅ Textos de Alumno actualizados.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar: {e}")

        with subtab4:
            with st.form("textos_comercial"):
                st.markdown("#### 📊 Textos para Comerciales")
                
                bienvenida_comercial = st.text_area(
                    "Mensaje de bienvenida", 
                    value=ajustes.get("bienvenida_comercial", "Área Comercial - CRM"),
                    help="Título que ve el comercial en la página principal"
                )
                
                tarjeta_comercial_clientes = st.text_area(
                    "Descripción - Gestión de Clientes", 
                    value=ajustes.get("tarjeta_comercial_clientes", "Consulta y gestiona tu cartera de clientes."),
                    help="Texto explicativo del módulo de clientes"
                )
                
                tarjeta_comercial_oportunidades = st.text_area(
                    "Descripción - Oportunidades de Venta", 
                    value=ajustes.get("tarjeta_comercial_oportunidades", "Registra y da seguimiento a nuevas oportunidades."),
                    help="Texto explicativo del módulo de oportunidades"
                )
                
                tarjeta_comercial_tareas = st.text_area(
                    "Descripción - Gestión de Tareas", 
                    value=ajustes.get("tarjeta_comercial_tareas", "Organiza tus visitas y recordatorios."),
                    help="Texto explicativo del módulo de tareas comerciales"
                )

                guardar_comercial = st.form_submit_button("💾 Guardar textos de Comercial")
                if guardar_comercial:
                    try:
                        comercial_data = {
                            "bienvenida_comercial": bienvenida_comercial,
                            "tarjeta_comercial_clientes": tarjeta_comercial_clientes,
                            "tarjeta_comercial_oportunidades": tarjeta_comercial_oportunidades,
                            "tarjeta_comercial_tareas": tarjeta_comercial_tareas
                        }
                        update_ajustes_app(supabase, comercial_data)
                        st.success("✅ Textos de Comercial actualizados.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar: {e}")

    # =========================
    # TAB 4: VISTA PREVIA
    # =========================
    with tab4:
        st.subheader("🔄 Vista Previa de Cambios")
        st.caption("Visualiza cómo se verán los cambios antes de aplicarlos")
        
        # Obtener valores actuales (incluye cambios no guardados del formulario)
        preview_ajustes = ajustes.copy()
        
        st.markdown("#### 🎨 Apariencia actual")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            <div class="branding-preview" style="
                background: linear-gradient(135deg, {preview_ajustes.get('color_primario', '#4285F4')} 0%, 
                {preview_ajustes.get('color_secundario', '#5f6368')} 100%);
                color: white;
            ">
                <h2>{preview_ajustes.get('nombre_app', 'Gestor de Formación')}</h2>
                <p>Vista previa del header</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("**Colores configurados:**")
            colors = {
                "Primario": preview_ajustes.get('color_primario', '#4285F4'),
                "Secundario": preview_ajustes.get('color_secundario', '#5f6368'),
                "Éxito": preview_ajustes.get('color_exito', '#10b981'),
                "Advertencia": preview_ajustes.get('color_advertencia', '#f59e0b'),
                "Error": preview_ajustes.get('color_error', '#ef4444')
            }
            
            for nombre, color in colors.items():
                st.markdown(f"""
                <div style="display: flex; align-items: center; margin: 5px 0;">
                    <div style="width: 20px; height: 20px; background-color: {color}; 
                               border-radius: 3px; margin-right: 10px; border: 1px solid #ccc;"></div>
                    <span><strong>{nombre}:</strong> {color}</span>
                </div>
                """, unsafe_allow_html=True)

        st.divider()
        
        st.markdown("#### 📝 Textos por rol")
        preview_roles = {
            "👑 Admin": preview_ajustes.get('bienvenida_admin', 'Panel de Administración SaaS'),
            "🏢 Gestor": preview_ajustes.get('bienvenida_gestor', 'Panel del Gestor'),
            "🎓 Alumno": preview_ajustes.get('bienvenida_alumno', 'Área del Alumno'),
            "📊 Comercial": preview_ajustes.get('bienvenida_comercial', 'Área Comercial - CRM')
        }
        
        cols = st.columns(4)
        for i, (rol, texto) in enumerate(preview_roles.items()):
            with cols[i]:
                st.markdown(f"""
                <div class="preview-card">
                    <h4>{rol}</h4>
                    <p style="font-size: 0.9em; color: #666;">{texto}</p>
                </div>
                """, unsafe_allow_html=True)

        st.divider()
        
        st.markdown("#### 📱 Configuración de login y footer")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Pantalla de login:**")
            st.info(preview_ajustes.get('mensaje_login', 'Accede al gestor con tus credenciales.'))
            if preview_ajustes.get('instrucciones_login'):
                st.caption(preview_ajustes.get('instrucciones_login'))
        
        with col2:
            st.markdown("**Pie de página:**")
            st.caption(preview_ajustes.get('mensaje_footer', '© 2025 Gestor de Formación · Streamlit + Supabase'))

    # =========================
    # Acciones masivas
    # =========================
    st.divider()
    st.markdown("### 🔧 Acciones Avanzadas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Recargar ajustes", help="Recarga la configuración desde la base de datos"):
            try:
                # Forzar recarga de ajustes
                st.success("✅ Ajustes recargados correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al recargar: {e}")
    
    with col2:
        if st.button("📋 Exportar configuración", help="Descarga la configuración actual"):
            try:
                import json
                config_json = json.dumps(ajustes, indent=2, ensure_ascii=False)
                st.download_button(
                    label="💾 Descargar JSON",
                    data=config_json,
                    file_name=f"ajustes_app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            except Exception as e:
                st.error(f"❌ Error al exportar: {e}")
    
    with col3:
        if st.button("⚠️ Restablecer por defecto", help="Vuelve a la configuración inicial"):
            if st.checkbox("Confirmar restablecimiento (no se puede deshacer)"):
                try:
                    defaults = {
                        "nombre_app": "Gestor de Formación",
                        "color_primario": "#4285F4",
                        "color_secundario": "#5f6368",
                        "color_exito": "#10b981",
                        "color_advertencia": "#f59e0b",
                        "color_error": "#ef4444",
                        "mensaje_login": "Accede al gestor con tus credenciales.",
                        "mensaje_footer": "© 2025 Gestor de Formación · Streamlit + Supabase",
                        "bienvenida_admin": "Panel de Administración SaaS",
                        "bienvenida_gestor": "Panel del Gestor",
                        "bienvenida_alumno": "Área del Alumno",
                        "bienvenida_comercial": "Área Comercial - CRM"
                    }
                    update_ajustes_app(supabase, defaults)
                    st.success("✅ Configuración restablecida a valores por defecto.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al restablecer: {e}")

    # =========================
    # Monitor de sistema para admin
    # =========================
    st.divider()
    st.markdown("### 📊 Estado del Sistema")
    
    try:
        data_service = get_data_service(supabase, session_state)
        metricas = data_service.get_metricas_admin()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏢 Empresas", metricas.get("total_empresas", "N/A"))
        with col2:
            st.metric("👥 Usuarios", metricas.get("total_usuarios", "N/A"))
        with col3:
            st.metric("📚 Cursos", metricas.get("total_cursos", "N/A"))
        with col4:
            st.metric("👨‍🎓 Grupos", metricas.get("total_grupos", "N/A"))
    except Exception as e:
        st.warning(f"No se pudieron cargar las métricas del sistema: {e}")

    st.divider()
    st.caption("💡 Los cambios en ajustes se aplican inmediatamente y afectan a todos los usuarios.")
