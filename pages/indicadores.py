import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("📈 Indicadores de Calidad ISO 9001")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 Solo administradores o gestores pueden acceder a esta sección.")
        st.stop()

    # =========================
    # Cargar datos de las tablas clave
    # =========================
    nc_res = supabase.table("no_conformidades").select("*").execute()
    df_nc = pd.DataFrame(nc_res.data) if nc_res.data else pd.DataFrame()

    ac_res = supabase.table("acciones_correctivas").select("*").execute()
    df_ac = pd.DataFrame(ac_res.data) if ac_res.data else pd.DataFrame()

    aud_res = supabase.table("auditorias").select("*").execute()
    df_aud = pd.DataFrame(aud_res.data) if aud_res.data else pd.DataFrame()

    # =========================
    # Filtro por fecha
    # =========================
    st.markdown("### 📅 Filtro por periodo")
    col1, col2 = st.columns(2)
    fecha_inicio = col1.date_input("Desde", datetime(datetime.now().year, 1, 1))
    fecha_fin = col2.date_input("Hasta", datetime.today())

    def filtrar_por_fecha(df, campo_fecha):
        if campo_fecha in df.columns:
            df[campo_fecha] = pd.to_datetime(df[campo_fecha], errors="coerce")
            return df[(df[campo_fecha] >= pd.to_datetime(fecha_inicio)) & (df[campo_fecha] <= pd.to_datetime(fecha_fin))]
        return df

    df_nc = filtrar_por_fecha(df_nc, "fecha")
    df_ac = filtrar_por_fecha(df_ac, "fecha_inicio")
    df_aud = filtrar_por_fecha(df_aud, "fecha")

    # =========================
    # KPIs
    # =========================
    st.markdown("### 📊 KPIs de Calidad")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("NC Abiertas", len(df_nc[df_nc["estado"] == "Abierta"]) if "estado" in df_nc.columns else 0)
    col2.metric("NC Cerradas", len(df_nc[df_nc["estado"] == "Cerrada"]) if "estado" in df_nc.columns else 0)
    col3.metric("Acciones Correctivas Cerradas", len(df_ac[df_ac["estado"] == "Cerrada"]) if "estado" in df_ac.columns else 0)
    col4.metric("Auditorías Realizadas", len(df_aud))

    # =========================
    # Tiempo medio de resolución de NC
    # =========================
    if "fecha" in df_nc.columns and "fecha_cierre" in df_nc.columns:
        df_nc["fecha"] = pd.to_datetime(df_nc["fecha"], errors="coerce")
        df_nc["fecha_cierre"] = pd.to_datetime(df_nc["fecha_cierre"], errors="coerce")
        df_nc["dias_resolucion"] = (df_nc["fecha_cierre"] - df_nc["fecha"]).dt.days
        tiempo_medio = df_nc["dias_resolucion"].mean(skipna=True)
        st.metric("⏱️ Tiempo medio de resolución (días)", round(tiempo_medio, 1) if pd.notnull(tiempo_medio) else "N/D")

    # =========================
    # Tablas de detalle
    # =========================
    st.markdown("### 📋 Detalle de datos filtrados")
    with st.expander("No Conformidades"):
        st.dataframe(df_nc)
    with st.expander("Acciones Correctivas"):
        st.dataframe(df_ac)
    with st.expander("Auditorías"):
        st.dataframe(df_aud)

    # =========================
    # Exportación
    # =========================
    st.download_button(
        "⬇️ Descargar indicadores (CSV)",
        data=pd.concat([
            df_nc.assign(tabla="No Conformidades"),
            df_ac.assign(tabla="Acciones Correctivas"),
            df_aud.assign(tabla="Auditorías")
        ], ignore_index=True).to_csv(index=False).encode("utf-8"),
        file_name="indicadores_calidad.csv",
        mime="text/csv"
    )
