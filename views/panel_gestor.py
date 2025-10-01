import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from components.tailadmin_dashboard import TailAdminDashboard
from components.tailadmin_forms import TailAdminForms
from services.data_service import get_data_service
from services.grupos_service import get_grupos_service
from services.empresas_service import get_empresas_service
from services.participantes_service import get_participantes_service

def render(supabase, session_state):
    """Panel del Gestor - Versión simplificada en una página"""
    
    # Verificación de permisos
    if session_state.role not in ["admin", "gestor"]:
        st.error("🔒 Acceso restringido. Solo administradores y gestores.")
        return
    
    dashboard = TailAdminDashboard()
    forms = TailAdminForms()
    
    # === INICIALIZAR SERVICIOS ===
    try:
        data_service = get_data_service(supabase, session_state)
        grupos_service = get_grupos_service(supabase, session_state)
        empresas_service = get_empresas_service(supabase, session_state)
        participantes_service = get_participantes_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error al inicializar servicios: {e}")
        return
    
    # === CARGAR INFORMACIÓN DE EMPRESA ===
    empresa_info = cargar_info_empresa(supabase, session_state)
    
    if not empresa_info:
        st.error("❌ No se pudo cargar información de la empresa")
        return
    
    # === HEADER ===
    mostrar_header_gestor(empresa_info, session_state)
    
    # === VERIFICAR MÓDULO FORMACIÓN ===
    if not empresa_info.get('formacion_activo'):
        mostrar_sin_acceso_formacion(empresa_info)
        return
    
    # === CARGAR DATOS ===
    with st.spinner("Cargando datos..."):
        datos = cargar_datos_dashboard(
            data_service, grupos_service, empresas_service,
            participantes_service, session_state
        )
    
    if not datos:
        st.warning("⚠️ No hay datos disponibles")
        return
    
    # === MÉTRICAS PRINCIPALES ===
    mostrar_metricas_principales(datos, dashboard)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # === GRÁFICOS PRINCIPALES ===
    col1, col2 = st.columns(2)
    
    with col1:
        mostrar_estado_grupos(datos['grupos'], dashboard)
        st.markdown("<br>", unsafe_allow_html=True)
        mostrar_top_acciones_formativas(datos['grupos'])
    
    with col2:
        mostrar_evolucion_participantes(datos['participantes'])
        st.markdown("<br>", unsafe_allow_html=True)
        mostrar_distribucion_modalidades(datos['grupos'])
    
    # === ALERTAS Y TAREAS PENDIENTES ===
    st.markdown("<br>", unsafe_allow_html=True)
    mostrar_alertas_gestor(datos, empresa_info, dashboard)
    
    # === ACTIVIDAD RECIENTE ===
    st.markdown("<br>", unsafe_allow_html=True)
    mostrar_actividad_reciente(datos, dashboard)
    
    # === FOOTER ===
    mostrar_footer_gestor(empresa_info)


# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def cargar_info_empresa(supabase, session_state):
    """Carga información de empresa y módulos activos"""
    
    try:
        empresa_id = session_state.user.get('empresa_id')
        
        if not empresa_id:
            return None
        
        empresa_res = supabase.table("empresas").select(
            "id, nombre, formacion_activo, formacion_inicio, formacion_fin, "
            "iso_activo, rgpd_activo, docu_avanzada_activo"
        ).eq("id", empresa_id).single().execute()
        
        if not empresa_res.data:
            return None
        
        empresa = empresa_res.data
        
        # Verificar vigencia de formación
        hoy = datetime.now().date()
        
        if empresa.get('formacion_activo'):
            if empresa.get('formacion_inicio'):
                try:
                    fecha_inicio = pd.to_datetime(empresa['formacion_inicio']).date()
                    if fecha_inicio > hoy:
                        empresa['formacion_activo'] = False
                except:
                    pass
            
            if empresa.get('formacion_fin'):
                try:
                    fecha_fin = pd.to_datetime(empresa['formacion_fin']).date()
                    if fecha_fin < hoy:
                        empresa['formacion_activo'] = False
                except:
                    pass
        
        return empresa
        
    except Exception as e:
        st.error(f"Error cargando empresa: {e}")
        return None


def cargar_datos_dashboard(data_service, grupos_service, empresas_service,
                           participantes_service, session_state):
    """Carga todos los datos necesarios"""
    
    try:
        datos = {
            'grupos': grupos_service.get_grupos_completos(),
            'participantes': participantes_service.get_participantes_completos(),
            'tutores': data_service.get_tutores_completos(),
            'acciones': data_service.get_acciones_formativas()
        }
        
        # Aulas (si existen)
        try:
            empresa_id = session_state.user.get('empresa_id')
            aulas_res = supabase.table("aulas").select("*").eq("empresa_id", empresa_id).execute()
            datos['aulas'] = pd.DataFrame(aulas_res.data or [])
        except:
            datos['aulas'] = pd.DataFrame()
        
        return datos
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return None


