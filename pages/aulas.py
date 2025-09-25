import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_calendar import calendar
from services.aulas_service import get_aulas_service
from utils import validar_texto_obligatorio, export_excel

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
        
        # Configuración del calendario
        calendar_options = {
            "editable": True,
            "selectable": True,
            "selectMirror": True,
            "dayMaxEvents": 3,
            "weekends": True,
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
            },
            "initialView": vista_inicial,
            "initialDate": fecha_inicio.isoformat(),
            "validRange": {
                "start": fecha_inicio.isoformat(),
                "end": fecha_fin.isoformat()
            },
            "height": 600,
            "slotMinTime": "07:00:00",
            "slotMaxTime": "22:00:00",
            "businessHours": {
                "daysOfWeek": [1, 2, 3, 4, 5],  # Lunes a Viernes
                "startTime": "08:00",
                "endTime": "19:00"
            },
            "eventDisplay": "block",
            "displayEventEnd": True,
            "nowIndicator": True,
            "locale": "es"
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
        calendar_result = calendar(
            events=eventos,
            options=calendar_options,
            custom_css=calendar_css,
            key="aulas_calendar"
        )
        
        # Mostrar información del evento seleccionado/clickeado
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
            st.markdown("**🔴 Bloqueada**")
            st.markdown("Aula no disponible")

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
        st.info("🚧 La gestión de reservas se implementará después del cronograma.")
    
    if session_state.role == "admin":
        with tab4:
            mostrar_metricas_aulas(aulas_service, session_state)

if __name__ == "__main__":
    main()
