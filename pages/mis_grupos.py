# pages/mis_grupos.py
import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("🎓 Mis Diplomas y Grupos")

    email = session_state.user.get("email")
    if not email:
        st.warning("No se ha detectado tu sesión correctamente.")
        return

    try:
        alumno_res = supabase.table("participantes").select("id, nombre, grupo_id").eq("email", email).execute()
        alumno = alumno_res.data[0] if alumno_res.data else None
        if not alumno:
            st.info("No estás registrado como participante.")
            return

        grupo_res = supabase.table("grupos").select("*").eq("id", alumno["grupo_id"]).execute()
        grupo = grupo_res.data[0] if grupo_res.data else None

        diplomas_res = supabase.table("diplomas").select("*").eq("participante_id", alumno["id"]).execute()
        diplomas = diplomas_res.data or []

        st.markdown(f"**Nombre:** {alumno['nombre']}")
        if grupo:
            st.markdown(f"**Grupo:** {grupo['codigo_grupo']}")
            st.markdown(f"**Localidad:** {grupo.get('localidad','')}")

        if diplomas:
            st.markdown("### 🏅 Diplomas disponibles")
            for d in diplomas:
                st.markdown(f"- [Diploma]({d['url']}) subido el {d['fecha_subida']}")
        else:
            st.info("No tienes diplomas registrados aún.")

    except Exception as e:
        st.error(f"❌ Error al cargar tus datos: {e}")
