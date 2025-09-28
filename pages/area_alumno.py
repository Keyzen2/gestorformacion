import streamlit as st
import pandas as pd
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
# VERIFICACIÓN DE ACCESO
# =========================
def verificar_acceso_alumno(session_state, supabase):
    # Si ya viene con rol alumno → OK
    if session_state.role == "alumno":
        return True

    # Si no, comprobar si el auth_id está en participantes
    auth_id = session_state.user.get("id")
    if not auth_id:
        st.error("🔒 No se ha encontrado usuario autenticado")
        st.stop()
        return False

    # CORREGIDO: Buscar por auth_id en lugar de email
    participante = supabase.table("participantes").select("id").eq("auth_id", auth_id).execute()
    if participante.data:
        # Forzamos rol alumno
        session_state.role = "alumno"
        return True

    # Si no es participante → error
    st.error("🔒 Acceso restringido al área de alumnos")
    st.stop()
    return False
    
def get_participante_id_from_auth(supabase, auth_id):
    """Convierte auth_id a participante_id - CORREGIDO"""
    try:
        result = supabase.table("participantes").select("id").eq("auth_id", auth_id).execute()
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        st.error(f"Error obteniendo participante_id: {e}")
        return None
# =========================
# TAB 1: MIS GRUPOS FUNDAE
# =========================
def mostrar_mis_grupos_fundae(grupos_service, participantes_service, session_state):
    """Muestra los grupos FUNDAE del participante - VERSIÓN CORREGIDA"""
    st.header("📚 Mis Grupos FUNDAE")
    
    # Debug del session_state
    debug_session_state(session_state)
    
    auth_id = session_state.user.get('id')
    
    if not auth_id or auth_id == "None":
        st.error("❌ No se pudo obtener tu identificador de usuario")
        return
    
    participante_id = get_participante_id_from_auth(grupos_service.supabase, auth_id)
    
    if not participante_id:
        st.error("❌ No se pudo encontrar tu registro como participante")
            
            # Información de ayuda
            st.info("""
            **Posibles causas:**
            - Tu cuenta no está registrada como participante
            - Falta la relación entre tu usuario y el registro de participante
            - El administrador aún no ha completado tu perfil
        
            **Solución:** Contacta con el administrador del sistema.
            """)
            return

    try:
        df_grupos = participantes_service.get_grupos_de_participante(participante_id)
        
        if df_grupos.empty:
            st.info("📭 No estás inscrito en ningún grupo FUNDAE")
            return
        
        st.markdown(f"### 🎯 Tienes {len(df_grupos)} grupo(s) asignado(s)")
        
        # Mostrar grupos en cards
        for _, grupo in df_grupos.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**📖 {grupo['codigo_grupo']}**")
                    st.markdown(f"*{grupo.get('accion_nombre', 'Sin acción formativa')}*")
                    
                    # Mostrar horas si están disponibles
                    if grupo.get('accion_horas', 0) > 0:
                        st.caption(f"⏱️ Duración: {grupo['accion_horas']} horas")
                
                with col2:
                    # Fechas del grupo
                    fecha_inicio = grupo.get("fecha_inicio")
                    fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
                    
                    if fecha_inicio:
                        inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')
                        st.write(f"📅 **Inicio:** {inicio_str}")
                    
                    if fecha_fin:
                        fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                        st.write(f"🏁 **Fin:** {fin_str}")
                        
                        # Calcular estado
                        hoy = pd.Timestamp.now().date()
                        fecha_fin_dt = pd.to_datetime(fecha_fin).date()
                        
                        if fecha_fin_dt < hoy:
                            st.success("✅ **Finalizado**")
                        elif fecha_inicio and pd.to_datetime(fecha_inicio).date() <= hoy <= fecha_fin_dt:
                            st.info("🟡 **En curso**")
                        else:
                            st.warning("⏳ **Próximamente**")
                    
                    # Modalidad e información adicional
                    if grupo.get('modalidad'):
                        st.caption(f"📍 Modalidad: {grupo['modalidad']}")
                    
                    if grupo.get('lugar_imparticion'):
                        st.caption(f"🏢 Lugar: {grupo['lugar_imparticion']}")
                
                with col3:
                    # Fecha de asignación
                    if grupo.get('fecha_asignacion'):
                        fecha_asignacion = pd.to_datetime(grupo['fecha_asignacion']).strftime('%d/%m/%Y')
                        st.caption(f"📋 Inscrito: {fecha_asignacion}")
                    
                    # Botón de información adicional
                    if st.button("ℹ️ Detalles", key=f"detalles_{grupo['grupo_id']}", use_container_width=True):
                        mostrar_detalles_grupo_fundae(grupos_service, grupo['grupo_id'])
        
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

