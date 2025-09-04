import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("🎓 Mis Grupos y Diplomas")

    # Validar rol
    if session_state.role != "alumno":
        st.warning("🔒 Solo los participantes pueden acceder a esta vista.")
        st.stop()

    participante_id = session_state.user.get("id")
    if not participante_id:
        st.error("❌ No se ha encontrado tu identificador como participante.")
        st.stop()

    # =========================
    # Cargar grupos del participante
    # =========================
    grupos_res = supabase.table("participantes").select("grupo_id").eq("id", participante_id).execute()
    grupo_ids = [g["grupo_id"] for g in grupos_res.data] if grupos_res.data else []

    if not grupo_ids:
        st.info("ℹ️ No estás inscrito en ningún grupo actualmente.")
        st.stop()

    # =========================
    # Mostrar grupos y diplomas
    # =========================
    for gid in grupo_ids:
        grupo = supabase.table("grupos").select("*").eq("id", gid).execute().data
        if not grupo:
            continue
        grupo = grupo[0]

        st.markdown(f"### 📘 Grupo: {grupo['codigo_grupo']}")
        st.write(f"**Acción Formativa:** {grupo.get('accion_formativa_id', '')}")
        st.write(f"**Fechas:** {grupo.get('fecha_inicio', '')} → {grupo.get('fecha_fin', '')}")
        st.write(f"**Empresa:** {grupo.get('empresa_id', '')}")

        # Buscar diploma
        diploma = supabase.table("diplomas").select("*").eq("grupo_id", gid).eq("participante_id", participante_id).execute().data
        if diploma:
            st.markdown(f"📥 [Descargar diploma]({diploma[0]['url']})")
        else:
            st.info("⏳ Diploma aún no disponible para este grupo.")
          
