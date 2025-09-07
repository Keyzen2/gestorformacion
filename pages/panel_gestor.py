import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from utils import is_module_active

def main(supabase, session_state):
    st.title("📊 Panel del Gestor")
    st.caption("Resumen estadístico de tu actividad formativa.")

    if session_state.role != "gestor":
        st.warning("🔒 Solo los gestores pueden acceder a este panel.")
        return

    empresa_id = session_state.user.get("empresa_id")
    empresa_data = session_state.user.get("empresa", {})
    empresa_crm = session_state.user.get("empresa_crm", {})

    if not is_module_active(empresa_data, empresa_crm, "formacion", datetime.today().date(), "gestor"):
        st.info("ℹ️ El módulo de formación no está activo para tu empresa.")
        return

    # =========================
    # Cargar datos
    # =========================
    try:
        acciones_res = supabase.table("acciones_formativas").select("id,nombre").eq("empresa_id", empresa_id).execute()
        total_acciones = len(acciones_res.data or [])
    except:
        total_acciones = 0

    try:
        grupos_res = supabase.table("grupos").select("id,codigo_grupo").eq("empresa_id", empresa_id).execute()
        df_grupos = pd.DataFrame(grupos_res.data or [])
        total_grupos = len(df_grupos)
    except:
        df_grupos = pd.DataFrame()
        total_grupos = 0

    try:
        part_res = supabase.table("participantes").select("*").eq("empresa_id", empresa_id).execute()
        df_part = pd.DataFrame(part_res.data or [])
        total_participantes = len(df_part)
    except:
        df_part = pd.DataFrame()
        total_participantes = 0

    try:
        diplomas_res = supabase.table("diplomas").select("id").eq("empresa_id", empresa_id).execute()
        total_diplomas = len(diplomas_res.data or [])
    except:
        total_diplomas = 0

    # =========================
    # Métricas principales
    # =========================
    st.subheader("📌 Resumen general")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📚 Acciones", total_acciones)
    col2.metric("👨‍🏫 Grupos", total_grupos)
    col3.metric("🧑‍🎓 Participantes", total_participantes)
    col4.metric("🏅 Diplomas", total_diplomas)

    st.divider()

    # =========================
    # Evolución de participantes
    # =========================
    if "fecha_alta" in df_part.columns:
        st.subheader("📈 Nuevos participantes por fecha")
        df_part["fecha_alta"] = pd.to_datetime(df_part["fecha_alta"], errors="coerce")
        df_evol = df_part.groupby(df_part["fecha_alta"].dt.date).size().reset_index(name="nuevos")
        chart = alt.Chart(df_evol).mark_bar().encode(
            x=alt.X("fecha_alta:T", title="Fecha"),
            y=alt.Y("nuevos:Q", title="Participantes"),
            tooltip=["fecha_alta", "nuevos"]
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)

    # =========================
    # Distribución por grupos
    # =========================
    if not df_part.empty and "grupo_id" in df_part.columns:
        st.subheader("👥 Participantes por grupo")
        grupo_counts = df_part["grupo_id"].value_counts().reset_index()
        grupo_counts.columns = ["Grupo ID", "Participantes"]
        st.bar_chart(grupo_counts.set_index("Grupo ID"))

    # =========================
    # Últimos participantes
    # =========================
    if not df_part.empty:
        st.subheader("🧑‍🎓 Últimos participantes registrados")
        df_recent = df_part.sort_values("fecha_alta", ascending=False).head(5)
        st.table(df_recent[["nombre", "apellidos", "email", "fecha_alta"]])

    # =========================
    # Participantes por grupo (detalle)
    # =========================
    st.divider()
    st.subheader("📋 Participantes asignados por grupo")

    try:
        pg_res = supabase.table("participantes_grupos").select("id,participante_id,grupo_id").execute()
        pg_data = pd.DataFrame(pg_res.data or [])
    except Exception as e:
        st.error(f"❌ Error al cargar asignaciones: {e}")
        pg_data = pd.DataFrame()

    if not df_grupos.empty and not pg_data.empty:
        for _, grupo in df_grupos.iterrows():
            grupo_id = grupo["id"]
            participantes_ids = pg_data[pg_data["grupo_id"] == grupo_id]["participante_id"].tolist()

            if participantes_ids:
                try:
                    part_res = supabase.table("participantes").select("id,nombre,email,dni").in_("id", participantes_ids).execute()
                    df_part_grupo = pd.DataFrame(part_res.data or [])
                    with st.expander(f"👥 {grupo['codigo_grupo']} ({len(df_part_grupo)} participantes)"):
                        st.table(df_part_grupo[["nombre", "email", "dni"]])
                except Exception as e:
                    st.error(f"❌ Error al cargar participantes del grupo {grupo['codigo_grupo']}: {e}")
            else:
                with st.expander(f"👥 {grupo['codigo_grupo']}"):
                    st.info("ℹ️ No hay participantes asignados a este grupo.")
