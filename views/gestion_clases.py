import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional
from services.clases_service import get_clases_service
from services.empresas_service import get_empresas_service
from services.participantes_service import get_participantes_service


# =========================
# GESTIÓN DE CLASES (TAB 1)
# =========================
def mostrar_gestion_clases(clases_service, empresas_service, session_state):
    """Gestión CRUD de clases."""
    st.header("📋 Gestión de Clases")
    
    # Cargar datos
    df_clases = clases_service.get_clases_con_empresa()
    
    if df_clases.empty:
        st.info("No hay clases registradas. Crea la primera clase abajo.")
    else:
        # Tabla de clases con filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filtro_nombre = st.text_input("🔍 Filtrar por nombre", key="filtro_clases_nombre")
        with col2:
            categorias_unicas = ["Todas"] + df_clases["categoria"].fillna("Sin categoría").unique().tolist()
            filtro_categoria = st.selectbox("🏷️ Filtrar por categoría", categorias_unicas, key="filtro_clases_categoria")
        with col3:
            filtro_estado = st.selectbox("📊 Estado", ["Todas", "Activas", "Inactivas"], key="filtro_clases_estado")
        
        # Aplicar filtros
        df_filtrado = df_clases.copy()
        
        if filtro_nombre:
            df_filtrado = df_filtrado[df_filtrado["nombre"].str.contains(filtro_nombre, case=False, na=False)]
        
        if filtro_categoria != "Todas":
            if filtro_categoria == "Sin categoría":
                df_filtrado = df_filtrado[df_filtrado["categoria"].isna()]
            else:
                df_filtrado = df_filtrado[df_filtrado["categoria"] == filtro_categoria]
        
        if filtro_estado == "Activas":
            df_filtrado = df_filtrado[df_filtrado["activa"] == True]
        elif filtro_estado == "Inactivas":
            df_filtrado = df_filtrado[df_filtrado["activa"] == False]
        
        # Mostrar tabla
        if not df_filtrado.empty:
            st.markdown(f"#### 📊 {len(df_filtrado)} clases encontradas")
            
            evento = st.dataframe(
                df_filtrado[["nombre", "categoria", "descripcion", "empresa_nombre", "activa", "created_at"]],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "nombre": "🏃‍♀️ Clase",
                    "categoria": "🏷️ Categoría",
                    "descripcion": "📝 Descripción",
                    "empresa_nombre": "🏢 Empresa",
                    "activa": st.column_config.CheckboxColumn("✅ Activa"),
                    "created_at": st.column_config.DatetimeColumn("📅 Creada", format="DD/MM/YYYY")
                }
            )
            
            # Formulario de edición si hay selección
            if evento.selection.rows:
                clase_seleccionada = df_filtrado.iloc[evento.selection.rows[0]]
                st.divider()
                mostrar_formulario_clase(clases_service, empresas_service, session_state, clase_seleccionada, es_creacion=False)
        else:
            st.warning("No se encontraron clases con los filtros aplicados")
    
    # Formulario de creación
    st.divider()
    mostrar_formulario_clase(clases_service, empresas_service, session_state, {}, es_creacion=True)

