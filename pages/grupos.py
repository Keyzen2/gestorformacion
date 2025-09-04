import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("👥 Grupos")

    # =========================
    # Cargar empresas
    # =========================
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
    if not empresas_dict:
        st.warning("No hay empresas disponibles. Crea primero una empresa.")
        st.stop()

    # =========================
    # Cargar acciones formativas
    # =========================
    acciones_res = supabase.table("acciones_formativas").select("id, nombre").execute()
    acciones_dict = {a["nombre"]: a["id"] for a in acciones_res.data} if acciones_res.data else {}

    # =========================
    # Cargar tutores
    # =========================
    tutores_res = supabase.table("tutores").select("id, nombre, apellidos").execute()
    tutores_dict = {f"{t['nombre']} {t['apellidos']}": t["id"] for t in tutores_res.data} if tutores_res.data else {}

    # =========================
    # Cargar grupos
    # =========================
    grupos_res = supabase.table("grupos").select("*").execute()
    df_grupos = pd.DataFrame(grupos_res.data) if grupos_res.data else pd.DataFrame()

    # =========================
    # Filtros y búsqueda
    # =========================
    if not df_grupos.empty:
        empresa_filter = st.selectbox("Filtrar por empresa", ["Todas"] + list(empresas_dict.keys()))
        accion_filter = st.selectbox("Filtrar por acción formativa", ["Todas"] + list(acciones_dict.keys()))
        search_query = st.text_input("🔍 Buscar por código de grupo")

        if empresa_filter != "Todas":
            df_grupos = df_grupos[df_grupos["empresa_id"] == empresas_dict[empresa_filter]]
        if accion_filter != "Todas":
            df_grupos = df_grupos[df_grupos["accion_formativa_id"] == acciones_dict[accion_filter]]
        if search_query:
            df_grupos = df_grupos[df_grupos["codigo_grupo"].str.contains(search_query, case=False, na=False)]

        # Paginación
        page_size = st.selectbox("Registros por página", [5, 10, 20, 50], index=1)
        total_rows = len(df_grupos)
        total_pages = (total_rows - 1) // page_size + 1
        if "page_number" not in st.session_state:
            st.session_state.page_number = 1

        col_prev, col_next = st.columns([1, 1])
        with col_prev:
            if st.button("⬅️ Anterior") and st.session_state.page_number > 1:
                st.session_state.page_number -= 1
        with col_next:
            if st.button("Siguiente ➡️") and st.session_state.page_number < total_pages:
                st.session_state.page_number += 1

        start_idx = (st.session_state.page_number - 1) * page_size
        end_idx = start_idx + page_size
        st.write(f"Página {st.session_state.page_number} de {total_pages}")

        # Mostrar grupos
        for _, row in df_grupos.iloc[start_idx:end_idx].iterrows():
            with st.expander(f"{row['codigo_grupo']}"):
                st.write(f"**Empresa:** {next((k for k,v in empresas_dict.items() if v == row['empresa_id']), '')}")
                st.write(f"**Acción formativa:** {next((k for k,v in acciones_dict.items() if v == row['accion_formativa_id']), '')}")
                st.write(f"**Fecha inicio:** {row.get('fecha_inicio', '')}")
                st.write(f"**Fecha fin:** {row.get('fecha_fin', '')}")

                col1, col2 = st.columns(2)

                # Editar grupo
                if col1.button("✏️ Editar", key=f"edit_{row['id']}"):
                    with st.form(f"edit_form_{row['id']}"):
                        nuevo_codigo = st.text_input("Código Grupo", value=row["codigo_grupo"])
                        nueva_empresa = st.selectbox("Empresa", list(empresas_dict.keys()),
                                                     index=list(empresas_dict.keys()).index(next((k for k,v in empresas_dict.items() if v == row["empresa_id"]), list(empresas_dict.keys())[0])))
                        nueva_accion = st.selectbox("Acción Formativa", list(acciones_dict.keys()),
                                                    index=list(acciones_dict.keys()).index(next((k for k,v in acciones_dict.items() if v == row["accion_formativa_id"]), list(acciones_dict.keys())[0])))
                        nueva_fecha_inicio = st.date_input("Fecha Inicio", pd.to_datetime(row["fecha_inicio"], errors="coerce") if row["fecha_inicio"] else None)
                        nueva_fecha_fin = st.date_input("Fecha Fin", pd.to_datetime(row["fecha_fin"], errors="coerce") if row["fecha_fin"] else None)
                        nuevos_tutores = st.multiselect("Tutores", list(tutores_dict.keys()))

                        guardar = st.form_submit_button("Guardar cambios")
                        if guardar:
                            if nueva_fecha_fin < nueva_fecha_inicio:
                                st.error("⚠️ La fecha de fin no puede ser anterior a la de inicio.")
                            else:
                                try:
                                    supabase.table("grupos").update({
                                        "codigo_grupo": nuevo_codigo,
                                        "empresa_id": empresas_dict[nueva_empresa],
                                        "accion_formativa_id": acciones_dict[nueva_accion],
                                        "fecha_inicio": nueva_fecha_inicio.isoformat(),
                                        "fecha_fin": nueva_fecha_fin.isoformat()
                                    }).eq("id", row["id"]).execute()

                                    # Actualizar tutores
                                    supabase.table("tutores_grupos").delete().eq("grupo_id", row["id"]).execute()
                                    for t in nuevos_tutores:
                                        supabase.table("tutores_grupos").insert({
                                            "grupo_id": row["id"],
                                            "tutor_id": tutores_dict[t]
                                        }).execute()

                                    st.success("✅ Grupo actualizado correctamente.")
                                    st.experimental_rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al actualizar: {str(e)}")

                # Eliminar grupo
                if col2.button("🗑️ Eliminar", key=f"delete_{row['id']}"):
                    confirmar = st.checkbox(f"Confirmar eliminación de '{row['codigo_grupo']}'", key=f"confirm_{row['id']}")
                    if confirmar:
                        try:
                            supabase.table("grupos").delete().eq("id", row["id"]).execute()
                            st.success("✅ Grupo eliminado.")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"❌ Error al eliminar: {str(e)}")

    # =========================
    # Crear nuevo grupo (solo admin)
    # =========================
    if session_state.role == "admin":
        st.markdown("### ➕ Crear Grupo")
        with st.form("crear_grupo"):
            empresa_nombre = st.selectbox("Empresa", list(empresas_dict.keys()))
            accion_nombre = st.selectbox("Acción Formativa", list(acciones_dict.keys()) if acciones_dict else ["No hay acciones"])
            tutores_seleccionados = st.multiselect("Selecciona Tutores", list(tutores_dict.keys()))
            codigo_grupo = st.text_input("Código Grupo *")
            fecha_inicio = st.date_input("Fecha Inicio")
            fecha_fin = st.date_input("Fecha Fin")
            submitted = st.form_submit_button("Crear Grupo")

            if submitted:
                if not codigo_grupo or not empresa_nombre or not accion_nombre:
                    st.error("⚠️ Código, empresa y acción formativa son obligatorios.")
                elif fecha_fin < fecha_inicio:
                    st.error("⚠️ La fecha de fin no puede ser anterior a la de inicio.")
                else:
                    try:
                        result = supabase.table("grupos").insert({
                            "codigo_grupo": codigo_grupo,
                            "fecha_inicio": fecha_inicio.isoformat(),
                            "fecha_fin": fecha_fin.isoformat(),
                            "empresa_id": empresas_dict[empresa_nombre],
                            "accion_formativa_id": acciones_dict[accion_nombre]
                        }).execute()
                        grupo_id = result.data[0]["id"]

                        for t in tutores_seleccionados:
                            supabase.table("tutores_grupos").insert({
                                "grupo_id": grupo_id,
                                "tutor_id": tutores_dict[t]
                            }).execute()

                        st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"❌ Error al crear el grupo: {str(e)}")
    else:
        st.info("🔒 Solo los administradores pueden crear nuevos grupos.")
