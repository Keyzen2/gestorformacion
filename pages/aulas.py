import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from services.aulas_service import get_aulas_service
from utils import export_excel

# Importar streamlit-calendar
try:
    from streamlit_calendar import calendar
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False

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

    evento = st.dataframe(
        df_display[columnas],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

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
        return df_filtrado.iloc[evento.selection.rows[0]]
    return None

def mostrar_formulario_aula(aula_data, aulas_service, session_state, es_creacion=False):
    """Formulario de aula siguiendo el patrón establecido"""
    if es_creacion:
        st.subheader("➕ Nueva Aula")
        datos = {}
    else:
        st.subheader(f"✏️ Editar {aula_data['nombre']}")
        datos = aula_data.copy()

    form_id = f"aula_{datos.get('id', 'nueva')}_{'crear' if es_creacion else 'editar'}"

    with st.form(form_id, clear_on_submit=es_creacion):
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

        st.markdown("### 🔧 Equipamiento")
        opciones_equipamiento = [
            "PROYECTOR", "PIZARRA_DIGITAL", "ORDENADORES", "AUDIO", 
            "AIRE_ACONDICIONADO", "CALEFACCION", "WIFI", "TELEVISION",
            "FLIPCHART", "IMPRESORA", "ESCANER"
        ]
        
        equipamiento_actual = datos.get("equipamiento", [])
        equipamiento = st.multiselect(
            "Seleccionar equipamiento disponible",
            options=opciones_equipamiento,
            default=equipamiento_actual,
            key=f"{form_id}_equipamiento"
        )

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

        observaciones = st.text_area(
            "📝 Observaciones",
            value=datos.get("observaciones", ""),
            key=f"{form_id}_observaciones",
            help="Comentarios adicionales sobre el aula"
        )

        # Validaciones
        errores = []
        if not nombre:
            errores.append("Nombre del aula es obligatorio")
        if capacidad_maxima < 1:
            errores.append("Capacidad debe ser mayor a 0")
        
        if errores:
            st.error(f"⚠️ Errores encontrados: {', '.join(errores)}")

        # Botones
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

        # Procesamiento
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
                    if session_state.role == "gestor":
                        datos_aula["empresa_id"] = session_state.user.get("empresa_id")
                    else:
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

def mostrar_cronograma_fullcalendar(aulas_service, session_state):
    """Cronograma usando streamlit-calendar basado en la documentación oficial"""
    
    st.markdown("### 📅 Cronograma Interactivo de Aulas")
    
    if not CALENDAR_AVAILABLE:
        st.error("📦 streamlit-calendar no está instalado. Instala con: pip install streamlit-calendar")
        mostrar_cronograma_alternativo(aulas_service, session_state)
        return

    # Controles de configuración
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        fecha_inicio = st.date_input(
            "📅 Desde", 
            value=datetime.now().date() - timedelta(days=7),
            key="cal_fecha_inicio"
        )
    
    with col2:
        fecha_fin = st.date_input(
            "📅 Hasta", 
            value=datetime.now().date() + timedelta(days=21),
            key="cal_fecha_fin"
        )
    
    with col3:
        vista_inicial = st.selectbox(
            "👁️ Vista inicial",
            ["dayGridMonth", "timeGridWeek", "timeGridDay", "listWeek"],
            index=1,
            key="cal_vista"
        )
    
    with col4:
        if st.button("🔄 Actualizar Cronograma", key="cal_refresh"):
            st.rerun()

    # Filtros de aulas
    try:
        df_aulas = aulas_service.get_aulas_con_empresa()
        if df_aulas.empty:
            st.warning("⚠️ No hay aulas disponibles")
            return
        
        # Selector de aulas
        aulas_disponibles = ["Todas"] + df_aulas['nombre'].tolist()
        aulas_seleccionadas = st.multiselect(
            "🏢 Filtrar por aulas específicas",
            aulas_disponibles,
            default=["Todas"],
            key="cal_filtro_aulas"
        )
        
        # Determinar IDs de aulas a filtrar
        if "Todas" in aulas_seleccionadas or not aulas_seleccionadas:
            aulas_ids = df_aulas['id'].tolist()
        else:
            aulas_ids = df_aulas[df_aulas['nombre'].isin(aulas_seleccionadas)]['id'].tolist()
        
    except Exception as e:
        st.error(f"❌ Error cargando aulas: {e}")
        return

    # Obtener eventos
    try:
        eventos = aulas_service.get_eventos_cronograma(
            fecha_inicio.isoformat() + "T00:00:00Z",
            fecha_fin.isoformat() + "T23:59:59Z",
            aulas_ids
        )
        
        # Debug info (removible en producción)
        with st.expander("🔍 Debug Info"):
            st.write(f"Se encontraron {len(eventos)} eventos")
            if eventos:
                st.write("Primer evento:", eventos[0])
        
        # Configuración del calendario según documentación oficial
        calendar_options = {
            "editable": "true",
            "navLinks": "true",
            "selectable": "true",
            "initialView": vista_inicial,
            "initialDate": fecha_inicio.isoformat(),
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
            },
            "height": 650,
            "slotMinTime": "07:00:00",
            "slotMaxTime": "22:00:00",
            "weekends": True,
            "businessHours": {
                "daysOfWeek": [1, 2, 3, 4, 5],
                "startTime": "08:00",
                "endTime": "19:00"
            },
            "nowIndicator": True,
            "dayMaxEvents": 3,
            "eventDisplay": "block",
            "displayEventEnd": True,
            "locale": "es",
            "timeZone": "local"
        }

        # CSS personalizado para tipos de eventos
        calendar_css = """
        .fc-event-grupo { 
            background-color: #28a745 !important;
            border-color: #28a745 !important;
            color: white !important;
        }
        .fc-event-mantenimiento { 
            background-color: #ffc107 !important;
            border-color: #ffc107 !important;
            color: #212529 !important;
        }
        .fc-event-evento { 
            background-color: #17a2b8 !important;
            border-color: #17a2b8 !important;
            color: white !important;
        }
        .fc-event-bloqueada { 
            background-color: #dc3545 !important;
            border-color: #dc3545 !important;
            color: white !important;
        }
        .fc-toolbar-title {
            font-size: 1.25em !important;
            font-weight: 600 !important;
        }
        .fc-button-primary {
            background-color: #0066cc !important;
            border-color: #0066cc !important;
        }
        .fc-button-primary:hover {
            background-color: #0056b3 !important;
            border-color: #0056b3 !important;
        }
        """

        # Renderizar el calendario
        try:
            calendar_result = calendar(
                events=eventos,
                options=calendar_options,
                custom_css=calendar_css,
                key="fullcalendar_aulas",
                callbacks=["dateClick", "eventClick", "select"]
            )
            
            # Procesar callbacks del calendario
            if calendar_result:
                
                # Click en evento
                if calendar_result.get("eventClick"):
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
                    
                    if evento_info['extendedProps'].get('grupo_codigo'):
                        st.success(f"**📚 Grupo:** {evento_info['extendedProps']['grupo_codigo']}")

                # Click en fecha vacía
                if calendar_result.get("dateClick"):
                    fecha_click = calendar_result["dateClick"]["date"]
                    st.info(f"📅 Fecha seleccionada: {pd.to_datetime(fecha_click).strftime('%d/%m/%Y')}")
                    
                    if st.button("➕ Crear reserva en esta fecha", key="crear_reserva_fecha"):
                        st.session_state["crear_reserva_fecha"] = fecha_click
                        st.rerun()

                # Selección de rango
                if calendar_result.get("select"):
                    seleccion = calendar_result["select"]
                    inicio = pd.to_datetime(seleccion["start"]).strftime('%d/%m/%Y %H:%M')
                    fin = pd.to_datetime(seleccion["end"]).strftime('%d/%m/%Y %H:%M')
                    st.info(f"📅 Rango seleccionado: {inicio} - {fin}")

        except Exception as e:
            st.error(f"❌ Error renderizando calendario: {e}")
            st.write("Error details:", str(e))
            mostrar_cronograma_alternativo(aulas_service, session_state)
            return

    except Exception as e:
        st.error(f"❌ Error obteniendo eventos: {e}")
        return

    # Leyenda
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
            st.markdown("**🔴 Bloqueada**")
            st.markdown("Aula no disponible")

