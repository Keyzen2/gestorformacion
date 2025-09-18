import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from services.data_service import get_data_service
from services.grupos_service import get_grupos_service

def main(supabase, session_state):
    """Panel del Gestor - Versión Corregida y Mejorada"""
    
    st.title("📊 Panel del Gestor")
    st.caption("Visión general de la plataforma para gestores y administradores.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # =========================
    # Inicializar servicios
    # =========================
    try:
        data_service = get_data_service(supabase, session_state)
        grupos_service = get_grupos_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error al inicializar servicios: {e}")
        return

    # =========================
    # Cargar todos los datos necesarios
    # =========================
    with st.spinner("Cargando información..."):
        try:
            # Cargar datos principales
            df_grupos = grupos_service.get_grupos_completos()
            df_participantes = data_service.get_participantes_completos()
            df_tutores = data_service.get_tutores_completos() 
            df_acciones = data_service.get_acciones_formativas()
            
            # Intentar cargar proyectos si existe el servicio
            df_proyectos = pd.DataFrame()
            try:
                from services.proyectos_service import get_proyectos_service
                proyectos_service = get_proyectos_service(supabase, session_state)
                df_proyectos = proyectos_service.get_proyectos_completos()
            except ImportError:
                pass  # Proyectos no disponible
                
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return

    # =========================
    # Métricas principales con st.metrics mejoradas
    # =========================
    st.subheader("📌 Resumen General")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_acciones = len(df_acciones)
        st.metric(
            "📚 Acciones", 
            total_acciones,
            help="Acciones formativas disponibles"
        )
    
    with col2:
        total_grupos = len(df_grupos)
        # 🔧 CORRECCIÓN: Verificar si existe la columna 'estado' antes de usarla
        if not df_grupos.empty and 'estado' in df_grupos.columns:
            grupos_activos = len(df_grupos[df_grupos['estado'] == 'abierto'])
        else:
            grupos_activos = 0
            
        st.metric(
            "👥 Grupos", 
            total_grupos,
            delta=f"{grupos_activos} activos" if grupos_activos > 0 else None,
            help="Total de grupos formativos"
        )
    
    with col3:
        total_participantes = len(df_participantes)
        # Participantes del último mes - VERSIÓN CORREGIDA
        if not df_participantes.empty and 'created_at' in df_participantes.columns:
            try:
                fecha_mes_pasado = datetime.now() - timedelta(days=30)
                df_temp = df_participantes.copy()
                # Convertir a datetime con UTC para comparación segura
                df_temp['created_at'] = pd.to_datetime(df_temp['created_at'], errors='coerce', utc=True)
                fecha_limite = pd.Timestamp(fecha_mes_pasado, tz='UTC')
                nuevos_mes = len(df_temp[df_temp['created_at'] > fecha_limite])
                delta_part = f"+{nuevos_mes} este mes" if nuevos_mes > 0 else None
            except Exception:
                delta_part = None
        else:
            delta_part = None
            
        st.metric(
            "🧑‍🎓 Participantes", 
            total_participantes,
            delta=delta_part,
            help="Participantes registrados"
        )
    
    with col4:
        total_tutores = len(df_tutores)
        st.metric(
            "👨‍🏫 Tutores", 
            total_tutores,
            help="Tutores disponibles"
        )
    
    with col5:
        if not df_proyectos.empty:
            total_proyectos = len(df_proyectos)
            proyectos_activos = len(df_proyectos[
                df_proyectos.get('estado_proyecto', 'CONVOCADO') == 'EN_EJECUCION'
            ]) if 'estado_proyecto' in df_proyectos.columns else 0
            
            st.metric(
                "🎯 Proyectos",
                total_proyectos,
                delta=f"{proyectos_activos} en ejecución" if proyectos_activos > 0 else None,
                help="Proyectos de formación"
            )
        else:
            st.metric("🎯 Proyectos", 0, help="Módulo de proyectos no disponible")

    st.divider()

    # =========================
    # Pestañas para organizar contenido
    # =========================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Analíticas", 
        "👥 Grupos y Participantes", 
        "🎯 Proyectos",
        "📋 Documentación FUNDAE"
    ])

    with tab1:
        mostrar_analytics(df_participantes, df_grupos, df_proyectos)

    with tab2:
        mostrar_grupos_participantes(df_grupos, df_participantes, grupos_service)

    with tab3:
        mostrar_resumen_proyectos(df_proyectos)

    with tab4:
        mostrar_documentacion_fundae()

    # Footer con información de actualización
    st.divider()
    st.caption(f"🔄 Datos actualizados automáticamente - Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")


