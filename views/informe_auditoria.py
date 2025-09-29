import streamlit as st
import pandas as pd
from datetime import datetime
from utils import generar_pdf  # Asegúrate de tener esta función en utils.py

def render(supabase, session_state):
    st.subheader("📑 Informe de Auditoría ISO 9001")
    st.caption("Generación de informe consolidado para presentar en auditorías internas o externas.")
    st.divider()

    # 🔒 Protección por rol
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # =========================
    # Selección de empresa (solo admin)
    # =========================
    empresa_id = None
    empresa_nombre = "Global"
    if session_state.role == "gestor":
        empresa_id = session_state.user.get("empresa_id")
    else:
        empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
        empresa_sel = st.selectbox("Selecciona empresa", list(empresas_dict.keys()))
        empresa_id = empresas_dict[empresa_sel]
        empresa_nombre = empresa_sel

    # =========================
    # Filtro por fechas
    # =========================
    col1, col2 = st.columns(2)
    fecha_inicio = col1.date_input("Desde", datetime(datetime.now().year, 1, 1))
    fecha_fin = col2.date_input("Hasta", datetime.today())

    def filtrar(df, campo):
        if campo in df.columns:
            df[campo] = pd.to_datetime(df[campo], errors="coerce")
            return df[(df[campo] >= pd.to_datetime(fecha_inicio)) & (df[campo] <= pd.to_datetime(fecha_fin))]
        return df

    # =========================
    # Cargar y filtrar datos
    # =========================
    def cargar(tabla):
        query = supabase.table(tabla).select("*")
        if empresa_id:
            query = query.eq("empresa_id", empresa_id)
        return pd.DataFrame(query.execute().data or [])

    df_nc = filtrar(cargar("no_conformidades"), "fecha_detectada")
    df_ac = filtrar(cargar("acciones_correctivas"), "fecha_inicio")
    df_aud = filtrar(cargar("auditorias"), "fecha")
    df_obj = cargar("objetivos_calidad")
    df_seg = cargar("seguimiento_objetivos")

    # =========================
    # KPIs
    # =========================
    st.markdown("### 📊 Resumen de Indicadores")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("NC Abiertas", len(df_nc[df_nc["estado"] == "Abierta"]) if "estado" in df_nc else 0)
    col2.metric("NC Cerradas", len(df_nc[df_nc["estado"] == "Cerrada"]) if "estado" in df_nc else 0)
    col3.metric("AC Cerradas", len(df_ac[df_ac["estado"] == "Cerrada"]) if "estado" in df_ac else 0)
    col4.metric("Auditorías", len(df_aud))

    # =========================
    # Tablas de detalle
    # =========================
    with st.expander("📋 No Conformidades"):
        st.dataframe(df_nc)
    with st.expander("🛠️ Acciones Correctivas"):
        st.dataframe(df_ac)
    with st.expander("📋 Auditorías"):
        st.dataframe(df_aud)
    with st.expander("🎯 Objetivos de Calidad"):
        st.dataframe(df_obj)
    with st.expander("📈 Seguimiento de Objetivos"):
        st.dataframe(df_seg)

    # =========================
    # Generar PDF
    # =========================
    st.markdown("### 🖨️ Generar Informe PDF")
    if st.button("📄 Generar PDF de Auditoría"):
        contenido = f"""
        Informe de Auditoría ISO 9001
        Empresa: {empresa_nombre}
        Periodo: {fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}

        Indicadores:
        - No Conformidades Abiertas: {len(df_nc[df_nc["estado"] == "Abierta"]) if "estado" in df_nc else 0}
        - No Conformidades Cerradas: {len(df_nc[df_nc["estado"] == "Cerrada"]) if "estado" in df_nc else 0}
        - Acciones Correctivas Cerradas: {len(df_ac[df_ac["estado"] == "Cerrada"]) if "estado" in df_ac else 0}
        - Auditorías Realizadas: {len(df_aud)}

        Objetivos de Calidad:
        """
        for _, obj in df_obj.iterrows():
            segs = df_seg[df_seg["objetivo_id"] == obj["id"]]
            valor = segs.sort_values("fecha", ascending=False)["valor_real"].iloc[0] if not segs.empty else "Sin seguimiento"
            contenido += f"\n- {obj['nombre']} → Meta: {obj['meta']} → Último valor: {valor}"

        pdf_buffer = generar_pdf(f"informe_auditoria_{empresa_nombre}.pdf", contenido=contenido)
        st.download_button("⬇️ Descargar Informe PDF", pdf_buffer, file_name=f"informe_auditoria_{empresa_nombre}.pdf")
