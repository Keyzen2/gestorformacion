import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from services.aulas_service import get_aulas_service
from utils import export_excel

# Intentar importar streamlit-calendar, usar vista alternativa si falla
try:
    from streamlit_calendar import calendar
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False
    st.warning("streamlit-calendar no está disponible. Usando vista alternativa.")

def mostrar_tabla_aulas(df_aulas, session_state, aulas_service, titulo_tabla="Lista de Aulas"):
    """Tabla de aulas siguiendo el patrón de Streamlit 1.49"""
    if df_aulas.empty:
        st.info("No hay aulas para mostrar")
        return None

    st.markdown(f"### {titulo_tabla}")

    # Filtros arriba de la tabla
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_nombre = st.text_input("Nombre contiene", key="filtro_aula_nombre")
    with col2:
        filtro_ubicacion = st.text_input("Ubicación contiene", key="filtro_aula_ubicacion")
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
    df_display["Estado"] = df_display["activa"].apply(lambda x: "Activa" if x else "Inactiva")
    df_display["Capacidad"] = df_display["capacidad_maxima"].apply(lambda x: f"{x} personas")
    
    # Mostrar tabla con selección
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

    # Botones de acción
    col_exp, col_imp = st.columns([1, 1])
    with col_exp:
        if not df_filtrado.empty:
            fecha_str = datetime.now().strftime("%Y%m%d")
            filename = f"aulas_{fecha_str}.xlsx"
            export_excel(df_filtrado, filename=filename, label="Exportar Excel")
    with col_imp:
        if st.button("Actualizar", use_container_width=True, key="btn_actualizar_aulas"):
            aulas_service.limpiar_cache_aulas()
            st.rerun()

    # Retornar aula seleccionada
    if evento.selection.rows:
        return df_filtrado.iloc[evento.selection.rows[0]]
    return None

