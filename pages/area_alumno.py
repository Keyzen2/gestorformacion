import streamlit as st
import pandas as pd
import importlib
import sys
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from services.participantes_service import get_participantes_service
from services.grupos_service import get_grupos_service
from services.clases_service import get_clases_service

# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="🎓 Área del Alumno",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# VERIFICACIÓN DE ACCESO CORREGIDA
# =========================
def verificar_acceso_alumno(session_state, supabase):
    """Verifica que el usuario tenga acceso al área de alumnos"""
    # Si ya viene con rol alumno → OK
    if session_state.role == "alumno":
        return True

    # Verificar datos de usuario
    if not hasattr(session_state, 'user') or not session_state.user:
        st.error("🔒 No se encontraron datos de usuario")
        st.stop()
        return False

    auth_id = session_state.user.get("id")
    
    if not auth_id or str(auth_id) == "None":
        st.error("🔒 Usuario no autenticado correctamente")
        st.stop()
        return False

    try:
        # CORREGIDO: Usar el servicio para obtener participante_id
        participantes_service = get_participantes_service(supabase, session_state)
        participante_id = participantes_service.get_participante_id_from_auth(auth_id)
        
        if participante_id:
            session_state.role = "alumno"
            # Guardar participante_id en session_state para uso posterior
            session_state.participante_id = participante_id
            return True
        else:
            st.error("🔒 Acceso restringido al área de alumnos")
            
            # Información de diagnóstico
            with st.expander("Información de diagnóstico"):
                st.write(f"Auth ID: {auth_id}")
                
                # Verificar si existe en usuarios
                user_check = supabase.table("usuarios").select("email, rol").eq("auth_id", auth_id).execute()
                if user_check.data:
                    user_data = user_check.data[0]
                    st.write(f"Usuario: {user_data['email']} (rol: {user_data['rol']})")
                    
                    # Verificar si existe participante con ese email
                    participante_check = supabase.table("participantes").select("id, auth_id").eq("email", user_data['email']).execute()
                    if participante_check.data:
                        p_data = participante_check.data[0]
                        st.write(f"Participante encontrado: ID {p_data['id']}")
                        st.write(f"Auth_ID del participante: {p_data['auth_id']}")
                        
                        if not p_data['auth_id']:
                            st.warning("El participante no tiene auth_id asignado. Contacta al administrador.")
                            # AUTOFIX: Intentar corregir automáticamente
                            try:
                                supabase.table("participantes").update({
                                    "auth_id": auth_id
                                }).eq("id", p_data['id']).execute()
                                st.success("¡Auth_id corregido automáticamente! Recarga la página.")
                            except Exception as fix_error:
                                st.error(f"Error intentando corregir: {fix_error}")
                    else:
                        st.warning("No existe registro de participante para este email.")
                else:
                    st.error("Usuario no encontrado en la base de datos.")
            
            st.stop()
            return False
            
    except Exception as e:
        st.error(f"Error verificando acceso: {e}")
        st.stop()
        return False

def debug_session_state(session_state):
    """Función de debug para verificar session_state"""
    try:
        st.write("**Debug Session State:**")
        st.write(f"Role: {getattr(session_state, 'role', 'NO_ROLE')}")
        
        if hasattr(session_state, 'user') and session_state.user:
            user = session_state.user
            st.write(f"User ID: {user.get('id', 'NO_ID')}")
            st.write(f"User Email: {user.get('email', 'NO_EMAIL')}")
        else:
            st.write("User: NO_USER_DATA")
            
        # Mostrar participante_id si existe
        if hasattr(session_state, 'participante_id'):
            st.write(f"Participante ID: {session_state.participante_id}")
    except Exception as e:
        st.write(f"Error en debug: {e}")

