import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 📝 Tareas CRM")
    st.caption("Gestión de tareas comerciales.")
    st.divider()

    rol = session_state.role
    empresa_id = session_state.user.get("empresa_id")

    if rol not in ["admin", "gestor", "comercial"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # Filtrar tareas según rol
    query = supabase.table("crm_tareas").select("*").eq("empresa_id", empresa_id)
    if rol == "comercial":
        comercial_id = session_state.user.get("comercial_id")
        query = query.eq("comercial_id", comercial_id)

    tareas = query.execute().data or []

    if tareas:
        df = pd.DataFrame(tareas)
        st.dataframe(df[["descripcion", "estado", "fecha_vencimiento", "fecha_creacion"]])
    else:
        st.info("No hay tareas registradas.")

    st.divider()
    st.markdown("### ➕ Nueva tarea")
    with st.form("nueva_tarea", clear_on_submit=True):
        descripcion = st.text_area("Descripción *")
        fecha_venc = st.date_input("Fecha de vencimiento", value=datetime.today())
        estado = st.selectbox("Estado", ["Pendiente", "En proceso", "Completada"])
        enviar = st.form_submit_button("Guardar")

    if enviar:
        if not descripcion:
            st.warning("⚠️ La descripción es obligatoria.")
        else:
            try:
                comercial_id = None
                if rol == "comercial":
                    comercial_id = session_state.user.get("comercial_id")
                supabase.table("crm_tareas").insert({
                    "empresa_id": empresa_id,
                    "descripcion": descripcion,
                    "estado": estado,
                    "fecha_vencimiento": fecha_venc.isoformat(),
                    "comercial_id": comercial_id
                }).execute()
                st.success("✅ Tarea creada.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al crear tarea: {e}")
      
