import streamlit as st
import pandas as pd
from utils import export_csv, validar_dni_cif

def main(supabase, session_state):
    st.subheader("👨‍🏫 Tutores")
    st.caption("Gestión de tutores internos y externos vinculados a grupos formativos.")
    st.divider()

    # Permisos
    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    if "page_tutores" not in st.session_state:
        st.session_state.page_tutores = 1

    # =========================
    # Cargar tutores
    # =========================
    try:
        if session_state.role == "gestor":
            tutores_res = supabase.table("tutores")\
                                   .select("*")\
                                   .eq("empresa_id", session_state.user.get("empresa_id"))\
                                   .execute().data
        else:
            tutores_res = supabase.table("tutores").select("*").execute().data

        df_tutores = pd.DataFrame(tutores_res) if tutores_res else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error al cargar tutores: {e}")
        return

    # =========================
    # Exportar CSV completo
    # =========================
    if not df_tutores.empty:
        export_csv(df_tutores, filename="tutores.csv")
        st.divider()

    # =========================
    # Filtros
    # =========================
    if not df_tutores.empty:
        st.markdown("### 🔍 Filtros")
        filtro_nombre = st.text_input("Buscar por nombre, apellidos o NIF")
        tipo_filter   = st.selectbox("Filtrar por tipo", ["Todos", "Interno", "Externo"])

        if filtro_nombre:
            sq = filtro_nombre.lower()
            df_tutores = df_tutores[
                df_tutores["nombre"].str.lower().str.contains(sq, na=False) |
                df_tutores["apellidos"].str.lower().str.contains(sq, na=False) |
                df_tutores["nif"].str.lower().str.contains(sq, na=False)
            ]
        if tipo_filter != "Todos":
            df_tutores = df_tutores[df_tutores["tipo_tutor"] == tipo_filter]

        if filtro_nombre or tipo_filter != "Todos":
            st.session_state.page_tutores = 1

        st.divider()
        st.markdown("### 📄 Listado de Tutores")

        # =========================
        # Paginación
        # =========================
        page_size   = st.selectbox("Registros por página", [5, 10, 20, 50], index=1)
        total_rows  = len(df_tutores)
        total_pages = (total_rows - 1) // page_size + 1
        page_actual = st.session_state.page_tutores

        col_prev, col_next = st.columns([1, 1])
        with col_prev:
            if st.button("⬅️ Anterior") and page_actual > 1:
                st.session_state.page_tutores -= 1
        with col_next:
            if st.button("Siguiente ➡️") and page_actual < total_pages:
                st.session_state.page_tutores += 1

        start_idx = (st.session_state.page_tutores - 1) * page_size
        end_idx   = start_idx + page_size
        st.caption(f"Página {st.session_state.page_tutores} de {total_pages}")

        # =========================
        # Cargar grupos asignados en bloque
        # =========================
        try:
            tutor_ids = df_tutores["id"].tolist()
            tg_res = supabase.table("tutores_grupos")\
                             .select("tutor_id,grupo_id")\
                             .in_("tutor_id", tutor_ids)\
                             .execute().data or []
            grupos_ids = list({tg["grupo_id"] for tg in tg_res})
            grupos_info = supabase.table("grupos")\
                                   .select("id,codigo_grupo")\
                                   .in_("id", grupos_ids)\
                                   .execute().data or []
            grupos_dict = {g["id"]: g["codigo_grupo"] for g in grupos_info}
            grupos_por_tutor = {}
            for tg in tg_res:
                grupos_por_tutor.setdefault(tg["tutor_id"], []).append(grupos_dict.get(tg["grupo_id"], ""))
        except Exception as e:
            st.error(f"❌ Error al cargar grupos asignados: {e}")
            grupos_por_tutor = {}

        # =========================
        # Visualización y edición
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

                # Mostrar grupos asignados
                grupos_asignados = grupos_por_tutor.get(row["id"], [])
                if grupos_asignados:
                    st.write("**Grupos asignados:**")
                    for g in grupos_asignados:
                        st.markdown(f"- {g}")
                else:
                    st.write("**Grupos asignados:** Ninguno")

                col1, col2 = st.columns(2)

                # Formulario de edición
                with col1:
                    with st.form(f"edit_form_{row['id']}", clear_on_submit=True):
                        nuevo_nombre     = st.text_input("Nombre", value=row["nombre"])
                        nuevos_apellidos = st.text_input("Apellidos", value=row["apellidos"])
                        nuevo_email      = st.text_input("Email", value=row.get("email", ""))
                        nuevo_telefono   = st.text_input("Teléfono", value=row.get("telefono", ""))
                        nuevo_nif        = st.text_input("NIF/DNI", value=row.get("nif", ""))
                        tipos            = ["Interno", "Externo"]
                        tipo_actual      = row.get("tipo_tutor") if row.get("tipo_tutor") in tipos else "Interno"
                        nuevo_tipo       = st.selectbox("Tipo de Tutor", tipos, index=tipos.index(tipo_actual))
                        nueva_direccion  = st.text_input("Dirección", value=row.get("direccion", ""))
                        nueva_ciudad     = st.text_input("Ciudad", value=row.get("ciudad", ""))
                        nueva_provincia  = st.text_input("Provincia", value=row.get("provincia", ""))
                        nuevo_cp         = st.text_input("Código Postal", value=row.get("codigo_postal", ""))
                        guardar = st.form_submit_button("💾 Guardar cambios")
                    if guardar:
                        if nuevo_nif and not validar_dni_cif(nuevo_nif):
                            st.error("⚠️ NIF/DNI inválido.")
                        else:
                            try:
                                supabase.table("tutores").update({
                                    "nombre":       nuevo_nombre,
                                    "apellidos":    nuevos_apellidos,
                                    "email":        nuevo_email,
                                    "telefono":     nuevo_telefono,
                                    "nif":          nuevo_nif,
                                    "tipo_tutor":   nuevo_tipo,
                                    "direccion":    nueva_direccion,
                                    "ciudad":       nueva_ciudad,
                                    "provincia":    nueva_provincia,
                                    "codigo_postal": nuevo_cp
                                }).eq("id", row["id"]).execute()
                                st.success("✅ Cambios guardados correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al actualizar: {e}")

                # Formulario de eliminación
                with col2:
                    with st.form(f"delete_form_{row['id']}", clear_on_submit=True):
                        st.warning(
                            f"⚠️ Vas a eliminar al tutor "
                            f"'{row['nombre']} {row['apellidos']}'. "
                            "Esta acción no se puede deshacer."
                        )
                        confirmar = st.checkbox("✅ Confirmo que quiero eliminar este tutor")
                        eliminar  = st.form_submit_button("🗑️ Eliminar definitivamente")

                    if eliminar and confirmar:
                        try:
                            # Eliminar asignaciones primero
                            supabase.table("tutores_grupos").delete().eq("tutor_id", row["id"]).execute()
                                                        # Eliminar tutor
                            supabase.table("tutores").delete().eq("id", row["id"]).execute()
                            st.success("✅ Tutor eliminado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al eliminar: {e}")

    else:
        st.info("ℹ️ No hay tutores registrados.")