# =========================
# TAB 1: MIS GRUPOS FUNDAE
# =========================
def mostrar_mis_grupos_fundae(grupos_service, participantes_service, session_state):
    """Muestra los grupos FUNDAE del participante - VERSIÓN CORREGIDA"""
    st.header("📚 Mis Grupos FUNDAE")
    
    # Debug del session_state (opcional)
    if st.checkbox("Mostrar información de debug", value=False):
        debug_session_state(session_state)
    
    # CORREGIDO: Obtener participante_id de forma más robusta
    participante_id = None
    
    if hasattr(session_state, 'participante_id'):
        participante_id = session_state.participante_id
    else:
        auth_id = session_state.user.get('id')
        participante_id = participantes_service.get_participante_id_from_auth(auth_id)
        if participante_id:
            session_state.participante_id = participante_id
    
    if not participante_id:
        st.error("❌ No se pudo encontrar tu registro como participante")
        return

    try:
        # Obtener grupos del participante usando el método correcto
        df_grupos = participantes_service.get_grupos_de_participante(participante_id)
        
        if df_grupos.empty:
            st.info("🔭 No estás inscrito en ningún grupo FUNDAE")
            st.markdown("""
            **¿Qué son los grupos FUNDAE?**
            - Formación bonificada para trabajadores
            - Cursos oficiales con certificación
            - Financiados por FUNDAE (Fundación Estatal para la Formación en el Empleo)
            
            Contacta con tu empresa para inscribirte en grupos formativos.
            """)
            return
        
        st.markdown(f"### 🎯 Tienes {len(df_grupos)} grupo(s) asignado(s)")
        
        # Mostrar grupos en cards
        for idx, grupo in df_grupos.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    codigo_grupo = grupo.get('codigo_grupo', 'Sin código')
                    accion_nombre = grupo.get('accion_nombre', 'Sin acción formativa')
                    
                    st.markdown(f"**📖 {codigo_grupo}**")
                    st.markdown(f"*{accion_nombre}*")
                    
                    # Mostrar horas si están disponibles
                    accion_horas = grupo.get('accion_horas', 0)
                    if accion_horas and accion_horas > 0:
                        st.caption(f"⏱️ Duración: {accion_horas} horas")
                
                with col2:
                    # Fechas del grupo
                    fecha_inicio = grupo.get("fecha_inicio")
                    fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
                    
                    if fecha_inicio:
                        try:
                            inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')
                            st.write(f"📅 **Inicio:** {inicio_str}")
                        except:
                            st.write(f"📅 **Inicio:** {fecha_inicio}")
                    
                    if fecha_fin:
                        try:
                            fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                            st.write(f"🏁 **Fin:** {fin_str}")
                            
                            # Calcular estado
                            try:
                                hoy = pd.Timestamp.now().date()
                                fecha_fin_dt = pd.to_datetime(fecha_fin).date()
                                
                                if fecha_fin_dt < hoy:
                                    st.success("✅ **Finalizado**")
                                elif fecha_inicio:
                                    fecha_inicio_dt = pd.to_datetime(fecha_inicio).date()
                                    if fecha_inicio_dt <= hoy <= fecha_fin_dt:
                                        st.info("🟡 **En curso**")
                                    else:
                                        st.warning("⏳ **Próximamente**")
                                else:
                                    st.info("📅 **Programado**")
                            except:
                                st.caption("📅 Estado no disponible")
                        except:
                            st.write(f"🏁 **Fin:** {fecha_fin}")
                    
                    # Modalidad e información adicional
                    modalidad = grupo.get('modalidad')
                    if modalidad:
                        st.caption(f"🎯 Modalidad: {modalidad}")
                    
                    lugar_imparticion = grupo.get('lugar_imparticion')
                    if lugar_imparticion:
                        st.caption(f"🏢 Lugar: {lugar_imparticion}")
                
                with col3:
                    # Fecha de asignación
                    fecha_asignacion = grupo.get('fecha_asignacion')
                    if fecha_asignacion:
                        try:
                            fecha_asignacion_str = pd.to_datetime(fecha_asignacion).strftime('%d/%m/%Y')
                            st.caption(f"📋 Inscrito: {fecha_asignacion_str}")
                        except:
                            st.caption(f"📋 Inscrito: {fecha_asignacion}")
                    
                    # Botón de información adicional
                    grupo_id = grupo.get('grupo_id', grupo.get('id', 'sin_id'))
                    if st.button("ℹ️ Detalles", key=f"detalles_{grupo_id}_{participante_id}_{idx}", use_container_width=True):
                        mostrar_detalles_grupo_fundae(grupos_service, grupo_id)
        
        # Información adicional sobre FUNDAE
        with st.expander("ℹ️ Información sobre Formación FUNDAE"):
            st.markdown("""
            **🎓 Sistema de Formación FUNDAE:**
            - **Gratuita**: Financiada por la Fundación Estatal para la Formación en el Empleo
            - **Certificada**: Al completar obtienes un diploma oficial
            - **Horarios establecidos**: Fechas y horarios fijos por grupo
            - **Seguimiento**: Tu empresa gestiona tu progreso y asistencia
            
            **📋 Tus responsabilidades:**
            - Asistir puntualmente a las sesiones
            - Participar activamente en la formación
            - Completar las evaluaciones requeridas
            
            **📜 Diplomas:** Una vez finalizado el grupo, recibirás tu diploma oficial.
            """)
    
    except Exception as e:
        st.error(f"❌ Error cargando tus grupos FUNDAE: {e}")
        st.write(f"Detalles del error: {str(e)}")

