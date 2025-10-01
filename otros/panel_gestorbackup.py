import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date
from services.data_service import get_data_service
from services.grupos_service import get_grupos_service
from services.empresas_service import get_empresas_service
from services.participantes_service import get_participantes_service

def render(supabase, session_state):
    """Panel del Gestor - Versión Modernizada Streamlit 1.49"""
    
    st.title("📊 Panel de Control - Formación FUNDAE")
    
    # Verificación de permisos mejorada
    if session_state.role not in ["admin", "gestor"]:
        st.error("🔒 Acceso restringido. Solo administradores y gestores.")
        st.info("👤 Contacta con tu administrador para obtener los permisos necesarios.")
        return

    # Información contextual según rol
    if session_state.role == "gestor":
        empresa_info = session_state.user.get("empresa_nombre", "Tu empresa")
        st.caption(f"👨‍💼 Panel de gestión para: **{empresa_info}**")
    else:
        st.caption("🔧 Vista de administrador - Todas las empresas")

    # =========================
    # INICIALIZACIÓN DE SERVICIOS CON MANEJO DE ERRORES
    # =========================
    try:
        with st.spinner("Inicializando servicios..."):
            data_service = get_data_service(supabase, session_state)
            grupos_service = get_grupos_service(supabase, session_state)
            empresas_service = get_empresas_service(supabase, session_state)
            participantes_service = get_participantes_service(supabase, session_state)
    except Exception as e:
        st.error("❌ Error crítico al inicializar servicios")
        with st.expander("🔧 Detalles técnicos"):
            st.code(f"Error: {e}")
        return

    # =========================
    # CARGA DE DATOS CON PROGRESO Y FILTROS JERÁRQUICOS
    # =========================
    datos_cargados = cargar_datos_dashboard(
        data_service, grupos_service, empresas_service, 
        participantes_service, session_state
    )
    
    if not datos_cargados:
        st.stop()

    df_grupos, df_participantes, df_empresas, df_tutores, df_acciones = datos_cargados

    # =========================
    # MÉTRICAS PRINCIPALES CON DISEÑO MODERNO
    # =========================
    mostrar_metricas_principales(df_grupos, df_participantes, df_empresas, df_tutores, df_acciones)

    st.divider()

    # =========================
    # NAVEGACIÓN POR TABS MODERNIZADA
    # =========================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Análisis", 
        "👥 Grupos Activos", 
        "🎓 Participantes",
        "🏢 Empresas",
        "📋 Documentación"
    ])

    with tab1:
        mostrar_analytics_avanzadas(df_grupos, df_participantes, df_empresas, session_state)

    with tab2:
        mostrar_gestion_grupos(df_grupos, df_participantes, grupos_service, session_state)

    with tab3:
        mostrar_resumen_participantes(df_participantes, df_grupos, session_state)

    with tab4:
        mostrar_resumen_empresas(df_empresas, session_state)

    with tab5:
        mostrar_documentacion_fundae_moderna()

    # =========================
    # FOOTER CON INFORMACIÓN ÚTIL
    # =========================
    mostrar_footer_informativo(session_state)


def cargar_datos_dashboard(data_service, grupos_service, empresas_service, participantes_service, session_state):
    """Carga todos los datos necesarios para el dashboard con manejo de errores."""
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Paso 1: Grupos
        status_text.text("Cargando grupos...")
        progress_bar.progress(20)
        df_grupos = grupos_service.get_grupos_completos()
        
        # Paso 2: Participantes  
        status_text.text("Cargando participantes...")
        progress_bar.progress(40)
        df_participantes = participantes_service.get_participantes_completos()
        
        # Paso 3: Empresas
        status_text.text("Cargando empresas...")
        progress_bar.progress(60)
        df_empresas = empresas_service.get_empresas_con_jerarquia()
        
        # Paso 4: Tutores
        status_text.text("Cargando tutores...")
        progress_bar.progress(80)
        df_tutores = data_service.get_tutores_completos()
        
        # Paso 5: Acciones formativas
        status_text.text("Cargando acciones formativas...")
        progress_bar.progress(100)
        df_acciones = data_service.get_acciones_formativas()
        
        # Limpiar indicadores de progreso
        progress_bar.empty()
        status_text.empty()
        
        # Verificar datos mínimos
        if df_grupos.empty and df_participantes.empty and df_acciones.empty:
            st.warning("⚠️ No se encontraron datos. Verifica que haya información cargada en el sistema.")
            return None
        
        return df_grupos, df_participantes, df_empresas, df_tutores, df_acciones
        
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"❌ Error al cargar datos: {e}")
        return None


