import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("🎓 Mis Cursos y Diplomas")

    email = session_state.user.get("email")
    if not email:
        st.warning("No se ha detectado tu sesión correctamente.")
        return

    try:
        # Buscar participante
        part_res = supabase.table("participantes").select("id", "grupo_id").eq("email", email).execute()
        participante = part_res.data[0] if part_res.data else None
        if not participante:
            st.info("No estás registrado como participante.")
            return

        # Buscar diplomas
        diplomas_res = supabase.table("diplomas").select("*").eq("participante_id", participante["id"]).execute()
        diplomas = diplomas_res.data or []
        if not diplomas:
            st.info("No tienes diplomas registrados aún.")
            return

        # Obtener info de grupos y cursos
        grupo_ids = [d["grupo_id"] for d in diplomas]
        grupos_res = supabase.table("grupos").select("id", "fecha_inicio", "fecha_fin", "accion_formativa_id").in_("id", grupo_ids).execute()
        grupos = {g["id"]: g for g in grupos_res.data or []}

        accion_ids = [g["accion_formativa_id"] for g in grupos.values()]
        acciones_res = supabase.table("acciones_formativas").select("id", "nombre", "duracion_horas").in_("id", accion_ids).execute()
        acciones = {a["id"]: a for a in acciones_res.data or []}

        # Construir tabla visual
        registros = []
        for d in diplomas:
            grupo = grupos.get(d["grupo_id"])
            accion = acciones.get(grupo["accion_formativa_id"]) if grupo else None
            if grupo and accion:
                registros.append({
                    "Curso": accion["nombre"],
                    "Inicio": grupo["fecha_inicio"],
                    "Fin": grupo["fecha_fin"],
                    "Duración": accion.get("duracion_horas", ""),
                    "Diploma": d["url"],
                    "Año": pd.to_datetime(grupo["fecha_inicio"]).year
                })

        df = pd.DataFrame(registros)

        # =========================
        # Filtros
        # =========================
        st.markdown("### 🔍 Filtros")
        col1, col2 = st.columns(2)
        filtro_nombre = col1.text_input("Filtrar por nombre de curso")
        filtro_ano = col2.selectbox("Filtrar por año", ["Todos"] + sorted(df["Año"].unique(), reverse=True))

        if filtro_nombre:
            df = df[df["Curso"].str.contains(filtro_nombre, case=False, na=False)]
        if filtro_ano != "Todos":
            df = df[df["Año"] == filtro_ano]

        # =========================
        # Vista tipo tarjetas
        # =========================
        if df.empty:
            st.info("No hay cursos que coincidan con los filtros.")
        else:
            for _, row in df.iterrows():
                with st.container():
                    st.markdown(f"### 🧾 {row['Curso']}")
                    st.markdown(f"📅 **Fechas:** {row['Inicio']} → {row['Fin']}")
                    st.markdown(f"⏱️ **Duración:** {row['Duración']} horas")
                    st.markdown(f"[📄 Descargar diploma]({row['Diploma']})", unsafe_allow_html=True)
                    st.divider()

    except Exception as e:
        st.error(f"❌ Error al cargar tus cursos: {e}")

