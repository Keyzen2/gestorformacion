import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("📋 Auditorías")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 Solo administradores o gestores pueden acceder a esta sección.")
        st.stop()

    # =========================
    # Cargar datos
    # =========================
    aud_res = supabase.table("auditorias").select("*").execute()
    df_aud = pd.DataFrame(aud_res.data) if aud_res.data else pd.DataFrame()

    nc_res = supabase.table("no_conformidades").select("id", "descripcion").execute()
    df_nc = pd.DataFrame(nc_res.data) if nc_res.data else pd.DataFrame()

    # =========================
    # KPIs
    # =========================
    st.markdown("### 📊 Resumen")
    total_aud = len(df_aud)
    internas = len(df_aud[df_aud["tipo"] == "Interna"]) if "tipo" in df_aud.columns else 0
    externas = len(df_aud[df_aud["tipo"] == "Externa"]) if "tipo" in df_aud.columns else 0
    cerradas = len(df_aud[df_aud["estado"] == "Cerrada"]) if "estado" in df_aud.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", total_aud)
    col2.metric("Internas", internas)
    col3.metric("Externas", externas)
    col4.metric("Cerradas", cerradas)

    # =========================
    # Filtros
    # =========================
    st.markdown("### 🔍 Filtros")
    tipo_filtro = st.selectbox("Filtrar por tipo", ["Todos", "Interna", "Externa"])
    if tipo_filtro != "Todos" and "tipo" in df_aud.columns:
        df_aud = df_aud[df_aud["tipo"] == tipo_filtro]

    estado_filtro = st.selectbox("Filtrar por estado", ["Todos", "Planificada", "En curso", "Cerrada"])
    if estado_filtro != "Todos" and "estado" in df_aud.columns:
        df_aud = df_aud[df_aud["estado"] == estado_filtro]

    # =========================
    # Exportación
    # =========================
    if not df_aud.empty:
        st.download_button(
            "⬇️ Descargar CSV",
            data=df_aud.to_csv(index=False).encode("utf-8"),
            file_name="auditorias.csv",
            mime="text/csv"
        )

    # =========================
    # Listado y gestión
    # =========================
    if not df_aud.empty:
        for _, row in df_aud.iterrows():
            with st.expander(f"Auditoría {row['id']} - {row['tipo']} ({row['estado']})"):
                st.write(f"**Fecha:** {row.get('fecha', '')}")
                st.write(f"**Auditor:** {row.get('auditor', '')}")
                st.write(f"**Descripción:** {row.get('descripcion', '')}")
                st.write(f"**Hallazgos:** {row.get('hallazgos', '')}")
                st.write(f"**No Conformidad asociada:** {row.get('no_conformidad_id', '')}")

                col1, col2 = st.columns(2)

                # ✏️ Editar
                with col1:
                    with st.form(f"edit_aud_{row['id']}", clear_on_submit=True):
                        nuevo_tipo = st.selectbox("Tipo", ["Interna", "Externa"], index=["Interna", "Externa"].index(row.get("tipo", "Interna")))
                        nuevo_estado = st.selectbox("Estado", ["Planificada", "En curso", "Cerrada"], index=["Planificada", "En curso", "Cerrada"].index(row.get("estado", "Planificada")))
                        nuevo_auditor = st.text_input("Auditor", value=row.get("auditor", ""))
                        nueva_desc = st.text_area("Descripción", value=row.get("descripcion", ""))
                        nuevos_hallazgos = st.text_area("Hallazgos", value=row.get("hallazgos", ""))

                        guardar = st.form_submit_button("Guardar cambios")
                        if guardar:
                            supabase.table("auditorias").update({
                                "tipo": nuevo_tipo,
                                "estado": nuevo_estado,
                                "auditor": nuevo_auditor,
                                "descripcion": nueva_desc,
                                "hallazgos": nuevos_hallazgos
                            }).eq("id", row["id"]).execute()
                            st.success("✅ Cambios guardados.")
                            st.experimental_rerun()

                # 🗑️ Eliminar
                with col2:
                    with st.form(f"delete_aud_{row['id']}"):
                        st.warning("⚠️ Esta acción eliminará la auditoría.")
                        confirmar = st.checkbox("Confirmo la eliminación")
                        eliminar = st.form_submit_button("Eliminar")
                        if eliminar and confirmar:
                            supabase.table("auditorias").delete().eq("id", row["id"]).execute()
                            st.success("✅ Eliminada.")
                            st.experimental_rerun()

    else:
        st.info("ℹ️ No hay auditorías registradas.")

    # =========================
    # Alta
    # =========================
    st.markdown("### ➕ Registrar Auditoría")
    with st.form("form_aud", clear_on_submit=True):
        tipo = st.selectbox("Tipo", ["Interna", "Externa"])
        estado = st.selectbox("Estado", ["Planificada", "En curso", "Cerrada"])
        fecha = st.date_input("Fecha", datetime.today())
        auditor = st.text_input("Auditor")
        descripcion = st.text_area("Descripción")
        hallazgos = st.text_area("Hallazgos")

        nc_id = None
        if not df_nc.empty:
            nc_opciones = {f"{row['id']} - {row['descripcion'][:50]}": row['id'] for _, row in df_nc.iterrows()}
            nc_seleccion = st.selectbox("No Conformidad asociada (opcional)", ["Ninguna"] + list(nc_opciones.keys()))
            if nc_seleccion != "Ninguna":
                nc_id = nc_opciones[nc_seleccion]

        submitted = st.form_submit_button("Guardar")
        if submitted:
            supabase.table("auditorias").insert({
                "tipo": tipo,
                "estado": estado,
                "fecha": fecha.isoformat(),
                "auditor": auditor,
                "descripcion": descripcion,
                "hallazgos": hallazgos,
                "no_conformidad_id": nc_id
            }).execute()
            st.success("✅ Auditoría registrada.")
            st.experimental_rerun()
              