def mostrar_cronograma_alternativo(aulas_service, session_state):
    """Vista alternativa si no funciona el calendario"""
    
    st.markdown("### 📅 Vista de Cronograma (Alternativa)")
    
    # Controles básicos
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Desde", value=datetime.now().date())
    with col2:
        fecha_fin = st.date_input("Hasta", value=datetime.now().date() + timedelta(days=7))
    
    try:
        df_reservas = aulas_service.get_reservas_periodo(
            fecha_inicio.isoformat() + "T00:00:00Z",
            fecha_fin.isoformat() + "T23:59:59Z"
        )
        
        if df_reservas.empty:
            st.info("📋 No hay reservas en el período seleccionado")
            return
        
        # Agrupar por fecha
        df_reservas['fecha'] = pd.to_datetime(df_reservas['fecha_inicio']).dt.date
        fechas_unicas = sorted(df_reservas['fecha'].unique())
        
        for fecha in fechas_unicas:
            eventos_dia = df_reservas[df_reservas['fecha'] == fecha].sort_values('fecha_inicio')
            
            st.markdown(f"#### 📅 {fecha.strftime('%A, %d de %B %Y')}")
            
            for _, evento in eventos_dia.iterrows():
                inicio = pd.to_datetime(evento['fecha_inicio'])
                fin = pd.to_datetime(evento['fecha_fin'])
                
                color_map = {'GRUPO': '🟢', 'EVENTO': '🔵', 'MANTENIMIENTO': '🟡', 'BLOQUEADA': '🔴'}
                emoji = color_map.get(evento['tipo_reserva'], '⚪')
                
                col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
                
                with col1:
                    st.markdown(f"**{inicio.strftime('%H:%M')} - {fin.strftime('%H:%M')}**")
                with col2:
                    st.markdown(f"**{evento['aula_nombre']}**")
                with col3:
                    st.markdown(f"{emoji} {evento['titulo']}")
                with col4:
                    estado_emoji = "✅" if evento['estado'] == 'CONFIRMADA' else "⏳"
                    st.markdown(f"{estado_emoji}")
            
            st.divider()
        
    except Exception as e:
        st.error(f"❌ Error: {e}")

