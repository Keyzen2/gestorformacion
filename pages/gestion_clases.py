import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional
from services.clases_service import get_clases_service
from services.empresas_service import get_empresas_service
from services.participantes_service import get_participantes_service

# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="🏃‍♀️ Gestión de Clases",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    st.markdown("### ➕ Crear Nueva Clase")
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
                    # Para gestores, usar su empresa automáticamente
                    empresa_id = session_state.user.get("empresa_id")
                    st.info(f"Empresa: {session_state.user.get('empresa_nombre', 'Tu empresa')}")
                
                color_cronograma = st.color_picker(
                    "Color en cronograma",
                    value=clase_data.get("color_cronograma", "#3498db"),
                    help="Color que aparecerá en el calendario"
                )
                
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
# GESTIÓN DE HORARIOS (TAB 2)
# =========================
def mostrar_gestion_horarios(clases_service, session_state):
    """Gestión de horarios por clase."""
    st.header("⏰ Gestión de Horarios")
    
    # Cargar clases disponibles
    df_clases = clases_service.get_clases_con_empresa()
    
    if df_clases.empty:
        st.warning("Primero debes crear clases antes de gestionar horarios")
        return
    
    # Selector de clase
    clases_activas = df_clases[df_clases["activa"] == True]
    clase_options = {f"{row['nombre']} ({row['empresa_nombre']})": row["id"] for _, row in clases_activas.iterrows()}
    
    if not clase_options:
        st.warning("No hay clases activas disponibles")
        return
    
    clase_seleccionada = st.selectbox(
        "Seleccionar clase para gestionar horarios",
        list(clase_options.keys()),
        key="selector_clase_horarios"
    )
    
    if clase_seleccionada:
        clase_id = clase_options[clase_seleccionada]
        
        # Cargar horarios de la clase
        df_horarios = clases_service.get_horarios_con_clase(clase_id)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("#### 📅 Horarios Actuales")
            
            if not df_horarios.empty:
                # Tabla de horarios
                evento_horario = st.dataframe(
                    df_horarios[["dia_nombre", "hora_inicio", "hora_fin", "capacidad_maxima", "activo"]],
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config={
                        "dia_nombre": "📅 Día",
                        "hora_inicio": "🕐 Inicio",
                        "hora_fin": "🕐 Fin",
                        "capacidad_maxima": "👥 Capacidad",
                        "activo": st.column_config.CheckboxColumn("✅ Activo")
                    }
                )
                
                # Editar horario seleccionado
                if evento_horario.selection.rows:
                    horario_seleccionado = df_horarios.iloc[evento_horario.selection.rows[0]]
                    st.divider()
                    mostrar_formulario_horario(clases_service, clase_id, horario_seleccionado, es_creacion=False)
            else:
                st.info("Esta clase no tiene horarios definidos")
        
        with col2:
            st.markdown("#### ➕ Nuevo Horario")
            mostrar_formulario_horario(clases_service, clase_id, {}, es_creacion=True)

