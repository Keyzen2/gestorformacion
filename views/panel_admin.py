import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from components.tailadmin_dashboard import TailAdminDashboard
from components.tailadmin_forms import TailAdminForms

def render(supabase, session_state):
    """Panel de Administración rediseñado con TailAdmin"""
    
    # Verificar permisos
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return
    
    dashboard = TailAdminDashboard()
    forms = TailAdminForms()
    
    # === HEADER PRINCIPAL ===
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    ">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700;">🛡️ Panel de Administración</h1>
        <p style="margin: 0.5rem 0 0; opacity: 0.9; font-size: 1rem;">
            Supervisión integral del sistema - {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # === CARGAR DATOS GLOBALES ===
    try:
        datos_globales = cargar_datos_sistema(supabase)
    except Exception as e:
        st.error(f"❌ Error al cargar datos del sistema: {e}")
        return
    
    # === MÉTRICAS PRINCIPALES (4 tarjetas destacadas) ===
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        cambio_empresas = calcular_cambio_mensual(
            datos_globales['empresas'], 
            'created_at'
        )
        dashboard.metric_card_primary(
            "Empresas Totales",
            str(datos_globales['total_empresas']),
            "🏢",
            cambio=f"+{cambio_empresas} este mes" if cambio_empresas > 0 else None,
            cambio_positivo=True
        )
    
    with col2:
        cambio_usuarios = calcular_cambio_mensual(
            datos_globales['usuarios'],
            'created_at'
        )
        dashboard.metric_card_primary(
            "Usuarios Activos",
            str(datos_globales['total_usuarios']),
            "👥",
            cambio=f"+{cambio_usuarios} este mes" if cambio_usuarios > 0 else None,
            cambio_positivo=True
        )
    
    with col3:
        dashboard.metric_card_primary(
            "Grupos Activos",
            str(datos_globales['grupos_activos']),
            "📚",
            cambio=f"{datos_globales['total_grupos']} totales"
        )
    
    with col4:
        dashboard.metric_card_primary(
            "Aulas Disponibles",
            str(datos_globales['aulas_activas']),
            "🏫",
            cambio=f"{datos_globales['total_aulas']} totales"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # === MÉTRICAS SECUNDARIAS (Grid 3x2) ===
    col1, col2, col3 = st.columns(3)
    
    with col1:
        dashboard.metric_card_secondary(
            "Participantes",
            str(datos_globales['total_participantes']),
            "🎓",
            "#10B981"
        )
    
    with col2:
        dashboard.metric_card_secondary(
            "Tutores",
            str(datos_globales['total_tutores']),
            "👨‍🏫",
            "#F59E0B"
        )
    
    with col3:
        dashboard.metric_card_secondary(
            "Acciones Formativas",
            str(datos_globales['total_acciones']),
            "📖",
            "#8B5CF6"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        dashboard.metric_card_secondary(
            "Proyectos Activos",
            str(datos_globales['proyectos_activos']),
            "📊",
            "#06B6D4"
        )
    
    with col2:
        dashboard.metric_card_secondary(
            "Clases Programadas",
            str(datos_globales['total_clases']),
            "📅",
            "#EC4899"
        )
    
    with col3:
        dashboard.metric_card_secondary(
            "Reservas Hoy",
            str(datos_globales['reservas_hoy']),
            "🗓️",
            "#F97316"
        )
    
    # === SISTEMA DE ALERTAS INTELIGENTE ===
    dashboard.section_header(
        "Sistema de Alertas",
        "Notificaciones críticas que requieren atención inmediata",
        "🚨"
    )
    
    alertas = generar_alertas_sistema(supabase, datos_globales)
    
    if not alertas:
        st.success("✅ ¡Excelente! No hay alertas críticas en el sistema.")
    else:
        col1, col2 = st.columns(2)
        
        alertas_criticas = [a for a in alertas if a['nivel'] == 'error']
        alertas_advertencia = [a for a in alertas if a['nivel'] == 'warning']
        
        with col1:
            for alerta in alertas_criticas:
                dashboard.alert_card(
                    "error",
                    alerta['titulo'],
                    alerta['mensaje'],
                    count=alerta.get('count')
                )
        
        with col2:
            for alerta in alertas_advertencia:
                dashboard.alert_card(
                    "warning",
                    alerta['titulo'],
                    alerta['mensaje'],
                    count=alerta.get('count')
                )
    
    # === TABS PRINCIPALES ===
    tabs = st.tabs([
        "📊 Estadísticas Globales",
        "📈 Análisis de Tendencias",
        "🏢 Gestión de Empresas",
        "👥 Gestión de Usuarios",
        "🎓 Módulo Formación",
        "🏫 Gestión de Aulas",
        "📅 Gestión de Clases",
        "📊 Proyectos FUNDAE",
        "💼 Módulo CRM"
    ])
    
    # === TAB 1: ESTADÍSTICAS GLOBALES ===
    with tabs[0]:
        mostrar_estadisticas_globales(supabase, datos_globales, dashboard)
    
    # === TAB 2: ANÁLISIS DE TENDENCIAS ===
    with tabs[1]:
        mostrar_analisis_tendencias(supabase, datos_globales, dashboard)
    
    # === TAB 3: GESTIÓN DE EMPRESAS ===
    with tabs[2]:
        mostrar_gestion_empresas(supabase, datos_globales, dashboard)
    
    # === TAB 4: GESTIÓN DE USUARIOS ===
    with tabs[3]:
        mostrar_gestion_usuarios(supabase, datos_globales, dashboard)
    
    # === TAB 5: MÓDULO FORMACIÓN ===
    with tabs[4]:
        mostrar_modulo_formacion(supabase, datos_globales, dashboard)
    
    # === TAB 6: GESTIÓN DE AULAS ===
    with tabs[5]:
        mostrar_gestion_aulas(supabase, datos_globales, dashboard)
    
    # === TAB 7: GESTIÓN DE CLASES ===
    with tabs[6]:
        mostrar_gestion_clases(supabase, datos_globales, dashboard)
    
    # === TAB 8: PROYECTOS FUNDAE ===
    with tabs[7]:
        mostrar_proyectos_fundae(supabase, datos_globales, dashboard)
    
    # === TAB 9: MÓDULO CRM ===
    with tabs[8]:
        mostrar_modulo_crm(supabase, datos_globales, dashboard)


# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def cargar_datos_sistema(supabase):
    """Carga todos los datos necesarios del sistema de forma optimizada"""
    
    datos = {}
    
    try:
        # Empresas
        empresas_res = supabase.table("empresas").select("*").execute()
        datos['empresas'] = empresas_res.data or []
        datos['total_empresas'] = len(datos['empresas'])
        
        # Usuarios
        usuarios_res = supabase.table("usuarios").select("*").execute()
        datos['usuarios'] = usuarios_res.data or []
        datos['total_usuarios'] = len(datos['usuarios'])
        
        # Grupos
        grupos_res = supabase.table("grupos").select("*").execute()
        datos['grupos'] = grupos_res.data or []
        datos['total_grupos'] = len(datos['grupos'])
        
        # Grupos activos (fecha_inicio <= hoy <= fecha_fin_prevista)
        hoy = datetime.now().date()
        datos['grupos_activos'] = len([
            g for g in datos['grupos']
            if g.get('fecha_inicio') and pd.to_datetime(g['fecha_inicio']).date() <= hoy
            and (not g.get('fecha_fin_prevista') or pd.to_datetime(g['fecha_fin_prevista']).date() >= hoy)
        ])
        
        # Aulas
        aulas_res = supabase.table("aulas").select("*").execute()
        datos['aulas'] = aulas_res.data or []
        datos['total_aulas'] = len(datos['aulas'])
        datos['aulas_activas'] = len([a for a in datos['aulas'] if a.get('activa')])
        
        # Participantes
        participantes_res = supabase.table("participantes").select("*").execute()
        datos['participantes'] = participantes_res.data or []
        datos['total_participantes'] = len(datos['participantes'])
        
        # Tutores
        tutores_res = supabase.table("tutores").select("*").execute()
        datos['tutores'] = tutores_res.data or []
        datos['total_tutores'] = len(datos['tutores'])
        
        # Acciones formativas
        acciones_res = supabase.table("acciones_formativas").select("*").execute()
        datos['acciones_formativas'] = acciones_res.data or []
        datos['total_acciones'] = len(datos['acciones_formativas'])
        
        # Proyectos
        proyectos_res = supabase.table("proyectos").select("*").execute()
        datos['proyectos'] = proyectos_res.data or []
        datos['proyectos_activos'] = len([
            p for p in datos['proyectos']
            if p.get('estado_proyecto') in ['CONVOCADO', 'EN_EJECUCION']
        ])
        
        # Clases
        clases_res = supabase.table("clases").select("*").execute()
        datos['clases'] = clases_res.data or []
        datos['total_clases'] = len([c for c in datos['clases'] if c.get('activa')])
        
        # Reservas de aulas hoy
        reservas_res = supabase.table("aula_reservas")\
            .select("*")\
            .gte("fecha_inicio", datetime.now().date().isoformat())\
            .lt("fecha_inicio", (datetime.now().date() + timedelta(days=1)).isoformat())\
            .execute()
        datos['reservas_hoy'] = len(reservas_res.data or [])
        
        return datos
        
    except Exception as e:
        st.error(f"Error en cargar_datos_sistema: {e}")
        return {}


def calcular_cambio_mensual(datos, campo_fecha):
    """Calcula cuántos registros se crearon este mes"""
    if not datos:
        return 0
    
    inicio_mes = datetime.now().replace(day=1).date()
    
    count = 0
    for registro in datos:
        if registro.get(campo_fecha):
            try:
                fecha = pd.to_datetime(registro[campo_fecha]).date()
                if fecha >= inicio_mes:
                    count += 1
            except:
                continue
    
    return count


def generar_alertas_sistema(supabase, datos_globales):
    """Genera alertas inteligentes basadas en el estado del sistema"""
    
    alertas = []
    hoy = datetime.now().date()
    
    # 1. Grupos finalizados sin diplomas
    try:
        diplomas_res = supabase.table("diplomas").select("grupo_id").execute()
        grupos_con_diplomas = set([d['grupo_id'] for d in (diplomas_res.data or []) if d.get('grupo_id')])
        
        grupos_finalizados_sin_diplomas = [
            g for g in datos_globales['grupos']
            if g.get('fecha_fin_prevista')
            and pd.to_datetime(g['fecha_fin_prevista']).date() < hoy
            and g['id'] not in grupos_con_diplomas
        ]
        
        if grupos_finalizados_sin_diplomas:
            alertas.append({
                'nivel': 'error',
                'titulo': 'Grupos sin diplomas',
                'mensaje': 'Grupos finalizados pendientes de generar diplomas',
                'count': len(grupos_finalizados_sin_diplomas)
            })
    except Exception as e:
        pass
    
    # 2. Participantes sin grupo asignado
    participantes_sin_grupo = [p for p in datos_globales['participantes'] if not p.get('grupo_id')]
    if len(participantes_sin_grupo) > 10:
        alertas.append({
            'nivel': 'warning',
            'titulo': 'Participantes sin grupo',
            'mensaje': 'Muchos participantes sin asignar a ningún grupo',
            'count': len(participantes_sin_grupo)
        })
    
    # 3. Grupos sin tutores
    try:
        tutores_grupos_res = supabase.table("tutores_grupos").select("grupo_id").execute()
        grupos_con_tutores = set([tg['grupo_id'] for tg in (tutores_grupos_res.data or []) if tg.get('grupo_id')])
        
        grupos_sin_tutores = [g for g in datos_globales['grupos'] if g['id'] not in grupos_con_tutores]
        
        if grupos_sin_tutores:
            alertas.append({
                'nivel': 'error',
                'titulo': 'Grupos sin tutores',
                'mensaje': 'Grupos activos que no tienen tutores asignados',
                'count': len(grupos_sin_tutores)
            })
    except Exception as e:
        pass
    
    # 4. Módulos próximos a vencer (30 días)
    try:
        fecha_limite = hoy + timedelta(days=30)
        empresas_vencimiento = []
        
        for empresa in datos_globales['empresas']:
            for modulo, campo in [('Formación', 'formacion_fin'), ('ISO', 'iso_fin'), ('RGPD', 'rgpd_fin')]:
                if empresa.get(campo):
                    try:
                        fecha_fin = pd.to_datetime(empresa[campo]).date()
                        if hoy <= fecha_fin <= fecha_limite:
                            empresas_vencimiento.append(empresa['nombre'])
                            break
                    except:
                        pass
        
        if empresas_vencimiento:
            alertas.append({
                'nivel': 'warning',
                'titulo': 'Módulos próximos a vencer',
                'mensaje': f'Empresas con módulos que vencen en 30 días',
                'count': len(empresas_vencimiento)
            })
    except Exception as e:
        pass
    
    # 5. Aulas sin reservas este mes
    try:
        inicio_mes = datetime.now().replace(day=1)
        reservas_mes_res = supabase.table("aula_reservas")\
            .select("aula_id")\
            .gte("fecha_inicio", inicio_mes.isoformat())\
            .execute()
        
        aulas_con_reservas = set([r['aula_id'] for r in (reservas_mes_res.data or []) if r.get('aula_id')])
        aulas_sin_uso = [a for a in datos_globales['aulas'] if a.get('activa') and a['id'] not in aulas_con_reservas]
        
        if len(aulas_sin_uso) > 3:
            alertas.append({
                'nivel': 'warning',
                'titulo': 'Aulas infrautilizadas',
                'mensaje': 'Aulas activas sin reservas este mes',
                'count': len(aulas_sin_uso)
            })
    except Exception as e:
        pass
    
    return alertas

# =====================================================
# TAB 1: ESTADÍSTICAS GLOBALES
# =====================================================

def mostrar_estadisticas_globales(supabase, datos_globales, dashboard):
    """Estadísticas completas del sistema con gráficos interactivos"""
    
    dashboard.section_header(
        "Resumen del Sistema",
        "Visión general de todos los módulos activos",
        "📊"
    )
    
    # === DISTRIBUCIÓN DE USUARIOS POR ROL ===
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 👥 Distribución de Usuarios por Rol")
        
        roles_count = {}
        for usuario in datos_globales['usuarios']:
            rol = usuario.get('rol', 'Sin rol')
            roles_count[rol] = roles_count.get(rol, 0) + 1
        
        if roles_count:
            df_roles = pd.DataFrame(list(roles_count.items()), columns=['Rol', 'Cantidad'])
            
            fig = px.pie(
                df_roles,
                values='Cantidad',
                names='Rol',
                color_discrete_sequence=['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
            )
            fig.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=40, b=20),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de usuarios")
    
    with col2:
        st.markdown("#### 🏢 Top 10 Empresas con Más Actividad")
        
        empresas_actividad = {}
        
        # Contar participantes por empresa
        for p in datos_globales['participantes']:
            if p.get('empresa_id'):
                empresa_id = p['empresa_id']
                empresas_actividad[empresa_id] = empresas_actividad.get(empresa_id, 0) + 1
        
        # Obtener nombres de empresas
        empresas_dict = {e['id']: e['nombre'] for e in datos_globales['empresas']}
        
        actividad_data = [
            {'Empresa': empresas_dict.get(emp_id, 'Desconocida'), 'Participantes': count}
            for emp_id, count in empresas_actividad.items()
        ]
        
        if actividad_data:
            df_actividad = pd.DataFrame(actividad_data).nlargest(10, 'Participantes')
            
            fig = px.bar(
                df_actividad,
                x='Participantes',
                y='Empresa',
                orientation='h',
                color='Participantes',
                color_continuous_scale='Blues'
            )
            fig.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=40, b=20),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de actividad")
    
    # === ESTADO DE GRUPOS ===
    st.markdown("<br>", unsafe_allow_html=True)
    dashboard.section_header("Estado de Grupos Formativos", icon="📚")
    
    col1, col2, col3 = st.columns(3)
    
    hoy = datetime.now().date()
    grupos_activos = 0
    grupos_finalizados = 0
    grupos_futuros = 0
    
    for grupo in datos_globales['grupos']:
        try:
            fecha_inicio = grupo.get('fecha_inicio')
            fecha_fin = grupo.get('fecha_fin_prevista')
            
            if fecha_inicio:
                inicio = pd.to_datetime(fecha_inicio).date()
                if inicio > hoy:
                    grupos_futuros += 1
                elif fecha_fin:
                    fin = pd.to_datetime(fecha_fin).date()
                    if fin >= hoy:
                        grupos_activos += 1
                    else:
                        grupos_finalizados += 1
                else:
                    grupos_activos += 1
        except:
            continue
    
    with col1:
        dashboard.metric_card_secondary("Activos Ahora", str(grupos_activos), "🟢", "#10B981")
    
    with col2:
        dashboard.metric_card_secondary("Finalizados", str(grupos_finalizados), "🔴", "#EF4444")
    
    with col3:
        dashboard.metric_card_secondary("Próximos", str(grupos_futuros), "🟡", "#F59E0B")
    
    # === MÓDULOS CONTRATADOS POR EMPRESA ===
    st.markdown("<br>", unsafe_allow_html=True)
    dashboard.section_header("Módulos Contratados", icon="📦")
    
    modulos_stats = {
        'Formación': len([e for e in datos_globales['empresas'] if e.get('formacion_activo')]),
        'ISO 9001': len([e for e in datos_globales['empresas'] if e.get('iso_activo')]),
        'RGPD': len([e for e in datos_globales['empresas'] if e.get('rgpd_activo')]),
        'Doc. Avanzada': len([e for e in datos_globales['empresas'] if e.get('docu_avanzada_activo')])
    }
    
    col1, col2, col3, col4 = st.columns(4)
    
    for i, (col, (modulo, count)) in enumerate(zip([col1, col2, col3, col4], modulos_stats.items())):
        with col:
            colores = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6']
            dashboard.metric_card_secondary(modulo, str(count), "✓", colores[i])


# =====================================================
# TAB 2: ANÁLISIS DE TENDENCIAS
# =====================================================

def mostrar_analisis_tendencias(supabase, datos_globales, dashboard):
    """Análisis temporal de crecimiento del sistema"""
    
    dashboard.section_header(
        "Tendencias Temporales",
        "Evolución del sistema en los últimos meses",
        "📈"
    )
    
    # === EVOLUCIÓN DE EMPRESAS ===
    st.markdown("#### 🏢 Crecimiento de Empresas")
    
    empresas_fechas = []
    for empresa in datos_globales['empresas']:
        fecha_creacion = empresa.get('created_at') or empresa.get('fecha_alta')
        if fecha_creacion:
            try:
                fecha = pd.to_datetime(fecha_creacion).date()
                empresas_fechas.append(fecha)
            except:
                continue
    
    if empresas_fechas:
        df_empresas = pd.DataFrame({'fecha': empresas_fechas})
        df_empresas = df_empresas.groupby('fecha').size().reset_index(name='nuevas')
        df_empresas['acumuladas'] = df_empresas['nuevas'].cumsum()
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_empresas['fecha'],
            y=df_empresas['acumuladas'],
            mode='lines+markers',
            name='Empresas Acumuladas',
            line=dict(color='#3B82F6', width=3),
            marker=dict(size=6)
        ))
        
        fig.update_layout(
            title="Evolución del Número de Empresas",
            xaxis_title="Fecha",
            yaxis_title="Empresas Totales",
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de fechas suficientes")
    
    # === ACTIVIDAD MENSUAL ===
    st.markdown("<br>", unsafe_allow_html=True)
    dashboard.section_header("Actividad Mensual", icon="📅")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 👥 Nuevos Usuarios por Mes")
        
        usuarios_por_mes = {}
        for usuario in datos_globales['usuarios']:
            if usuario.get('created_at'):
                try:
                    fecha = pd.to_datetime(usuario['created_at'])
                    mes_key = fecha.strftime('%Y-%m')
                    usuarios_por_mes[mes_key] = usuarios_por_mes.get(mes_key, 0) + 1
                except:
                    continue
        
        if usuarios_por_mes:
            df_usuarios_mes = pd.DataFrame(
                list(usuarios_por_mes.items()),
                columns=['Mes', 'Usuarios']
            ).sort_values('Mes')
            
            fig = px.bar(
                df_usuarios_mes,
                x='Mes',
                y='Usuarios',
                color='Usuarios',
                color_continuous_scale='Greens'
            )
            fig.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos mensuales")
    
    with col2:
        st.markdown("#### 📚 Grupos Creados por Mes")
        
        grupos_por_mes = {}
        for grupo in datos_globales['grupos']:
            if grupo.get('created_at'):
                try:
                    fecha = pd.to_datetime(grupo['created_at'])
                    mes_key = fecha.strftime('%Y-%m')
                    grupos_por_mes[mes_key] = grupos_por_mes.get(mes_key, 0) + 1
                except:
                    continue
        
        if grupos_por_mes:
            df_grupos_mes = pd.DataFrame(
                list(grupos_por_mes.items()),
                columns=['Mes', 'Grupos']
            ).sort_values('Mes')
            
            fig = px.bar(
                df_grupos_mes,
                x='Mes',
                y='Grupos',
                color='Grupos',
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos mensuales")


# =====================================================
# TAB 3: GESTIÓN DE EMPRESAS
# =====================================================

def mostrar_gestion_empresas(supabase, datos_globales, dashboard):
    """Vista detallada de empresas con análisis por ubicación y tipo"""
    
    dashboard.section_header(
        "Gestión de Empresas",
        "Análisis detallado de clientes y distribución",
        "🏢"
    )
    
    # === FILTROS ===
    col1, col2, col3 = st.columns(3)
    
    with col1:
        tipo_filtro = st.selectbox(
            "Tipo de Empresa",
            ["Todas", "CLIENTE_SAAS", "GESTORA", "CLIENTE_GESTOR"]
        )
    
    with col2:
        modulo_filtro = st.selectbox(
            "Módulo Activo",
            ["Todos", "Formación", "ISO", "RGPD", "Doc. Avanzada"]
        )
    
    with col3:
        provincia_filtro = st.selectbox(
            "Provincia",
            ["Todas"] + sorted(list(set([e.get('provincia', 'Sin provincia') for e in datos_globales['empresas'] if e.get('provincia')])))
        )
    
    # Aplicar filtros
    empresas_filtradas = datos_globales['empresas']
    
    if tipo_filtro != "Todas":
        empresas_filtradas = [e for e in empresas_filtradas if e.get('tipo_empresa') == tipo_filtro]
    
    if modulo_filtro != "Todos":
        campo_map = {
            'Formación': 'formacion_activo',
            'ISO': 'iso_activo',
            'RGPD': 'rgpd_activo',
            'Doc. Avanzada': 'docu_avanzada_activo'
        }
        campo = campo_map[modulo_filtro]
        empresas_filtradas = [e for e in empresas_filtradas if e.get(campo)]
    
    if provincia_filtro != "Todas":
        empresas_filtradas = [e for e in empresas_filtradas if e.get('provincia') == provincia_filtro]
    
    st.markdown(f"**Total empresas filtradas:** {len(empresas_filtradas)}")
    
    # === DISTRIBUCIÓN GEOGRÁFICA ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🗺️ Distribución Geográfica")
    
    provincias_count = {}
    for empresa in empresas_filtradas:
        provincia = empresa.get('provincia', 'Sin provincia')
        provincias_count[provincia] = provincias_count.get(provincia, 0) + 1
    
    if provincias_count:
        df_provincias = pd.DataFrame(
            list(provincias_count.items()),
            columns=['Provincia', 'Empresas']
        ).sort_values('Empresas', ascending=False).head(10)
        
        fig = px.bar(
            df_provincias,
            x='Empresas',
            y='Provincia',
            orientation='h',
            color='Empresas',
            color_continuous_scale='Viridis'
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    # === TABLA DE EMPRESAS ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📋 Listado de Empresas")
    
    if empresas_filtradas:
        df_display = pd.DataFrame([{
            'Nombre': e.get('nombre', ''),
            'CIF': e.get('cif', ''),
            'Provincia': e.get('provincia', 'N/A'),
            'Tipo': e.get('tipo_empresa', 'N/A'),
            'Formación': '✓' if e.get('formacion_activo') else '✗',
            'ISO': '✓' if e.get('iso_activo') else '✗',
            'RGPD': '✓' if e.get('rgpd_activo') else '✗'
        } for e in empresas_filtradas])
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("No hay empresas que coincidan con los filtros")


# =====================================================
# TAB 4: GESTIÓN DE USUARIOS
# =====================================================

def mostrar_gestion_usuarios(supabase, datos_globales, dashboard):
    """Análisis de usuarios del sistema"""
    
    dashboard.section_header(
        "Gestión de Usuarios",
        "Análisis de accesos y roles en el sistema",
        "👥"
    )
    
    # === MÉTRICAS POR ROL ===
    roles_count = {}
    for usuario in datos_globales['usuarios']:
        rol = usuario.get('rol', 'Sin rol')
        roles_count[rol] = roles_count.get(rol, 0) + 1
    
    cols = st.columns(len(roles_count) if roles_count else 1)
    colores = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
    
    for i, (col, (rol, count)) in enumerate(zip(cols, roles_count.items())):
        with col:
            dashboard.metric_card_secondary(
                rol.title(),
                str(count),
                "👤",
                colores[i % len(colores)]
            )
    
    # === USUARIOS POR EMPRESA ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🏢 Usuarios por Empresa")
    
    empresas_usuarios = {}
    empresas_dict = {e['id']: e['nombre'] for e in datos_globales['empresas']}
    
    for usuario in datos_globales['usuarios']:
        if usuario.get('empresa_id'):
            empresa_nombre = empresas_dict.get(usuario['empresa_id'], 'Desconocida')
            empresas_usuarios[empresa_nombre] = empresas_usuarios.get(empresa_nombre, 0) + 1
    
    if empresas_usuarios:
        df_empresas_usuarios = pd.DataFrame(
            list(empresas_usuarios.items()),
            columns=['Empresa', 'Usuarios']
        ).sort_values('Usuarios', ascending=False).head(15)
        
        fig = px.treemap(
            df_empresas_usuarios,
            path=['Empresa'],
            values='Usuarios',
            color='Usuarios',
            color_continuous_scale='RdYlGn'
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    
    # === ACTIVIDAD RECIENTE ===
    st.markdown("<br>", unsafe_allow_html=True)
    dashboard.section_header("Actividad Reciente", "Últimos 30 días", "📅")
    
    fecha_limite = datetime.now().date() - timedelta(days=30)
    
    usuarios_recientes = []
    for usuario in datos_globales['usuarios']:
        if usuario.get('created_at'):
            try:
                fecha = pd.to_datetime(usuario['created_at']).date()
                if fecha >= fecha_limite:
                    empresa_nombre = empresas_dict.get(usuario.get('empresa_id'), 'Sin empresa')
                    usuarios_recientes.append({
                        'Fecha': fecha,
                        'Email': usuario.get('email', 'N/A'),
                        'Rol': usuario.get('rol', 'N/A'),
                        'Empresa': empresa_nombre
                    })
            except:
                continue
    
    if usuarios_recientes:
        df_recientes = pd.DataFrame(usuarios_recientes).sort_values('Fecha', ascending=False)
        st.dataframe(df_recientes, use_container_width=True, hide_index=True)
    else:
        st.info("No hay usuarios creados en los últimos 30 días")


# =====================================================
# TAB 5: MÓDULO FORMACIÓN
# =====================================================

def mostrar_modulo_formacion(supabase, datos_globales, dashboard):
    """Análisis completo del módulo de formación"""
    
    dashboard.section_header(
        "Módulo de Formación FUNDAE",
        "Estadísticas de grupos, participantes y acciones formativas",
        "🎓"
    )
    
    # === MÉTRICAS PRINCIPALES ===
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        dashboard.metric_card_secondary(
            "Acciones Formativas",
            str(datos_globales['total_acciones']),
            "📚",
            "#3B82F6"
        )
    
    with col2:
        dashboard.metric_card_secondary(
            "Grupos Totales",
            str(datos_globales['total_grupos']),
            "👥",
            "#10B981"
        )
    
    with col3:
        dashboard.metric_card_secondary(
            "Participantes",
            str(datos_globales['total_participantes']),
            "🎓",
            "#F59E0B"
        )
    
    with col4:
        dashboard.metric_card_secondary(
            "Tutores",
            str(datos_globales['total_tutores']),
            "👨‍🏫",
            "#8B5CF6"
        )
    
    # === ACCIONES FORMATIVAS POR MODALIDAD ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📊 Acciones Formativas por Modalidad")
    
    modalidades_count = {}
    for accion in datos_globales['acciones_formativas']:
        modalidad = accion.get('modalidad', 'Sin especificar')
        modalidades_count[modalidad] = modalidades_count.get(modalidad, 0) + 1
    
    if modalidades_count:
        col1, col2 = st.columns(2)
        
        with col1:
            df_modalidades = pd.DataFrame(
                list(modalidades_count.items()),
                columns=['Modalidad', 'Cantidad']
            )
            
            fig = px.pie(
                df_modalidades,
                values='Cantidad',
                names='Modalidad',
                color_discrete_sequence=['#3B82F6', '#10B981', '#F59E0B']
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Horas totales por modalidad
            horas_por_modalidad = {}
            for accion in datos_globales['acciones_formativas']:
                modalidad = accion.get('modalidad', 'Sin especificar')
                horas = accion.get('horas', 0) or accion.get('num_horas', 0) or 0
                horas_por_modalidad[modalidad] = horas_por_modalidad.get(modalidad, 0) + horas
            
            if horas_por_modalidad:
                df_horas = pd.DataFrame(
                    list(horas_por_modalidad.items()),
                    columns=['Modalidad', 'Horas Totales']
                )
                
                fig = px.bar(
                    df_horas,
                    x='Modalidad',
                    y='Horas Totales',
                    color='Horas Totales',
                    color_continuous_scale='Purples'
                )
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
    
    # === PARTICIPANTES POR GRUPO ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 👥 Top 10 Grupos con Más Participantes")
    
    participantes_por_grupo = {}
    for participante in datos_globales['participantes']:
        if participante.get('grupo_id'):
            grupo_id = participante['grupo_id']
            participantes_por_grupo[grupo_id] = participantes_por_grupo.get(grupo_id, 0) + 1
    
    if participantes_por_grupo:
        grupos_dict = {g['id']: g.get('codigo_grupo', 'Sin código') for g in datos_globales['grupos']}
        
        top_grupos = sorted(participantes_por_grupo.items(), key=lambda x: x[1], reverse=True)[:10]
        
        df_top_grupos = pd.DataFrame([
            {'Grupo': grupos_dict.get(grupo_id, 'Desconocido'), 'Participantes': count}
            for grupo_id, count in top_grupos
        ])
        
        fig = px.bar(
            df_top_grupos,
            x='Participantes',
            y='Grupo',
            orientation='h',
            color='Participantes',
            color_continuous_scale='Teal'
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


# =====================================================
# TAB 6: GESTIÓN DE AULAS
# =====================================================

def mostrar_gestion_aulas(supabase, datos_globales, dashboard):
    """Estadísticas y ocupación de aulas"""
    
    dashboard.section_header(
        "Gestión de Aulas",
        "Análisis de infraestructura y ocupación",
        "🏫"
    )
    
    # === MÉTRICAS DE AULAS ===
    col1, col2, col3 = st.columns(3)
    
    with col1:
        dashboard.metric_card_secondary(
            "Aulas Totales",
            str(datos_globales['total_aulas']),
            "🏫",
            "#3B82F6"
        )
    
    with col2:
        dashboard.metric_card_secondary(
            "Aulas Activas",
            str(datos_globales['aulas_activas']),
            "✓",
            "#10B981"
        )
    
    with col3:
        capacidad_total = sum([a.get('capacidad_maxima', 0) for a in datos_globales['aulas']])
        dashboard.metric_card_secondary(
            "Capacidad Total",
            str(capacidad_total),
            "👥",
            "#F59E0B"
        )
    
    # === RESERVAS DEL MES ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📅 Actividad de Reservas")
    
    try:
        inicio_mes = datetime.now().replace(day=1)
        reservas_mes_res = supabase.table("aula_reservas")\
            .select("*")\
            .gte("fecha_inicio", inicio_mes.isoformat())\
            .execute()
        
        reservas_mes = reservas_mes_res.data or []
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Reservas Este Mes", len(reservas_mes))
            st.metric("Reservas Hoy", datos_globales['reservas_hoy'])
        
        with col2:
            # Reservas por tipo
            tipos_count = {}
            for reserva in reservas_mes:
                tipo = reserva.get('tipo_reserva', 'Sin tipo')
                tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
            
            if tipos_count:
                df_tipos = pd.DataFrame(
                    list(tipos_count.items()),
                    columns=['Tipo', 'Cantidad']
                )
                
                fig = px.pie(
                    df_tipos,
                    values='Cantidad',
                    names='Tipo',
                    color_discrete_sequence=['#3B82F6', '#10B981', '#F59E0B']
                )
                fig.update_layout(height=250)
                st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error cargando reservas: {e}")
    
    # === OCUPACIÓN POR AULA ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📊 Tasa de Ocupación por Aula")
    
    try:
        # Obtener todas las reservas
        todas_reservas_res = supabase.table("aula_reservas").select("aula_id").execute()
        todas_reservas = todas_reservas_res.data or []
        
        reservas_por_aula = {}
        for reserva in todas_reservas:
            aula_id = reserva.get('aula_id')
            if aula_id:
                reservas_por_aula[aula_id] = reservas_por_aula.get(aula_id, 0) + 1
        
        if reservas_por_aula:
            aulas_dict = {a['id']: a.get('nombre', 'Sin nombre') for a in datos_globales['aulas']}
            
            df_ocupacion = pd.DataFrame([
                {'Aula': aulas_dict.get(aula_id, 'Desconocida'), 'Reservas': count}
                for aula_id, count in reservas_por_aula.items()
            ]).sort_values('Reservas', ascending=True)
            
            fig = px.bar(
                df_ocupacion,
                x='Reservas',
                y='Aula',
                orientation='h',
                color='Reservas',
                color_continuous_scale='Oranges'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de reservas")
    
    except Exception as e:
        st.error(f"Error calculando ocupación: {e}")


# =====================================================
# TAB 7: GESTIÓN DE CLASES
# =====================================================

def mostrar_gestion_clases(supabase, datos_globales, dashboard):
    """Estadísticas del sistema de clases"""
    
    dashboard.section_header(
        "Gestión de Clases",
        "Análisis de programación y asistencia",
        "📅"
    )
    
    # === MÉTRICAS DE CLASES ===
    col1, col2, col3 = st.columns(3)
    
    with col1:
        dashboard.metric_card_secondary(
            "Clases Totales",
            str(len(datos_globales['clases'])),
            "📚",
            "#3B82F6"
        )
    
    with col2:
        dashboard.metric_card_secondary(
            "Clases Activas",
            str(datos_globales['total_clases']),
            "✓",
            "#10B981"
        )
    
    with col3:
        # Horarios programados
        try:
            horarios_res = supabase.table("clases_horarios").select("id").execute()
            total_horarios = len(horarios_res.data or [])
            dashboard.metric_card_secondary(
                "Horarios Programados",
                str(total_horarios),
                "🕐",
                "#F59E0B"
            )
        except:
            dashboard.metric_card_secondary("Horarios Programados", "0", "🕐", "#F59E0B")
    
    # === CLASES POR CATEGORÍA ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📊 Distribución por Categoría")
    
    categorias_count = {}
    for clase in datos_globales['clases']:
        categoria = clase.get('categoria', 'Sin categoría')
        categorias_count[categoria] = categorias_count.get(categoria, 0) + 1
    
    if categorias_count:
        df_categorias = pd.DataFrame(
            list(categorias_count.items()),
            # Continuación del TAB 7: GESTIÓN DE CLASES

            columns=['Categoría', 'Cantidad']
        )
        
        fig = px.bar(
            df_categorias,
            x='Categoría',
            y='Cantidad',
            color='Cantidad',
            color_continuous_scale='Mint'
        )
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de categorías")
    
    # === RESERVAS DE CLASES ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📋 Estadísticas de Reservas")
    
    try:
        reservas_clases_res = supabase.table("clases_reservas").select("estado").execute()
        reservas_clases = reservas_clases_res.data or []
        
        if reservas_clases:
            estados_count = {}
            for reserva in reservas_clases:
                estado = reserva.get('estado', 'Sin estado')
                estados_count[estado] = estados_count.get(estado, 0) + 1
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Total Reservas", len(reservas_clases))
                
                for estado, count in estados_count.items():
                    st.metric(estado.replace('_', ' ').title(), count)
            
            with col2:
                df_estados = pd.DataFrame(
                    list(estados_count.items()),
                    columns=['Estado', 'Cantidad']
                )
                
                fig = px.pie(
                    df_estados,
                    values='Cantidad',
                    names='Estado',
                    color_discrete_sequence=['#10B981', '#3B82F6', '#EF4444', '#9CA3AF']
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay reservas registradas")
    
    except Exception as e:
        st.error(f"Error cargando reservas de clases: {e}")


# =====================================================
# TAB 8: PROYECTOS FUNDAE
# =====================================================

def mostrar_proyectos_fundae(supabase, datos_globales, dashboard):
    """Seguimiento de proyectos y subvenciones"""
    
    dashboard.section_header(
        "Proyectos FUNDAE",
        "Gestión de convocatorias y subvenciones",
        "📊"
    )
    
    # === MÉTRICAS DE PROYECTOS ===
    col1, col2, col3, col4 = st.columns(4)
    
    proyectos_convocados = len([p for p in datos_globales['proyectos'] if p.get('estado_proyecto') == 'CONVOCADO'])
    proyectos_ejecucion = len([p for p in datos_globales['proyectos'] if p.get('estado_proyecto') == 'EN_EJECUCION'])
    proyectos_finalizados = len([p for p in datos_globales['proyectos'] if p.get('estado_proyecto') == 'FINALIZADO'])
    
    with col1:
        dashboard.metric_card_secondary(
            "Total Proyectos",
            str(len(datos_globales['proyectos'])),
            "📁",
            "#3B82F6"
        )
    
    with col2:
        dashboard.metric_card_secondary(
            "Convocados",
            str(proyectos_convocados),
            "📢",
            "#F59E0B"
        )
    
    with col3:
        dashboard.metric_card_secondary(
            "En Ejecución",
            str(proyectos_ejecucion),
            "⚙️",
            "#10B981"
        )
    
    with col4:
        dashboard.metric_card_secondary(
            "Finalizados",
            str(proyectos_finalizados),
            "✅",
            "#6B7280"
        )
    
    # === PRESUPUESTOS ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 💰 Análisis Económico")
    
    presupuesto_total = sum([float(p.get('presupuesto_total', 0) or 0) for p in datos_globales['proyectos']])
    importe_concedido = sum([float(p.get('importe_concedido', 0) or 0) for p in datos_globales['proyectos']])
    importe_justificado = sum([float(p.get('importe_justificado', 0) or 0) for p in datos_globales['proyectos']])
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Presupuesto Total", f"{presupuesto_total:,.2f} €")
    
    with col2:
        st.metric("Importe Concedido", f"{importe_concedido:,.2f} €")
    
    with col3:
        st.metric("Importe Justificado", f"{importe_justificado:,.2f} €")
    
    # === PROYECTOS POR TIPO ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📊 Proyectos por Tipo")
    
    tipos_count = {}
    for proyecto in datos_globales['proyectos']:
        tipo = proyecto.get('tipo_proyecto', 'Sin tipo')
        tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
    
    if tipos_count:
        df_tipos = pd.DataFrame(
            list(tipos_count.items()),
            columns=['Tipo', 'Cantidad']
        )
        
        fig = px.pie(
            df_tipos,
            values='Cantidad',
            names='Tipo',
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    # === TIMELINE DE PROYECTOS ===
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📅 Timeline de Proyectos Activos")
    
    proyectos_activos = [
        p for p in datos_globales['proyectos']
        if p.get('estado_proyecto') in ['CONVOCADO', 'EN_EJECUCION']
        and p.get('fecha_inicio') and p.get('fecha_fin')
    ]
    
    if proyectos_activos:
        timeline_data = []
        for p in proyectos_activos[:10]:  # Mostrar máximo 10
            try:
                timeline_data.append({
                    'Proyecto': p.get('nombre', 'Sin nombre')[:30],
                    'Inicio': pd.to_datetime(p['fecha_inicio']),
                    'Fin': pd.to_datetime(p['fecha_fin']),
                    'Estado': p.get('estado_proyecto', 'N/A')
                })
            except:
                continue
        
        if timeline_data:
            df_timeline = pd.DataFrame(timeline_data)
            
            fig = px.timeline(
                df_timeline,
                x_start='Inicio',
                x_end='Fin',
                y='Proyecto',
                color='Estado',
                color_discrete_map={
                    'CONVOCADO': '#F59E0B',
                    'EN_EJECUCION': '#10B981',
                    'FINALIZADO': '#6B7280'
                }
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay proyectos activos con fechas")
    
    # === ALERTAS DE VENCIMIENTO ===
    st.markdown("<br>", unsafe_allow_html=True)
    dashboard.section_header("Alertas de Vencimiento", icon="⚠️")
    
    hoy = datetime.now().date()
    fecha_limite = hoy + timedelta(days=60)
    
    proyectos_proximos = []
    for proyecto in datos_globales['proyectos']:
        if proyecto.get('fecha_justificacion'):
            try:
                fecha_just = pd.to_datetime(proyecto['fecha_justificacion']).date()
                if hoy <= fecha_just <= fecha_limite:
                    proyectos_proximos.append({
                        'Proyecto': proyecto.get('nombre', 'Sin nombre'),
                        'Fecha Justificación': fecha_just,
                        'Días Restantes': (fecha_just - hoy).days
                    })
            except:
                continue
    
    if proyectos_proximos:
        df_proximos = pd.DataFrame(proyectos_proximos).sort_values('Días Restantes')
        st.dataframe(df_proximos, use_container_width=True, hide_index=True)
    else:
        st.success("No hay proyectos con vencimientos próximos")


# =====================================================
# TAB 9: MÓDULO CRM
# =====================================================

def mostrar_modulo_crm(supabase, datos_globales, dashboard):
    """Estadísticas del módulo CRM"""
    
    dashboard.section_header(
        "Módulo CRM",
        "Gestión de relaciones con clientes",
        "💼"
    )
    
    try:
        # Cargar datos CRM
        oportunidades_res = supabase.table("crm_oportunidades").select("*").execute()
        oportunidades = oportunidades_res.data or []
        
        tareas_res = supabase.table("crm_tareas").select("*").execute()
        tareas = tareas_res.data or []
        
        comunicaciones_res = supabase.table("crm_comunicaciones").select("*").execute()
        comunicaciones = comunicaciones_res.data or []
        
        # === MÉTRICAS CRM ===
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            dashboard.metric_card_secondary(
                "Oportunidades",
                str(len(oportunidades)),
                "💡",
                "#3B82F6"
            )
        
        with col2:
            dashboard.metric_card_secondary(
                "Tareas",
                str(len(tareas)),
                "📋",
                "#10B981"
            )
        
        with col3:
            dashboard.metric_card_secondary(
                "Comunicaciones",
                str(len(comunicaciones)),
                "📞",
                "#F59E0B"
            )
        
        with col4:
            # Valor total de oportunidades
            valor_total = sum([float(o.get('valor_estimado', 0) or 0) for o in oportunidades])
            dashboard.metric_card_secondary(
                "Valor Pipeline",
                f"{valor_total:,.0f}€",
                "💰",
                "#8B5CF6"
            )
        
        # === OPORTUNIDADES POR ESTADO ===
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 💡 Pipeline de Oportunidades")
        
        if oportunidades:
            estados_count = {}
            valores_por_estado = {}
            
            for oportunidad in oportunidades:
                estado = oportunidad.get('estado', 'Sin estado')
                estados_count[estado] = estados_count.get(estado, 0) + 1
                
                valor = float(oportunidad.get('valor_estimado', 0) or 0)
                valores_por_estado[estado] = valores_por_estado.get(estado, 0) + valor
            
            col1, col2 = st.columns(2)
            
            with col1:
                df_estados = pd.DataFrame(
                    list(estados_count.items()),
                    columns=['Estado', 'Cantidad']
                )
                
                fig = px.funnel(
                    df_estados,
                    x='Cantidad',
                    y='Estado',
                    color='Estado',
                    color_discrete_sequence=px.colors.sequential.RdBu
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                df_valores = pd.DataFrame(
                    list(valores_por_estado.items()),
                    columns=['Estado', 'Valor Total']
                )
                
                fig = px.bar(
                    df_valores,
                    x='Estado',
                    y='Valor Total',
                    color='Valor Total',
                    color_continuous_scale='Greens'
                )
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay oportunidades registradas")
        
        # === TAREAS PENDIENTES ===
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📋 Estado de Tareas")
        
        if tareas:
            estados_tareas = {}
            for tarea in tareas:
                estado = tarea.get('estado', 'Sin estado')
                estados_tareas[estado] = estados_tareas.get(estado, 0) + 1
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                for estado, count in estados_tareas.items():
                    st.metric(estado.replace('_', ' ').title(), count)
            
            with col2:
                df_tareas = pd.DataFrame(
                    list(estados_tareas.items()),
                    columns=['Estado', 'Cantidad']
                )
                
                fig = px.pie(
                    df_tareas,
                    values='Cantidad',
                    names='Estado',
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay tareas registradas")
        
        # === COMUNICACIONES RECIENTES ===
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📞 Actividad de Comunicaciones")
        
        if comunicaciones:
            # Últimos 30 días
            fecha_limite = datetime.now() - timedelta(days=30)
            
            comunicaciones_recientes = [
                c for c in comunicaciones
                if c.get('fecha') and pd.to_datetime(c['fecha']) >= fecha_limite
            ]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Comunicaciones (30 días)", len(comunicaciones_recientes))
                st.metric("Total histórico", len(comunicaciones))
            
            with col2:
                # Por tipo
                tipos_count = {}
                for com in comunicaciones_recientes:
                    tipo = com.get('tipo', 'Sin tipo')
                    tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
                
                if tipos_count:
                    df_tipos = pd.DataFrame(
                        list(tipos_count.items()),
                        columns=['Tipo', 'Cantidad']
                    )
                    
                    fig = px.bar(
                        df_tipos,
                        x='Tipo',
                        y='Cantidad',
                        color='Cantidad',
                        color_continuous_scale='Blues'
                    )
                    fig.update_layout(height=250, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay comunicaciones registradas")
    
    except Exception as e:
        st.error(f"Error cargando datos CRM: {e}")
        st.info("Verifica que las tablas CRM estén creadas correctamente")


# =====================================================
# EXPORT - Si se requiere en el futuro
# =====================================================

def exportar_informe_ejecutivo(datos_globales):
    """Genera un informe ejecutivo en PDF (futuro)"""
    pass