def mostrar_formulario_clase(clases_service, empresas_service, session_state, clase_data, es_creacion=False):
    """Formulario para crear/editar clases."""
    
    titulo = "➕ Crear Clase" if es_creacion else f"✏️ Editar Clase: {clase_data['nombre']}"
    
    with st.container(border=True):
        st.subheader(titulo)
        
        form_key = f"clase_{'nueva' if es_creacion else clase_data['id']}"
        
        with st.form(form_key, clear_on_submit=es_creacion):
            col1, col2 = st.columns(2)
            
            with col1:
                nombre = st.text_input(
                    "Nombre de la clase",
                    value=clase_data.get("nombre", ""),
                    help="Ej: Pilates Principiantes, Yoga Avanzado"
                )
                
                categoria = st.selectbox(
                    "Categoría",
                    ["", "Pilates", "Yoga", "Fitness", "Natación", "Danza", "Artes Marciales", "Otro"],
                    index=["", "Pilates", "Yoga", "Fitness", "Natación", "Danza", "Artes Marciales", "Otro"].index(clase_data.get("categoria", "")) if clase_data.get("categoria", "") in ["", "Pilates", "Yoga", "Fitness", "Natación", "Danza", "Artes Marciales", "Otro"] else 0
                )
                
                if categoria == "Otro":
                    categoria_personalizada = st.text_input("Especificar categoría")
                    if categoria_personalizada:
                        categoria = categoria_personalizada
            
            with col2:
                # Selector de empresa
                if session_state.role == "admin":
                    df_empresas = empresas_service.get_empresas_con_jerarquia()
                    empresa_options = {f"{row['nombre']} ({row.get('tipo_empresa', 'N/A')})": row["id"] for _, row in df_empresas.iterrows()}
                    
                    empresa_actual = ""
                    if not es_creacion and clase_data.get("empresa_id"):
                        empresa_actual = next(
                            (k for k, v in empresa_options.items() if v == clase_data["empresa_id"]), 
                            ""
                        )
                    
                    empresa_seleccionada = st.selectbox(
                        "Empresa",
                        [""] + list(empresa_options.keys()),
                        index=list(empresa_options.keys()).index(empresa_actual) + 1 if empresa_actual else 0
                    )
                    
                    empresa_id = empresa_options.get(empresa_seleccionada) if empresa_seleccionada else None
                    
                else:
                    # Para gestores, obtener nombre de empresa
                    empresa_id = session_state.user.get("empresa_id")
                    
                    if empresa_id:
                        try:
                            # Buscar nombre de empresa en el DataFrame ya cargado
                            df_empresas = empresas_service.get_empresas_con_jerarquia()
                            empresa_row = df_empresas[df_empresas["id"] == empresa_id]
                            
                            if not empresa_row.empty:
                                empresa_nombre = empresa_row.iloc[0]["nombre"]
                            else:
                                # Fallback: consulta directa
                                empresa_info = empresas_service.supabase.table("empresas").select("nombre").eq("id", empresa_id).execute()
                                empresa_nombre = empresa_info.data[0]["nombre"] if empresa_info.data else "Empresa no encontrada"
                        except Exception as e:
                            print(f"Error cargando empresa: {e}")
                            empresa_nombre = "Error cargando empresa"
                    else:
                        empresa_nombre = "Sin empresa asignada"
                        empresa_id = None
                    
                    st.info(f"Empresa: {empresa_nombre}")
                
                activa = st.checkbox(
                    "Clase activa",
                    value=clase_data.get("activa", True),
                    help="Solo las clases activas aparecen en reservas"
                )
            
            descripcion = st.text_area(
                "Descripción",
                value=clase_data.get("descripcion", ""),
                help="Descripción de la clase, nivel, requisitos, etc."
            )
            
            # Validaciones
            errores = []
            if not nombre:
                errores.append("Nombre requerido")
            if not categoria:
                errores.append("Categoría requerida")
            if not empresa_id:
                errores.append("Empresa requerida")
            
            if errores:
                st.warning(f"⚠️ Campos requeridos: {', '.join(errores)}")
            
            # Botones
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                submitted = st.form_submit_button(
                    "➕ Crear Clase" if es_creacion else "💾 Guardar Cambios",
                    type="primary",
                    use_container_width=True
                )
            
            with col_btn2:
                if not es_creacion and session_state.role == "admin":
                    eliminar = st.form_submit_button(
                        "🗑️ Eliminar",
                        type="secondary",
                        use_container_width=True
                    )
                else:
                    eliminar = False
            
            # Procesamiento
            if submitted:
                if errores:
                    st.error(f"❌ Corrige estos errores: {', '.join(errores)}")
                else:
                    datos_clase = {
                        "nombre": nombre,
                        "descripcion": descripcion,
                        "categoria": categoria,
                        "color_cronograma": color_cronograma,
                        "activa": activa,
                        "empresa_id": empresa_id
                    }
                    
                    if es_creacion:
                        success, clase_id = clases_service.crear_clase(datos_clase)
                        if success:
                            st.success("✅ Clase creada correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error creando la clase")
                    else:
                        success = clases_service.actualizar_clase(clase_data["id"], datos_clase)
                        if success:
                            st.success("✅ Clase actualizada correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error actualizando la clase")
            
            if eliminar:
                if st.session_state.get("confirmar_eliminar_clase"):
                    success = clases_service.eliminar_clase(clase_data["id"])
                    if success:
                        st.success("✅ Clase eliminada correctamente")
                        del st.session_state["confirmar_eliminar_clase"]
                        st.rerun()
                    else:
                        st.error("❌ No se puede eliminar. La clase tiene horarios o reservas activas.")
                else:
                    st.session_state["confirmar_eliminar_clase"] = True
                    st.warning("⚠️ Pulsa nuevamente para confirmar eliminación")

