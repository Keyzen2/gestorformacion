import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 🧑‍⚖️ Derechos de los Interesados")
    st.caption("Registra y gestiona las solicitudes de acceso, rectificación, cancelación, oposición y otros derechos.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    st.markdown("### ➕ Registrar nueva solicitud")

    with st.form("nueva_solicitud", clear_on_submit=True):
        nombre = st.text_input("Nombre del solicitante")
        email = st.text_input("Email del solicitante")
        tipo = st.selectbox("Tipo de derecho solicitado", [
            "Acceso", "Rectificación", "Cancelación", "Oposición",
            "Portabilidad", "Limitación", "Supresión"
        ])
        fecha_solicitud = st.date_input("Fecha de solicitud", value=datetime.today())
        estado = st.selectbox("Estado", ["Pendiente", "En proceso", "Resuelta", "Rechazada"])
        observaciones = st.text_area("Observaciones internas")
        enviar = st.form_submit_button("Guardar solicitud")

    if enviar:
        if not nombre or not email:
            st.warning("⚠️ El nombre y el email son obligatorios.")
        else:
            try:
                supabase.table("rgpd_derechos").insert({
                    "empresa_id": empresa_id,
                    "nombre": nombre,
                    "email": email,
                    "tipo": tipo,
                    "fecha_solicitud": fecha_solicitud.isoformat(),
                    "estado": estado,
                    "observaciones": observaciones,
                    "fecha_registro": datetime.utcnow().isoformat()
                }).execute()
                st.success("✅ Solicitud registrada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")

    st.markdown("### 📋 Solicitudes registradas")

    try:
        solicitudes = supabase.table("rgpd_derechos").select("*").eq("empresa_id", empresa_id).execute().data or []
        if solicitudes:
            df = pd.DataFrame(solicitudes)
            df = df[["nombre", "email", "tipo", "fecha_solicitud", "estado", "observaciones"]]
            st.dataframe(df)
            st.download_button("⬇️ Exportar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="derechos_rgpd.csv", mime="text/csv")
        else:
            st.info("No hay solicitudes registradas.")
    except Exception as e:
        st.error(f"❌ Error al cargar solicitudes: {e}")