def mostrar_metricas_principales(df_grupos, df_participantes, df_empresas, df_tutores, df_acciones):
    """Métricas principales con diseño moderno y cálculos inteligentes."""
    
    st.subheader("📊 Resumen Ejecutivo")
    
    # Cálculos con manejo de datos vacíos
    total_acciones = len(df_acciones) if not df_acciones.empty else 0
    total_grupos = len(df_grupos) if not df_grupos.empty else 0
    total_participantes = len(df_participantes) if not df_participantes.empty else 0
    total_tutores = len(df_tutores) if not df_tutores.empty else 0
    total_empresas = len(df_empresas) if not df_empresas.empty else 0
    
    # Cálculos avanzados
    grupos_activos = 0
    participantes_nuevos_mes = 0
    
    if not df_grupos.empty and 'estado' in df_grupos.columns:
        grupos_activos = len(df_grupos[df_grupos['estado'].isin(['abierto', 'finalizar'])])
    
    if not df_participantes.empty and 'created_at' in df_participantes.columns:
        try:
            fecha_limite = datetime.now() - timedelta(days=30)
            df_temp = df_participantes.copy()
            df_temp['created_at'] = pd.to_datetime(df_temp['created_at'], errors='coerce')
            participantes_nuevos_mes = len(df_temp[
                df_temp['created_at'] > pd.Timestamp(fecha_limite, tz='UTC')
            ])
        except:
            pass

    # Layout de métricas con columnas responsivas
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "📚 Acciones Formativas", 
            total_acciones,
            help="Total de acciones formativas disponibles"
        )
    
    with col2:
        delta_grupos = f"{grupos_activos} activos" if grupos_activos > 0 else None
        st.metric(
            "👥 Grupos", 
            total_grupos,
            delta=delta_grupos,
            help="Grupos formativos totales y activos"
        )
    
    with col3:
        delta_part = f"+{participantes_nuevos_mes} este mes" if participantes_nuevos_mes > 0 else None
        st.metric(
            "🎓 Participantes", 
            total_participantes,
            delta=delta_part,
            help="Participantes registrados en el sistema"
        )
    
    with col4:
        st.metric(
            "👨‍🏫 Tutores", 
            total_tutores,
            help="Tutores disponibles para formación"
        )
    
    with col5:
        st.metric(
            "🏢 Empresas", 
            total_empresas,
            help="Empresas en el sistema"
        )

    # Indicadores de salud del sistema
    mostrar_indicadores_salud(df_grupos, df_participantes, df_acciones)


def mostrar_indicadores_salud(df_grupos, df_participantes, df_acciones):
    """Indicadores visuales de salud del sistema."""
    
    st.markdown("#### 🔍 Estado del Sistema")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Ocupación de grupos
        if not df_grupos.empty and not df_participantes.empty:
            grupos_con_participantes = len(df_participantes['grupo_id'].dropna().unique()) if 'grupo_id' in df_participantes.columns else 0
            total_grupos = len(df_grupos)
            ocupacion = (grupos_con_participantes / total_grupos * 100) if total_grupos > 0 else 0
            
            color = "🟢" if ocupacion > 70 else "🟡" if ocupacion > 40 else "🔴"
            st.metric(
                f"{color} Ocupación de Grupos",
                f"{ocupacion:.1f}%",
                help="Porcentaje de grupos con participantes asignados"
            )
        else:
            st.metric("📊 Ocupación de Grupos", "N/A")
    
    with col2:
        # Participantes por grupo (promedio)
        if not df_grupos.empty and not df_participantes.empty and 'grupo_id' in df_participantes.columns:
            participantes_por_grupo = df_participantes.groupby('grupo_id').size().mean()
            st.metric(
                "👥 Promedio por Grupo",
                f"{participantes_por_grupo:.1f}",
                help="Promedio de participantes por grupo"
            )
        else:
            st.metric("👥 Promedio por Grupo", "N/A")
    
    with col3:
        # Acciones más utilizadas
        if not df_grupos.empty and 'accion_formativa_id' in df_grupos.columns:
            acciones_utilizadas = len(df_grupos['accion_formativa_id'].dropna().unique())
            total_acciones = len(df_acciones) if not df_acciones.empty else 0
            utilizacion = (acciones_utilizadas / total_acciones * 100) if total_acciones > 0 else 0
            
            st.metric(
                "📈 Uso de Acciones",
                f"{utilizacion:.1f}%",
                help="Porcentaje de acciones formativas en uso"
            )
        else:
            st.metric("📈 Uso de Acciones", "N/A")


