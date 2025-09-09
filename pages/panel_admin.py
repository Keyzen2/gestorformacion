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
    # Cargar datos base para filtros
    # =========================
    empresas_res = supabase.table("empresas").select("id, nombre").execute().data or []
    empresas_dict = {e["id"]: e["nombre"] for e in empresas_res}

    tutores_res = supabase.table("tutores").select("id, nombre").execute().data or []
    tutores_dict = {t["id"]: t["nombre"] for t in tutores_res}

    # =========================
    # Filtros interactivos
    # =========================
    st.sidebar.header("Filtros")
    empresa_sel = st.sidebar.selectbox("🏢 Empresa", ["Todas"] + list(empresas_dict.values()))
    tutor_sel = st.sidebar.selectbox("🧑‍🏫 Tutor", ["Todos"] + list(tutores_dict.values()))
    fecha_inicio = st.sidebar.date_input("📅 Desde", value=None)
    fecha_fin = st.sidebar.date_input("📅 Hasta", value=None)

    # =========================
    # Construir consultas filtradas
    # =========================
    grupos_query = supabase.table("grupos").select("id, codigo_grupo, fecha_fin, empresa_id")

    if empresa_sel != "Todas":
        empresa_id = next(i for i, n in empresas_dict.items() if n == empresa_sel)
        grupos_query = grupos_query.eq("empresa_id", empresa_id)

    if tutor_sel != "Todos":
        tutor_id = next(i for i, n in tutores_dict.items() if n == tutor_sel)
        # Buscar grupos asociados a este tutor en la tabla intermedia
        grupos_ids_res = supabase.table("tutores_grupos").select("grupo_id").eq("tutor_id", tutor_id).execute().data or []
        grupos_ids = [g["grupo_id"] for g in grupos_ids_res]
        if grupos_ids:
            grupos_query = grupos_query.in_("id", grupos_ids)
        else:
            # Si no hay grupos para este tutor, devolvemos lista vacía
            grupos_res = []
            grupos_query = None

    if fecha_inicio:
        grupos_query = grupos_query.gte("fecha_fin", fecha_inicio.isoformat()) if grupos_query else None
    if fecha_fin:
        grupos_query = grupos_query.lte("fecha_fin", fecha_fin.isoformat()) if grupos_query else None

    grupos_res = grupos_query.execute().data if grupos_query else []

    # Otras tablas (sin filtros de fecha salvo que aplique)
    diplomas_res = supabase.table("diplomas").select("id, url, participante_id, grupo_id").execute().data or []
    participantes_res = supabase.table("participantes").select("id, nombre, email, grupo_id, empresa_id").execute().data or []
    tutores_grupos_res = supabase.table("tutores_grupos").select("grupo_id").execute().data or []

    # =========================
    # NUEVA alerta: módulos próximos a vencer
    # =========================
    DIAS_AVISO_VENCIMIENTO = 30
    modulos_res = supabase.table("modulos").select("id, nombre, empresa_id, fecha_vencimiento").execute().data or []
    empresas_con_vencimientos = [
        m for m in modulos_res
        if m.get("fecha_vencimiento") and
           0 <= (pd.to_datetime(m["fecha_vencimiento"]).date() - hoy).days <= DIAS_AVISO_VENCIMIENTO
    ]

    # =========================
    # Calcular alertas existentes
    # =========================
    grupos_finalizados = [g for g in grupos_res if pd.to_datetime(g["fecha_fin"]).date() < hoy]
    grupos_con_diplomas = set(d["grupo_id"] for d in diplomas_res)
    grupos_sin_diplomas = [g for g in grupos_finalizados if g["id"] not in grupos_con_diplomas]

    participantes_sin_grupo = [p for p in participantes_res if not p["grupo_id"]]

    grupos_con_tutores = set(tg["grupo_id"] for tg in tutores_grupos_res)
    grupos_sin_tutores = [g for g in grupos_res if g["id"] not in grupos_con_tutores]

    diplomas_invalidos = [d for d in diplomas_res if not d["url"] or not d["url"].startswith("https://")]

    empresas_con_participantes = set(p["empresa_id"] for p in participantes_res if p["empresa_id"])
    empresas_sin_participantes = [e for e in empresas_res if e["id"] not in empresas_con_participantes]

    # =========================
    # Tabs: Alertas y Estadísticas
    # =========================
    tab1, tab2 = st.tabs(["🔔 Alertas del sistema", "📊 Estadísticas"])

    with tab1:
        st.subheader("🔍 Alertas activas (según filtros)")

        if empresas_con_vencimientos:
            st.warning(f"⚠️ {len(empresas_con_vencimientos)} módulos están próximos a vencer en los próximos {DIAS_AVISO_VENCIMIENTO} días.")
            with st.expander("Ver módulos próximos a vencer"):
                for m in empresas_con_vencimientos:
                    empresa_nombre = empresas_dict.get(m["empresa_id"], m["empresa_id"])
                    st.markdown(f"- 🏢 **{empresa_nombre}** | 📦 Módulo: `{m['nombre']}` | ⏳ Vence: `{m['fecha_vencimiento']}`")

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

        if not any([grupos_sin_diplomas, participantes_sin_grupo, grupos_sin_tutores, diplomas_invalidos, empresas_sin_participantes, empresas_con_vencimientos]):
            st.success("✅ Todo está en orden. No hay alertas activas.")

    with tab2:
        st.subheader("📈 Métricas globales (según filtros)")
        try:
            total_empresas = supabase.table("empresas").select("*", count="exact").execute().count or 0
            total_usuarios = supabase.table("usuarios").select("*", count="exact").execute().count or 0
            total_cursos = supabase.table("acciones_formativas").select("*", count="exact").execute().count or 0
            total_grupos = len(grupos_res)  # filtrado
            total_participantes = len(participantes_res)  # filtrado
        except Exception as e:
            st.error(f"❌ Error al cargar métricas: {e}")
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
