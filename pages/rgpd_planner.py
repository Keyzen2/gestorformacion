import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 🗂️ Planner RGPD")
    st.caption("Tablero de tareas para auditorías, revisiones y formaciones.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    # Estados posibles
    estados = ["Pendiente", "En curso", "Completada"]

    # Cargar tareas
    try:
        tareas = supabase.table("rgpd_tareas").select("*").eq("empresa_id", empresa_id).order("fecha_limite").execute().data or []
        df_tareas = pd.DataFrame(tareas)
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las tareas: {e}")
        df_tareas = pd.DataFrame()

    # Mostrar tablero Kanban
    cols = st.columns(len(estados))
    for col, estado in zip(cols, estados):
        col.subheader(estado)
        if not df_tareas.empty:
            for _, tarea in df_tareas[df_tareas["estado"] == estado].iterrows():
                with col.expander(f"{tarea['titulo']} — {tarea.get('tipo','')}"):
                    st.write(tarea.get("descripcion", ""))
                    st.write(f"**Responsable:** {tarea.get('responsable','')}")
                    st.write(f"**Fecha límite:** {tarea.get('fecha_limite','')}")
                    # Botones para cambiar estado
                    for nuevo_estado in estados:
                        if nuevo_estado != estado:
                            if st.button(f"Mover a {nuevo_estado}", key=f"{tarea['id']}_{nuevo_estado}"):
                                supabase.table("rgpd_tareas").update({"estado": nuevo_estado}).eq("id", tarea["id"]).execute()
                                st.experimental_rerun()
                    # Botón para eliminar
                    if st.button("🗑️ Eliminar tarea", key=f"del_{tarea['id']}"):
                        supabase.table("rgpd_tareas").delete().eq("id", tarea["id"]).execute()
                        st.experimental_rerun()

    st.divider()
    st.markdown("### ➕ Nueva tarea")
    with st.form("nueva_tarea", clear_on_submit=True):
        titulo = st.text_input("Título *")
        descripcion = st.text_area("Descripción")
        tipo = st.selectbox("Tipo", ["Auditoría", "Revisión", "Formación", "Otro"])
        responsable = st.text_input("Responsable")
        fecha_limite = st.date_input("Fecha límite", value=datetime.today())
        enviar = st.form_submit_button("Crear tarea")

    if enviar:
        if not titulo:
            st.warning("⚠️ El título es obligatorio.")
        else:
            try:
                supabase.table("rgpd_tareas").insert({
                    "empresa_id": empresa_id,
                    "titulo": titulo,
                    "descripcion": descripcion,
                    "tipo": tipo,
                    "responsable": responsable,
                    "fecha_limite": fecha_limite.isoformat(),
                    "estado": "Pendiente"
                }).execute()
                st.success("✅ Tarea creada correctamente.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Error al crear la tarea: {e}")
              
