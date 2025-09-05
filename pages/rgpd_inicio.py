import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 🛡️ Cumple RGPD")
    st.caption("Diagnóstico inicial y guía de cumplimiento para tu empresa.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    st.markdown("### 📋 Checklist de cumplimiento")
    st.write("Marca lo que ya tienes implementado:")

    with st.form("rgpd_diagnostico"):
        item1 = st.checkbox("Registro de actividades de tratamiento")
        item2 = st.checkbox("Cláusulas informativas en formularios y contratos")
        item3 = st.checkbox("Contratos con encargados del tratamiento")
        item4 = st.checkbox("Procedimiento para atender derechos ARCO")
        item5 = st.checkbox("Medidas técnicas de seguridad (cifrado, backups)")
        item6 = st.checkbox("Canal para reportar brechas de seguridad")

        enviar = st.form_submit_button("Guardar diagnóstico")

    if enviar:
        try:
            supabase.table("rgpd_diagnostico").upsert({
                "empresa_id": empresa_id,
                "registro_tratamiento": item1,
                "clausulas": item2,
                "encargados": item3,
                "derechos": item4,
                "seguridad": item5,
                "canal_brechas": item6,
                "fecha": datetime.utcnow().isoformat()
            }, on_conflict=["empresa_id"]).execute()
            st.success("✅ Diagnóstico guardado.")
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")

    # Semáforo visual
    try:
        diag = supabase.table("rgpd_diagnostico").select("*").eq("empresa_id", empresa_id).execute().data[0]
        cumplidos = sum([
            diag["registro_tratamiento"],
            diag["clausulas"],
            diag["encargados"],
            diag["derechos"],
            diag["seguridad"],
            diag["canal_brechas"]
        ])
        st.markdown("### 🔦 Estado de cumplimiento")
        if cumplidos == 6:
            st.success("🟢 Cumplimiento completo")
        elif cumplidos >= 3:
            st.warning("🟡 Cumplimiento parcial")
        else:
            st.error("🔴 Cumplimiento insuficiente")
    except:
        st.info("ℹ️ Aún no has realizado el diagnóstico.")
