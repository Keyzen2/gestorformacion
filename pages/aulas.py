import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_calendar import calendar
from services.aulas_service import get_aulas_service
from utils import export_excel

def mostrar_cronograma_interactivo(aulas_service, session_state):
    """Cronograma visual interactivo usando streamlit-calendar"""
    
    st.markdown("### 📅 Cronograma Interactivo de Aulas")
    
    # Controles superiores
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        fecha_inicio = st.date_input(
            "📅 Desde", 
            value=datetime.now().date(),
            key="cronograma_inicio"
        )
    
    with col2:
        fecha_fin = st.date_input(
            "📅 Hasta", 
            value=datetime.now().date() + timedelta(days=14),
            key="cronograma_fin"
        )
    
    with col3:
        vista_inicial = st.selectbox(
            "👁️ Vista inicial",
            ["dayGridMonth", "timeGridWeek", "timeGridDay", "listWeek"],
            index=1,
            key="cronograma_vista_inicial"
        )
    
    with col4:
        if st.button("🔄 Actualizar", key="cronograma_refresh"):
            st.rerun()
    
    # Filtros de aulas
    try:
        df_aulas = aulas_service.get_aulas_con_empresa()
        if not df_aulas.empty:
            aulas_disponibles = df_aulas['nombre'].tolist()
            aulas_seleccionadas = st.multiselect(
                "🏢 Filtrar por aulas específicas (vacío = todas)",
                aulas_disponibles,
                key="cronograma_filtro_aulas"
            )
            
            # Filtrar aulas si es necesario
            if aulas_seleccionadas:
                aulas_ids = df_aulas[df_aulas['nombre'].isin(aulas_seleccionadas)]['id'].tolist()
            else:
                aulas_ids = df_aulas['id'].tolist()
        else:
            st.warning("⚠️ No hay aulas disponibles")
            return
    except Exception as e:
        st.error(f"❌ Error cargando aulas: {e}")
        return
    
    # Obtener eventos para el cronograma
    try:
        eventos = aulas_service.get_eventos_cronograma(
            fecha_inicio.isoformat() + "T00:00:00Z",
            fecha_fin.isoformat() + "T23:59:59Z", 
            aulas_ids
        )
        
        # Debug: mostrar información de eventos
        st.write(f"**Debug:** Se encontraron {len(eventos)} eventos")
        if eventos:
            st.write("**Primer evento:**", eventos[0])
        else:
            st.info("No se encontraron eventos para mostrar en el cronograma")
        
        # Configuración simplificada del calendario
        calendar_options = {
            "initialView": "dayGridMonth",
            "headerToolbar": {
                "left": "prev,next",
                "center": "title",
                "right": "dayGridMonth,listWeek"
            },
            "height": 600
        }
        
        # CSS personalizado para el calendario
        calendar_css = """
        .fc-event-grupo { 
            border-left: 5px solid #28a745 !important;
            background-color: #d4edda !important;
            color: #155724 !important;
        }
        .fc-event-mantenimiento { 
            border-left: 5px solid #ffc107 !important;
            background-color: #fff3cd !important;
            color: #856404 !important;
        }
        .fc-event-evento { 
            border-left: 5px solid #17a2b8 !important;
            background-color: #d1ecf1 !important;
            color: #0c5460 !important;
        }
        .fc-event-bloqueada { 
            border-left: 5px solid #dc3545 !important;
            background-color: #f8d7da !important;
            color: #721c24 !important;
        }
        .fc-toolbar-title {
            font-size: 1.2em !important;
            font-weight: 600 !important;
        }
        .fc-button-primary {
            background-color: #0066cc !important;
            border-color: #0066cc !important;
        }
        """
        
        # Renderizar calendario
        try:
            calendar_result = calendar(
                events=eventos,
                options=calendar_options,
                custom_css=calendar_css,
                key="aulas_calendar"
            )
            
            # Si llegamos aquí, el calendario se renderizó correctamente
            calendar_loaded = True
            
        except Exception as e:
            st.error(f"Error renderizando calendario: {e}")
            calendar_loaded = False
            calendar_result = None
        
        # Si el calendario no se cargó, mostrar vista alternativa
        if not calendar_loaded or calendar_result is None:
            col_warn1, col_warn2 = st.columns([3, 1])
            with col_warn1:
                st.warning("⚠️ El calendario no se pudo cargar. Mostrando vista alternativa.")
            with col_warn2:
                if st.button("🔄 Reintentar Calendario", key="retry_calendar"):
                    st.rerun()
            
            mostrar_vista_cronograma_alternativa(eventos, aulas_service)
            return
        
        # Mostrar información del evento seleccionado/clickeado si hay resultado del calendario
        if calendar_result and calendar_result.get("eventClick"):
            evento_info = calendar_result["eventClick"]["event"]
            st.markdown("---")
            st.markdown("### 📋 Detalle de Reserva Seleccionada")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.info(f"**🏢 Aula:** {evento_info['extendedProps']['aula_nombre']}")
                st.info(f"**📝 Título:** {evento_info['title'].split(': ', 1)[-1]}")
            
            with col2:
                fecha_inicio_evento = pd.to_datetime(evento_info['start']).strftime('%d/%m/%Y %H:%M')
                fecha_fin_evento = pd.to_datetime(evento_info['end']).strftime('%d/%m/%Y %H:%M')
                st.info(f"**📅 Inicio:** {fecha_inicio_evento}")
                st.info(f"**📅 Fin:** {fecha_fin_evento}")
            
            with col3:
                tipo_reserva = evento_info['extendedProps']['tipo_reserva']
                estado = evento_info['extendedProps']['estado']
                st.info(f"**🏷️ Tipo:** {tipo_reserva}")
                st.info(f"**📊 Estado:** {estado}")
            
            # Mostrar código de grupo si existe
            if evento_info['extendedProps'].get('grupo_codigo'):
                st.success(f"**📚 Grupo:** {evento_info['extendedProps']['grupo_codigo']}")
        
        # Información adicional sobre clicks en fechas
        if calendar_result.get("dateClick"):
            fecha_click = calendar_result["dateClick"]["date"]
            st.info(f"📅 Fecha seleccionada: {pd.to_datetime(fecha_click).strftime('%d/%m/%Y')}")
            
            # Aquí podrías añadir lógica para crear nueva reserva
            if st.button("➕ Crear reserva en esta fecha", key="crear_reserva_fecha"):
                st.session_state["crear_reserva_fecha"] = fecha_click
                st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error generando cronograma: {e}")
    
    # Leyenda de colores
    with st.expander("🎨 Leyenda de Colores"):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("**🟢 Formación (GRUPO)**")
            st.markdown("Grupos formativos programados")
        
        with col2:
            st.markdown("**🟡 Mantenimiento**")
            st.markdown("Tareas de mantenimiento")
        
        with col3:
            st.markdown("**🔵 Eventos**")
            st.markdown("Eventos especiales")
        
        with col4:
def mostrar_formulario_reserva_manual(aulas_service, session_state):
    """Formulario para crear reservas manuales"""
    
    st.markdown("#### ➕ Crear Nueva Reserva Manual")
    
    with st.form("nueva_reserva_manual"):
        # Cargar aulas disponibles
        df_aulas = aulas_service.get_aulas_con_empresa()
        if df_aulas.empty:
            st.warning("No hay aulas disponibles")
            return
        
        aulas_dict = dict(zip(df_aulas['nombre'], df_aulas['id']))
        
        col1, col2 = st.columns(2)
        
        with col1:
            aula_seleccionada = st.selectbox(
                "🏢 Seleccionar Aula",
                options=list(aulas_dict.keys()),
                key="reserva_aula"
            )
            
            titulo = st.text_input(
                "📝 Título de la Reserva",
                placeholder="Ej: Reunión de departamento",
                key="reserva_titulo"
            )
            
            tipo_reserva = st.selectbox(
                "🏷️ Tipo de Reserva",
                options=["EVENTO", "MANTENIMIENTO", "BLOQUEADA"],
                key="reserva_tipo"
            )
        
        with col2:
            fecha_reserva = st.date_input(
                "📅 Fecha",
                value=datetime.now().date(),
                min_value=datetime.now().date(),
                key="reserva_fecha"
            )
            
            col_hora1, col_hora2 = st.columns(2)
            with col_hora1:
                hora_inicio = st.time_input(
                    "🕐 Hora Inicio",
                    value=datetime.strptime("09:00", "%H:%M").time(),
                    key="reserva_hora_inicio"
                )
            
            with col_hora2:
                hora_fin = st.time_input(
                    "🕕 Hora Fin", 
                    value=datetime.strptime("10:00", "%H:%M").time(),
                    key="reserva_hora_fin"
                )
            
            responsable = st.text_input(
                "👤 Responsable",
                value=session_state.user.get("nombre", ""),
                key="reserva_responsable"
            )
        
        observaciones = st.text_area(
            "📝 Observaciones",
            placeholder="Comentarios adicionales...",
            key="reserva_observaciones"
        )
        
        # Botón de envío
        submitted = st.form_submit_button("✅ Crear Reserva", type="primary")
        
        if submitted:
            # Validaciones
            if not titulo.strip():
                st.error("El título es obligatorio")
                return
            
            if hora_inicio >= hora_fin:
                st.error("La hora de inicio debe ser anterior a la hora de fin")
                return
            
            # Crear timestamps
            fecha_inicio_dt = datetime.combine(fecha_reserva, hora_inicio)
            fecha_fin_dt = datetime.combine(fecha_reserva, hora_fin)
            
            fecha_inicio_iso = fecha_inicio_dt.isoformat() + "Z"
            fecha_fin_iso = fecha_fin_dt.isoformat() + "Z"
            
            aula_id = aulas_dict[aula_seleccionada]
            
            # Verificar disponibilidad con detalles de conflictos
            if not aulas_service.verificar_disponibilidad_aula(aula_id, fecha_inicio_iso, fecha_fin_iso):
                conflictos = aulas_service.obtener_conflictos_detallados(aula_id, fecha_inicio_iso, fecha_fin_iso)
                
                st.error("🚫 El aula no está disponible en ese horario")
                
                if conflictos:
                    st.markdown("**Conflictos detectados:**")
                    for conflicto in conflictos:
                        emoji_tipo = {
                            'GRUPO': '📚',
                            'MANTENIMIENTO': '🔧',
                            'EVENTO': '🎯',
                            'BLOQUEADA': '🚫'
                        }.get(conflicto['tipo_reserva'], '📅')
                        
                        grupo_info = f" (Grupo: {conflicto['grupo_codigo']})" if conflicto['grupo_codigo'] else ""
                        
                        st.warning(f"{emoji_tipo} **{conflicto['titulo']}**{grupo_info}\n"
                                 f"📅 {conflicto['fecha_inicio']} - {conflicto['fecha_fin']}")
                return
            
            # Crear reserva
            datos_reserva = {
                "aula_id": aula_id,
                "titulo": titulo.strip(),
                "fecha_inicio": fecha_inicio_iso,
                "fecha_fin": fecha_fin_iso,
                "tipo_reserva": tipo_reserva,
                "estado": "CONFIRMADA",
                "responsable": responsable.strip(),
                "observaciones": observaciones.strip()
            }
            
            success, reserva_id = aulas_service.crear_reserva(datos_reserva)
            
            if success:
                st.success("✅ Reserva creada correctamente")
                st.rerun()
            else:
                st.error("❌ Error al crear la reserva")