def mostrar_formulario_aula(aula_data, aulas_service, session_state, es_creacion=False):
    """Formulario de aula"""
    if es_creacion:
        st.subheader("Nueva Aula")
        datos = {}
    else:
        st.subheader(f"Editar {aula_data['nombre']}")
        datos = aula_data.copy()

    form_id = f"aula_{datos.get('id', 'nueva')}_{'crear' if es_creacion else 'editar'}"

    with st.form(form_id, clear_on_submit=es_creacion):
        st.markdown("### Información Básica")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input(
                "Nombre del Aula", 
                value=datos.get("nombre", ""), 
                key=f"{form_id}_nombre"
            )
            capacidad_maxima = st.number_input(
                "Capacidad Máxima", 
                min_value=1, 
                max_value=200, 
                value=int(datos.get("capacidad_maxima", 20)),
                key=f"{form_id}_capacidad"
            )
        
        with col2:
            ubicacion = st.text_input(
                "Ubicación", 
                value=datos.get("ubicacion", ""), 
                key=f"{form_id}_ubicacion"
            )
            activa = st.checkbox(
                "Aula Activa", 
                value=datos.get("activa", True),
                key=f"{form_id}_activa"
            )

        st.markdown("### Equipamiento")
        opciones_equipamiento = [
            "PROYECTOR", "PIZARRA_DIGITAL", "ORDENADORES", "AUDIO", 
            "AIRE_ACONDICIONADO", "CALEFACCION", "WIFI", "TELEVISION"
        ]
        
        equipamiento_actual = datos.get("equipamiento", [])
        equipamiento = st.multiselect(
            "Seleccionar equipamiento disponible",
            options=opciones_equipamiento,
            default=equipamiento_actual,
            key=f"{form_id}_equipamiento"
        )

        st.markdown("### Configuración Visual")
        color_cronograma = st.color_picker(
            "Color en Cronograma",
            value=datos.get("color_cronograma", "#3498db"),
            key=f"{form_id}_color"
        )

        observaciones = st.text_area(
            "Observaciones",
            value=datos.get("observaciones", ""),
            key=f"{form_id}_observaciones"
        )

        # Validaciones
        errores = []
        if not nombre:
            errores.append("Nombre del aula es obligatorio")
        if capacidad_maxima < 1:
            errores.append("Capacidad debe ser mayor a 0")
        
        if errores:
            st.error(f"Errores: {', '.join(errores)}")

        # Botones
        if es_creacion:
            submitted = st.form_submit_button("Crear Aula", type="primary")
        else:
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("Guardar Cambios", type="primary")
            with col_btn2:
                eliminar = st.form_submit_button("Eliminar") if session_state.role == "admin" else False

        # Procesamiento
        if submitted and not errores:
            try:
                datos_aula = {
                    "nombre": nombre,
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
                        st.success("Aula creada correctamente")
                        st.rerun()
                    else:
                        st.error("Error al crear el aula")
                else:
                    success = aulas_service.actualizar_aula(datos["id"], datos_aula)
                    if success:
                        st.success("Aula actualizada correctamente")
                        st.rerun()
                    else:
                        st.error("Error al actualizar el aula")
                        
            except Exception as e:
                st.error(f"Error procesando aula: {e}")

        # Manejar eliminación
        if 'eliminar' in locals() and eliminar:
            if st.session_state.get("confirmar_eliminar_aula"):
                try:
                    success = aulas_service.eliminar_aula(datos["id"])
                    if success:
                        st.success("Aula eliminada correctamente")
                        del st.session_state["confirmar_eliminar_aula"]
                        st.rerun()
                except Exception as e:
                    st.error(f"Error eliminando aula: {e}")
            else:
                st.session_state["confirmar_eliminar_aula"] = True
                st.warning("Presiona 'Eliminar' nuevamente para confirmar")

def mostrar_cronograma_simple(aulas_service, session_state):
    """Cronograma simple sin dependencias externas"""
    
    st.markdown("### Cronograma de Aulas")
    
    # Controles
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fecha_inicio = st.date_input(
            "Desde", 
            value=datetime.now().date(),
            key="cronograma_inicio"
        )
    
    with col2:
        fecha_fin = st.date_input(
            "Hasta", 
            value=datetime.now().date() + timedelta(days=7),
            key="cronograma_fin"
        )
    
    with col3:
        if st.button("Actualizar", key="cronograma_refresh"):
            st.rerun()
    
    # Obtener reservas
    try:
        df_reservas = aulas_service.get_reservas_periodo(
            fecha_inicio.isoformat() + "T00:00:00Z",
            fecha_fin.isoformat() + "T23:59:59Z"
        )
        
        if df_reservas.empty:
            st.info("No hay reservas en el período seleccionado")
            st.markdown("**Sugerencia:** Crea reservas en la pestaña 'Reservas' para ver el cronograma.")
            return
        
        # Mostrar reservas por día
        df_reservas['fecha'] = pd.to_datetime(df_reservas['fecha_inicio']).dt.date
        fechas_unicas = sorted(df_reservas['fecha'].unique())
        
        for fecha in fechas_unicas:
            reservas_dia = df_reservas[df_reservas['fecha'] == fecha].sort_values('fecha_inicio')
            
            st.markdown(f"#### {fecha.strftime('%A, %d de %B %Y')}")
            
            for _, reserva in reservas_dia.iterrows():
                inicio = pd.to_datetime(reserva['fecha_inicio'])
                fin = pd.to_datetime(reserva['fecha_fin'])
                
                # Color según tipo
                color_map = {
                    'GRUPO': 'green',
                    'EVENTO': 'blue', 
                    'MANTENIMIENTO': 'orange',
                    'BLOQUEADA': 'red'
                }
                color = color_map.get(reserva['tipo_reserva'], 'gray')
                
                col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
                
                with col1:
                    st.markdown(f"**{inicio.strftime('%H:%M')} - {fin.strftime('%H:%M')}**")
                
                with col2:
                    st.markdown(f"**{reserva['aula_nombre']}**")
                
                with col3:
                    st.markdown(f":{color}[{reserva['titulo']}]")
                
                with col4:
                    estado = "Confirmada" if reserva['estado'] == 'CONFIRMADA' else reserva['estado']
                    st.markdown(f"*{estado}*")
            
            st.divider()
        
        # Estadísticas
        st.markdown("### Resumen")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Reservas", len(df_reservas))
        
        with col2:
            aulas_ocupadas = df_reservas['aula_nombre'].nunique()
            st.metric("Aulas Utilizadas", aulas_ocupadas)
        
        with col3:
            dias_activos = len(fechas_unicas)
            st.metric("Días con Actividad", dias_activos)
        
    except Exception as e:
        st.error(f"Error cargando cronograma: {e}")

def mostrar_formulario_reserva_manual(aulas_service, session_state):
    """Formulario para crear reservas manuales"""
    
    st.markdown("#### Crear Nueva Reserva Manual")
    
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
                "Seleccionar Aula",
                options=list(aulas_dict.keys()),
                key="reserva_aula"
            )
            
            titulo = st.text_input(
                "Título de la Reserva",
                placeholder="Ej: Reunión de departamento",
                key="reserva_titulo"
            )
            
            tipo_reserva = st.selectbox(
                "Tipo de Reserva",
                options=["EVENTO", "MANTENIMIENTO", "BLOQUEADA"],
                key="reserva_tipo"
            )
        
        with col2:
            fecha_reserva = st.date_input(
                "Fecha",
                value=datetime.now().date(),
                min_value=datetime.now().date(),
                key="reserva_fecha"
            )
            
            col_hora1, col_hora2 = st.columns(2)
            with col_hora1:
                hora_inicio = st.time_input(
                    "Hora Inicio",
                    value=datetime.strptime("09:00", "%H:%M").time(),
                    key="reserva_hora_inicio"
                )
            
            with col_hora2:
                hora_fin = st.time_input(
                    "Hora Fin", 
                    value=datetime.strptime("10:00", "%H:%M").time(),
                    key="reserva_hora_fin"
                )
            
            responsable = st.text_input(
                "Responsable",
                value=session_state.user.get("nombre", ""),
                key="reserva_responsable"
            )
        
        observaciones = st.text_area(
            "Observaciones",
            placeholder="Comentarios adicionales...",
            key="reserva_observaciones"
        )
        
        # Botón de envío
        submitted = st.form_submit_button("Crear Reserva", type="primary")
        
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
            
            # Verificar disponibilidad
            if not aulas_service.verificar_disponibilidad_aula(aula_id, fecha_inicio_iso, fecha_fin_iso):
                conflictos = aulas_service.obtener_conflictos_detallados(aula_id, fecha_inicio_iso, fecha_fin_iso)
                
                st.error("El aula no está disponible en ese horario")
                
                if conflictos:
                    st.markdown("**Conflictos detectados:**")
                    for conflicto in conflictos:
                        st.warning(f"**{conflicto['titulo']}**: {conflicto['fecha_inicio']} - {conflicto['fecha_fin']}")
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
                st.success("Reserva creada correctamente")
                st.rerun()
            else:
                st.error("Error al crear la reserva")