# =========================
# GESTIÓN DE HORARIOS - FUNCIÓN DE FORMULARIO (PRIMERO)
# =========================
def mostrar_formulario_horario(clases_service, clase_id, horario_data, es_creacion=False):
    """Formulario para crear/editar horarios CON selector de aula"""
    
    form_key = f"horario_{'nuevo' if es_creacion else horario_data['id']}"
    
    with st.form(form_key, clear_on_submit=es_creacion):
        if not es_creacion:
            st.markdown(f"**Editando horario: {horario_data['dia_nombre']} {horario_data['hora_inicio']}-{horario_data['hora_fin']}**")
        
        # === SELECTOR DE AULA ===
        st.markdown("#### 🏫 Asignación de Aula")
        
        aula_id = None
        aulas_opciones = {}
        
        try:
            from services.aulas_service import get_aulas_service
            aulas_service = get_aulas_service(
                clases_service.supabase, 
                clases_service.session_state
            )
            df_aulas = aulas_service.get_aulas_con_empresa()
            
            if not df_aulas.empty:
                df_aulas_activas = df_aulas[df_aulas['activa'] == True]
                
                aulas_opciones = {
                    f"{row['nombre']} - Cap: {row['capacidad_maxima']} ({row.get('ubicacion', 'N/A')})": row['id']
                    for _, row in df_aulas_activas.iterrows()
                }
                
                aula_actual = ""
                if not es_creacion and horario_data.get("aula_id"):
                    aula_match = df_aulas[df_aulas['id'] == horario_data['aula_id']]
                    if not aula_match.empty:
                        aula_row = aula_match.iloc[0]
                        aula_actual = f"{aula_row['nombre']} - Cap: {aula_row['capacidad_maxima']} ({aula_row.get('ubicacion', 'N/A')})"
                
                aula_seleccionada = st.selectbox(
                    "Aula asignada",
                    ["Sin aula asignada"] + list(aulas_opciones.keys()),
                    index=(
                        list(aulas_opciones.keys()).index(aula_actual) + 1 
                        if aula_actual and aula_actual in aulas_opciones.keys() else 0
                    ),
                    help="Selecciona el aula donde se impartirá la clase",
                    key=f"{form_key}_aula"
                )
                
                aula_id = aulas_opciones.get(aula_seleccionada) if aula_seleccionada != "Sin aula asignada" else None
                
                if aula_id:
                    aula_info = df_aulas[df_aulas['id'] == aula_id].iloc[0]
                    st.info(f"✅ Aula: **{aula_info['nombre']}** | Capacidad: {aula_info['capacidad_maxima']}")
            else:
                st.warning("No hay aulas disponibles")
        
        except Exception as e:
            st.error(f"Error cargando aulas: {e}")
        
        st.markdown("---")
        
        # === DÍA Y HORAS ===
        col1, col2 = st.columns([1, 2])
        
        with col1:
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dia_actual = int(horario_data.get("dia_semana", 0))
            
            dia_semana = st.selectbox(
                "Día de la semana",
                range(7),
                format_func=lambda x: dias_semana[x],
                index=dia_actual,
                key=f"{form_key}_dia"
            )
        
        with col2:
            col_hora1, col_hora2 = st.columns(2)
            
            with col_hora1:
                hora_inicio = st.time_input(
                    "Hora inicio",
                    value=time.fromisoformat(horario_data["hora_inicio"]) if not es_creacion and horario_data.get("hora_inicio") else time(9, 0),
                    key=f"{form_key}_hora_inicio"
                )
            
            with col_hora2:
                hora_fin = st.time_input(
                    "Hora fin",
                    value=time.fromisoformat(horario_data["hora_fin"]) if not es_creacion and horario_data.get("hora_fin") else time(10, 0),
                    key=f"{form_key}_hora_fin"
                )
        
        # === CAPACIDAD Y ESTADO ===
        col1, col2 = st.columns(2)
        
        with col1:
            capacidad_maxima = st.number_input(
                "Capacidad máxima",
                min_value=1,
                max_value=100,
                value=horario_data.get("capacidad_maxima", 20),
                help="Número máximo de participantes",
                key=f"{form_key}_capacidad"
            )
        
        with col2:
            activo = st.checkbox(
                "Horario activo",
                value=horario_data.get("activo", True),
                help="Solo los horarios activos aparecen para reserva",
                key=f"{form_key}_activo"
            )
        
        # === VALIDACIONES ===
        errores = []
        advertencias = []
        
        if hora_inicio >= hora_fin:
            errores.append("La hora de fin debe ser posterior a la de inicio")
        
        if not aula_id:
            advertencias.append("Sin aula asignada: No aparecerá en el cronograma de aulas")
        
        if errores:
            for error in errores:
                st.error(f"❌ {error}")
        
        if advertencias:
            for advertencia in advertencias:
                st.warning(f"⚠️ {advertencia}")
        
        st.markdown("---")
        
        # === BOTONES ===
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            submitted = st.form_submit_button(
                "Crear Horario" if es_creacion else "Guardar Cambios",
                type="primary",
                disabled=bool(errores),
                use_container_width=True
            )
        
        with col_btn2:
            if not es_creacion:
                eliminar = st.form_submit_button(
                    "Eliminar", 
                    type="secondary",
                    use_container_width=True
                )
            else:
                eliminar = False
        
        # === PROCESAMIENTO ===
        if submitted:
            if errores:
                st.error("Corrige los errores antes de continuar")
            else:
                datos_horario = {
                    "clase_id": clase_id,
                    "dia_semana": dia_semana,
                    "hora_inicio": hora_inicio.strftime("%H:%M:%S"),
                    "hora_fin": hora_fin.strftime("%H:%M:%S"),
                    "capacidad_maxima": capacidad_maxima,
                    "aula_id": aula_id,
                    "activo": activo
                }
                
                if es_creacion:
                    success, mensaje = clases_service.crear_horario(datos_horario)
                    if success:
                        st.success("Horario creado correctamente")
                        if aula_id:
                            st.info("Este horario aparecerá en el cronograma de aulas")
                        st.rerun()
                    else:
                        st.error(f"Error creando el horario: {mensaje}")
                else:
                    success = clases_service.actualizar_horario(horario_data["id"], datos_horario)
                    if success:
                        st.success("Horario actualizado correctamente")
                        st.rerun()
                    else:
                        st.error("Error actualizando el horario")
        
        if eliminar:
            confirmar_key = f"confirmar_eliminar_horario_{horario_data['id']}"
            if st.session_state.get(confirmar_key):
                success = clases_service.eliminar_horario(horario_data["id"])
                if success:
                    st.success("Horario eliminado correctamente")
                    del st.session_state[confirmar_key]
                    st.rerun()
                else:
                    st.error("No se puede eliminar. El horario tiene reservas futuras.")
            else:
                st.session_state[confirmar_key] = True
                st.warning("Pulsa nuevamente para confirmar eliminación")

