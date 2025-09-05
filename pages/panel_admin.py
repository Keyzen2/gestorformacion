import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 🛡️ Panel de Administración")
    st.caption("Resumen de alertas y supervisión del sistema.")
    st.divider()

    if session_state.role != "admin":
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    hoy = datetime.today().date()

    # =========================
    # 1. Grupos finalizados sin diplomas
    # =========================
    try:
        grupos_res = supabase.table("grupos").select("id, fecha_fin").execute().data or []
        grupos_finalizados = [g for g in grupos_res if pd.to_datetime(g["fecha_fin"]).date() < hoy]
        diplomas_res = supabase.table("diplomas").select("grupo_id").execute().data or []
        grupos_con_diplomas = set(d["grupo_id"] for d in diplomas_res)
        grupos_sin_diplomas = [g for g in grupos_finalizados if g["id"] not in grupos_con_diplomas]
    except Exception as e:
        st.error(f"❌ Error al verificar diplomas: {e}")
        grupos_sin_diplomas = []

    # =========================
    # 2. Participantes sin grupo
    # =========================
    try:
        participantes_res = supabase.table("participantes").select("id, grupo_id").execute().data or []
        participantes_sin_grupo = [p for p in participantes_res if not p["grupo_id"]]
    except Exception as e:
        st.error(f"❌ Error al verificar participantes: {e}")
        participantes_sin_grupo = []

    # =========================
    # 3. Grupos sin tutores asignados
    # =========================
    try:
        tutores_grupos_res = supabase.table("tutores_grupos").select("grupo_id").execute().data or []
        grupos_con_tutores = set(tg["grupo_id"] for tg in tutores_grupos_res)
        grupos_sin_tutores = [g for g in grupos_res if g["id"] not in grupos_con_tutores]
    except Exception as e:
        st.error(f"❌ Error al verificar tutores: {e}")
        grupos_sin_tutores = []

    # =========================
    # 4. Diplomas sin archivo válido
    # =========================
    try:
        diplomas_res = supabase.table("diplomas").select("id, url").execute().data or []
        diplomas_invalidos = [d for d in diplomas_res if not d["url"] or not d["url"].startswith("https://")]
    except Exception as e:
        st.error(f"❌ Error al verificar archivos de diplomas: {e}")
        diplomas_invalidos = []

    # =========================
    # 5. Empresas sin participantes
    # =========================
    try:
        empresas_res = supabase.table("empresas").select("id, nombre").execute().data or []
        participantes_res = supabase.table("participantes").select("empresa_id").execute().data or []
        empresas_con_participantes = set(p["empresa_id"] for p in participantes_res if p["empresa_id"])
        empresas_sin_participantes = [e for e in empresas_res if e["id"] not in empresas_con_participantes]
    except Exception as e:
        st.error(f"❌ Error al verificar empresas: {e}")
        empresas_sin_participantes = []

    # =========================
    # Mostrar alertas
    # =========================
    st.markdown("### 🔔 Alertas del sistema")

    if grupos_sin_diplomas:
        st.warning(f"⚠️ {len(grupos_sin_diplomas)} grupos finalizados no tienen diplomas asignados.")
    if participantes_sin_grupo:
        st.warning(f"⚠️ {len(participantes_sin_grupo)} participantes no están asignados a ningún grupo.")
    if grupos_sin_tutores:
        st.warning(f"⚠️ {len(grupos_sin_tutores)} grupos no tienen tutores asignados.")
    if diplomas_invalidos:
        st.warning(f"⚠️ {len(diplomas_invalidos)} diplomas tienen enlaces inválidos o vacíos.")
    if empresas_sin_participantes:
        st.warning(f"⚠️ {len(empresas_sin_participantes)} empresas no tienen participantes registrados.")

    if not any([
        grupos_sin_diplomas,
        participantes_sin_grupo,
        grupos_sin_tutores,
        diplomas_invalidos,
        empresas_sin_participantes
    ]):
        st.success("✅ Todo está en orden. No hay alertas activas.")

    st.divider()
    st.caption("Este panel se actualiza automáticamente cada vez que accedes.")
