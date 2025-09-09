import streamlit as st
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 🛡️ Cumple RGPD")
    st.caption("Diagnóstico inicial y guía de cumplimiento para tu empresa.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    # Cargar diagnóstico previo (si existe)
    try:
        diag_existente = supabase.table("rgpd_diagnostico")\
            .select("*")\
            .eq("empresa_id", empresa_id)\
            .execute().data
        diag_existente = diag_existente[0] if diag_existente else {}
    except Exception:
        diag_existente = {}

    st.markdown("### 📋 Checklist de cumplimiento")
    st.write("Marca lo que ya tienes implementado:")

    with st.form("rgpd_diagnostico"):
        item1 = st.checkbox(
            "Registro de actividades de tratamiento",
            value=diag_existente.get("registro_tratamiento", False)
        )
        item2 = st.checkbox(
            "Cláusulas informativas en formularios y contratos",
            value=diag_existente.get("clausulas", False)
        )
        item3 = st.checkbox(
            "Contratos con encargados del tratamiento",
            value=diag_existente.get("encargados", False)
        )
        item4 = st.checkbox(
            "Procedimiento para atender derechos ARCO",
            value=diag_existente.get("derechos", False)
        )
        item5 = st.checkbox(
            "Medidas técnicas de seguridad (cifrado, backups)",
            value=diag_existente.get("seguridad", False)
        )
        item6 = st.checkbox(
            "Canal para reportar brechas de seguridad",
            value=diag_existente.get("canal_brechas", False)
        )

        enviar = st.form_submit_button("💾 Guardar diagnóstico")

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
        if diag_existente:
            cumplidos = sum([
                bool(diag_existente.get("registro_tratamiento")),
                bool(diag_existente.get("clausulas")),
                bool(diag_existente.get("encargados")),
                bool(diag_existente.get("derechos")),
                bool(diag_existente.get("seguridad")),
                bool(diag_existente.get("canal_brechas"))
            ])
            st.markdown("### 🔦 Estado de cumplimiento")
            if cumplidos == 6:
                st.success("🟢 Cumplimiento completo")
            elif cumplidos >= 3:
                st.warning("🟡 Cumplimiento parcial")
            else:
                st.error("🔴 Cumplimiento insuficiente")
        else:
            st.info("ℹ️ Aún no has realizado el diagnóstico.")
    except Exception as e:
        st.error(f"❌ Error al mostrar el estado: {e}")
        
