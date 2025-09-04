import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import io

def main(supabase, session_state):
    st.subheader("🏢 Empresas")

    # Solo admin puede gestionar empresas
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden gestionar empresas.")
        st.stop()

    # =========================
    # Cargar empresas
    # =========================
    empresas_res = supabase.table("empresas").select("*").execute()
    df_empresas = pd.DataFrame(empresas_res.data) if empresas_res.data else pd.DataFrame()

    # =========================
    # Filtros
    # =========================
    if not df_empresas.empty:
        search_query = st.text_input("🔍 Buscar por nombre o CIF")
        if search_query:
            df_empresas = df_empresas[
                df_empresas["nombre"].str.contains(search_query, case=False, na=False) |
                df_empresas["cif"].str.contains(search_query, case=False, na=False)
            ]

        # =========================
        # Exportar listado
        # =========================
        st.markdown("### 📤 Exportar listado de empresas")
        col_csv, col_excel = st.columns(2)

        with col_csv:
            st.download_button(
                label="⬇️ Descargar CSV",
                data=df_empresas.to_csv(index=False).encode("utf-8"),
                file_name="empresas_filtradas.csv",
                mime="text/csv"
            )

        with col_excel:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_empresas.to_excel(writer, index=False, sheet_name='Empresas')
                writer.save()
                processed_data = output.getvalue()

            st.download_button(
                label="⬇️ Descargar Excel",
                data=processed_data,
                file_name="empresas_filtradas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # =========================
        # Estadísticas visuales
        # =========================
        st.markdown("### 📈 Estadísticas de Empresas")

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
        page_size = st.selectbox("Registros por página", [5, 10, 20, 50], index=1)
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

                # Editar empresa
                if f"editado_{row['id']}" not in st.session_state:
                    st.session_state[f"editado_{row['id']}"] = False

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
                        if guardar and not st.session_state[f"editado_{row['id']}"]:
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

                                st.session_state[f"editado_{row['id']}"] = True
                                st.success("✅ Cambios guardados correctamente.")
                            except Exception as e:
                                st.error(f"❌ Error al actualizar: {str(e)}")

                # Eliminar empresa
                with st.form(f"delete_form_{row['id']}"):
                    st.warning(f"Vas a eliminar la empresa '{row['nombre']}'. Esta acción no se puede deshacer.")
                    confirmar = st.checkbox("✅ Confirmo que quiero eliminar esta empresa")
                    eliminar = st.form_submit_button("🗑️ Eliminar definitivamente")

                    if eliminar:
                        if confirmar:
                            try:
                                supabase.table("empresas").delete().eq("id", row["id"]).execute()
                                st.success("✅ Empresa eliminada.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"❌ Error al eliminar: {str(e)}")
                        else:
                            st.error("⚠️ Debes marcar la casilla de confirmación antes de eliminar.")
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
            if not nombre or not cif:
                st.error("⚠️ Nombre y CIF son obligatorios.")
            else:
                # Verificar si ya existe una empresa con ese CIF
                existe = supabase.table("empresas").select("id").eq("cif", cif).execute()
                if existe.data:
                    st.error(f"⚠️ Ya existe una empresa con el CIF '{cif}'.")
                else:
                    try:
                        nueva_empresa = {
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
                        }
                        supabase.table("empresas").insert(nueva_empresa).execute()
                        st.session_state.empresa_creada = True
                        st.success(f"✅ Empresa '{nombre}' creada correctamente.")

                        # Recargar datos para que aparezca la nueva empresa
                        empresas_res = supabase.table("empresas").select("*").execute()
                        df_empresas = pd.DataFrame(empresas_res.data) if empresas_res.data else pd.DataFrame()

                    except Exception as e:
                        st.error(f"❌ Error al crear la empresa: {str(e)}")
                        
                                
