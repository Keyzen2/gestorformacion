import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.subheader("📚 Acciones Formativas")
    st.caption("Gestión de acciones formativas y configuración de cursos.")

    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)

    # =========================
    # Cargar datos
    # =========================
    with st.spinner("Cargando datos..."):
        df_acciones = data_service.get_acciones_formativas()
        areas_dict = data_service.get_areas_dict()
        grupos_acciones_df = data_service.get_grupos_acciones()

    # =========================
    # Métricas
    # =========================
    if not df_acciones.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📚 Total Acciones", len(df_acciones))
        
        with col2:
            # Acciones creadas este mes
            if "fecha_creacion" in df_acciones.columns:
                este_mes = df_acciones[
                    pd.to_datetime(df_acciones["fecha_creacion"], errors="coerce").dt.month == datetime.now().month
                ]
                st.metric("🆕 Nuevas este mes", len(este_mes))
            else:
                st.metric("🆕 Nuevas este mes", 0)
        
        with col3:
            # Modalidad más común
            if "modalidad" in df_acciones.columns:
                modalidad_top = df_acciones["modalidad"].value_counts().idxmax() if len(df_acciones) > 0 else "N/A"
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

    # Aplicar filtros
    df_filtered = df_acciones.copy()
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["codigo_accion"].str.lower().str.contains(q_lower, na=False) |
            df_filtered.get("area_profesional", pd.Series()).str.lower().str.contains(q_lower, na=False)
        ]
    
    if modalidad_filter != "Todas":
        df_filtered = df_filtered[df_filtered.get("modalidad") == modalidad_filter]

    # Exportar CSV
    if not df_filtered.empty:
        export_csv(df_filtered, filename="acciones_formativas.csv")
    
    st.divider()

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_accion(accion_id, datos_editados):
        """Función para guardar cambios en una acción formativa."""
        try:
            # Procesar área profesional
            if "area_profesional_sel" in datos_editados:
                area_sel = datos_editados.pop("area_profesional_sel")
                datos_editados["cod_area_profesional"] = areas_dict.get(area_sel, "")
                datos_editados["area_profesional"] = area_sel.split(" - ", 1)[1] if " - " in area_sel else area_sel

            # Procesar grupo de acciones
            if "grupo_accion_sel" in datos_editados:
                grupo_sel = datos_editados.pop("grupo_accion_sel")
                cod_area = datos_editados.get("cod_area_profesional", "")
                grupos_filtrados = grupos_acciones_df[
                    grupos_acciones_df["cod_area_profesional"] == cod_area
                ]
                grupos_dict = {g["nombre"]: g["codigo"] for _, g in grupos_filtrados.iterrows()}
                datos_editados["codigo_grupo_accion"] = grupos_dict.get(grupo_sel, "")

            success = data_service.update_accion_formativa(accion_id, datos_editados)
            if success:
                st.success("✅ Acción formativa actualizada correctamente.")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar: {e}")

    def crear_accion(datos_nuevos):
        """Función para crear una nueva acción formativa."""
        try:
            # Validaciones
            if not datos_nuevos.get("codigo_accion") or not datos_nuevos.get("nombre"):
                st.error("⚠️ Código y nombre son obligatorios.")
                return

            # Procesar área profesional
            if "area_profesional_sel" in datos_nuevos:
                area_sel = datos_nuevos.pop("area_profesional_sel")
                datos_nuevos["cod_area_profesional"] = areas_dict.get(area_sel, "")
                datos_nuevos["area_profesional"] = area_sel.split(" - ", 1)[1] if " - " in area_sel else area_sel

            # Procesar grupo de acciones
            if "grupo_accion_sel" in datos_nuevos:
                grupo_sel = datos_nuevos.pop("grupo_accion_sel")
                cod_area = datos_nuevos.get("cod_area_profesional", "")
                grupos_filtrados = grupos_acciones_df[
                    grupos_acciones_df["cod_area_profesional"] == cod_area
                ]
                grupos_dict = {g["nombre"]: g["codigo"] for _, g in grupos_filtrados.iterrows()}
                datos_nuevos["codigo_grupo_accion"] = grupos_dict.get(grupo_sel, "")

            # Asegurar que tiene empresa_id si es gestor
            if session_state.role == "gestor":
                datos_nuevos["empresa_id"] = session_state.user.get("empresa_id")

            success = data_service.create_accion_formativa(datos_nuevos)
            if success:
                st.success("✅ Acción formativa creada correctamente.")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error al crear: {e}")

    # =========================
    # Campos dinámicos para el formulario
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos = [
            "codigo_accion", "nombre", "area_profesional_sel", "grupo_accion_sel",
            "sector", "objetivos", "contenidos", "nivel", "modalidad", 
            "num_horas", "certificado_profesionalidad", "observaciones"
        ]
        return campos

    # Configurar opciones para selects
    campos_select = {
        "area_profesional_sel": list(areas_dict.keys()) if areas_dict else ["No disponible"],
        "nivel": ["Básico", "Intermedio", "Avanzado"],
        "modalidad": ["Presencial", "Online", "Mixta"],
        "certificado_profesionalidad": [True, False]
    }

    # Campos de texto largo
    campos_textarea = {
        "objetivos": {"label": "Objetivos del curso"},
        "contenidos": {"label": "Contenidos temáticos"},
        "observaciones": {"label": "Observaciones adicionales"}
    }

    # =========================
    # Mostrar interfaz
    # =========================
    if df_filtered.empty:
        st.info("ℹ️ No hay acciones formativas para mostrar.")
        if data_service.can_modify_data():
            st.markdown("### ➕ Crear primera acción formativa")
            # Aquí iría el formulario de creación
    else:
        # Añadir campos calculados para mostrar mejor información
        df_display = df_filtered.copy()
        
        # Preparar área profesional para mostrar
        if "cod_area_profesional" in df_display.columns:
            df_display["area_profesional_sel"] = df_display.apply(
                lambda row: next(
                    (k for k, v in areas_dict.items() if v == row.get("cod_area_profesional")),
                    row.get("area_profesional", "")
                ), axis=1
            )

        # Preparar grupo de acciones
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
                "id", "codigo_accion", "nombre", "area_profesional_sel", 
                "modalidad", "nivel", "num_horas", "certificado_profesionalidad"
            ],
            titulo="Acción Formativa",
            on_save=guardar_accion,
            on_create=crear_accion,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=data_service.can_modify_data()
        )

    st.divider()
    st.caption("💡 Las acciones formativas son la base para crear grupos y asignar participantes.")