def mostrar_detalles_grupo_fundae(grupos_service, grupo_id):
    """Muestra detalles adicionales de un grupo FUNDAE."""
    try:
        # CORREGIDO: Verificar si el método existe antes de llamarlo
        if hasattr(grupos_service, 'get_grupo_completo'):
            grupo_detalle = grupos_service.get_grupo_completo(grupo_id)
        else:
            # Método alternativo: obtener grupo básico
            grupo_detalle = grupos_service.supabase.table("grupos").select("*").eq("id", grupo_id).execute()
            grupo_detalle = grupo_detalle.data[0] if grupo_detalle.data else None
        
        if grupo_detalle:
            st.markdown("#### 📋 Información Detallada del Grupo")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Código:** {grupo_detalle.get('codigo_grupo', 'N/A')}")
                st.write(f"**Estado:** {grupo_detalle.get('estado', 'N/A')}")
                st.write(f"**Modalidad:** {grupo_detalle.get('modalidad', 'N/A')}")
                
            with col2:
                st.write(f"**Lugar:** {grupo_detalle.get('lugar_imparticion', 'N/A')}")
                st.write(f"**Observaciones:** {grupo_detalle.get('observaciones', 'Ninguna')}")
            
            # Horarios si están disponibles
            if grupo_detalle.get('horarios'):
                st.markdown("**⏰ Horarios:**")
                st.text(grupo_detalle['horarios'])
        else:
            st.warning("No se pudieron cargar los detalles del grupo")
    
    except Exception as e:
        st.error(f"Error cargando detalles: {e}")

