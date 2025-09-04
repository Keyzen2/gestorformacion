import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("🎓 Mis Grupos y Diplomas")

    # Validar rol
    if session_state.role != "alumno":
        st.warning("🔒 Solo los participantes pueden acceder a esta vista.")
        st.stop()

    # Obtener email del usuario logueado
    email_usuario = session_state.user.get("email")
    if not email_usuario:
        st.error("❌ No se ha encontrado tu email de usuario.")
        st.stop()

    # Buscar participante vinculado
    res = supabase.table("participantes").select("id, nombre").eq("email", email_usuario).execute()
    if not res.data:
        st.error("❌ No se ha encontrado tu registro como participante.")
        st.stop()

    participante_id = res.data[0]["id"]
    nombre_participante = res.data[0]["nombre"]

    st.markdown(f"👋 Hola, **{nombre_participante}**. Aquí están tus grupos y diplomas disponibles.")

    # =========================
    # Buscar grupos del participante
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

        # Buscar diploma real
        diploma = supabase.table("diplomas").select("*").eq("grupo_id", gid).eq("participante_id", participante_id).execute().data
        if diploma:
            st.markdown(f"📥 [Descargar diploma]({diploma[0]['url']})")
        else:
            st.info("⏳ Diploma aún no disponible para este grupo.")
            
