import streamlit as st
import pandas as pd

# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="🎓 Mis Cursos",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# MAIN
# =========================
def main(supabase, session_state):
    st.title("🎓 Mis Cursos")

    # 1. Obtener email del usuario logueado
    email = session_state.user.get("email")
    if not email:
        st.error("❌ No se pudo identificar al usuario.")
        return

    # 2. Cargar datos desde vista
    try:
        part_res = supabase.table("vw_participantes_completo").select("*").eq("email", email).execute()
        df = pd.DataFrame(part_res.data or [])
    except Exception as e:
        st.error(f"❌ Error cargando cursos: {e}")
        return

    if df.empty:
        st.info("📋 No tienes cursos asignados aún.")
        return

    # =========================
    # FILTROS
    # =========================
    st.markdown("### 🔍 Filtros")
    col1, col2, col3 = st.columns(3)

    filtro_nombre = col1.text_input("Filtrar por curso o empresa")
    anos_disponibles = sorted(
        pd.to_datetime(df["grupo_fecha_inicio"], errors="coerce").dropna().dt.year.unique(),
        reverse=True
    )
    filtro_ano = col2.selectbox("Filtrar por año", ["Todos"] + [str(a) for a in anos_disponibles])
    filtro_estado = col3.selectbox("Filtrar por estado", ["Todos", "Pendiente de inicio", "En curso", "Curso finalizado", "Con diploma"])

    # Aplicar filtros
    if filtro_nombre:
        df = df[
            df["accion_nombre"].str.contains(filtro_nombre, case=False, na=False) |
            df["empresa_nombre"].str.contains(filtro_nombre, case=False, na=False)
        ]
    if filtro_ano != "Todos":
        df = df[pd.to_datetime(df["grupo_fecha_inicio"], errors="coerce").dt.year == int(filtro_ano)]
    if filtro_estado != "Todos":
        if filtro_estado == "Con diploma":
            df = df[df["tiene_diploma"] == True]
        else:
            df = df[df["estado_formacion"] == filtro_estado]

    # =========================
    # VISTA EN TARJETAS
    # =========================
    if df.empty:
        st.warning("⚠️ No se encontraron cursos con esos filtros.")
        return

    for _, row in df.iterrows():
        with st.container():
            st.markdown(f"### 🧾 {row['accion_nombre']} ({row['accion_horas']}h)")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"🏢 **Empresa:** {row['empresa_nombre']}")
                st.markdown(f"📅 **Fechas:** {row['grupo_fecha_inicio']} → {row['grupo_fecha_fin_prevista']}")
                st.markdown(f"📌 **Estado:** {row['estado_formacion']}")
            with col2:
                if row.get("tiene_diploma") and row.get("diploma_url"):
                    st.markdown(f"[📄 Descargar diploma]({row['diploma_url']})", unsafe_allow_html=True)

            st.divider()