def mostrar_analytics_avanzadas(df_grupos, df_participantes, df_empresas, session_state):
    """Analytics avanzadas con gráficos modernos."""
    
    st.markdown("### 📈 Análisis Avanzado")
    
    if df_participantes.empty and df_grupos.empty:
        st.info("📊 Datos insuficientes para generar análisis.")
        return

    # Selector de período de análisis
    col_periodo, col_filtro = st.columns([2, 3])
    
    with col_periodo:
        periodo = st.selectbox(
            "📅 Período de análisis",
            ["Últimos 30 días", "Últimos 90 días", "Últimos 6 meses", "Todo el año"],
            index=2
        )
    
    with col_filtro:
        if session_state.role == "admin" and not df_empresas.empty:
            empresas_disponibles = ["Todas"] + df_empresas['nombre'].tolist()
            empresa_filtro = st.selectbox("🏢 Filtrar por empresa", empresas_disponibles)
        else:
            empresa_filtro = "Todas"

    # Aplicar filtros de período
    df_participantes_filtrado = aplicar_filtro_periodo(df_participantes, periodo)
    df_grupos_filtrado = aplicar_filtro_periodo(df_grupos, periodo)

    # Gráficos en dos columnas
    col_izq, col_der = st.columns(2)
    
    with col_izq:
        mostrar_evolucion_participantes(df_participantes_filtrado)
        
    with col_der:
        mostrar_distribucion_modalidades(df_grupos_filtrado)
    
    # Gráfico de línea temporal completo
    st.markdown("#### 📊 Evolución Temporal Completa")
    mostrar_timeline_completo(df_participantes_filtrado, df_grupos_filtrado)


