import streamlit as st
import pandas as pd
from utils import validar_dni_cif

def main(supabase, session_state):
    st.subheader("🧾 Participantes")

    # =========================
    # Cargar grupos
    # =========================
    grupos_res = supabase.table("grupos").select("id, codigo_grupo, empresa_id").execute()
    grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data} if grupos_res.data else {}

    # Filtrar grupos para gestor
    if session_state.role == "gestor":
        empresa_id_usuario = session_state.user.get("empresa_id")
        grupos_dict = {codigo: gid for codigo, gid in grupos_dict.items()
                       if any(g["empresa_id"] == empresa_id_usuario and g["id"] == gid for g in grupos_res.data)}

    if not grupos_dict:
        st.warning("No hay grupos disponibles.")
        st.stop()

    # =========================
    # Cargar participantes
    # =========================
    participantes_res = supabase.table("participantes").select("*").execute()
    df_participantes = pd.DataFrame(participantes_res.data) if participantes_res.data else pd.DataFrame()

    # Filtrar participantes para gestor
    if session_state.role == "gestor":
        ids_grupos_permitidos = list(grupos_dict.values())
        df_participantes = df_participantes[df_participantes["grupo_id"].isin(ids_grupos_permitidos)]

    # =========================
    # Mostrar listado
    # =========================
    if not df_participantes.empty:
        grupo_filter = st.selectbox("Filtrar por grupo", ["Todos"] + list(grupos_dict.keys()))
        search_query = st.text_input("🔍 Buscar por nombre o DNI")

        if grupo_filter != "Todos":
            df_participantes = df_participantes[df_participantes["grupo_id"] == grupos_dict[grupo_filter]]
        if search_query:
            df_participantes = df_participantes[
                df_participantes["nombre"].str.contains(search_query, case=False, na=False) |
                df_participantes["dni"].str.contains(search_query, case=False, na=False)
            ]

        st.dataframe(df_participantes)

    # =========================
    # Crear nuevo participante (solo admin)
    # =========================
    if session_state.role == "admin":
        st.markdown("### ➕ Crear Participante")
        with st.form("crear_participante"):
            nombre = st.text_input("Nombre *")
            dni = st.text_input("DNI/NIE/CIF *")
            grupo_nombre = st.selectbox("Grupo", list(grupos_dict.keys()))
            submitted = st.form_submit_button("Crear Participante")

            if submitted:
                if not nombre or not dni or not grupo_nombre:
                    st.error("⚠️ Todos los campos son obligatorios.")
                elif not validar_dni_cif(dni):
                    st.error("⚠️ El DNI/NIE/CIF no es válido.")
                else:
                    try:
                        supabase.table("participantes").insert({
                            "nombre": nombre,
                            "dni": dni,
                            "grupo_id": grupos_dict[grupo_nombre]
                        }).execute()
                        st.success(f"✅ Participante '{nombre}' creado correctamente.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"❌ Error al crear el participante: {str(e)}")
    else:
        st.info("🔒 Solo los administradores pueden dar de alta participantes.")
