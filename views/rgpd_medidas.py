import streamlit as st
import pandas as pd
from datetime import datetime

def render(supabase, session_state):
    st.markdown("## 🔐 Medidas Técnicas y Organizativas")
    st.caption("Registra las acciones de seguridad que protegen los datos personales en tu empresa.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    st.markdown("### ✅ Checklist de medidas aplicadas")

    with st.form("medidas_seguridad", clear_on_submit=True):
        cifrado = st.checkbox("Cifrado de datos en tránsito y en reposo")
        backups = st.checkbox("Copias de seguridad periódicas")
        acceso = st.checkbox("Control de acceso por roles")
        antivirus = st.checkbox("Antivirus y protección contra malware")
        formacion = st.checkbox("Formación interna sobre protección de datos")
        registro = st.checkbox("Registro de accesos y modificaciones")
        enviar = st.form_submit_button("Guardar medidas")

    if enviar:
        try:
            supabase.table("rgpd_medidas").upsert({
                "empresa_id": empresa_id,
                "cifrado": cifrado,
                "backups": backups,
                "acceso": acceso,
                "antivirus": antivirus,
                "formacion": formacion,
                "registro": registro,
                "fecha": datetime.utcnow().isoformat()
            }, on_conflict=["empresa_id"]).execute()
            st.success("✅ Medidas guardadas correctamente.")
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")

    st.markdown("### 🔦 Estado de cumplimiento")

    try:
        medidas = supabase.table("rgpd_medidas").select("*").eq("empresa_id", empresa_id).execute().data[0]
        aplicadas = sum([
            medidas["cifrado"],
            medidas["backups"],
            medidas["acceso"],
            medidas["antivirus"],
            medidas["formacion"],
            medidas["registro"]
        ])
        if aplicadas == 6:
            st.success("🟢 Seguridad completa")
        elif aplicadas >= 3:
            st.warning("🟡 Seguridad parcial")
        else:
            st.error("🔴 Seguridad insuficiente")
    except:
        st.info("ℹ️ Aún no has registrado tus medidas de seguridad.")
