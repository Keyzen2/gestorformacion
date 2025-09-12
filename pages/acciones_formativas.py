import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.subheader("📚 Acciones Formativas")
    st.caption("Gestión de acciones formativas y configuración de cursos.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    data_service = get_data_service(supabase, session_state)

    # =========================
    # Cargar datos
    # =========================
    with st.spinner("Cargando datos..."):
        df_acciones = data_service.get_acciones_formativas()
        areas_dict = data_service.get_areas_dict()
        grupos_acciones_df = data_service.get_grupos_acciones()

    # =========================
    # Filtrar acciones por empresa (gestor)
    # =========================
    empresa_id = session_state.user.get("empresa_id")
    df_acciones = data_service.get_acciones_formativas()

    if session_state.role == "gestor":
        df_acciones = df_acciones[df_acciones["empresa_id"] == empresa_id]

    # Mensaje si no hay acciones
    if df_acciones.empty:
        st.info("No hay acciones formativas para esta empresa todavía. Puedes crear una nueva acción.")
    else:
        st.markdown("### Acciones formativas disponibles")
        st.dataframe(df_acciones)

    # Botón para crear nueva acción
    if session_state.role == "gestor" or data_service.can_modify_data():
        if st.button("➕ Crear nueva acción formativa"):
            st.session_state.creando_accion = True

    # =========================
    # Métricas
    # =========================
    if not df_filtered.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📚 Total Acciones", len(df_filtered))
        with col2:
            if "fecha_creacion" in df_filtered.columns:
                este_mes = df_filtered[
                    pd.to_datetime(df_filtered["fecha_creacion"], errors="coerce").dt.month == datetime.now().month
                ]
                st.metric("🆕 Nuevas este mes", len(este_mes))
            else:
                st.metric("🆕 Nuevas este mes", 0)
        with col3:
            if "modalidad" in df_filtered.columns:
                modalidad_top = df_filtered["modalidad"].value_counts().idxmax() if len(df_filtered) > 0 else "N/A"
                st.metric("📊 Modalidad principal", modalidad_top)
            else:
                st.metric("📊 Modalidad principal", "N/A")

    st.divider()

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("🔍 Buscar por nombre o código")
    with col2:
        modalidad_filter = st.selectbox(
            "Filtrar por modalidad", 
            ["Todas", "Presencial", "Online", "Mixta"]
        )

    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered.get("nombre", pd.Series(dtype=str)).str.lower().str.contains(q_lower, na=False) |
            df_filtered.get("codigo_accion", pd.Series(dtype=str)).str.lower().str.contains(q_lower, na=False) |
            df_filtered.get("area_profesional", pd.Series(dtype=str)).str.lower().str.contains(q_lower, na=False)
        ]
    if modalidad_filter != "Todas" and "modalidad" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["modalidad"] == modalidad_filter]

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_accion(accion_id, datos_editados):
        try:
            if "area_profesional_sel" in datos_editados:
                area_sel = datos_editados.pop("area_profesional_sel")
                datos_editados["cod_area_profesional"] = areas_dict.get(area_sel, "")
                datos_editados["area_profesional"] = area_sel.split(" - ", 1)[1] if " - " in area_sel else area_sel

            if "grupo_accion_sel" in datos_editados:
                grupo_sel = datos_editados.pop("grupo_accion_sel")
                cod_area = datos_editados.get("cod_area_profesional", "")
                grupos_filtrados = grupos_acciones_df[
                    grupos_acciones_df["cod_area_profesional"] == cod_area
                ]
                grupos_dict = {g["nombre"]: g["codigo"] for _, g in grupos_filtrados.iterrows()}
                datos_editados["codigo_grupo_accion"] = grupos_dict.get(grupo_sel, "")

            ini = datos_editados.get("fecha_inicio")
            fin = datos_editados.get("fecha_fin")
            if ini and fin and ini > fin:
                st.error("⚠️ La fecha de inicio no puede ser posterior a la fecha de fin.")
                return

            success = data_service.update_accion_formativa(accion_id, datos_editados)
            if success:
                st.success("✅ Acción formativa actualizada correctamente.")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar: {e}")

    def crear_accion(datos_nuevos):
        try:
            if not datos_nuevos.get("codigo_accion") or not datos_nuevos.get("nombre"):
                st.error("⚠️ Código y nombre son obligatorios.")
                return

            if "area_profesional_sel" in datos_nuevos:
                area_sel = datos_nuevos.pop("area_profesional_sel")
                datos_nuevos["cod_area_profesional"] = areas_dict.get(area_sel, "")
                datos_nuevos["area_profesional"] = area_sel.split(" - ", 1)[1] if " - " in area_sel else area_sel

            if "grupo_accion_sel" in datos_nuevos:
                grupo_sel = datos_nuevos.pop("grupo_accion_sel")
                cod_area = datos_nuevos.get("cod_area_profesional", "")
                grupos_filtrados = grupos_acciones_df[
                    grupos_acciones_df["cod_area_profesional"] == cod_area
                ]
                grupos_dict = {g["nombre"]: g["codigo"] for _, g in grupos_filtrados.iterrows()}
                datos_nuevos["codigo_grupo_accion"] = grupos_dict.get(grupo_sel, "")

            if session_state.role == "gestor":
                datos_nuevos["empresa_id"] = empresa_id

            ini = datos_nuevos.get("fecha_inicio")
            fin = datos_nuevos.get("fecha_fin")
            if ini and fin and ini > fin:
                st.error("⚠️ La fecha de inicio no puede ser posterior a la fecha de fin.")
                return

            success = data_service.create_accion_formativa(datos_nuevos)
            if success:
                st.success("✅ Acción formativa creada correctamente.")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error al crear: {e}")

    # =========================
    # Campos dinámicos - SOLO CAMPOS REALES
    # =========================
    def get_campos_dinamicos(datos):
        campos = [
            "codigo_accion", "nombre", "descripcion", "objetivos", "contenidos",
            "requisitos", "horas", "num_horas", "modalidad", "fecha_inicio",
            "fecha_fin", "area_profesional", "nivel", "certificado_profesionalidad",
            "cod_area_profesional", "sector", "codigo_grupo_accion", "observaciones"
        ]
        return campos

    campos_select = {
        "nivel": ["Básico", "Intermedio", "Avanzado"],
        "modalidad": ["Presencial", "Online", "Mixta"],
        "certificado_profesionalidad": [True, False],
        "area_profesional_sel": list(areas_dict.keys()) if areas_dict else ["No disponible"]
    }

    campos_textarea = {
        "descripcion": {"label": "Descripción de la acción"},
        "objetivos": {"label": "Objetivos del curso"},
        "contenidos": {"label": "Contenidos temáticos"},
        "requisitos": {"label": "Requisitos de acceso"},
        "observaciones": {"label": "Observaciones adicionales"}
    }

    campos_help = {
        "codigo_accion": "Código único de la acción formativa (obligatorio)",
        "nombre": "Denominación completa de la acción formativa (obligatorio)",
        "descripcion": "Descripción detallada de la acción",
        "horas": "Número de horas de la acción formativa",
        "num_horas": "Duración en horas (campo alternativo)",
        "modalidad": "Modalidad de impartición",
        "nivel": "Nivel de dificultad (Básico, Intermedio, Avanzado)",
        "certificado_profesionalidad": "Indica si es un certificado de profesionalidad",
        "sector": "Sector profesional al que se dirige",
        "area_profesional": "Área profesional de la acción"
    }

    # =========================
    # Mostrar listado
    # =========================
    if df_filtered.empty:
        st.info("ℹ️ No hay acciones formativas para mostrar.")
        if allow_creation:
            st.markdown("### ➕ Crear primera acción formativa")
    else:
        df_display = df_filtered.copy()
        if "cod_area_profesional" in df_display.columns:
            df_display["area_profesional_sel"] = df_display.apply(
                lambda row: next(
                    (k for k, v in areas_dict.items() if v == row.get("cod_area_profesional")),
                    row.get("area_profesional", "")
                ), axis=1
            )

        if "codigo_grupo_accion" in df_display.columns:
            df_display["grupo_accion_sel"] = df_display.apply(
                lambda row: next(
                    (g["nombre"] for _, g in grupos_acciones_df.iterrows() 
                     if g["codigo"] == row.get("codigo_grupo_accion")),
                    ""
                ), axis=1
            )

        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "codigo_accion", "nombre", "modalidad", "nivel", 
                "num_horas", "certificado_profesionalidad", "fecha_inicio", "fecha_fin"
            ],
            titulo="Acción Formativa",
            on_save=guardar_accion,
            on_create=crear_accion if allow_creation else None,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_dinamicos=get_campos_dinamicos,
            campos_obligatorios=["codigo_accion", "nombre"],
            search_columns=["nombre", "codigo_accion", "area_profesional"],
            campos_readonly=["id", "created_at"],
            allow_creation=allow_creation,
            campos_help=campos_help
        )

    st.divider()
    st.caption("💡 Las acciones formativas son la base para crear grupos y asignar participantes.")
