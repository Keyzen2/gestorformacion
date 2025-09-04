import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import io

def main(supabase, session_state):
    st.subheader("🏢 Empresas")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden gestionar empresas.")
        st.stop()

    # =========================
    # Cargar empresas
    # =========================
    empresas_res = supabase.table("empresas").select("*").execute()
    df_empresas = pd.DataFrame(empresas_res.data) if empresas_res.data else pd.DataFrame()
    
# =========================
# Panel resumen de KPIs
# =========================
st.markdown("### 📊 Resumen de Empresas")

total_empresas = len(df_empresas)
empresas_mes = df_empresas[
    pd.to_datetime(df_empresas["fecha_alta"], errors="coerce").dt.month == datetime.now().month
]

total_mes = len(empresas_mes)

provincia_top = df_empresas["provincia"].value_counts().idxmax() if "provincia" in df_empresas.columns else "N/D"
ciudad_top = df_empresas["ciudad"].value_counts().idxmax() if "ciudad" in df_empresas.columns else "N/D"

col1, col2, col3, col4 = st.columns(4)
col1.metric("🏢 Total Empresas", total_empresas)
col2.metric("🗓️ Nuevas este mes", total_mes)
col3.metric("📍 Provincia más frecuente", provincia_top)
col4.metric("🌆 Ciudad más frecuente", ciudad_top)

    # =========================
    # Filtro y exportación
    # =========================
    search_query = st.text_input("🔍 Buscar por nombre o CIF")
    if search_query:
        df_empresas = df_empresas[
            df_empresas["nombre"].str.contains(search_query, case=False, na=False) |
            df_empresas["cif"].str.contains(search_query, case=False, na=False)
        ]

    if not df_empresas.empty:
        col_csv, col_excel = st.columns(2)
        with col_csv:
            st.download_button(
                "⬇️ Descargar CSV",
                data=df_empresas.to_csv(index=False).encode("utf-8"),
                file_name="empresas.csv",
                mime="text/csv"
            )
        with col_excel:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_empresas.to_excel(writer, index=False, sheet_name='Empresas')
                writer.save()
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=output.getvalue(),
                    file_name="empresas.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        # =========================
        # Estadísticas visuales
        # =========================
        st.markdown("### 📈 Estadísticas")
        if "provincia" in df_empresas.columns:
            prov_count = df_empresas["provincia"].value_counts().reset_index()
            prov_count.columns = ["Provincia", "Total"]
            fig_prov = px.bar(prov_count, x="Provincia", y="Total", title="Empresas por Provincia", text="Total")
            st.plotly_chart(fig_prov, use_container_width=True)

        if "ciudad" in df_empresas.columns:
            ciudad_count = df_empresas["ciudad"].value_counts().reset_index()
            ciudad_count.columns = ["Ciudad", "Total"]
            fig_ciudad = px.pie(ciudad_count, names="Ciudad", values="Total", title="Distribución por Ciudad")
            st.plotly_chart(fig_ciudad, use_container_width=True)

        if "fecha_alta" in df_empresas.columns:
            df_empresas["año_alta"] = pd.to_datetime(df_empresas["fecha_alta"], errors="coerce").dt.year
            año_count = df_empresas["año_alta"].value_counts().sort_index().reset_index()
            año_count.columns = ["Año", "Total"]
            fig_año = px.line(año_count, x="Año", y="Total", markers=True, title="Empresas dadas de alta por año")
            st.plotly_chart(fig_año, use_container_width=True)

        # =========================
        # Paginación
        # =========================
        page_size = st.selectbox("Registros por página", [5, 10, 20], index=1)
        total_rows = len(df_empresas)
        total_pages = (total_rows - 1) // page_size + 1
        if "page_empresas" not in st.session_state:
            st.session_state.page_empresas = 1

        col_prev, col_next = st.columns([1, 1])
        with col_prev:
            if st.button("⬅️ Anterior") and st.session_state.page_empresas > 1:
                st.session_state.page_empresas -= 1
        with col_next:
            if st.button("Siguiente ➡️") and st.session_state.page_empresas < total_pages:
                st.session_state.page_empresas += 1

        start_idx = (st.session_state.page_empresas - 1) * page_size
        end_idx = start_idx + page_size
        st.write(f"Página {st.session_state.page_empresas} de {total_pages}")

        # =========================
        # Mostrar empresas
        # =========================
        for _, row in df_empresas.iloc[start_idx:end_idx].iterrows():
            with st.expander(f"{row['nombre']} ({row['cif']})"):
                st.write(f"**Dirección:** {row.get('direccion', '')}")
                st.write(f"**Teléfono:** {row.get('telefono', '')}")
                st.write(f"**Email:** {row.get('email', '')}")
                st.write(f"**Representante:** {row.get('representante_nombre', '')} ({row.get('representante_dni', '')})")
                st.write(f"**Ciudad:** {row.get('ciudad', '')}")
                st.write(f"**Provincia:** {row.get('provincia', '')}")
                st.write(f"**Código Postal:** {row.get('codigo_postal', '')}")
                st.write(f"**Fecha Alta:** {row.get('fecha_alta', '')}")

                col1, col2 = st.columns(2)

                # ✏️ Editar empresa
                if col1.button("✏️ Editar", key=f"edit_{row['id']}"):
                    with st.form(f"edit_form_{row['id']}", clear_on_submit=True):
                        nuevo_nombre = st.text_input("Nombre", value=row["nombre"])
                        nuevo_cif = st.text_input("CIF", value=row["cif"])
                        nueva_direccion = st.text_input("Dirección", value=row.get("direccion", ""))
                        nuevo_telefono = st.text_input("Teléfono", value=row.get("telefono", ""))
                        nuevo_email = st.text_input("Email", value=row.get("email", ""))
                        nuevo_rep_nombre = st.text_input("Nombre del representante", value=row.get("representante_nombre", ""))
                        nuevo_rep_dni = st.text_input("DNI del representante", value=row.get("representante_dni", ""))
                        nueva_ciudad = st.text_input("Ciudad", value=row.get("ciudad", ""))
                        nueva_provincia = st.text_input("Provincia", value=row.get("provincia", ""))
                        nuevo_cp = st.text_input("Código Postal", value=row.get("codigo_postal", ""))

                        guardar = st.form_submit_button("Guardar cambios")
                        if guardar:
                            try:
                                supabase.table("empresas").update({
                                    "nombre": nuevo_nombre,
                                    "cif": nuevo_cif,
                                    "direccion": nueva_direccion,
                                    "telefono": nuevo_telefono,
                                    "email": nuevo_email,
                                    "representante_nombre": nuevo_rep_nombre,
                                    "representante_dni": nuevo_rep_dni,
                                    "ciudad": nueva_ciudad,
                                    "provincia": nueva_provincia,
                                    "codigo_postal": nuevo_cp
                                }).eq("id", row["id"]).execute()
                                st.success("✅ Cambios guardados correctamente.")
                            except Exception as e:
                                st.error(f"❌ Error al actualizar: {str(e)}")

                # 🗑️ Eliminar empresa
                with col2:
                    with st.form(f"delete_form_{row['id']}"):
                        st.warning(f"¿Eliminar empresa '{row['nombre']}'? Esta acción no se puede deshacer.")
                        confirmar = st.checkbox("Confirmo la eliminación")
                        eliminar = st.form_submit_button("🗑️ Eliminar")
                        if eliminar and confirmar:
                            try:
                                supabase.table("empresas").delete().eq("id", row["id"]).execute()
                                st.success("✅ Empresa eliminada.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"❌ Error al eliminar: {str(e)}")
    else:
        st.info("ℹ️ No hay empresas registradas.")

    # =========================
    # Crear nueva empresa
    # =========================
    st.markdown("### ➕ Crear Empresa")
    if "empresa_creada" not in st.session_state:
        st.session_state.empresa_creada = False

    with st.form("crear_empresa", clear_on_submit=True):
        nombre = st.text_input("Nombre *")
        cif = st.text_input("CIF *")
        direccion = st.text_input("Dirección")
        telefono = st.text_input("Teléfono")
        email = st.text_input("Email")
        representante_nombre = st.text_input("Nombre del representante")
        representante_dni = st.text_input("DNI del representante")
        ciudad = st.text_input("Ciudad")
        provincia = st.text_input("Provincia")
        codigo_postal = st.text_input("Código Postal")

        submitted = st.form_submit_button("Crear Empresa")
        if submitted and not st.session_state.empresa_creada:
            if not nombre
                    if submitted and not st.session_state.empresa_creada:
            if not nombre or not cif:
                st.error("⚠️ Los campos 'Nombre' y 'CIF' son obligatorios.")
            else:
                try:
                    # Verificar si ya existe una empresa con ese CIF
                    existe = supabase.table("empresas").select("id").eq("cif", cif).execute()
                    if existe.data:
                        st.error(f"⚠️ Ya existe una empresa con el CIF '{cif}'.")
                    else:
                        supabase.table("empresas").insert({
                            "nombre": nombre,
                            "cif": cif,
                            "direccion": direccion,
                            "telefono": telefono,
                            "email": email,
                            "representante_nombre": representante_nombre,
                            "representante_dni": representante_dni,
                            "ciudad": ciudad,
                            "provincia": provincia,
                            "codigo_postal": codigo_postal,
                            "fecha_alta": datetime.utcnow().isoformat()
                        }).execute()

                        st.session_state.empresa_creada = True
                        st.success(f"✅ Empresa '{nombre}' creada correctamente.")

                        # Recargar datos
                        empresas_res = supabase.table("empresas").select("*").execute()
                        df_empresas = pd.DataFrame(empresas_res.data) if empresas_res.data else pd.DataFrame()
                except Exception as e:
                    st.error(f"❌ Error al crear la empresa: {str(e)}")
                    
