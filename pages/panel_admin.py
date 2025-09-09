import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 📈 Panel CRM - Admin")
    st.caption("Resumen global de actividad comercial y ranking de comerciales.")
    st.divider()

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        st.stop()

    # --- KPIs globales ---
    col1, col2, col3, col4 = st.columns(4)

    total_clientes = len(supabase.table("participantes").select("id").execute().data or [])
    col1.metric("👥 Clientes", total_clientes)

    oportunidades = supabase.table("crm_oportunidades").select("*").execute().data or []
    abiertas = [o for o in oportunidades if o.get("estado") == "Abierta"]
    ganadas = [o for o in oportunidades if o.get("estado") == "Ganada"]
    col2.metric("📂 Oportunidades abiertas", len(abiertas))
    col3.metric("🏆 Oportunidades ganadas", len(ganadas))

    tareas = supabase.table("crm_tareas").select("*").execute().data or []
    pendientes = [t for t in tareas if t.get("estado") != "Completada"]
    col4.metric("📝 Tareas pendientes", len(pendientes))

    st.divider()

    # --- Ranking de comerciales ---
    st.markdown("### 🏆 Ranking de comerciales")
    col_f1, col_f2 = st.columns(2)
    año_sel = col_f1.selectbox("Año", ["Todos"] + list(range(datetime.today().year, datetime.today().year - 5, -1)))
    mes_sel = col_f2.selectbox("Mes", ["Todos"] + list(range(1, 13)))

    comerciales_res = supabase.table("comerciales").select("id,nombre").execute()
    comerciales = {c["id"]: c["nombre"] for c in (comerciales_res.data or [])}

    oportunidades_ganadas = supabase.table("crm_oportunidades").select("*").eq("estado", "Ganada").execute().data or []
    df = pd.DataFrame(oportunidades_ganadas)
    if not df.empty:
        df["fecha_cierre_real"] = pd.to_datetime(df["fecha_cierre_real"], errors="coerce")
        if año_sel != "Todos":
            df = df[df["fecha_cierre_real"].dt.year == año_sel]
        if mes_sel != "Todos":
            df = df[df["fecha_cierre_real"].dt.month == mes_sel]

        ranking = df.groupby("comercial_id").agg(
            oportunidades_cerradas=("id", "count"),
            total_ganado=("importe", "sum")
        ).reset_index()
        ranking["comercial"] = ranking["comercial_id"].map(comerciales)
        ranking = ranking.sort_values(by="total_ganado", ascending=False)

        st.dataframe(ranking[["comercial", "oportunidades_cerradas", "total_ganado"]])
    else:
        st.info("No hay oportunidades ganadas para mostrar ranking.")

    st.divider()

    # --- Últimas comunicaciones ---
    st.markdown("### 📬 Últimas comunicaciones")
    comms_res = supabase.table("crm_comunicaciones").select("*").order("fecha", desc=True).limit(5).execute()
    comunicaciones = comms_res.data or []
    if comunicaciones:
        df_comms = pd.DataFrame(comunicaciones)
        st.table(df_comms[["tipo", "asunto", "fecha"]])
    else:
        st.info("No hay comunicaciones registradas.")
        