def mostrar_analytics(df_participantes, df_grupos, df_proyectos):
    """Mostrar gráficos analíticos"""
    
    st.markdown("### 📈 Analíticas y Tendencias")
    
    if df_participantes.empty and df_grupos.empty:
        st.info("📝 No hay datos suficientes para mostrar analíticas.")
        return

    # Gráfico de evolución de participantes
    if not df_participantes.empty and 'created_at' in df_participantes.columns:
        st.markdown("#### 📊 Evolución de Participantes")
        
        try:
            # Preparar datos de fecha
            df_part_clean = df_participantes.copy()
            df_part_clean['fecha_registro'] = pd.to_datetime(
                df_part_clean['created_at'], 
                errors='coerce'
            )
            
            # Filtrar fechas válidas y últimos 6 meses
            df_part_valid = df_part_clean[df_part_clean['fecha_registro'].notna()].copy()
            fecha_limite = datetime.now() - timedelta(days=180)  # 6 meses
            # Convertir fecha_limite a timestamp con timezone para comparación segura
            fecha_limite_tz = pd.Timestamp(fecha_limite, tz='UTC')
            df_part_recent = df_part_valid[df_part_valid['fecha_registro'] > fecha_limite_tz]
            
            if not df_part_recent.empty:
                # Agrupar por mes
                df_part_recent['mes'] = df_part_recent['fecha_registro'].dt.to_period('M')
                participantes_por_mes = df_part_recent.groupby('mes').size().reset_index(name='nuevos')
                participantes_por_mes['mes_str'] = participantes_por_mes['mes'].astype(str)
                participantes_por_mes['acumulados'] = participantes_por_mes['nuevos'].cumsum()
                
                # Crear gráfico con Plotly
                fig = make_subplots(
                    rows=1, cols=1,
                    subplot_titles=['Participantes Nuevos por Mes']
                )
                
                # Barras para nuevos participantes
                fig.add_trace(
                    go.Bar(
                        x=participantes_por_mes['mes_str'],
                        y=participantes_por_mes['nuevos'],
                        name='Nuevos',
                        marker_color='lightblue',
                        yaxis='y'
                    )
                )
                
                # Línea para acumulados
                fig.add_trace(
                    go.Scatter(
                        x=participantes_por_mes['mes_str'],
                        y=participantes_por_mes['acumulados'],
                        mode='lines+markers',
                        name='Acumulados',
                        line=dict(color='blue', width=3),
                        yaxis='y2'
                    )
                )
                
                fig.update_layout(
                    height=400,
                    xaxis_title="Mes",
                    yaxis=dict(title="Nuevos Participantes", side="left"),
                    yaxis2=dict(title="Total Acumulado", side="right", overlaying="y"),
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay participantes registrados en los últimos 6 meses")
                
        except Exception as e:
            st.error(f"Error al generar gráfico de evolución: {e}")

    # Distribución por modalidad de grupos
    if not df_grupos.empty:
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("#### 📚 Distribución por Modalidad")
            
            try:
                if 'accion_modalidad' in df_grupos.columns:
                    modalidades = df_grupos['accion_modalidad'].value_counts()
                    
                    if not modalidades.empty:
                        fig_modalidad = px.pie(
                            values=modalidades.values,
                            names=modalidades.index,
                            title="Modalidades de Formación"
                        )
                        st.plotly_chart(fig_modalidad, use_container_width=True)
                    else:
                        st.info("No hay datos de modalidad disponibles")
                else:
                    st.info("Información de modalidad no disponible")
                    
            except Exception as e:
                st.error(f"Error al generar gráfico de modalidades: {e}")

        with col_right:
            st.markdown("#### 📅 Estados de Grupos")
            
            try:
                if 'estado' in df_grupos.columns:
                    estados = df_grupos['estado'].value_counts()
                    
                    if not estados.empty:
                        colores_estado = {
                            'abierto': '#2ecc71',
                            'finalizar': '#f39c12', 
                            'finalizado': '#3498db',
                            'cancelado': '#e74c3c'
                        }
                        
                        colors = [colores_estado.get(estado.lower(), '#95a5a6') for estado in estados.index]
                        
                        fig_estados = px.bar(
                            x=estados.index,
                            y=estados.values,
                            title="Estados de los Grupos",
                            color=estados.index,
                            color_discrete_map=colores_estado
                        )
                        fig_estados.update_layout(showlegend=False)
                        st.plotly_chart(fig_estados, use_container_width=True)
                    else:
                        st.info("No hay datos de estado disponibles")
                else:
                    # Calcular estados basado en fechas si no existe la columna
                    st.info("Calculando estados basado en fechas...")
                    estados_calculados = calcular_estados_grupos(df_grupos)
                    if estados_calculados:
                        fig_estados = px.bar(
                            x=list(estados_calculados.keys()),
                            y=list(estados_calculados.values()),
                            title="Estados de los Grupos (Calculados)"
                        )
                        st.plotly_chart(fig_estados, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Error al generar gráfico de estados: {e}")


def mostrar_grupos_participantes(df_grupos, df_participantes, grupos_service):
    """Mostrar información detallada de grupos y participantes"""
    
    st.markdown("### 👥 Información de Grupos y Participantes")
    
    if df_grupos.empty:
        st.info("📝 No hay grupos registrados.")
        return

    # Filtros
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
    
    with col_filtro1:
        estados_disponibles = ['Todos'] + df_grupos['estado'].dropna().unique().tolist() if 'estado' in df_grupos.columns else ['Todos']
        filtro_estado = st.selectbox("Filtrar por estado", estados_disponibles)
    
    with col_filtro2:
        modalidades_disponibles = ['Todas'] + df_grupos['accion_modalidad'].dropna().unique().tolist() if 'accion_modalidad' in df_grupos.columns else ['Todas']
        filtro_modalidad = st.selectbox("Filtrar por modalidad", modalidades_disponibles)
    
    with col_filtro3:
        buscar_texto = st.text_input("🔍 Buscar grupo", placeholder="Código o nombre...")

    # Aplicar filtros
    df_filtrado = df_grupos.copy()
    
    if filtro_estado != 'Todos' and 'estado' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['estado'] == filtro_estado]
    
    if filtro_modalidad != 'Todas' and 'accion_modalidad' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['accion_modalidad'] == filtro_modalidad]
    
    if buscar_texto:
        mask_busqueda = (
            df_filtrado.get('codigo_grupo', pd.Series(dtype='object')).str.contains(buscar_texto, case=False, na=False) |
            df_filtrado.get('accion_nombre', pd.Series(dtype='object')).str.contains(buscar_texto, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask_busqueda]

    # Mostrar grupos filtrados
    if not df_filtrado.empty:
        st.info(f"📊 Mostrando {len(df_filtrado)} de {len(df_grupos)} grupos")
        
        # Mostrar cada grupo con participantes
        for _, grupo in df_filtrado.iterrows():
            mostrar_grupo_detalle(grupo, df_participantes)
    else:
        st.warning("No se encontraron grupos que coincidan con los filtros")


def mostrar_grupo_detalle(grupo, df_participantes):
    """Mostrar detalle de un grupo específico"""
    
    codigo_grupo = grupo.get('codigo_grupo', f"Grupo {grupo['id']}")
    accion_nombre = grupo.get('accion_nombre', 'Sin acción')
    estado = grupo.get('estado', 'No definido')
    modalidad = grupo.get('accion_modalidad', 'No definida')
    
    # Buscar participantes del grupo
    if not df_participantes.empty and 'grupo_id' in df_participantes.columns:
        participantes_grupo = df_participantes[df_participantes['grupo_id'] == grupo['id']]
    else:
        participantes_grupo = pd.DataFrame()
    
    num_participantes = len(participantes_grupo)
    
    # Color del estado
    color_estado = {
        'abierto': '🟢',
        'finalizar': '🟡', 
        'finalizado': '🔵',
        'cancelado': '🔴'
    }.get(estado.lower() if isinstance(estado, str) else 'no definido', '⚪')
    
    with st.expander(f"{color_estado} {codigo_grupo} - {accion_nombre} ({num_participantes} participantes)", expanded=False):
        # Información del grupo
        col_info1, col_info2, col_info3, col_info4 = st.columns(4)
        
        with col_info1:
            st.write(f"**Estado:** {estado}")
            st.write(f"**Modalidad:** {modalidad}")
        
        with col_info2:
            fecha_inicio = grupo.get('fecha_inicio')
            if fecha_inicio:
                try:
                    fecha_formatted = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')
                    st.write(f"**Inicio:** {fecha_formatted}")
                except:
                    st.write(f"**Inicio:** {fecha_inicio}")
            else:
                st.write("**Inicio:** No definida")
        
        with col_info3:
            fecha_fin = grupo.get('fecha_fin_prevista') or grupo.get('fecha_fin')
            if fecha_fin:
                try:
                    fecha_formatted = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                    st.write(f"**Fin:** {fecha_formatted}")
                except:
                    st.write(f"**Fin:** {fecha_fin}")
            else:
                st.write("**Fin:** No definida")
        
        with col_info4:
            localidad = grupo.get('localidad', 'No especificada')
            st.write(f"**Localidad:** {localidad}")
        
        # Lista de participantes
        if not participantes_grupo.empty:
            st.markdown("**👥 Participantes:**")
            
            # Seleccionar columnas disponibles
            columnas_mostrar = []
            for col in ['nombre', 'apellidos', 'email', 'dni', 'telefono']:
                if col in participantes_grupo.columns:
                    columnas_mostrar.append(col)
            
            if columnas_mostrar:
                # Crear DataFrame para mostrar
                df_display = participantes_grupo[columnas_mostrar].copy()
                
                # Formatear nombres completos si tenemos nombre y apellidos
                if 'nombre' in df_display.columns and 'apellidos' in df_display.columns:
                    df_display['Nombre Completo'] = df_display['nombre'].fillna('') + ' ' + df_display['apellidos'].fillna('')
                    df_display = df_display.drop(['nombre', 'apellidos'], axis=1)
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            else:
                st.info("Información de participantes no disponible")
        else:
            st.info("No hay participantes asignados a este grupo")


def mostrar_resumen_proyectos(df_proyectos):
    """Mostrar resumen de proyectos si están disponibles"""
    
    st.markdown("### 🎯 Resumen de Proyectos")
    
    if df_proyectos.empty:
        st.info("📝 No hay proyectos registrados o el módulo de proyectos no está disponible.")
        return

    # Métricas de proyectos
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_proyectos = len(df_proyectos)
        st.metric("📁 Total Proyectos", total_proyectos)
    
    with col2:
        if 'estado_proyecto' in df_proyectos.columns:
            activos = len(df_proyectos[df_proyectos['estado_proyecto'] == 'EN_EJECUCION'])
            st.metric("🔄 En Ejecución", activos)
        else:
            st.metric("🔄 En Ejecución", "N/A")
    
    with col3:
        if 'presupuesto_total' in df_proyectos.columns:
            presupuesto_total = df_proyectos['presupuesto_total'].fillna(0).sum()
            st.metric("💰 Presupuesto Total", f"{presupuesto_total:,.0f}€")
        else:
            st.metric("💰 Presupuesto Total", "N/A")
    
    with col4:
        if 'importe_concedido' in df_proyectos.columns:
            concedido = df_proyectos['importe_concedido'].fillna(0).sum()
            st.metric("✅ Importe Concedido", f"{concedido:,.0f}€")
        else:
            st.metric("✅ Importe Concedido", "N/A")

    # Gráfico de estados de proyectos
    if 'estado_proyecto' in df_proyectos.columns:
        st.markdown("#### 📊 Estados de Proyectos")
        
        estados = df_proyectos['estado_proyecto'].value_counts()
        
        if not estados.empty:
            fig_estados = px.pie(
                values=estados.values,
                names=estados.index,
                title="Distribución por Estado"
            )
            st.plotly_chart(fig_estados, use_container_width=True)

    # Lista de proyectos más recientes
    st.markdown("#### 📋 Proyectos Recientes")
    
    columnas_mostrar = ['nombre', 'tipo_proyecto', 'estado_proyecto', 'fecha_inicio', 'presupuesto_total']
    columnas_disponibles = [col for col in columnas_mostrar if col in df_proyectos.columns]
    
    if columnas_disponibles:
        df_display = df_proyectos[columnas_disponibles].head(10)
        
        # Formatear presupuesto
        if 'presupuesto_total' in df_display.columns:
            df_display['presupuesto_total'] = df_display['presupuesto_total'].fillna(0).apply(
                lambda x: f"{x:,.0f}€" if x > 0 else "Sin presupuesto"
            )
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)