# =========================
# GESTIÓN DE HORARIOS - FUNCIÓN PRINCIPAL (DESPUÉS)
# =========================
def mostrar_gestion_horarios(clases_service, session_state):
    """Gestión de horarios por clase"""
    st.header("⏰ Gestión de Horarios")
    
    df_clases = clases_service.get_clases_con_empresa()
    
    if df_clases.empty:
        st.warning("Primero debes crear clases antes de gestionar horarios")
        return
    
    clases_activas = df_clases[df_clases["activa"] == True]
    
    if clases_activas.empty:
        st.warning("No hay clases activas disponibles")
        return
    
    tab_lista, tab_crear = st.tabs(["📋 Lista de Horarios", "➕ Crear Nuevo Horario"])
    
    # TAB 1: Lista
    with tab_lista:
        st.markdown("### 🔍 Filtros")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            modo_vista = st.radio(
                "Vista",
                ["Ver todos", "Filtrar por clase"],
                horizontal=True,
                key="modo_vista_horarios"
            )
        
        with col2:
            if modo_vista == "Filtrar por clase":
                clase_options = {
                    f"{row['nombre']} ({row['empresa_nombre']})": row["id"] 
                    for _, row in clases_activas.iterrows()
                }
                
                clase_seleccionada_nombre = st.selectbox(
                    "Clase",
                    list(clase_options.keys()),
                    key="selector_clase_filtro"
                )
                
                clase_id_filtro = clase_options[clase_seleccionada_nombre]
            else:
                clase_id_filtro = None
        
        with col3:
            filtro_activo = st.selectbox(
                "Estado",
                ["Todos", "Activos", "Inactivos"],
                key="filtro_estado_horarios"
            )
        
        st.markdown("---")
        
        try:
            df_horarios = clases_service.get_horarios_con_clase(clase_id_filtro)
            
            if not df_horarios.empty:
                # Aplicar filtro de estado
                if filtro_activo == "Activos":
                    df_horarios = df_horarios[df_horarios["activo"] == True]
                elif filtro_activo == "Inactivos":
                    df_horarios = df_horarios[df_horarios["activo"] == False]
            
            if not df_horarios.empty:
                # Crear columna display para aula
                if 'aula_nombre' in df_horarios.columns:
                    df_horarios['aula_display'] = df_horarios['aula_nombre'].apply(
                        lambda x: f'✅ {x}' if pd.notna(x) and x else '⚠️ Sin aula'
                    )
                    columnas_mostrar = ["clase_nombre", "dia_nombre", "hora_inicio", "hora_fin", 
                                       "capacidad_maxima", "aula_display", "activo"]
                else:
                    columnas_mostrar = ["clase_nombre", "dia_nombre", "hora_inicio", "hora_fin", 
                                       "capacidad_maxima", "activo"]
                
                st.info(f"📊 {len(df_horarios)} horarios encontrados")
                
                evento_horario = st.dataframe(
                    df_horarios[columnas_mostrar],
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config={
                        "clase_nombre": "Clase",
                        "dia_nombre": "Día",
                        "hora_inicio": "Inicio",
                        "hora_fin": "Fin",
                        "capacidad_maxima": "Capacidad",
                        "aula_display": "Aula",
                        "activo": st.column_config.CheckboxColumn("Activo")
                    }
                )
                
                # Editar horario seleccionado
                if evento_horario.selection.rows:
                    horario_seleccionado = df_horarios.iloc[evento_horario.selection.rows[0]]
                    st.markdown("---")
                    st.markdown("### ✏️ Editar Horario")
                    
                    # Convertir a dict para pasar al formulario
                    horario_dict = horario_seleccionado.to_dict()
                    
                    mostrar_formulario_horario(
                        clases_service, 
                        horario_dict["clase_id"], 
                        horario_dict, 
                        es_creacion=False
                    )
            else:
                st.info("No hay horarios que coincidan con los filtros")
        
        except Exception as e:
            st.error(f"Error cargando horarios: {e}")
            import traceback
            traceback.print_exc()
    
    # TAB 2: Crear
    with tab_crear:
        st.markdown("### ➕ Crear Nuevo Horario")
        
        clase_options = {
            f"{row['nombre']} ({row['empresa_nombre']})": row["id"] 
            for _, row in clases_activas.iterrows()
        }
        
        clase_seleccionada = st.selectbox(
            "Selecciona la clase para el nuevo horario",
            list(clase_options.keys()),
            key="selector_clase_crear",
            help="Elige la clase a la que quieres añadir un horario"
        )
        
        clase_id_crear = clase_options[clase_seleccionada]
        
        st.markdown("---")
        
        # Formulario de creación (con datos vacíos)
        mostrar_formulario_horario(clases_service, clase_id_crear, {}, es_creacion=True)
        
