import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("📊 Dashboard de Calidad ISO 9001")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 Solo administradores o gestores pueden acceder a esta sección.")
        st.stop()

    # Cargar datos
    df_nc = pd.DataFrame(supabase.table("no_conformidades").select("*").execute().data or [])
    df_ac = pd.DataFrame(supabase.table("acciones_correctivas").select("*").execute().data or [])
    df_aud = pd.DataFrame(supabase.table("auditorias").select("*").execute().data or [])

    # Filtro por fechas
    st.markdown("### 📅 Filtro por periodo")
    col1, col2 = st.columns(2)
    fecha_inicio = col1.date_input("Desde", datetime(datetime.now().year, 1, 1))
    fecha_fin = col2.date_input("Hasta", datetime.today())

    def filtrar(df, campo):
        if campo in df.columns:
            df[campo] = pd.to_datetime(df[campo], errors="coerce")
            return df[(df[campo] >= pd.to_datetime(fecha_inicio)) & (df[campo] <= pd.to_datetime(fecha_fin))]
        return df

    df_nc = filtrar(df_nc, "fecha")
    df_ac = filtrar(df_ac, "fecha_inicio")
    df_aud = filtrar(df_aud, "fecha")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("NC Abiertas", len(df_nc[df_nc["estado"] == "Abierta"]) if "estado" in df_nc else 0)
    col2.metric("NC Cerradas", len(df_nc[df_nc["estado"] == "Cerrada"]) if "estado" in df_nc else 0)
    col3.metric("AC Cerradas", len(df_ac[df_ac["estado"] == "Cerrada"]) if "estado" in df_ac else 0)
    col4.metric("Auditorías", len(df_aud))

    # Gráficos nativos
    if "estado" in df_nc.columns:
        st.markdown("#### Distribución de No Conformidades por Estado")
        st.bar_chart(df_nc["estado"].value_counts())

    if "estado" in df_ac.columns:
        st.markdown("#### Distribución de Acciones Correctivas por Estado")
        st.bar_chart(df_ac["estado"].value_counts())

    if "tipo" in df_aud.columns:
        st.markdown("#### Auditorías por Tipo")
        st.bar_chart(df_aud["tipo"].value_counts())

    # Tablas de detalle
    with st.expander("📋 No Conformidades"):
        st.dataframe(df_nc)
    with st.expander("🛠️ Acciones Correctivas"):
        st.dataframe(df_ac)
    with st.expander("📋 Auditorías"):
        st.dataframe(df_aud)
      
