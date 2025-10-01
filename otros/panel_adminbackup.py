import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import altair as alt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import io

def render(supabase, session_state):
    st.title("🛡️ Panel de Administración")
    st.caption("Supervisión del sistema, métricas globales y detección de alertas.")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    hoy = datetime.today().date()

    # =========================
    # Cargar datos base de forma segura
    # =========================
    try:
        # Cargar empresas
        empresas_res = supabase.table("empresas").select("id, nombre, created_at, fecha_alta").execute()
        empresas_data = empresas_res.data or []
        empresas_dict = {e["id"]: e["nombre"] for e in empresas_data}

        # Cargar tutores
        tutores_res = supabase.table("tutores").select("id, nombre, apellidos, empresa_id").execute()
        tutores_data = tutores_res.data or []
        tutores_dict = {t["id"]: f"{t['nombre']} {t.get('apellidos', '')}" for t in tutores_data}

        # Cargar usuarios
        usuarios_res = supabase.table("usuarios").select("id, rol, created_at, empresa_id").execute()
        usuarios_data = usuarios_res.data or []

    except Exception as e:
        st.error(f"❌ Error al cargar datos base: {e}")
        return

    # =========================
    # Métricas principales mejoradas
    # =========================
    try:
        # Usar funciones SQL optimizadas si están disponibles
        try:
            metricas_res = supabase.rpc('get_admin_metrics').execute()
            if metricas_res.data:
                metricas = metricas_res.data[0]
                total_empresas = metricas.get('total_empresas', 0)
                total_usuarios = metricas.get('total_usuarios', 0)
                total_cursos = metricas.get('total_cursos', 0)
                total_grupos = metricas.get('total_grupos', 0)
                nuevas_empresas_mes = metricas.get('nuevas_empresas_mes', 0)
                usuarios_activos_mes = metricas.get('usuarios_activos_mes', 0)
                grupos_activos = metricas.get('grupos_activos', 0)
            else:
                raise Exception("No data from RPC function")
        except Exception:
            # Fallback a consultas directas
            total_empresas = len(empresas_data)
            total_usuarios = len(usuarios_data)
            
            cursos_res = supabase.table("acciones_formativas").select("id").execute()
            total_cursos = len(cursos_res.data or [])
            
            grupos_res = supabase.table("grupos").select("id, fecha_inicio, fecha_fin_prevista").execute()
            grupos_data = grupos_res.data or []
            total_grupos = len(grupos_data)
            
            # Calcular nuevas empresas este mes
            inicio_mes = datetime.now().replace(day=1).date()
            nuevas_empresas_mes = len([
                e for e in empresas_data 
                if e.get('created_at') or e.get('fecha_alta')
                and pd.to_datetime(e.get('created_at') or e.get('fecha_alta'), errors='coerce').date() >= inicio_mes
            ])
            
            # Calcular usuarios activos este mes
            usuarios_activos_mes = len([
                u for u in usuarios_data 
                if u.get('created_at') and pd.to_datetime(u['created_at'], errors='coerce').date() >= inicio_mes
            ])
            
            # Calcular grupos activos
            grupos_activos = len([
                g for g in grupos_data
                if (g.get('fecha_inicio') and pd.to_datetime(g['fecha_inicio'], errors='coerce').date() <= hoy)
                and (not g.get('fecha_fin_prevista') or pd.to_datetime(g['fecha_fin_prevista'], errors='coerce').date() >= hoy)
            ])

        # Mostrar métricas principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🏢 Empresas", 
                total_empresas,
                delta=f"+{nuevas_empresas_mes} este mes" if nuevas_empresas_mes > 0 else None
            )
        
        with col2:
            st.metric(
                "👤 Usuarios", 
                total_usuarios,
                delta=f"+{usuarios_activos_mes} este mes" if usuarios_activos_mes > 0 else None
            )
        
        with col3:
            st.metric("📚 Cursos", total_cursos)
        
        with col4:
            st.metric(
                "👥 Grupos", 
                total_grupos,
                delta=f"{grupos_activos} activos"
            )

    except Exception as e:
        st.error(f"❌ Error al calcular métricas: {e}")

    st.divider()

    # =========================
    # Filtros interactivos mejorados
    # =========================
    with st.expander("🔍 Filtros Avanzados"):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            empresa_sel = st.selectbox("🏢 Empresa", ["Todas"] + list(empresas_dict.values()))
        
        with col2:
            tutor_sel = st.selectbox("🧑‍🏫 Tutor", ["Todos"] + list(tutores_dict.values()))
        
        with col3:
            fecha_inicio = st.date_input("📅 Desde", value=None)
        
        with col4:
            fecha_fin = st.date_input("📅 Hasta", value=None)

    # =========================
    # Cargar datos filtrados de forma segura
    # =========================
    try:
        # Construir consulta de grupos con filtros
        grupos_query = supabase.table("grupos").select("id, codigo_grupo, fecha_inicio, fecha_fin, fecha_fin_prevista, empresa_id")

        # Aplicar filtro de empresa
        if empresa_sel != "Todas":
            empresa_id_filtro = next((k for k, v in empresas_dict.items() if v == empresa_sel), None)
            if empresa_id_filtro:
                grupos_query = grupos_query.eq("empresa_id", empresa_id_filtro)

        # Aplicar filtro de tutor
        if tutor_sel != "Todos":
            tutor_id_filtro = next((k for k, v in tutores_dict.items() if v == tutor_sel), None)
            if tutor_id_filtro:
                # Buscar grupos asociados a este tutor
                try:
                    tutores_grupos_res = supabase.table("tutores_grupos").select("grupo_id").eq("tutor_id", tutor_id_filtro).execute()
                    grupos_ids = [tg["grupo_id"] for tg in (tutores_grupos_res.data or [])]
                    if grupos_ids:
                        grupos_query = grupos_query.in_("id", grupos_ids)
                    else:
                        # No hay grupos para este tutor
                        grupos_filtrados = []
                        grupos_query = None
                except Exception as e:
                    st.warning(f"⚠️ Error al filtrar por tutor: {e}")

        # Aplicar filtros de fecha
        if fecha_inicio and grupos_query:
            grupos_query = grupos_query.gte("fecha_inicio", fecha_inicio.isoformat())
        if fecha_fin and grupos_query:
            grupos_query = grupos_query.lte("fecha_fin_prevista", fecha_fin.isoformat())

        # Ejecutar consulta
        if grupos_query:
            grupos_filtrados = grupos_query.execute().data or []
        else:
            grupos_filtrados = []

        # Cargar otros datos necesarios para alertas
        diplomas_res = supabase.table("diplomas").select("id, url, participante_id, grupo_id").execute()
        diplomas_data = diplomas_res.data or []

        participantes_res = supabase.table("participantes").select("id, nombre, email, grupo_id, empresa_id").execute()
        participantes_data = participantes_res.data or []

        tutores_grupos_res = supabase.table("tutores_grupos").select("grupo_id, tutor_id").execute()
        tutores_grupos_data = tutores_grupos_res.data or []

    except Exception as e:
        st.error(f"❌ Error al aplicar filtros: {e}")
        grupos_filtrados = []
        diplomas_data = []
        participantes_data = []
        tutores_grupos_data = []

    # =========================
    # Calcular alertas de forma segura
    # =========================
    try:
        # Alertas sobre grupos finalizados sin diplomas
        grupos_finalizados = []
        for g in grupos_filtrados:
            try:
                fecha_fin = g.get("fecha_fin") or g.get("fecha_fin_prevista")
                if fecha_fin and pd.to_datetime(fecha_fin, errors='coerce').date() < hoy:
                    grupos_finalizados.append(g)
            except Exception:
                continue

        grupos_con_diplomas = set(d["grupo_id"] for d in diplomas_data if d.get("grupo_id"))
        grupos_sin_diplomas = [g for g in grupos_finalizados if g["id"] not in grupos_con_diplomas]

        # Participantes sin grupo
        participantes_sin_grupo = [p for p in participantes_data if not p.get("grupo_id")]

        # Grupos sin tutores
        grupos_con_tutores = set(tg["grupo_id"] for tg in tutores_grupos_data if tg.get("grupo_id"))
        grupos_sin_tutores = [g for g in grupos_filtrados if g["id"] not in grupos_con_tutores]

        # Diplomas con URLs inválidas
        diplomas_invalidos = [
            d for d in diplomas_data 
            if not d.get("url") or not str(d["url"]).startswith(("http://", "https://"))
        ]

        # Empresas sin participantes
        empresas_con_participantes = set(p["empresa_id"] for p in participantes_data if p.get("empresa_id"))
        empresas_sin_participantes = [e for e in empresas_data if e["id"] not in empresas_con_participantes]

        # Alertas sobre módulos próximos a vencer (verificar si existe la tabla)
        empresas_con_vencimientos = []
        try:
            DIAS_AVISO_VENCIMIENTO = 30
            fecha_limite = hoy + timedelta(days=DIAS_AVISO_VENCIMIENTO)
            
            # Verificar vencimientos en empresas (fechas de fin de módulos)
            for empresa in empresas_data:
                alertas_empresa = []
                
                # Verificar módulo de formación
                if empresa.get("formacion_fin"):
                    try:
                        fecha_fin_formacion = pd.to_datetime(empresa["formacion_fin"]).date()
                        if hoy <= fecha_fin_formacion <= fecha_limite:
                            alertas_empresa.append(f"Formación vence el {fecha_fin_formacion}")
                    except Exception:
                        pass
                
                # Verificar módulo ISO
                if empresa.get("iso_fin"):
                    try:
                        fecha_fin_iso = pd.to_datetime(empresa["iso_fin"]).date()
                        if hoy <= fecha_fin_iso <= fecha_limite:
                            alertas_empresa.append(f"ISO 9001 vence el {fecha_fin_iso}")
                    except Exception:
                        pass
                
                # Verificar módulo RGPD
                if empresa.get("rgpd_fin"):
                    try:
                        fecha_fin_rgpd = pd.to_datetime(empresa["rgpd_fin"]).date()
                        if hoy <= fecha_fin_rgpd <= fecha_limite:
                            alertas_empresa.append(f"RGPD vence el {fecha_fin_rgpd}")
                    except Exception:
                        pass
                
                if alertas_empresa:
                    empresas_con_vencimientos.append({
                        "empresa": empresa["nombre"],
                        "alertas": alertas_empresa
                    })

        except Exception as e:
            st.warning(f"⚠️ Error al verificar vencimientos: {e}")

    except Exception as e:
        st.error(f"❌ Error al calcular alertas: {e}")
        grupos_sin_diplomas = []
        participantes_sin_grupo = []
        grupos_sin_tutores = []
        diplomas_invalidos = []
        empresas_sin_participantes = []
        empresas_con_vencimientos = []

    # =========================
    # Tabs: Alertas, Estadísticas y Análisis
    # =========================
    tab1, tab2, tab3, tab4 = st.tabs(["🔔 Alertas del Sistema", "📊 Estadísticas Detalladas", "📈 Análisis de Tendencias", "📄 Informe de Cursos"])

    with tab1:
        st.subheader("🔍 Alertas Activas")
        
        alertas_encontradas = 0

        # Alertas sobre vencimientos de módulos
        if empresas_con_vencimientos:
            alertas_encontradas += len(empresas_con_vencimientos)
            st.warning(f"⚠️ {len(empresas_con_vencimientos)} empresas tienen módulos próximos a vencer")
            with st.expander("Ver vencimientos próximos"):
                for empresa_alert in empresas_con_vencimientos:
                    st.markdown(f"**🏢 {empresa_alert['empresa']}**")
                    for alerta in empresa_alert['alertas']:
                        st.markdown(f"  - ⏰ {alerta}")

        # Alertas sobre grupos sin diplomas
        if grupos_sin_diplomas:
            alertas_encontradas += len(grupos_sin_diplomas)
            st.warning(f"⚠️ {len(grupos_sin_diplomas)} grupos finalizados sin diplomas")
            with st.expander("Ver grupos sin diplomas"):
                for g in grupos_sin_diplomas[:10]:  # Mostrar máximo 10
                    empresa_nombre = empresas_dict.get(g.get("empresa_id"), "Empresa desconocida")
                    st.markdown(f"- 🗂️ **{g['codigo_grupo']}** ({empresa_nombre}) - Fin: {g.get('fecha_fin', g.get('fecha_fin_prevista', 'Sin fecha'))}")
                if len(grupos_sin_diplomas) > 10:
                    st.caption(f"... y {len(grupos_sin_diplomas) - 10} grupos más")

        # Alertas sobre participantes sin grupo
        if participantes_sin_grupo:
            alertas_encontradas += len(participantes_sin_grupo)
            st.warning(f"⚠️ {len(participantes_sin_grupo)} participantes sin grupo asignado")
            with st.expander("Ver participantes sin grupo"):
                for p in participantes_sin_grupo[:10]:  # Mostrar máximo 10
                    empresa_nombre = empresas_dict.get(p.get("empresa_id"), "Sin empresa")
                    st.markdown(f"- 👤 **{p['nombre']}** ({p['email']}) - {empresa_nombre}")
                if len(participantes_sin_grupo) > 10:
                    st.caption(f"... y {len(participantes_sin_grupo) - 10} participantes más")

        # Alertas sobre grupos sin tutores
        if grupos_sin_tutores:
            alertas_encontradas += len(grupos_sin_tutores)
            st.warning(f"⚠️ {len(grupos_sin_tutores)} grupos sin tutores asignados")
            with st.expander("Ver grupos sin tutores"):
                for g in grupos_sin_tutores[:10]:
                    empresa_nombre = empresas_dict.get(g.get("empresa_id"), "Empresa desconocida")
                    st.markdown(f"- 🧑‍🏫 **{g['codigo_grupo']}** ({empresa_nombre})")
                if len(grupos_sin_tutores) > 10:
                    st.caption(f"... y {len(grupos_sin_tutores) - 10} grupos más")

        # Alertas sobre diplomas inválidos
        if diplomas_invalidos:
            alertas_encontradas += len(diplomas_invalidos)
            st.warning(f"⚠️ {len(diplomas_invalidos)} diplomas con enlaces inválidos")
            with st.expander("Ver diplomas inválidos"):
                for d in diplomas_invalidos[:10]:
                    st.markdown(f"- 📄 Diploma ID: `{d['id']}` - URL: `{d.get('url', 'Sin URL')}`")
                if len(diplomas_invalidos) > 10:
                    st.caption(f"... y {len(diplomas_invalidos) - 10} diplomas más")

        # Alertas sobre empresas sin participantes
        if empresas_sin_participantes:
            alertas_encontradas += len(empresas_sin_participantes)
            st.warning(f"⚠️ {len(empresas_sin_participantes)} empresas sin participantes")
            with st.expander("Ver empresas sin participantes"):
                for e in empresas_sin_participantes[:10]:
                    st.markdown(f"- 🏢 **{e['nombre']}**")
                if len(empresas_sin_participantes) > 10:
                    st.caption(f"... y {len(empresas_sin_participantes) - 10} empresas más")

        # Mensaje si no hay alertas
        if alertas_encontradas == 0:
            st.success("✅ ¡Excelente! No hay alertas activas en el sistema.")
            st.balloons()

        # Resumen de alertas
        if alertas_encontradas > 0:
            st.info(f"📊 Total de alertas encontradas: **{alertas_encontradas}**")

    with tab2:
        st.subheader("📈 Estadísticas Detalladas del Sistema")
        
        # Distribución de usuarios por rol
        if usuarios_data:
            roles_count = {}
            for usuario in usuarios_data:
                rol = usuario.get('rol', 'Sin rol')
                roles_count[rol] = roles_count.get(rol, 0) + 1

            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 👥 Usuarios por Rol")
                for rol, count in roles_count.items():
                    st.write(f"**{rol.capitalize()}:** {count}")

            with col2:
                st.markdown("#### 🏢 Top 5 Empresas con más Usuarios")
                empresas_usuarios = {}
                for usuario in usuarios_data:
                    if usuario.get('empresa_id'):
                        empresa_nombre = empresas_dict.get(usuario['empresa_id'], 'Desconocida')
                        empresas_usuarios[empresa_nombre] = empresas_usuarios.get(empresa_nombre, 0) + 1
                
                top_empresas = sorted(empresas_usuarios.items(), key=lambda x: x[1], reverse=True)[:5]
                for empresa, count in top_empresas:
                    st.write(f"**{empresa}:** {count} usuarios")

        # Estadísticas de grupos y participantes
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Estados de Grupos")
            grupos_activos_count = 0
            grupos_finalizados_count = 0
            grupos_futuros_count = 0
            
            for grupo in grupos_filtrados:
                try:
                    fecha_inicio = grupo.get('fecha_inicio')
                    fecha_fin = grupo.get('fecha_fin_prevista')
                    
                    if fecha_inicio:
                        inicio = pd.to_datetime(fecha_inicio).date()
                        if inicio > hoy:
                            grupos_futuros_count += 1
                        elif fecha_fin:
                            fin = pd.to_datetime(fecha_fin).date()
                            if fin >= hoy:
                                grupos_activos_count += 1
                            else:
                                grupos_finalizados_count += 1
                        else:
                            grupos_activos_count += 1
                except Exception:
                    continue
            
            st.write(f"**🟢 Activos:** {grupos_activos_count}")
            st.write(f"**🔴 Finalizados:** {grupos_finalizados_count}")
            st.write(f"**🟡 Futuros:** {grupos_futuros_count}")

        with col2:
            st.markdown("#### 🎓 Estadísticas de Participantes")
            participantes_con_grupo = len([p for p in participantes_data if p.get('grupo_id')])
            participantes_sin_grupo_count = len(participantes_sin_grupo)
            
            st.write(f"**Con grupo:** {participantes_con_grupo}")
            st.write(f"**Sin grupo:** {participantes_sin_grupo_count}")
            st.write(f"**Total:** {len(participantes_data)}")

    with tab3:
        st.subheader("📈 Análisis de Tendencias")
        
        # Gráfico de evolución de empresas
        try:
            if empresas_data:
                # Preparar datos para el gráfico
                empresas_fechas = []
                for empresa in empresas_data:
                    fecha_creacion = empresa.get('created_at') or empresa.get('fecha_alta')
                    if fecha_creacion:
                        try:
                            fecha = pd.to_datetime(fecha_creacion).date()
                            empresas_fechas.append(fecha)
                        except Exception:
                            continue

                if empresas_fechas:
                    # Crear DataFrame para el gráfico
                    df_empresas = pd.DataFrame({'fecha': empresas_fechas})
                    df_empresas['count'] = 1
                    df_empresas = df_empresas.groupby('fecha').sum().cumsum().reset_index()
                    
                    # Crear gráfico con Altair
                    chart = alt.Chart(df_empresas).mark_line(point=True).encode(
                        x=alt.X('fecha:T', title='Fecha'),
                        y=alt.Y('count:Q', title='Empresas Acumuladas'),
                        tooltip=['fecha:T', 'count:Q']
                    ).properties(
                        title='Evolución del Número de Empresas',
                        width=600,
                        height=300
                    )
                    
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.info("ℹ️ No hay datos de fechas de creación de empresas para mostrar tendencias.")
                
        except Exception as e:
            st.error(f"❌ Error al generar gráfico de tendencias: {e}")
                
        # Tabla de actividad reciente
        st.markdown("#### 📅 Actividad Reciente (Últimos 7 días)")
        try:
            fecha_limite = hoy - timedelta(days=7)
            
            actividad_reciente = []
            
            # Empresas creadas
            for empresa in empresas_data:
                fecha_creacion = empresa.get('created_at') or empresa.get('fecha_alta')
                if fecha_creacion:
                    try:
                        fecha = pd.to_datetime(fecha_creacion).date()
                        if fecha >= fecha_limite:
                            actividad_reciente.append({
                                'Fecha': fecha,
                                'Tipo': 'Empresa creada',
                                'Descripción': empresa['nombre']
                            })
                    except Exception:
                        continue
            
            # Usuarios creados
            for usuario in usuarios_data:
                if usuario.get('created_at'):
                    try:
                        fecha = pd.to_datetime(usuario['created_at']).date()
                        if fecha >= fecha_limite:
                            rol = usuario.get('rol', 'Sin rol')
                            actividad_reciente.append({
                                'Fecha': fecha,
                                'Tipo': f'Usuario {rol} creado',
                                'Descripción': f"ID: {usuario['id']}"
                            })
                    except Exception:
                        continue
            
            if actividad_reciente:
                df_actividad = pd.DataFrame(actividad_reciente)
                df_actividad = df_actividad.sort_values('Fecha', ascending=False)
                st.dataframe(df_actividad, use_container_width=True, hide_index=True)
            else:
                st.info("ℹ️ No hay actividad reciente en los últimos 7 días.")
                
        except Exception as e:
            st.error(f"❌ Error al cargar actividad reciente: {e}")
            
    with tab4:
        st.subheader("📄 Generar Informe de Curso")
    
        # =====================
        # 1. Selección de filtros
        # =====================
        anos_data = supabase.table("acciones_formativas").select("ano_fundae").execute().data
        anos_validos = sorted({a["ano_fundae"] for a in anos_data if a.get("ano_fundae")})
        ano_fundae = st.selectbox("📅 Año FUNDAE", anos_validos or ["(ninguno)"])
    
        # Empresas gestoras disponibles
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_data}
        empresa_sel = st.selectbox("🏢 Empresa Gestora", list(empresas_dict.keys()) or ["(ninguna)"])
        empresa_id = empresas_dict.get(empresa_sel)
    
        # =====================
        # 2. Acciones de la empresa y año
        # =====================
        acciones = []
        if empresa_id and ano_fundae:
            acciones_res = (
                supabase.table("acciones_formativas")
                .select("id, nombre, codigo_accion, horas, modalidad, ano_fundae")
                .eq("empresa_id", empresa_id)
                .eq("ano_fundae", ano_fundae)
                .execute()
            )
            acciones = acciones_res.data or []
    
        acciones_dict = {a["nombre"]: a["id"] for a in acciones}
        accion_sel = st.selectbox("📚 Acción Formativa", list(acciones_dict.keys()) or ["(ninguna)"])
        accion_id = acciones_dict.get(accion_sel)
    
        # =====================
        # 3. Grupos de la acción
        # =====================
        grupos = []
        if accion_id:
            grupos_res = (
                supabase.table("grupos")
                .select("id, codigo_grupo, fecha_inicio, fecha_fin_prevista, horario, lugar_imparticion, observaciones")
                .eq("accion_formativa_id", accion_id)
                .execute()
            )
            grupos = grupos_res.data or []
    
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos}
        grupo_sel = st.selectbox("👥 Grupo", list(grupos_dict.keys()) or ["(ninguno)"])
        grupo_id = grupos_dict.get(grupo_sel)
    
        # =====================
        # 4. Generación de informe PDF
        # =====================
        if st.button("📥 Exportar Informe PDF", type="primary", use_container_width=True):
            if not (accion_id and grupo_id):
                st.error("❌ Selecciona acción formativa y grupo válidos antes de exportar.")
            else:
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4)
                styles = getSampleStyleSheet()
                story = []
    
                story.append(Paragraph("Ficha del Curso", styles["Title"]))
                story.append(Spacer(1, 12))
    
                # Datos básicos en tabla
                data = [
                    ["Campo", "Valor"],
                    ["Año FUNDAE", str(ano_fundae)],
                    ["Empresa Gestora", empresa_sel],
                    ["Acción Formativa", accion_sel],
                    ["Grupo", grupo_sel],
                ]
                table = Table(data, colWidths=[150, 300])
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(table)
    
                story.append(Spacer(1, 20))
                story.append(Paragraph("👉 El informe completo debería incluir tutores, participantes y empresas asociadas.", styles["Italic"]))
    
                doc.build(story)
                pdf = buffer.getvalue()
                buffer.close()
    
                st.download_button(
                    "⬇️ Descargar PDF",
                    pdf,
                    file_name=f"informe_curso_{ano_fundae}_{accion_sel}_{grupo_sel}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary"
                )
            
    st.divider()
    st.caption(f"🔄 Panel actualizado automáticamente - Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
