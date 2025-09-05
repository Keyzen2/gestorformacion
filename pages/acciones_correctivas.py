import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("🛠️ Acciones Correctivas")
    st.caption("Gestión de acciones correctivas asociadas a no conformidades.")
    st.divider()

    # 🔒 Protección por rol y módulo ISO activo
    if session_state.role == "gestor":
        empresa_id = session_state.user.get("empresa_id")
        empresa_res = supabase.table("empresas").select("iso_activo", "iso_inicio", "iso_fin").eq("id", empresa_id).execute()
        empresa = empresa_res.data[0] if empresa_res.data else {}
        hoy = datetime.today().date()

        iso_permitido = (
            empresa.get("iso_activo") and
            (empresa.get("iso_inicio") is None or pd.to_datetime(empresa["iso_inicio"]).date() <= hoy) and
            (empresa.get("iso_fin") is None or pd.to_datetime(empresa["iso_fin"]).date() >= hoy)
        )

        if not iso_permitido:
            st.warning("🔒 Tu empresa no tiene activado el módulo ISO 9001.")
            st.stop()

    elif session_state.role != "admin":
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # =========================
    # Cargar datos
    # =========================
    try:
        if session_state.role == "gestor":
            ac_res = supabase.table("acciones_correctivas").select("*").eq("empresa_id", empresa_id).execute()
            nc_res = supabase.table("no_conformidades").select("id", "descripcion").eq("empresa_id", empresa_id).execute()
        else:
            ac_res = supabase.table("acciones_correctivas").select("*").execute()
            nc_res = supabase.table("no_conformidades").select("id", "descripcion").execute()

        df_ac = pd.DataFrame(ac_res.data) if ac_res.data else pd.DataFrame()
        df_nc = pd.DataFrame(nc_res.data) if nc_res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        df_ac = pd.DataFrame()
        df_nc = pd.DataFrame()

    # =========================
    # KPIs
    # =========================
    st.markdown("### 📊 Resumen")
    total_ac = len(df_ac)
    abiertas = len(df_ac[df_ac["estado"] == "Abierta"]) if "estado" in df_ac.columns else 0
    en_curso = len(df_ac[df_ac["estado"] == "En curso"]) if "estado" in df_ac.columns else 0
    cerradas = len(df_ac[df_ac["estado"] == "Cerrada"]) if "estado" in df_ac.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", total_ac)
    col2.metric("Abiertas", abiertas)
    col3.metric("En curso", en_curso)
    col4.metric("Cerradas", cerradas)

    # =========================
    # Filtros
    # =========================
    st.markdown("### 🔍 Filtros")
    estado_filtro = st.selectbox("Filtrar por estado", ["Todos", "Abierta", "En curso", "Cerrada"])
    if estado_filtro != "Todos" and "estado" in df_ac.columns:
        df_ac = df_ac[df_ac["estado"] == estado_filtro]

    # =========================
    # Exportación
    # =========================
    if not df_ac.empty:
        st.download_button(
            "⬇️ Descargar CSV",
            data=df_ac.to_csv(index=False).encode("utf-8"),
            file_name="acciones_correctivas.csv",
            mime="text/csv"
        )

    # =========================
    # Listado y gestión
    # =========================
    if not df_ac.empty:
        for _, row in df_ac.iterrows():
            with st.expander(f"AC-{row['id']} ({row['estado']})"):
                st.write(f"**No Conformidad asociada:** {row.get('no_conformidad_id', '')}")
                st.write(f"**Descripción:** {row.get('descripcion', '')}")
                st.write(f"**Responsable:** {row.get('responsable', '')}")
                st.write(f"**Fecha inicio:** {row.get('fecha_inicio', '')}")
                st.write(f"**Fecha cierre:** {row.get('fecha_cierre', '')}")
                st.write(f"**Seguimiento:** {row.get('seguimiento', '')}")

                if session_state.role == "admin":
                    col1, col2 = st.columns(2)

                    with col1:
                        with st.form(f"edit_ac_{row['id']}", clear_on_submit=True):
                            nueva_desc = st.text_area("Descripción", value=row["descripcion"])
                            nuevo_resp = st.text_input("Responsable", value=row.get("responsable", ""))
                            nuevo_estado = st.selectbox("Estado", ["Abierta", "En curso", "Cerrada"], index=["Abierta", "En curso", "Cerrada"].index(row.get("estado", "Abierta")))
                            nuevo_seguimiento = st.text_area("Seguimiento", value=row.get("seguimiento", ""))

                            guardar = st.form_submit_button("Guardar cambios")
                            if guardar:
                                supabase.table("acciones_correctivas").update({
                                    "descripcion": nueva_desc,
                                    "responsable": nuevo_resp,
                                    "estado": nuevo_estado,
                                    "seguimiento": nuevo_seguimiento
                                }).eq("id", row["id"]).execute()
                                st.success("✅ Cambios guardados.")
                                st.experimental_rerun()

                    with col2:
                        with st.form(f"delete_ac_{row['id']}"):
                            st.warning("⚠️ Esta acción eliminará la acción correctiva.")
                            confirmar = st.checkbox("Confirmo la eliminación")
                            eliminar = st.form_submit_button("Eliminar")
                            if eliminar and confirmar:
                                supabase.table("acciones_correctivas").delete().eq("id", row["id"]).execute()
                                st.success("✅ Eliminada.")
                                st.experimental_rerun()
    else:
        st.info("ℹ️ No hay acciones correctivas registradas.")

    # =========================
    # Alta (admin y gestor)
    # =========================
    if session_state.role in ["admin", "gestor"]:
        st.markdown("### ➕ Registrar Acción Correctiva")
        with st.form("form_ac", clear_on_submit=True):
            nc_id = None
            if not df_nc.empty:
                nc_opciones = {f"{row['id']} - {row['descripcion'][:50]}": row['id'] for _, row in df_nc.iterrows()}
                nc_seleccion = st.selectbox("No Conformidad asociada", list(nc_opciones.keys()))
                nc_id = nc_opciones[nc_seleccion]

            descripcion = st.text_area("Descripción *")
            responsable = st.text_input("Responsable")
            fecha_inicio = st.date_input("Fecha inicio", datetime.today())
            estado = st.selectbox("Estado", ["Abierta", "En curso", "Cerrada"])
            seguimiento = st.text_area("Seguimiento")
            submitted = st.form_submit_button("Guardar")

            if submitted:
                data = {
                    "no_conformidad_id": nc_id,
                    "descripcion": descripcion,
                    "responsable": responsable,
                    "fecha_inicio": fecha_inicio.isoformat(),
                    "estado": estado,
                    "seguimiento": seguimiento
                }
                if session_state.role == "gestor":
                    data["empresa_id"] = empresa_id
                supabase.table("acciones_correctivas").insert(data).execute()
                st.success("✅ Acción correctiva registrada.")
                st.experimental_rerun()
          