def mostrar_formulario_reserva_manual(aulas_service, session_state):
    """Formulario para crear reservas manuales"""
    
    st.markdown("### ➕ Nueva Reserva Manual")
    
    # Obtener lista de aulas disponibles
    try:
        df_aulas = aulas_service.get_aulas_con_empresa()
        if df_aulas.empty:
            st.warning("⚠️ No hay aulas disponibles")
            return
        
        aulas_opciones = {f"{row['nombre']} ({row['ubicacion']})": row['id'] 
                         for _, row in df_aulas.iterrows()}
        
    except Exception as e:
        st.error(f"❌ Error cargando aulas: {e}")
        return

    with st.form("nueva_reserva_manual"):
        col1, col2 = st.columns(2)
        
        with col1:
            aula_seleccionada = st.selectbox(
                "🏢 Seleccionar Aula",
                options=list(aulas_opciones.keys()),
                key="reserva_aula"
            )
            
            tipo_reserva = st.selectbox(
                "🏷️ Tipo de Reserva",
                ["GRUPO", "EVENTO", "MANTENIMIENTO", "BLOQUEADA"],
                key="reserva_tipo"
            )
            
            titulo = st.text_input(
                "📝 Título de la Reserva",
                key="reserva_titulo",
                help="Descripción breve de la reserva"
            )
        
        with col2:
            fecha_reserva = st.date_input(
                "📅 Fecha",
                value=datetime.now().date(),
                key="reserva_fecha"
            )
            
            col_hora1, col_hora2 = st.columns(2)
            with col_hora1:
                hora_inicio = st.time_input(
                    "⏰ Hora Inicio",
                    value=datetime.now().time(),
                    key="reserva_hora_inicio"
                )
            with col_hora2:
                hora_fin = st.time_input(
                    "⏰ Hora Fin",
                    value=(datetime.now() + timedelta(hours=2)).time(),
                    key="reserva_hora_fin"
                )
        
        descripcion = st.text_area(
            "📝 Descripción Adicional",
            key="reserva_descripcion",
            help="Información adicional sobre la reserva (opcional)"
        )
        
        # Validaciones
        errores = []
        if not titulo:
            errores.append("El título es obligatorio")
        if hora_inicio >= hora_fin:
            errores.append("La hora de fin debe ser posterior a la de inicio")
        
        if errores:
            for error in errores:
                st.error(f"⚠️ {error}")
        
        submitted = st.form_submit_button(
            "➕ Crear Reserva", 
            type="primary", 
            use_container_width=True,
            disabled=bool(errores)
        )
        
        if submitted and not errores:
            try:
                # Crear datetime completos
                fecha_inicio_completa = datetime.combine(fecha_reserva, hora_inicio)
                fecha_fin_completa = datetime.combine(fecha_reserva, hora_fin)
                
                # Verificar conflictos
                aula_id = aulas_opciones[aula_seleccionada]
                
                conflictos = aulas_service.verificar_conflictos_reserva(
                    aula_id,
                    fecha_inicio_completa.isoformat(),
                    fecha_fin_completa.isoformat()
                )
                
                if conflictos:
                    st.error("❌ Ya existe una reserva en este horario para esta aula")
                    return
                
                # Crear la reserva
                datos_reserva = {
                    "aula_id": aula_id,
                    "titulo": titulo,
                    "descripcion": descripcion,
                    "tipo_reserva": tipo_reserva,
                    "fecha_inicio": fecha_inicio_completa.isoformat(),
                    "fecha_fin": fecha_fin_completa.isoformat(),
                    "estado": "CONFIRMADA",
                    "created_by": session_state.user.get("id"),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                success, reserva_id = aulas_service.crear_reserva(datos_reserva)
                
                if success:
                    st.success("✅ Reserva creada correctamente")
                    st.rerun()
                else:
                    st.error("❌ Error al crear la reserva")
                    
            except Exception as e:
                st.error(f"❌ Error procesando reserva: {e}")

def mostrar_lista_reservas(aulas_service, session_state):
    """Lista de reservas existentes con opciones de gestión"""
    
    st.markdown("### 📋 Reservas Existentes")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fecha_desde = st.date_input(
            "Desde",
            value=datetime.now().date() - timedelta(days=7),
            key="lista_fecha_desde"
        )
    
    with col2:
        fecha_hasta = st.date_input(
            "Hasta",
            value=datetime.now().date() + timedelta(days=14),
            key="lista_fecha_hasta"
        )
    
    with col3:
        filtro_tipo = st.selectbox(
            "Tipo",
            ["Todos", "GRUPO", "EVENTO", "MANTENIMIENTO", "BLOQUEADA"],
            key="lista_filtro_tipo"
        )
    
    try:
        # Obtener reservas
        df_reservas = aulas_service.get_reservas_periodo(
            fecha_desde.isoformat() + "T00:00:00Z",
            fecha_hasta.isoformat() + "T23:59:59Z"
        )
        
        if not df_reservas.empty:
            # Aplicar filtro de tipo
            if filtro_tipo != "Todos":
                df_reservas = df_reservas[df_reservas['tipo_reserva'] == filtro_tipo]
            
            # Formatear datos para mostrar
            df_display = df_reservas.copy()
            df_display['Fecha'] = pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%d/%m/%Y')
            df_display['Horario'] = (
                pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%H:%M') + 
                " - " + 
                pd.to_datetime(df_display['fecha_fin']).dt.strftime('%H:%M')
            )
            df_display['Estado'] = df_display['estado'].apply(
                lambda x: "✅ Confirmada" if x == "CONFIRMADA" else "⏳ Pendiente"
            )
            
            # Mostrar tabla
            columnas_mostrar = ['Fecha', 'Horario', 'aula_nombre', 'titulo', 'tipo_reserva', 'Estado']
            
            evento = st.dataframe(
                df_display[columnas_mostrar],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    'aula_nombre': 'Aula',
                    'titulo': 'Título',
                    'tipo_reserva': 'Tipo'
                }
            )
            
            # Opciones para reserva seleccionada
            if evento.selection.rows and session_state.role in ["admin", "gestor"]:
                reserva_seleccionada = df_reservas.iloc[evento.selection.rows[0]]
                
                st.markdown("---")
                st.markdown("### 🔧 Acciones para Reserva Seleccionada")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📝 Editar Reserva", key="editar_reserva_btn"):
                        st.session_state["editar_reserva_id"] = reserva_seleccionada['id']
                        st.rerun()
                
                with col2:
                    if reserva_seleccionada['estado'] == 'PENDIENTE':
                        if st.button("✅ Confirmar", key="confirmar_reserva_btn"):
                            try:
                                success = aulas_service.actualizar_estado_reserva(
                                    reserva_seleccionada['id'], 
                                    'CONFIRMADA'
                                )
                                if success:
                                    st.success("✅ Reserva confirmada")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                
                with col3:
                    if st.button("🗑️ Eliminar", key="eliminar_reserva_btn"):
                        if st.session_state.get("confirmar_eliminar_reserva"):
                            try:
                                success = aulas_service.eliminar_reserva(reserva_seleccionada['id'])
                                if success:
                                    st.success("✅ Reserva eliminada")
                                    del st.session_state["confirmar_eliminar_reserva"]
                                    st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                        else:
                            st.session_state["confirmar_eliminar_reserva"] = True
                            st.warning("⚠️ Presiona nuevamente para confirmar")
        
        else:
            st.info("📋 No hay reservas en el período seleccionado")
            
    except Exception as e:
        st.error(f"❌ Error cargando reservas: {e}")

