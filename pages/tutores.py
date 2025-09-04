import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("👨‍🏫 Tutores")

    # =========================
    # Cargar tutores
    # =========================
    tutores_res = supabase.table("tutores").select("*").execute().data
    df_tutores = pd.DataFrame(tutores_res) if tutores_res else pd.DataFrame()

    # =========================
    # Filtros
    # =========================
    if not df_tutores.empty:
        filtro_nombre = st.text_input("🔍 Buscar por nombre, apellidos o NIF")
        tipo_filter = st.selectbox("Filtrar por tipo", ["Todos", "Interno", "Externo"])

        if filtro_nombre:
            df_tutores = df_tutores[
                df_tutores["nombre"].str.contains(filtro_nombre, case=False, na=False) |
                df_tutores["apellidos"].str.contains(filtro_nombre, case=False, na=False) |
                df_tutores["nif"].str.contains(filtro_nombre, case=False, na=False)
            ]
        if tipo_filter != "Todos":
            df_tutores = df_tutores[df_tutores["tipo_tutor"] == tipo_filter]

        # =========================
        # Paginación
        # =========================
        page_size = st.selectbox("Registros por página", [5, 10, 20, 50], index=1)
        total_rows = len(df_tutores)
        total_pages = (total_rows - 1) // page_size + 1
        if "page_tutores" not in st.session_state:
            st.session_state.page_tutores = 1

        col_prev, col_next = st.columns([1, 1])
        with col_prev:
            if st.button("⬅️ Anterior") and st.session_state.page_tutores > 1:
                st.session_state.page_tutores -= 1
        with col_next:
            if st.button("Siguiente ➡️") and st.session_state.page_tutores < total_pages:
                st.session_state.page_tutores += 1

        start_idx = (st.session_state.page_tutores - 1) * page_size
        end_idx = start_idx + page_size
        st.write(f"Página {st.session_state.page_tutores} de {total_pages}")

        # =========================
        # Mostrar tutores
        # =========================
        for _, row in df_tutores.iloc[start_idx:end_idx].iterrows():
            with st.expander(f"{row['nombre']} {row['apellidos']}"):
                st.write(f"**Email:** {row.get('email', '')}")
                st.write(f"**Teléfono:** {row.get('telefono', '')}")
                st.write(f"**NIF/DNI:** {row.get('nif', '')}")
                st.write(f"**Tipo:** {row.get('tipo_tutor', '')}")
                st.write(f"**Dirección:** {row.get('direccion', '')}")
                st.write(f"**Ciudad:** {row.get('ciudad', '')}")
                st.write(f"**Provincia:** {row.get('provincia', '')}")
                st.write(f"**Código Postal:** {row.get('codigo_postal', '')}")

                col1, col2 = st.columns(2)

                # =========================
                # Editar tutor
                # =========================
                if f"editado_{row['id']}" not in st.session_state:
                    st.session_state[f"editado_{row['id']}"] = False

                if col1.button("✏️ Editar", key=f"edit_{row['id']}"):
                    with st.form(f"edit_form_{row['id']}", clear_on_submit=True):
                        nuevo_nombre = st.text_input("Nombre", value=row["nombre"])
                        nuevos_apellidos = st.text_input("Apellidos", value=row["apellidos"])
                        nuevo_email = st.text_input("Email", value=row.get("email", ""))
                        nuevo_telefono = st.text_input("Teléfono", value=row.get("telefono", ""))
                        nuevo_nif = st.text_input("NIF/DNI", value=row.get("nif", ""))
                        nuevo_tipo = st.selectbox("Tipo de Tutor", ["Interno", "Externo"], index=["Interno", "Externo"].index(row.get("tipo_tutor", "Interno")))
                        nueva_direccion = st.text_input("Dirección", value=row.get("direccion", ""))
                        nueva_ciudad = st.text_input("Ciudad", value=row.get("ciudad", ""))
                        nueva_provincia = st.text_input("Provincia", value=row.get("provincia", ""))
                        nuevo_cp = st.text_input("Código Postal", value=row.get("codigo_postal", ""))

                        guardar = st.form_submit_button("Guardar cambios")
                        if guardar and not st.session_state[f"editado_{row['id']}"]:
                            try:
                                supabase.table("tutores").update({
                                    "nombre": nuevo_nombre,
                                    "apellidos": nuevos_apellidos,
                                    "email": nuevo_email,
                                    "telefono": nuevo_telefono,
                                    "nif": nuevo_nif,
                                    "tipo_tutor": nuevo_tipo,
                                    "direccion": nueva_direccion,
                                    "ciudad": nueva_ciudad,
                                    "provincia": nueva_provincia,
                                    "codigo_postal": nuevo_cp
                                }).eq("id", row["id"]).execute()

                                st.session_state[f"editado_{row['id']}"] = True
                                st.success("✅ Cambios guardados correctamente.")
                            except Exception as e:
                                st.error(f"❌ Error al actualizar: {str(e)}")

                # =========================
                # Eliminar tutor
                # =========================
                with st.form(f"delete_form_{row['id']}"):
                    st.warning(f"Vas a eliminar al tutor '{row['nombre']} {row['apellidos']}'. Esta acción no se puede deshacer.")
                    confirmar = st.checkbox("✅ Confirmo que quiero eliminar este tutor")
                    eliminar = st.form_submit_button("🗑️ Eliminar definitivamente")

                    if eliminar:
                        if confirmar:
                            try:
                                supabase.table("tutores").delete().eq("id", row["id"]).execute()
                                st.success("✅ Tutor eliminado.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"❌ Error al eliminar: {str(e)}")
                        else:
                            st.error("⚠️ Debes marcar la casilla de confirmación antes de eliminar.")

