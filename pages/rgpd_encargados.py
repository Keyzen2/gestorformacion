import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 🤝 Encargados del Tratamiento")
    st.caption("Registra los proveedores que acceden a datos personales y vincula sus contratos.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    st.markdown("### ➕ Añadir nuevo encargado")

    with st.form("nuevo_encargado", clear_on_submit=True):
        nombre = st.text_input("Nombre del proveedor o encargado")
        servicio = st.text_input("Tipo de servicio prestado (ej. gestoría, hosting, software)")
        contrato_url = st.text_input("Enlace al contrato firmado (PDF o documento)")
        fecha_contrato = st.date_input("Fecha de firma del contrato", value=datetime.today())
        enviar = st.form_submit_button("Guardar encargado")

    if enviar:
        if not nombre or not servicio:
            st.warning("⚠️ El nombre y el tipo de servicio son obligatorios.")
        else:
            try:
                supabase.table("rgpd_encargados").insert({
                    "empresa_id": empresa_id,
                    "nombre": nombre,
                    "servicio": servicio,
                    "contrato_url": contrato_url,
                    "fecha_contrato": fecha_contrato.isoformat(),
                    "fecha_registro": datetime.utcnow().isoformat()
                }).execute()
                st.success("✅ Encargado registrado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")

    st.markdown("### 📋 Encargados registrados")

    try:
        encargados = supabase.table("rgpd_encargados").select("*").eq("empresa_id", empresa_id).execute().data or []
        if encargados:
            df = pd.DataFrame(encargados)
            df = df[["nombre", "servicio", "fecha_contrato", "contrato_url"]]
            st.dataframe(df)
            st.download_button("⬇️ Exportar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="encargados_rgpd.csv", mime="text/csv")
        else:
            st.info("Aún no has registrado ningún encargado.")
    except Exception as e:
        st.error(f"❌ Error al cargar encargados: {e}")
