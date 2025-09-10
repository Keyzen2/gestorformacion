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
    with st.spinner("Cargando acciones formativas..."):
        ds = get_data_service(supabase, session_state)

        df_acciones = ds.get_acciones_formativas_completas()
        empresas_dict = ds.get_empresas_dict()

        empresas_opciones = [""] + sorted(empresas_dict.keys())

    # Fallback de columnas de fecha si faltan
    if "fecha_inicio" not in df_acciones.columns:
        df_acciones["fecha_inicio"] = None
    if "fecha_fin" not in df_acciones.columns:
        df_acciones["fecha_fin"] = None

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
    def guardar_accion_formativa(accion_id, datos_editados):
        try:
            if "empresa_nombre" in datos_editados and datos_editados["empresa_nombre"]:
                nombre = datos_editados.pop("empresa_nombre")
                if nombre in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[nombre]
                else:
                    st.error(f"⚠️ Empresa '{nombre}' no encontrada.")
                    return

            # Validar coherencia de fechas
            inicio = datos_editados.get("fecha_inicio")
            fin = datos_editados.get("fecha_fin")
            if inicio and fin and inicio > fin:
                st.error("⚠️ La fecha de inicio no puede ser posterior a la fecha de fin.")
                return

            supabase.table("acciones_formativas").update(datos_editados).eq("id", accion_id).execute()
            st.success("✅ Acción formativa actualizada correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"⚠️ Error al actualizar acción formativa: {e}")

    def crear_accion_formativa(datos_nuevos):
        try:
            if not datos_nuevos.get("nombre"):
                st.error("⚠️ El nombre de la acción formativa es obligatorio.")
                return

            empresa_id = None
            if datos_nuevos.get("empresa_nombre"):
                if datos_nuevos["empresa_nombre"] in empresas_dict:
                    empresa_id = empresas_dict[datos_nuevos["empresa_nombre"]]
                else:
                    st.error(f"⚠️ Empresa '{datos_nuevos['empresa_nombre']}' no encontrada.")
                    return

            inicio = datos_nuevos.get("fecha_inicio")
            fin = datos_nuevos.get("fecha_fin")
            if inicio and fin and inicio > fin:
                st.error("⚠️ La fecha de inicio no puede ser posterior a la fecha de fin.")
                return

            payload = {
                "nombre": datos_nuevos["nombre"],
                "descripcion": datos_nuevos.get("descripcion"),
                "empresa_id": empresa_id,
                "fecha_inicio": inicio,
                "fecha_fin": fin,
                "modalidad": datos_nuevos.get("modalidad"),
                "horas": datos_nuevos.get("horas")
            }

            res = supabase.table("acciones_formativas").insert(payload).execute()
            if res.data:
                st.success("✅ Acción formativa creada correctamente.")
                st.rerun()
            else:
                st.error("⚠️ No se pudo crear la acción formativa.")
        except Exception as e:
            st.error(f"⚠️ Error al crear acción formativa: {e}")

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
            on_save=guardar_accion_formativa,
            on_create=crear_accion_formativa,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=data_service.can_modify_data()
        )

    st.divider()
    st.caption("💡 Las acciones formativas son la base para crear grupos y asignar participantes.")