def mostrar_metricas_admin(aulas_service, session_state):
    """Métricas y estadísticas para administradores"""
    
    if session_state.role != "admin":
        st.warning("🔒 Solo administradores pueden ver las métricas")
        return
    
    st.markdown("### 📊 Métricas de Aulas")
    
    try:
        # Obtener métricas
        metricas = aulas_service.get_metricas_aulas()
        
        # KPIs principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🏢 Total Aulas",
                metricas.get('total_aulas', 0),
                delta=f"{metricas.get('aulas_activas', 0)} activas"
            )
        
        with col2:
            st.metric(
                "📅 Reservas Hoy",
                metricas.get('reservas_hoy', 0)
            )
        
        with col3:
            ocupacion = metricas.get('porcentaje_ocupacion', 0)
            st.metric(
                "📈 % Ocupación",
                f"{ocupacion:.1f}%",
                delta=f"{'Alta' if ocupacion > 70 else 'Media' if ocupacion > 40 else 'Baja'}"
            )
        
        with col4:
            st.metric(
                "👥 Capacidad Total",
                metricas.get('capacidad_total', 0)
            )
        
        st.markdown("---")
        
        # Gráficos
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Distribución por Tipo de Reserva")
            
            tipos_data = metricas.get('reservas_por_tipo', {})
            if tipos_data:
                st.bar_chart(tipos_data)
            else:
                st.info("No hay datos de reservas por tipo")
        
        with col2:
            st.markdown("#### 🏢 Aulas Más Utilizadas")
            
            aulas_data = metricas.get('aulas_mas_utilizadas', {})
            if aulas_data:
                st.bar_chart(aulas_data)
            else:
                st.info("No hay datos de utilización de aulas")
        
        # Tabla de detalles
        st.markdown("#### 📋 Detalle de Ocupación por Aula")
        
        df_detalle = aulas_service.get_detalle_ocupacion_aulas()
        if not df_detalle.empty:
            st.dataframe(
                df_detalle,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'nombre': 'Aula',
                    'capacidad_maxima': 'Capacidad',
                    'reservas_mes': 'Reservas Mes',
                    'horas_ocupadas': 'Horas Ocupadas',
                    'porcentaje_ocupacion': st.column_config.ProgressColumn(
                        'Ocupación %',
                        min_value=0,
                        max_value=100
                    )
                }
            )
        else:
            st.info("No hay datos de ocupación disponibles")
            
        # Exportar métricas
        if st.button("📥 Exportar Métricas", key="exportar_metricas"):
            try:
                fecha_str = datetime.now().strftime("%Y%m%d")
                filename = f"metricas_aulas_{fecha_str}.xlsx"
                export_excel(df_detalle, filename=filename, label="Métricas exportadas")
            except Exception as e:
                st.error(f"❌ Error exportando: {e}")
                
    except Exception as e:
        st.error(f"❌ Error cargando métricas: {e}")