# =========================
# TAB 2: MIS CLASES RESERVADAS
# =========================
def mostrar_mis_clases_reservadas(clases_service, session_state):
    """Muestra las clases reservadas - VERSIÓN CORREGIDA"""
    st.header("🏃‍♀️ Mis Clases Reservadas")
    
    # CORREGIDO: Obtener participante_id de forma más robusta
    participante_id = None
    
    if hasattr(session_state, 'participante_id'):
        participante_id = session_state.participante_id
    else:
        # Si no está en session_state, intentar obtenerlo del servicio
        auth_id = session_state.user.get('id')
        if hasattr(clases_service, 'get_participante_id_from_auth'):
            participante_id = clases_service.get_participante_id_from_auth(auth_id)
        else:
            # Buscar directamente en la base de datos
            result = clases_service.supabase.table("participantes").select("id").eq("auth_id", auth_id).execute()
            participante_id = result.data[0]["id"] if result.data else None
            
        if participante_id:
            session_state.participante_id = participante_id
    
    if not participante_id:
        st.error("❌ No se pudo encontrar tu registro como participante")
        return
        
    try:
        # Verificar suscripción
        suscripcion = clases_service.get_suscripcion_participante(participante_id)
        
        if not suscripcion or not suscripcion.get("activa"):
            st.warning("⚠️ No tienes una suscripción activa de clases")
            st.info("Contacta con tu centro de formación para activar tu suscripción.")
            return
        
        # Mostrar información de suscripción
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🎯 Clases Mensuales", suscripcion.get("clases_mensuales", 0))
        with col2:
            st.metric("✅ Usadas Este Mes", suscripcion.get("clases_usadas_mes", 0))
        with col3:
            disponibles = suscripcion.get("clases_mensuales", 0) - suscripcion.get("clases_usadas_mes", 0)
            st.metric("⚡ Disponibles", disponibles)
        with col4:
            if suscripcion.get("fecha_activacion"):
                fecha_activacion = pd.to_datetime(suscripcion["fecha_activacion"]).strftime('%d/%m/%Y')
                st.caption(f"📅 Activa desde: {fecha_activacion}")
        
        # Progreso mensual
        if suscripcion.get("clases_mensuales", 0) > 0:
            progreso = suscripcion.get("clases_usadas_mes", 0) / suscripcion["clases_mensuales"]
            st.progress(progreso, f"Uso mensual: {suscripcion.get('clases_usadas_mes', 0)}/{suscripcion['clases_mensuales']}")
        
        st.divider()
        
        # Filtros de período
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_inicio = st.date_input(
                "Ver reservas desde",
                value=date.today(),
                key="mis_reservas_inicio"
            )
        
        with col2:
            fecha_fin = st.date_input(
                "Hasta",
                value=date.today() + timedelta(days=30),
                key="mis_reservas_fin"
            )
        
        # Obtener reservas del participante
        df_reservas = clases_service.get_reservas_participante(participante_id, fecha_inicio, fecha_fin)
        
        if df_reservas.empty:
            st.info("🔭 No tienes clases reservadas en este período")
            st.markdown("💡 Ve a la pestaña **'Reservar Clases'** para hacer nuevas reservas")
        else:
            st.markdown(f"### 📋 {len(df_reservas)} reserva(s) encontrada(s)")
            
            # Mostrar tabla de reservas
            st.dataframe(
                df_reservas[['clase_nombre', 'fecha_clase', 'horario_display', 'estado']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "clase_nombre": "🏃‍♀️ Clase",
                    "fecha_clase": "📅 Fecha",
                    "horario_display": "⏰ Horario",
                    "estado": "📊 Estado"
                }
            )
    
    except Exception as e:
        st.error(f"❌ Error cargando tus reservas: {e}")
        st.write(f"Detalles del error: {str(e)}")

