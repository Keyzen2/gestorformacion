import streamlit as st
import pandas as pd
from datetime import datetime, date

def render(supabase, session_state):
    st.markdown("## 🗂️ Planner RGPD")
    st.caption("Tablero de tareas para auditorías, revisiones y formaciones.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    # Estados posibles y colores
    estados = {
        "Pendiente": "🔴",
        "En curso": "🟡",
        "Completada": "🟢"
    }

    # Cargar tareas
    try:
        tareas = supabase.table("rgpd_tareas").select("*").eq("empresa_id", empresa_id).order("fecha_limite").execute().data or []
        df_tareas = pd.DataFrame(tareas)
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las tareas: {e}")
        df_tareas = pd.DataFrame()

    # Filtros
    st.markdown("### 🔍 Filtros")
    col_f1, col_f2 = st.columns(2)
    filtro_tipo = col_f1.selectbox("Filtrar por tipo", ["Todos"] + sorted(df_tareas["tipo"].dropna().unique()) if not df_tareas.empty else ["Todos"])
    filtro_resp = col_f2.selectbox("Filtrar por responsable", ["Todos"] + sorted(df_tareas["responsable"].dropna().unique()) if not df_tareas.empty else ["Todos"])

    if filtro_tipo != "Todos":
        df_tareas = df_tareas[df_tareas["tipo"] == filtro_tipo]
    if filtro_resp != "Todos":
        df_tareas = df_tareas[df_tareas["responsable"] == filtro_resp]

    # Contadores por estado
    st.markdown("### 📊 Resumen de tareas")
    cols_resumen = st.columns(len(estados))
    for col, (estado, icono) in zip(cols_resumen, estados.items()):
        total = len(df_tareas[df_tareas["estado"] == estado]) if not df_tareas.empty else 0
        col.metric(f"{icono} {estado}", total)

    st.divider()

    # Mostrar tablero Kanban
    cols = st.columns(len(estados))
    for col, (estado, icono) in zip(cols, estados.items()):
        col.subheader(f"{icono} {estado}")
        if not df_tareas.empty:
            for _, tarea in df_tareas[df_tareas["estado"] == estado].iterrows():
                vencida = tarea.get("fecha_limite") and pd.to_datetime(tarea["fecha_limite"]).date() < date.today() and estado != "Completada"
                color_alerta = "⚠️ " if vencida else ""
                with col.expander(f"{color_alerta}{tarea['titulo']} — {tarea.get('tipo','')}"):
                    st.write(tarea.get("descripcion", ""))
                    st.write(f"**Responsable:** {tarea.get('responsable','')}")
                    st.write(f"**Fecha límite:** {tarea.get('fecha_limite','')}")
                    
                    # Histórico de cambios
                    try:
                        historial = supabase.table("rgpd_tareas_historial").select("*").eq("tarea_id", tarea["id"]).order("fecha_cambio", desc=True).execute().data or []
                        if historial:
                            st.markdown("**Histórico de cambios:**")
                            for h in historial:
                                st.write(f"- {h['fecha_cambio']}: {h['accion']} por {h.get('usuario','')}")
                    except:
                        pass

                    # Botones para cambiar estado
                    for nuevo_estado in estados.keys():
                        if nuevo_estado != estado:
                            if st.button(f"Mover a {nuevo_estado}", key=f"{tarea['id']}_{nuevo_estado}"):
                                supabase.table("rgpd_tareas").update({"estado": nuevo_estado}).eq("id", tarea["id"]).execute()
                                supabase.table("rgpd_tareas_historial").insert({
                                    "tarea_id": tarea["id"],
                                    "accion": f"Cambio de estado a {nuevo_estado}",
                                    "fecha_cambio": datetime.utcnow().isoformat(),
                                    "usuario": session_state.user.get("email")
                                }).execute()
                                st.experimental_rerun()

                    # Botón para eliminar
                    if st.button("🗑️ Eliminar tarea", key=f"del_{tarea['id']}"):
                        supabase.table("rgpd_tareas").delete().eq("id", tarea["id"]).execute()
                        supabase.table("rgpd_tareas_historial").insert({
                            "tarea_id": tarea["id"],
                            "accion": "Eliminada",
                            "fecha_cambio": datetime.utcnow().isoformat(),
                            "usuario": session_state.user.get("email")
                        }).execute()
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
                res = supabase.table("rgpd_tareas").insert({
                    "empresa_id": empresa_id,
                    "titulo": titulo,
                    "descripcion": descripcion,
                    "tipo": tipo,
                    "responsable": responsable,
                    "fecha_limite": fecha_limite.isoformat(),
                    "estado": "Pendiente"
                }).execute()
                if res.data:
                    supabase.table("rgpd_tareas_historial").insert({
                        "tarea_id": res.data[0]["id"],
                        "accion": "Creada",
                        "fecha_cambio": datetime.utcnow().isoformat(),
                        "usuario": session_state.user.get("email")
                    }).execute()
                st.success("✅ Tarea creada correctamente.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Error al crear la tarea: {e}")
                        
