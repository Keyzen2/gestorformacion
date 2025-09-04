import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("📚 Acciones Formativas")

    # =========================
    # Cargar catálogo de áreas profesionales
    # =========================
    try:
        areas_res = supabase.table("areas_profesionales").select("*").order("familia", desc=False).execute()
        areas_dict = {f"{a['codigo']} - {a['nombre']}": a['codigo'] for a in areas_res.data} if areas_res.data else {}
    except Exception as e:
        st.error(f"Error al cargar áreas profesionales: {str(e)}")
        areas_dict = {}

    # =========================
    # Cargar acciones formativas
    # =========================
    try:
        acciones_res = supabase.table("acciones_formativas").select("*").execute()
        df_acciones = pd.DataFrame(acciones_res.data) if acciones_res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar acciones formativas: {str(e)}")
        df_acciones = pd.DataFrame()

    # =========================
    # Botón para ver acciones formativas
    # =========================
    if st.button("📋 Ver Acciones Formativas"):
        if not df_acciones.empty:
            st.dataframe(df_acciones)
        else:
            st.info("No hay acciones formativas registradas.")

    # =========================
    # Búsqueda rápida
    # =========================
    if not df_acciones.empty:
        search_query = st.text_input("🔍 Buscar por nombre, código o área profesional")
        if search_query:
            sq = search_query.lower()
            df_acciones = df_acciones[
                df_acciones["nombre"].str.lower().str.contains(sq) |
                df_acciones["codigo_accion"].str.lower().str.contains(sq) |
                df_acciones["area_profesional"].str.lower().str.contains(sq)
            ]

    # =========================
    # Crear nueva acción formativa
    # =========================
    st.markdown("### ➕ Crear Acción Formativa")

    if "accion_creada" not in st.session_state:
        st.session_state.accion_creada = False

    with st.form("crear_accion_formativa", clear_on_submit=True):
        codigo_accion = st.text_input("Código de la acción *")
        nombre_accion = st.text_input("Nombre de la acción *")
        area_sel = st.selectbox("Área profesional", list(areas_dict.keys()) if areas_dict else [])
        sector = st.text_input("Sector")
        objetivos = st.text_area("Objetivos")
        contenidos = st.text_area("Contenidos")
        nivel = st.selectbox("Nivel", ["Básico", "Intermedio", "Avanzado"])
        modalidad = st.selectbox("Modalidad", ["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)
        certificado_profesionalidad = st.checkbox("¿Certificado de profesionalidad?")
        observaciones = st.text_area("Observaciones")

        submitted = st.form_submit_button("Crear Acción Formativa")

    if submitted and not st.session_state.accion_creada:
        if not codigo_accion or not nombre_accion:
            st.error("⚠️ Código y nombre son obligatorios.")
        else:
            try:
                supabase.table("acciones_formativas").insert({
                    "codigo_accion": codigo_accion,
                    "nombre": nombre_accion,
                    "cod_area_profesional": areas_dict.get(area_sel, ""),
                    "area_profesional": area_sel.split(" - ", 1)[1] if " - " in area_sel else area_sel,
                    "sector": sector,
                    "objetivos": objetivos,
                    "contenidos": contenidos,
                    "nivel": nivel,
                    "modalidad": modalidad,
                    "num_horas": int(num_horas),
                    "certificado_profesionalidad": certificado_profesionalidad,
                    "observaciones": observaciones
                }).execute()

                st.session_state.accion_creada = True
                st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                st.experimental_rerun()

            except Exception as e:
                st.error(f"❌ Error al crear la acción formativa: {str(e)}")

    # =========================
    # Mostrar listado con edición/eliminación
    # =========================
    if not df_acciones.empty:
        for _, row in df_acciones.iterrows():
            with st.expander(f"{row['nombre']} ({row['modalidad']})"):
                st.write(f"**Código:** {row.get('codigo_accion', '')}")
                st.write(f"**Área profesional:** {row.get('area_profesional', '')}")
                st.write(f"**Sector:** {row.get('sector', '')}")
                st.write(f"**Objetivos:** {row.get('objetivos', '')}")
                st.write(f"**Contenidos:** {row.get('contenidos', '')}")
                st.write(f"**Nivel:** {row.get('nivel', '')}")
                st.write(f"**Horas:** {row.get('num_horas', '')}")
                st.write(f"**Certificado profesionalidad:** {'Sí' if row.get('certificado_profesionalidad') else 'No'}")
                st.write(f"**Observaciones:** {row.get('observaciones', '')}")

                col1, col2 = st.columns(2)

                if f"edit_done_{row['id']}" not in st.session_state:
                    st.session_state[f"edit_done_{row['id']}"] = False

                with col1:
                    with st.form(f"edit_form_{row['id']}", clear_on_submit=True):
                        nuevo_codigo = st.text_input("Código de la acción", value=row["codigo_accion"])
                        nuevo_nombre = st.text_input("Nombre", value=row["nombre"])
                        area_actual_key = next((k for k, v in areas_dict.items() if v == row.get("cod_area_profesional")), "")
                        nueva_area_sel = st.selectbox(
                            "Área profesional",
                            list(areas_dict.keys()),
                            index=list(areas_dict.keys()).index(area_actual_key) if area_actual_key in areas_dict else 0
                        )
                        nuevo_sector = st.text_input("Sector", value=row.get("sector", ""))
                        nuevos_objetivos = st.text_area("Objetivos", value=row.get("objetivos", ""))
                        nuevos_contenidos = st.text_area("Contenidos", value=row.get("contenidos", ""))
                        nuevo_nivel = st.selectbox(
                            "Nivel",
                            ["Básico", "Intermedio", "Avanzado"],
                            index=["Básico", "Intermedio", "Avanzado"].index(row.get("nivel", "Básico"))
                        )
                        nueva_modalidad = st.selectbox(
                            "Modalidad",
                            ["Presencial", "Online", "Mixta"],
                            index=["Presencial", "Online", "Mixta"].index(row["modalidad"])
                        )
                        nuevas_horas = st.number_input("Número de horas", min_value=1, value=int(row.get("num_horas", 1)), step=1)
                        nuevo_certificado = st.checkbox("¿Certificado de profesionalidad?", value=row.get("certificado_profesionalidad", False))
                        nuevas_obs = st.text_area("Observaciones", value=row.get("observaciones", ""))

                        guardar_cambios = st.form_submit_button("Guardar cambios")

                    if guardar_cambios and not st.session_state[f"edit_done_{row['id']}"]:
                        try:
                            supabase.table("acciones_formativas").update({
                                "codigo_accion": nuevo_codigo,
                                "nombre": nuevo_nombre,
                                "cod_area_profesional": areas_dict.get(nueva_area_sel, ""),
                                "area_profesional": nueva_area_sel.split(" - ", 1)[1] if " - " in nueva_area_sel else nueva_area_sel,
                                "sector": nuevo_sector,
                                "objetivos": nuevos_objetivos,
                                "contenidos": nuevos_contenidos,
                                "nivel": nuevo_nivel,
                                "modalidad": nueva_modalidad,
                                "num_horas": int(nuevas_horas),
                                "certificado_profesionalidad": nuevo_certificado,
                                "observaciones": nuevas_obs
                            }).eq("id", row["id"]).execute()

                            st.session_state[f"edit_done_{row['id']}"] = True
                            st.success("✅ Cambios guardados correctamente.")
                            st.experimental_rerun()

                        except Exception as e:
                            st.error(f"❌ Error al actualizar: {str(e)}")

                 with col2:
                    if st.button("🗑️ Eliminar", key=f"delete_{row['id']}"):
                        try:
                            supabase.table("acciones_formativas").delete().eq("id", row["id"]).execute()
                            st.success("✅ Acción formativa eliminada correctamente.")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"❌ Error al eliminar: {str(e)}")

                        