def mostrar_header_gestor(empresa_info, session_state):
    """Header personalizado para gestor"""
    
    empresa_nombre = empresa_info.get('nombre', 'Tu Empresa')
    usuario_nombre = session_state.user.get('nombre', 'Gestor')
    
    # Contar módulos activos
    modulos_activos = sum([
        empresa_info.get('formacion_activo', False),
        empresa_info.get('iso_activo', False),
        empresa_info.get('rgpd_activo', False),
        empresa_info.get('docu_avanzada_activo', False)
    ])
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #10B981 0%, #34D399 100%);
        color: white;
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    ">
        <h1 style="margin: 0; font-size: 1.75rem; font-weight: 700; color: white;">
            📊 Panel de Gestión
        </h1>
        <p style="margin: 0.5rem 0 0; opacity: 0.95; font-size: 1.1rem; color: white;">
            <strong>{empresa_nombre}</strong> · {usuario_nombre}
        </p>
        <p style="margin: 0.5rem 0 0; opacity: 0.9; font-size: 0.875rem; color: white;">
            {modulos_activos} módulos activos · {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </p>
    </div>
    """, unsafe_allow_html=True)


def mostrar_sin_acceso_formacion(empresa_info):
    """Pantalla cuando no hay módulo de formación"""
    
    st.warning("⚠️ El módulo de Formación no está activo")
    
    # Fechas de vigencia
    if empresa_info.get('formacion_inicio'):
        try:
            fecha_inicio = pd.to_datetime(empresa_info['formacion_inicio']).strftime('%d/%m/%Y')
            st.info(f"📅 Fecha de activación prevista: {fecha_inicio}")
        except:
            pass
    
    # Otros módulos disponibles
    modulos_disponibles = []
    if empresa_info.get('iso_activo'):
        modulos_disponibles.append("🏅 ISO 9001")
    if empresa_info.get('rgpd_activo'):
        modulos_disponibles.append("🔒 RGPD")
    if empresa_info.get('docu_avanzada_activo'):
        modulos_disponibles.append("📚 Documentación Avanzada")
    
    if modulos_disponibles:
        st.success(f"Módulos disponibles: {', '.join(modulos_disponibles)}")
    else:
        st.info("📞 Contacta con el administrador para activar módulos")


def mostrar_metricas_principales(datos, dashboard):
    """Métricas principales del dashboard"""
    
    df_grupos = datos.get('grupos', pd.DataFrame())
    df_participantes = datos.get('participantes', pd.DataFrame())
    df_tutores = datos.get('tutores', pd.DataFrame())
    df_aulas = datos.get('aulas', pd.DataFrame())
    
    # Cálculos
    total_grupos = len(df_grupos) if not df_grupos.empty else 0
    grupos_activos = 0
    
    if not df_grupos.empty and 'estado' in df_grupos.columns:
        grupos_activos = len(df_grupos[df_grupos['estado'].isin(['abierto', 'finalizar'])])
    
    total_participantes = len(df_participantes) if not df_participantes.empty else 0
    participantes_nuevos_mes = 0
    
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
    
    total_tutores = len(df_tutores) if not df_tutores.empty else 0
    total_aulas = len(df_aulas) if not df_aulas.empty else 0
    
    # Mostrar métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        dashboard.metric_card_primary(
            "Grupos Totales",
            str(total_grupos),
            "📚",
            cambio=f"{grupos_activos} activos" if grupos_activos > 0 else None
        )
    
    with col2:
        dashboard.metric_card_primary(
            "Participantes",
            str(total_participantes),
            "🎓",
            cambio=f"+{participantes_nuevos_mes} este mes" if participantes_nuevos_mes > 0 else None
        )
    
    with col3:
        dashboard.metric_card_primary(
            "Tutores",
            str(total_tutores),
            "👨‍🏫"
        )
    
    with col4:
        dashboard.metric_card_primary(
            "Aulas",
            str(total_aulas),
            "🏫"
        )


def mostrar_estado_grupos(df_grupos, dashboard):
    """Estado actual de grupos"""
    
    dashboard.section_header("Estado de Grupos", icono="📊")
    
    if df_grupos.empty:
        st.info("No hay grupos registrados")
        return
    
    # Calcular estados
    hoy = datetime.now().date()
    estados = {
        'Activos': 0,
        'Próximos': 0,
        'Finalizados': 0,
        'Cancelados': 0
    }
    
    for _, grupo in df_grupos.iterrows():
        estado = grupo.get('estado', '').lower()
        
        if estado == 'cancelado':
            estados['Cancelados'] += 1
        elif estado == 'finalizado':
            estados['Finalizados'] += 1
        else:
            try:
                fecha_inicio = grupo.get('fecha_inicio')
                if fecha_inicio:
                    inicio = pd.to_datetime(fecha_inicio).date()
                    if inicio > hoy:
                        estados['Próximos'] += 1
                    else:
                        estados['Activos'] += 1
                else:
                    estados['Activos'] += 1
            except:
                estados['Activos'] += 1
    
    # Gráfico de dona
    colores = {
        'Activos': '#10B981',
        'Próximos': '#F59E0B',
        'Finalizados': '#3B82F6',
        'Cancelados': '#EF4444'
    }
    
    fig = px.pie(
        values=list(estados.values()),
        names=list(estados.keys()),
        hole=0.4,
        color_discrete_map=colores
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=300, showlegend=True)
    
    st.plotly_chart(fig, use_container_width=True)


def mostrar_evolucion_participantes(df_participantes):
    """Evolución temporal de participantes"""
    
    st.markdown("#### 👥 Evolución de Participantes")
    
    if df_participantes.empty or 'created_at' not in df_participantes.columns:
        st.info("Sin datos de fechas")
        return
    
    try:
        df_temp = df_participantes.copy()
        df_temp['fecha'] = pd.to_datetime(df_temp['created_at'], errors='coerce')
        df_temp = df_temp.dropna(subset=['fecha'])
        
        if df_temp.empty:
            st.info("Sin fechas válidas")
            return
        
        # Agrupar por mes
        df_temp['mes'] = df_temp['fecha'].dt.to_period('M')
        evolucion = df_temp.groupby('mes').size().reset_index(name='nuevos')
        evolucion['mes_str'] = evolucion['mes'].astype(str)
        evolucion['acumulado'] = evolucion['nuevos'].cumsum()
        
        # Gráfico de área
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=evolucion['mes_str'],
            y=evolucion['acumulado'],
            fill='tozeroy',
            mode='lines+markers',
            line=dict(color='#3B82F6', width=2),
            fillcolor='rgba(59, 130, 246, 0.2)'
        ))
        
        fig.update_layout(
            height=300,
            showlegend=False,
            xaxis_title="Mes",
            yaxis_title="Total Acumulado",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error: {e}")


def mostrar_distribucion_modalidades(df_grupos):
    """Distribución por modalidades"""
    
    st.markdown("#### 📚 Modalidades de Formación")
    
    if df_grupos.empty:
        st.info("Sin datos")
        return
    
    try:
        modalidad_col = 'accion_modalidad' if 'accion_modalidad' in df_grupos.columns else 'modalidad'
        
        if modalidad_col not in df_grupos.columns:
            st.info("Sin información de modalidad")
            return
        
        modalidades = df_grupos[modalidad_col].value_counts()
        
        if modalidades.empty:
            st.info("Sin modalidades")
            return
        
        colores = {
            'PRESENCIAL': '#10B981',
            'TELEFORMACION': '#3B82F6',
            'MIXTA': '#F59E0B'
        }
        
        colors = [colores.get(m, '#6B7280') for m in modalidades.index]
        
        fig = px.bar(
            x=modalidades.index,
            y=modalidades.values,
            color=modalidades.index,
            color_discrete_map=colores
        )
        
        fig.update_layout(
            height=300,
            showlegend=False,
            xaxis_title="Modalidad",
            yaxis_title="Cantidad"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error: {e}")


def mostrar_top_acciones_formativas(df_grupos):
    """Top 5 acciones formativas más utilizadas"""
    
    st.markdown("#### 🏆 Top Acciones Formativas")
    
    if df_grupos.empty or 'accion_nombre' not in df_grupos.columns:
        st.info("Sin datos")
        return
    
    try:
        top_acciones = df_grupos['accion_nombre'].value_counts().head(5)
        
        if top_acciones.empty:
            st.info("Sin acciones registradas")
            return
        
        fig = px.bar(
            x=top_acciones.values,
            y=top_acciones.index,
            orientation='h',
            color=top_acciones.values,
            color_continuous_scale='Greens'
        )
        
        fig.update_layout(
            height=250,
            showlegend=False,
            xaxis_title="Grupos",
            yaxis_title=""
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error: {e}")


def mostrar_alertas_gestor(datos, empresa_info, dashboard):
    """Alertas importantes para el gestor"""
    
    dashboard.section_header("Alertas y Tareas Pendientes", icono="⚠️")
    
    df_grupos = datos.get('grupos', pd.DataFrame())
    df_participantes = datos.get('participantes', pd.DataFrame())
    
    alertas = []
    
    # Grupos sin participantes
    if not df_grupos.empty and not df_participantes.empty and 'grupo_id' in df_participantes.columns:
        grupos_con_part = df_participantes['grupo_id'].dropna().unique()
        grupos_sin_part = df_grupos[~df_grupos['id'].isin(grupos_con_part)]
        
        if not grupos_sin_part.empty:
            alertas.append({
                'tipo': 'warning',
                'titulo': 'Grupos sin participantes',
                'mensaje': f'{len(grupos_sin_part)} grupos no tienen participantes asignados',
                'count': len(grupos_sin_part)
            })
    
    # Participantes sin grupo
    if not df_participantes.empty and 'grupo_id' in df_participantes.columns:
        part_sin_grupo = df_participantes[df_participantes['grupo_id'].isna()]
        
        if not part_sin_grupo.empty:
            alertas.append({
                'tipo': 'info',
                'titulo': 'Participantes sin grupo',
                'mensaje': f'{len(part_sin_grupo)} participantes pendientes de asignar',
                'count': len(part_sin_grupo)
            })
    
    # Grupos próximos a finalizar
    if not df_grupos.empty and 'fecha_fin_prevista' in df_grupos.columns:
        try:
            hoy = datetime.now().date()
            fecha_limite = hoy + timedelta(days=15)
            
            df_temp = df_grupos.copy()
            df_temp['fecha_fin_prevista'] = pd.to_datetime(df_temp['fecha_fin_prevista'], errors='coerce')
            
            grupos_proximos = df_temp[
                (df_temp['fecha_fin_prevista'].dt.date >= hoy) &
                (df_temp['fecha_fin_prevista'].dt.date <= fecha_limite) &
                (df_temp['estado'] == 'abierto')
            ]
            
            if not grupos_proximos.empty:
                alertas.append({
                    'tipo': 'warning',
                    'titulo': 'Grupos próximos a finalizar',
                    'mensaje': f'{len(grupos_proximos)} grupos finalizan en los próximos 15 días',
                    'count': len(grupos_proximos)
                })
        except:
            pass
    
    # Mostrar alertas
    if alertas:
        col1, col2 = st.columns(2)
        
        for i, alerta in enumerate(alertas):
            with col1 if i % 2 == 0 else col2:
                dashboard.alert_card(
                    alerta['tipo'],
                    alerta['titulo'],
                    alerta['mensaje'],
                    count=alerta.get('count')
                )
    else:
        st.success("✅ No hay alertas pendientes")


def mostrar_actividad_reciente(datos, dashboard):
    """Actividad reciente en el sistema"""
    
    dashboard.section_header("Actividad Reciente", "Últimos 7 días", icono="📅")
    
    df_participantes = datos.get('participantes', pd.DataFrame())
    df_grupos = datos.get('grupos', pd.DataFrame())
    
    if df_participantes.empty and df_grupos.empty:
        st.info("Sin actividad reciente")
        return
    
    fecha_limite = datetime.now() - timedelta(days=7)
    actividad = []
    
    # Participantes nuevos
    if not df_participantes.empty and 'created_at' in df_participantes.columns:
        try:
            df_temp = df_participantes.copy()
            df_temp['created_at'] = pd.to_datetime(df_temp['created_at'], errors='coerce')
            recientes = df_temp[df_temp['created_at'] > pd.Timestamp(fecha_limite, tz='UTC')]
            
            for _, p in recientes.iterrows():
                actividad.append({
                    'Fecha': p['created_at'].strftime('%d/%m/%Y'),
                    'Tipo': '🎓 Participante',
                    'Descripción': p.get('nombre', 'Sin nombre')
                })
        except:
            pass
    
    # Grupos nuevos
    if not df_grupos.empty and 'created_at' in df_grupos.columns:
        try:
            df_temp = df_grupos.copy()
            df_temp['created_at'] = pd.to_datetime(df_temp['created_at'], errors='coerce')
            recientes = df_temp[df_temp['created_at'] > pd.Timestamp(fecha_limite, tz='UTC')]
            
            for _, g in recientes.iterrows():
                actividad.append({
                    'Fecha': g['created_at'].strftime('%d/%m/%Y'),
                    'Tipo': '📚 Grupo',
                    'Descripción': g.get('codigo_grupo', 'Sin código')
                })
        except:
            pass
    
    if actividad:
        df_actividad = pd.DataFrame(actividad).sort_values('Fecha', ascending=False)
        st.dataframe(df_actividad, use_container_width=True, hide_index=True)
    else:
        st.info("Sin actividad en los últimos 7 días")


def mostrar_footer_gestor(empresa_info):
    """Footer informativo"""
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption(f"🔄 Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    with col2:
        empresa_nombre = empresa_info.get('nombre', 'Tu empresa')
        st.caption(f"🏢 Empresa: {empresa_nombre}")
    
    with col3:
        st.caption("📊 Panel FUNDAE v2.0")