def mostrar_detalles_grupo_fundae(grupos_service, grupo_id):
    """Muestra detalles adicionales de un grupo FUNDAE."""
    try:
        # Obtener información detallada del grupo
        grupo_detalle = grupos_service.get_grupo_completo(grupo_id)
        
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
    
    except Exception as e:
        st.error(f"Error cargando detalles: {e}")

# =========================
# TAB 2: MIS CLASES RESERVADAS
# =========================
def mostrar_mis_clases_reservadas(clases_service, session_state):
    """Muestra las clases reservadas - VERSIÓN CORREGIDA"""
    st.header("🏃‍♀️ Mis Clases Reservadas")
    
    auth_id = session_state.user.get('id')
    
    if not auth_id or auth_id == "None":
        st.error("❌ No se pudo obtener tu identificador de usuario")
        return
    
    participante_id = get_participante_id_from_auth(clases_service.supabase, auth_id)
    
    if not participante_id:
        st.error("❌ No se pudo encontrar tu registro como participante")
        return
        
    try:
        # Verificar suscripción
        suscripcion = clases_service.get_suscripcion_participante(participante_id)
        
        if not suscripcion or not suscripcion.get("activa"):
            st.warning("⚠️ No tienes una suscripción activa de clases")
            st.info("Contacta con tu centro de formación para activar tu suscripción y poder reservar clases.")
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
            st.info("📭 No tienes clases reservadas en este período")
            st.markdown("💡 Ve a la pestaña **'Reservar Clases'** para hacer nuevas reservas")
        else:
            st.markdown(f"### 📋 {len(df_reservas)} reserva(s) encontrada(s)")
            
            # Agrupar por estado
            reservas_por_estado = df_reservas.groupby('estado').size().to_dict()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📅 Reservadas", reservas_por_estado.get("RESERVADA", 0))
            with col2:
                st.metric("✅ Asistidas", reservas_por_estado.get("ASISTIO", 0))
            with col3:
                st.metric("❌ Perdidas", reservas_por_estado.get("NO_ASISTIO", 0))
            with col4:
                st.metric("🚫 Canceladas", reservas_por_estado.get("CANCELADA", 0))
            
            # Mostrar reservas en cards
            for _, reserva in df_reservas.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        st.markdown(f"**🏃‍♀️ {reserva['clase_nombre']}**")
                        st.caption(f"🏷️ {reserva.get('categoria', 'Sin categoría')}")
                        
                        # Fecha y día
                        fecha_clase = pd.to_datetime(reserva['fecha_clase']).strftime('%d/%m/%Y')
                        st.write(f"📅 **{fecha_clase}** ({reserva['dia_semana']})")
                    
                    with col2:
                        st.write(f"⏰ **{reserva['horario_display']}**")
                        
                        # Estado con colores
                        estado = reserva['estado']
                        if estado == "RESERVADA":
                            st.info("📅 Reservada")
                        elif estado == "ASISTIO":
                            st.success("✅ Asistida")
                        elif estado == "NO_ASISTIO":
                            st.error("❌ No asististe")
                        elif estado == "CANCELADA":
                            st.warning("🚫 Cancelada")
                        
                        # Notas si las hay
                        if reserva.get('notas'):
                            st.caption(f"📝 {reserva['notas']}")
                    
                    with col3:
                        # Botón de cancelar solo para reservas futuras
                        fecha_clase_dt = pd.to_datetime(reserva['fecha_clase']).date()
                        hoy = date.today()
                        
                        if estado == "RESERVADA" and fecha_clase_dt >= hoy:
                            # Verificar si se puede cancelar (ej: hasta 2 horas antes)
                            puede_cancelar = fecha_clase_dt > hoy or (
                                fecha_clase_dt == hoy and 
                                datetime.now().hour < pd.to_datetime(reserva['hora_inicio']).hour - 2
                            )
                            
                            if puede_cancelar:
                                if st.button("🚫 Cancelar", key=f"cancelar_{reserva['id']}", use_container_width=True):
                                    confirmar_key = f"confirmar_cancelar_{reserva['id']}"
                                    if st.session_state.get(confirmar_key):
                                        success = clases_service.cancelar_reserva(reserva['id'], participante_id)
                                        if success:
                                            st.success("✅ Reserva cancelada")
                                            del st.session_state[confirmar_key]
                                            st.rerun()
                                        else:
                                            st.error("❌ Error cancelando")
                                    else:
                                        st.session_state[confirmar_key] = True
                                        st.warning("⚠️ Confirmar")
                            else:
                                st.caption("🕒 No se puede cancelar")
                        else:
                            st.caption("📋 Finalizada")
        
        # Resumen mensual
        with st.expander("📊 Mi Resumen Mensual"):
            resumen = clases_service.get_resumen_mensual_participante(participante_id)
            
            if resumen:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("🎯 Clases Disponibles", resumen.get("clases_disponibles", 0))
                    st.metric("✅ Asistencias", reumen.get("asistencias", 0))
                
                with col2:
                    st.metric("⚡ Clases Restantes", resumen.get("clases_restantes", 0))
                    st.metric("❌ No Asistencias", resumen.get("no_asistencias", 0))
                
                with col3:
                    st.metric("📅 Total Reservadas", resumen.get("total_reservadas", 0))
                    
                    porcentaje = resumen.get("porcentaje_asistencia", 0)
                    st.metric("📈 % Asistencia", f"{porcentaje}%")
                    
                    if porcentaje >= 80:
                        st.success("🏆 Excelente asistencia!")
                    elif porcentaje >= 60:
                        st.info("👍 Buena asistencia")
                    else:
                        st.warning("📈 Puedes mejorar")
    
    except Exception as e:
        st.error(f"❌ Error cargando tus reservas: {e}")