def mostrar_formulario_horario(clases_service, clase_id, horario_data, es_creacion=False):
    """Formulario para crear/editar horarios."""
    
    form_key = f"horario_{'nuevo' if es_creacion else horario_data['id']}"
    
    with st.form(form_key, clear_on_submit=es_creacion):
        if not es_creacion:
            st.markdown(f"**Editando horario: {horario_data['dia_nombre']} {horario_data['hora_inicio']}-{horario_data['hora_fin']}**")
        
        # Día de la semana
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        dia_actual = horario_data.get("dia_semana", 0)
        
        dia_semana = st.selectbox(
            "Día de la semana",
            range(7),
            format_func=lambda x: dias_semana[x],
            index=dia_actual
        )
        
        # Horarios
        col_hora1, col_hora2 = st.columns(2)
        
        with col_hora1:
            hora_inicio = st.time_input(
                "Hora inicio",
                value=time.fromisoformat(horario_data["hora_inicio"]) if not es_creacion and horario_data.get("hora_inicio") else time(9, 0)
            )
        
        with col_hora2:
            hora_fin = st.time_input(
                "Hora fin",
                value=time.fromisoformat(horario_data["hora_fin"]) if not es_creacion and horario_data.get("hora_fin") else time(10, 0)
            )
        
        # Capacidad
        capacidad_maxima = st.number_input(
            "Capacidad máxima",
            min_value=1,
            max_value=100,
            value=horario_data.get("capacidad_maxima", 20),
            help="Número máximo de participantes por clase"
        )
        
        # Estado activo
        activo = st.checkbox(
            "Horario activo",
            value=horario_data.get("activo", True),
            help="Solo los horarios activos aparecen para reserva"
        )
        
        # Validaciones
        errores = []
        if hora_inicio >= hora_fin:
            errores.append("La hora de fin debe ser posterior a la de inicio")
        
        # Verificar conflictos de horario
        if es_creacion or (hora_inicio != time.fromisoformat(horario_data["hora_inicio"]) or 
                          hora_fin != time.fromisoformat(horario_data["hora_fin"]) or 
                          dia_semana != horario_data["dia_semana"]):
            
            # Aquí podrías verificar conflictos con otros horarios de la misma clase
            pass
        
        if errores:
            st.warning(f"⚠️ Errores: {', '.join(errores)}")
            
        if st.checkbox("Mostrar debug", key=f"debug_{form_key}"):
            st.write("Datos del formulario:")
            st.write(f"- Clase ID: {clase_id}")
            st.write(f"- Día: {dia_semana}")
            st.write(f"- Hora inicio: {hora_inicio}")
            st.write(f"- Hora fin: {hora_fin}")
            st.write(f"- Capacidad: {capacidad_maxima}")
            
        # Botones
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            submitted = st.form_submit_button(
                "➕ Crear Horario" if es_creacion else "💾 Guardar",
                type="primary",
                disabled=bool(errores)
            )
        
        with col_btn2:
            if not es_creacion:
                eliminar = st.form_submit_button("🗑️ Eliminar", type="secondary")
            else:
                eliminar = False
        
        # Procesamiento
        if submitted and not errores:
            datos_horario = {
                "clase_id": clase_id,
                "dia_semana": dia_semana,
                "hora_inicio": hora_inicio.isoformat(),
                "hora_fin": hora_fin.isoformat(),
                "capacidad_maxima": capacidad_maxima,
                "activo": activo
            }
            
            st.write("Datos a enviar:", datos_horario)
            
            success, horario_id = clases_service.crear_horario(datos_horario)
            
            if es_creacion:
                success, horario_id = clases_service.crear_horario(datos_horario)
                if success:
                    st.success("✅ Horario creado correctamente")
                    st.rerun()
                else:
                    st.error("❌ Error creando el horario")
            else:
                success = clases_service.actualizar_horario(horario_data["id"], datos_horario)
                if success:
                    st.success("✅ Horario actualizado correctamente")
                    st.rerun()
                else:
                    st.error("❌ Error actualizando el horario")
        
        if eliminar:
            if st.session_state.get(f"confirmar_eliminar_horario_{horario_data['id']}"):
                success = clases_service.eliminar_horario(horario_data["id"])
                if success:
                    st.success("✅ Horario eliminado correctamente")
                    del st.session_state[f"confirmar_eliminar_horario_{horario_data['id']}"]
                    st.rerun()
                else:
                    st.error("❌ No se puede eliminar. El horario tiene reservas futuras.")
            else:
                st.session_state[f"confirmar_eliminar_horario_{horario_data['id']}"] = True
                st.warning("⚠️ Pulsa nuevamente para confirmar eliminación")

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
    
    # Obtener reservas usando los servicios
    try:
        # Aquí necesitarías un método en clases_service para obtener reservas filtradas
        df_reservas = obtener_reservas_periodo(clases_service, fecha_inicio, fecha_fin, estado_filtro)
        
        if df_reservas.empty:
            st.info("No hay reservas en el período seleccionado")
        else:
            st.markdown(f"#### 📊 {len(df_reservas)} reservas encontradas")
            
            # Tabla de reservas
            evento_reserva = st.dataframe(
                df_reservas,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "fecha_clase": st.column_config.DateColumn("📅 Fecha"),
                    "participante_nombre": "👤 Participante",
                    "clase_nombre": "🏃‍♀️ Clase",
                    "horario": "⏰ Horario",
                    "estado": "📊 Estado"
                }
            )
            
            # Gestión de asistencia para reserva seleccionada
            if evento_reserva.selection.rows:
                reserva_seleccionada = df_reservas.iloc[evento_reserva.selection.rows[0]]
                mostrar_gestion_asistencia(clases_service, reserva_seleccionada)
    
    except Exception as e:
        st.error(f"Error cargando reservas: {e}")

def obtener_reservas_periodo(clases_service, fecha_inicio, fecha_fin, estado_filtro):
    """Obtiene reservas del período con filtros."""
    try:
        # Esta función requeriría implementación en clases_service
        # Por ahora usamos un DataFrame vacío como placeholder
        return pd.DataFrame()
    except:
        return pd.DataFrame()

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
def main(supabase, session_state):
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

if __name__ == "__main__":
    st.error("Este archivo debe ser ejecutado desde main.py")
