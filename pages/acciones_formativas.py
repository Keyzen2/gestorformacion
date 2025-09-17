import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv
from components.listado_con_ficha import listado_con_ficha
from services.grupos_service import get_grupos_service

def main(supabase, session_state):
    st.title("📚 Gestión de Acciones Formativas")
    st.caption("Catálogo de cursos y acciones formativas para FUNDAE")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    grupos_service = get_grupos_service(supabase, session_state)

    # =========================
    # CARGAR DATOS
    # =========================
    with st.spinner("Cargando datos..."):
        df_acciones = grupos_service.get_acciones_formativas()
        areas_dict = grupos_service.get_areas_dict()
        grupos_acciones_df = grupos_service.get_grupos_acciones()

    # Filtrar acciones por rol
    empresa_id = session_state.user.get("empresa_id")
    df_filtered = df_acciones.copy() if not df_acciones.empty else pd.DataFrame()

    if session_state.role == "gestor" and not df_filtered.empty:
        if "empresa_id" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["empresa_id"] == empresa_id]

    # =========================
    # KPIs MEJORADOS - CORREGIDO CAMPO DE FECHA
    # =========================
    if not df_filtered.empty:
        # Calcular métricas
        total_acciones = len(df_filtered)
        
        # Intentar con created_at primero (estándar Supabase)
        campo_fecha = None
        campos_fecha_posibles = ["created_at", "creado_at", "fecha_creacion"]
        
        for campo in campos_fecha_posibles:
            if campo in df_filtered.columns:
                campo_fecha = campo
                break
        
        # Nuevas este mes
        nuevas_mes = 0
        if campo_fecha:
            try:
                df_fechas = pd.to_datetime(df_filtered[campo_fecha], errors="coerce")
                nuevas_mes = len(df_fechas[df_fechas.dt.month == datetime.now().month])
            except:
                nuevas_mes = 0
        
        # Nuevas este año
        nuevas_ano = 0
        if campo_fecha:
            try:
                df_fechas = pd.to_datetime(df_filtered[campo_fecha], errors="coerce")
                nuevas_ano = len(df_fechas[df_fechas.dt.year == datetime.now().year])
            except:
                nuevas_ano = 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📚 Total Acciones", total_acciones)
        with col2:
            st.metric("🆕 Nuevas este mes", nuevas_mes)
        with col3:
            st.metric("📅 Nuevas este año", nuevas_ano)
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📚 Total Acciones", 0)
        with col2:
            st.metric("🆕 Nuevas este mes", 0)
        with col3:
            st.metric("📅 Nuevas este año", 0)

    st.divider()

    # =========================
    # FILTROS DE BÚSQUEDA ÚNICOS
    # =========================
    st.markdown("### 🔍 Filtros")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre o código", key="busqueda_acciones")
    with col2:
        modalidades = ["Todas", "Presencial", "Online", "Mixta"]
        modalidad_filter = st.selectbox("Modalidad", modalidades, key="filtro_modalidad")

    # Aplicar filtros
    if query and not df_filtered.empty:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered.get("nombre", pd.Series(dtype=str)).str.lower().str.contains(q_lower, na=False) |
            df_filtered.get("codigo_accion", pd.Series(dtype=str)).str.lower().str.contains(q_lower, na=False) |
            df_filtered.get("area_profesional", pd.Series(dtype=str)).str.lower().str.contains(q_lower, na=False)
        ]

    if modalidad_filter != "Todas" and not df_filtered.empty and "modalidad" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["modalidad"] == modalidad_filter]

    allow_creation = grupos_service.can_modify_data()

    # =========================
    # FUNCIONES CRUD MEJORADAS (SIN FECHAS)
    # =========================
    def guardar_accion(accion_id, datos_editados):
        """Guarda cambios en una acción formativa - SIN FECHAS"""
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

            # ELIMINAR fechas si vienen en los datos (no deben procesarse)
            fechas_a_eliminar = ["fecha_inicio", "fecha_fin", "fecha_creacion"]
            for fecha in fechas_a_eliminar:
                if fecha in datos_editados:
                    del datos_editados[fecha]

            success = grupos_service.update_accion_formativa(accion_id, datos_editados)
            if success:
                st.success("✅ Acción formativa actualizada correctamente.")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar: {e}")

    def crear_accion(datos_nuevos):
        """Crea una nueva acción formativa - SIN FECHAS"""
        try:
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

            # Asignar empresa automáticamente para gestor
            if session_state.role == "gestor":
                datos_nuevos["empresa_id"] = empresa_id

            # ELIMINAR fechas si vienen en los datos (no deben procesarse)
            fechas_a_eliminar = ["fecha_inicio", "fecha_fin", "fecha_creacion"]
            for fecha in fechas_a_eliminar:
                if fecha in datos_nuevos:
                    del datos_nuevos[fecha]

            success = grupos_service.create_accion_formativa(datos_nuevos)
            if success:
                st.success("✅ Acción formativa creada correctamente.")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error al crear: {e}")

    # =========================
    # CONFIGURACIÓN CAMPOS (SIN FECHAS)
    # =========================
    def get_campos_dinamicos(datos):
        """Campos a mostrar - SIN fechas"""
        campos = [
            "codigo_accion", "nombre", "descripcion", "objetivos", "contenidos",
            "requisitos", "horas", "num_horas", "modalidad", "area_profesional", 
            "nivel", "certificado_profesionalidad", "cod_area_profesional", 
            "sector", "codigo_grupo_accion", "observaciones"
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
    # FORMULARIO DE CREACIÓN ESTILO GRUPOS.PY
    # =========================
    if allow_creation:
        with st.expander("➕ Crear nueva acción formativa", expanded=False):
            st.markdown("**Complete los datos básicos de la acción formativa**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nuevo_codigo = st.text_input(
                    "Código de la acción *",
                    help="Código único identificativo",
                    key="nuevo_codigo"
                )
                nuevo_nombre = st.text_input(
                    "Nombre de la acción *",
                    help="Denominación completa de la acción formativa",
                    key="nuevo_nombre"
                )
                nueva_modalidad = st.selectbox(
                    "Modalidad *",
                    ["Presencial", "Online", "Mixta"],
                    key="nueva_modalidad"
                )
                nueva_num_horas = st.number_input(
                    "Número de horas *",
                    min_value=1,
                    step=1,
                    value=20,
                    help="Duración total de la acción formativa",
                    key="nuevas_horas"
                )

            with col2:
                nueva_area_prof = st.selectbox(
                    "Área profesional *",
                    list(areas_dict.keys()) if areas_dict else ["No disponible"],
                    key="nueva_area"
                )
                nuevo_nivel = st.selectbox(
                    "Nivel",
                    ["Básico", "Intermedio", "Avanzado"],
                    key="nuevo_nivel"
                )
                nuevo_certificado = st.checkbox(
                    "Certificado de profesionalidad",
                    key="nuevo_certificado"
                )
                nuevo_sector = st.text_input(
                    "Sector",
                    help="Sector profesional al que se dirige",
                    key="nuevo_sector"
                )

            # Campos de texto largo
            nueva_descripcion = st.text_area(
                "Descripción",
                height=60,
                help="Descripción general de la acción formativa",
                key="nueva_descripcion"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                nuevos_objetivos = st.text_area(
                    "Objetivos",
                    height=80,
                    help="Objetivos de aprendizaje",
                    key="nuevos_objetivos"
                )
            with col2:
                nuevos_contenidos = st.text_area(
                    "Contenidos",
                    height=80,
                    help="Contenidos temáticos principales",
                    key="nuevos_contenidos"
                )

            nuevos_requisitos = st.text_area(
                "Requisitos de acceso",
                height=60,
                help="Requisitos previos para acceder a la formación",
                key="nuevos_requisitos"
            )
            nuevas_observaciones = st.text_area(
                "Observaciones",
                height=60,
                help="Información adicional relevante",
                key="nuevas_observaciones"
            )

            # Botones de acción
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("➕ Crear acción", type="primary", use_container_width=True):
                    if not nuevo_codigo or not nuevo_nombre:
                        st.error("⚠️ Código y nombre son obligatorios")
                    else:
                        datos_nuevos = {
                            "codigo_accion": nuevo_codigo,
                            "nombre": nuevo_nombre,
                            "modalidad": nueva_modalidad,
                            "num_horas": nueva_num_horas,
                            "area_profesional_sel": nueva_area_prof,
                            "nivel": nuevo_nivel,
                            "certificado_profesionalidad": nuevo_certificado,
                            "sector": nuevo_sector,
                            "descripcion": nueva_descripcion,
                            "objetivos": nuevos_objetivos,
                            "contenidos": nuevos_contenidos,
                            "requisitos": nuevos_requisitos,
                            "observaciones": nuevas_observaciones
                        }

                        crear_accion(datos_nuevos)
            
            with col2:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.rerun()

    st.divider()

    # =========================
    # LISTADO DE ACCIONES MEJORADO
    # =========================
    st.markdown("### 📋 Catálogo de Acciones Formativas")
    
    if not df_filtered.empty:
        df_display = df_filtered.copy()

        # Preparar campos calculados para mostrar
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

        # MOSTRAR SIN FECHAS
        columnas_visibles = [
            "codigo_accion", "nombre", "modalidad", "nivel", 
            "num_horas", "certificado_profesionalidad", "area_profesional"
        ]

        listado_con_ficha(
            df_display,
            columnas_visibles=columnas_visibles,
            titulo="Acción Formativa",
            on_save=guardar_accion,
            on_create=None,  # Creación manejada arriba
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_dinamicos=get_campos_dinamicos,
            campos_obligatorios=["codigo_accion", "nombre"],
            search_columns=["nombre", "codigo_accion", "area_profesional"],
            campos_readonly=["id", "created_at"],
            allow_creation=False,  # Deshabilitado porque lo manejamos arriba
            campos_help=campos_help
        )
    else:
        st.info("ℹ️ No hay acciones formativas disponibles.")
        
        if allow_creation:
            st.markdown("### 🚀 ¡Crea tu primera acción formativa!")
            st.markdown("Use el formulario de arriba para comenzar")

    st.divider()
    
    # =========================
    # INFORMACIÓN FINAL
    # =========================
    with st.expander("ℹ️ Información sobre Acciones Formativas", expanded=False):
        st.markdown("""
        **¿Qué son las Acciones Formativas?**
        
        Las acciones formativas son el catálogo base de cursos que su organización puede impartir:
        
        - **Sin fechas**: Las fechas específicas se definen al crear grupos
        - **Reutilizables**: Una acción puede tener múltiples grupos a lo largo del tiempo
        - **Base para FUNDAE**: Necesarias para generar XML de grupos
        - **Flexibles**: Pueden ser presenciales, online o mixtas
        
        **Flujo recomendado:**
        1. Crear acciones formativas (catálogo general)
        2. Crear grupos específicos con fechas y participantes
        3. Asignar tutores y empresas a los grupos
        4. Generar documentación FUNDAE
        """)
        
    st.caption("💡 Las acciones formativas son la base para crear grupos con fechas específicas y participantes.")