# =========================
# GESTIÓN DE RESERVAS (TAB 3)
# =========================
def mostrar_gestion_reservas(clases_service, participantes_service, session_state):
    """Gestión de reservas y asistencias."""
    st.header("📅 Gestión de Reservas")
    
    # Filtros de fecha
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fecha_inicio = st.date_input(
            "Desde",
            value=date.today() - timedelta(days=7),
            key="reservas_fecha_inicio"
        )
    
    with col2:
        fecha_fin = st.date_input(
            "Hasta",
            value=date.today() + timedelta(days=7),
            key="reservas_fecha_fin"
        )
    
    with col3:
        estado_filtro = st.selectbox(
            "Estado",
            ["Todas", "Reservadas", "Asistió", "No Asistió", "Canceladas"],
            key="filtro_estado_reservas"
        )
    
    if fecha_inicio > fecha_fin:
        st.error("La fecha de inicio debe ser anterior a la fecha de fin")
        return
    
    # Obtener reservas usando el servicio
    try:
        df_reservas = clases_service.get_reservas_periodo(fecha_inicio, fecha_fin, estado_filtro)
        
        if df_reservas.empty:
            st.info("No hay reservas en el período seleccionado")
        else:
            st.markdown(f"#### 📊 {len(df_reservas)} reservas encontradas")
            
            # Mostrar reservas con avatar usando st.data_editor
            evento_reserva = st.dataframe(
                df_reservas,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "avatar_url": st.column_config.ImageColumn(
                        "Avatar",
                        width="small",
                        help="Foto del participante"
                    ),
                    "fecha_clase": st.column_config.DateColumn(
                        "Fecha",
                        format="DD/MM/YYYY"
                    ),
                    "participante_nombre": "Participante",
                    "clase_nombre": "Clase",
                    "horario": "Horario",
                    "estado": "Estado"
                }
            )
            
            # Gestión de asistencia para reserva seleccionada
            if evento_reserva.selection.rows:
                reserva_seleccionada = df_reservas.iloc[evento_reserva.selection.rows[0]]
                mostrar_gestion_asistencia(clases_service, reserva_seleccionada)
    
    except Exception as e:
        st.error(f"Error cargando reservas: {e}")
        import traceback
        traceback.print_exc()