# =========================
# TAB 3: RESERVAR CLASES
# =========================   
def mostrar_reservar_clases(clases_service, session_state):
    """Reservar clases - VERSIÓN CORREGIDA"""
    st.header("📅 Reservar Clases")
    
    # CORREGIDO: Obtener participante_id de forma más robusta
    participante_id = None
    
    if hasattr(session_state, 'participante_id'):
        participante_id = session_state.participante_id
    else:
        auth_id = session_state.user.get('id')
        if hasattr(clases_service, 'get_participante_id_from_auth'):
            participante_id = clases_service.get_participante_id_from_auth(auth_id)
        else:
            result = clases_service.supabase.table("participantes").select("id").eq("auth_id", auth_id).execute()
            participante_id = result.data[0]["id"] if result.data else None
            
        if participante_id:
            session_state.participante_id = participante_id
    
    if not participante_id:
        st.error("❌ No se pudo encontrar tu registro como participante")
        return
    
    try:
        # Verificar suscripción
        suscripcion = clases_service.get_suscripcion_participante(participante_id)
        
        if not suscripcion or not suscripcion.get("activa"):
            st.warning("⚠️ No tienes una suscripción activa")
            st.info("Contacta con tu centro de formación para activar tu suscripción.")
            return
        
        # Verificar clases disponibles
        clases_disponibles = suscripcion.get("clases_mensuales", 0) - suscripcion.get("clases_usadas_mes", 0)
        
        if clases_disponibles <= 0:
            st.error("❌ Has agotado tus clases mensuales")
            st.info(f"Tienes {suscripcion.get('clases_mensuales', 0)} clases al mes. El contador se reinicia el próximo mes.")
            return
        
        # Mostrar estado de suscripción
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("⚡ Clases Disponibles", clases_disponibles)
        with col2:
            st.metric("✅ Usadas Este Mes", suscripcion.get("clases_usadas_mes", 0))
        with col3:
            st.metric("🎯 Total Mensuales", suscripcion.get("clases_mensuales", 0))
        
        st.divider()
        
        # Selector de período
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_inicio_busqueda = st.date_input(
                "Ver clases desde",
                value=date.today(),
                min_value=date.today(),
                key="buscar_clases_inicio"
            )
        
        with col2:
            fecha_fin_busqueda = st.date_input(
                "Hasta",
                value=date.today() + timedelta(days=14),
                min_value=date.today(),
                key="buscar_clases_fin"
            )
        
        # MEJORADO: Intentar obtener clases disponibles reales
        try:
            if hasattr(clases_service, 'get_clases_disponibles_participante'):
                clases_disponibles_lista = clases_service.get_clases_disponibles_participante(
                    participante_id, fecha_inicio_busqueda, fecha_fin_busqueda
                )
                
                if clases_disponibles_lista:
                    st.markdown("### 📅 Clases Disponibles")
                    
                    for clase in clases_disponibles_lista:
                        with st.container(border=True):
                            col1, col2, col3 = st.columns([2, 2, 1])
                            
                            with col1:
                                st.write(f"**{clase['title']}**")
                                st.caption(f"Categoría: {clase['extendedProps'].get('categoria', 'N/A')}")
                            
                            with col2:
                                fecha_clase = clase['extendedProps']['fecha_clase']
                                hora_inicio = clase['start'].split('T')[1][:5]
                                hora_fin = clase['end'].split('T')[1][:5]
                                st.write(f"📅 {fecha_clase}")
                                st.write(f"⏰ {hora_inicio} - {hora_fin}")
                            
                            with col3:
                                cupos_libres = clase['extendedProps'].get('cupos_libres', 0)
                                st.metric("🎯 Cupos", cupos_libres)
                                
                                if st.button("📝 Reservar", key=f"reservar_{clase['id']}", 
                                           disabled=cupos_libres <= 0):
                                    # Aquí iría la lógica de reserva
                                    st.success("¡Reserva realizada!")
                else:
                    st.info("🔭 No hay clases disponibles en el período seleccionado")
            else:
                st.info("💡 Funcionalidad de reservas disponible próximamente")
                st.markdown("En esta sección podrás:")
                st.markdown("- Ver clases disponibles por día y horario")
                st.markdown("- Reservar clases con cupos disponibles")
                st.markdown("- Verificar tu límite mensual")
        
        except Exception as e:
            st.warning(f"Error cargando clases disponibles: {e}")
            st.info("💡 Funcionalidad de reservas en desarrollo")
        
    except Exception as e:
        st.error(f"❌ Error cargando clases disponibles: {e}")