def mostrar_formulario_editar_reserva(aulas_service, session_state, reserva_id):
    """Formulario para editar una reserva existente"""
    
    try:
        # Obtener datos de la reserva
        reserva_data = aulas_service.get_reserva_by_id(reserva_id)
        if not reserva_data:
            st.error("❌ Reserva no encontrada")
            return
        
        # Obtener lista de aulas
        df_aulas = aulas_service.get_aulas_con_empresa()
        aulas_opciones = {f"{row['nombre']} ({row['ubicacion']})": row['id'] 
                         for _, row in df_aulas.iterrows()}
        
        # Encontrar aula actual
        aula_actual = next(
            (k for k, v in aulas_opciones.items() if v == reserva_data['aula_id']), 
            list(aulas_opciones.keys())[0]
        )
        
        st.markdown(f"### ✏️ Editar Reserva: {reserva_data['titulo']}")
        
        with st.form("editar_reserva"):
            col1, col2 = st.columns(2)
            
            with col1:
                aula_seleccionada = st.selectbox(
                    "🏢 Aula",
                    options=list(aulas_opciones.keys()),
                    index=list(aulas_opciones.keys()).index(aula_actual),
                    key="edit_reserva_aula"
                )
                
                tipo_reserva = st.selectbox(
                    "🏷️ Tipo de Reserva",
                    ["GRUPO", "EVENTO", "MANTENIMIENTO", "BLOQUEADA"],
                    index=["GRUPO", "EVENTO", "MANTENIMIENTO", "BLOQUEADA"].index(reserva_data['tipo_reserva']),
                    key="edit_reserva_tipo"
                )
                
                titulo = st.text_input(
                    "📝 Título",
                    value=reserva_data['titulo'],
                    key="edit_reserva_titulo"
                )
            
            with col2:
                # Parsear fechas existentes
                fecha_inicio_actual = pd.to_datetime(reserva_data['fecha_inicio'])
                fecha_fin_actual = pd.to_datetime(reserva_data['fecha_fin'])
                
                fecha_reserva = st.date_input(
                    "📅 Fecha",
                    value=fecha_inicio_actual.date(),
                    key="edit_reserva_fecha"
                )
                
                col_hora1, col_hora2 = st.columns(2)
                with col_hora1:
                    hora_inicio = st.time_input(
                        "⏰ Hora Inicio",
                        value=fecha_inicio_actual.time(),
                        key="edit_reserva_hora_inicio"
                    )
                with col_hora2:
                    hora_fin = st.time_input(
                        "⏰ Hora Fin",
                        value=fecha_fin_actual.time(),
                        key="edit_reserva_hora_fin"
                    )
                
                estado = st.selectbox(
                    "📊 Estado",
                    ["PENDIENTE", "CONFIRMADA", "CANCELADA"],
                    index=["PENDIENTE", "CONFIRMADA", "CANCELADA"].index(reserva_data['estado']),
                    key="edit_reserva_estado"
                )
            
            descripcion = st.text_area(
                "📝 Descripción",
                value=reserva_data.get('descripcion', ''),
                key="edit_reserva_descripcion"
            )
            
            # Validaciones
            errores = []
            if not titulo:
                errores.append("El título es obligatorio")
            if hora_inicio >= hora_fin:
                errores.append("La hora de fin debe ser posterior a la de inicio")
            
            if errores:
                for error in errores:
                    st.error(f"⚠️ {error}")
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                submitted = st.form_submit_button(
                    "💾 Guardar Cambios", 
                    type="primary", 
                    use_container_width=True,
                    disabled=bool(errores)
                )
            
            with col_btn2:
                cancelar = st.form_submit_button(
                    "❌ Cancelar", 
                    use_container_width=True
                )
            
            if cancelar:
                if "editar_reserva_id" in st.session_state:
                    del st.session_state["editar_reserva_id"]
                st.rerun()
            
            if submitted and not errores:
                try:
                    # Crear datetime completos
                    fecha_inicio_completa = datetime.combine(fecha_reserva, hora_inicio)
                    fecha_fin_completa = datetime.combine(fecha_reserva, hora_fin)
                    
                    aula_id = aulas_opciones[aula_seleccionada]
                    
                    # Verificar conflictos (excluyendo la reserva actual)
                    conflictos = aulas_service.verificar_conflictos_reserva(
                        aula_id,
                        fecha_inicio_completa.isoformat(),
                        fecha_fin_completa.isoformat(),
                        excluir_reserva_id=reserva_id
                    )
                    
                    if conflictos:
                        st.error("❌ Ya existe otra reserva en este horario para esta aula")
                        return
                    
                    # Actualizar la reserva
                    datos_actualizados = {
                        "aula_id": aula_id,
                        "titulo": titulo,
                        "descripcion": descripcion,
                        "tipo_reserva": tipo_reserva,
                        "fecha_inicio": fecha_inicio_completa.isoformat(),
                        "fecha_fin": fecha_fin_completa.isoformat(),
                        "estado": estado,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    
                    success = aulas_service.actualizar_reserva(reserva_id, datos_actualizados)
                    
                    if success:
                        st.success("✅ Reserva actualizada correctamente")
                        if "editar_reserva_id" in st.session_state:
                            del st.session_state["editar_reserva_id"]
                        st.rerun()
                    else:
                        st.error("❌ Error al actualizar la reserva")
                        
                except Exception as e:
                    st.error(f"❌ Error procesando actualización: {e}")
                    
    except Exception as e:
        st.error(f"❌ Error cargando reserva para editar: {e}")

def mostrar_widget_estadisticas_rapidas(aulas_service):
    """Widget con estadísticas rápidas en la barra lateral"""
    
    try:
        stats = aulas_service.get_estadisticas_rapidas()
        
        st.sidebar.markdown("### 📊 Resumen Rápido")
        
        # Métricas compactas
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            st.metric("🏢 Aulas", stats.get('total_aulas', 0))
            st.metric("📅 Hoy", stats.get('reservas_hoy', 0))
        
        with col2:
            st.metric("✅ Activas", stats.get('aulas_activas', 0))
            ocupacion = stats.get('ocupacion_actual', 0)
            st.metric("📈 Ocupación", f"{ocupacion:.0f}%")
        
        # Próximas reservas
        proximas = aulas_service.get_proximas_reservas(limite=3)
        if proximas:
            st.sidebar.markdown("#### 🔔 Próximas Reservas")
            for reserva in proximas:
                fecha_hora = pd.to_datetime(reserva['fecha_inicio']).strftime('%d/%m %H:%M')
                st.sidebar.info(f"**{fecha_hora}**\n{reserva['aula_nombre']}: {reserva['titulo'][:20]}...")
        
        # Aulas disponibles ahora
        disponibles = aulas_service.get_aulas_disponibles_ahora()
        if disponibles:
            st.sidebar.success(f"🟢 {len(disponibles)} aulas disponibles ahora")
        else:
            st.sidebar.warning("🔴 Todas las aulas ocupadas")
            
    except Exception as e:
        st.sidebar.error(f"❌ Error en estadísticas: {e}")

def mostrar_notificaciones_aulas(aulas_service, session_state):
    """Sistema de notificaciones para eventos importantes"""
    
    if session_state.role not in ["admin", "gestor"]:
        return
    
    try:
        notificaciones = aulas_service.get_notificaciones_pendientes()
        
        if notificaciones:
            st.sidebar.markdown("### 🔔 Notificaciones")
            
            for notif in notificaciones[:5]:  # Máximo 5 notificaciones
                tipo = notif['tipo']
                mensaje = notif['mensaje']
                
                if tipo == 'CONFLICTO':
                    st.sidebar.error(f"⚠️ {mensaje}")
                elif tipo == 'MANTENIMIENTO':
                    st.sidebar.warning(f"🔧 {mensaje}")
                elif tipo == 'RECORDATORIO':
                    st.sidebar.info(f"📋 {mensaje}")
                else:
                    st.sidebar.info(f"ℹ️ {mensaje}")
            
            # Botón para marcar como leídas
            if st.sidebar.button("✅ Marcar todas como leídas", key="marcar_notif_leidas"):
                aulas_service.marcar_notificaciones_leidas()
                st.rerun()
                
    except Exception as e:
        st.sidebar.error(f"❌ Error en notificaciones: {e}")

def main(supabase, session_state):
    """Función principal del módulo de aulas con funcionalidades completas"""
    
    # Verificar permisos básicos
    if session_state.role not in ["admin", "gestor", "tutor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return
    
    # Inicializar servicio
    try:
        aulas_service = get_aulas_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error inicializando servicio de aulas: {e}")
        return
    
    # Widgets de la barra lateral
    with st.sidebar:
        mostrar_widget_estadisticas_rapidas(aulas_service)
        mostrar_notificaciones_aulas(aulas_service, session_state)
    
    # Título principal
    st.title("🏢 Gestión de Aulas")
    st.caption("Sistema completo de gestión de aulas y reservas para formación")
    
    # Verificar si hay una reserva para editar
    if st.session_state.get("editar_reserva_id"):
        mostrar_formulario_editar_reserva(
            aulas_service, 
            session_state, 
            st.session_state["editar_reserva_id"]
        )
        return
    
    # Tabs principales
    if session_state.role == "admin":
        tabs = st.tabs(["🏢 Aulas", "📅 Cronograma", "📋 Reservas", "📊 Métricas"])
    else:
        tabs = st.tabs(["🏢 Aulas", "📅 Cronograma", "📋 Reservas"])
    
    # TAB 1: Gestión de Aulas
    with tabs[0]:
        try:
            # Cargar datos de aulas
            df_aulas = aulas_service.get_aulas_con_empresa()
            
            # Mostrar alertas importantes
            alertas = aulas_service.get_alertas_aulas()
            for alerta in alertas:
                if alerta['tipo'] == 'ERROR':
                    st.error(f"❌ {alerta['mensaje']}")
                elif alerta['tipo'] == 'WARNING':
                    st.warning(f"⚠️ {alerta['mensaje']}")
                elif alerta['tipo'] == 'INFO':
                    st.info(f"ℹ️ {alerta['mensaje']}")
            
            # Columnas en dos partes
            col_tabla, col_form = st.columns([2, 1])
            
            with col_tabla:
                # Mostrar tabla y capturar selección
                aula_seleccionada = mostrar_tabla_aulas(df_aulas, session_state, aulas_service)
            
            with col_form:
                # Botón para crear nueva aula
                if session_state.role in ["admin", "gestor"]:
                    if st.button("➕ Nueva Aula", use_container_width=True, type="primary"):
                        st.session_state["crear_nueva_aula"] = True
                        st.rerun()
                
                # Mostrar formulario según el estado
                if st.session_state.get("crear_nueva_aula"):
                    mostrar_formulario_aula(None, aulas_service, session_state, es_creacion=True)
                    
                    if st.button("❌ Cancelar", key="cancelar_nueva_aula"):
                        del st.session_state["crear_nueva_aula"]
                        st.rerun()
                
                elif aula_seleccionada is not None:
                    if session_state.role in ["admin", "gestor"]:
                        mostrar_formulario_aula(aula_seleccionada, aulas_service, session_state)
                    else:
                        # Solo visualización para tutores
                        st.info("👁️ Modo solo lectura")
                        with st.expander("📋 Detalles del Aula"):
                            for key, value in aula_seleccionada.to_dict().items():
                                st.text(f"{key}: {value}")
                
                else:
                    st.info("👆 Selecciona un aula de la tabla para ver sus detalles")
                    
                    # Widget de aulas disponibles
                    disponibles_ahora = aulas_service.get_aulas_disponibles_ahora()
                    if disponibles_ahora:
                        st.success(f"🟢 {len(disponibles_ahora)} aulas disponibles ahora")
                        with st.expander("Ver aulas disponibles"):
                            for aula in disponibles_ahora:
                                st.write(f"• {aula['nombre']} (Capacidad: {aula['capacidad_maxima']})")
                    
        except Exception as e:
            st.error(f"❌ Error en gestión de aulas: {e}")
            st.exception(e)  # Para debugging
    
    # TAB 2: Cronograma
    with tabs[1]:
        try:
            # Verificar si streamlit-calendar está disponible
            if CALENDAR_AVAILABLE:
                mostrar_cronograma_fullcalendar(aulas_service, session_state)
            else:
                st.warning("📦 streamlit-calendar no está instalado. Usando vista alternativa.")
                mostrar_cronograma_alternativo(aulas_service, session_state)
                
                # Mostrar instrucciones de instalación
                with st.expander("💡 Cómo habilitar el calendario interactivo"):
                    st.code("pip install streamlit-calendar", language="bash")
                    st.markdown("Reinicia la aplicación después de la instalación.")
                    
        except Exception as e:
            st.error(f"❌ Error en cronograma: {e}")
            # Fallback automático a vista alternativa
            st.info("🔄 Cambiando a vista alternativa...")
            mostrar_cronograma_alternativo(aulas_service, session_state)
    
    # TAB 3: Reservas
    with tabs[2]:
        try:
            # Subtabs para reservas
            if session_state.role in ["admin", "gestor"]:
                sub_tabs = st.tabs(["📋 Lista", "➕ Nueva Reserva"])
                
                with sub_tabs[0]:
                    mostrar_lista_reservas(aulas_service, session_state)
                
                with sub_tabs[1]:
                    mostrar_formulario_reserva_manual(aulas_service, session_state)
            else:
                # Solo lista para tutores
                st.info("👁️ Solo puedes visualizar reservas")
                mostrar_lista_reservas(aulas_service, session_state)
                
        except Exception as e:
            st.error(f"❌ Error en reservas: {e}")
    
    # TAB 4: Métricas (Solo Admin)
    if session_state.role == "admin" and len(tabs) > 3:
        with tabs[3]:
            try:
                mostrar_metricas_admin(aulas_service, session_state)
            except Exception as e:
                st.error(f"❌ Error en métricas: {e}")

# Testing y desarrollo
if __name__ == "__main__":
    # Para testing del módulo
    st.set_page_config(
        page_title="Gestión de Aulas",
        page_icon="🏢",
        layout="wide"
    )
    
    # Mock session state para testing
    class MockSessionState:
        def __init__(self):
            self.role = "admin"
            self.user = {"id": 1, "empresa_id": 1}
    
    # Mock supabase para testing
    class MockSupabase:
        pass
    
    # Mensaje informativo para desarrolladores
    st.info("🧪 **Modo Testing Activado**")
    st.markdown("""
    Este módulo está siendo ejecutado en modo de desarrollo.
    
    **Para usar en producción:**
    1. Integra este archivo en tu estructura `pages/`
    2. Implementa `services/aulas_service.py`
    3. Configura las tablas de base de datos
    4. Instala dependencias: `pip install streamlit-calendar`
    """)
    
    try:
        main(MockSupabase(), MockSessionState())
    except Exception as e:
        st.error(f"❌ Error en modo testing: {e}")
        st.info("Este módulo necesita ser ejecutado desde la aplicación principal con los servicios configurados")
        
        # Mostrar estructura esperada del servicio
        with st.expander("📋 Estructura esperada del servicio"):
            st.code("""
# services/aulas_service.py
class AulasService:
    def get_aulas_con_empresa(self): pass
    def get_eventos_cronograma(self, fecha_inicio, fecha_fin, aulas_ids): pass
    def crear_aula(self, datos): pass
    def actualizar_aula(self, id, datos): pass
    def eliminar_aula(self, id): pass
    def crear_reserva(self, datos): pass
    def verificar_conflictos_reserva(self, aula_id, inicio, fin, excluir=None): pass
    def get_metricas_aulas(self): pass
    def get_estadisticas_rapidas(self): pass
    def get_proximas_reservas(self, limite=5): pass
    def get_aulas_disponibles_ahora(self): pass
    def get_notificaciones_pendientes(self): pass
    def get_alertas_aulas(self): pass
            """, language="python")