def main(supabase, session_state):
    """Vista principal de Aulas"""
    aulas_service = get_aulas_service(supabase, session_state)
    
    st.title("Gestión de Aulas")
    
    # Tabs según rol
    if session_state.role == "admin":
        tab1, tab2, tab3, tab4 = st.tabs([
            "Gestión de Aulas", 
            "Cronograma", 
            "Reservas", 
            "Métricas"
        ])
    else:
        tab1, tab2, tab3 = st.tabs([
            "Mis Aulas", 
            "Cronograma", 
            "Reservas"
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
            if st.button("Crear Nueva Aula", type="primary", use_container_width=True):
                st.session_state.aula_creando = True
                st.rerun()
        
        with col2:
            if st.button("Actualizar Lista", use_container_width=True):
                aulas_service.limpiar_cache_aulas()
                st.rerun()
        
        # Mostrar formulario según estado
        if st.session_state.get("aula_creando"):
            mostrar_formulario_aula({}, aulas_service, session_state, es_creacion=True)
            if st.button("Cancelar Creación"):
                del st.session_state["aula_creando"]
                st.rerun()
        
        elif aula_seleccionada is not None:
            mostrar_formulario_aula(aula_seleccionada, aulas_service, session_state)
    
    with tab2:
        mostrar_cronograma_simple(aulas_service, session_state)
    
    with tab3:
        st.markdown("### Gestión de Reservas")
        
        # Subtabs para organizar mejor
        subtab1, subtab2 = st.tabs(["Nueva Reserva", "Lista de Reservas"])
        
        with subtab1:
            mostrar_formulario_reserva_manual(aulas_service, session_state)
        
        with subtab2:
            # Mostrar lista simple de reservas
            try:
                df_reservas = aulas_service.get_reservas_periodo(
                    (datetime.now() - timedelta(days=7)).isoformat() + "T00:00:00Z",
                    (datetime.now() + timedelta(days=30)).isoformat() + "T23:59:59Z"
                )
                
                if not df_reservas.empty:
                    # Formatear para mostrar
                    df_display = df_reservas.copy()
                    df_display['Fecha'] = pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%d/%m/%Y')
                    df_display['Hora'] = pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%H:%M')
                    
                    st.dataframe(
                        df_display[['Fecha', 'Hora', 'aula_nombre', 'titulo', 'tipo_reserva', 'estado']],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No hay reservas recientes")
                    
            except Exception as e:
                st.error(f"Error cargando reservas: {e}")
    
    if session_state.role == "admin":
        with tab4:
            # Métricas básicas
            try:
                metricas = aulas_service.get_estadisticas_aulas()
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Aulas", metricas.get("total_aulas", 0))
                
                with col2:
                    st.metric("Aulas Activas", metricas.get("aulas_activas", 0))
                
                with col3:
                    st.metric("Reservas Hoy", metricas.get("reservas_hoy", 0))
                
                with col4:
                    ocupacion = metricas.get("ocupacion_promedio", 0)
                    st.metric("Ocupación Promedio", f"{ocupacion}%")
                    
            except Exception as e:
                st.error(f"Error al cargar métricas: {e}")

if __name__ == "__main__":
    main()