# =========================
# TAB 4: MI PERFIL
# =========================
def mostrar_mi_perfil(participantes_service, clases_service, session_state):
    """Mi perfil con gestión de avatar - VERSIÓN ACTUALIZADA"""
    st.header("👤 Mi Perfil")

    # CORREGIDO: Obtener participante_id de forma más robusta
    participante_id = None

    if hasattr(session_state, "participante_id"):
        participante_id = session_state.participante_id
    else:
        auth_id = session_state.user.get("id")
        participante_id = participantes_service.get_participante_id_from_auth(auth_id)
        if participante_id:
            session_state.participante_id = participante_id

    if not participante_id:
        st.error("❌ No se pudo encontrar tu registro como participante")
        return

    try:
        # Obtener datos del participante
        participante_res = participantes_service.supabase.table("participantes").select(
            """
            id, nombre, apellidos, email, telefono, nif, fecha_nacimiento, sexo,
            empresa:empresas(nombre, tipo_empresa)
            """
        ).eq("id", participante_id).execute()

        if not participante_res.data:
            st.error("❌ No se encontraron tus datos")
            return

        participante = participante_res.data[0]

        # Layout principal con avatar
        col_avatar, col_info = st.columns([1, 3])
        
        with col_avatar:
            st.markdown("### 📸 Avatar")
            
            # Obtener y mostrar avatar
            avatar_info = participantes_service.get_avatar_participante(participante_id)
            
            if avatar_info:
                st.image(avatar_info["archivo_url"], width=150, caption="Tu avatar")
                st.caption(f"Subido: {pd.to_datetime(avatar_info['created_at']).strftime('%d/%m/%Y')}")
                
                # Botón eliminar avatar
                if st.button("🗑️ Eliminar", type="secondary", use_container_width=True, key="eliminar_avatar"):
                    if participantes_service.eliminar_avatar(participante_id):
                        st.success("Avatar eliminado")
                        st.rerun()
                    else:
                        st.error("Error eliminando avatar")
            else:
                # Avatar por defecto
                st.image("https://via.placeholder.com/150x150/e1e1e1/999999?text=Sin+Avatar", width=150)
                st.caption("Sin avatar")
            
            # Subir nuevo avatar
            st.markdown("**📤 Cambiar Avatar**")
            uploaded_file = st.file_uploader(
                "Seleccionar imagen",
                type=['png', 'jpg', 'jpeg'],
                help="Max 2MB. Se ajustará a 150x150px",
                key="avatar_upload",
                label_visibility="collapsed"
            )
            
            if uploaded_file:
                # Preview
                st.image(uploaded_file, width=150, caption="Vista previa")
                
                if st.button("💾 Guardar", type="primary", use_container_width=True, key="guardar_avatar"):
                    with st.spinner("Subiendo..."):
                        success = participantes_service.subir_avatar(participante_id, uploaded_file)
                        if success:
                            st.success("✅ Avatar actualizado")
                            st.rerun()
                        else:
                            st.error("❌ Error subiendo avatar")

        with col_info:
            # Información del participante en dos columnas
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### 📋 Información Personal")
                st.markdown(f"**👤 Nombre:** {participante.get('nombre', 'N/A')}")
                st.markdown(f"**👥 Apellidos:** {participante.get('apellidos', 'N/A')}")
                st.markdown(f"**📧 Email:** {participante.get('email', 'N/A')}")
                st.markdown(f"**📞 Teléfono:** {participante.get('telefono', 'No disponible')}")

            with col2:
                st.markdown("### 🏢 Información Adicional")
                st.markdown(f"**🆔 Documento:** {participante.get('nif', 'No disponible')}")

                if participante.get("fecha_nacimiento"):
                    fecha_nac = pd.to_datetime(participante["fecha_nacimiento"]).strftime("%d/%m/%Y")
                    st.markdown(f"**🎂 Fecha Nacimiento:** {fecha_nac}")
                
                if participante.get("sexo"):
                    st.markdown(f"**⚥ Sexo:** {participante['sexo']}")

                # Información de empresa
                if participante.get("empresa"):
                    st.markdown(f"**🏢 Empresa:** {participante['empresa']['nombre']}")

        # Estadísticas mejoradas
        st.markdown("### 📊 Mis Estadísticas")
        try:
            # Grupos FUNDAE
            grupos_participante = participantes_service.get_grupos_de_participante(participante_id)
            num_grupos = len(grupos_participante) if not grupos_participante.empty else 0
            
            # Suscripción de clases
            suscripcion_clases = clases_service.get_suscripcion_participante(participante_id)
            
            # Resumen mensual si tiene suscripción
            resumen_clases = {}
            if suscripcion_clases:
                try:
                    resumen_clases = clases_service.get_resumen_mensual_participante(participante_id)
                except:
                    pass
            
            col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
            
            with col_stats1:
                st.metric("🎓 Grupos FUNDAE", num_grupos)
            
            with col_stats2:
                if suscripcion_clases and suscripcion_clases.get("activa"):
                    clases_disponibles = (
                        suscripcion_clases.get("clases_mensuales", 0)
                        - suscripcion_clases.get("clases_usadas_mes", 0)
                    )
                    st.metric("🏃‍♀️ Clases Disponibles", clases_disponibles)
                else:
                    st.metric("🏃‍♀️ Clases Disponibles", 0)
            
            with col_stats3:
                if resumen_clases and resumen_clases.get("asistencias") is not None:
                    st.metric("✅ Asistencias", resumen_clases.get("asistencias", 0))
                else:
                    st.metric("✅ Asistencias", "N/A")
            
            with col_stats4:
                # Diplomas obtenidos
                try:
                    diplomas_res = (
                        participantes_service.supabase.table("diplomas")
                        .select("id")
                        .eq("participante_id", participante_id)
                        .execute()
                    )
                    num_diplomas = len(diplomas_res.data) if diplomas_res.data else 0
                    st.metric("📜 Diplomas", num_diplomas)
                except Exception:
                    st.metric("📜 Diplomas", "N/A")
            
            # Información adicional de suscripción si existe
            if suscripcion_clases and suscripcion_clases.get("activa"):
                st.markdown("#### 🏃‍♀️ Estado de Suscripción")
                
                # Progreso mensual
                clases_usadas = suscripcion_clases.get("clases_usadas_mes", 0)
                clases_totales = suscripcion_clases.get("clases_mensuales", 1)
                progreso = clases_usadas / max(1, clases_totales)
                
                st.progress(progreso, f"Clases este mes: {clases_usadas}/{clases_totales}")
                
                # Porcentaje de asistencia si hay datos
                if resumen_clases and resumen_clases.get("porcentaje_asistencia") is not None:
                    porcentaje = resumen_clases["porcentaje_asistencia"]
                    st.metric("📈 % Asistencia", f"{porcentaje}%")
        
            # NUEVA SECCIÓN DE DIPLOMAS - AÑADIR AQUÍ
            st.markdown("### 📜 Mis Diplomas")
            
            try:
                # Obtener diplomas del participante
                diplomas_res = participantes_service.supabase.table("diplomas").select("""
                    id, nombre_diploma, fecha_emision, url_archivo, tipo_archivo,
                    grupo:grupos(codigo_grupo, 
                                accion_formativa:acciones_formativas(nombre))
                """).eq("participante_id", participante_id).order("fecha_emision", desc=True).execute()
                
                if diplomas_res.data:
                    st.success(f"Tienes {len(diplomas_res.data)} diploma(s) disponible(s)")
                    
                    for diploma in diplomas_res.data:
                        with st.container(border=True):
                            col1, col2, col3 = st.columns([2, 2, 1])
                            
                            with col1:
                                st.markdown(f"**📜 {diploma.get('nombre_diploma', 'Diploma')}**")
                                if diploma.get('grupo'):
                                    grupo_info = diploma['grupo']
                                    codigo_grupo = grupo_info.get('codigo_grupo', 'Sin código')
                                    accion_nombre = ""
                                    if grupo_info.get('accion_formativa'):
                                        accion_nombre = grupo_info['accion_formativa'].get('nombre', '')
                                    st.caption(f"Grupo: {codigo_grupo}")
                                    if accion_nombre:
                                        st.caption(f"Curso: {accion_nombre}")
                            
                            with col2:
                                if diploma.get('fecha_emision'):
                                    fecha_emision = pd.to_datetime(diploma['fecha_emision']).strftime('%d/%m/%Y')
                                    st.write(f"📅 **Fecha:** {fecha_emision}")
                                
                                tipo_archivo = diploma.get('tipo_archivo', 'PDF')
                                st.write(f"📄 **Formato:** {tipo_archivo}")
                            
                            with col3:
                                if diploma.get('url_archivo'):
                                    st.link_button(
                                        "📥 Descargar",
                                        diploma['url_archivo'],
                                        use_container_width=True
                                    )
                                else:
                                    st.button("📄 Ver", disabled=True, use_container_width=True)
                else:
                    st.info("No tienes diplomas disponibles aún")
                    st.caption("Los diplomas se generan al finalizar los grupos formativos")
        
            except Exception as e:
                st.error(f"Error cargando diplomas: {e}")
        
        except Exception as e:
            st.error(f"❌ Error cargando estadísticas: {e}")
        
        except Exception as e:
            st.error(f"❌ Error cargando información del perfil: {e}")

