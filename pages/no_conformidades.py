import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("🚨 No Conformidades (ISO 9001)")
    st.caption("Registro, seguimiento y cierre de no conformidades detectadas en procesos, auditorías o inspecciones.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 Solo administradores o gestores pueden acceder a esta sección.")
        st.stop()

    # =========================
    # Cargar datos desde la vista
    # =========================
    nc_res = supabase.table("no_conformidades_app").select("*").execute()
    df_nc = pd.DataFrame(nc_res.data) if nc_res.data else pd.DataFrame()

    # =========================
    # KPIs
    # =========================
    st.markdown("### 📊 Resumen")
    total_nc = len(df_nc)
    abiertas = len(df_nc[df_nc["estado"] == "Abierta"]) if "estado" in df_nc.columns else 0
    cerradas = len(df_nc[df_nc["estado"] == "Cerrada"]) if "estado" in df_nc.columns else 0
    en_curso = len(df_nc[df_nc["estado"] == "En curso"]) if "estado" in df_nc.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", total_nc)
    col2.metric("Abiertas", abiertas)
    col3.metric("En curso", en_curso)
    col4.metric("Cerradas", cerradas)

    # =========================
    # Filtros
    # =========================
    st.markdown("### 🔍 Filtros")
    estado_filtro = st.selectbox("Filtrar por estado", ["Todos", "Abierta", "En curso", "Cerrada"])
    if estado_filtro != "Todos" and "estado" in df_nc.columns:
        df_nc = df_nc[df_nc["estado"] == estado_filtro]

    responsable_filtro = st.text_input("Filtrar por responsable")
    if responsable_filtro and "responsable" in df_nc.columns:
        df_nc = df_nc[df_nc["responsable"].str.contains(responsable_filtro, case=False, na=False)]

    # =========================
    # Exportación
    # =========================
    if not df_nc.empty:
        st.download_button(
            "⬇️ Descargar CSV",
            data=df_nc.to_csv(index=False).encode("utf-8"),
            file_name="no_conformidades.csv",
            mime="text/csv"
        )

    # =========================
    # Listado y gestión
    # =========================
    if not df_nc.empty:
        for _, row in df_nc.iterrows():
            with st.expander(f"{row['descripcion'][:50]}... ({row['estado']})"):
                st.write(f"**Responsable:** {row.get('responsable', '')}")
                st.write(f"**Fecha detección:** {row.get('fecha', '')}")
                st.write(f"**Estado:** {row.get('estado', '')}")
                st.write(f"**Acciones tomadas:** {row.get('acciones', '')}")

                col1, col2 = st.columns(2)

                # ✏️ Editar
                with col1:
                    with st.form(f"edit_nc_{row['id']}", clear_on_submit=True):
                        nueva_desc = st.text_area("Descripción", value=row["descripcion"])
                        nuevo_resp = st.text_input("Responsable", value=row.get("responsable", ""))
                        nuevo_estado = st.selectbox("Estado", ["Abierta", "En curso", "Cerrada"], index=["Abierta", "En curso", "Cerrada"].index(row.get("estado", "Abierta")))
                        nuevas_acciones = st.text_area("Acciones tomadas", value=row.get("acciones", ""))

                        guardar = st.form_submit_button("Guardar cambios")
                        if guardar:
                            supabase.table("no_conformidades").update({
                                "descripcion": nueva_desc,
                                "responsable": nuevo_resp,
                                "estado": nuevo_estado,
                                "acciones": nuevas_acciones
                            }).eq("id", row["id"]).execute()
                            st.success("✅ Cambios guardados.")
                            st.experimental_rerun()

                # 🗑️ Eliminar
                with col2:
                    with st.form(f"delete_nc_{row['id']}"):
                        st.warning("⚠️ Esta acción eliminará la no conformidad.")
                        confirmar = st.checkbox("Confirmo la eliminación")
                        eliminar = st.form_submit_button("Eliminar")
                        if eliminar and confirmar:
                            supabase.table("no_conformidades").delete().eq("id", row["id"]).execute()
                            st.success("✅ Eliminada.")
                            st.experimental_rerun()

    else:
        st.info("ℹ️ No hay no conformidades registradas.")

    # =========================
    # Alta
    # =========================
    st.markdown("### ➕ Registrar No Conformidad")
    with st.form("form_nc", clear_on_submit=True):
        descripcion = st.text_area("Descripción *")
        responsable = st.text_input("Responsable")
        fecha = st.date_input("Fecha detección", datetime.today())
        estado = st.selectbox("Estado", ["Abierta", "En curso", "Cerrada"])
        acciones = st.text_area("Acciones tomadas")
        submitted = st.form_submit_button("Guardar")

        if submitted:
            supabase.table("no_conformidades").insert({
                "descripcion": descripcion,
                "responsable": responsable,
                "fecha_detectada": fecha.isoformat(),
                "estado": estado,
                "acciones": acciones
            }).execute()
            st.success("✅ No conformidad registrada.")
            st.experimental_rerun()
