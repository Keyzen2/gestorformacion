import streamlit as st
import pandas as pd
from datetime import datetime

def render(supabase, session_state):
    st.markdown("## 🧠 Evaluación de Impacto en Protección de Datos (EIPD)")
    st.caption("Determina si tu empresa necesita una EIPD y documenta el análisis.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    st.markdown("### ❓ ¿Necesitas una EIPD?")
    st.write("Responde a las siguientes preguntas para saber si estás obligado a realizarla:")

    with st.form("evaluacion_eipd", clear_on_submit=True):
        p1 = st.checkbox("¿Tratas datos sensibles (salud, ideología, orientación sexual, etc.)?")
        p2 = st.checkbox("¿Realizas seguimiento sistemático de personas (ej. geolocalización, videovigilancia)?")
        p3 = st.checkbox("¿Tratas datos a gran escala?")
        p4 = st.checkbox("¿Utilizas tecnologías innovadoras para tratar datos personales?")
        p5 = st.checkbox("¿Combinas datos de distintas fuentes para crear perfiles?")
        p6 = st.checkbox("¿Tratas datos de menores o colectivos vulnerables?")
        enviar = st.form_submit_button("Evaluar")

    if enviar:
        try:
            supabase.table("rgpd_evaluacion").upsert({
                "empresa_id": empresa_id,
                "datos_sensibles": p1,
                "seguimiento": p2,
                "gran_escala": p3,
                "tecnologia": p4,
                "perfiles": p5,
                "menores": p6,
                "fecha": datetime.utcnow().isoformat()
            }, on_conflict=["empresa_id"]).execute()
            st.success("✅ Evaluación guardada.")
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")

    st.markdown("### 📊 Resultado")

    try:
        eval = supabase.table("rgpd_evaluacion").select("*").eq("empresa_id", empresa_id).execute().data[0]
        criterios = sum([
            eval["datos_sensibles"],
            eval["seguimiento"],
            eval["gran_escala"],
            eval["tecnologia"],
            eval["perfiles"],
            eval["menores"]
        ])
        if criterios >= 2:
            st.error("🔴 Debes realizar una Evaluación de Impacto (EIPD).")
            st.markdown("Puedes documentarla en la siguiente sección.")
        elif criterios == 1:
            st.warning("🟡 Podrías necesitar una EIPD. Revisa con tu DPD.")
        else:
            st.success("🟢 No parece necesario realizar una EIPD.")
    except:
        st.info("ℹ️ Aún no has completado la evaluación.")

    st.divider()
    st.markdown("### 📝 Documentar la EIPD (si aplica)")

    with st.form("documentar_eipd", clear_on_submit=True):
        descripcion = st.text_area("Descripción del tratamiento y riesgos identificados")
        medidas = st.text_area("Medidas adoptadas para mitigar los riesgos")
        responsable = st.text_input("Responsable de la evaluación")
        enviar_doc = st.form_submit_button("Guardar documentación")

    if enviar_doc:
        try:
            supabase.table("rgpd_eipd_documentacion").upsert({
                "empresa_id": empresa_id,
                "descripcion": descripcion,
                "medidas": medidas,
                "responsable": responsable,
                "fecha": datetime.utcnow().isoformat()
            }, on_conflict=["empresa_id"]).execute()
            st.success("✅ Documentación de EIPD guardada.")
        except Exception as e:
            st.error(f"❌ Error al guardar la documentación: {e}")