# =========================
# TAB 3: RESERVAR CLASES
# =========================   
def mostrar_reservar_clases(clases_service, session_state):
    """Reservar clases - VERSIÓN CORREGIDA"""
    st.header("📅 Reservar Clases")
    
    auth_id = session_state.user.get('id')
    
    if not auth_id or auth_id == "None":
        st.error("❌ No se pudo obtener tu identificador de usuario")
        return
    
    participante_id = get_participante_id_from_auth(clases_service.supabase, auth_id)
    
    if not participante_id:
        st.error("❌ No se pudo encontrar tu registro como participante")
        return
    
    try:  # ← ESTE TRY DEBE ESTAR AL INICIO DE LA FUNCIÓN
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
        
        # ... TODO TU CÓDIGO EXISTENTE HASTA AQUÍ ...
        
        if not clases_filtradas:
            st.warning("🔍 No hay clases que coincidan con los filtros aplicados")
            return
        
        # Mostrar clases disponibles
        st.markdown(f"#### 📋 {len(clases_filtradas)} clase(s) tras filtros")
        
        # Agrupar por día para mejor visualización
        clases_por_dia = {}
        for clase in clases_filtradas:
            fecha_clase = pd.to_datetime(clase["start"]).date()
            if fecha_clase not in clases_por_dia:
                clases_por_dia[fecha_clase] = []
            clases_por_dia[fecha_clase].append(clase)
        
        # Mostrar por días
        for fecha_dia, clases_del_dia in sorted(clases_por_dia.items()):
            dia_semana = pd.to_datetime(fecha_dia).strftime('%A')
            fecha_str = fecha_dia.strftime('%d/%m/%Y')
            
            st.markdown(f"### 📅 {dia_semana} {fecha_str}")
            
            # Ordenar clases del día por hora
            clases_del_dia_ordenadas = sorted(clases_del_dia, key=lambda x: pd.to_datetime(x["start"]))
            
            for clase in clases_del_dia_ordenadas:
                props = clase.get("extendedProps", {})
                
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        st.markdown(f"**🏃‍♀️ {clase['title']}**")
                        st.caption(f"🏷️ {props.get('categoria', 'Sin categoría')}")
                        
                        # Horario
                        hora_inicio = pd.to_datetime(clase["start"]).strftime('%H:%M')
                        hora_fin = pd.to_datetime(clase["end"]).strftime('%H:%M')
                        st.write(f"⏰ **{hora_inicio} - {hora_fin}**")
                    
                    with col2:
                        # Disponibilidad
                        cupos_libres = props.get("cupos_libres", 0)
                        capacidad_maxima = props.get("capacidad_maxima", 0)
                        
                        if cupos_libres > 5:
                            st.success(f"✅ {cupos_libres} cupos disponibles")
                        elif cupos_libres > 0:
                            st.warning(f"⚠️ Solo {cupos_libres} cupos")
                        else:
                            st.error("❌ Sin cupos")
                        
                        st.caption(f"👥 Capacidad total: {capacidad_maxima}")
                        
                        # Ocupación visual
                        if capacidad_maxima > 0:
                            ocupacion = (capacidad_maxima - cupos_libres) / capacidad_maxima
                            st.progress(ocupacion, f"Ocupación: {int(ocupacion * 100)}%")
                    
                    with col3:
                        # Botón de reservar
                        puede_reservar = cupos_libres > 0 and props.get("disponible", False)
                        
                        if puede_reservar:
                            if st.button(
                                "📅 Reservar", 
                                key=f"reservar_{clase['horario_id']}_{props['fecha_clase']}", 
                                type="primary",
                                use_container_width=True
                            ):
                                # Realizar reserva
                                success, mensaje = clases_service.crear_reserva(
                                    participante_id, 
                                    clase["horario_id"], 
                                    pd.to_datetime(props["fecha_clase"]).date()
                                )
                                
                                if success:
                                    st.success("✅ ¡Reserva realizada!")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(f"❌ {mensaje}")
                        else:
                            st.error("❌ No disponible")
        
        # Consejos para reservar
        with st.expander("💡 Consejos para Reservar Clases"):
            st.markdown("""
            **🎯 Recomendaciones:**
            - Reserva con anticipación para asegurar tu cupo
            - Cancela con al menos 2 horas de antelación si no puedes asistir
            - Llega 5-10 minutos antes de la clase
            - Trae ropa cómoda y una toalla
            
            **📱 Gestión de Reservas:**
            - Puedes ver todas tus reservas en la pestaña "Mis Clases"
            - Las cancelaciones liberan cupos para otros participantes
            - Tu asistencia se registra automáticamente
            
            **📈 Límites Mensuales:**
            - Tu suscripción se renueva automáticamente cada mes
            - Las clases no utilizadas no se acumulan
            - Contacta con recepción para cambios de suscripción
            """)
    
    except Exception as e:  # ← ESTE EXCEPT AHORA TIENE SU TRY CORRESPONDIENTE
        st.error(f"❌ Error cargando clases disponibles: {e}")

