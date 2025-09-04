import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("📚 Acciones Formativas")

    # =========================
    # Cargar empresas
    # =========================
    try:
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
    except Exception as e:
        st.error(f"Error al cargar empresas: {str(e)}")
        empresas_dict = {}

    if not empresas_dict:
        st.warning("No hay empresas disponibles. Crea primero una empresa.")
        st.stop()

    # =========================
    # Cargar acciones
    # =========================
    try:
        acciones_res = supabase.table("acciones_formativas").select("*").execute()
        df_acciones = pd.DataFrame(acciones_res.data) if acciones_res.data else pd.DataFrame()

        if not df_acciones.empty:
            for col in ["fecha_inicio", "fecha_fin"]:
                if col in df_acciones.columns:
                    df_acciones[col] = pd.to_datetime(df_acciones[col], errors="coerce").dt.strftime("%d/%m/%Y")
    except Exception as e:
        st.error(f"Error al cargar acciones formativas: {str(e)}")
        df_acciones = pd.DataFrame()

    # =========================
    # Crear nueva acción
    # =========================
    st.markdown("### ➕ Crear Acción Formativa")
    with st.form("crear_accion_formativa"):
        nombre_accion = st.text_input("Nombre de la acción *")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)
        fecha_inicio = st.date_input("Fecha de inicio *")
        fecha_fin = st.date_input("Fecha de fin *")
        empresa_nombre = st.selectbox("Empresa", options=list(empresas_dict.keys()))
        empresa_id = empresas_dict.get(empresa_nombre)

        submitted = st.form_submit_button("Crear Acción Formativa")

        if submitted:
            if not nombre_accion or not empresa_id:
                st.error("⚠️ Nombre y empresa son obligatorios.")
            elif fecha_fin <= fecha_inicio:
                st.error("⚠️ La fecha de fin debe ser posterior a la fecha de inicio.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre_accion,
                        "modalidad": modalidad,
                        "num_horas": int(num_horas),
                        "empresa_id": empresa_id,
                        "fecha_inicio": fecha_inicio.isoformat(),
                        "fecha_fin": fecha_fin.isoformat()
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")

    # =========================
    # Filtro + búsqueda
    # =========================
    if not df_acciones.empty:
        empresa_filter = st.selectbox("Filtrar por empresa", options=["Todas"] + list(empresas_dict.keys()))
        search_query = st.text_input("🔍 Buscar por nombre o modalidad")

        df_filtrado = df_acciones[df_acciones["empresa_id"].notnull()]
        if empresa_filter != "Todas":
            df_filtrado = df_filtrado[df_filtrado["empresa_id"] == empresas_dict[empresa_filter]]

        if search_query:
            sq = search_query.lower()
            df_filtrado = df_filtrado[
                df_filtrado["nombre"].str.lower().str.contains(sq) |
                df_filtrado["modalidad"].str.lower().str.contains(sq)
            ]

        # =========================
        # Paginación
        # =========================
        page_size = st.selectbox("Registros por página", [5, 10, 20, 50], index=1)
        total_rows = len(df_filtrado)
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

        # =========================
        # Mostrar registros con edición/eliminación
        # =========================
        for _, row in df_filtrado.iloc[start_idx:end_idx].iterrows():
            with st.expander(f"{row['nombre']} ({row['modalidad']})"):
                st.write(f"**Horas:** {row.get('num_horas', '')}")
                st.write(f"**Fecha inicio:** {row.get('fecha_inicio', '')}")
                st.write(f"**Fecha fin:** {row.get('fecha_fin', '')}")

                col1, col2 = st.columns(2)

                # Botón editar
                if col1.button("✏️ Editar", key=f"edit_{row['id']}"):
                    with st.form(f"edit_form_{row['id']}"):
                        nuevo_nombre = st.text_input("Nombre", value=row["nombre"])
                        nueva_modalidad = st.selectbox("Modalidad", ["Presencial", "Online", "Mixta"], index=["Presencial", "Online", "Mixta"].index(row["modalidad"]) if row["modalidad"] in ["Presencial", "Online", "Mixta"] else 0)
                        nuevas_horas = st.number_input("Número de horas", min_value=1, value=int(row.get("num_horas", 1)), step=1)
                        nueva_fecha_inicio = st.date_input("Fecha de inicio", value=pd.to_datetime(row["fecha_inicio"], dayfirst=True) if row["fecha_inicio"] else None)
                        nueva_fecha_fin = st.date_input("Fecha de fin", value=pd.to_datetime(row["fecha_fin"], dayfirst=True) if row["fecha_fin"] else None)
                        nueva_empresa = st.selectbox("Empresa", list(empresas_dict.keys()), index=list(empresas_dict.keys()).index(next((k for k,v in empresas_dict.items() if v == row["empresa_id"]), list(empresas_dict.keys())[0])))

                        guardar_cambios = st.form_submit_button("Guardar cambios")
                        if guardar_cambios:
                            if nueva_fecha_fin <= nueva_fecha_inicio:
                                st.error("⚠️ La fecha de fin debe ser posterior a la fecha de inicio.")
                            else:
                                try:
                                    supabase.table("acciones_formativas").update({
                                        "nombre": nuevo_nombre,
                                        "modalidad": nueva_modalidad,
                                        "num_horas": int(nuevas_horas),
                                        "empresa_id": empresas_dict[nueva_empresa],
                                        "fecha_inicio": nueva_fecha_inicio.isoformat(),
                                        "fecha_fin": nueva_fecha_fin.isoformat()
                                    }).eq("id", row["id"]).execute()
                                    st.success("✅ Cambios guardados correctamente.")
                                    st.experimental_rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al actualizar: {str(e)}")

                # Botón eliminar
                if col2.button("🗑️ Eliminar", key=f"delete_{row['id']}"):
                    confirmar = st.checkbox(f"Confirmar eliminación de '{row['nombre']}'", key=f"confirm_{row['id']}")
                    if confirmar:
                        try:
                            supabase.table("acciones_formativas").delete().eq("id", row["id"]).execute()
                            st.success("✅ Acción formativa eliminada.")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"❌ Error al eliminar: {str(e)}")

