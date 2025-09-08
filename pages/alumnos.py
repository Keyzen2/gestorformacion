import streamlit as st
import pandas as pd
from utils import get_ajustes_app

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
    # Cargar datos de grupos
    # =========================
    grupos_data = []
    for gid in grupo_ids:
        grupo = supabase.table("grupos").select("*").eq("id", gid).execute().data
        if grupo:
            grupos_data.append(grupo[0])

    if not grupos_data:
        st.info("ℹ️ No se encontraron datos de tus grupos.")
        st.stop()

    df_grupos = pd.DataFrame(grupos_data)
    df_grupos["fecha_inicio"] = pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce")
    df_grupos["fecha_fin"] = pd.to_datetime(df_grupos["fecha_fin"], errors="coerce")
    df_grupos = df_grupos.sort_values("fecha_inicio")

    # =========================
    # Filtro visual
    # =========================
    filtro = st.text_input("🔍 Filtrar por código de grupo o empresa")
    if filtro:
        df_grupos = df_grupos[
            df_grupos["codigo_grupo"].str.contains(filtro, case=False, na=False) |
            df_grupos["empresa_id"].astype(str).str.contains(filtro, case=False, na=False)
        ]

    # =========================
    # Mostrar grupos con diplomas
    # =========================
    for _, grupo in df_grupos.iterrows():
        with st.expander(f"📘 Grupo: {grupo['codigo_grupo']} ({grupo['fecha_inicio'].date()} → {grupo['fecha_fin'].date()})"):
            st.write(f"**Acción Formativa:** {grupo.get('accion_formativa_id', '—')}")
            st.write(f"**Empresa:** {grupo.get('empresa_id', '—')}")
            st.write(f"**Fechas:** {grupo['fecha_inicio'].date()} → {grupo['fecha_fin'].date()}")

            diploma = supabase.table("diplomas").select("*").eq("grupo_id", grupo["id"]).eq("participante_id", participante_id).execute().data
            if diploma:
                st.markdown(f"📥 [Descargar diploma]({diploma[0]['url']})")
            else:
                st.info("⏳ Diploma aún no disponible para este grupo.")
                
