import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from services.data_service import get_data_service

def main(supabase, session_state):
    st.title("📊 Panel del Gestor")
    st.caption("Resumen estadístico de tu actividad formativa.")

    if session_state.role != "gestor":
        st.warning("🔒 Solo los gestores pueden acceder a este panel.")
        return

    empresa_id = session_state.user.get("empresa_id")
    
    # Verificar que el gestor tenga empresa asignada
    if not empresa_id:
        st.error("❌ No tienes una empresa asignada. Contacta con el administrador.")
        return

    # Obtener datos de empresa desde session_state (configurados en app.py)
    empresa_data = getattr(session_state, 'empresa', {})
    empresa_crm = getattr(session_state, 'empresa_crm', {})
    
    # Verificar si el módulo de formación está activo
    def is_formacion_active():
        """Verifica si el módulo de formación está activo para esta empresa."""
        if not empresa_data.get("formacion_activo"):
            return False
        
        hoy = datetime.today().date()
        inicio = empresa_data.get("formacion_inicio")
        if inicio:
            try:
                if pd.to_datetime(inicio).date() > hoy:
                    return False
            except:
                pass
        
        return True

    if not is_formacion_active():
        st.info("ℹ️ El módulo de formación no está activo para tu empresa.")
        return

    # Inicializar DataService
    try:
        data_service = get_data_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error al inicializar servicio de datos: {e}")
        return

    # =========================
    # Cargar datos con manejo de errores mejorado
    # =========================
    with st.spinner("Cargando datos de tu empresa..."):
        try:
            # Acciones formativas
            total_acciones = len(
                supabase.table("acciones_formativas").select("id").eq("empresa_id", empresa_id).execute().data or []
            )
        except Exception as e:
            st.warning(f"⚠️ Error al cargar acciones: {e}")
            total_acciones = 0

        try:
            # Grupos usando DataService
            df_grupos = data_service.get_grupos_completos()
            total_grupos = len(df_grupos)
        except Exception as e:
            st.warning(f"⚠️ Error al cargar grupos: {e}")
            df_grupos = pd.DataFrame()
            total_grupos = 0

        try:
            # Participantes
            part_res = supabase.table("participantes").select("*").eq("empresa_id", empresa_id).execute()
            df_part = pd.DataFrame(part_res.data or [])
            total_participantes = len(df_part)
        except Exception as e:
            st.warning(f"⚠️ Error al cargar participantes: {e}")
            df_part = pd.DataFrame()
            total_participantes = 0

        try:
            # Diplomas
            total_diplomas = len(
                supabase.table("diplomas").select("id").eq("empresa_id", empresa_id).execute().data or []
            )
        except Exception as e:
            st.warning(f"⚠️ Error al cargar diplomas: {e}")
            total_diplomas = 0

        try:
            # Tutores
            total_tutores = len(
                supabase.table("tutores").select("id").eq("empresa_id", empresa_id).execute().data or []
            )
        except Exception as e:
            st.warning(f"⚠️ Error al cargar tutores: {e}")
            total_tutores = 0

    # =========================
    # Métricas principales
    # =========================
    st.subheader("📌 Resumen general")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📚 Acciones", total_acciones)
    with col2:
        st.metric("👥 Grupos", total_grupos)
    with col3:
        st.metric("🧑‍🎓 Participantes", total_participantes)
    with col4:
        st.metric("🏅 Diplomas", total_diplomas)
    with col5:
        st.metric("👨‍🏫 Tutores", total_tutores)

    st.divider()

    # =========================
    # Análisis temporal de participantes
    # =========================
    if not df_part.empty and "created_at" in df_part.columns:
        st.subheader("📈 Evolución de participantes")
        
        try:
            # Preparar datos para el gráfico
            df_part["fecha_registro"] = pd.to_datetime(df_part["created_at"], errors="coerce")
            df_part_valid = df_part[df_part["fecha_registro"].notna()].copy()
            
            if not df_part_valid.empty:
                # Agrupar por fecha
                df_evol = df_part_valid.groupby(df_part_valid["fecha_registro"].dt.date).size().reset_index(name="nuevos")
                df_evol["acumulados"] = df_evol["nuevos"].cumsum()
                
                # Crear gráfico con Altair
                base = alt.Chart(df_evol).add_selection(
                    alt.selection_interval(bind='scales')
                )
                
                line = base.mark_line(color='blue', point=True).encode(
                    x=alt.X("fecha_registro:T", title="Fecha"),
                    y=alt.Y("acumulados:Q", title="Participantes acumulados"),
                    tooltip=["fecha_registro:T", "nuevos:Q", "acumulados:Q"]
                )
                
                bars = base.mark_bar(color='lightblue', opacity=0.7).encode(
                    x=alt.X("fecha_registro:T", title="Fecha"),
                    y=alt.Y("nuevos:Q", title="Nuevos participantes"),
                    tooltip=["fecha_registro:T", "nuevos:Q"]
                )
                
                chart = alt.layer(bars, line).resolve_scale(y='independent').properties(height=300)
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("ℹ️ No hay datos de fecha válidos para mostrar la evolución.")
                
        except Exception as e:
            st.error(f"❌ Error al generar gráfico de evolución: {e}")

    # =========================
    # Distribución por grupos
    # =========================
    if not df_part.empty and "grupo_id" in df_part.columns and total_grupos > 0:
        st.subheader("👥 Distribución de participantes por grupo")
        
        try:
            # Contar participantes por grupo
            participantes_por_grupo = df_part["grupo_id"].value_counts()
            
            if not participantes_por_grupo.empty:
                # Mapear IDs de grupo a códigos de grupo
                grupo_nombres = {}
                for _, grupo in df_grupos.iterrows():
                    codigo = grupo.get("codigo_grupo", f"Grupo {grupo['id']}")
                    grupo_nombres[grupo["id"]] = codigo
                
                # Preparar datos para el gráfico
                df_distribucion = pd.DataFrame({
                    "grupo_id": participantes_por_grupo.index,
                    "participantes": participantes_por_grupo.values
                })
                
                df_distribucion["grupo_nombre"] = df_distribucion["grupo_id"].map(grupo_nombres).fillna("Grupo desconocido")
                
                # Crear gráfico de barras
                chart = alt.Chart(df_distribucion).mark_bar().encode(
                    x=alt.X("grupo_nombre:N", title="Grupo", sort="-y"),
                    y=alt.Y("participantes:Q", title="Número de participantes"),
                    color=alt.Color("participantes:Q", scale=alt.Scale(scheme='blues')),
                    tooltip=["grupo_nombre:N", "participantes:Q"]
                ).properties(height=300)
                
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("ℹ️ No hay datos de distribución por grupos.")
                
        except Exception as e:
            st.error(f"❌ Error al generar distribución por grupos: {e}")

    # =========================
    # Tabla de últimos participantes
    # =========================
    if not df_part.empty:
        st.subheader("🧑‍🎓 Últimos participantes registrados")
        
        try:
            # Ordenar por fecha de creación
            if "created_at" in df_part.columns:
                df_recent = df_part.sort_values("created_at", ascending=False).head(10)
            else:
                df_recent = df_part.head(10)
            
            # Seleccionar columnas para mostrar
            columnas_mostrar = []
            for col in ["nombre", "apellidos", "email", "dni", "created_at"]:
                if col in df_recent.columns:
                    columnas_mostrar.append(col)
            
            if columnas_mostrar:
                df_display = df_recent[columnas_mostrar].copy()
                
                # Formatear fecha si existe
                if "created_at" in df_display.columns:
                    df_display["created_at"] = pd.to_datetime(df_display["created_at"], errors='coerce').dt.strftime('%d/%m/%Y')
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            else:
                st.info("ℹ️ No hay datos de participantes para mostrar.")
                
        except Exception as e:
            st.error(f"❌ Error al mostrar últimos participantes: {e}")

    # =========================
    # Detalle de participantes por grupo
    # =========================
    if not df_grupos.empty:
        st.divider()
        st.subheader("📋 Participantes por grupo (detalle)")

        try:
            for _, grupo in df_grupos.iterrows():
                grupo_id = grupo["id"]
                codigo_grupo = grupo.get("codigo_grupo", f"Grupo {grupo_id}")
                accion_nombre = grupo.get("accion_nombre", "Sin acción")
                
                # Buscar participantes de este grupo
                participantes_grupo = df_part[df_part["grupo_id"] == grupo_id] if "grupo_id" in df_part.columns else pd.DataFrame()
                
                num_participantes = len(participantes_grupo)
                
                with st.expander(f"👥 {codigo_grupo} - {accion_nombre} ({num_participantes} participantes)"):
                    if not participantes_grupo.empty:
                        # Mostrar tabla de participantes
                        columnas_participantes = []
                        for col in ["nombre", "apellidos", "email", "dni", "telefono"]:
                            if col in participantes_grupo.columns:
                                columnas_participantes.append(col)
                        
                        if columnas_participantes:
                            st.dataframe(
                                participantes_grupo[columnas_participantes],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("ℹ️ No hay información detallada de participantes.")
                    else:
                        st.info("ℹ️ No hay participantes asignados a este grupo.")
                        
                    # Información adicional del grupo
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        fecha_inicio = grupo.get("fecha_inicio")
                        if fecha_inicio:
                            st.write(f"**Inicio:** {pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')}")
                    with col2:
                        fecha_fin = grupo.get("fecha_fin_prevista")
                        if fecha_fin:
                            st.write(f"**Fin prevista:** {pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')}")
                    with col3:
                        modalidad = grupo.get("accion_modalidad")
                        if modalidad:
                            st.write(f"**Modalidad:** {modalidad}")
                            
        except Exception as e:
            st.error(f"❌ Error al mostrar detalle por grupos: {e}")

    # =========================
    # Resumen de estado de grupos
    # =========================
    if not df_grupos.empty:
        st.divider()
        st.subheader("📊 Estado de los grupos")
        
        try:
            hoy = datetime.today().date()
            grupos_activos = 0
            grupos_finalizados = 0
            grupos_futuros = 0
            grupos_sin_fecha = 0
            
            for _, grupo in df_grupos.iterrows():
                fecha_inicio = grupo.get("fecha_inicio")
                fecha_fin = grupo.get("fecha_fin_prevista")
                
                if not fecha_inicio:
                    grupos_sin_fecha += 1
                    continue
                
                try:
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
                        
                except Exception:
                    grupos_sin_fecha += 1
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🟢 Grupos Activos", grupos_activos)
            with col2:
                st.metric("🔴 Grupos Finalizados", grupos_finalizados)
            with col3:
                st.metric("🟡 Grupos Futuros", grupos_futuros)
            with col4:
                st.metric("⚪ Sin fechas", grupos_sin_fecha)
                
        except Exception as e:
            st.error(f"❌ Error al calcular estado de grupos: {e}")

    st.divider()
    st.caption(f"🔄 Datos actualizados automáticamente - Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
