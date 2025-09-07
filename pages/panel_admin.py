import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.title("🛡️ Panel de Administración")
    st.caption("Supervisión del sistema y métricas globales.")

    if session_state.role != "admin":
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    hoy = datetime.today().date()

    # =========================
    # Cargar datos para alertas
    # =========================
    try:
        grupos_res = supabase.table("grupos").select("id, codigo_grupo, fecha_fin").execute().data or []
        grupos_finalizados = [g for g in grupos_res if pd.to_datetime(g["fecha_fin"]).date() < hoy]
        diplomas_res = supabase.table("diplomas").select("grupo_id").execute().data or []
        grupos_con_diplomas = set(d["grupo_id"] for d in diplomas_res)
        grupos_sin_diplomas = [g for g in grupos_finalizados if g["id"] not in grupos_con_diplomas]
    except Exception as e:
        st.error(f"❌ Error al verificar diplomas: {e}")
        grupos_sin_diplomas = []

    try:
        participantes_res = supabase.table("participantes").select("id, nombre, email, grupo_id, empresa_id").execute().data or []
        participantes_sin_grupo = [p for p in participantes_res if not p["grupo_id"]]
    except Exception as e:
        st.error(f"❌ Error al verificar participantes: {e}")
        participantes_sin_grupo = []

    try:
        tutores_grupos_res = supabase.table("tutores_grupos").select("grupo_id").execute().data or []
        grupos_con_tutores = set(tg["grupo_id"] for tg in tutores_grupos_res)
        grupos_sin_tutores = [g for g in grupos_res if g["id"] not in grupos_con_tutores]
    except Exception as e:
        st.error(f"❌ Error al verificar tutores: {e}")
        grupos_sin_tutores = []

    try:
        diplomas_full = supabase.table("diplomas").select("id, url, participante_id, grupo_id").execute().data or []
        diplomas_invalidos = [d for d in diplomas_full if not d["url"] or not d["url"].startswith("https://")]
    except Exception as e:
        st.error(f"❌ Error al verificar archivos de diplomas: {e}")
        diplomas_invalidos = []

    try:
        empresas_res = supabase.table("empresas").select("id, nombre").execute().data or []
        empresas_con_participantes = set(p["empresa_id"] for p in participantes_res if p["empresa_id"])
        empresas_sin_participantes = [e for e in empresas_res if e["id"] not in empresas_con_participantes]
    except Exception as e:
        st.error(f"❌ Error al verificar empresas: {e}")
        empresas_sin_participantes = []

    # =========================
    # Tabs: Alertas y Estadísticas
    # =========================
    tab1, tab2 = st.tabs(["🔔 Alertas del sistema", "📊 Estadísticas globales"])

    with tab1:
        st.subheader("🔍 Alertas activas")

        if grupos_sin_diplomas:
            st.warning(f"⚠️ {len(grupos_sin_diplomas)} grupos finalizados no tienen diplomas asignados.")
            with st.expander("Ver grupos sin diplomas"):
                for g in grupos_sin_diplomas:
                    st.markdown(f"- 🗂️ Grupo `{g['codigo_grupo']}` | Fecha fin: `{g['fecha_fin']}`")

        if participantes_sin_grupo:
            st.warning(f"⚠️ {len(participantes_sin_grupo)} participantes no están asignados a ningún grupo.")
            with st.expander("Ver participantes sin grupo"):
                for p in participantes_sin_grupo:
                    st.markdown(f"- 👤 {p['nombre']} | 📧 {p['email']}")

        if grupos_sin_tutores:
            st.warning(f"⚠️ {len(grupos_sin_tutores)} grupos no tienen tutores asignados.")
            with st.expander("Ver grupos sin tutores"):
                for g in grupos_sin_tutores:
                    st.markdown(f"- 🧑‍🏫 Grupo `{g['codigo_grupo']}` | Fecha fin: `{g['fecha_fin']}`")

        if diplomas_invalidos:
            st.warning(f"⚠️ {len(diplomas_invalidos)} diplomas tienen enlaces inválidos o vacíos.")
            with st.expander("Ver diplomas inválidos"):
                for d in diplomas_invalidos:
                    st.markdown(f"- 📄 Diploma ID `{d['id']}` | Participante `{d['participante_id']}` | Grupo `{d['grupo_id']}`")

        if empresas_sin_participantes:
            st.warning(f"⚠️ {len(empresas_sin_participantes)} empresas no tienen participantes registrados.")
            with st.expander("Ver empresas sin participantes"):
                for e in empresas_sin_participantes:
                    st.markdown(f"- 🏢 Empresa: `{e['nombre']}`")

        if not any([
            grupos_sin_diplomas,
            participantes_sin_grupo,
            grupos_sin_tutores,
            diplomas_invalidos,
            empresas_sin_participantes
        ]):
            st.success("✅ Todo está en orden. No hay alertas activas.")

    with tab2:
        st.subheader("📈 Métricas globales del sistema")
        try:
            total_empresas = supabase.table("empresas").select("*").execute().count or 0
            total_usuarios = supabase.table("usuarios").select("*").execute().count or 0
            total_cursos = supabase.table("acciones_formativas").select("*").execute().count or 0
            total_grupos = supabase.table("grupos").select("*").execute().count or 0
            total_participantes = supabase.table("participantes").select("*").execute().count or 0
        except:
            total_empresas = total_usuarios = total_cursos = total_grupos = total_participantes = 0

        col1, col2, col3 = st.columns(3)
        col1.metric("🏢 Empresas registradas", total_empresas)
        col2.metric("👤 Usuarios activos", total_usuarios)
        col3.metric("📚 Cursos activos", total_cursos)

        col4, col5 = st.columns(2)
        col4.metric("👥 Grupos creados", total_grupos)
        col5.metric("🎓 Participantes registrados", total_participantes)

    st.divider()
    st.caption("Este panel se actualiza automáticamente cada vez que accedes.")
    
