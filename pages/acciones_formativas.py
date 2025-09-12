import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv

def main(supabase, session_state):
    st.subheader("📚 Acciones Formativas")

    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar áreas profesionales
    # =========================
    try:
        areas_res = (
            supabase
            .table("areas_profesionales")
            .select("*")
            .order("familia", desc=False)
            .execute()
        )
        areas_dict = {
            f"{a.get('codigo','')} - {a.get('nombre','')}": a.get("codigo","")
            for a in (areas_res.data or [])
        }
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las áreas profesionales: {e}")
        areas_dict = {}

    # =========================
    # Cargar grupos de acciones
    # =========================
    try:
        grupos_acciones_res = supabase.table("grupos_acciones").select("*").execute()
        grupos_acciones_data = grupos_acciones_res.data or []
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos de acciones: {e}")
        grupos_acciones_data = []

    # =========================
    # Cargar acciones formativas
    # =========================
    try:
        acciones_res = (
            supabase
            .table("acciones_formativas")
            .select("*")
            .eq("empresa_id", empresa_id)
            .execute()
        )
        df_acciones = pd.DataFrame(acciones_res.data or [])
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las acciones formativas: {e}")
        df_acciones = pd.DataFrame()

    # =========================
    # Métricas de Acciones
    # =========================
    col1, col2 = st.columns(2)
    col1.metric("Total Acciones Formativas", len(df_acciones))
    col2.metric(
        "Nuevas este mes",
        len(
            df_acciones[
                pd.to_datetime(df_acciones.get("fecha_creacion"), errors="coerce")
                .dt.month
                == datetime.now().month
            ]
        ) if not df_acciones.empty else 0,
    )
    st.divider()

    # =========================
    # 🔍 Buscar y exportar CSV
    # =========================
    st.markdown("### 🔍 Buscar y Exportar")
    query = st.text_input("Buscar por nombre, código o área profesional")
    df_fil = df_acciones.copy()
    if query:
        sq = query.lower()
        df_fil = df_fil[
            df_fil.get("nombre", pd.Series(dtype=str)).str.lower().str.contains(sq, na=False) |
            df_fil.get("codigo_accion", pd.Series(dtype=str)).str.lower().str.contains(sq, na=False) |
            df_fil.get("area_profesional", pd.Series(dtype=str)).str.lower().str.contains(sq, na=False)
        ]
    if not df_fil.empty:
        export_csv(df_fil, filename="acciones_formativas.csv")
        st.dataframe(df_fil)
    else:
        st.info("ℹ️ No hay acciones para mostrar.")
    st.divider()

    # =========================
    # ➕ Crear nueva Acción Formativa
    # =========================
    st.markdown("### ➕ Crear Acción Formativa")
    if "accion_creada" not in st.session_state:
        st.session_state.accion_creada = False

    with st.form("crear_accion_formativa", clear_on_submit=True):
        codigo_accion    = st.text_input("Código de la acción *")
        nombre_accion    = st.text_input("Nombre de la acción *")
        area_sel         = st.selectbox(
            "Área profesional",
            list(areas_dict.keys()) if areas_dict else []
        )
        cod_area         = areas_dict.get(area_sel, "")
        grupos_filtrados = [g for g in grupos_acciones_data if g["cod_area_profesional"] == cod_area]
        grupos_dict      = {g["nombre"]: g["codigo"] for g in grupos_filtrados}
        grupo_accion_sel = st.selectbox(
            "Grupo de acciones",
            list(grupos_dict.keys()) if grupos_dict else ["No disponible"]
        )

        # Campos adicionales según XSD / exportación Fundae
        sector                       = st.text_input("Sector")
        objetivos                     = st.text_area("Objetivos")
        contenidos                    = st.text_area("Contenidos")
        nivel                         = st.selectbox("Nivel", ["Básico", "Intermedio", "Avanzado"])
        modalidad                     = st.selectbox("Modalidad", ["Presencial", "Online", "Mixta"])
        num_horas                     = st.number_input("Número de horas", min_value=1, value=1, step=1)
        duracion_horas                 = st.number_input("Duración total horas (opcional)", min_value=0, value=0, step=1)
        certificado_profesionalidad   = st.checkbox("¿Certificado de profesionalidad?")
        certificado                    = st.text_input("Certificado (opcional)")
        observaciones                 = st.text_area("Observaciones")
        submitted                     = st.form_submit_button("Crear Acción Formativa")

    if submitted and not st.session_state.accion_creada:
        if not codigo_accion or not nombre_accion:
            st.error("⚠️ Código y nombre son obligatorios.")
        else:
            try:
                supabase.table("acciones_formativas").insert({
                    "codigo_accion":              codigo_accion,
                    "nombre":                     nombre_accion,
                    "cod_area_profesional":       cod_area,
                    "area_profesional":           area_sel.split(" - ", 1)[1] if " - " in area_sel else area_sel,
                    "codigo_grupo_accion":        grupos_dict.get(grupo_accion_sel, ""),
                    "sector":                     sector,
                    "objetivos":                  objetivos,
                    "contenidos":                 contenidos,
                    "nivel":                      nivel,
                    "modalidad":                  modalidad,
                    "num_horas":                  int(num_horas),
                    "duracion_horas":             int(duracion_horas),
                    "certificado_profesionalidad": certificado_profesionalidad,
                    "certificado":                certificado,
                    "observaciones":              observaciones,
                    "empresa_id":                 empresa_id,
                    "fecha_creacion":             datetime.utcnow()
                }).execute()
                st.session_state.accion_creada = True
                st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al crear la acción formativa: {e}")
    st.divider()

    # =========================
    # 📋 Listado, edición y eliminación
    # =========================
    if not df_acciones.empty:
        for _, row in df_acciones.iterrows():
            with st.expander(f"{row.get('nombre','')} ({row.get('modalidad','')})"):
                for campo in [
                    "codigo_accion", "area_profesional", "codigo_grupo_accion",
                    "sector", "objetivos", "contenidos", "nivel", "num_horas",
                    "duracion_horas", "certificado_profesionalidad", "certificado",
                    "observaciones"
                ]:
                    st.write(f"**{campo.replace('_',' ').capitalize()}:** {row.get(campo, '')}")

                col1, col2 = st.columns(2)
                key_done  = f"edit_done_{row['id']}"
                if key_done not in st.session_state:
                    st.session_state[key_done] = False

                # Formulario de edición
                with col1:
                    with st.form(f"edit_form_{row['id']}", clear_on_submit=True):
                        nuevo_codigo       = st.text_input("Código de la acción", value=row.get("codigo_accion",""))
                        nuevo_nombre       = st.text_input("Nombre", value=row.get("nombre",""))
                        area_actual_key    = next((k for k,v in areas_dict.items() if v == row.get("cod_area_profesional")), "")
                        nueva_area_sel     = st.selectbox(
                            "Área profesional",
                            list(areas_dict.keys()),
                            index=list(areas_dict.keys()).index(area_actual_key) if area_actual_key in areas_dict else 0
                        )
                        cod_area_actual    = areas_dict.get(nueva_area_sel, "")
                        grupos_filtrados   = [g for g in grupos_acciones_data if g["cod_area_profesional"] == cod_area_actual]
                        grupos_dict        = {g["nombre"]: g["codigo"] for g in grupos_filtrados}
                        grupo_actual_key   = next((k for k,v in grupos_dict.items() if v == row.get("codigo_grupo_accion")), "")
                        nuevo_grupo_accion_sel = st.selectbox(
                            "Grupo de acciones",
                            list(grupos_dict.keys()),
                            index=list(grupos_dict.keys()).index(grupo_actual_key) if grupo_actual_key in grupos_dict else 0
                        )

                        # Campos adicionales
                        nuevo_sector       = st.text_input("Sector", value=row.get("sector",""))
                        nuevos_objetivos   = st.text_area("Objetivos", value=row.get("objetivos",""))
                        nuevos_contenidos  = st.text_area("Contenidos", value=row.get("contenidos",""))
                        nuevo_nivel        = st.selectbox("Nivel", ["Básico", "Intermedio", "Avanzado"], index=["Básico","Intermedio","Avanzado"].index(row.get("nivel","Básico")))
                        nueva_modalidad    = st.selectbox("Modalidad", ["Presencial","Online","Mixta"], index=["Presencial","Online","Mixta"].index(row.get("modalidad","Presencial")))
                        nuevas_horas       = st.number_input("Número de horas", min_value=1, value=int(row.get("num_horas",1)), step=1)
                        nueva_duracion     = st.number_input("Duración total horas (opcional)", min_value=0, value=int(row.get("duracion_horas",0)), step=1)
                        nuevo_certificado  = st.checkbox("¿Certificado de profesionalidad?", value=row.get("certificado_profesionalidad", False))
                        nuevo_certificado_text = st.text_input("Certificado (opcional)", value=row.get("certificado",""))
                        nuevas_obs         = st.text_area("Observaciones", value=row.get("observaciones",""))
                        guardar_cambios    = st.form_submit_button("Guardar cambios")

                if guardar_cambios and not st.session_state[key_done]:
                    try:
                        supabase.table("acciones_formativas").update({
                            "codigo_accion":              nuevo_codigo,
                            "nombre":                     nuevo_nombre,
                            "cod_area_profesional":       areas_dict.get(nueva_area_sel,""),
                            "area_profesional":           nueva_area_sel.split(" - ",1)[1] if " - " in nueva_area_sel else nueva_area_sel,
                            "codigo_grupo_accion":        grupos_dict.get(nuevo_grupo_accion_sel,""),
                            "sector":                     nuevo_sector,
                            "objetivos":                  nuevos_objetivos,
                            "contenidos":                 nuevos_contenidos,
                            "nivel":                      nuevo_nivel,
                            "modalidad":                  nueva_modalidad,
                            "num_horas":                  int(nuevas_horas),
                            "duracion_horas":             int(nueva_duracion),
                            "certificado_profesionalidad": nuevo_certificado,
                            "certificado":                nuevo_certificado_text,
                            "observaciones":              nuevas_obs,
                            "empresa_id":                 empresa_id
                        }).eq("id", row["id"]).execute()
                        st.session_state[key_done] = True
                        st.success("✅ Cambios guardados correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al actualizar: {e}")

                # Botón de eliminación
                with col2:
                    if st.button("🗑️ Eliminar", key=f"delete_{row['id']}"):
                        try:
                            supabase.table("acciones_formativas").delete().eq("id", row["id"]).execute()
                            st.success("✅ Acción formativa eliminada correctamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al eliminar: {e}")
