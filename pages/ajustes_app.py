import streamlit as st
from datetime import datetime
from utils import get_ajustes_app, update_ajustes_app
from services.data_service import get_data_service

def main(supabase, session_state):
    st.title("⚙️ Configuración del Sistema")
    st.caption("Gestiona los textos, apariencia y configuración operativa de la plataforma")

    if session_state.role != "admin":
        st.warning("🔒 Solo el administrador puede acceder a esta sección.")
        return

    # Cargar ajustes actuales
    try:
        ajustes = get_ajustes_app(supabase)
        if not ajustes:
            ajustes = {}
    except Exception as e:
        st.error(f"Error al cargar configuración: {e}")
        ajustes = {}

    # Tabs principales para mejor organización
    tabs = st.tabs(["🎨 Apariencia", "📝 Textos", "📊 Sistema", "🔧 Herramientas", 📊 Tablas])

    # =========================
    # TAB APARIENCIA
    # =========================
    with tabs[0]:
        st.subheader("🎨 Branding y Apariencia")
        
        with st.form("config_apariencia"):
            col1, col2 = st.columns(2)
            
            with col1:
                nombre_app = st.text_input(
                    "Nombre de la aplicación",
                    value=ajustes.get("nombre_app", "Gestor de Formación"),
                    help="Nombre que aparece en títulos y cabeceras"
                )
                
                logo_url = st.text_input(
                    "URL del logo",
                    value=ajustes.get("logo_url", ""),
                    help="URL completa de la imagen del logo (opcional)"
                )
                
                if logo_url:
                    try:
                        st.image(logo_url, width=100, caption="Vista previa del logo")
                    except:
                        st.warning("No se puede mostrar la imagen. Verifica la URL.")
            
            with col2:
                color_primario = st.color_picker(
                    "Color primario", 
                    value=ajustes.get("color_primario", "#667eea"),
                    help="Color principal de la interfaz"
                )
                
                color_secundario = st.color_picker(
                    "Color secundario",
                    value=ajustes.get("color_secundario", "#764ba2"),
                    help="Color secundario para acentos"
                )
                
                # Vista previa de colores
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, {color_primario}, {color_secundario});
                    height: 60px;
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: 600;
                    margin-top: 1rem;
                ">
                    Vista previa del gradiente
                </div>
                """, unsafe_allow_html=True)

            guardar_apariencia = st.form_submit_button("💾 Guardar apariencia", use_container_width=True)
            
            if guardar_apariencia:
                try:
                    update_ajustes_app(supabase, {
                        "nombre_app": nombre_app,
                        "logo_url": logo_url,
                        "color_primario": color_primario,
                        "color_secundario": color_secundario
                    })
                    st.cache_data.clear()
                    st.success("✅ Apariencia actualizada correctamente")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    # =========================
    # TAB TEXTOS
    # =========================
    with tabs[1]:
        st.subheader("📝 Mensajes y Textos")
        
        # Configuración básica
        with st.expander("📱 Textos básicos", expanded=True):
            with st.form("textos_basicos"):
                mensaje_login = st.text_area(
                    "Mensaje de bienvenida en login",
                    value=ajustes.get("mensaje_login", "Accede al sistema de gestión de formación"),
                    height=80,
                    help="Texto que ven los usuarios al iniciar sesión"
                )
                
                mensaje_footer = st.text_area(
                    "Texto del pie de página",
                    value=ajustes.get("mensaje_footer", "© 2025 Sistema de Gestión FUNDAE"),
                    height=80,
                    help="Aparece en la parte inferior de todas las páginas"
                )

                if st.form_submit_button("💾 Guardar textos básicos"):
                    try:
                        update_ajustes_app(supabase, {
                            "mensaje_login": mensaje_login,
                            "mensaje_footer": mensaje_footer
                        })
                        st.success("✅ Textos básicos actualizados")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        # Textos por rol
        tab_admin, tab_gestor, tab_alumno, tab_comercial = st.tabs(["👑 Admin", "🏢 Gestor", "🎓 Alumno", "📊 Comercial"])
        
        with tab_admin:
            with st.form("textos_admin"):
                st.markdown("**Textos para Administradores**")
                
                bienvenida_admin = st.text_input(
                    "Título del panel",
                    value=ajustes.get("bienvenida_admin", "Panel de Administración"),
                    help="Encabezado que ve el admin"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    tarjeta_admin_usuarios = st.text_area(
                        "Descripción - Gestión Usuarios",
                        value=ajustes.get("tarjeta_admin_usuarios", "Crear y gestionar usuarios del sistema"),
                        height=60
                    )
                    
                    tarjeta_admin_empresas = st.text_area(
                        "Descripción - Gestión Empresas", 
                        value=ajustes.get("tarjeta_admin_empresas", "Administrar empresas y sus módulos"),
                        height=60
                    )
                
                with col2:
                    tarjeta_admin_ajustes = st.text_area(
                        "Descripción - Configuración",
                        value=ajustes.get("tarjeta_admin_ajustes", "Ajustar configuración global del sistema"),
                        height=60
                    )

                if st.form_submit_button("💾 Guardar textos Admin"):
                    try:
                        update_ajustes_app(supabase, {
                            "bienvenida_admin": bienvenida_admin,
                            "tarjeta_admin_usuarios": tarjeta_admin_usuarios,
                            "tarjeta_admin_empresas": tarjeta_admin_empresas,
                            "tarjeta_admin_ajustes": tarjeta_admin_ajustes
                        })
                        st.success("✅ Textos de Admin actualizados")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        with tab_gestor:
            with st.form("textos_gestor"):
                st.markdown("**Textos para Gestores de Formación**")
                
                bienvenida_gestor = st.text_input(
                    "Título del panel",
                    value=ajustes.get("bienvenida_gestor", "Gestión de Formación"),
                    help="Encabezado que ve el gestor"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    tarjeta_gestor_grupos = st.text_area(
                        "Descripción - Grupos",
                        value=ajustes.get("tarjeta_gestor_grupos", "Crear y gestionar grupos formativos"),
                        height=60
                    )
                    
                    tarjeta_gestor_documentos = st.text_area(
                        "Descripción - Documentos",
                        value=ajustes.get("tarjeta_gestor_documentos", "Generar documentación FUNDAE"),
                        height=60
                    )
                
                with col2:
                    tarjeta_gestor_docu_avanzada = st.text_area(
                        "Descripción - Documentos Avanzados",
                        value=ajustes.get("tarjeta_gestor_docu_avanzada", "Repositorio documental avanzado"),
                        height=60
                    )

                if st.form_submit_button("💾 Guardar textos Gestor"):
                    try:
                        update_ajustes_app(supabase, {
                            "bienvenida_gestor": bienvenida_gestor,
                            "tarjeta_gestor_grupos": tarjeta_gestor_grupos,
                            "tarjeta_gestor_documentos": tarjeta_gestor_documentos,
                            "tarjeta_gestor_docu_avanzada": tarjeta_gestor_docu_avanzada
                        })
                        st.success("✅ Textos de Gestor actualizados")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        with tab_alumno:
            with st.form("textos_alumno"):
                st.markdown("**Textos para Alumnos**")
                
                bienvenida_alumno = st.text_input(
                    "Título del panel",
                    value=ajustes.get("bienvenida_alumno", "Mi Área de Formación"),
                    help="Encabezado que ve el alumno"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    tarjeta_alumno_grupos = st.text_area(
                        "Descripción - Mis Grupos",
                        value=ajustes.get("tarjeta_alumno_grupos", "Consultar grupos en los que participo"),
                        height=60
                    )
                    
                    tarjeta_alumno_diplomas = st.text_area(
                        "Descripción - Mis Diplomas",
                        value=ajustes.get("tarjeta_alumno_diplomas", "Descargar certificados y diplomas"),
                        height=60
                    )
                
                with col2:
                    tarjeta_alumno_seguimiento = st.text_area(
                        "Descripción - Mi Progreso",
                        value=ajustes.get("tarjeta_alumno_seguimiento", "Ver el progreso de mi formación"),
                        height=60
                    )

                if st.form_submit_button("💾 Guardar textos Alumno"):
                    try:
                        update_ajustes_app(supabase, {
                            "bienvenida_alumno": bienvenida_alumno,
                            "tarjeta_alumno_grupos": tarjeta_alumno_grupos,
                            "tarjeta_alumno_diplomas": tarjeta_alumno_diplomas,
                            "tarjeta_alumno_seguimiento": tarjeta_alumno_seguimiento
                        })
                        st.success("✅ Textos de Alumno actualizados")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        with tab_comercial:
            with st.form("textos_comercial"):
                st.markdown("**Textos para Comerciales**")
                
                bienvenida_comercial = st.text_input(
                    "Título del panel",
                    value=ajustes.get("bienvenida_comercial", "Área Comercial"),
                    help="Encabezado que ve el comercial"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    tarjeta_comercial_clientes = st.text_area(
                        "Descripción - Clientes",
                        value=ajustes.get("tarjeta_comercial_clientes", "Gestionar cartera de clientes"),
                        height=60
                    )
                    
                    tarjeta_comercial_oportunidades = st.text_area(
                        "Descripción - Oportunidades",
                        value=ajustes.get("tarjeta_comercial_oportunidades", "Seguimiento de oportunidades de venta"),
                        height=60
                    )
                
                with col2:
                    tarjeta_comercial_tareas = st.text_area(
                        "Descripción - Tareas",
                        value=ajustes.get("tarjeta_comercial_tareas", "Organizar visitas y seguimientos"),
                        height=60
                    )

                if st.form_submit_button("💾 Guardar textos Comercial"):
                    try:
                        update_ajustes_app(supabase, {
                            "bienvenida_comercial": bienvenida_comercial,
                            "tarjeta_comercial_clientes": tarjeta_comercial_clientes,
                            "tarjeta_comercial_oportunidades": tarjeta_comercial_oportunidades,
                            "tarjeta_comercial_tareas": tarjeta_comercial_tareas
                        })
                        st.success("✅ Textos de Comercial actualizados")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # =========================
    # TAB SISTEMA
    # =========================
    with tabs[2]:
        st.subheader("📊 Estado del Sistema")
        
        try:
            data_service = get_data_service(supabase, session_state)
            
            # Usar métricas de data_service si está disponible
            if hasattr(data_service, 'get_metricas_admin'):
                metricas = data_service.get_metricas_admin()
            else:
                # Fallback a consultas directas
                empresas_res = supabase.table("empresas").select("id", count="exact").execute()
                usuarios_res = supabase.table("usuarios").select("id", count="exact").execute()
                grupos_res = supabase.table("grupos").select("id", count="exact").execute()
                cursos_res = supabase.table("acciones_formativas").select("id", count="exact").execute()
                
                metricas = {
                    "total_empresas": empresas_res.count or 0,
                    "total_usuarios": usuarios_res.count or 0,
                    "total_grupos": grupos_res.count or 0,
                    "total_cursos": cursos_res.count or 0
                }
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🏢 Empresas", metricas.get("total_empresas", 0))
            
            with col2:
                st.metric("👥 Usuarios", metricas.get("total_usuarios", 0))
            
            with col3:
                st.metric("👨‍🎓 Grupos", metricas.get("total_grupos", 0))
            
            with col4:
                st.metric("📚 Acciones Formativas", metricas.get("total_cursos", 0))

        except Exception as e:
            st.warning(f"No se pudieron cargar las métricas del sistema: {e}")

        # Información adicional del sistema
        with st.expander("ℹ️ Información del sistema"):
            st.markdown(f"""
            **Última actualización de ajustes**: {ajustes.get('updated_at', 'No disponible')}
            
            **Campos disponibles en ajustes_app**:
            - ✅ Branding (nombre_app, logo_url, colores)
            - ✅ Textos de login y footer
            - ✅ Mensajes de bienvenida por rol
            - ✅ Descripciones de tarjetas por funcionalidad
            """)

    # =========================
    # TAB HERRAMIENTAS
    # =========================
    with tabs[3]:
        st.subheader("🔧 Herramientas de Administración")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Recargar configuración", help="Recarga ajustes desde la base de datos"):
                try:
                    st.cache_data.clear()
                    st.success("✅ Configuración recargada")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al recargar: {e}")
        
        with col2:
            if st.button("📋 Exportar configuración", help="Descarga la configuración actual"):
                try:
                    import json
                    config_export = {
                        "timestamp": datetime.now().isoformat(),
                        "version": "1.0",
                        "ajustes": ajustes
                    }
                    config_json = json.dumps(config_export, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="💾 Descargar JSON",
                        data=config_json,
                        file_name=f"config_sistema_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                except Exception as e:
                    st.error(f"Error al exportar: {e}")
        
        with col3:
            with st.popover("⚠️ Restablecer configuración"):
                st.write("**¿Estás seguro?**")
                st.write("Esta acción restaurará todos los textos a valores por defecto.")
                
                if st.button("🔴 Sí, restablecer todo", type="primary"):
                    try:
                        defaults = {
                            "nombre_app": "Gestor de Formación",
                            "mensaje_login": "Accede al sistema de gestión de formación",
                            "mensaje_footer": "© 2025 Sistema de Gestión FUNDAE",
                            "color_primario": "#667eea",
                            "color_secundario": "#764ba2",
                            "logo_url": "",
                            "bienvenida_admin": "Panel de Administración",
                            "bienvenida_gestor": "Gestión de Formación",
                            "bienvenida_alumno": "Mi Área de Formación",
                            "bienvenida_comercial": "Área Comercial",
                            "tarjeta_admin_usuarios": "Crear y gestionar usuarios del sistema",
                            "tarjeta_admin_empresas": "Administrar empresas y sus módulos",
                            "tarjeta_admin_ajustes": "Ajustar configuración global del sistema",
                            "tarjeta_gestor_grupos": "Crear y gestionar grupos formativos",
                            "tarjeta_gestor_documentos": "Generar documentación FUNDAE",
                            "tarjeta_gestor_docu_avanzada": "Repositorio documental avanzado",
                            "tarjeta_alumno_grupos": "Consultar grupos en los que participo",
                            "tarjeta_alumno_diplomas": "Descargar certificados y diplomas",
                            "tarjeta_alumno_seguimiento": "Ver el progreso de mi formación",
                            "tarjeta_comercial_clientes": "Gestionar cartera de clientes",
                            "tarjeta_comercial_oportunidades": "Seguimiento de oportunidades de venta",
                            "tarjeta_comercial_tareas": "Organizar visitas y seguimientos"
                        }
                        update_ajustes_app(supabase, defaults)
                        st.cache_data.clear()
                        st.success("✅ Configuración restablecida")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al restablecer: {e}")

    # =========================
    # 📊 CONFIGURACIÓN DE TABLAS
    # =========================
    with st.tab("📊 Tablas"):
        st.subheader("📊 Configuración de Tablas")
    
        # Posibles columnas de usuarios
        columnas_posibles_usuarios = [
            "nombre_completo", "email", "telefono", "rol",
            "nif", "empresa_nombre", "created_at"
        ]
    
        # Cargar ajustes actuales
        columnas_seleccionadas = ajustes.get("columnas_usuarios", columnas_posibles_usuarios)
    
        columnas_seleccionadas = st.multiselect(
            "Columnas visibles en la tabla de Usuarios",
            options=columnas_posibles_usuarios,
            default=columnas_seleccionadas
        )
    
        if st.button("💾 Guardar configuración de columnas"):
            update_ajustes_app(supabase, {
                "columnas_usuarios": columnas_seleccionadas
            })
            st.success("✅ Configuración guardada")
            st.rerun()
            
    st.divider()
    # =========================
    # INFORMACIÓN FINAL
    # =========================
    with st.expander("ℹ️ Información sobre configuración", expanded=False):
        st.markdown("""
        **¿Qué puedes configurar aquí?**
        
        - **🎨 Apariencia**: Logo, colores corporativos y branding
        - **📝 Textos**: Mensajes personalizados por rol de usuario
        - **📊 Sistema**: Monitoreo básico de datos y estadísticas
        - **🔧 Herramientas**: Exportar, importar y restablecer configuración
        
        **Los cambios se aplican inmediatamente** y afectan a todos los usuarios.
        
        **Recomendaciones:**
        - Usa textos claros y específicos para cada rol
        - Mantén los colores corporativos coherentes
        - Exporta la configuración antes de hacer cambios importantes
        - El logo debe ser una URL válida y accesible públicamente
        """)

    st.caption("💡 Los ajustes se guardan automáticamente y se aplican de forma inmediata.")