# =========================
# TAB 4: MI PERFIL
# =========================
def mostrar_mi_perfil(participantes_service, clases_service, session_state):
    """Mi perfil - VERSIÓN CORREGIDA"""
    st.header("👤 Mi Perfil")
    
    auth_id = session_state.user.get('id')
    
    if not auth_id or auth_id == "None":
        st.error("❌ No se pudo obtener tu identificador de usuario")
        return
    
    participante_id = get_participante_id_from_auth(participantes_service.supabase, auth_id)
    
    if not participante_id:
        st.error("❌ No se pudo encontrar tu registro como participante")
        return
        
    try:
        participante_res = participantes_service.supabase.table("participantes").select("""
            id, nombre, apellidos, email, telefono, nif, fecha_nacimiento, sexo,
            empresa:empresas(nombre, tipo_empresa)
        """).eq("id", participante_id).execute()
        
        # Layout en dos columnas
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Sección de Avatar
            st.markdown("### 📸 Foto de Perfil")
            
            # Mostrar avatar actual
            avatar = participantes_service.get_avatar_participante(participante_id)
            
            if avatar and avatar.get("archivo_url"):
                st.image(
                    avatar["archivo_url"],
                    caption="Tu foto actual",
                    width=200
                )
                
                # Información del archivo
                st.caption(f"📁 {avatar.get('archivo_nombre', 'Sin nombre')}")
                if avatar.get("tamaño_bytes"):
                    tamaño_mb = avatar["tamaño_bytes"] / (1024 * 1024)
                    st.caption(f"📏 {tamaño_mb:.2f} MB")
                
                # Botón para cambiar foto
                if st.button("🔄 Cambiar Foto", use_container_width=True):
                    st.session_state["cambiar_avatar"] = True
                
                # Botón para eliminar foto
                if st.button("🗑️ Eliminar Foto", use_container_width=True):
                    if st.session_state.get("confirmar_eliminar_avatar"):
                        success = participantes_service.eliminar_avatar(participante_id)
                        if success:
                            st.success("✅ Foto eliminada")
                            del st.session_state["confirmar_eliminar_avatar"]
                            st.rerun()
                    else:
                        st.session_state["confirmar_eliminar_avatar"] = True
                        st.warning("⚠️ Confirmar eliminación")
            else:
                st.info("📷 Sin foto de perfil")
                st.image(
                    "https://via.placeholder.com/200x200/CCCCCC/FFFFFF?text=Sin+Foto",
                    width=200
                )
                st.session_state["cambiar_avatar"] = True
            
            # Subir nueva foto
            if st.session_state.get("cambiar_avatar", False):
                st.markdown("#### 📤 Subir Nueva Foto")
                
                avatar_file = st.file_uploader(
                    "Seleccionar imagen",
                    type=["jpg", "jpeg", "png"],
                    key="upload_avatar_perfil",
                    help="JPG o PNG, máximo 2MB"
                )
                
                if avatar_file is not None:
                    file_size_mb = avatar_file.size / (1024 * 1024)
                    
                    # Previsualización
                    st.image(avatar_file, caption="Vista previa", width=150)
                    
                    # Información del archivo
                    col_info1, col_info2 = st.columns(2)
                    with col_info1:
                        st.write(f"**📁 Archivo:** {avatar_file.name}")
                    with col_info2:
                        color = "🔴" if file_size_mb > 2 else "🟢"
                        st.write(f"{color} **Tamaño:** {file_size_mb:.2f} MB")
                    
                    if file_size_mb > 2:
                        st.error("❌ Archivo muy grande. Máximo 2MB.")
                    else:
                        if st.button(
                            "📤 Subir Avatar", 
                            key="btn_upload_avatar_perfil", 
                            type="primary",
                            use_container_width=True
                        ):
                            success = participantes_service.subir_avatar(participante_id, avatar_file)
                            if success:
                                st.success("✅ Avatar subido correctamente")
                                st.session_state["cambiar_avatar"] = False
                                st.rerun()
                            else:
                                st.error("❌ Error subiendo avatar")
        
        with col2:
            # Sección de Información Personal
            st.markdown("### 📋 Información Personal")
            
            col_info1, col_info2 = st.columns(2)
            
            with col_info1:
                st.markdown(f"**👤 Nombre:** {participante.get('nombre', 'N/A')}")
                st.markdown(f"**👥 Apellidos:** {participante.get('apellidos', 'N/A')}")
                st.markdown(f"**📧 Email:** {participante.get('email', 'N/A')}")
                st.markdown(f"**📞 Teléfono:** {participante.get('telefono', 'No disponible')}")
            
            with col_info2:
                st.markdown(f"**🆔 Documento:** {participante.get('nif', 'No disponible')}")
                
                if participante.get('fecha_nacimiento'):
                    fecha_nac = pd.to_datetime(participante['fecha_nacimiento']).strftime('%d/%m/%Y')
                    st.markdown(f"**🎂 Fecha Nacimiento:** {fecha_nac}")
                
                if participante.get('sexo'):
                    sexo_display = {"M": "Masculino", "F": "Femenino", "O": "Otro"}.get(participante['sexo'], participante['sexo'])
                    st.markdown(f"**⚧ Sexo:** {sexo_display}")
                
                # Información de empresa
                if participante.get('empresa'):
                    st.markdown(f"**🏢 Empresa:** {participante['empresa']['nombre']}")
            
            # Sección de Estado de Suscripciones
            st.markdown("### 📊 Estado de Suscripciones")
            
            # Suscripción FUNDAE (grupos)
            try:
                grupos_participante = participantes_service.get_grupos_de_participante(participante_id)
                num_grupos = len(grupos_participante) if not grupos_participante.empty else 0
                
                col_fundae, col_clases = st.columns(2)
                
                with col_fundae:
                    st.metric("🎓 Grupos FUNDAE", num_grupos)
                    if num_grupos > 0:
                        activos = len(grupos_participante[grupos_participante.get('fecha_fin', pd.NaType) >= pd.Timestamp.now().date()])
                        st.caption(f"Activos: {activos}")
                
                with col_clases:
                    # Suscripción de clases
                    suscripcion_clases = clases_service.get_suscripcion_participante(participante_id)
                    
                    if suscripcion_clases and suscripcion_clases.get("activa"):
                        clases_disponibles = suscripcion_clases.get("clases_mensuales", 0) - suscripcion_clases.get("clases_usadas_mes", 0)
                        st.metric("🏃‍♀️ Clases Disponibles", clases_disponibles)
                        st.caption(f"Total mensuales: {suscripcion_clases.get('clases_mensuales', 0)}")
                    else:
                        st.metric("🏃‍♀️ Clases Disponibles", 0)
                        st.caption("Sin suscripción activa")
            
            except Exception as e:
                st.error(f"❌ Error cargando estado de suscripciones: {e}")
            
            # Estadísticas de Actividad
            st.markdown("### 📈 Estadísticas de Actividad")
            
            try:
                # Resumen mensual de clases
                resumen_clases = clases_service.get_resumen_mensual_participante(participante_id)
                
                if resumen_clases:
                    col_stats1, col_stats2 = st.columns(2)
                    
                    with col_stats1:
                        st.metric("✅ Asistencias Este Mes", resumen_clases.get("asistencias", 0))
                        st.metric("📅 Total Reservadas", resumen_clases.get("total_reservadas", 0))
                    
                    with col_stats2:
                        st.metric("❌ No Asistencias", resumen_clases.get("no_asistencias", 0))
                        porcentaje = resumen_clases.get("porcentaje_asistencia", 0)
                        st.metric("📊 % Asistencia", f"{porcentaje}%")
                    
                    # Barra de progreso de asistencia
                    if porcentaje > 0:
                        if porcentaje >= 80:
                            st.success(f"🏆 Excelente asistencia: {porcentaje}%")
                        elif porcentaje >= 60:
                            st.info(f"👍 Buena asistencia: {porcentaje}%")
                        else:
                            st.warning(f"📈 Puedes mejorar: {porcentaje}%")
                        
                        st.progress(porcentaje / 100, f"Asistencia mensual")
                
                else:
                    st.info("📊 No hay estadísticas de clases disponibles")
            
            except Exception as e:
                st.error(f"❌ Error cargando estadísticas: {e}")
            
            # Consejos y Recomendaciones
            with st.expander("💡 Consejos para Aprovechar al Máximo"):
                st.markdown("""
                **🎯 Para Formación FUNDAE:**
                - Asiste puntualmente a todas las sesiones
                - Participa activamente en las actividades
                - Completa las evaluaciones requeridas
                - Consulta con tus tutores ante cualquier duda
                
                **🏃‍♀️ Para Clases:**
                - Reserva con anticipación para asegurar tu cupo
                - Cancela con al menos 2 horas de antelación
                - Llega 5-10 minutos antes de la clase
                - Mantén una asistencia regular para mejores resultados
                
                **👤 Perfil:**
                - Mantén tu información actualizada
                - Sube una foto de perfil para personalizar tu experiencia
                - Revisa regularmente tu progreso y estadísticas
                """)

    except Exception as e:
        st.error(f"❌ Error cargando información del perfil: {e}")

# =========================
# MAIN FUNCTION
# =========================
def main(supabase, session_state):
    st.title("🎓 Área del Alumno")
    
    # ✅ Verificar acceso con supabase
    if not verificar_acceso_alumno(session_state, supabase):
        return
    
    # Cargar servicios
    participantes_service = get_participantes_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    clases_service = get_clases_service(supabase, session_state)
    
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
    st.error("Este archivo debe ser ejecutado desde main.py")
