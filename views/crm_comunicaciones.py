import streamlit as st
import pandas as pd
from datetime import datetime

def render(supabase, session_state):
    st.markdown("## 📬 Comunicaciones CRM")
    st.caption("Registro de interacciones con clientes.")
    st.divider()

    rol = session_state.role
    empresa_id = session_state.user.get("empresa_id")

    if rol not in ["admin", "gestor", "comercial"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # Filtrar comunicaciones según rol
    query = supabase.table("crm_comunicaciones").select("*").eq("empresa_id", empresa_id)
    if rol == "comercial":
        comercial_id = session_state.user.get("comercial_id")
        query = query.eq("comercial_id", comercial_id)

    comunicaciones = query.execute().data or []

    if comunicaciones:
        df = pd.DataFrame(comunicaciones)
        st.dataframe(df[["tipo", "asunto", "fecha", "notas"]])
    else:
        st.info("No hay comunicaciones registradas.")

    st.divider()
    st.markdown("### ➕ Nueva comunicación")
    with st.form("nueva_comunicacion", clear_on_submit=True):
        tipo = st.selectbox("Tipo", ["Email", "Llamada", "Reunión"])
        asunto = st.text_input("Asunto")
        fecha = st.date_input("Fecha", value=datetime.today())
        notas = st.text_area("Notas")
        enviar = st.form_submit_button("Guardar")

    if enviar:
        try:
            comercial_id = None
            if rol == "comercial":
                comercial_id = session_state.user.get("comercial_id")
            supabase.table("crm_comunicaciones").insert({
                "empresa_id": empresa_id,
                "tipo": tipo,
                "asunto": asunto,
                "fecha": fecha.isoformat(),
                "notas": notas,
                "comercial_id": comercial_id
            }).execute()
            st.success("✅ Comunicación registrada.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al registrar comunicación: {e}")
          