def mostrar_evolucion_participantes(df_participantes):
    """Gráfico de evolución de participantes."""
    
    if df_participantes.empty or 'created_at' not in df_participantes.columns:
        st.info("📊 No hay datos de participantes para mostrar evolución.")
        return
    
    try:
        # Preparar datos
        df_temp = df_participantes.copy()
        df_temp['fecha'] = pd.to_datetime(df_temp['created_at'], errors='coerce')
        df_temp = df_temp.dropna(subset=['fecha'])
        
        if df_temp.empty:
            st.info("📊 No hay fechas válidas para mostrar evolución.")
            return
        
        # Agrupar por mes
        df_temp['mes'] = df_temp['fecha'].dt.to_period('M')
        evolucion = df_temp.groupby('mes').size().reset_index(name='nuevos')
        evolucion['mes_str'] = evolucion['mes'].astype(str)
        evolucion['acumulado'] = evolucion['nuevos'].cumsum()
        
        # Crear gráfico
        fig = go.Figure()
        
        # Barras
        fig.add_trace(go.Bar(
            x=evolucion['mes_str'],
            y=evolucion['nuevos'],
            name='Nuevos',
            marker_color='lightblue',
            opacity=0.7
        ))
        
        # Línea acumulada
        fig.add_trace(go.Scatter(
            x=evolucion['mes_str'],
            y=evolucion['acumulado'],
            mode='lines+markers',
            name='Total Acumulado',
            line=dict(color='blue', width=3),
            yaxis='y2'
        ))
        
        fig.update_layout(
            title="Evolución de Participantes",
            xaxis_title="Período",
            yaxis=dict(title="Nuevos Participantes", side="left"),
            yaxis2=dict(title="Total Acumulado", side="right", overlaying="y"),
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error al generar gráfico de evolución: {e}")


def mostrar_distribucion_modalidades(df_grupos):
    """Gráfico de distribución por modalidades."""
    
    if df_grupos.empty:
        st.info("📊 No hay datos de grupos para modalidades.")
        return
    
    try:
        modalidad_col = None
        # Buscar columna de modalidad
        for col in ['accion_modalidad', 'modalidad']:
            if col in df_grupos.columns:
                modalidad_col = col
                break
        
        if not modalidad_col:
            st.info("📊 No hay información de modalidad disponible.")
            return
        
        modalidades = df_grupos[modalidad_col].value_counts()
        
        if modalidades.empty:
            st.info("📊 No hay modalidades para mostrar.")
            return
        
        # Colores personalizados
        colores = {
            'PRESENCIAL': '#2ecc71',
            'TELEFORMACION': '#3498db', 
            'MIXTA': '#f39c12'
        }
        
        colors = [colores.get(mod, '#95a5a6') for mod in modalidades.index]
        
        fig = px.pie(
            values=modalidades.values,
            names=modalidades.index,
            title="Distribución por Modalidad",
            color_discrete_sequence=colors
        )
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(height=400)
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error al generar gráfico de modalidades: {e}")


def mostrar_timeline_completo(df_participantes, df_grupos):
    """Timeline completo con participantes y grupos."""
    
    try:
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Participantes por Mes', 'Grupos por Mes'),
            vertical_spacing=0.1
        )
        
        # Timeline participantes
        if not df_participantes.empty and 'created_at' in df_participantes.columns:
            df_temp = df_participantes.copy()
            df_temp['fecha'] = pd.to_datetime(df_temp['created_at'], errors='coerce')
            df_temp = df_temp.dropna(subset=['fecha'])
            
            if not df_temp.empty:
                df_temp['mes'] = df_temp['fecha'].dt.to_period('M')
                part_mes = df_temp.groupby('mes').size().reset_index(name='count')
                part_mes['mes_str'] = part_mes['mes'].astype(str)
                
                fig.add_trace(
                    go.Scatter(
                        x=part_mes['mes_str'],
                        y=part_mes['count'],
                        mode='lines+markers',
                        name='Participantes',
                        line=dict(color='blue', width=2),
                        marker=dict(size=8)
                    ),
                    row=1, col=1
                )
        
        # Timeline grupos
        if not df_grupos.empty and 'created_at' in df_grupos.columns:
            df_temp = df_grupos.copy()
            df_temp['fecha'] = pd.to_datetime(df_temp['created_at'], errors='coerce')
            df_temp = df_temp.dropna(subset=['fecha'])
            
            if not df_temp.empty:
                df_temp['mes'] = df_temp['fecha'].dt.to_period('M')
                grupos_mes = df_temp.groupby('mes').size().reset_index(name='count')
                grupos_mes['mes_str'] = grupos_mes['mes'].astype(str)
                
                fig.add_trace(
                    go.Bar(
                        x=grupos_mes['mes_str'],
                        y=grupos_mes['count'],
                        name='Grupos',
                        marker_color='lightgreen'
                    ),
                    row=2, col=1
                )
        
        fig.update_layout(
            height=600,
            showlegend=True,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error al generar timeline: {e}")


def aplicar_filtro_periodo(df, periodo):
    """Aplica filtro de período a un DataFrame."""
    
    if df.empty or 'created_at' not in df.columns:
        return df
    
    try:
        dias_map = {
            "Últimos 30 días": 30,
            "Últimos 90 días": 90, 
            "Últimos 6 meses": 180,
            "Todo el año": 365
        }
        
        dias = dias_map.get(periodo, 180)
        fecha_limite = datetime.now() - timedelta(days=dias)
        
        df_temp = df.copy()
        df_temp['created_at'] = pd.to_datetime(df_temp['created_at'], errors='coerce')
        
        return df_temp[df_temp['created_at'] > pd.Timestamp(fecha_limite, tz='UTC')]
        
    except Exception:
        return df


def mostrar_gestion_grupos(df_grupos, df_participantes, grupos_service, session_state):
    """Gestión avanzada de grupos con filtros y acciones."""
    
    st.markdown("### 👥 Gestión de Grupos Activos")
    
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados en el sistema.")
        return

    # Filtros avanzados
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        estados_disponibles = ['Todos']
        if 'estado' in df_grupos.columns:
            estados_disponibles.extend(df_grupos['estado'].dropna().unique().tolist())
        estado_filtro = st.selectbox("🔄 Estado", estados_disponibles)
    
    with col2:
        modalidades_disponibles = ['Todas']
        modalidad_col = 'accion_modalidad' if 'accion_modalidad' in df_grupos.columns else 'modalidad'
        if modalidad_col in df_grupos.columns:
            modalidades_disponibles.extend(df_grupos[modalidad_col].dropna().unique().tolist())
        modalidad_filtro = st.selectbox("🎓 Modalidad", modalidades_disponibles)
    
    with col3:
        fecha_filtro = st.date_input("📅 Desde fecha", value=None)
    
    with col4:
        busqueda = st.text_input("🔍 Buscar", placeholder="Código o nombre...")

    # Aplicar filtros
    df_filtrado = aplicar_filtros_grupos(df_grupos, estado_filtro, modalidad_filtro, fecha_filtro, busqueda)
    
    # Mostrar resultados
    if not df_filtrado.empty:
        st.info(f"📊 {len(df_filtrado)} de {len(df_grupos)} grupos")
        
        # Vista de grupos en cards modernas
        mostrar_grupos_cards(df_filtrado, df_participantes, session_state)
    else:
        st.warning("🔍 No se encontraron grupos que coincidan con los filtros.")


def aplicar_filtros_grupos(df, estado_filtro, modalidad_filtro, fecha_filtro, busqueda):
    """Aplica todos los filtros a los grupos."""
    
    df_filtrado = df.copy()
    
    # Filtro por estado
    if estado_filtro != 'Todos' and 'estado' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['estado'] == estado_filtro]
    
    # Filtro por modalidad
    modalidad_col = 'accion_modalidad' if 'accion_modalidad' in df_filtrado.columns else 'modalidad'
    if modalidad_filtro != 'Todas' and modalidad_col in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado[modalidad_col] == modalidad_filtro]
    
    # Filtro por fecha
    if fecha_filtro:
        fecha_col = None
        for col in ['fecha_inicio', 'created_at']:
            if col in df_filtrado.columns:
                fecha_col = col
                break
        
        if fecha_col:
            try:
                df_filtrado[fecha_col] = pd.to_datetime(df_filtrado[fecha_col], errors='coerce')
                df_filtrado = df_filtrado[df_filtrado[fecha_col] >= pd.Timestamp(fecha_filtro)]
            except:
                pass
    
    # Filtro por búsqueda
    if busqueda:
        mask = False
        for col in ['codigo_grupo', 'accion_nombre']:
            if col in df_filtrado.columns:
                mask |= df_filtrado[col].str.contains(busqueda, case=False, na=False)
        if mask is not False:
            df_filtrado = df_filtrado[mask]
    
    return df_filtrado


