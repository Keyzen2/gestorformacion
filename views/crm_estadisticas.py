import streamlit as st
import pandas as pd
from datetime import datetime

def render(supabase, session_state):
    st.markdown("## 📊 Estadísticas CRM")
    st.caption("Análisis de rendimiento comercial.")
    st.divider()

    rol = session_state.role
    empresa_id = session_state.user.get("empresa_id")

    if rol not in ["admin", "gestor", "comercial"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # --- Selección de empresa para admin ---
    if rol == "admin":
        empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
        empresa_sel = st.selectbox("Empresa", list(empresas_dict.keys()))
        empresa_id = empresas_dict[empresa_sel]

    # --- Cargar comerciales ---
    comerciales_res = supabase.table("comerciales").select("id,nombre").eq("empresa_id", empresa_id).execute()
    comerciales_dict = {c["id"]: c["nombre"] for c in (comerciales_res.data or [])}

    # --- Cargar oportunidades ganadas ---
    oportunidades_res = supabase.table("crm_oportunidades").select("*").eq("empresa_id", empresa_id).eq("estado", "Ganada").execute()
    oportunidades = oportunidades_res.data or []

    if not oportunidades:
        st.info("No hay oportunidades ganadas para mostrar estadísticas.")
        return

    df = pd.DataFrame(oportunidades)
    df["fecha_cierre_real"] = pd.to_datetime(df["fecha_cierre_real"], errors="coerce")

    # --- Comercial: filtrar solo las suyas ---
    if rol == "comercial":
        comercial_id = session_state.user.get("comercial_id")
        df = df[df["comercial_id"] == comercial_id]

    # --- Estadísticas mensuales ---
    df["mes"] = df["fecha_cierre_real"].dt.to_period("M")
    mensual = df.groupby(["comercial_id", "mes"]).agg(
        oportunidades_cerradas=("id", "count"),
        total_ganado=("importe", "sum")
    ).reset_index()
    mensual["comercial"] = mensual["comercial_id"].map(comerciales_dict)

    st.markdown("### 📅 Estadísticas mensuales")
    st.dataframe(mensual[["mes", "comercial", "oportunidades_cerradas", "total_ganado"]])

    # --- Estadísticas anuales ---
    df["año"] = df["fecha_cierre_real"].dt.year
    anual = df.groupby(["comercial_id", "año"]).agg(
        oportunidades_cerradas=("id", "count"),
        total_ganado=("importe", "sum")
    ).reset_index()
    anual["comercial"] = anual["comercial_id"].map(comerciales_dict)

    st.markdown("### 📆 Estadísticas anuales")
    st.dataframe(anual[["año", "comercial", "oportunidades_cerradas", "total_ganado"]])

    # --- Ranking por total ganado ---
    ranking = df.groupby("comercial_id").agg(
        oportunidades_cerradas=("id", "count"),
        total_ganado=("importe", "sum")
    ).reset_index()
    ranking["comercial"] = ranking["comercial_id"].map(comerciales_dict)
    ranking = ranking.sort_values(by="total_ganado", ascending=False)

    st.markdown("### 🏆 Ranking de comerciales")
    st.dataframe(ranking[["comercial", "oportunidades_cerradas", "total_ganado"]])
  