def mostrar_asignacion_grupos(aulas_service, session_state):
    """Permite asignar grupos formativos existentes a aulas"""
    
    st.markdown("#### 📚 Asignar Grupos Formativos a Aulas")
    
    try:
        # Obtener grupos sin aula asignada o con fechas próximas
        from services.grupos_service import get_grupos_service
        grupos_service = get_grupos_service(aulas_service.supabase, session_state)
        
        # Obtener grupos activos
        df_grupos = grupos_service.get_grupos_basicos()
        if df_grupos.empty:
            st.info("📋 No hay grupos formativos disponibles")
            return
        
        # Filtrar grupos que necesitan aula (estado ABIERTO o FINALIZAR)
        df_grupos_disponibles = df_grupos[
            df_grupos.get('estado', 'ABIERTO').isin(['ABIERTO', 'FINALIZAR'])
        ]
        
        if df_grupos_disponibles.empty:
            st.info("📋 No hay grupos que necesiten asignación de aula")
            return
        
        with st.form("asignar_grupo_aula"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Selector de grupo
                grupos_options = {}
                for _, grupo in df_grupos_disponibles.iterrows():
                    fecha_inicio = grupo.get('fecha_inicio', 'Sin fecha')
                    if isinstance(fecha_inicio, str) and fecha_inicio != 'Sin fecha':
                        try:
                            fecha_dt = pd.to_datetime(fecha_inicio)
                            fecha_str = fecha_dt.strftime('%d/%m/%Y')
                        except:
                            fecha_str = fecha_inicio
                    else:
                        fecha_str = 'Sin fecha'
                    
                    label = f"{grupo['codigo_grupo']} - {grupo.get('accion_nombre', 'Sin acción')} ({fecha_str})"
                    grupos_options[label] = grupo['id']
                
                grupo_seleccionado = st.selectbox(
                    "📚 Seleccionar Grupo",
                    options=list(grupos_options.keys()),
                    key="asignar_grupo"
                )
            
            with col2:
                # Selector de aula
                df_aulas = aulas_service.get_aulas_con_empresa()
                if df_aulas.empty:
                    st.warning("No hay aulas disponibles")
                    return
                
                aulas_options = {}
                for _, aula in df_aulas.iterrows():
                    label = f"{aula['nombre']} (Cap: {aula['capacidad_maxima']})"
                    aulas_options[label] = aula['id']
                
                aula_seleccionada = st.selectbox(
                    "🏢 Seleccionar Aula",
                    options=list(aulas_options.keys()),
                    key="asignar_aula"
                )
            
            # Opciones adicionales
            st.markdown("##### ⚙️ Configuración de Horario")
            
            col3, col4 = st.columns(2)
            with col3:
                hora_inicio_defecto = st.time_input(
                    "🕐 Hora Inicio (defecto)",
                    value=datetime.strptime("09:00", "%H:%M").time(),
                    key="grupo_hora_inicio"
                )
            
            with col4:
                hora_fin_defecto = st.time_input(
                    "🕕 Hora Fin (defecto)",
                    value=datetime.strptime("17:00", "%H:%M").time(),
                    key="grupo_hora_fin"
                )
            
            submitted = st.form_submit_button("🎯 Asignar Grupo a Aula", type="primary")
            
            if submitted:
                grupo_id = grupos_options[grupo_seleccionado]
                aula_id = aulas_options[aula_seleccionada]
                
                # Obtener datos del grupo seleccionado
                grupo_data = df_grupos_disponibles[df_grupos_disponibles['id'] == grupo_id].iloc[0]
                
                fecha_inicio = grupo_data.get('fecha_inicio')
                fecha_fin = grupo_data.get('fecha_fin_prevista') or grupo_data.get('fecha_inicio')
                
                if not fecha_inicio:
                    st.error("❌ El grupo seleccionado no tiene fecha de inicio")
                    return
                
                # Crear reserva automática para el grupo
                try:
                    fecha_inicio_dt = pd.to_datetime(fecha_inicio).date()
                    if isinstance(fecha_fin, str):
                        fecha_fin_dt = pd.to_datetime(fecha_fin).date()
                    else:
                        fecha_fin_dt = fecha_inicio_dt
                    
                    # Crear timestamps con las horas seleccionadas
                    inicio_completo = datetime.combine(fecha_inicio_dt, hora_inicio_defecto)
                    fin_completo = datetime.combine(fecha_fin_dt, hora_fin_defecto)
                    
                    datos_reserva = {
                        "aula_id": aula_id,
                        "grupo_id": grupo_id,
                        "titulo": f"Formación - {grupo_data['codigo_grupo']}",
                        "fecha_inicio": inicio_completo.isoformat() + "Z",
                        "fecha_fin": fin_completo.isoformat() + "Z",
                        "tipo_reserva": "GRUPO",
                        "estado": "CONFIRMADA",
                        "responsable": "Sistema automático"
                    }
                    
                    # Verificar disponibilidad con detalles
                    if not aulas_service.verificar_disponibilidad_aula(
                        aula_id, 
                        datos_reserva["fecha_inicio"], 
                        datos_reserva["fecha_fin"]
                    ):
                        conflictos = aulas_service.obtener_conflictos_detallados(
                            aula_id, 
                            datos_reserva["fecha_inicio"], 
                            datos_reserva["fecha_fin"]
                        )
                        
                        st.error("El aula no está disponible en las fechas del grupo")
                        
                        if conflictos:
                            st.markdown("**Reservas que interfieren:**")
                            for conflicto in conflictos:
                                emoji_tipo = {
                                    'GRUPO': 'Formación',
                                    'MANTENIMIENTO': 'Mantenimiento',
                                    'EVENTO': 'Evento',
                                    'BLOQUEADA': 'Bloqueada'
                                }.get(conflicto['tipo_reserva'], 'Reserva')
                                
                                grupo_info = f" (Grupo: {conflicto['grupo_codigo']})" if conflicto['grupo_codigo'] else ""
                                
                                st.warning(f"**{conflicto['titulo']}** ({emoji_tipo}){grupo_info}\n"
                                         f"Fechas: {conflicto['fecha_inicio']} - {conflicto['fecha_fin']}")
                        return
                    
                    success, reserva_id = aulas_service.crear_reserva(datos_reserva)
                    
                    if success:
                        st.success("✅ Grupo asignado correctamente al aula")
                        st.rerun()
                    else:
                        st.error("❌ Error al asignar el grupo al aula")
                        
                except Exception as e:
                    st.error(f"❌ Error procesando fechas del grupo: {e}")
    
    except Exception as e:
        st.error(f"❌ Error cargando grupos: {e}")

def mostrar_lista_reservas_detallada(aulas_service, session_state):
    """Lista detallada de todas las reservas con acciones"""
    
    st.markdown("#### 📋 Reservas Existentes")
    
    # Filtros de fecha
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fecha_desde = st.date_input(
            "📅 Desde",
            value=datetime.now().date() - timedelta(days=7),
            key="filtro_desde"
        )
    
    with col2:
        fecha_hasta = st.date_input(
            "📅 Hasta",
            value=datetime.now().date() + timedelta(days=30),
            key="filtro_hasta"
        )
    
    with col3:
        if st.button("🔍 Buscar", type="primary"):
            st.rerun()
    
    # Obtener reservas en el rango
    try:
        df_reservas = aulas_service.get_reservas_periodo(
            fecha_desde.isoformat() + "T00:00:00Z",
            fecha_hasta.isoformat() + "T23:59:59Z"
        )
        
        if df_reservas.empty:
            st.info("📋 No hay reservas en el período seleccionado")
            return
        
        # Preparar datos para mostrar
        df_display = df_reservas.copy()
        
        # Formatear fechas y añadir información
        df_display['Fecha'] = pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%d/%m/%Y')
        df_display['Hora Inicio'] = pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%H:%M')
        df_display['Hora Fin'] = pd.to_datetime(df_display['fecha_fin']).dt.strftime('%H:%M')
        
        # Mapear tipos a emojis
        emoji_map = {
            'GRUPO': '📚',
            'MANTENIMIENTO': '🔧',
            'EVENTO': '🎯',
            'BLOQUEADA': '🚫'
        }
        df_display['Tipo'] = df_display['tipo_reserva'].map(emoji_map) + " " + df_display['tipo_reserva']
        
        # Estado con colores
        estado_map = {
            'CONFIRMADA': '✅',
            'TENTATIVA': '⏳',
            'CANCELADA': '❌'
        }
        df_display['Estado'] = df_display['estado'].map(estado_map) + " " + df_display['estado']
        
        # Mostrar tabla
        columnas = ['aula_nombre', 'titulo', 'Fecha', 'Hora Inicio', 'Hora Fin', 'Tipo', 'Estado', 'responsable']
        
        # Usar dataframe con selección
        evento_reserva = st.dataframe(
            df_display[columnas],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "aula_nombre": st.column_config.TextColumn("🏢 Aula"),
                "titulo": st.column_config.TextColumn("📝 Título"),
                "responsable": st.column_config.TextColumn("👤 Responsable"),
            }
        )
        
        # Acciones sobre reserva seleccionada
        if evento_reserva.selection.rows:
            reserva_seleccionada = df_reservas.iloc[evento_reserva.selection.rows[0]]
            
            st.markdown("---")
            st.markdown("##### 🔧 Acciones sobre Reserva Seleccionada")
            
            col_acc1, col_acc2, col_acc3 = st.columns(3)
            
            with col_acc1:
                if st.button("📝 Ver Detalles", use_container_width=True):
                    st.info(f"""
                    **📋 Detalles de la Reserva:**
                    - **ID:** {reserva_seleccionada['id']}
                    - **Aula:** {reserva_seleccionada['aula_nombre']}
                    - **Título:** {reserva_seleccionada['titulo']}
                    - **Tipo:** {reserva_seleccionada['tipo_reserva']}
                    - **Estado:** {reserva_seleccionada['estado']}
                    - **Responsable:** {reserva_seleccionada.get('responsable', 'N/A')}
                    - **Observaciones:** {reserva_seleccionada.get('observaciones', 'Sin observaciones')}
                    """)
            
            with col_acc2:
                if reserva_seleccionada['estado'] == 'CONFIRMADA':
                    if st.button("⏳ Marcar Tentativa", use_container_width=True):
                        success = aulas_service.actualizar_reserva(
                            reserva_seleccionada['id'], 
                            {"estado": "TENTATIVA"}
                        )
                        if success:
                            st.success("✅ Estado actualizado")
                            st.rerun()
            
            with col_acc3:
                if st.button("🗑️ Cancelar Reserva", use_container_width=True):
                    if st.session_state.get("confirmar_cancelar_reserva") == reserva_seleccionada['id']:
                        success = aulas_service.actualizar_reserva(
                            reserva_seleccionada['id'],
                            {"estado": "CANCELADA"}
                        )
                        if success:
                            st.success("✅ Reserva cancelada")
                            del st.session_state["confirmar_cancelar_reserva"]
                            st.rerun()
                    else:
                        st.session_state["confirmar_cancelar_reserva"] = reserva_seleccionada['id']
                        st.warning("⚠️ Presiona nuevamente para confirmar")
        
    except Exception as e:
        st.error(f"❌ Error cargando reservas: {e}")