def mostrar_grupos_cards(df_grupos, df_participantes, session_state):
    """Muestra grupos en formato de cards modernas."""
    
    # Paginación
    page_size = st.selectbox("📄 Grupos por página", [6, 12, 24], index=0)
    
    total_pages = (len(df_grupos) + page_size - 1) // page_size
    page = st.number_input("Página", 1, max(total_pages, 1), 1) - 1
    
    start_idx = page * page_size
    end_idx = start_idx + page_size
    df_pagina = df_grupos.iloc[start_idx:end_idx]
    
    # Mostrar groups en grid
    cols = st.columns(3)  # 3 columnas para las cards
    
    for idx, (_, grupo) in enumerate(df_pagina.iterrows()):
        col_idx = idx % 3
        
        with cols[col_idx]:
            mostrar_card_grupo(grupo, df_participantes)


def mostrar_card_grupo(grupo, df_participantes):
    """Muestra una card individual de grupo."""
    
    codigo = grupo.get('codigo_grupo', f"Grupo {grupo['id']}")
    accion = grupo.get('accion_nombre', 'Sin acción')
    estado = grupo.get('estado', 'Sin estado')
    modalidad = grupo.get('accion_modalidad', 'No definida')
    
    # Contar participantes
    num_participantes = 0
    if not df_participantes.empty and 'grupo_id' in df_participantes.columns:
        num_participantes = len(df_participantes[df_participantes['grupo_id'] == grupo['id']])
    
    # Color del estado
    colores_estado = {
        'abierto': '🟢',
        'finalizar': '🟡',
        'finalizado': '🔵',
        'cancelado': '🔴'
    }
    color = colores_estado.get(estado.lower() if isinstance(estado, str) else '', '⚪')
    
    # Card con container border
    with st.container(border=True):
        st.markdown(f"**{color} {codigo}**")
        st.caption(f"📚 {accion}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👥 Participantes", num_participantes)
        with col2:
            st.caption(f"📖 {modalidad}")
        
        # Fechas si están disponibles
        fecha_inicio = grupo.get('fecha_inicio')
        if fecha_inicio:
            try:
                fecha_fmt = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')
                st.caption(f"📅 Inicio: {fecha_fmt}")
            except:
                st.caption(f"📅 Inicio: {fecha_inicio}")
        
        # Botón de acción
        if st.button("👁️ Ver detalle", key=f"grupo_{grupo['id']}", use_container_width=True):
            mostrar_detalle_grupo_modal(grupo, df_participantes)


