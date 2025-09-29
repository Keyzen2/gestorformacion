import streamlit as st
import pandas as pd
from utils import get_ajustes_app

def main(supabase, session_state):
    # Cargar ajustes de la app
    ajustes = get_ajustes_app(supabase)
    titulo = ajustes.get("titulo_alumno", "🎓 Mis Grupos y Diplomas")
    mensaje = ajustes.get("mensaje_bienvenida_alumno", "")

    st.subheader(titulo)
    if mensaje:
        st.info(mensaje)

    # Solo rol alumno
    if session_state.role != "alumno":
        st.warning("🔒 Solo los participantes pueden acceder a esta vista.")
        st.stop()

    email_usuario = session_state.user.get("email")
    if not email_usuario:
        st.error("❌ No se ha encontrado tu email de usuario.")
        st.stop()

    # Obtener participante y grupos en una sola consulta
    p_res = supabase.table("participantes").select("id,nombre,grupo_id").eq("email", email_usuario).execute()
    if not p_res.data:
        st.error("❌ No se ha encontrado tu registro como participante.")
        st.stop()

    participante_id = p_res.data[0]["id"]
    nombre_participante = p_res.data[0]["nombre"]
    grupo_ids = list({p["grupo_id"] for p in p_res.data if p.get("grupo_id")})

    saludo_plantilla = ajustes.get("saludo_alumno", "👋 Hola, **{nombre}**.")
    st.markdown(saludo_plantilla.format(nombre=nombre_participante))

    if not grupo_ids:
        st.info("ℹ️ No estás inscrito en ningún grupo actualmente.")
        st.stop()

    # Cargar todos los grupos en una sola consulta
    grupos_res = supabase.table("grupos").select("*").in_("id", grupo_ids).execute()
    grupos_data = grupos_res.data or []
    if not grupos_data:
        st.info("ℹ️ No se encontraron datos de tus grupos.")
        st.stop()

    df = pd.DataFrame(grupos_data)
    df["fecha_inicio"] = pd.to_datetime(df["fecha_inicio"], errors="coerce")
    df["fecha_fin"] = pd.to_datetime(df["fecha_fin"], errors="coerce")
    df = df.sort_values("fecha_inicio")

    # Filtro
    filtro = st.text_input("🔍 Filtrar por código de grupo o empresa")
    if filtro:
        mask = (
            df["codigo_grupo"].str.contains(filtro, case=False, na=False)
            | df["empresa_id"].astype(str).str.contains(filtro, case=False, na=False)
        )
        df = df[mask]

    # Cargar todos los diplomas del participante en una sola consulta
    diplomas_res = supabase.table("diplomas").select("grupo_id,url").eq("participante_id", participante_id).execute()
    diplomas_dict = {d["grupo_id"]: d["url"] for d in (diplomas_res.data or [])}

    # Mostrar grupos y diplomas
    for _, grupo in df.iterrows():
        inicio = grupo["fecha_inicio"].strftime("%d/%m/%Y") if pd.notna(grupo["fecha_inicio"]) else "—"
        fin = grupo["fecha_fin"].strftime("%d/%m/%Y") if pd.notna(grupo["fecha_fin"]) else "—"
        header = f"📘 Grupo: {grupo['codigo_grupo']} ({inicio} → {fin})"
        with st.expander(header):
            st.write(f"**Acción Formativa ID:** {grupo.get('accion_formativa_id','—')}")
            st.write(f"**Empresa ID:** {grupo.get('empresa_id','—')}")
            st.write(f"**Fechas:** {inicio} → {fin}")

            if grupo["id"] in diplomas_dict:
                label = ajustes.get("texto_descarga_diploma", "📥 Descargar diploma")
                st.markdown(f"{label} — [Click aquí]({diplomas_dict[grupo['id']]})")
            else:
                st.info(ajustes.get(
                    "texto_espera_diploma",
                    "⏳ Diploma aún no disponible para este grupo."
                ))
                