def main(supabase, session_state):
    """Vista principal de Aulas siguiendo patrón establecido"""
    aulas_service = get_aulas_service(supabase, session_state)
    
    st.title("🏢 Gestión de Aulas")
    
    # Tabs según rol
    if session_state.role == "admin":
        tab1, tab2, tab3, tab4 = st.tabs([
            "🏢 Gestión de Aulas", 
            "📅 Cronograma", 
            "📝 Reservas", 
            "📊 Métricas"
        ])
    else:
        tab1, tab2, tab3 = st.tabs([
            "🏢 Mis Aulas", 
            "📅 Cronograma", 
            "📝 Reservas"
        ])
    
    with tab1:
        # Cargar aulas según rol
        df_aulas = aulas_service.get_aulas_con_empresa()
        
        # Mostrar tabla principal
        aula_seleccionada = mostrar_tabla_aulas(df_aulas, session_state, aulas_service)
        
        st.divider()
        
        # Botones de acción
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("➕ Crear Nueva Aula", type="primary", use_container_width=True):
                st.session_state.aula_creando = True
                st.rerun()
        
        with col2:
            if st.button("🔄 Actualizar Lista", use_container_width=True):
                aulas_service.limpiar_cache_aulas()
                st.rerun()
        
        # Mostrar formulario según estado
        if st.session_state.get("aula_creando"):
            mostrar_formulario_aula({}, aulas_service, session_state, es_creacion=True)
            if st.button("❌ Cancelar Creación"):
                del st.session_state["aula_creando"]
                st.rerun()
        
        elif aula_seleccionada is not None:
            mostrar_formulario_aula(aula_seleccionada, aulas_service, session_state)
    
    with tab2:
        mostrar_cronograma_interactivo(aulas_service, session_state)
    
    with tab3:
        st.markdown("### 📝 Gestión de Reservas")
        
        # Subtabs para organizar mejor
        subtab1, subtab2, subtab3 = st.tabs(["➕ Nueva Reserva", "📚 Asignar Grupos", "📋 Lista de Reservas"])
        
        with subtab1:
            mostrar_formulario_reserva_manual(aulas_service, session_state)
        
        with subtab2:
            mostrar_asignacion_grupos(aulas_service, session_state)
        
        with subtab3:
            mostrar_lista_reservas_detallada(aulas_service, session_state)
    
    if session_state.role == "admin":
        with tab4:
            mostrar_metricas_aulas(aulas_service, session_state)