def mostrar_documentacion_fundae():
    """Mostrar documentación FUNDAE organizada"""
    
    st.markdown("### 📋 Documentación y Modelos FUNDAE")
    st.caption("Enlaces oficiales a modelos y documentos publicados por FUNDAE")

    # Organizar en pestañas
    tab_contrat, tab_rlt, tab_impart, tab_eval, tab_costes, tab_pif = st.tabs([
        "📄 Contratación", "👥 RLT", "🎓 Impartición", 
        "📊 Evaluación", "💰 Costes", "🎯 PIF"
    ])

    with tab_contrat:
        st.markdown("#### 📋 Contratación entidad organizadora")
        st.markdown("- [Contrato de encomienda](https://www.fundae.es/DocumentosModelos/Contrato%20de%20encomienda.pdf)")
        st.markdown("- [Desistimiento del contrato](https://www.fundae.es/DocumentosModelos/Desistimiento%20contrato%20encomienda.pdf)")

    with tab_rlt:
        st.markdown("#### 👥 Representación Legal de los Trabajadores (RLT)")
        st.markdown("- [Información a la RLT](https://www.fundae.es/DocumentosModelos/Informacion%20RLT.pdf)")
        st.markdown("- [Acta de discrepancias](https://www.fundae.es/DocumentosModelos/Acta%20de%20discrepancias.pdf)")
        st.markdown("- [Solicitud de información de la RLT](https://www.fundae.es/DocumentosModelos/Solicitud%20informacion%20RLT.pdf)")

    with tab_impart:
        st.markdown("#### 🎓 Impartición")
        st.markdown("- [Control de asistencia](https://www.fundae.es/DocumentosModelos/Control%20de%20asistencia.pdf)")
        st.markdown("- [Diploma](https://www.fundae.es/DocumentosModelos/Diploma.pdf)")
        st.markdown("- [Certificado de asistencia](https://www.fundae.es/DocumentosModelos/Certificado%20asistencia.pdf)")
        st.markdown("- [Declaración uso aula virtual 2024](https://www.fundae.es/DocumentosModelos/Declaracion%20aula%20virtual%202024.pdf)")
        st.markdown("- [Declaración uso aula virtual 2025](https://www.fundae.es/DocumentosModelos/Declaracion%20aula%20virtual%202025.pdf)")

    with tab_eval:
        st.markdown("#### 📊 Evaluación")
        st.markdown("- [Manual de ayuda evaluación de calidad](https://www.fundae.es/DocumentosModelos/Manual%20evaluacion%20calidad.pdf)")
        st.markdown("- [Instrucciones envío cuestionarios 2024](https://www.fundae.es/DocumentosModelos/Instrucciones%20cuestionarios%202024.pdf)")

    with tab_costes:
        st.markdown("#### 💰 Costes")
        st.markdown("- [B1. Resumen de costes](https://www.fundae.es/DocumentosModelos/B1%20Resumen%20costes.pdf)")
        st.markdown("- [Anexos de costes](https://www.fundae.es/DocumentosModelos/Anexos%20costes.pdf)")
        st.markdown("- [B2. Permisos individuales de formación](https://www.fundae.es/DocumentosModelos/B2%20Permisos%20individuales.pdf)")
        st.markdown("- [Guía de orientación de costes](https://www.fundae.es/DocumentosModelos/Guia%20costes.pdf)")

    with tab_pif:
        st.markdown("#### 🎯 Permiso Individual de Formación")
        st.markdown("- [Solicitud de PIF a la empresa](https://www.fundae.es/DocumentosModelos/Solicitud%20PIF.pdf)")


def calcular_estados_grupos(df_grupos):
    """Calcular estados de grupos basado en fechas cuando no existe la columna estado"""
    
    if df_grupos.empty:
        return {}
    
    estados = {'Futuros': 0, 'Activos': 0, 'Finalizados': 0, 'Sin fechas': 0}
    hoy = datetime.now().date()
    
    for _, grupo in df_grupos.iterrows():
        fecha_inicio = grupo.get('fecha_inicio')
        fecha_fin = grupo.get('fecha_fin_prevista') or grupo.get('fecha_fin')
        
        try:
            if not fecha_inicio:
                estados['Sin fechas'] += 1
                continue
                
            inicio = pd.to_datetime(fecha_inicio).date()
            
            if inicio > hoy:
                estados['Futuros'] += 1
            elif fecha_fin:
                fin = pd.to_datetime(fecha_fin).date()
                if fin >= hoy:
                    estados['Activos'] += 1
                else:
                    estados['Finalizados'] += 1
            else:
                estados['Activos'] += 1
                
        except Exception:
            estados['Sin fechas'] += 1
    
    return estados
