import streamlit as st
import pandas as pd
from datetime import datetime

def render(supabase, session_state):
    st.markdown("## 📘 Registro de Actividades de Tratamiento")
    st.caption("Documenta cada tratamiento de datos personales que realiza tu empresa.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    st.markdown("### ➕ Añadir nuevo tratamiento")

    with st.form("nuevo_tratamiento", clear_on_submit=True):
        actividad = st.text_input("Nombre del tratamiento (ej. Gestión de nóminas)")
        finalidad = st.text_area("Finalidad del tratamiento")
        tipo_datos = st.text_input("Tipo de datos tratados (ej. nombre, DNI, salud)")
        base_legal = st.selectbox("Base legal", ["Consentimiento", "Contrato", "Obligación legal", "Interés legítimo"])
        responsable = st.text_input("Responsable interno del tratamiento")
        encargado = st.text_input("Encargado externo (si aplica)")
        enviar = st.form_submit_button("Guardar tratamiento")

    if enviar:
        if not actividad or not finalidad or not tipo_datos:
            st.warning("⚠️ Los campos principales son obligatorios.")
        else:
            try:
                supabase.table("rgpd_tratamientos").insert({
                    "empresa_id": empresa_id,
                    "actividad": actividad,
                    "finalidad": finalidad,
                    "tipo_datos": tipo_datos,
                    "base_legal": base_legal,
                    "responsable": responsable,
                    "encargado": encargado,
                    "fecha": datetime.utcnow().isoformat()
                }).execute()
                st.success("✅ Tratamiento registrado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")

    st.markdown("### 📋 Tratamientos registrados")

    try:
        tratamientos = supabase.table("rgpd_tratamientos").select("*").eq("empresa_id", empresa_id).execute().data or []
        if tratamientos:
            df = pd.DataFrame(tratamientos)
            df = df[["actividad", "finalidad", "tipo_datos", "base_legal", "responsable", "encargado", "fecha"]]
            st.dataframe(df)
            st.download_button("⬇️ Exportar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="tratamientos_rgpd.csv", mime="text/csv")
        else:
            st.info("Aún no has registrado ningún tratamiento.")
    except Exception as e:
        st.error(f"❌ Error al cargar tratamientos: {e}")