if __name__ == "__main__":
    main()
                            fecha_str = fecha_dt.strftime('%d/%m/%Y')
                        except:
                            fecha_str = fecha_inicio
                    else:
                        fecha_str = 'Sin fecha'
                    
                    label = f"{grupo['codigo_grupo']} - {grupo.get('accion_nombre', 'Sin acción')} ({fecha_str})"
                    grupos_options[label] = grupo['id']
                
                grupo_seleccionado = st.selectbox(
                    "📚 Seleccionar Grupo",
                    options=list(grupos_options.keys()),
                    key="asignar_grupo"
                )
            
            with col2:
                # Selector de aula
                df_aulas = aulas_service.get_aulas_con_empresa()
                if df_aulas.empty:
                    st.warning("No hay aulas disponibles")
                    return
                
                aulas_options = {}
                for _, aula in df_aulas.iterrows():
                    label = f"{aula['nombre']} (Cap: {aula['capacidad_maxima']})"
                    aulas_options[label] = aula['id']
                
                aula_seleccionada = st.selectbox(
                    "🏢 Seleccionar Aula",
                    options=list(aulas_options.keys()),
                    key="asignar_aula"
                )
            
            # Opciones adicionales
            st.markdown("##### ⚙️ Configuración de Horario")
            
            col3, col4 = st.columns(2)
            with col3:
                hora_inicio_defecto = st.time_input(
                    "🕐 Hora Inicio (defecto)",
                    value=datetime.strptime("09:00", "%H:%M").time(),
                    key="grupo_hora_inicio"
                )
            
            with col4:
                hora_fin_defecto = st.time_input(
                    "🕕 Hora Fin (defecto)",
                    value=datetime.strptime("17:00", "%H:%M").time(),
                    key="grupo_hora_fin"
                )
            
            submitted = st.form_submit_button("🎯 Asignar Grupo a Aula", type="primary")
            
            if submitted:
                grupo_id = grupos_options[grupo_seleccionado]
                aula_id = aulas_options[aula_seleccionada]
                
                # Obtener datos del grupo seleccionado
                grupo_data = df_grupos_disponibles[df_grupos_disponibles['id'] == grupo_id].iloc[0]
                
                fecha_inicio = grupo_data.get('fecha_inicio')
                fecha_fin = grupo_data.get('fecha_fin_prevista') or grupo_data.get('fecha_inicio')
                
                if not fecha_inicio:
                    st.error("❌ El grupo seleccionado no tiene fecha de inicio")
                    return
                
                # Crear reserva automática para el grupo
                try:
                    fecha_inicio_dt = pd.to_datetime(fecha_inicio).date()
                    if isinstance(fecha_fin, str):
                        fecha_fin_dt = pd.to_datetime(fecha_fin).date()
                    else:
                        fecha_fin_dt = fecha_inicio_dt
                    
                    # Crear timestamps con las horas seleccionadas
                    inicio_completo = datetime.combine(fecha_inicio_dt, hora_inicio_defecto)
                    fin_completo = datetime.combine(fecha_fin_dt, hora_fin_defecto)
                    
                    datos_reserva = {
                        "aula_id": aula_id,
                        "grupo_id": grupo_id,
                        "titulo": f"Formación - {grupo_data['codigo_grupo']}",
                        "fecha_inicio": inicio_completo.isoformat() + "Z",
                        "fecha_fin": fin_completo.isoformat() + "Z",
                        "tipo_reserva": "GRUPO",
                        "estado": "CONFIRMADA",
                        "responsable": "Sistema automático"
                    }
                    
                    # Verificar disponibilidad con detalles
                    if not aulas_service.verificar_disponibilidad_aula(
                        aula_id, 
                        datos_reserva["fecha_inicio"], 
                        datos_reserva["fecha_fin"]
                    ):
                        conflictos = aulas_service.obtener_conflictos_detallados(
                            aula_id, 
                            datos_reserva["fecha_inicio"], 
                            datos_reserva["fecha_fin"]
                        )
                        
                        st.error("El aula no está disponible en las fechas del grupo")
                        
                        if conflictos:
                            st.markdown("**Reservas que interfieren:**")
                            for conflicto in conflictos:
                                emoji_tipo = {
                                    'GRUPO': 'Formación',
                                    'MANTENIMIENTO': 'Mantenimiento',
                                    'EVENTO': 'Evento',
                                    'BLOQUEADA': 'Bloqueada'
                                }.get(conflicto['tipo_reserva'], 'Reserva')
                                
                                grupo_info = f" (Grupo: {conflicto['grupo_codigo']})" if conflicto['grupo_codigo'] else ""
                                
                                st.warning(f"**{conflicto['titulo']}** ({emoji_tipo}){grupo_info}\n"
                                         f"Fechas: {conflicto['fecha_inicio']} - {conflicto['fecha_fin']}")
                        return
                    
                    success, reserva_id = aulas_service.crear_reserva(datos_reserva)
                    
                    if success:
                        st.success("✅ Grupo asignado correctamente al aula")
                        st.rerun()
                    else:
                        st.error("❌ Error al asignar el grupo al aula")
                        
                except Exception as e:
                    st.error(f"❌ Error procesando fechas del grupo: {e}")
    
    except Exception as e:
        st.error(f"❌ Error cargando grupos: {e}")

def mostrar_lista_reservas_detallada(aulas_service, session_state):
    """Lista detallada de todas las reservas con acciones"""
    
    st.markdown("#### 📋 Reservas Existentes")
    
    # Filtros de fecha
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fecha_desde = st.date_input(
            "📅 Desde",
            value=datetime.now().date() - timedelta(days=7),
            key="filtro_desde"
        )
    
    with col2:
        fecha_hasta = st.date_input(
            "📅 Hasta",
            value=datetime.now().date() + timedelta(days=30),
            key="filtro_hasta"
        )
    
    with col3:
        if st.button("🔍 Buscar", type="primary"):
            st.rerun()
    
    # Obtener reservas en el rango
    try:
        df_reservas = aulas_service.get_reservas_periodo(
            fecha_desde.isoformat() + "T00:00:00Z",
            fecha_hasta.isoformat() + "T23:59:59Z"
        )
        
        if df_reservas.empty:
            st.info("📋 No hay reservas en el período seleccionado")
            return
        
        # Preparar datos para mostrar
        df_display = df_reservas.copy()
        
        # Formatear fechas y añadir información
        df_display['Fecha'] = pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%d/%m/%Y')
        df_display['Hora Inicio'] = pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%H:%M')
        df_display['Hora Fin'] = pd.to_datetime(df_display['fecha_fin']).dt.strftime('%H:%M')
        
        # Mapear tipos a emojis
        emoji_map = {
            'GRUPO': '📚',
            'MANTENIMIENTO': '🔧',
            'EVENTO': '🎯',
            'BLOQUEADA': '🚫'
        }
        df_display['Tipo'] = df_display['tipo_reserva'].map(emoji_map) + " " + df_display['tipo_reserva']
        
        # Estado con colores
        estado_map = {
            'CONFIRMADA': '✅',
            'TENTATIVA': '⏳',
            'CANCELADA': '❌'
        }
        df_display['Estado'] = df_display['estado'].map(estado_map) + " " + df_display['estado']
        
        # Mostrar tabla
        columnas = ['aula_nombre', 'titulo', 'Fecha', 'Hora Inicio', 'Hora Fin', 'Tipo', 'Estado', 'responsable']
        
        # Usar dataframe con selección
        evento_reserva = st.dataframe(
            df_display[columnas],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "aula_nombre": st.column_config.TextColumn("🏢 Aula"),
                "titulo": st.column_config.TextColumn("📝 Título"),
                "responsable": st.column_config.TextColumn("👤 Responsable"),
            }
        )
        
        # Acciones sobre reserva seleccionada
        if evento_reserva.selection.rows:
            reserva_seleccionada = df_reservas.iloc[evento_reserva.selection.rows[0]]
            
            st.markdown("---")
            st.markdown("##### 🔧 Acciones sobre Reserva Seleccionada")
            
            col_acc1, col_acc2, col_acc3 = st.columns(3)
            
            with col_acc1:
                if st.button("📝 Ver Detalles", use_container_width=True):
                    st.info(f"""
                    **📋 Detalles de la Reserva:**
                    - **ID:** {reserva_seleccionada['id']}
                    - **Aula:** {reserva_seleccionada['aula_nombre']}
                    - **Título:** {reserva_seleccionada['titulo']}
                    - **Tipo:** {reserva_seleccionada['tipo_reserva']}
                    - **Estado:** {reserva_seleccionada['estado']}
                    - **Responsable:** {reserva_seleccionada.get('responsable', 'N/A')}
                    - **Observaciones:** {reserva_seleccionada.get('observaciones', 'Sin observaciones')}
                    """)
            
            with col_acc2:
                if reserva_seleccionada['estado'] == 'CONFIRMADA':
                    if st.button("⏳ Marcar Tentativa", use_container_width=True):
                        success = aulas_service.actualizar_reserva(
                            reserva_seleccionada['id'], 
                            {"estado": "TENTATIVA"}
                        )
                        if success:
                            st.success("✅ Estado actualizado")
                            st.rerun()
            
            with col_acc3:
                if st.button("🗑️ Cancelar Reserva", use_container_width=True):
                    if st.session_state.get("confirmar_cancelar_reserva") == reserva_seleccionada['id']:
                        success = aulas_service.actualizar_reserva(
                            reserva_seleccionada['id'],
                            {"estado": "CANCELADA"}
                        )
                        if success:
                            st.success("✅ Reserva cancelada")
                            del st.session_state["confirmar_cancelar_reserva"]
                            st.rerun()
                    else:
                        st.session_state["confirmar_cancelar_reserva"] = reserva_seleccionada['id']
                        st.warning("⚠️ Presiona nuevamente para confirmar")
        
    except Exception as e:
        st.error(f"❌ Error cargando reservas: {e}")