def mostrar_detalle_grupo_modal(grupo, df_participantes):
    """Muestra detalle de grupo en modal."""
    
    # Usar dialog si está disponible en Streamlit 1.49, sino usar expander
    try:
        with st.dialog(f"Grupo: {grupo.get('codigo_grupo', 'Sin código')}"):
            mostrar_detalle_grupo_completo(grupo, df_participantes)
    except:
        # Fallback para versiones anteriores
        with st.expander(f"📋 Detalle: {grupo.get('codigo_grupo', 'Sin código')}", expanded=True):
            mostrar_detalle_grupo_completo(grupo, df_participantes)


def mostrar_detalle_grupo_completo(grupo, df_participantes):
    """Contenido completo del detalle de grupo."""
    
    # Información general
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("🆔 Código", grupo.get('codigo_grupo', 'N/A'))
        st.metric("📚 Acción", grupo.get('accion_nombre', 'N/A'))
        st.metric("🔄 Estado", grupo.get('estado', 'N/A'))
    
    with col2:
        st.metric("📖 Modalidad", grupo.get('accion_modalidad', 'N/A'))
        st.metric("⏰ Horas", grupo.get('accion_horas', 'N/A'))
        st.metric("📍 Localidad", grupo.get('localidad', 'N/A'))
    
    # Fechas del grupo
    st.markdown("#### 📅 Fechas")
    col_fechas1, col_fechas2 = st.columns(2)
    
    with col_fechas1:
        fecha_inicio = grupo.get('fecha_inicio')
        if fecha_inicio:
            try:
                fecha_fmt = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')
                st.info(f"🚀 Inicio: {fecha_fmt}")
            except:
                st.info(f"🚀 Inicio: {fecha_inicio}")
        else:
            st.info("🚀 Inicio: No definida")
    
    with col_fechas2:
        fecha_fin = grupo.get('fecha_fin_prevista') or grupo.get('fecha_fin')
        if fecha_fin:
            try:
                fecha_fmt = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                st.info(f"🏁 Fin: {fecha_fmt}")
            except:
                st.info(f"🏁 Fin: {fecha_fin}")
        else:
            st.info("🏁 Fin: No definida")
    
    # Lista de participantes
    if not df_participantes.empty and 'grupo_id' in df_participantes.columns:
        participantes_grupo = df_participantes[df_participantes['grupo_id'] == grupo['id']]
        
        if not participantes_grupo.empty:
            st.markdown("#### 👥 Participantes")
            
            # Seleccionar columnas disponibles
            columnas_mostrar = []
            for col in ['nombre', 'apellidos', 'email', 'dni']:
                if col in participantes_grupo.columns:
                    columnas_mostrar.append(col)
            
            if columnas_mostrar:
                df_display = participantes_grupo[columnas_mostrar].copy()
                
                # Formatear nombre completo
                if 'nombre' in df_display.columns and 'apellidos' in df_display.columns:
                    df_display['Nombre Completo'] = (
                        df_display['nombre'].fillna('') + ' ' + 
                        df_display['apellidos'].fillna('')
                    ).str.strip()
                    df_display = df_display.drop(['nombre', 'apellidos'], axis=1)
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            else:
                st.info("Información de participantes no disponible")
        else:
            st.info("No hay participantes asignados a este grupo")


