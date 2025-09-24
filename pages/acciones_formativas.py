import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv
from services.data_service import get_data_service

def main(supabase, session_state):
    st.title("📚 Gestión de Acciones Formativas")
    st.caption("Catálogo de cursos y acciones formativas para FUNDAE")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio
    data_service = get_data_service(supabase, session_state)

    # =========================
    # CARGAR DATOS CON JERARQUÍA  
    # =========================
    with st.spinner("Cargando datos..."):
        df_acciones = data_service.get_acciones_formativas()
        areas_dict = data_service.get_areas_dict() 
        grupos_acciones_df = data_service.get_grupos_acciones()

    # =========================
    # MÉTRICAS CON JERARQUÍA
    # =========================
    if not df_acciones.empty:
        total_acciones = len(df_acciones)
        
        # Calcular nuevas este mes/año
        nuevas_mes = nuevas_ano = 0
        if "created_at" in df_acciones.columns:
            try:
                df_fechas = pd.to_datetime(df_acciones["created_at"], errors="coerce")
                nuevas_mes = len(df_fechas[df_fechas.dt.month == datetime.now().month])
                nuevas_ano = len(df_fechas[df_fechas.dt.year == datetime.now().year])
            except:
                pass
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📚 Total Acciones", total_acciones)
        with col2:
            st.metric("🆕 Nuevas este mes", nuevas_mes)
        with col3:
            st.metric("📅 Nuevas este año", nuevas_ano)
        with col4:
            if session_state.role == "admin":
                empresas_gestoras = df_acciones["empresa_id"].nunique() if "empresa_id" in df_acciones.columns else 0
                st.metric("🏢 Empresas Gestoras", empresas_gestoras)
            else:
                modalidades = df_acciones["modalidad"].nunique() if "modalidad" in df_acciones.columns else 0
                st.metric("🎯 Modalidades", modalidades)
        
        # Información contextual por rol
        if session_state.role == "gestor":
            st.caption("🏢 Mostrando acciones de tu empresa gestora")
        elif session_state.role == "admin":
            st.caption("🌍 Mostrando todas las acciones del sistema")
    else:
        st.info("📋 No hay acciones formativas disponibles para tu rol.")

    st.divider()

    # =========================
    # TABLA PRINCIPAL CON NUEVO PATRÓN
    # =========================
    if not df_acciones.empty:
        # Filtros
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            search_term = st.text_input(
                "🔍 Buscar acciones formativas",
                placeholder="Buscar por nombre, código o área...",
                key="search_acciones"
            )
        with col2:
            modalidad_filter = st.selectbox(
                "Modalidad",
                ["Todas"] + list(df_acciones["modalidad"].dropna().unique()),
                key="modalidad_filter"
            )
        with col3:
            if st.button("📊 Exportar CSV", use_container_width=True):
                csv_data = export_csv(df_acciones)
                st.download_button(
                    label="⬇️ Descargar",
                    data=csv_data,
                    file_name=f"acciones_formativas_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

        # Aplicar filtros
        df_filtered = df_acciones.copy()
        
        if search_term:
            search_lower = search_term.lower()
            df_filtered = df_filtered[
                df_filtered["nombre"].str.lower().str.contains(search_lower, na=False) |
                df_filtered["codigo_accion"].str.lower().str.contains(search_lower, na=False) |
                df_filtered["area_profesional"].fillna("").str.lower().str.contains(search_lower, na=False)
            ]
        
        if modalidad_filter != "Todas":
            df_filtered = df_filtered[df_filtered["modalidad"] == modalidad_filter]

        # Preparar columnas para mostrar
        columnas_mostrar = [
            "codigo_accion", "nombre", "modalidad", "num_horas", 
            "area_profesional", "nivel", "certificado_profesionalidad"
        ]

        # Configurar columnas
        column_config = {
            "codigo_accion": st.column_config.TextColumn("🏷️ Código", width="small"),
            "nombre": st.column_config.TextColumn("📚 Nombre", width="large"),
            "modalidad": st.column_config.TextColumn("🎯 Modalidad", width="small"),
            "num_horas": st.column_config.NumberColumn("⏱️ Horas", width="small"),
            "area_profesional": st.column_config.TextColumn("🎓 Área", width="medium"),
            "nivel": st.column_config.TextColumn("📈 Nivel", width="small"),
            "certificado_profesionalidad": st.column_config.CheckboxColumn("🏆 Certificado", width="small")
        }

        # Añadir empresa para admin
        if session_state.role == "admin" and "empresa_id" in df_filtered.columns:
            empresas_dict = data_service.get_empresas_dict()
            df_filtered["empresa_nombre"] = df_filtered["empresa_id"].map(
                {v: k for k, v in empresas_dict.items()}
            ).fillna("Sin empresa")
            columnas_mostrar.append("empresa_nombre")
            column_config["empresa_nombre"] = st.column_config.TextColumn("🏢 Empresa", width="medium")

        # Mostrar tabla con selección
        event = st.dataframe(
            df_filtered[columnas_mostrar],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config=column_config
        )

        # Procesar selección
        accion_seleccionada = None
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            accion_seleccionada = df_filtered.iloc[selected_idx]

    st.divider()

    # =========================
    # BOTONES DE ACCIÓN
    # =========================
    if data_service.can_modify_data():
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("➕ Crear Nueva Acción", type="primary", use_container_width=True):
                st.session_state.modo_accion = "crear"
                st.rerun()
        
        with col2:
            if st.button("✏️ Editar Seleccionada", disabled=accion_seleccionada is None, use_container_width=True):
                if accion_seleccionada is not None:
                    st.session_state.modo_accion = "editar"
                    st.session_state.accion_editando = accion_seleccionada.to_dict()
                    st.rerun()
        
        with col3:
            if st.button("🗑️ Eliminar Seleccionada", disabled=accion_seleccionada is None, use_container_width=True):
                if accion_seleccionada is not None:
                    st.session_state.modo_accion = "eliminar"
                    st.session_state.accion_eliminando = accion_seleccionada.to_dict()
                    st.rerun()

    # =========================
    # FORMULARIOS MODALES
    # =========================
    
    # Formulario de creación
    if hasattr(st.session_state, 'modo_accion') and st.session_state.modo_accion == "crear":
        mostrar_formulario_creacion(data_service, areas_dict, grupos_acciones_df, session_state)
    
    # Formulario de edición
    elif hasattr(st.session_state, 'modo_accion') and st.session_state.modo_accion == "editar":
        mostrar_formulario_edicion(data_service, areas_dict, grupos_acciones_df, session_state)
    
    # Confirmación de eliminación
    elif hasattr(st.session_state, 'modo_accion') and st.session_state.modo_accion == "eliminar":
        mostrar_confirmacion_eliminacion(data_service, session_state)

    # =========================
    # INFORMACIÓN CONTEXTUAL FUNDAE
    # =========================
    with st.expander("ℹ️ Información sobre Acciones Formativas FUNDAE", expanded=False):
        st.markdown("""
        **Gestión de Acciones Formativas con Jerarquía Empresarial**
        
        Las acciones formativas son el catálogo base de cursos que tu organización puede impartir:
        
        **🏢 Según tu rol:**
        - **Gestor**: Puedes crear acciones para tu empresa gestora
        - **Admin**: Puedes crear acciones para cualquier empresa del sistema
        
        **📋 Campos obligatorios FUNDAE:**
        - Código único de acción (por empresa gestora y año)
        - Nombre completo de la acción
        - Modalidad: Presencial, Online (Teleformación) o Mixta
        - Número de horas de duración
        
        **🔄 Flujo recomendado:**
        1. Crear acciones formativas (catálogo general)
        2. Crear grupos específicos con fechas y participantes
        3. Asignar tutores y empresas participantes
        4. Generar documentación XML FUNDAE
        """)

def mostrar_formulario_creacion(data_service, areas_dict, grupos_acciones_df, session_state):
    """Formulario de creación de acción formativa."""
    with st.form("crear_accion", clear_on_submit=False):
        st.markdown("### ➕ Crear Nueva Acción Formativa")
        st.markdown("**Complete los datos básicos obligatorios**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            codigo_accion = st.text_input(
                "Código de la acción *",
                help="Código único identificativo",
                key="nuevo_codigo"
            )
            nombre = st.text_input(
                "Nombre de la acción *", 
                help="Denominación completa de la acción formativa",
                key="nuevo_nombre"
            )
            modalidad = st.selectbox(
                "Modalidad *",
                ["Presencial", "Online", "Mixta"],
                key="nueva_modalidad"
            )
            num_horas = st.number_input(
                "Número de horas *",
                min_value=1,
                max_value=9999,
                value=20,
                help="Duración total de la acción formativa",
                key="nuevas_horas"
            )

        with col2:
            area_profesional = st.selectbox(
                "Área profesional *",
                list(areas_dict.keys()) if areas_dict else ["No disponible"],
                key="nueva_area"
            )
            nivel = st.selectbox(
                "Nivel",
                ["Básico", "Intermedio", "Avanzado"],
                key="nuevo_nivel"
            )
            certificado_profesionalidad = st.checkbox(
                "Certificado de profesionalidad",
                key="nuevo_certificado"
            )
            sector = st.text_input(
                "Sector",
                help="Sector profesional al que se dirige",
                key="nuevo_sector"
            )

        # Solo admin puede seleccionar empresa gestora
        empresa_gestora_id = None
        if session_state.role == "admin":
            empresas_dict = data_service.get_empresas_dict()
            if empresas_dict:
                empresa_gestora = st.selectbox(
                    "Empresa Gestora *",
                    list(empresas_dict.keys()),
                    key="nueva_empresa_gestora"
                )
                empresa_gestora_id = empresas_dict[empresa_gestora]

        # Campos de texto largo
        descripcion = st.text_area(
            "Descripción",
            height=60,
            help="Descripción general de la acción formativa",
            key="nueva_descripcion"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            objetivos = st.text_area(
                "Objetivos",
                height=80,
                help="Objetivos de aprendizaje",
                key="nuevos_objetivos"
            )
        with col2:
            contenidos = st.text_area(
                "Contenidos",
                height=80,
                help="Contenidos temáticos principales",
                key="nuevos_contenidos"
            )

        requisitos = st.text_area(
            "Requisitos de acceso",
            height=60,
            help="Requisitos previos para acceder a la formación",
            key="nuevos_requisitos"
        )
        
        observaciones = st.text_area(
            "Observaciones",
            height=60,
            help="Información adicional relevante",
            key="nuevas_observaciones"
        )

        # Botones de acción
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("✅ Crear Acción", type="primary", use_container_width=True)
        with col2:
            canceled = st.form_submit_button("❌ Cancelar", use_container_width=True)

        if submitted:
            # Validaciones
            if not codigo_accion or not nombre or not modalidad or not num_horas:
                st.error("⚠️ Código, nombre, modalidad y horas son obligatorios")
                return
            
            if session_state.role == "admin" and not empresa_gestora_id:
                st.error("⚠️ Debe seleccionar empresa gestora")
                return

            # Preparar datos
            datos_nuevos = {
                "codigo_accion": codigo_accion.strip(),
                "nombre": nombre.strip(),
                "modalidad": modalidad,
                "num_horas": num_horas,
                "nivel": nivel,
                "certificado_profesionalidad": certificado_profesionalidad,
                "sector": sector.strip() if sector else None,
                "descripcion": descripcion.strip() if descripcion else None,
                "objetivos": objetivos.strip() if objetivos else None,
                "contenidos": contenidos.strip() if contenidos else None,
                "requisitos": requisitos.strip() if requisitos else None,
                "observaciones": observaciones.strip() if observaciones else None
            }

            # Procesar área profesional
            if area_profesional and " - " in area_profesional:
                codigo_area, nombre_area = area_profesional.split(" - ", 1)
                datos_nuevos["cod_area_profesional"] = codigo_area
                datos_nuevos["area_profesional"] = nombre_area

            # Asignar empresa gestora para admin
            if session_state.role == "admin" and empresa_gestora_id:
                datos_nuevos["empresa_id"] = empresa_gestora_id

            try:
                # Usar el método FUNDAE de data_service
                success = data_service.create_accion_formativa_con_validaciones_fundae(datos_nuevos)
                if success:
                    st.success("✅ Acción formativa creada correctamente.")
                    del st.session_state.modo_accion
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error al crear: {e}")

        elif canceled:
            del st.session_state.modo_accion
            st.rerun()

def mostrar_formulario_edicion(data_service, areas_dict, grupos_acciones_df, session_state):
    """Formulario de edición de acción formativa."""
    accion = st.session_state.accion_editando
    
    with st.form("editar_accion", clear_on_submit=False):
        st.markdown(f"### ✏️ Editar Acción: {accion.get('nombre', 'Sin nombre')}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            codigo_accion = st.text_input(
                "Código de la acción *",
                value=accion.get("codigo_accion", ""),
                key="edit_codigo"
            )
            nombre = st.text_input(
                "Nombre de la acción *",
                value=accion.get("nombre", ""),
                key="edit_nombre"
            )
            modalidad = st.selectbox(
                "Modalidad *",
                ["Presencial", "Online", "Mixta"],
                index=["Presencial", "Online", "Mixta"].index(accion.get("modalidad", "Presencial")),
                key="edit_modalidad"
            )
            num_horas = st.number_input(
                "Número de horas *",
                min_value=1,
                max_value=9999,
                value=int(accion.get("num_horas", 20)),
                key="edit_horas"
            )

        with col2:
            # Área profesional actual
            area_actual = None
            if accion.get("cod_area_profesional"):
                for k, v in areas_dict.items():
                    if v == accion.get("cod_area_profesional"):
                        area_actual = k
                        break
            
            area_profesional = st.selectbox(
                "Área profesional *",
                list(areas_dict.keys()) if areas_dict else ["No disponible"],
                index=list(areas_dict.keys()).index(area_actual) if area_actual else 0,
                key="edit_area"
            )
            nivel = st.selectbox(
                "Nivel",
                ["Básico", "Intermedio", "Avanzado"],
                index=["Básico", "Intermedio", "Avanzado"].index(accion.get("nivel", "Básico")),
                key="edit_nivel"
            )
            certificado_profesionalidad = st.checkbox(
                "Certificado de profesionalidad",
                value=accion.get("certificado_profesionalidad", False),
                key="edit_certificado"
            )
            sector = st.text_input(
                "Sector",
                value=accion.get("sector", ""),
                key="edit_sector"
            )

        # Campos de texto largo
        descripcion = st.text_area(
            "Descripción",
            value=accion.get("descripcion", ""),
            height=60,
            key="edit_descripcion"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            objetivos = st.text_area(
                "Objetivos",
                value=accion.get("objetivos", ""),
                height=80,
                key="edit_objetivos"
            )
        with col2:
            contenidos = st.text_area(
                "Contenidos",
                value=accion.get("contenidos", ""),
                height=80,
                key="edit_contenidos"
            )

        requisitos = st.text_area(
            "Requisitos de acceso",
            value=accion.get("requisitos", ""),
            height=60,
            key="edit_requisitos"
        )
        
        observaciones = st.text_area(
            "Observaciones",
            value=accion.get("observaciones", ""),
            height=60,
            key="edit_observaciones"
        )

        # Botones de acción
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
        with col2:
            canceled = st.form_submit_button("❌ Cancelar", use_container_width=True)

        if submitted:
            # Preparar datos editados
            datos_editados = {
                "codigo_accion": codigo_accion.strip(),
                "nombre": nombre.strip(),
                "modalidad": modalidad,
                "num_horas": num_horas,
                "nivel": nivel,
                "certificado_profesionalidad": certificado_profesionalidad,
                "sector": sector.strip() if sector else None,
                "descripcion": descripcion.strip() if descripcion else None,
                "objetivos": objetivos.strip() if objetivos else None,
                "contenidos": contenidos.strip() if contenidos else None,
                "requisitos": requisitos.strip() if requisitos else None,
                "observaciones": observaciones.strip() if observaciones else None
            }

            # Procesar área profesional
            if area_profesional and " - " in area_profesional:
                codigo_area, nombre_area = area_profesional.split(" - ", 1)
                datos_editados["cod_area_profesional"] = codigo_area
                datos_editados["area_profesional"] = nombre_area

            try:
                # Usar el método FUNDAE de data_service
                success = data_service.update_accion_formativa_con_validaciones_fundae(accion["id"], datos_editados)
                if success:
                    st.success("✅ Acción formativa actualizada correctamente.")
                    del st.session_state.modo_accion
                    del st.session_state.accion_editando
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error al actualizar: {e}")

        elif canceled:
            del st.session_state.modo_accion
            del st.session_state.accion_editando
            st.rerun()

def mostrar_confirmacion_eliminacion(data_service, session_state):
    """Confirmación de eliminación de acción formativa."""
    accion = st.session_state.accion_eliminando
    
    st.warning(f"⚠️ ¿Está seguro de que desea eliminar la acción formativa **{accion.get('nombre', 'Sin nombre')}**?")
    st.caption("Esta acción no se puede deshacer.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🗑️ Sí, Eliminar", type="primary", use_container_width=True):
            try:
                success = data_service.delete_accion_formativa(accion["id"])
                if success:
                    st.success("✅ Acción formativa eliminada correctamente.")
                    del st.session_state.modo_accion
                    del st.session_state.accion_eliminando
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error al eliminar: {e}")
    
    with col2:
        if st.button("❌ Cancelar", use_container_width=True):
            del st.session_state.modo_accion
            del st.session_state.accion_eliminando
            st.rerun()