def mostrar_tabla_aulas(df_aulas, session_state, aulas_service, titulo_tabla="🏢 Lista de Aulas"):
    """Tabla de aulas siguiendo el patrón de Streamlit 1.49"""
    if df_aulas.empty:
        st.info("📋 No hay aulas para mostrar")
        return None

    st.markdown(f"### {titulo_tabla}")

    # 🔎 Filtros fijos arriba de la tabla
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_nombre = st.text_input("🏢 Nombre contiene", key="filtro_aula_nombre")
    with col2:
        filtro_ubicacion = st.text_input("📍 Ubicación contiene", key="filtro_aula_ubicacion")
    with col3:
        filtro_activa = st.selectbox("Estado", ["Todas", "Activas", "Inactivas"], key="filtro_aula_estado")

    # Aplicar filtros
    df_filtrado = df_aulas.copy()
    
    if filtro_nombre:
        df_filtrado = df_filtrado[df_filtrado["nombre"].str.contains(filtro_nombre, case=False, na=False)]
    if filtro_ubicacion:
        df_filtrado = df_filtrado[df_filtrado["ubicacion"].str.contains(filtro_ubicacion, case=False, na=False)]
    if filtro_activa != "Todas":
        activa_bool = filtro_activa == "Activas"
        df_filtrado = df_filtrado[df_filtrado["activa"] == activa_bool]

    # Transformar datos para mostrar
    df_display = df_filtrado.copy()
    df_display["Estado"] = df_display["activa"].apply(lambda x: "✅ Activa" if x else "❌ Inactiva")
    df_display["Capacidad"] = df_display["capacidad_maxima"].apply(lambda x: f"👥 {x}")
    
    # 📊 Mostrar tabla con selección
    columnas = ["nombre", "ubicacion", "Capacidad", "Estado"]
    if session_state.role == "admin":
        columnas.insert(2, "empresa_nombre")

    # Configuración de columnas
    column_config = {
        "nombre": st.column_config.TextColumn("🏢 Aula", width="medium"),
        "ubicacion": st.column_config.TextColumn("📍 Ubicación", width="medium"),
        "Capacidad": st.column_config.TextColumn("👥 Capacidad", width="small"),
        "Estado": st.column_config.TextColumn("📊 Estado", width="small"),
        "empresa_nombre": st.column_config.TextColumn("🏢 Empresa", width="medium")
    }

    evento = st.dataframe(
        df_display[columnas],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config=column_config
    )

    # 🔢 Controles de paginación
    st.markdown("### 📑 Navegación")
    col_pag1, col_pag2 = st.columns([1, 3])
    with col_pag1:
        page_size = st.selectbox("Registros por página", [10, 20, 50, 100], index=1, key="aulas_page_size")
    with col_pag2:
        total_rows = len(df_filtrado)
        total_pages = (total_rows // page_size) + (1 if total_rows % page_size else 0)
        page_number = st.number_input("Página", min_value=1, max_value=max(total_pages, 1), step=1, value=1, key="aulas_page_num")

    start_idx = (page_number - 1) * page_size
    end_idx = start_idx + page_size
    df_paged = df_filtrado.iloc[start_idx:end_idx]

    # ✅ Botones de acción
    col_exp, col_imp = st.columns([1, 1])
    with col_exp:
        if not df_filtrado.empty:
            fecha_str = datetime.now().strftime("%Y%m%d")
            filename = f"aulas_{fecha_str}.xlsx"
            export_excel(df_filtrado, filename=filename, label="📥 Exportar Excel")
    with col_imp:
        if st.button("🔄 Actualizar", use_container_width=True, key="btn_actualizar_aulas"):
            aulas_service.limpiar_cache_aulas()
            st.rerun()

    # Retornar aula seleccionada
    if evento.selection.rows:
        return df_paged.iloc[evento.selection.rows[0]]
    return None

def mostrar_formulario_aula(aula_data, aulas_service, session_state, es_creacion=False):
    """Formulario de aula siguiendo el patrón establecido"""
    if es_creacion:
        st.subheader("➕ Nueva Aula")
        datos = {}
    else:
        st.subheader(f"✏️ Editar {aula_data['nombre']}")
        datos = aula_data.copy()

    # ID único para el formulario
    form_id = f"aula_{datos.get('id', 'nueva')}_{'crear' if es_creacion else 'editar'}"

    with st.form(form_id, clear_on_submit=es_creacion):
        # =========================
        # DATOS BÁSICOS
        # =========================
        st.markdown("### 🏢 Información Básica")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input(
                "🏢 Nombre del Aula", 
                value=datos.get("nombre", ""), 
                key=f"{form_id}_nombre",
                help="Nombre identificativo del aula"
            )
            capacidad_maxima = st.number_input(
                "👥 Capacidad Máxima", 
                min_value=1, 
                max_value=200, 
                value=int(datos.get("capacidad_maxima", 20)),
                key=f"{form_id}_capacidad"
            )
        
        with col2:
            ubicacion = st.text_input(
                "📍 Ubicación", 
                value=datos.get("ubicacion", ""), 
                key=f"{form_id}_ubicacion",
                help="Descripción de la ubicación física del aula"
            )
            activa = st.checkbox(
                "✅ Aula Activa", 
                value=datos.get("activa", True),
                key=f"{form_id}_activa"
            )

        # =========================
        # EQUIPAMIENTO
        # =========================
        st.markdown("### 🔧 Equipamiento")
        
        opciones_equipamiento = [
            "PROYECTOR", "PIZARRA_DIGITAL", "ORDENADORES", "AUDIO", 
            "AIRE_ACONDICIONADO", "CALEFACCION", "WIFI", "TELEVISION",
            "FLIPCHART", "IMPRESORA", "ESCANER"
        ]
        
        equipamiento_actual = datos.get("equipamiento", [])
        if equipamiento_actual and isinstance(equipamiento_actual[0], str):
            equipamiento_actual = equipamiento_actual
        
        equipamiento = st.multiselect(
            "Seleccionar equipamiento disponible",
            options=opciones_equipamiento,
            default=equipamiento_actual,
            key=f"{form_id}_equipamiento"
        )

        # =========================
        # PERSONALIZACIÓN
        # =========================
        st.markdown("### 🎨 Configuración Visual")
        
        col1, col2 = st.columns(2)
        
        with col1:
            color_cronograma = st.color_picker(
                "🎨 Color en Cronograma",
                value=datos.get("color_cronograma", "#3498db"),
                key=f"{form_id}_color"
            )
        
        with col2:
            st.write("**Vista previa del color:**")
            st.markdown(
                f'<div style="background-color: {color_cronograma}; height: 30px; border-radius: 5px; border: 1px solid #ddd;"></div>',
                unsafe_allow_html=True
            )

        # =========================
        # OBSERVACIONES
        # =========================
        observaciones = st.text_area(
            "📝 Observaciones",
            value=datos.get("observaciones", ""),
            key=f"{form_id}_observaciones",
            help="Comentarios adicionales sobre el aula"
        )

        # =========================
        # VALIDACIONES
        # =========================
        errores = []
        if not nombre:
            errores.append("Nombre del aula es obligatorio")
        if capacidad_maxima < 1:
            errores.append("Capacidad debe ser mayor a 0")
        
        if errores:
            st.error(f"⚠️ Errores encontrados: {', '.join(errores)}")

        # =========================
        # BOTONES
        # =========================
        st.markdown("---")
        if es_creacion:
            submitted = st.form_submit_button("➕ Crear Aula", type="primary", use_container_width=True)
        else:
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
            with col_btn2:
                if session_state.role == "admin":
                    eliminar = st.form_submit_button("🗑️ Eliminar", type="secondary", use_container_width=True)
                else:
                    eliminar = False

        # =========================
        # PROCESAMIENTO
        # =========================
        if submitted and not errores:
            try:
                datos_aula = {
                    "nombre": nombre,
                    "descripcion": datos.get("descripcion", ""),
                    "capacidad_maxima": capacidad_maxima,
                    "equipamiento": equipamiento,
                    "ubicacion": ubicacion,
                    "activa": activa,
                    "color_cronograma": color_cronograma,
                    "observaciones": observaciones,
                    "updated_at": datetime.utcnow().isoformat()
                }

                if es_creacion:
                    # Añadir empresa_id según rol
                    if session_state.role == "gestor":
                        datos_aula["empresa_id"] = session_state.user.get("empresa_id")
                    else:
                        # Para admin, podríamos añadir selector de empresa
                        datos_aula["empresa_id"] = session_state.user.get("empresa_id")
                    
                    datos_aula["created_at"] = datetime.utcnow().isoformat()
                    
                    success, aula_id = aulas_service.crear_aula(datos_aula)
                    if success:
                        st.success("✅ Aula creada correctamente")
                        st.rerun()
                    else:
                        st.error("❌ Error al crear el aula")
                else:
                    success = aulas_service.actualizar_aula(datos["id"], datos_aula)
                    if success:
                        st.success("✅ Aula actualizada correctamente")
                        st.rerun()
                    else:
                        st.error("❌ Error al actualizar el aula")
                        
            except Exception as e:
                st.error(f"❌ Error procesando aula: {e}")

        # Manejar eliminación
        if 'eliminar' in locals() and eliminar:
            if st.session_state.get("confirmar_eliminar_aula"):
                try:
                    success = aulas_service.eliminar_aula(datos["id"])
                    if success:
                        st.success("✅ Aula eliminada correctamente")
                        del st.session_state["confirmar_eliminar_aula"]
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error eliminando aula: {e}")
            else:
                st.session_state["confirmar_eliminar_aula"] = True
                st.warning("⚠️ Presiona 'Eliminar' nuevamente para confirmar")

def mostrar_vista_cronograma_alternativa(eventos, aulas_service):
    """Vista de cronograma alternativa cuando streamlit-calendar no funciona"""
    
    st.markdown("### 📅 Vista de Cronograma (Alternativa)")
    
    if not eventos:
        st.info("No hay reservas para mostrar en el período seleccionado")
        st.markdown("**💡 Sugerencia:** Crea algunas reservas en la pestaña 'Reservas' para ver el cronograma.")
        return
    
    # Convertir eventos a DataFrame
    eventos_data = []
    for evento in eventos:
        fecha_inicio = pd.to_datetime(evento['start'])
        fecha_fin = pd.to_datetime(evento['end'])
        
        eventos_data.append({
            'Fecha': fecha_inicio.date(),
            'Día': fecha_inicio.strftime('%A'),
            'Hora Inicio': fecha_inicio.strftime('%H:%M'),
            'Hora Fin': fecha_fin.strftime('%H:%M'),
            'Aula': evento['extendedProps']['aula_nombre'],
            'Título': evento['title'].split(': ', 1)[-1],
            'Tipo': evento['extendedProps']['tipo_reserva'],
            'Estado': evento['extendedProps']['estado'],
            'Color': evento['backgroundColor']
        })
    
    df_eventos = pd.DataFrame(eventos_data)
    
    # Agrupar por fecha
    fechas_unicas = sorted(df_eventos['Fecha'].unique())
    
    # Mostrar cronograma por días
    for fecha in fechas_unicas:
        eventos_dia = df_eventos[df_eventos['Fecha'] == fecha].sort_values('Hora Inicio')
        
        st.markdown(f"#### 📅 {fecha.strftime('%A, %d de %B %Y')}")
        
        if eventos_dia.empty:
            st.info("Sin reservas para este día")
        else:
            # Crear vista visual de horarios
            for _, evento in eventos_dia.iterrows():
                # Color según tipo
                color_map = {
                    'GRUPO': '🟢',
                    'EVENTO': '🔵', 
                    'MANTENIMIENTO': '🟡',
                    'BLOQUEADA': '🔴'
                }
                emoji = color_map.get(evento['Tipo'], '⚪')
                
                # Mostrar cada evento como una tarjeta
                with st.container():
                    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
                    
                    with col1:
                        st.markdown(f"**{evento['Hora Inicio']} - {evento['Hora Fin']}**")
                    
                    with col2:
                        st.markdown(f"**{evento['Aula']}**")
                    
                    with col3:
                        st.markdown(f"{emoji} {evento['Título']}")
                    
                    with col4:
                        estado_emoji = "✅" if evento['Estado'] == 'CONFIRMADA' else "⏳"
                        st.markdown(f"{estado_emoji} {evento['Estado']}")
        
        st.divider()
    
    # Resumen de estadísticas
    st.markdown("### 📊 Resumen del Período")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Reservas", len(df_eventos))
    
    with col2:
        aulas_ocupadas = df_eventos['Aula'].nunique()
        st.metric("Aulas Utilizadas", aulas_ocupadas)
    
    with col3:
        reservas_por_tipo = df_eventos['Tipo'].value_counts()
        tipo_principal = reservas_por_tipo.index[0] if not reservas_por_tipo.empty else "N/A"
        st.metric("Tipo Principal", tipo_principal)
    
    with col4:
        dias_con_actividad = df_eventos['Fecha'].nunique()
        st.metric("Días con Actividad", dias_con_actividad)
    
    # Gráfico de barras por tipo
    if not df_eventos.empty:
        st.markdown("### 📈 Reservas por Tipo")
        tipo_counts = df_eventos['Tipo'].value_counts()
        st.bar_chart(tipo_counts)
        
        # Tabla detallada
        with st.expander("📋 Ver Tabla Detallada"):
            st.dataframe(
                df_eventos[['Fecha', 'Hora Inicio', 'Hora Fin', 'Aula', 'Título', 'Tipo', 'Estado']],
                use_container_width=True,
                hide_index=True
            )

def mostrar_vista_alternativa_cronograma(eventos):
    """Vista alternativa cuando el calendario no funciona"""
    if not eventos:
        st.info("No hay reservas para mostrar en el período seleccionado")
        return
    
    # Convertir eventos a DataFrame para mostrar
    eventos_df = []
    for evento in eventos:
        fecha_inicio = pd.to_datetime(evento['start'])
        fecha_fin = pd.to_datetime(evento['end'])
        
        eventos_df.append({
            'Aula': evento['extendedProps']['aula_nombre'],
            'Título': evento['title'].split(': ', 1)[-1],
            'Fecha': fecha_inicio.strftime('%d/%m/%Y'),
            'Hora Inicio': fecha_inicio.strftime('%H:%M'),
            'Hora Fin': fecha_fin.strftime('%H:%M'),
            'Tipo': evento['extendedProps']['tipo_reserva'],
            'Estado': evento['extendedProps']['estado']
        })
    
    df_eventos = pd.DataFrame(eventos_df)
    
    # Mostrar tabla con formato
    st.dataframe(
        df_eventos,
        use_container_width=True,
        hide_index=True
    )

def mostrar_metricas_aulas(aulas_service, session_state):
    """Métricas usando componentes nativos de Streamlit 1.49"""
    try:
        metricas = aulas_service.get_estadisticas_aulas()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🏢 Total Aulas", metricas.get("total_aulas", 0))
        
        with col2:
            st.metric("✅ Aulas Activas", metricas.get("aulas_activas", 0))
        
        with col3:
            ocupacion = metricas.get("ocupacion_promedio", 0)
            st.metric("📊 Ocupación Promedio", f"{ocupacion}%")
        
        with col4:
            st.metric("📅 Reservas Hoy", metricas.get("reservas_hoy", 0))
            
        # Gráfico de ocupación por aula
        if session_state.role == "admin":
            st.markdown("### 📈 Ocupación por Aula")
            df_ocupacion = aulas_service.get_ocupacion_por_aula()
            if not df_ocupacion.empty:
                st.bar_chart(df_ocupacion.set_index("nombre")["ocupacion_porcentaje"])
            
    except Exception as e:
        st.error(f"❌ Error al cargar métricas: {e}")

def main(supabase, session_state):
    """Vista principal de Aulas siguiendo patrón establecido"""
    aulas_service = get_aulas_service(supabase, session_state)
    
    st.title("🏢 Gestión de Aulas")
    
    # Tabs según rol
    if session_state.role == "admin":
        tab1, tab2, tab3, tab4 = st.tabs([
            "🏢 Gestión de Aulas", 
            "📅 Cronograma", 
            "📝 Reservas", 
            "📊 Métricas"
        ])
    else:
        tab1, tab2, tab3 = st.tabs([
            "🏢 Mis Aulas", 
            "📅 Cronograma", 
            "📝 Reservas"
        ])
    
    with tab1:
        # Cargar aulas según rol
        df_aulas = aulas_service.get_aulas_con_empresa()
        
        # Mostrar tabla principal
        aula_seleccionada = mostrar_tabla_aulas(df_aulas, session_state, aulas_service)
        
        st.divider()
        
        # Botones de acción
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("➕ Crear Nueva Aula", type="primary", use_container_width=True):
                st.session_state.aula_creando = True
                st.rerun()
        
        with col2:
            if st.button("🔄 Actualizar Lista", use_container_width=True):
                aulas_service.limpiar_cache_aulas()
                st.rerun()
        
        # Mostrar formulario según estado
        if st.session_state.get("aula_creando"):
            mostrar_formulario_aula({}, aulas_service, session_state, es_creacion=True)
            if st.button("❌ Cancelar Creación"):
                del st.session_state["aula_creando"]
                st.rerun()
        
        elif aula_seleccionada is not None:
            mostrar_formulario_aula(aula_seleccionada, aulas_service, session_state)
    
    with tab2:
        mostrar_cronograma_interactivo(aulas_service, session_state)
    
    with tab3:
        st.markdown("### 📝 Gestión de Reservas")
        
        # Subtabs para organizar mejor
        subtab1, subtab2, subtab3 = st.tabs(["➕ Nueva Reserva", "📚 Asignar Grupos", "📋 Lista de Reservas"])
        
        with subtab1:
            mostrar_formulario_reserva_manual(aulas_service, session_state)
        
        with subtab2:
            mostrar_asignacion_grupos(aulas_service, session_state)
        
        with subtab3:
            mostrar_lista_reservas_detallada(aulas_service, session_state)
    
    if session_state.role == "admin":
        with tab4:
            mostrar_metricas_aulas(aulas_service, session_state)

if __name__ == "__main__":
    main()