def mostrar_resumen_participantes(df_participantes, df_grupos, session_state):
    """Resumen avanzado de participantes."""
    
    st.markdown("### 🎓 Resumen de Participantes")
    
    if df_participantes.empty:
        st.info("👥 No hay participantes registrados en el sistema.")
        return

    # Métricas de participantes
    col1, col2, col3, col4 = st.columns(4)
    
    total_participantes = len(df_participantes)
    
    with col1:
        st.metric("👥 Total", total_participantes)
    
    with col2:
        con_grupo = len(df_participantes[df_participantes['grupo_id'].notna()]) if 'grupo_id' in df_participantes.columns else 0
        st.metric("🎓 Con Grupo", con_grupo)
    
    with col3:
        sin_grupo = total_participantes - con_grupo
        st.metric("❓ Sin Grupo", sin_grupo)
    
    with col4:
        # Participantes activos (últimos 30 días)
        activos_mes = 0
        if 'created_at' in df_participantes.columns:
            try:
                fecha_limite = datetime.now() - timedelta(days=30)
                df_temp = df_participantes.copy()
                df_temp['created_at'] = pd.to_datetime(df_temp['created_at'], errors='coerce')
                activos_mes = len(df_temp[df_temp['created_at'] > pd.Timestamp(fecha_limite, tz='UTC')])
            except:
                pass
        st.metric("🆕 Nuevos (30d)", activos_mes)

    # Gráfico de asignación de grupos
    if 'grupo_id' in df_participantes.columns:
        st.markdown("#### 📊 Distribución por Asignación")
        
        data_asignacion = {
            'Estado': ['Con Grupo', 'Sin Grupo'],
            'Cantidad': [con_grupo, sin_grupo]
        }
        
        fig = px.pie(
            values=data_asignacion['Cantidad'],
            names=data_asignacion['Estado'],
            title="Asignación a Grupos",
            color_discrete_map={'Con Grupo': '#2ecc71', 'Sin Grupo': '#e74c3c'}
        )
        
        st.plotly_chart(fig, use_container_width=True)

    # Top 5 grupos con más participantes
    if not df_grupos.empty and 'grupo_id' in df_participantes.columns:
        st.markdown("#### 🏆 Top Grupos por Participantes")
        
        participantes_por_grupo = df_participantes['grupo_id'].value_counts().head(5)
        
        if not participantes_por_grupo.empty:
            # Obtener nombres de grupos
            top_grupos_info = []
            for grupo_id, count in participantes_por_grupo.items():
                grupo_info = df_grupos[df_grupos['id'] == grupo_id]
                if not grupo_info.empty:
                    nombre = grupo_info.iloc[0].get('codigo_grupo', f'Grupo {grupo_id}')
                    top_grupos_info.append({'nombre': nombre, 'participantes': count})
            
            if top_grupos_info:
                df_top = pd.DataFrame(top_grupos_info)
                
                fig = px.bar(
                    df_top,
                    x='participantes',
                    y='nombre',
                    orientation='h',
                    title="Grupos con Más Participantes",
                    labels={'participantes': 'Número de Participantes', 'nombre': 'Grupo'}
                )
                
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)


def mostrar_resumen_empresas(df_empresas, session_state):
    """Resumen de empresas según rol."""
    
    st.markdown("### 🏢 Resumen de Empresas")
    
    if df_empresas.empty:
        st.info("🏢 No hay empresas disponibles.")
        return

    # Filtro por rol
    if session_state.role == "gestor":
        empresa_id = session_state.user.get("empresa_id")
        df_empresas = df_empresas[
            (df_empresas["id"] == empresa_id) | 
            (df_empresas["empresa_matriz_id"] == empresa_id)
        ]

    if df_empresas.empty:
        st.info("🏢 No hay empresas asignadas a tu gestión.")
        return

    # Métricas de empresas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_empresas = len(df_empresas)
        st.metric("🏢 Total", total_empresas)
    
    with col2:
        if 'formacion_activo' in df_empresas.columns:
            con_formacion = len(df_empresas[df_empresas['formacion_activo'] == True])
            st.metric("📚 Con Formación", con_formacion)
        else:
            st.metric("📚 Con Formación", "N/A")
    
    with col3:
        if 'tipo_empresa' in df_empresas.columns:
            gestoras = len(df_empresas[df_empresas['tipo_empresa'] == 'GESTORA'])
            st.metric("🎯 Gestoras", gestoras)
        else:
            st.metric("🎯 Gestoras", "N/A")
    
    with col4:
        if 'tipo_empresa' in df_empresas.columns:
            clientes = len(df_empresas[df_empresas['tipo_empresa'] == 'CLIENTE_GESTOR'])
            st.metric("👥 Clientes", clientes)
        else:
            st.metric("👥 Clientes", "N/A")

    # Distribución por tipo de empresa
    if 'tipo_empresa' in df_empresas.columns:
        st.markdown("#### 📊 Distribución por Tipo")
        
        tipos = df_empresas['tipo_empresa'].value_counts()
        
        if not tipos.empty:
            # Mapeo de nombres más amigables
            nombres_tipos = {
                'CLIENTE_SAAS': 'Cliente SaaS',
                'GESTORA': 'Gestora',
                'CLIENTE_GESTOR': 'Cliente de Gestora'
            }
            
            tipos_display = tipos.rename(index=nombres_tipos)
            
            fig = px.bar(
                x=tipos_display.values,
                y=tipos_display.index,
                orientation='h',
                title="Empresas por Tipo",
                labels={'x': 'Cantidad', 'y': 'Tipo de Empresa'}
            )
            
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    # Lista de empresas
    st.markdown("#### 📋 Lista de Empresas")
    
    columnas_mostrar = ['nombre', 'cif', 'ciudad', 'tipo_empresa']
    columnas_disponibles = [col for col in columnas_mostrar if col in df_empresas.columns]
    
    if columnas_disponibles:
        df_display = df_empresas[columnas_disponibles].copy()
        
        # Formatear tipo de empresa
        if 'tipo_empresa' in df_display.columns:
            nombres_tipos = {
                'CLIENTE_SAAS': 'Cliente SaaS',
                'GESTORA': 'Gestora',
                'CLIENTE_GESTOR': 'Cliente de Gestora'
            }
            df_display['tipo_empresa'] = df_display['tipo_empresa'].map(nombres_tipos).fillna(df_display['tipo_empresa'])
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)


