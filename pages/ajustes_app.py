import streamlit as st
from datetime import datetime
from utils import get_ajustes_app, update_ajustes_app
from services.data_service import get_data_service

def main(supabase, session_state):
    st.title("⚙️ Configuración del Sistema")
    st.caption("Gestiona los textos y configuración operativa de la plataforma")

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

    # =========================
    # CONFIGURACIÓN BÁSICA
    # =========================
    st.subheader("📱 Información Básica")
    
    with st.form("config_basica"):
        col1, col2 = st.columns(2)
        
        with col1:
            nombre_app = st.text_input(
                "Nombre de la aplicación",
                value=ajustes.get("nombre_app", "Gestor de Formación FUNDAE"),
                help="Nombre que aparece en títulos y cabeceras"
            )
            
            mensaje_login = st.text_area(
                "Mensaje de bienvenida en login",
                value=ajustes.get("mensaje_login", "Accede al sistema de gestión de formación"),
                height=80,
                help="Texto que ven los usuarios al iniciar sesión"
            )
        
        with col2:
            mensaje_footer = st.text_area(
                "Texto del pie de página",
                value=ajustes.get("mensaje_footer", "© 2025 Sistema de Gestión FUNDAE"),
                height=80,
                help="Aparece en la parte inferior de todas las páginas"
            )
            
            email_soporte = st.text_input(
                "Email de soporte técnico",
                value=ajustes.get("email_soporte", ""),
                help="Email de contacto para incidencias (opcional)"
            )

        guardar_basico = st.form_submit_button("💾 Guardar configuración básica", use_container_width=True)
        
        if guardar_basico:
            try:
                update_ajustes_app(supabase, {
                    "nombre_app": nombre_app,
                    "mensaje_login": mensaje_login,
                    "mensaje_footer": mensaje_footer,
                    "email_soporte": email_soporte
                })
                st.success("✅ Configuración básica actualizada")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    st.divider()

    # =========================
    # TEXTOS POR ROL DE USUARIO
    # =========================
    st.subheader("👤 Mensajes por Tipo de Usuario")
    
    tab1, tab2, tab3, tab4 = st.tabs(["👑 Admin", "🏢 Gestor", "🎓 Alumno", "📊 Comercial"])
    
    with tab1:
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

    with tab2:
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

    with tab3:
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

    with tab4:
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

    st.divider()

    # =========================
    # INFORMACIÓN DEL SISTEMA
    # =========================
    st.subheader("📊 Estado del Sistema")
    
    try:
        data_service = get_data_service(supabase, session_state)
        
        # Usar el método optimizado de data_service con cache
        metricas = data_service.get_metricas_admin()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🏢 Empresas", metricas.get("total_empresas", 0))
        
        with col2:
            st.metric("👥 Usuarios", metricas.get("total_usuarios", 0))
        
        with col3:
            st.metric("👨‍🎓 Grupos", metricas.get("total_grupos", 0))
        
        with col4:
            # CORRIGIDO: usar el nombre correcto del data_service
            st.metric("📚 Acciones Formativas", metricas.get("total_cursos", 0))

    except Exception as e:
        st.warning(f"No se pudieron cargar las métricas del sistema: {e}")

    # =========================
    # HERRAMIENTAS DE ADMINISTRACIÓN
    # =========================
    st.subheader("🔧 Herramientas de Administración")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Recargar configuración", help="Recarga ajustes desde la base de datos"):
            try:
                st.cache_data.clear()  # Limpiar cache si existe
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
                        "nombre_app": "Gestor de Formación FUNDAE",
                        "mensaje_login": "Accede al sistema de gestión de formación",
                        "mensaje_footer": "© 2025 Sistema de Gestión FUNDAE",
                        "bienvenida_admin": "Panel de Administración",
                        "bienvenida_gestor": "Gestión de Formación",
                        "bienvenida_alumno": "Mi Área de Formación",
                        "bienvenida_comercial": "Área Comercial",
                        "tarjeta_admin_usuarios": "Crear y gestionar usuarios del sistema",
                        "tarjeta_admin_empresas": "Administrar empresas y sus módulos",
                        "tarjeta_admin_ajustes": "Ajustar configuración global del sistema",
                        "tarjeta_gestor_grupos": "Crear y gestionar grupos formativos",
                        "tarjeta_gestor_documentos": "Generar documentación FUNDAE",
                        "tarjeta_alumno_grupos": "Consultar grupos en los que participo",
                        "tarjeta_alumno_diplomas": "Descargar certificados y diplomas",
                        "tarjeta_comercial_clientes": "Gestionar cartera de clientes"
                    }
                    update_ajustes_app(supabase, defaults)
                    st.success("✅ Configuración restablecida")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al restablecer: {e}")

    st.divider()
    
    # =========================
    # INFORMACIÓN FINAL
    # =========================
    with st.expander("ℹ️ Información sobre configuración", expanded=False):
        st.markdown("""
        **¿Qué puedes configurar aquí?**
        
        - **Textos de la aplicación**: Personaliza mensajes que ven los usuarios
        - **Información básica**: Nombre de la app y datos de contacto
        - **Mensajes por rol**: Diferentes textos según el tipo de usuario
        - **Estado del sistema**: Monitoreo básico de datos
        
        **Los cambios se aplican inmediatamente** y afectan a todos los usuarios.
        
        **Recomendaciones:**
        - Usa textos claros y específicos para cada rol
        - Mantén un email de soporte actualizado
        - Exporta la configuración antes de hacer cambios importantes
        """)

    st.caption("💡 Los ajustes se guardan automáticamente y se aplican de forma inmediata.")
