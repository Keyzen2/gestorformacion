import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 🚨 Canal de Incidencias")
    st.caption("Registra cualquier brecha de seguridad, error humano o incidente relacionado con datos personales.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    st.markdown("### ➕ Registrar nueva incidencia")

    with st.form("nueva_incidencia", clear_on_submit=True):
        tipo = st.selectbox("Tipo de incidencia", [
            "Brecha de seguridad", "Error humano", "Acceso indebido", "Pérdida de datos", "Otro"
        ])
        descripcion = st.text_area("Descripción del incidente")
        fecha_incidencia = st.date_input("Fecha del incidente", value=datetime.today())
        impacto = st.selectbox("Impacto", ["Alto", "Medio", "Bajo"])
        medidas = st.text_area("Medidas tomadas")
        estado = st.selectbox("Estado", ["Detectado", "Investigando", "Resuelto", "Notificado AEPD"])
        enviar = st.form_submit_button("Guardar incidencia")

    if enviar:
        if not descripcion:
            st.warning("⚠️ La descripción es obligatoria.")
        else:
            try:
                supabase.table("rgpd_incidencias").insert({
                    "empresa_id": empresa_id,
                    "tipo": tipo,
                    "descripcion": descripcion,
                    "fecha_incidencia": fecha_incidencia.isoformat(),
                    "impacto": impacto,
                    "medidas": medidas,
                    "estado": estado,
                    "fecha_registro": datetime.utcnow().isoformat()
                }).execute()
                st.success("✅ Incidencia registrada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")

    st.markdown("### 📋 Incidencias registradas")

    try:
        incidencias = supabase.table("rgpd_incidencias").select("*").eq("empresa_id", empresa_id).execute().data or []
        if incidencias:
            df = pd.DataFrame(incidencias)
            df = df[["tipo", "descripcion", "fecha_incidencia", "impacto", "estado", "medidas"]]
            st.dataframe(df)
            st.download_button("⬇️ Exportar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="incidencias_rgpd.csv", mime="text/csv")
        else:
            st.info("No hay incidencias registradas.")
    except Exception as e:
        st.error(f"❌ Error al cargar incidencias: {e}")
