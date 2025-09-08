import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    # Título y descripción
    st.title("🛡️ Panel de Administración")
    st.caption("Supervisión del sistema y métricas globales.")

    # Verificar si el usuario tiene rol de administrador
    if session_state.role != "admin":
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    hoy = datetime.today().date()

    # =========================
    # Cargar datos para alertas
    # =========================
    try:
        # Consultar tablas para obtener los datos necesarios
        grupos_res = supabase.table("grupos").select("id, codigo_grupo, fecha_fin").execute().data or []
        diplomas_res = supabase.table("diplomas").select("grupo_id").execute().data or []
        participantes_res = supabase.table("participantes").select("id, nombre, email, grupo_id, empresa_id").execute().data or []
        tutores_grupos_res = supabase.table("tutores_grupos").select("grupo_id").execute().data or []
        empresas_res = supabase.table("empresas").select("id, nombre").execute().data or []

        # Filtrar los datos para las alertas
        grupos_finalizados = [g for g in grupos_res if pd.to_datetime(g["fecha_fin"]).date() < hoy]
        grupos_con_diplomas = set(d["grupo_id"] for d in diplomas_res)
        grupos_sin_diplomas = [g for g in grupos_finalizados if g["id"] not in grupos_con_diplomas]

        participantes_sin_grupo = [p for p in participantes_res if not p["grupo_id"]]

        grupos_con_tutores = set(tg["grupo_id"] for tg in tutores_grupos_res)
        grupos_sin_tutores = [g for g in grupos_res if g["id"] not in grupos_con_tutores]

        diplomas_full = supabase.table("diplomas").select("id, url, participante_id, grupo_id").execute().data or []
        diplomas_invalidos = [d for d in diplomas_full if not d["url"] or not d["url"].startswith("https://")]

        empresas_con_participantes = set(p["empresa_id"] for p in participantes_res if p["empresa_id"])
        empresas_sin_participantes = [e for e in empresas_res if e["id"] not in empresas_con_participantes]

    except Exception as e:
        st.error(f"❌ Error al cargar datos del sistema: {e}")
        grupos_sin_diplomas = grupos_sin_tutores = grupos_finalizados = participantes_sin_grupo = []
        diplomas_invalidos = empresas_sin_participantes = []

    # =========================
    # Tabs: Alertas y Estadísticas
    # =========================
    tab1, tab2 = st.tabs(["🔔 Alertas del sistema", "📊 Estadísticas globales"])

    with tab1:
        st.subheader("🔍 Alertas activas")

        # Alertas de grupos sin diplomas
        if grupos_sin_diplomas:
            st.warning(f"⚠️ {len(grupos_sin_diplomas)} grupos finalizados no tienen diplomas asignados.")
            with st.expander("Ver grupos sin diplomas"):
                for g in grupos_sin_diplomas:
                    st.markdown(f"- 🗂️ Grupo `{g['codigo_grupo']}` | Fecha fin: `{g['fecha_fin']}`")

        # Alertas de participantes sin grupo
        if participantes_sin_grupo:
            st.warning(f"⚠️ {len(participantes_sin_grupo)} participantes no están asignados a ningún grupo.")
            with st.expander("Ver participantes sin grupo"):
                for p in participantes_sin_grupo:
                    st.markdown(f"- 👤 {p['nombre']} | 📧 {p['email']}")

        # Alertas de grupos sin tutores
        if grupos_sin_tutores:
            st.warning(f"⚠️ {len(grupos_sin_tutores)} grupos no tienen tutores asignados.")
            with st.expander("Ver grupos sin tutores"):
                for g in grupos_sin_tutores:
                    st.markdown(f"- 🧑‍🏫 Grupo `{g['codigo_grupo']}` | Fecha fin: `{g['fecha_fin']}`")

        # Alertas de diplomas inválidos
        if diplomas_invalidos:
            st.warning(f"⚠️ {len(diplomas_invalidos)} diplomas tienen enlaces inválidos o vacíos.")
            with st.expander("Ver diplomas inválidos"):
                for d in diplomas_invalidos:
                    st.markdown(f"- 📄 Diploma ID `{d['id']}` | Participante `{d['participante_id']}` | Grupo `{d['grupo_id']}`")

        # Alertas de empresas sin participantes
        if empresas_sin_participantes:
            st.warning(f"⚠️ {len(empresas_sin_participantes)} empresas no tienen participantes registrados.")
            with st.expander("Ver empresas sin participantes"):
                for e in empresas_sin_participantes:
                    st.markdown(f"- 🏢 Empresa: `{e['nombre']}`")

        # Mensaje de éxito si no hay alertas activas
        if not any([grupos_sin_diplomas, participantes_sin_grupo, grupos_sin_tutores, diplomas_invalidos, empresas_sin_participantes]):
            st.success("✅ Todo está en orden. No hay alertas activas.")

    with tab2:
        st.subheader("📈 Métricas globales del sistema")
        try:
            # Obtener métricas globales
            total_empresas = supabase.table("empresas").select("*").execute().count or 0
            total_usuarios = supabase.table("usuarios").select("*").execute().count or 0
            total_cursos = supabase.table("acciones_formativas").select("*").execute().count or 0
            total_grupos = supabase.table("grupos").select("*").execute().count or 0
            total_participantes = supabase.table("participantes").select("*").execute().count or 0
        except Exception as e:
            st.error(f"❌ Error al cargar métricas globales: {e}")
            total_empresas = total_usuarios = total_cursos = total_grupos = total_participantes = 0

        # Mostrar las métricas en columnas
        col1, col2, col3 = st.columns(3)
        col1.metric("🏢 Empresas registradas", total_empresas)
        col2.metric("👤 Usuarios activos", total_usuarios)
        col3.metric("📚 Cursos activos", total_cursos)

        col4, col5 = st.columns(2)
        col4.metric("👥 Grupos creados", total_grupos)
        col5.metric("🎓 Participantes registrados", total_participantes)

    # Divider y nota de actualización
    st.divider()
    st.caption("Este panel se actualiza automáticamente cada vez que accedes.")
    
