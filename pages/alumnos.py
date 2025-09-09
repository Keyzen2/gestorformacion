import streamlit as st
import pandas as pd
from datetime import datetime
from utils import get_ajustes_app

def main(supabase, session_state):
    # Cargar ajustes de la app
    ajustes = get_ajustes_app(supabase)
    titulo = ajustes.get("titulo_alumno", "🎓 Mis Grupos y Diplomas")
    mensaje = ajustes.get("mensaje_bienvenida_alumno", "")

    # Encabezado y bienvenida personalizada
    st.subheader(titulo)
    if mensaje:
        st.info(mensaje)

    # Sólo rol alumno
    if session_state.role != "alumno":
        st.warning("🔒 Solo los participantes pueden acceder a esta vista.")
        st.stop()

    # Email del usuario logueado
    email_usuario = session_state.user.get("email")
    if not email_usuario:
        st.error("❌ No se ha encontrado tu email de usuario.")
        st.stop()

    # Buscar registro de participante
    p_res = (
        supabase
        .table("participantes")
        .select("id,nombre")
        .eq("email", email_usuario)
        .execute()
    )
    if not p_res.data:
        st.error("❌ No se ha encontrado tu registro como participante.")
        st.stop()

    participante_id     = p_res.data[0]["id"]
    nombre_participante = p_res.data[0]["nombre"]

    # Mensaje de saludo con el nombre
    saludo_plantilla = ajustes.get("saludo_alumno", "👋 Hola, **{nombre}**.")
    st.markdown(saludo_plantilla.format(nombre=nombre_participante))

    # Recuperar grupo_id(s) del participante
    grp_res = (
        supabase
        .table("participantes")
        .select("grupo_id")
        .eq("id", participante_id)
        .execute()
    )
    grupo_ids = [g["grupo_id"] for g in grp_res.data or []]
    if not grupo_ids:
        st.info("ℹ️ No estás inscrito en ningún grupo actualmente.")
        st.stop()

    # Cargar datos de cada grupo
    grupos_data = []
    for gid in grupo_ids:
        g = supabase.table("grupos").select("*").eq("id", gid).execute().data
        if g:
            grupos_data.append(g[0])

    if not grupos_data:
        st.info("ℹ️ No se encontraron datos de tus grupos.")
        st.stop()

    # DataFrame y formateo de fechas
    df = pd.DataFrame(grupos_data)
    df["fecha_inicio"] = pd.to_datetime(df["fecha_inicio"], errors="coerce")
    df["fecha_fin"]    = pd.to_datetime(df["fecha_fin"],    errors="coerce")
    df = df.sort_values("fecha_inicio")

    # Filtro por código de grupo o empresa
    filtro = st.text_input("🔍 Filtrar por código de grupo o empresa")
    if filtro:
        mask = (
            df["codigo_grupo"].str.contains(filtro, case=False, na=False)
            | df["empresa_id"].astype(str).str.contains(filtro, case=False, na=False)
        )
        df = df[mask]

    # Mostrar cada grupo y diploma
    for _, grupo in df.iterrows():
        inicio = grupo["fecha_inicio"].date() if pd.notna(grupo["fecha_inicio"]) else "—"
        fin    = grupo["fecha_fin"].date()    if pd.notna(grupo["fecha_fin"])    else "—"
        header = f"📘 Grupo: {grupo['codigo_grupo']} ({inicio} → {fin})"
        with st.expander(header):
            st.write(f"**Acción Formativa ID:** {grupo.get('accion_formativa_id','—')}")
            st.write(f"**Empresa ID:** {grupo.get('empresa_id','—')}")
            st.write(f"**Fechas:** {inicio} → {fin}")

            # Comprobar diploma
            dip_res = (
                supabase
                .table("diplomas")
                .select("url")
                .eq("grupo_id", grupo["id"])
                .eq("participante_id", participante_id)
                .execute()
            )
            if dip_res.data:
                url = dip_res.data[0].get("url")
                label = ajustes.get("texto_descarga_diploma", "📥 Descargar diploma")
                st.markdown(f"{label} — [Click aquí]({url})")
            else:
                st.info(ajustes.get(
                    "texto_espera_diploma",
                    "⏳ Diploma aún no disponible para este grupo."
                ))
                
