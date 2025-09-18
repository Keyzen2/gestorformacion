import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
from datetime import datetime, timedelta
from services.proyectos_service import get_proyectos_service

try:
    from streamlit_option_menu import option_menu
    OPTION_MENU_AVAILABLE = True
except ImportError:
    OPTION_MENU_AVAILABLE = False
    st.warning("⚠️ Para mejor experiencia, instala: pip install streamlit-option-menu")

def main(supabase, session_state):
    """Página principal de gestión de proyectos"""
    
    # Verificar permisos
    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return
    
    # Inicializar servicio
    try:
        proyectos_service = get_proyectos_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error al inicializar servicio: {e}")
        return
    
    # Header principal
    st.title("📊 Gestión de Proyectos de Formación")
    st.caption("Control integral de proyectos, subvenciones y ejecución de formación")
    
    # Navegación principal
    if OPTION_MENU_AVAILABLE:
        tab_selected = option_menu(
            menu_title=None,
            options=["Dashboard", "Proyectos", "Gantt", "Grupos", "Reportes"],
            icons=["speedometer2", "folder", "calendar3", "people", "file-text"],
            menu_icon="cast",
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background-color": "#fafafa"},
                "icon": {"color": "orange", "font-size": "18px"},
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px"},
                "nav-link-selected": {"background-color": "#02ab21"},
            }
        )
    else:
        # Fallback sin option_menu
        tab_selected = st.selectbox("Seleccionar vista:", 
            ["Dashboard", "Proyectos", "Gantt", "Grupos", "Reportes"])
    
    st.divider()
    
    # Enrutamiento según selección
    if tab_selected == "Dashboard":
        mostrar_dashboard(proyectos_service)
    elif tab_selected == "Proyectos":
        gestionar_proyectos(proyectos_service, supabase, session_state)
    elif tab_selected == "Gantt":
        mostrar_vista_gantt(proyectos_service)
    elif tab_selected == "Grupos":
        gestionar_grupos_proyecto(proyectos_service)
    elif tab_selected == "Reportes":
        mostrar_reportes(proyectos_service)

import pandas as pd

def safe_date_value(fecha_valor):
    """Convierte fecha de forma segura para st.date_input - VERSIÓN CORREGIDA"""
    if fecha_valor is None:
        return None
    
    try:
        # Si es NaT de pandas, retornar None
        if pd.isna(fecha_valor):
            return None
            
        # Si es string vacío
        if isinstance(fecha_valor, str) and fecha_valor.strip() == '':
            return None
        
        # Si es string, convertir a date
        if isinstance(fecha_valor, str):
            fecha_dt = pd.to_datetime(fecha_valor, errors='coerce')
            if pd.isna(fecha_dt):  # Si falló la conversión
                return None
            return fecha_dt.date()
        
        # Si es Timestamp de pandas, verificar si es NaT
        if hasattr(fecha_valor, '_typ') and fecha_valor._typ == 'timestamp':
            if pd.isna(fecha_valor):
                return None
            return fecha_valor.date()
        
        # Si es datetime, extraer date
        if isinstance(fecha_valor, datetime):
            return fecha_valor.date()
            
        # Si ya es date
        if isinstance(fecha_valor, date):
            return fecha_valor
        
        # Para otros tipos con método .date()
        if hasattr(fecha_valor, 'date') and callable(fecha_valor.date):
            try:
                return fecha_valor.date()
            except (AttributeError, ValueError):
                return None
                
        # Si nada funciona, retornar None
        return None
        
    except (ValueError, TypeError, AttributeError, Exception):
        return None
        