def mostrar_gestion_asistencia(clases_service, reserva_data):
    """Formulario para gestionar asistencia."""
    st.divider()
    st.markdown("#### ✅ Gestión de Asistencia")
    
    with st.container(border=True):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write(f"**Participante:** {reserva_data['participante_nombre']}")
            st.write(f"**Clase:** {reserva_data['clase_nombre']}")
            st.write(f"**Fecha:** {reserva_data['fecha_clase']}")
            st.write(f"**Horario:** {reserva_data['horario']}")
            st.write(f"**Estado actual:** {reserva_data['estado']}")
        
        with col2:
            if reserva_data["estado"] == "RESERVADA":
                col_asistio, col_no_asistio = st.columns(2)
                
                with col_asistio:
                    if st.button("✅ Asistió", type="primary", use_container_width=True):
                        success = clases_service.marcar_asistencia(reserva_data["id"], True)
                        if success:
                            st.success("Asistencia marcada")
                            st.rerun()
                
                with col_no_asistio:
                    if st.button("❌ No Asistió", type="secondary", use_container_width=True):
                        success = clases_service.marcar_asistencia(reserva_data["id"], False)
                        if success:
                            st.success("No asistencia marcada")
                            st.rerun()
            else:
                st.info(f"Estado: {reserva_data['estado']}")

