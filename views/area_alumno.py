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
    """Muestra los grupos FUNDAE del participante - VERSIÓN MEJORADA."""
    st.header("📚 Mis Grupos FUNDAE")
    
    # Obtener participante_id de forma robusta
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
        # Obtener grupos del participante
        df_grupos = participantes_service.get_grupos_de_participante(participante_id)
        
        if df_grupos.empty:
            st.info("🔭 No estás inscrito en ningún grupo FUNDAE")
            
            with st.expander("ℹ️ ¿Qué son los grupos FUNDAE?", expanded=True):
                st.markdown("""
                **🎓 Formación Bonificada FUNDAE**
                
                Los grupos FUNDAE son cursos de formación gratuita financiados por la 
                Fundación Estatal para la Formación en el Empleo.
                
                **Características:**
                - ✅ Formación 100% gratuita
                - ✅ Certificación oficial
                - ✅ Horarios establecidos
                - ✅ Seguimiento personalizado
                
                **Para inscribirte:** Contacta con tu empresa o el departamento de formación.
                """)
            return
        
        st.success(f"🎯 Estás inscrito en {len(df_grupos)} grupo(s)")
        
        # Mostrar cada grupo como una tarjeta expandible
        for idx, grupo in df_grupos.iterrows():
            codigo_grupo = grupo.get('codigo_grupo', 'Sin código')
            accion_nombre = grupo.get('accion_nombre', 'Sin acción formativa')
            
            # Determinar estado del grupo
            fecha_inicio = grupo.get("fecha_inicio")
            fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
            estado_emoji = "📅"
            estado_texto = "Programado"
            
            if fecha_fin:
                try:
                    hoy = pd.Timestamp.now().date()
                    fecha_fin_dt = pd.to_datetime(fecha_fin).date()
                    
                    if fecha_fin_dt < hoy:
                        estado_emoji = "✅"
                        estado_texto = "Finalizado"
                    elif fecha_inicio:
                        fecha_inicio_dt = pd.to_datetime(fecha_inicio).date()
                        if fecha_inicio_dt <= hoy <= fecha_fin_dt:
                            estado_emoji = "🟡"
                            estado_texto = "En curso"
                        else:
                            estado_emoji = "⏳"
                            estado_texto = "Próximamente"
                except:
                    pass
            
            # Título del expander con información clave
            titulo_expander = f"{estado_emoji} {codigo_grupo} - {accion_nombre} ({estado_texto})"
            
            with st.expander(titulo_expander, expanded=(idx == 0 and estado_texto == "En curso")):
                # Información organizada en tabs
                tab_info, tab_horarios = st.tabs(["📋 Información General", "⏰ Horarios"])
                
                with tab_info:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**📖 Datos del Curso**")
                        st.write(f"**Código:** {codigo_grupo}")
                        st.write(f"**Acción Formativa:** {accion_nombre}")
                        
                        accion_horas = grupo.get('accion_horas', 0)
                        if accion_horas and accion_horas > 0:
                            st.write(f"**Duración:** {accion_horas} horas")
                        
                        modalidad = grupo.get('modalidad')
                        if modalidad:
                            st.write(f"**Modalidad:** {modalidad}")
                        
                        if modalidad and modalidad.upper() in ['PRESENCIAL', 'MIXTA']:
                            # Obtener detalles del grupo para horarios
                            grupo_id = grupo.get('grupo_id', grupo.get('id'))
                            
                            try:
                                if hasattr(grupos_service, 'get_grupo_completo'):
                                    grupo_detalle = grupos_service.get_grupo_completo(grupo_id)
                                else:
                                    grupo_res = grupos_service.supabase.table("grupos").select("*").eq("id", grupo_id).execute()
                                    grupo_detalle = grupo_res.data[0] if grupo_res.data else None
                                
                                if grupo_detalle and grupo_detalle.get('horarios'):
                                    st.markdown("---")
                                    st.markdown("**📅 Horarios**")
                                    
                                    horarios_texto = grupo_detalle['horarios']
                                    
                                    if isinstance(horarios_texto, str):
                                        lineas = horarios_texto.strip().split('\n')
                                        for linea in lineas:
                                            if linea.strip():
                                                st.caption(f"• {linea.strip()}")
                                    else:
                                        st.caption(horarios_texto)
                            except Exception:
                                pass
                        
                        lugar_imparticion = grupo.get('lugar_imparticion')
                        if lugar_imparticion:
                            st.write(f"**Lugar:** {lugar_imparticion}")
                    
                    with col2:
                        st.markdown("**📅 Fechas**")
                        
                        if fecha_inicio:
                            try:
                                inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')
                                st.write(f"**Inicio:** {inicio_str}")
                            except:
                                st.write(f"**Inicio:** {fecha_inicio}")
                        
                        if fecha_fin:
                            try:
                                fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                                st.write(f"**Fin:** {fin_str}")
                            except:
                                st.write(f"**Fin:** {fecha_fin}")
                        
                        # Fecha de inscripción
                        fecha_asignacion = grupo.get('fecha_asignacion')
                        if fecha_asignacion:
                            try:
                                asignacion_str = pd.to_datetime(fecha_asignacion).strftime('%d/%m/%Y')
                                st.write(f"**Inscrito el:** {asignacion_str}")
                            except:
                                pass
                        
                        # Estado visual
                        if estado_texto == "Finalizado":
                            st.success(f"{estado_emoji} {estado_texto}")
                        elif estado_texto == "En curso":
                            st.info(f"{estado_emoji} {estado_texto}")
                        elif estado_texto == "Próximamente":
                            st.warning(f"{estado_emoji} {estado_texto}")
                        else:
                            st.write(f"{estado_emoji} {estado_texto}")
            
                        
                        # Observaciones si existen
                        if grupo_detalle and grupo_detalle.get('observaciones'):
                            observaciones = grupo_detalle['observaciones']
                            if observaciones.strip():
                                st.markdown("---")
                                st.markdown("**📝 Observaciones**")
                                st.info(observaciones)
                    

        # Información adicional al final
        st.divider()
        
        with st.expander("ℹ️ Información sobre Formación FUNDAE"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **🎓 ¿Qué es FUNDAE?**
                
                FUNDAE (Fundación Estatal para la Formación en el Empleo) es la entidad 
                que gestiona la formación bonificada para trabajadores en España.
                
                **Características:**
                - Formación 100% gratuita
                - Certificación oficial
                - Compatible con tu trabajo
                - Mejora tu empleabilidad
                """)
            
            with col2:
                st.markdown("""
                **📋 Tus Responsabilidades**
                
                Para aprovechar al máximo la formación:
                
                - ✅ Asistir puntualmente a las sesiones
                - ✅ Participar activamente
                - ✅ Completar las evaluaciones
                - ✅ Informar si no puedes asistir
                
                **📜 Al finalizar:** Recibirás tu diploma oficial
                """)
    
    except Exception as e:
        st.error(f"❌ Error cargando tus grupos FUNDAE: {e}")
        if st.checkbox("Mostrar detalles técnicos del error"):
            st.code(str(e))

# =========================
# TAB 2: MIS CLASES RESERVADAS
# =========================
def mostrar_mis_clases_reservadas(clases_service, session_state):
    """Muestra las clases reservadas del participante con avatares de otros alumnos"""
    st.header("🏃‍♀️ Mis Clases Reservadas")
    
    participante_id = getattr(session_state, 'participante_id', None)
    if not participante_id:
        st.error("No se pudo identificar tu registro")
        return
        
    try:
        # Verificar suscripción primero
        suscripcion = clases_service.get_suscripcion_participante(participante_id)
        
        if not suscripcion or not suscripcion.get("activa"):
            st.warning("No tienes una suscripción activa de clases")
            return
        
        # Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎯 Clases Mensuales", suscripcion.get("clases_mensuales", 0))
        with col2:
            st.metric("✅ Usadas", suscripcion.get("clases_usadas_mes", 0))
        with col3:
            disponibles = suscripcion.get("clases_mensuales", 0) - suscripcion.get("clases_usadas_mes", 0)
            st.metric("⚡ Disponibles", disponibles)
        
        st.divider()
        
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📅 Ver reservas desde:**")
            fecha_inicio = st.date_input(
                "Fecha inicio",
                value=date.today(),
                key="mis_reservas_inicio",
                label_visibility="collapsed"
            )
        with col2:
            st.markdown("**📅 Hasta:**")
            fecha_fin = st.date_input(
                "Fecha fin",
                value=date.today() + timedelta(days=30),
                key="mis_reservas_fin",
                label_visibility="collapsed"
            )
        
        # Obtener reservas
        df_reservas = clases_service.get_reservas_participante(participante_id, fecha_inicio, fecha_fin)
        
        if df_reservas.empty:
            st.info("No tienes clases reservadas en este período")
            return
        
        hoy = date.today()
        reservas_futuras = df_reservas[df_reservas['fecha_clase'] >= hoy]
        reservas_pasadas = df_reservas[df_reservas['fecha_clase'] < hoy]
        
        # Próximas clases
        if not reservas_futuras.empty:
            st.markdown("#### 🔜 Próximas Clases")
            for _, row in reservas_futuras.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    
                    with col1:
                        st.markdown(f"**🏃‍♀️ {row['clase_nombre']}**")
                        
                        fecha_display = pd.to_datetime(row['fecha_clase']).strftime('%d/%m/%Y')
                        st.markdown(f"**📅 {fecha_display}** | **⏰ {row['horario_display']}**")
                        
                        # Avatares de otros alumnos - CORREGIDO
                        try:
                            fecha_clase_dt = date.fromisoformat(str(row["fecha_clase"]))
                            avatares = clases_service.get_avatares_reserva(
                                row["horario_id"], 
                                fecha_clase_dt
                            )
                            
                            if avatares and len(avatares) > 0:
                                st.caption(f"👥 {len(avatares)} participantes:")
                                avatar_html = " ".join([
                                    f'<img src="{url}" style="width:32px; height:32px; border-radius:50%; margin-right:4px; object-fit:cover; border: 2px solid #ddd;" />'
                                    for url in avatares[:8]
                                ])
                                st.markdown(avatar_html, unsafe_allow_html=True)
                        
                        except Exception as e:
                            pass
                    
                    with col2:
                        st.write(f"📊 Estado: {row['estado']}")
                    
                    with col3:
                        if row["estado"] == "RESERVADA":
                            if st.button("❌ Cancelar", key=f"cancelar_{row['id']}"):
                                ok = clases_service.cancelar_reserva(row["id"], participante_id)
                                if ok:
                                    st.success("Reserva cancelada")
                                    st.rerun()
                                else:
                                    st.error("No puedes cancelar (menos de 2h antes o error)")
        
        # Historial
        if not reservas_pasadas.empty:
            with st.expander(f"📜 Historial ({len(reservas_pasadas)} clases)"):
                st.dataframe(
                    reservas_pasadas[['clase_nombre', 'fecha_clase', 'horario_display', 'estado']],
                    use_container_width=True,
                    hide_index=True
                )
    
    except Exception as e:
        st.error(f"Error cargando tus reservas: {e}")


# =========================
# TAB 3: RESERVAR CLASES
# =========================   
def mostrar_reservar_clases(clases_service, session_state):
    """Reservar clases mostrando también los avatares de alumnos que ya reservaron"""
    st.header("📅 Reservar Clases")
    
    participante_id = getattr(session_state, 'participante_id', None)
    if not participante_id:
        st.error("No se pudo identificar tu registro como participante")
        return
    
    try:
        suscripcion = clases_service.get_suscripcion_participante(participante_id)
        if not suscripcion or not suscripcion.get("activa"):
            st.warning("No tienes una suscripción activa")
            return
        
        # Métricas
        col1, col2, col3 = st.columns(3)
        clases_disponibles = suscripcion.get("clases_mensuales", 0) - suscripcion.get("clases_usadas_mes", 0)
        with col1: st.metric("⚡ Disponibles", clases_disponibles)
        with col2: st.metric("✅ Usadas", suscripcion.get("clases_usadas_mes", 0))
        with col3: st.metric("🎯 Mensuales", suscripcion.get("clases_mensuales", 0))
        
        if clases_disponibles <= 0:
            st.error("Has agotado tus clases mensuales")
            return
        
        st.divider()
        
        # Periodo
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio_busqueda = st.date_input("Ver clases desde", value=date.today(), min_value=date.today(), key="buscar_clases_inicio")
        with col2:
            fecha_fin_busqueda = st.date_input("Hasta", value=date.today() + timedelta(days=14), min_value=date.today(), key="buscar_clases_fin")
        
        # Obtener clases
        clases_disponibles_lista = clases_service.get_clases_disponibles_participante(participante_id, fecha_inicio_busqueda, fecha_fin_busqueda)
        
        if not clases_disponibles_lista:
            st.info("No hay clases disponibles en el período seleccionado")
            return
        
        st.markdown("### 📅 Clases Disponibles para Reservar")
        
        for clase in clases_disponibles_lista:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**{clase['title']}**")
                    st.caption(f"Categoría: {clase['extendedProps'].get('categoria', 'N/A')}")
                    
                    # Avatares de quienes ya reservaron - CORREGIDO
                    try:
                        fecha_clase_dt = pd.to_datetime(clase['extendedProps']['fecha_clase']).date()
                        avatares = clases_service.get_avatares_reserva(
                            clase["horario_id"], 
                            fecha_clase_dt
                        )
                        
                        if avatares and len(avatares) > 0:
                            st.caption(f"👥 {len(avatares)} participantes ya inscritos:")
                            # Mostrar avatares en línea
                            avatar_html = " ".join([
                                f'<img src="{url}" style="width:32px; height:32px; border-radius:50%; margin-right:4px; object-fit:cover; border: 2px solid #ddd;" title="Participante" />'
                                for url in avatares[:5]  # Máximo 5 avatares
                            ])
                            if len(avatares) > 5:
                                avatar_html += f'<span style="margin-left:8px; color:#666;">+{len(avatares)-5} más</span>'
                            
                            st.markdown(avatar_html, unsafe_allow_html=True)
                        else:
                            st.caption("👥 Sé el primero en reservar")
                    
                    except Exception as e:
                        st.caption("👥 Información de participantes no disponible")
                
                with col2:
                    fecha_clase = clase['extendedProps']['fecha_clase']
                    hora_inicio = clase['start'].split('T')[1][:5]
                    hora_fin = clase['end'].split('T')[1][:5]
                    st.write(f"📅 {pd.to_datetime(fecha_clase).strftime('%d/%m/%Y')}")
                    st.write(f"⏰ {hora_inicio} - {hora_fin}")
                
                with col3:
                    cupos_libres = clase['extendedProps'].get('cupos_libres', 0)
                    st.metric("🎯 Cupos", cupos_libres)
                    
                    reserva_key = f"reservar_{clase['id']}"
                    if st.button("📝 Reservar", key=reserva_key, disabled=cupos_libres <= 0, use_container_width=True):
                        fecha_clase_obj = pd.to_datetime(fecha_clase).date()
                        success, mensaje = clases_service.crear_reserva(participante_id, clase['horario_id'], fecha_clase_obj)
                        if success:
                            st.success("¡Reserva realizada correctamente!")
                            st.rerun()
                        else:
                            st.error(f"Error en la reserva: {mensaje}")

    except Exception as e:
        st.error(f"Error cargando clases: {e}")

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

    except Exception as e:
        st.error(f"❌ Error cargando información del perfil: {e}")

def mostrar_mis_diplomas(participantes_service, session_state):
    """Muestra los diplomas del participante desde el bucket con filtros"""
    st.header("📜 Mis Diplomas")
    
    participante_id = getattr(session_state, 'participante_id', None)
    if not participante_id:
        st.error("No se pudo identificar tu registro como participante")
        return
    
    try:
        diplomas_res = participantes_service.supabase.table("diplomas").select("""
            id, archivo_nombre, url, fecha_subida,
            grupo:grupos(codigo_grupo, accion_formativa:acciones_formativas(nombre))
        """).eq("participante_id", participante_id).order("fecha_subida", desc=True).execute()
        
        if not diplomas_res.data:
            st.info("📭 No tienes diplomas disponibles aún")
            return
        
        diplomas = diplomas_res.data

    except Exception as e:
        st.error(f"❌ Error cargando diplomas: {e}")
        return   # 👈 muy importante para no seguir si falla la consulta

    # =========================
    # FILTROS AVANZADOS
    # =========================
    st.markdown("### 🔍 Filtros de búsqueda")
    col1, col2, col3 = st.columns(3)

    with col1:
        filtro_nombre = st.text_input("🔎 Nombre contiene")
    with col2:
        filtro_fecha = st.date_input("📅 Emitido desde", value=None)
    with col3:
        filtro_curso = st.text_input("📘 Curso contiene")

    # Aplicar filtros
    if filtro_nombre:
        diplomas = [d for d in diplomas if filtro_nombre.lower() in d.get("archivo_nombre", "").lower()]
    if filtro_fecha:
        diplomas = [d for d in diplomas if d.get("fecha_subida") and pd.to_datetime(d["fecha_subida"]).date() >= filtro_fecha]
    if filtro_curso:
        diplomas = [
            d for d in diplomas 
            if d.get("grupo") and d["grupo"].get("accion_formativa") and filtro_curso.lower() in d["grupo"]["accion_formativa"]["nombre"].lower()
        ]

    # =========================
    # LISTADO DE DIPLOMAS
    # =========================
    for diploma in diplomas:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                nombre_archivo = diploma.get("archivo_nombre", "Diploma")
                st.markdown(f"**📜 {nombre_archivo}**")
                
                if diploma.get("grupo"):
                    grupo = diploma["grupo"]
                    st.caption(f"Grupo: {grupo.get('codigo_grupo','')}")
                    if grupo.get("accion_formativa"):
                        st.caption(f"Curso: {grupo['accion_formativa'].get('nombre','')}")
            
            with col2:
                if diploma.get("fecha_subida"):
                    fecha = pd.to_datetime(diploma["fecha_subida"]).strftime("%d/%m/%Y")
                    st.write(f"📅 Emitido: {fecha}")
            
            with col3:
                if diploma.get("url"):
                    st.link_button("📥 Descargar", diploma["url"], use_container_width=True)
                else:
                    st.button("Sin archivo", disabled=True, use_container_width=True)


# =========================
# MAIN FUNCTION
# =========================
def render(supabase, session_state):
    st.title("🎓 Área del Alumno")
    
    # Cargar datos del participante si no existen
    if not hasattr(session_state, "participante_nombre"):
        participantes_service = get_participantes_service(supabase, session_state)
        participante_id = session_state.participante_id
        participante_res = participantes_service.supabase.table("participantes").select("nombre").eq("id", participante_id).execute()
        if participante_res.data:
            session_state.participante_nombre = participante_res.data[0]["nombre"]
    
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
    
    # Mostrar información del usuario
    st.caption(
        f"👤 Bienvenido/a: {session_state.get('participante_nombre', 'Usuario')} "
        f"| 📧 {session_state.user.get('email', 'N/A')}"
    )
    
    # Tabs principales
    tabs = st.tabs([
        "📚 Mis Grupos FUNDAE",
        "🏃‍♀️ Mis Clases", 
        "📅 Reservar Clases",
        "👤 Mi Perfil",
        "📜 Mis Diplomas"
    ])
    
    with tabs[0]:
        mostrar_mis_grupos_fundae(grupos_service, participantes_service, session_state)
    
    with tabs[1]:
        mostrar_mis_clases_reservadas(clases_service, session_state)
    
    with tabs[2]:
        mostrar_reservar_clases(clases_service, session_state)
    
    with tabs[3]:
        mostrar_mi_perfil(participantes_service, clases_service, session_state)

    with tabs[4]:
        mostrar_mis_diplomas(participantes_service, session_state)