def mostrar_documentacion_fundae_moderna():
    """Documentación FUNDAE con diseño moderno."""
    
    st.markdown("### 📋 Documentación FUNDAE")
    st.caption("Enlaces oficiales a modelos y documentos FUNDAE organizados por categorías")

    # Usar columns para mejor organización
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📄 Contratación")
        with st.container(border=True):
            st.markdown("- [📋 Contrato de encomienda](https://www.fundae.es/DocumentosModelos/Contrato%20de%20encomienda.pdf)")
            st.markdown("- [❌ Desistimiento del contrato](https://www.fundae.es/DocumentosModelos/Desistimiento%20contrato%20encomienda.pdf)")
        
        st.markdown("#### 🎓 Impartición")
        with st.container(border=True):
            st.markdown("- [📝 Control de asistencia](https://www.fundae.es/DocumentosModelos/Control%20de%20asistencia.pdf)")
            st.markdown("- [🏆 Diploma](https://www.fundae.es/DocumentosModelos/Diploma.pdf)")
            st.markdown("- [📜 Certificado de asistencia](https://www.fundae.es/DocumentosModelos/Certificado%20asistencia.pdf)")
            st.markdown("- [💻 Declaración aula virtual 2024](https://www.fundae.es/DocumentosModelos/Declaracion%20aula%20virtual%202024.pdf)")
            st.markdown("- [💻 Declaración aula virtual 2025](https://www.fundae.es/DocumentosModelos/Declaracion%20aula%20virtual%202025.pdf)")
    
    with col2:
        st.markdown("#### 👥 RLT")
        with st.container(border=True):
            st.markdown("- [ℹ️ Información a la RLT](https://www.fundae.es/DocumentosModelos/Informacion%20RLT.pdf)")
            st.markdown("- [⚖️ Acta de discrepancias](https://www.fundae.es/DocumentosModelos/Acta%20de%20discrepancias.pdf)")
            st.markdown("- [📨 Solicitud información RLT](https://www.fundae.es/DocumentosModelos/Solicitud%20informacion%20RLT.pdf)")
        
        st.markdown("#### 💰 Costes y Evaluación")
        with st.container(border=True):
            st.markdown("- [💼 B1. Resumen de costes](https://www.fundae.es/DocumentosModelos/B1%20Resumen%20costes.pdf)")
            st.markdown("- [📊 Anexos de costes](https://www.fundae.es/DocumentosModelos/Anexos%20costes.pdf)")
            st.markdown("- [📈 Guía de orientación de costes](https://www.fundae.es/DocumentosModelos/Guia%20costes.pdf)")
            st.markdown("- [📋 Manual evaluación calidad](https://www.fundae.es/DocumentosModelos/Manual%20evaluacion%20calidad.pdf)")

    # Información adicional
    st.info("💡 Todos los documentos son oficiales de FUNDAE. Se abren en nueva ventana.")


def mostrar_footer_informativo(session_state):
    """Footer con información útil del sistema."""
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption(f"🔄 Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    with col2:
        if session_state.role == "gestor":
            empresa_nombre = session_state.user.get("empresa_nombre", "Tu empresa")
            st.caption(f"🏢 Empresa: {empresa_nombre}")
        else:
            st.caption("👑 Vista de administrador")
    
    with col3:
        st.caption("📊 Panel FUNDAE v2.0")