# =========================
# MÉTRICAS Y REPORTES (TAB 4)
# =========================
def mostrar_metricas_clases(clases_service, session_state):
    """Dashboard de métricas y reportes."""
    st.header("📊 Métricas y Reportes")
    
    # Obtener estadísticas
    stats = clases_service.get_estadisticas_clases()
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🏃‍♀️ Total Clases", stats.get("total_clases", 0))
    with col2:
        st.metric("✅ Clases Activas", stats.get("clases_activas", 0))
    with col3:
        st.metric("📅 Reservas Hoy", stats.get("reservas_hoy", 0))
    with col4:
        st.metric("👥 Participantes Suscritos", stats.get("participantes_suscritos", 0))
    
    # Ocupación promedio
    st.markdown("#### 📈 Ocupación Promedio")
    ocupacion = stats.get("ocupacion_promedio", 0)
    st.progress(ocupacion / 100, f"{ocupacion}% de ocupación")
    
    # Reportes detallados
    st.markdown("#### 📋 Reportes Detallados")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fecha_reporte_inicio = st.date_input(
            "Desde",
            value=date.today() - timedelta(days=30),
            key="reporte_fecha_inicio"
        )
    
    with col2:
        fecha_reporte_fin = st.date_input(
            "Hasta",
            value=date.today(),
            key="reporte_fecha_fin"
        )
    
    if st.button("📊 Generar Reporte de Ocupación", type="primary"):
        try:
            df_ocupacion = clases_service.get_ocupacion_detallada(fecha_reporte_inicio, fecha_reporte_fin)
            
            if not df_ocupacion.empty:
                st.markdown("#### 📈 Ocupación por Clase")
                st.dataframe(
                    df_ocupacion,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "clase_nombre": "🏃‍♀️ Clase",
                        "categoria": "🏷️ Categoría",
                        "dia_semana": "📅 Día",
                        "horario": "⏰ Horario",
                        "capacidad_maxima": "👥 Capacidad",
                        "reservas_activas": "✅ Reservas",
                        "porcentaje_ocupacion": st.column_config.ProgressColumn(
                            "📊 Ocupación",
                            min_value=0,
                            max_value=100
                        )
                    }
                )
                
                # Exportar datos
                if st.button("📥 Exportar a CSV"):
                    csv = df_ocupacion.to_csv(index=False)
                    st.download_button(
                        "Descargar reporte",
                        data=csv,
                        file_name=f"ocupacion_clases_{fecha_reporte_inicio}_{fecha_reporte_fin}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("No hay datos de ocupación para el período seleccionado")
                
        except Exception as e:
            st.error(f"Error generando reporte: {e}")

# =========================
# MAIN FUNCTION
# =========================
def render(supabase, session_state):
    st.title("🏃‍♀️ Gestión de Clases")
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.error("🔒 No tienes permisos para acceder a esta sección")
        st.info("Esta sección está disponible solo para Administradores y Gestores")
        return
    
    # Cargar servicios
    clases_service = get_clases_service(supabase, session_state)
    empresas_service = get_empresas_service(supabase, session_state)
    participantes_service = get_participantes_service(supabase, session_state)
    
    # Mostrar información del usuario
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"👤 Usuario: {session_state.user.get('nombre', 'Usuario')} ({session_state.role})")
    with col2:
        if session_state.role == "gestor":
            st.caption(f"🏢 Empresa: {session_state.user.get('empresa_nombre', 'N/A')}")
    
    # Tabs principales
    tabs = st.tabs([
        "📋 Clases",
        "⏰ Horarios", 
        "📅 Reservas",
        "📊 Métricas"
    ])
    
    with tabs[0]:
        mostrar_gestion_clases(clases_service, empresas_service, session_state)
    
    with tabs[1]:
        mostrar_gestion_horarios(clases_service, session_state)
    
    with tabs[2]:
        mostrar_gestion_reservas(clases_service, participantes_service, session_state)
    
    with tabs[3]:
        mostrar_metricas_clases(clases_service, session_state)