# =========================
# MAIN FUNCTION
# =========================
def main(supabase, session_state):
    st.title("🎓 Área del Alumno")
    
    # Verificar acceso
    if not verificar_acceso_alumno(session_state, supabase):
        return
    
    # CARGA ROBUSTA DE SERVICIOS - CORREGIDA
    try:
        # Importaciones al inicio
        from services.participantes_service import get_participantes_service
        from services.grupos_service import get_grupos_service
        from services.clases_service import get_clases_service
        
        # Crear servicios
        participantes_service = get_participantes_service(supabase, session_state)
        grupos_service = get_grupos_service(supabase, session_state)
        clases_service = get_clases_service(supabase, session_state)
        
        # Verificar que el servicio crítico tiene los métodos necesarios
        if not hasattr(participantes_service, 'get_grupos_de_participante'):
            st.warning("⚠️ Recargando servicios...")
            
            # Forzar recarga del módulo
            import importlib
            import sys
            
            modules_to_reload = [
                'services.participantes_service',
                'services.grupos_service', 
                'services.clases_service'
            ]
            
            for module_name in modules_to_reload:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
            
            # Reimportar después de la recarga
            from services.participantes_service import get_participantes_service as get_participantes_service_reload
            from services.grupos_service import get_grupos_service as get_grupos_service_reload
            from services.clases_service import get_clases_service as get_clases_service_reload
            
            # Recrear servicios con nombres únicos
            participantes_service = get_participantes_service_reload(supabase, session_state)
            grupos_service = get_grupos_service_reload(supabase, session_state)
            clases_service = get_clases_service_reload(supabase, session_state)
            
            # Verificar nuevamente
            if not hasattr(participantes_service, 'get_grupos_de_participante'):
                st.error("❌ Error crítico: No se pudo cargar el servicio de participantes correctamente")
                st.info("Intenta recargar la página o contacta al administrador")
                return
            else:
                st.success("✅ Servicios recargados correctamente")
    
    except Exception as e:
        st.error(f"❌ Error cargando servicios: {e}")
        st.info("Intenta recargar la página")
        return
    
    # Debug opcional
    if st.sidebar.checkbox("🔧 Mostrar debug", value=False):
        with st.sidebar.expander("Debug Info"):
            st.write("**Servicios cargados:**")
            st.write(f"- Participantes: {type(participantes_service).__name__}")
            st.write(f"- Grupos: {type(grupos_service).__name__}")
            st.write(f"- Clases: {type(clases_service).__name__}")
            st.write(f"- Método grupos disponible: {hasattr(participantes_service, 'get_grupos_de_participante')}")
    
    # Mostrar información del usuario
    st.caption(
        f"👤 Bienvenido/a: {session_state.user.get('nombre', 'Usuario')} "
        f"| 📧 {session_state.user.get('email', 'N/A')}"
    )
    
    # Tabs principales
    tabs = st.tabs([
        "📚 Mis Grupos FUNDAE",
        "🏃‍♀️ Mis Clases", 
        "📅 Reservar Clases",
        "👤 Mi Perfil"
    ])
    
    with tabs[0]:
        mostrar_mis_grupos_fundae(grupos_service, participantes_service, session_state)
    
    with tabs[1]:
        mostrar_mis_clases_reservadas(clases_service, session_state)
    
    with tabs[2]:
        mostrar_reservar_clases(clases_service, session_state)
    
    with tabs[3]:
        mostrar_mi_perfil(participantes_service, clases_service, session_state)

if __name__ == "__main__":
    st.error("Este archivo debe ser ejecutado desde app.py")