def mostrar_dashboard(proyectos_service):
    """Dashboard principal con métricas y resumen"""
    
    st.markdown("### 📈 Dashboard de Proyectos")
    
    # Cargar datos
    with st.spinner("Cargando datos del dashboard..."):
        df_proyectos = proyectos_service.get_proyectos_completos()
    
    if df_proyectos.empty:
        st.info("📝 No hay proyectos registrados. Crea tu primer proyecto en la pestaña 'Proyectos'.")
        return
    
    # Calcular métricas con manejo de errores
    try:
        metricas = proyectos_service.calcular_metricas_dashboard(df_proyectos)
        
        # Verificar que las métricas se calcularon correctamente
        metricas_requeridas = ["total_proyectos", "proyectos_activos", "presupuesto_total", "importe_concedido", "tasa_exito", "proximos_vencimientos"]
        for metrica in metricas_requeridas:
            if metrica not in metricas:
                st.warning(f"Métrica '{metrica}' no disponible")
                metricas[metrica] = 0
                
    except Exception as e:
        st.error(f"Error al calcular métricas del dashboard: {e}")
        # Métricas por defecto en caso de error
        metricas = {
            "total_proyectos": len(df_proyectos) if not df_proyectos.empty else 0,
            "proyectos_activos": 0,
            "presupuesto_total": 0,
            "importe_concedido": 0,
            "tasa_exito": 0,
            "proximos_vencimientos": 0
        }
    
    # Mostrar métricas principales - usando características 1.49
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta_activos = f"{metricas.get('proyectos_activos', 0)}/{metricas.get('total_proyectos', 0)}"
        st.metric(
            "🚀 Proyectos Activos", 
            metricas.get('proyectos_activos', 0),
            delta=delta_activos,
            help="Proyectos en ejecución vs total"
        )
    
    with col2:
        importe_concedido = metricas.get('importe_concedido', 0)
        if importe_concedido > 0:
            delta_presupuesto = f"+{importe_concedido:,.0f}€ concedido"
        else:
            delta_presupuesto = "Sin financiación concedida"
        
        st.metric(
            "💰 Presupuesto Total", 
            f"{metricas.get('presupuesto_total', 0):,.0f}€",
            delta=delta_presupuesto,
            help="Presupuesto total vs importe concedido"
        )
    
    with col3:
        st.metric(
            "🎯 Tasa de Éxito", 
            f"{metricas.get('tasa_exito', 0):.1f}%",
            delta="Concedidos/Presentados",
            help="Porcentaje de proyectos concedidos vs presentados"
        )
    
    with col4:
        st.metric(
            "⏰ Próximos Hitos", 
            metricas.get('proximos_vencimientos', 0),
            delta="Próximos 30 días",
            help="Fechas clave en los próximos 30 días"
        )
    
    st.divider()
    
    # Gráficos del dashboard
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("#### 📊 Estados de Proyectos")
        if not df_proyectos.empty and 'estado_proyecto' in df_proyectos.columns:
            try:
                estados_count = df_proyectos['estado_proyecto'].value_counts()
                if not estados_count.empty:
                    fig_estados = px.pie(
                        values=estados_count.values, 
                        names=estados_count.index,
                        title="Distribución por Estado",
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig_estados.update_layout(height=400)
                    st.plotly_chart(fig_estados, use_container_width=True)
                else:
                    st.info("No hay datos de estados para mostrar")
            except Exception as e:
                st.error(f"Error al generar gráfico de estados: {e}")
        else:
            st.info("No hay datos disponibles para el gráfico de estados")
    
    with col_right:
        st.markdown("#### 💸 Evolución de Presupuestos")
        if not df_proyectos.empty and 'year_proyecto' in df_proyectos.columns:
            try:
                # Crear columna year_proyecto si no existe
                if 'year_proyecto' not in df_proyectos.columns:
                    # Intentar extraer año de fecha_inicio
                    try:
                        df_proyectos['year_proyecto'] = pd.to_datetime(df_proyectos['fecha_inicio'], errors='coerce').dt.year
                    except:
                        df_proyectos['year_proyecto'] = datetime.now().year
                
                presupuesto_por_año = df_proyectos.groupby('year_proyecto')['presupuesto_total'].sum().reset_index()
                
                if not presupuesto_por_año.empty:
                    fig_presupuesto = px.bar(
                        presupuesto_por_año, 
                        x='year_proyecto', 
                        y='presupuesto_total',
                        title="Presupuesto por Año",
                        labels={'presupuesto_total': 'Presupuesto (€)', 'year_proyecto': 'Año'}
                    )
                    fig_presupuesto.update_layout(height=400)
                    st.plotly_chart(fig_presupuesto, use_container_width=True)
                else:
                    st.info("No hay datos de presupuesto para mostrar")
            except Exception as e:
                st.error(f"Error al generar gráfico de presupuestos: {e}")
        else:
            st.info("No hay datos disponibles para el gráfico de presupuestos")
    
    # Tabla de proyectos próximos a vencer
    st.markdown("#### ⚠️ Proyectos con Fechas Próximas")
    try:
        proyectos_urgentes = obtener_proyectos_urgentes(df_proyectos)
        
        if not proyectos_urgentes.empty:
            columnas_urgentes = ['nombre', 'estado_proyecto', 'fecha_fin', 'fecha_justificacion', 'dias_restantes']
            # Verificar que las columnas existen
            columnas_disponibles_urgentes = [col for col in columnas_urgentes if col in proyectos_urgentes.columns]
            
            if columnas_disponibles_urgentes:
                st.dataframe(
                    proyectos_urgentes[columnas_disponibles_urgentes],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No se pueden mostrar detalles de proyectos urgentes")
        else:
            st.success("✅ No hay fechas urgentes en los próximos 30 días")
    except Exception as e:
        st.error(f"Error al mostrar proyectos urgentes: {e}")
        st.info("No se pueden mostrar proyectos con fechas próximas")


@st.dialog("Editar Proyecto", width="large") 
def modal_editar_proyecto(proyecto, proyectos_service):
    """Modal para editar proyecto existente"""
    
    st.markdown(f"### ✏️ Editar: {proyecto['nombre']}")
    estado_color = {
        "CONVOCADO": "🟡",
        "EN_EJECUCION": "🟢", 
        "FINALIZADO": "🔵",
        "JUSTIFICADO": "✅"
    }.get(proyecto.get('estado_proyecto', 'CONVOCADO'), "⚪")
    st.caption(f"Estado actual: {estado_color} {proyecto.get('estado_proyecto', 'CONVOCADO')}")
    
    with st.form("form_editar_proyecto_modal", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input("Nombre del Proyecto *", value=proyecto.get('nombre', ''))
            tipo_proyecto = st.selectbox("Tipo de Proyecto *", 
                ["FORMACION", "SUBVENCION", "PRIVADO", "CONSULTORIA"],
                index=["FORMACION", "SUBVENCION", "PRIVADO", "CONSULTORIA"].index(proyecto.get('tipo_proyecto', 'FORMACION')) if proyecto.get('tipo_proyecto') in ["FORMACION", "SUBVENCION", "PRIVADO", "CONSULTORIA"] else 0)
            organismo = st.text_input("Organismo Responsable", value=proyecto.get('organismo_responsable', ''))
            
            # Manejar presupuesto con conversión segura
            presupuesto_actual = proyecto.get('presupuesto_total', 0)
            try:
                presupuesto_valor = float(presupuesto_actual) if presupuesto_actual else 0.0
            except (ValueError, TypeError):
                presupuesto_valor = 0.0
            
            presupuesto = st.number_input("Presupuesto Total (€)", 
                min_value=0.0, step=1000.0, value=presupuesto_valor)
            responsable_nombre = st.text_input("Responsable del Proyecto", value=proyecto.get('responsable_nombre', ''))
        
        with col2:
            descripcion = st.text_area("Descripción del Proyecto", value=proyecto.get('descripcion', ''))
            estado_proyecto = st.selectbox("Estado del Proyecto", 
                ["CONVOCADO", "EN_EJECUCION", "FINALIZADO", "JUSTIFICADO"],
                index=["CONVOCADO", "EN_EJECUCION", "FINALIZADO", "JUSTIFICADO"].index(proyecto.get('estado_proyecto', 'CONVOCADO')) if proyecto.get('estado_proyecto') in ["CONVOCADO", "EN_EJECUCION", "FINALIZADO", "JUSTIFICADO"] else 0)
            
            estados_subv = ["", "CONVOCADA", "PRESUPUESTO", "CONCEDIDA", "PERDIDA"]
            estado_subv_actual = proyecto.get('estado_subvencion', '') or ''
            idx_subv = estados_subv.index(estado_subv_actual) if estado_subv_actual in estados_subv else 0
            estado_subvencion = st.selectbox("Estado de Subvención", estados_subv, index=idx_subv)
            
            # Manejar importe concedido con conversión segura
            importe_actual = proyecto.get('importe_concedido', 0)
            try:
                importe_valor = float(importe_actual) if importe_actual else 0.0
            except (ValueError, TypeError):
                importe_valor = 0.0
            
            importe_concedido = st.number_input("Importe Concedido (€)", 
                min_value=0.0, step=1000.0, value=importe_valor)
            responsable_email = st.text_input("Email del Responsable", value=proyecto.get('responsable_email', ''))
        
        # Fechas clave
        st.subheader("📅 Fechas Importantes")
        col3, col4, col5 = st.columns(3)
        
        with col3:
            fecha_convocatoria = st.date_input("Fecha Convocatoria", value=safe_date_value(proyecto.get('fecha_convocatoria')))
            fecha_inicio = st.date_input("Fecha Inicio", value=safe_date_value(proyecto.get('fecha_inicio')))
        
        with col4:
            fecha_ejecucion = st.date_input("Fecha Ejecución", value=safe_date_value(proyecto.get('fecha_ejecucion')))
            fecha_fin = st.date_input("Fecha Fin", value=safe_date_value(proyecto.get('fecha_fin')))
        
        with col5:
            fecha_justificacion = st.date_input("Fecha Justificación", value=safe_date_value(proyecto.get('fecha_justificacion')))
            fecha_presentacion = st.date_input("Presentación Informes", value=safe_date_value(proyecto.get('fecha_presentacion_informes')))
        
        # Botones
        col_save, col_delete = st.columns([3, 1])
        
        with col_save:
            submitted = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
        
        with col_delete:
            if proyectos_service.can_modify_data() and proyectos_service.session_state.role == "admin":
                delete_clicked = st.form_submit_button("🗑️ Eliminar", help="Solo administradores")
        
        if submitted:
            datos_actualizados = {
                "nombre": nombre,
                "descripcion": descripcion,
                "tipo_proyecto": tipo_proyecto,
                "estado_proyecto": estado_proyecto,
                "estado_subvencion": estado_subvencion if estado_subvencion else None,
                "fecha_convocatoria": fecha_convocatoria,
                "fecha_inicio": fecha_inicio,
                "fecha_ejecucion": fecha_ejecucion,
                "fecha_fin": fecha_fin,
                "fecha_justificacion": fecha_justificacion,
                "fecha_presentacion_informes": fecha_presentacion,
                "presupuesto_total": presupuesto,
                "importe_concedido": importe_concedido if importe_concedido > 0 else None,
                "organismo_responsable": organismo,
                "responsable_nombre": responsable_nombre,
                "responsable_email": responsable_email
            }
            
            if proyectos_service.actualizar_proyecto(proyecto['id'], datos_actualizados):
                st.success("✅ Proyecto actualizado correctamente")
                st.rerun()
        
        # Manejar eliminación
        if proyectos_service.can_modify_data() and proyectos_service.session_state.role == "admin":
            if 'delete_clicked' in locals() and delete_clicked:
                confirmar_key = f"confirm_delete_proyecto_{proyecto['id']}"
                if st.session_state.get(confirmar_key, False):
                    if proyectos_service.eliminar_proyecto(proyecto['id']):
                        st.success("Proyecto eliminado correctamente")
                        st.rerun()
                else:
                    st.session_state[confirmar_key] = True
                    st.warning("Presione 'Eliminar' de nuevo para confirmar")


def gestionar_proyectos(proyectos_service, supabase, session_state):
    """Gestión CRUD de proyectos - VERSIÓN CORREGIDA"""
    
    st.markdown("### 📁 Gestión de Proyectos")
    
    # Filtros de búsqueda
    crear_filtros_proyecto(proyectos_service)
    
    st.divider()
    
    # Botón para crear nuevo proyecto
    if proyectos_service.can_modify_data():
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            if st.button("➕ Nuevo Proyecto", type="primary", use_container_width=True):
                modal_crear_proyecto(proyectos_service, supabase, session_state)
        
        with col_btn2:
            if st.button("🔄 Actualizar", use_container_width=True):
                proyectos_service.get_proyectos_completos.clear()
                st.rerun()
    
    # Cargar y mostrar proyectos
    with st.spinner("Cargando proyectos..."):
        df_proyectos = proyectos_service.get_proyectos_completos()
    
    if df_proyectos.empty:
        st.info("📝 No hay proyectos registrados.")
        return
    
    # Aplicar filtros desde session_state
    filtros = st.session_state.get('filtros_proyecto', {})
    df_filtrado = proyectos_service.filtrar_proyectos(df_proyectos, filtros)
    
    if len(df_filtrado) != len(df_proyectos):
        st.info(f"🎯 Mostrando {len(df_filtrado)} de {len(df_proyectos)} proyectos")
    
    # Tabla principal de proyectos
    st.markdown("#### Selecciona un proyecto para editarlo:")
    
    columnas_visibles = [
        'nombre', 'tipo_proyecto', 'estado_proyecto', 'estado_subvencion',
        'fecha_inicio', 'fecha_fin', 'presupuesto_total', 'empresa_nombre'
    ]
    
    # Preparar datos para mostrar con manejo seguro de valores
    df_display = df_filtrado[columnas_visibles].copy()
    
    # Formatear columnas numéricas de forma segura
    if 'presupuesto_total' in df_display.columns:
        def formatear_presupuesto(x):
            try:
                if pd.isna(x) or x == '' or x is None:
                    return "Sin presupuesto"
                valor = float(x)
                return f"{valor:,.0f}€" if valor > 0 else "Sin presupuesto"
            except (ValueError, TypeError):
                return "Sin presupuesto"
        
        df_display['presupuesto_total'] = df_display['presupuesto_total'].apply(formatear_presupuesto)
    
    try:
        event = st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="tabla_proyectos_principal"
        )
        
        # Manejar selección para edición MODAL
        if event and hasattr(event, 'selection') and event.selection.get("rows"):
            selected_idx = event.selection["rows"][0]
            if selected_idx < len(df_filtrado):
                proyecto_seleccionado = df_filtrado.iloc[selected_idx]
                mostrar_formulario_edicion_proyecto(proyecto_seleccionado, proyectos_service)
                
    except Exception as e:
        st.error(f"❌ Error al mostrar tabla: {e}")
        st.write("Detalles del error:", str(e))
        # Mostrar información de debug
        st.write("Columnas disponibles:", df_display.columns.tolist())
        st.write("Tipos de datos:", df_display.dtypes.to_dict())


def crear_filtros_proyecto(proyectos_service):
    """Panel de filtros para proyectos"""
    
    st.markdown("#### 🔍 Filtros de Búsqueda")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        años = list(range(2020, 2031))
        año_seleccionado = st.selectbox("📅 Año", ["Todos"] + años, key="filtro_año")
    
    with col2:
        estados_proyecto = ["Todos", "CONVOCADO", "EN_EJECUCION", "FINALIZADO", "JUSTIFICADO"]
        estado_filtro = st.selectbox("🔄 Estado Proyecto", estados_proyecto, key="filtro_estado")
    
    with col3:
        estados_subvencion = ["Todos", "CONVOCADA", "PRESUPUESTO", "CONCEDIDA", "PERDIDA"]
        subvencion_filtro = st.selectbox("💰 Estado Subvención", estados_subvencion, key="filtro_subvencion")
    
    with col4:
        tipos = ["Todos", "FORMACION", "SUBVENCION", "PRIVADO", "CONSULTORIA"]
        tipo_filtro = st.selectbox("📂 Tipo", tipos, key="filtro_tipo")
    
    with col5:
        buscar_texto = st.text_input("🔍 Buscar", placeholder="Nombre, organismo...", key="filtro_buscar")
    
    # Guardar filtros en session_state
    st.session_state.filtros_proyecto = {
        'año': año_seleccionado if año_seleccionado != "Todos" else None,
        'estado_proyecto': estado_filtro if estado_filtro != "Todos" else None,
        'estado_subvencion': subvencion_filtro if subvencion_filtro != "Todos" else None,
        'tipo_proyecto': tipo_filtro if tipo_filtro != "Todos" else None,
        'buscar_texto': buscar_texto if buscar_texto else None
    }


@st.dialog("Crear Nuevo Proyecto", width="large")
def modal_crear_proyecto(proyectos_service, supabase, session_state):
    """Modal para crear nuevo proyecto"""
    
    st.markdown("### ✨ Nuevo Proyecto de Formación")
    
    with st.form("form_crear_proyecto", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input("Nombre del Proyecto *", placeholder="Ej: Formación Digital 2025")
            tipo_proyecto = st.selectbox("Tipo de Proyecto *", 
                ["FORMACION", "SUBVENCION", "PRIVADO", "CONSULTORIA"])
            organismo = st.text_input("Organismo Responsable", 
                placeholder="Ej: SEPE, Fundación Estatal...")
            presupuesto = st.number_input("Presupuesto Total (€)", min_value=0.0, step=1000.0, value=0.0)
            responsable_nombre = st.text_input("Responsable del Proyecto")
        
        with col2:
            descripcion = st.text_area("Descripción del Proyecto", height=100)
            estado_proyecto = st.selectbox("Estado del Proyecto", 
                ["CONVOCADO", "EN_EJECUCION", "FINALIZADO", "JUSTIFICADO"])
            estado_subvencion = st.selectbox("Estado de Subvención", 
                ["CONVOCADA", "PRESUPUESTO", "CONCEDIDA", "PERDIDA"], 
                help="Dejar en blanco si no aplica")
            importe_concedido = st.number_input("Importe Concedido (€)", min_value=0.0, step=1000.0, value=0.0)
            responsable_email = st.text_input("Email del Responsable")
        
        # Fechas clave
        st.subheader("📅 Fechas Importantes")
        col3, col4, col5 = st.columns(3)
        
        with col3:
            fecha_convocatoria = st.date_input("Fecha Convocatoria", value=None)
            fecha_inicio = st.date_input("Fecha Inicio", value=None)
        
        with col4:
            fecha_ejecucion = st.date_input("Fecha Ejecución", value=None)
            fecha_fin = st.date_input("Fecha Fin", value=None)
        
        with col5:
            fecha_justificacion = st.date_input("Fecha Justificación", value=None)
            fecha_presentacion = st.date_input("Presentación Informes", value=None)
        
        # Empresa (solo para admin)
        empresa_id = None
        if session_state.role == "admin":
            st.subheader("🏢 Asignación de Empresa")
            try:
                empresas_result = supabase.table("empresas").select("id, nombre").execute()
                if empresas_result.data:
                    empresas_dict = {emp['nombre']: emp['id'] for emp in empresas_result.data}
                    empresa_nombre = st.selectbox("Empresa Responsable", [""] + list(empresas_dict.keys()))
                    if empresa_nombre:
                        empresa_id = empresas_dict[empresa_nombre]
            except Exception as e:
                st.error(f"Error al cargar empresas: {e}")
        
        col_submit, col_cancel = st.columns([1, 3])
        with col_submit:
            submitted = st.form_submit_button("✅ Crear Proyecto", type="primary", use_container_width=True)
        
        if submitted:
            # Validaciones
            if not nombre:
                st.error("El nombre del proyecto es obligatorio")
                return
            
            if not tipo_proyecto:
                st.error("Debe seleccionar un tipo de proyecto")
                return
            
            # Preparar datos
            datos_proyecto = {
                "nombre": nombre,
                "descripcion": descripcion,
                "tipo_proyecto": tipo_proyecto,
                "estado_proyecto": estado_proyecto,
                "estado_subvencion": estado_subvencion if estado_subvencion != "CONVOCADA" else None,
                "fecha_convocatoria": fecha_convocatoria,
                "fecha_inicio": fecha_inicio,
                "fecha_ejecucion": fecha_ejecucion,
                "fecha_fin": fecha_fin,
                "fecha_justificacion": fecha_justificacion,
                "fecha_presentacion_informes": fecha_presentacion,
                "presupuesto_total": presupuesto,
                "importe_concedido": importe_concedido if importe_concedido > 0 else None,
                "organismo_responsable": organismo,
                "responsable_nombre": responsable_nombre,
                "responsable_email": responsable_email,
                "empresa_id": empresa_id
            }
            
            if proyectos_service.crear_proyecto(datos_proyecto):
                st.success("Proyecto creado correctamente")
                st.rerun()


def mostrar_formulario_edicion_proyecto(proyecto, proyectos_service):
    """Mostrar información del proyecto seleccionado y botón para abrir modal"""
    
    st.markdown("---")
    st.markdown("### 📝 Proyecto Seleccionado")
    
    col_info, col_actions = st.columns([3, 1])
    
    with col_info:
        estado_color = {
            "CONVOCADO": "🟡",
            "EN_EJECUCION": "🟢", 
            "FINALIZADO": "🔵",
            "JUSTIFICADO": "✅"
        }.get(proyecto.get('estado_proyecto', 'CONVOCADO'), "⚪")
        
        presupuesto = proyecto.get('presupuesto_total', 0)
        presupuesto_str = f"{presupuesto:,.0f}€" if presupuesto > 0 else "Sin presupuesto"
        
        st.info(f"""
        **{proyecto['nombre']}** - {proyecto.get('tipo_proyecto', 'N/A')}  
        💰 Presupuesto: {presupuesto_str} | 🏢 {proyecto.get('organismo_responsable', 'N/A')}  
        {estado_color} Estado: {proyecto.get('estado_proyecto', 'CONVOCADO')}  
        📅 {proyecto.get('fecha_inicio', 'N/A')} → {proyecto.get('fecha_fin', 'N/A')}
        """)
    
    with col_actions:
        if st.button("✏️ Editar Proyecto", type="primary", use_container_width=True, key="btn_editar_proyecto_modal"):
            modal_editar_proyecto(proyecto, proyectos_service)

def mostrar_vista_gantt(proyectos_service):
    """Vista de timeline Gantt para proyectos"""
    
    st.markdown("### 📅 Vista Timeline - Gantt")
    st.caption("Visualización temporal de proyectos y sus hitos")
    
    # Cargar proyectos
    df_proyectos = proyectos_service.get_proyectos_completos()
    
    if df_proyectos.empty:
        st.info("📝 No hay proyectos para mostrar en el timeline")
        return
    
    # Filtros específicos para Gantt
    col1, col2, col3 = st.columns(3)
    
    with col1:
        año_gantt = st.selectbox("Año para Timeline", ["Todos"] + list(range(2020, 2031)), key="gantt_año")
    
    with col2:
        estado_gantt = st.multiselect("Estados a mostrar", 
            ["CONVOCADO", "EN_EJECUCION", "FINALIZADO", "JUSTIFICADO"],
            default=["EN_EJECUCION", "FINALIZADO"])
    
    with col3:
        mostrar_hitos = st.checkbox("Mostrar hitos detallados", value=False)
    
    # Filtrar datos para Gantt
    df_gantt = df_proyectos.copy()
    
    if año_gantt != "Todos":
        df_gantt = df_gantt[df_gantt['year_proyecto'] == año_gantt]
    
    if estado_gantt:
        df_gantt = df_gantt[df_gantt['estado_proyecto'].isin(estado_gantt)]
    
    if df_gantt.empty:
        st.warning("No hay proyectos que coincidan con los filtros seleccionados")
        return
    
    # Preparar datos para el gráfico Gantt
    gantt_data = []
    
    for _, proyecto in df_gantt.iterrows():
        # Usar fecha_inicio y fecha_fin, con fallbacks
        fecha_start = proyecto.get('fecha_inicio') or proyecto.get('fecha_ejecucion')
        fecha_end = proyecto.get('fecha_fin') or proyecto.get('fecha_justificacion')
        
        if fecha_start and fecha_end:
            gantt_data.append({
                'Task': proyecto['nombre'][:30] + ('...' if len(proyecto['nombre']) > 30 else ''),
                'Start': fecha_start,
                'Finish': fecha_end,
                'Resource': proyecto['estado_proyecto'],
                'Description': f"Tipo: {proyecto['tipo_proyecto']} | Empresa: {proyecto.get('empresa_nombre', 'N/A')}"
            })
    
    if not gantt_data:
        st.warning("No hay proyectos con fechas válidas para mostrar en el timeline")
        return
    
    # Crear gráfico Gantt usando Plotly
    try:
        # Colores por estado
        colors = {
            'CONVOCADO': '#e74c3c',
            'EN_EJECUCION': '#f39c12', 
            'FINALIZADO': '#27ae60',
            'JUSTIFICADO': '#3498db'
        }
        
        fig = ff.create_gantt(
            gantt_data,
            colors=colors,
            index_col='Resource',
            show_colorbar=True,
            group_tasks=True,
            title="Timeline de Proyectos",
            height=600
        )
        
        fig.update_layout(
            xaxis_title="Línea de Tiempo",
            yaxis_title="Proyectos",
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Información adicional
        st.markdown("#### 📊 Resumen del Timeline")
        col_info1, col_info2, col_info3 = st.columns(3)
        
        with col_info1:
            st.metric("Proyectos en Timeline", len(gantt_data))
        
        with col_info2:
            if gantt_data:
                fecha_min = min([item['Start'] for item in gantt_data])
                fecha_max = max([item['Finish'] for item in gantt_data])
                duracion = (fecha_max - fecha_min).days
                st.metric("Duración Total", f"{duracion} días")
        
        with col_info3:
            proyectos_activos_gantt = len([item for item in gantt_data if item['Resource'] == 'EN_EJECUCION'])
            st.metric("En Ejecución", proyectos_activos_gantt)
        
    except Exception as e:
        st.error(f"Error al crear el gráfico Gantt: {e}")
        st.info("Verifica que los proyectos tengan fechas de inicio y fin válidas")

def gestionar_grupos_proyecto(proyectos_service):
    """Gestión de asignación de grupos a proyectos"""
    
    st.markdown("### 👥 Asignación de Grupos a Proyectos")
    st.caption("Vincular grupos formativos con proyectos")
    
    # Seleccionar proyecto
    df_proyectos = proyectos_service.get_proyectos_completos()
    
    if df_proyectos.empty:
        st.info("📝 No hay proyectos registrados")
        return
    
    proyecto_options = {f"{row['nombre']} ({row['estado_proyecto']})": row['id'] 
                       for _, row in df_proyectos.iterrows()}
    
    proyecto_seleccionado = st.selectbox("Seleccionar Proyecto", [""] + list(proyecto_options.keys()))
    
    if not proyecto_seleccionado:
        st.info("👆 Selecciona un proyecto para gestionar sus grupos")
        return
    
    proyecto_id = proyecto_options[proyecto_seleccionado]
    
    # Mostrar información del proyecto
    proyecto_info = df_proyectos[df_proyectos['id'] == proyecto_id].iloc[0]
    
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.info(f"**Tipo:** {proyecto_info['tipo_proyecto']}")
    with col_info2:
        st.info(f"**Estado:** {proyecto_info['estado_proyecto']}")
    with col_info3:
        st.info(f"**Empresa:** {proyecto_info.get('empresa_nombre', 'N/A')}")
    
    st.divider()
    
    # Cargar grupos con información de acción formativa
    try:
        if proyectos_service.session_state.role == "gestor":
            grupos_res = proyectos_service.supabase.table("grupos").select("""
                id, codigo_grupo, estado, localidad, fecha_inicio, fecha_fin_prevista,
                accion_formativa:acciones_formativas(nombre, modalidad, num_horas)
            """).eq("empresa_id", proyectos_service.session_state.user.get("empresa_id")).execute()
        else:
            grupos_res = proyectos_service.supabase.table("grupos").select("""
                id, codigo_grupo, estado, localidad, fecha_inicio, fecha_fin_prevista,
                accion_formativa:acciones_formativas(nombre, modalidad, num_horas)
            """).execute()
            
        grupos_disponibles = grupos_res.data or []
        
    except Exception as e:
        st.error(f"Error al cargar grupos: {e}")
        grupos_disponibles = []
    
    if not grupos_disponibles:
        st.info("No hay grupos disponibles")
        return
    
    # Grupos actualmente asignados al proyecto
    try:
        grupos_proyecto_res = proyectos_service.supabase.table("proyecto_grupos")\
            .select("grupo_id, created_at")\
            .eq("proyecto_id", proyecto_id)\
            .execute()
        
        grupos_asignados_ids = [pg["grupo_id"] for pg in (grupos_proyecto_res.data or [])]
        
    except Exception as e:
        st.error(f"Error al cargar grupos del proyecto: {e}")
        grupos_asignados_ids = []
    
    # Mostrar grupos asignados
    st.markdown("#### 📋 Grupos Asignados")
    if grupos_asignados_ids:
        grupos_asignados = [g for g in grupos_disponibles if g["id"] in grupos_asignados_ids]
        
        if grupos_asignados:
            for grupo in grupos_asignados:
                # Información de acción formativa
                accion_info = grupo.get('accion_formativa', {})
                accion_nombre = accion_info.get('nombre', 'Sin acción') if accion_info else 'Sin acción'
                modalidad = accion_info.get('modalidad', 'No definida') if accion_info else 'No definida'
                
                with st.expander(f"📚 {grupo['codigo_grupo']} - {accion_nombre}", expanded=False):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        st.write(f"**Acción:** {accion_nombre}")
                        st.write(f"**Modalidad:** {modalidad}")
                    
                    with col2:
                        st.write(f"**Estado:** {grupo.get('estado', 'No definido').capitalize()}")
                        st.write(f"**Localidad:** {grupo.get('localidad', 'No definida')}")
                    
                    with col3:
                        if st.button("🗑️ Quitar", key=f"remove_grupo_{grupo['id']}", help="Quitar grupo del proyecto"):
                            try:
                                proyectos_service.supabase.table("proyecto_grupos")\
                                    .delete()\
                                    .eq("proyecto_id", proyecto_id)\
                                    .eq("grupo_id", grupo['id'])\
                                    .execute()
                                st.success(f"✅ Grupo {grupo['codigo_grupo']} eliminado del proyecto")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al quitar grupo: {e}")
        else:
            st.info("Los grupos asignados no se encuentran disponibles")
    else:
        st.info("No hay grupos asignados a este proyecto")
    
    # Asignar nuevos grupos
    if proyectos_service.can_modify_data():
        st.markdown("#### ➕ Asignar Nuevos Grupos")
        
        # Filtrar grupos no asignados
        grupos_no_asignados = [g for g in grupos_disponibles if g["id"] not in grupos_asignados_ids]
        
        if not grupos_no_asignados:
            st.info("Todos los grupos disponibles ya están asignados a este proyecto.")
            return
        
        # Selector mejorado con nombres de acción formativa
        with st.form("form_asignar_grupo", clear_on_submit=True):
            grupo_options = []
            grupo_mapping = {}
            
            for g in grupos_no_asignados:
                # Extraer información de acción formativa
                accion_info = g.get('accion_formativa', {})
                accion_nombre = accion_info.get('nombre', 'Sin acción') if accion_info else 'Sin acción'
                modalidad = accion_info.get('modalidad', '') if accion_info else ''
                num_horas = accion_info.get('num_horas', '') if accion_info else ''
                estado = g.get('estado', 'abierto').capitalize()
                
                # Formato: "GRUP001 - Excel Avanzado (PRESENCIAL) [Abierto] - 40h"
                display_text = f"{g['codigo_grupo']} - {accion_nombre}"
                
                if modalidad:
                    display_text += f" ({modalidad})"
                
                display_text += f" [{estado}]"
                
                if num_horas:
                    display_text += f" - {num_horas}h"
                
                grupo_options.append(display_text)
                grupo_mapping[display_text] = g
            
            if grupo_options:
                grupo_seleccionado = st.selectbox(
                    "Seleccionar grupo para asignar",
                    options=[""] + grupo_options,
                    help="Formato: Código - Acción Formativa (Modalidad) [Estado] - Horas"
                )
                
                asignar_clicked = st.form_submit_button("✅ Asignar Grupo al Proyecto", type="primary")
                
                if asignar_clicked and grupo_seleccionado:
                    try:
                        grupo_data = grupo_mapping[grupo_seleccionado]
                        
                        # Verificar que no esté ya asignado
                        existe = proyectos_service.supabase.table("proyecto_grupos")\
                            .select("id")\
                            .eq("proyecto_id", proyecto_id)\
                            .eq("grupo_id", grupo_data['id'])\
                            .execute()
                        
                        if existe.data:
                            st.warning("⚠️ Este grupo ya está asignado al proyecto.")
                        else:
                            # Asignar grupo al proyecto
                            proyectos_service.supabase.table("proyecto_grupos").insert({
                                "proyecto_id": proyecto_id,
                                "grupo_id": grupo_data['id'],
                                "fecha_asignacion": datetime.utcnow().isoformat(),
                                "activo": True
                            }).execute()
                            
                            accion_nombre = grupo_data.get('accion_formativa', {}).get('nombre', grupo_data['codigo_grupo'])
                            st.success(f"✅ Grupo '{grupo_data['codigo_grupo']} - {accion_nombre}' asignado correctamente")
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"❌ Error al asignar grupo: {e}")
                
                elif asignar_clicked:
                    st.warning("⚠️ Selecciona un grupo para asignar")
            else:
                st.info("No hay grupos disponibles para mostrar")
    else:
        st.info("No tienes permisos para modificar asignaciones de grupos")

def mostrar_reportes(proyectos_service):
    """Reportes y exportación de datos"""
    
    st.markdown("### 📊 Reportes y Análisis")
    
    df_proyectos = proyectos_service.get_proyectos_completos()
    
    if df_proyectos.empty:
        st.info("📝 No hay datos para generar reportes")
        return
    
    # Opciones de reporte
    tipo_reporte = st.selectbox("Tipo de Reporte", [
        "Resumen Ejecutivo",
        "Estado de Subvenciones", 
        "Análisis Financiero",
        "Timeline de Proyectos",
        "Exportar Datos"
    ])
    
    if tipo_reporte == "Resumen Ejecutivo":
        mostrar_reporte_ejecutivo(df_proyectos)
    elif tipo_reporte == "Estado de Subvenciones":
        mostrar_reporte_subvenciones(df_proyectos)
    elif tipo_reporte == "Análisis Financiero":
        mostrar_reporte_financiero(df_proyectos)
    elif tipo_reporte == "Exportar Datos":
        mostrar_opciones_exportacion(df_proyectos)


def mostrar_reporte_ejecutivo(df_proyectos):
    """Reporte ejecutivo con métricas principales"""
    
    st.markdown("#### 📈 Resumen Ejecutivo")
    
    # Métricas por año
    st.markdown("##### Distribución por Año")
    if 'year_proyecto' in df_proyectos.columns:
        distribucion_año = df_proyectos['year_proyecto'].value_counts().sort_index()
        fig_año = px.bar(x=distribucion_año.index, y=distribucion_año.values, 
                        title="Proyectos por Año")
        st.plotly_chart(fig_año, use_container_width=True)
    
    # Tabla resumen por estado
    st.markdown("##### Resumen por Estado")
    resumen_estados = df_proyectos.groupby('estado_proyecto').agg({
        'nombre': 'count',
        'presupuesto_total': 'sum',
        'importe_concedido': 'sum'
    }).rename(columns={'nombre': 'Cantidad'})
    
    st.dataframe(resumen_estados, use_container_width=True)


def mostrar_reporte_subvenciones(df_proyectos):
    """Reporte específico de subvenciones"""
    
    st.markdown("#### 💰 Estado de Subvenciones")
    
    # Filtrar solo proyectos con estado de subvención
    df_subvenciones = df_proyectos[df_proyectos['estado_subvencion'].notna() & 
                                  (df_proyectos['estado_subvencion'] != '')]
    
    if df_subvenciones.empty:
        st.info("No hay proyectos con información de subvenciones")
        return
    
    # Gráfico de estados de subvención
    estados_subv = df_subvenciones['estado_subvencion'].value_counts()
    fig_subv = px.pie(values=estados_subv.values, names=estados_subv.index,
                     title="Distribución de Estados de Subvención")
    st.plotly_chart(fig_subv, use_container_width=True)
    
    # Tabla detallada
    cols_subv = ['nombre', 'estado_subvencion', 'presupuesto_total', 'importe_concedido', 'organismo_responsable']
    st.dataframe(df_subvenciones[cols_subv], use_container_width=True, hide_index=True)


def mostrar_reporte_financiero(df_proyectos):
    """Análisis financiero de proyectos - VERSIÓN CORREGIDA"""
    
    st.markdown("#### 💼 Análisis Financiero")
    
    if df_proyectos.empty:
        st.info("No hay proyectos para analizar.")
        return
    
    try:
        # 🔧 CORRECCIÓN: Limpiar y convertir datos numéricos de forma segura
        df_clean = df_proyectos.copy()
        
        # Convertir presupuesto_total de forma segura
        df_clean['presupuesto_total'] = pd.to_numeric(
            df_clean['presupuesto_total'], 
            errors='coerce'
        ).fillna(0)
        
        # Convertir importe_concedido de forma segura
        df_clean['importe_concedido'] = pd.to_numeric(
            df_clean['importe_concedido'], 
            errors='coerce'
        ).fillna(0)
        
        # Calcular métricas
        presupuesto_total = float(df_clean['presupuesto_total'].sum())
        importe_concedido = float(df_clean['importe_concedido'].sum())
        
        # Mostrar métricas principales
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Presupuesto Total", f"{presupuesto_total:,.0f}€" if presupuesto_total > 0 else "0€")
        
        with col2:
            st.metric("Importe Concedido", f"{importe_concedido:,.0f}€" if importe_concedido > 0 else "0€")
        
        with col3:
            if presupuesto_total > 0:
                porcentaje_concedido = (importe_concedido / presupuesto_total) * 100
                st.metric("% Concedido", f"{porcentaje_concedido:.1f}%")
            else:
                st.metric("% Concedido", "0%")
        
        # Evolución financiera por año (solo si existe la columna)
        if 'year_proyecto' in df_clean.columns:
            try:
                finanzas_año = df_clean.groupby('year_proyecto').agg({
                    'presupuesto_total': 'sum',
                    'importe_concedido': 'sum'
                }).fillna(0)
                
                if not finanzas_año.empty:
                    fig_finanzas = px.bar(
                        finanzas_año.reset_index(), 
                        x='year_proyecto',
                        y=['presupuesto_total', 'importe_concedido'],
                        title="Evolución Financiera por Año",
                        barmode='group',
                        labels={'value': 'Importe (€)', 'year_proyecto': 'Año'}
                    )
                    st.plotly_chart(fig_finanzas, use_container_width=True)
                else:
                    st.info("No hay datos de años para mostrar evolución")
                    
            except Exception as e:
                st.warning("No se puede mostrar evolución por año")
        else:
            st.info("No hay información de años disponible")
            
    except Exception as e:
        st.error(f"Error al generar reporte financiero: {str(e)}")
        st.info("Verificando integridad de datos financieros...")


def mostrar_opciones_exportacion(df_proyectos):
    """Opciones para exportar datos"""
    
    st.markdown("#### 📤 Exportar Datos")
    
    formato_export = st.selectbox("Formato de Exportación", ["CSV", "Excel"])
    
    # Seleccionar columnas
    todas_columnas = df_proyectos.columns.tolist()
    columnas_export = st.multiselect("Columnas a Exportar", todas_columnas, default=todas_columnas[:10])
    
    if st.button("Descargar"):
        if not columnas_export:
            st.error("Selecciona al menos una columna")
            return
        
        df_export = df_proyectos[columnas_export]
        
        if formato_export == "CSV":
            csv = df_export.to_csv(index=False)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"proyectos_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:  # Excel
            from io import BytesIO
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Proyectos')
            
            st.download_button(
                label="📥 Descargar Excel",
                data=output.getvalue(),
                file_name=f"proyectos_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

def obtener_proyectos_urgentes(df_proyectos):
    """Obtiene proyectos con fechas próximas a vencer - VERSIÓN ULTRA CORREGIDA"""
    
    if df_proyectos.empty:
        return pd.DataFrame()
    
    try:
        hoy = datetime.now().date()
        fecha_limite = hoy + timedelta(days=30)
        
        proyectos_urgentes = []
        
        for _, proyecto in df_proyectos.iterrows():
            campos_fecha = ['fecha_fin', 'fecha_justificacion', 'fecha_presentacion_informes']
            
            for fecha_col in campos_fecha:
                fecha_valor = proyecto.get(fecha_col)
                
                # Usar la función safe_date_value corregida
                fecha_convertida = safe_date_value(fecha_valor)
                
                # Si logramos convertir la fecha y está en rango
                if fecha_convertida and hoy <= fecha_convertida <= fecha_limite:
                    dias_restantes = (fecha_convertida - hoy).days
                    
                    proyectos_urgentes.append({
                        'nombre': proyecto.get('nombre', 'Sin nombre'),
                        'estado_proyecto': proyecto.get('estado_proyecto', 'N/A'),
                        'fecha_fin': safe_date_value(proyecto.get('fecha_fin')),
                        'fecha_justificacion': safe_date_value(proyecto.get('fecha_justificacion')),
                        'dias_restantes': dias_restantes,
                        'tipo_vencimiento': fecha_col.replace('fecha_', '').replace('_', ' ').title(),
                        'fecha_urgente': fecha_convertida
                    })
                    break  # Solo agregar una vez por proyecto
        
        # Convertir a DataFrame
        df_result = pd.DataFrame(proyectos_urgentes)
        
        # Ordenar por días restantes si hay datos
        if not df_result.empty and 'dias_restantes' in df_result.columns:
            df_result = df_result.sort_values('dias_restantes')
        
        return df_result
        
    except Exception as e:
        # Si hay cualquier error, retornar DataFrame vacío
        return pd.DataFrame()
