import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 📄 Cláusulas y Consentimientos")
    st.caption("Gestiona tus textos legales y asegúrate de que estén actualizados.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    st.markdown("### ➕ Registrar nueva cláusula")

    with st.form("nueva_clausula", clear_on_submit=True):
        tipo = st.selectbox("Tipo de cláusula", ["Formulario web", "Contrato", "Aviso legal", "Otro"])
        ubicacion = st.text_input("Dónde se aplica (ej. página de contacto, contrato laboral)")
        version = st.text_input("Versión o referencia (ej. v1.2, 2025-09)")
        texto = st.text_area("Texto legal completo")
        enlace = st.text_input("Enlace público (si aplica)")
        enviar = st.form_submit_button("Guardar cláusula")

    if enviar:
        if not texto or not ubicacion:
            st.warning("⚠️ El texto legal y la ubicación son obligatorios.")
        else:
            try:
                supabase.table("rgpd_clausulas").insert({
                    "empresa_id": empresa_id,
                    "tipo": tipo,
                    "ubicacion": ubicacion,
                    "version": version,
                    "texto": texto,
                    "enlace": enlace,
                    "fecha": datetime.utcnow().isoformat()
                }).execute()
                st.success("✅ Cláusula registrada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")

    st.markdown("### 📋 Cláusulas registradas")

    try:
        clausulas = supabase.table("rgpd_clausulas").select("*").eq("empresa_id", empresa_id).execute().data or []
        if clausulas:
            df = pd.DataFrame(clausulas)
            df = df[["tipo", "ubicacion", "version", "fecha", "enlace"]]
            st.dataframe(df)
            st.download_button("⬇️ Exportar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="clausulas_rgpd.csv", mime="text/csv")
        else:
            st.info("Aún no has registrado ninguna cláusula.")
    except Exception as e:
        st.error(f"❌ Error al cargar cláusulas: {e}")
