import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
from utils import export_csv, validar_dni_cif
from services.data_service import get_data_service

def main(supabase, session_state):
    st.title("👨‍🏫 Gestión de Tutores")
    st.caption("Gestión de tutores internos y externos vinculados a grupos formativos")

    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # =========================
    # INICIALIZAR DATA SERVICE
    # =========================
    try:
        data_service = get_data_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error al inicializar servicio de datos: {e}")
        return

    # =========================
    # CARGAR DATOS
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            df_tutores = data_service.get_tutores_completos()
            
            # Empresas para admin
            empresas_dict = {}
            if session_state.role == "admin":
                try:
                    empresas_dict = data_service.get_empresas_dict()
                except Exception as e:
                    st.warning(f"⚠️ Error al cargar empresas: {e}")
        except Exception as e:
            st.error(f"❌ Error al cargar tutores: {e}")
            return

    # =========================
    # MÉTRICAS UNIFICADAS
    # =========================
    if not df_tutores.empty:
        # Calcular métricas principales
        total_tutores = len(df_tutores)
        internos = len(df_tutores[df_tutores["tipo_tutor"] == "interno"])
        externos = len(df_tutores[df_tutores["tipo_tutor"] == "externo"])
        con_cv = len(df_tutores[df_tutores["cv_url"].notna() & (df_tutores["cv_url"] != "")])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Tutores", total_tutores)
        with col2:
            st.metric("🏢 Internos", internos)
        with col3:
            st.metric("🌐 Externos", externos)
        with col4:
            st.metric("📄 Con CV", con_cv, f"{(con_cv/total_tutores*100):.1f}%" if total_tutores > 0 else "0%")

    st.divider()

    # =========================
    # DEFINIR PERMISOS Y OPCIONES
    # =========================
    puede_modificar = data_service.can_modify_data()

    # Especialidades FUNDAE
    especialidades_opciones = [
        "", "Administración y Gestión", "Comercio y Marketing", 
        "Informática y Comunicaciones", "Sanidad", "Servicios Socioculturales", 
        "Hostelería y Turismo", "Educación", "Industrias Alimentarias", 
        "Química", "Imagen Personal", "Industrias Extractivas",
        "Fabricación Mecánica", "Instalación y Mantenimiento", 
        "Electricidad y Electrónica", "Energía y Agua", 
        "Transporte y Mantenimiento de Vehículos", "Edificación y Obra Civil",
        "Vidrio y Cerámica", "Madera, Mueble y Corcho", 
        "Textil, Confección y Piel", "Artes Gráficas", "Imagen y Sonido", 
        "Actividades Físicas y Deportivas", "Marítimo-Pesquera", 
        "Industrias Agroalimentarias", "Agraria", "Seguridad y Medio Ambiente"
    ]

    # Campos select
    campos_select = {
        "tipo_tutor": ["", "interno", "externo"],
        "especialidad": especialidades_opciones,
        "tipo_documento": [
            ("", "Seleccionar tipo"),
            (10, "NIF"),           # Código 10 para NIF
            (20, "Pasaporte"),     # Código 20 para Pasaporte  
            (60, "NIE")            # Código 60 para NIE
        ]
    }

    if session_state.role == "admin" and empresas_dict:
        empresas_opciones = [""] + sorted(empresas_dict.keys())
        campos_select["empresa_sel"] = empresas_opciones

    # =========================
    # FILTROS DE BÚSQUEDA UNIFICADOS
    # =========================
    st.markdown("### 🔍 Filtros de Búsqueda")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        buscar_texto = st.text_input(
            "Buscar tutor",
            placeholder="Nombre, email, NIF...",
            key="buscar_tutor_unificado"
        )
    
    with col2:
        if session_state.role == "admin" and empresas_dict:
            empresas_opciones = ["Todas"] + sorted(empresas_dict.keys())
            empresa_filtro = st.selectbox("Filtrar por empresa", empresas_opciones)
        else:
            empresa_filtro = "Todas"
    
    with col3:
        tipo_filtro = st.selectbox("Tipo de tutor", ["Todos", "interno", "externo"])
    
    with col4:
        estado_cv = st.selectbox("Estado CV", ["Todos", "Con CV", "Sin CV"])
    
    with col5:
        especialidad_filtro = st.selectbox(
            "Especialidad", 
            ["Todas"] + [esp for esp in especialidades_opciones if esp != ""]
        )

    # Aplicar filtros
    df_filtrado = df_tutores.copy()
    
    if buscar_texto:
        buscar_lower = buscar_texto.lower()
        mascara = (
            df_filtrado["nombre"].str.lower().str.contains(buscar_lower, na=False) |
            df_filtrado["apellidos"].str.lower().str.contains(buscar_lower, na=False) |
            df_filtrado["email"].str.lower().str.contains(buscar_lower, na=False) |
            df_filtrado["nif"].str.lower().str.contains(buscar_lower, na=False)
        )
        df_filtrado = df_filtrado[mascara]
    
    if session_state.role == "admin" and empresa_filtro != "Todas":
        if empresa_filtro in empresas_dict:
            empresa_id = empresas_dict[empresa_filtro]
            df_filtrado = df_filtrado[df_filtrado["empresa_id"] == empresa_id]
    
    if tipo_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tipo_tutor"] == tipo_filtro]
    
    if estado_cv == "Con CV":
        df_filtrado = df_filtrado[df_filtrado["cv_url"].notna() & (df_filtrado["cv_url"] != "")]
    elif estado_cv == "Sin CV":
        df_filtrado = df_filtrado[~(df_filtrado["cv_url"].notna() & (df_filtrado["cv_url"] != ""))]
    
    if especialidad_filtro != "Todas":
        df_filtrado = df_filtrado[df_filtrado["especialidad"] == especialidad_filtro]

    # Mostrar resultados de filtros
    if len(df_filtrado) != len(df_tutores):
        st.info(f"🎯 {len(df_filtrado)} de {len(df_tutores)} tutores mostrados")

    st.divider()

    # =========================
    # FUNCIONES CRUD OPTIMIZADAS
    # =========================
    def guardar_tutor(tutor_id, datos_editados):
        """Actualiza un tutor existente."""
        try:
            # Validaciones básicas
            if not datos_editados.get("nombre") or not datos_editados.get("apellidos"):
                st.error("⚠️ Nombre y apellidos son obligatorios.")
                return False
                
            if not datos_editados.get("tipo_tutor"):
                st.error("⚠️ El tipo de tutor es obligatorio.")
                return False
                
            # Validar email
            email = datos_editados.get("email")
            if email and "@" not in email:
                st.error("⚠️ Email no válido.")
                return False
                
            # Validar NIF
            nif = datos_editados.get("nif")
            if nif and not validar_dni_cif(nif):
                st.error("⚠️ NIF/DNI no válido.")
                return False

            # Procesar empresa según rol
            if session_state.role == "admin":
                empresa_sel = datos_editados.pop("empresa_sel", "")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]
                else:
                    # Mantener empresa actual si no se selecciona nueva
                    tutor_actual = df_tutores[df_tutores["id"] == tutor_id].iloc[0] if not df_tutores.empty else None
                    if tutor_actual is not None:
                        datos_editados["empresa_id"] = tutor_actual.get("empresa_id")
            elif session_state.role == "gestor":
                datos_editados["empresa_id"] = session_state.user.get("empresa_id")

            if not datos_editados.get("empresa_id"):
                st.error("⚠️ Los tutores deben tener una empresa asignada.")
                return False

            # Limpiar solo campos auxiliares, mantener todos los valores editados
            datos_limpios = {}
            for k, v in datos_editados.items():
                if not k.endswith("_sel"):  # Solo remover campos auxiliares
                    datos_limpios[k] = v  # Mantener todos los valores, incluso vacíos
            
            datos_limpios["updated_at"] = datetime.utcnow().isoformat()

            # Actualizar en base de datos
            result = supabase.table("tutores").update(datos_limpios).eq("id", tutor_id).execute()
            
            if result and not (hasattr(result, 'error') and result.error):
                # Limpiar cache
                data_service.get_tutores_completos.clear()
                st.success("✅ Tutor actualizado correctamente.")
                return True
            else:
                error_msg = getattr(result, 'error', 'Error desconocido') if hasattr(result, 'error') else 'Error desconocido'
                st.error(f"❌ Error al actualizar tutor: {error_msg}")
                return False
                
        except Exception as e:
            st.error(f"❌ Error al guardar tutor: {e}")
            return False

    def crear_tutor(datos_nuevos):
        """Crea un nuevo tutor."""
        try:
            # Validaciones básicas
            if not datos_nuevos.get("nombre") or not datos_nuevos.get("apellidos"):
                st.error("⚠️ Nombre y apellidos son obligatorios.")
                return False
                
            if not datos_nuevos.get("tipo_tutor"):
                st.error("⚠️ El tipo de tutor es obligatorio.")
                return False

            # Validar email
            email = datos_nuevos.get("email")
            if email and "@" not in email:
                st.error("⚠️ Email no válido.")
                return False
                
            # Validar NIF
            nif = datos_nuevos.get("nif")
            if nif and not validar_dni_cif(nif):
                st.error("⚠️ NIF/DNI no válido.")
                return False

            # Procesar empresa según rol
            if session_state.role == "admin":
                empresa_sel = datos_nuevos.pop("empresa_sel", "")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_nuevos["empresa_id"] = empresas_dict[empresa_sel]
                else:
                    datos_nuevos["empresa_id"] = None
            elif session_state.role == "gestor":
                datos_nuevos["empresa_id"] = session_state.user.get("empresa_id")

            if not datos_nuevos.get("empresa_id"):
                st.error("⚠️ Los tutores deben tener una empresa asignada.")
                return False

            # Generar ID para el tutor
            tutor_id = str(uuid.uuid4())
            datos_nuevos["id"] = tutor_id

            # NO filtrar valores vacíos aquí - dejar que el usuario pueda limpiar campos
            datos_limpios = {k: v for k, v in datos_nuevos.items() 
                           if not k.endswith("_sel")}
            
            # Añadir timestamp
            datos_limpios["created_at"] = datetime.utcnow().isoformat()

            # Crear en base de datos
            result = supabase.table("tutores").insert(datos_limpios).execute()
            
            if result and not (hasattr(result, 'error') and result.error):
                # Limpiar cache
                data_service.get_tutores_completos.clear()
                st.success("✅ Tutor creado correctamente.")
                return True
            else:
                st.error("❌ Error al crear tutor.")
                return False
                
        except Exception as e:
            st.error(f"❌ Error al crear tutor: {e}")
            return False

    # =========================
    # PREPARAR DATOS PARA DISPLAY
    # =========================
    def preparar_datos_display(df_orig):
        """Prepara datos para mostrar en formularios con valores compatibles."""
        df_display = df_orig.copy()
        
        # Convertir empresa_id a nombre para admin
        if session_state.role == "admin" and empresas_dict:
            df_display["empresa_sel"] = df_display["empresa_id"].map(
                {v: k for k, v in empresas_dict.items()}
            ).fillna("")

        # Asegurar que tipo_tutor tenga valores válidos
        if "tipo_tutor" in df_display.columns:
            df_display["tipo_tutor"] = df_display["tipo_tutor"].fillna("").astype(str)
            # Normalizar valores
            df_display["tipo_tutor"] = df_display["tipo_tutor"].replace({
                "Interno": "interno",
                "Externo": "externo"
            })

        # Asegurar que especialidad esté en las opciones
        if "especialidad" in df_display.columns:
            df_display["especialidad"] = df_display["especialidad"].fillna("")
            # Solo mantener especialidades válidas
            mask_validas = df_display["especialidad"].isin(especialidades_opciones)
            df_display.loc[~mask_validas, "especialidad"] = ""

        # Mapear códigos de tipo_documento a texto para display
        if "tipo_documento" in df_display.columns:
            tipo_doc_map = {10: "NIF", 20: "Pasaporte", 60: "NIE", "": "", None: ""}
            df_display["tipo_documento_texto"] = df_display["tipo_documento"].map(tipo_doc_map).fillna("")

        # Añadir columna de estado del CV
        df_display["cv_status"] = df_display["cv_url"].apply(
            lambda x: "✅ Con CV" if pd.notna(x) and x != "" else "⏳ Sin CV"
        )
        
        return df_display

    # =========================
    # MOSTRAR TABLA Y FORMULARIOS
    # =========================
    if df_filtrado.empty:
        if df_tutores.empty:
            st.info("ℹ️ No hay tutores registrados.")
        else:
            st.warning("🔍 No se encontraron tutores con los filtros aplicados.")
            if st.button("🔄 Limpiar filtros"):
                st.rerun()
    else:
        # Preparar datos para display con valores compatibles
        df_display = preparar_datos_display(df_filtrado)
        
        # Columnas visibles en la tabla + gestión CV
        columnas_visibles = [
            "nombre", "apellidos", "email", "telefono",
            "tipo_tutor", "especialidad", "cv_status"
        ]
        
        if "empresa_nombre" in df_display.columns:
            columnas_visibles.insert(-1, "empresa_nombre")

        # =========================
        # TABLA PRINCIPAL - ESTILO GRUPOS.PY
        # =========================
        st.markdown("### Selecciona un tutor para editarlo:")

        try:
            event = st.dataframe(
                df_display[columnas_visibles],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="tabla_tutores_principal"
            )
        except Exception as e:
            st.error(f"❌ Error al mostrar tabla: {e}")
            return

        # Manejar selección para edición
        if event and hasattr(event, 'selection') and event.selection.get("rows"):
            try:
                selected_idx = event.selection["rows"][0]
                if selected_idx < len(df_display):
                    tutor_seleccionado = df_display.iloc[selected_idx]
                    
                    # Mostrar formulario de edición manual
                    st.markdown("---")
                    st.markdown("### ✏️ Editar Tutor Seleccionado")
                    st.caption(f"Editando: {tutor_seleccionado['nombre']} {tutor_seleccionado.get('apellidos', '')}")
                    
                    with st.form(f"form_editar_tutor_{tutor_seleccionado['id']}", clear_on_submit=False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            nombre = st.text_input("Nombre *", value=tutor_seleccionado.get('nombre', ''), key="edit_nombre")
                            email = st.text_input("Email", value=tutor_seleccionado.get('email', ''), key="edit_email")
                            tipo_tutor = st.selectbox("Tipo de tutor *", ["", "interno", "externo"], 
                                                    index=["", "interno", "externo"].index(tutor_seleccionado.get('tipo_tutor', '')) if tutor_seleccionado.get('tipo_tutor') in ["", "interno", "externo"] else 0,
                                                    key="edit_tipo")
                            nif = st.text_input("NIF/DNI", value=tutor_seleccionado.get('nif', ''), key="edit_nif")
                            direccion = st.text_input("Dirección", value=tutor_seleccionado.get('direccion', ''), key="edit_direccion")
                        
                        with col2:
                            apellidos = st.text_input("Apellidos *", value=tutor_seleccionado.get('apellidos', ''), key="edit_apellidos")
                            telefono = st.text_input("Teléfono", value=tutor_seleccionado.get('telefono', ''), key="edit_telefono")
                            especialidad = st.selectbox("Especialidad", especialidades_opciones, 
                                                      index=especialidades_opciones.index(tutor_seleccionado.get('especialidad', '')) if tutor_seleccionado.get('especialidad') in especialidades_opciones else 0,
                                                      key="edit_especialidad")
                            
                            # Crear selectbox para tipo_documento con códigos
                            opciones_tipo_doc = [("", "Seleccionar tipo"), (10, "NIF"), (20, "Pasaporte"), (60, "NIE")]
                            valor_actual = tutor_seleccionado.get('tipo_documento')
                            if pd.isna(valor_actual) or valor_actual == "":
                                indice_tipo_doc = 0
                            else:
                                indice_tipo_doc = 0
                                for i, (codigo, texto) in enumerate(opciones_tipo_doc):
                                    if codigo == valor_actual:
                                        indice_tipo_doc = i
                                        break
                            
                            tipo_documento = st.selectbox(
                                "Tipo documento", 
                                opciones_tipo_doc,
                                index=indice_tipo_doc,
                                format_func=lambda x: x[1],  # Mostrar solo el texto
                                key="edit_tipo_doc"
                            )
                            ciudad = st.text_input("Ciudad", value=tutor_seleccionado.get('ciudad', ''), key="edit_ciudad")
                        
                        col3, col4 = st.columns(2)
                        with col3:
                            provincia = st.text_input("Provincia", value=tutor_seleccionado.get('provincia', ''), key="edit_provincia")
                            # Verificar si titulacion existe en BD antes de mostrar
                            titulacion = None
                            if "titulacion" in df_tutores.columns:
                                titulacion = st.text_area("Titulación", value=tutor_seleccionado.get('titulacion', ''), key="edit_titulacion")
                        with col4:
                            codigo_postal = st.text_input("Código postal", value=tutor_seleccionado.get('codigo_postal', ''), key="edit_cp")
                            if session_state.role == "admin" and empresas_dict:
                                empresa_sel = st.selectbox("Empresa", [""] + sorted(empresas_dict.keys()), 
                                                         index=([""] + sorted(empresas_dict.keys())).index(tutor_seleccionado.get('empresa_sel', '')) if tutor_seleccionado.get('empresa_sel') in ([""] + sorted(empresas_dict.keys())) else 0,
                                                         key="edit_empresa")
                        
                        if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                            datos_editados = {
                                "nombre": nombre,
                                "apellidos": apellidos,
                                "email": email,
                                "telefono": telefono,
                                "nif": nif,
                                "tipo_tutor": tipo_tutor,
                                "especialidad": especialidad,
                                "tipo_documento": tipo_documento[0] if tipo_documento and tipo_documento[0] != "" else None,
                                "direccion": direccion,
                                "ciudad": ciudad,
                                "provincia": provincia,
                                "codigo_postal": codigo_postal
                            }
                            
                            # Solo añadir titulacion si existe en BD
                            if titulacion is not None and "titulacion" in df_tutores.columns:
                                datos_editados["titulacion"] = titulacion
                            
                            if session_state.role == "admin" and empresas_dict:
                                datos_editados["empresa_sel"] = empresa_sel
                            
                            if guardar_tutor(tutor_seleccionado['id'], datos_editados):
                                st.rerun()
                                
            except Exception as e:
                st.error(f"❌ Error al procesar selección: {e}")

        st.divider()

        # =========================
        # CREAR NUEVO TUTOR (DEBAJO DE LA TABLA)
        # =========================
        if puede_modificar:
            with st.expander("➕ Crear Nuevo Tutor", expanded=False):
                # Formulario manual completamente sin componentes externos
                with st.form("crear_tutor_form", clear_on_submit=True):
                    st.markdown("**Datos del nuevo tutor**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        nombre = st.text_input("Nombre *", key="nuevo_nombre")
                        email = st.text_input("Email", key="nuevo_email")
                        tipo_tutor = st.selectbox("Tipo de tutor *", ["", "interno", "externo"], key="nuevo_tipo")
                        nif = st.text_input("NIF/DNI", key="nuevo_nif")
                        direccion = st.text_input("Dirección", key="nuevo_direccion")
                    
                    with col2:
                        apellidos = st.text_input("Apellidos *", key="nuevo_apellidos")
                        telefono = st.text_input("Teléfono", key="nuevo_telefono")
                        especialidad = st.selectbox("Especialidad", especialidades_opciones, key="nuevo_especialidad")
                        tipo_documento = st.selectbox(
                            "Tipo documento", 
                            [("", "Seleccionar tipo"), (10, "NIF"), (20, "Pasaporte"), (60, "NIE")],
                            format_func=lambda x: x[1],  # Mostrar solo el texto
                            key="nuevo_tipo_doc"
                        )
                        ciudad = st.text_input("Ciudad", key="nuevo_ciudad")
                    
                    col3, col4 = st.columns(2)
                    with col3:
                        provincia = st.text_input("Provincia", key="nuevo_provincia")
                        titulacion = st.text_area("Titulación", key="nuevo_titulacion")
                    with col4:
                        codigo_postal = st.text_input("Código postal", key="nuevo_cp")
                        if session_state.role == "admin" and empresas_dict:
                            empresa_sel = st.selectbox("Empresa", [""] + sorted(empresas_dict.keys()), key="nuevo_empresa")
                    
                    if st.form_submit_button("✅ Crear Tutor", type="primary"):
                        datos_nuevos = {
                            "nombre": nombre,
                            "apellidos": apellidos,
                            "email": email,
                            "telefono": telefono,
                            "nif": nif,
                            "tipo_tutor": tipo_tutor,
                            "especialidad": especialidad,
                            "tipo_documento": tipo_documento[0] if tipo_documento and tipo_documento[0] != "" else None,
                            "direccion": direccion,
                            "ciudad": ciudad,
                            "provincia": provincia,
                            "codigo_postal": codigo_postal,
                            "titulacion": titulacion
                        }
                        
                        if session_state.role == "admin" and empresas_dict:
                            datos_nuevos["empresa_sel"] = empresa_sel
                        
                        if crear_tutor(datos_nuevos):
                            st.rerun()

        st.divider()

        # =========================
        # GESTIÓN DE CURRÍCULUMS (RESPETA FILTROS)
        # =========================
        st.markdown("### 📄 Gestión de Currículums")
        st.caption("Subir y gestionar currículums (filtros aplicados)")
        
        # Aplicar los mismos filtros que la tabla principal
        tutores_cv_filtrados = df_display.copy()
        
        # Separar tutores con y sin CV de los datos YA filtrados
        tutores_sin_cv = tutores_cv_filtrados[~(tutores_cv_filtrados["cv_url"].notna() & (tutores_cv_filtrados["cv_url"] != ""))].copy()
        tutores_con_cv = tutores_cv_filtrados[tutores_cv_filtrados["cv_url"].notna() & (tutores_cv_filtrados["cv_url"] != "")].copy()
        
        # Mostrar métricas de CV filtradas
        col1, col2 = st.columns(2)
        with col1:
            st.metric("⏳ Sin CV", len(tutores_sin_cv))
        with col2:
            st.metric("✅ Con CV", len(tutores_con_cv))
        
        # Gestión de tutores SIN CV
        if not tutores_sin_cv.empty:
            st.warning(f"⚠️ {len(tutores_sin_cv)} tutores sin CV (mostrados con filtros):")
            
            for idx, tutor in tutores_sin_cv.head(5).iterrows():
                nombre_completo = f"{tutor['nombre']} {tutor.get('apellidos', '')}".strip()
                empresa_nombre = tutor.get("empresa_nombre", "Sin empresa")
                
                with st.expander(f"📤 Subir CV - {nombre_completo} ({empresa_nombre})", expanded=False):
                    mostrar_gestion_cv_individual(supabase, session_state, data_service, tutor, puede_modificar)
            
            if len(tutores_sin_cv) > 5:
                st.caption(f"... y {len(tutores_sin_cv) - 5} tutores más sin CV")
        else:
            if len(tutores_cv_filtrados) > 0:
                st.success("✅ Todos los tutores mostrados tienen CV")
            else:
                st.info("ℹ️ No hay tutores para mostrar con los filtros aplicados")

        # Gestión de tutores CON CV
        if not tutores_con_cv.empty:
            with st.expander(f"📄 Gestionar CVs existentes ({len(tutores_con_cv)})", expanded=False):
                for idx, tutor in tutores_con_cv.iterrows():
                    nombre_completo = f"{tutor['nombre']} {tutor.get('apellidos', '')}".strip()
                    empresa_nombre = tutor.get("empresa_nombre", "Sin empresa")
                    
                    col_info, col_actions = st.columns([3, 1])
                    
                    with col_info:
                        st.markdown(f"**👤 {nombre_completo}** - {empresa_nombre}")
                    
                    with col_actions:
                        # Botones en una sola fila
                        col_btn1, col_btn2, col_btn3 = st.columns(3)
                        
                        with col_btn1:
                            if st.button("👁️", key=f"ver_cv_{tutor['id']}", help="Ver CV"):
                                st.markdown(f"🔗 [Abrir CV]({tutor['cv_url']})")
                        
                        with col_btn2:
                            if st.button("🔄", key=f"update_cv_{tutor['id']}", help="Actualizar CV"):
                                # Formulario inline para actualizar
                                with st.form(f"update_form_{tutor['id']}"):
                                    cv_file = st.file_uploader(
                                        "Nuevo CV",
                                        type=["pdf", "doc", "docx"],
                                        key=f"new_cv_{tutor['id']}",
                                        help="PDF, DOC o DOCX, máximo 10MB"
                                    )
                                    
                                    if st.form_submit_button("📤 Actualizar"):
                                        if cv_file is not None:
                                            success = subir_cv_tutor(supabase, data_service, tutor, cv_file)
                                            if success:
                                                st.rerun()
                        
                        with col_btn3:
                            if st.button("🗑️", key=f"delete_cv_{tutor['id']}", help="Eliminar CV"):
                                if eliminar_cv_tutor(supabase, data_service, tutor['id']):
                                    st.rerun()

    # =========================
    # EXPORTACIÓN Y RESUMEN
    # =========================
    if not df_filtrado.empty:
        with st.expander("📊 Exportar y Resumen", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 Exportar Tutores CSV", use_container_width=True):
                    export_csv(df_filtrado, "tutores_export")
                    
            with col2:
                st.markdown("**Resumen de tutores filtrados:**")
                total_filtrados = len(df_filtrado)
                st.write(f"- Total tutores: {total_filtrados}")
                
                if total_filtrados > 0:
                    internos_pct = (len(df_filtrado[df_filtrado["tipo_tutor"] == "interno"]) / total_filtrados) * 100
                    st.write(f"- Tutores internos: {internos_pct:.1f}%")
                    
                    cv_filtrados = len(df_filtrado[df_filtrado["cv_url"].notna() & (df_filtrado["cv_url"] != "")])
                    con_cv_pct = (cv_filtrados / total_filtrados) * 100
                    st.write(f"- Con CV subido: {con_cv_pct:.1f}%")

    # =========================
    # INFORMACIÓN Y AYUDA
    # =========================
    with st.expander("ℹ️ Información sobre Tutores FUNDAE", expanded=False):
        st.markdown("""
        **Gestión de Tutores para FUNDAE**
        
        **Tipos de tutores:**
        - **Internos**: Empleados de la empresa que imparten formación
        - **Externos**: Colaboradores especializados contratados
        
        **Requisitos FUNDAE:**
        - CV actualizado obligatorio para validación
        - Especialidad según catálogo oficial de familias profesionales
        - Experiencia mínima en el área de especialización
        
        **Flujo recomendado:**
        1. Registrar tutor con datos completos
        2. Subir CV en formato PDF (recomendado)
        3. Asignar especialidad según familia profesional
        4. Vincular a grupos formativos correspondientes
        
        **Documentación requerida:**
        - Curriculum vitae actualizado
        - Titulación académica
        - Certificados de experiencia profesional
        """)
        
    st.caption("💡 Los tutores cualificados son esenciales para la aprobación de grupos formativos en FUNDAE.")


def mostrar_gestion_cv_individual(supabase, session_state, data_service, tutor, puede_modificar):
    """Gestión de CV para un tutor individual."""
    if not puede_modificar:
        st.info("ℹ️ No tienes permisos para subir CVs")
        return
    
    st.info("📱 **Para móviles:** Asegúrate de que el archivo esté guardado en tu dispositivo")
    
    cv_file = st.file_uploader(
        "Seleccionar CV",
        type=["pdf", "doc", "docx"],
        key=f"upload_cv_individual_{tutor['id']}",
        help="PDF, DOC o DOCX, máximo 10MB"
    )
    
    if cv_file is not None:
        file_size_mb = cv_file.size / (1024 * 1024)
        
        col_info_file, col_size_file = st.columns(2)
        with col_info_file:
            st.success(f"✅ **Archivo:** {cv_file.name}")
        with col_size_file:
            color = "🔴" if file_size_mb > 10 else "🟢"
            st.write(f"{color} **Tamaño:** {file_size_mb:.2f} MB")
        
        if file_size_mb > 10:
            st.error("❌ Archivo muy grande. Máximo 10MB.")
        else:
            if st.button(
                f"📤 Subir CV de {tutor['nombre']}", 
                key=f"btn_upload_individual_{tutor['id']}", 
                type="primary",
                use_container_width=True
            ):
                success = subir_cv_tutor(supabase, data_service, tutor, cv_file)
                if success:
                    st.rerun()
    else:
        st.info("📂 Selecciona un archivo para continuar")


def subir_cv_tutor(supabase, data_service, tutor, cv_file):
    """Función helper para subir CV de tutor."""
    try:
        with st.spinner("📤 Subiendo CV..."):
            # Validar que el archivo se puede leer
            try:
                file_bytes = cv_file.getvalue()
                if len(file_bytes) == 0:
                    raise ValueError("El archivo está vacío")
            except Exception as e:
                st.error(f"❌ Error al leer el archivo: {e}")
                return False
            
            # Generar path estructurado
            empresa_id_tutor = tutor.get("empresa_id")
            file_extension = cv_file.name.split(".")[-1] if "." in cv_file.name else "pdf"
            timestamp = int(datetime.now().timestamp())
            filename = f"empresa_{empresa_id_tutor}/tutores/cv_{tutor['id']}_{timestamp}.{file_extension}"
            
            # Subir a bucket de Supabase
            try:
                upload_res = supabase.storage.from_("curriculums").upload(
                    filename, 
                    file_bytes, 
                    file_options={
                        "content-type": cv_file.type,
                        "cache-control": "3600",
                        "upsert": "true"
                    }
                )
                
                # Verificar si la subida fue exitosa
                if hasattr(upload_res, 'error') and upload_res.error:
                    raise Exception(f"Error de subida: {upload_res.error}")
                
                # Obtener URL pública
                public_url = supabase.storage.from_("curriculums").get_public_url(filename)
                if not public_url:
                    raise Exception("No se pudo generar URL pública")
                
                # Actualizar base de datos
                supabase.table("tutores").update({
                    "cv_url": public_url
                }).eq("id", tutor["id"]).execute()
                
                # Limpiar cache
                data_service.get_tutores_completos.clear()
                
                st.success("✅ CV subido correctamente!")
                st.balloons()
                
                # Mostrar link directo
                st.markdown(f"🔗 [Ver CV subido]({public_url})")
                
                return True
                
            except Exception as upload_error:
                st.error(f"❌ Error al subir archivo: {upload_error}")
                
                st.info("""
                🔧 **Soluciones:**
                - Verifica que el bucket 'curriculums' existe en Supabase
                - Asegúrate de que tienes permisos de subida
                - Intenta con un archivo más pequeño
                - Contacta al administrador si persiste el error
                """)
                return False
    
    except Exception as e:
        st.error(f"❌ Error general: {e}")
        return False


def eliminar_cv_tutor(supabase, data_service, tutor_id):
    """Función helper para eliminar CV de tutor."""
    try:
        confirmar_key = f"confirm_delete_cv_{tutor_id}"
        if st.session_state.get(confirmar_key, False):
            # Eliminar archivo del storage también
            try:
                # Obtener la URL actual para extraer el path del archivo
                tutor_actual = supabase.table("tutores").select("cv_url").eq("id", tutor_id).execute()
                if tutor_actual.data and tutor_actual.data[0].get("cv_url"):
                    cv_url = tutor_actual.data[0]["cv_url"]
                    # Extraer el path del archivo de la URL
                    if "curriculums/" in cv_url:
                        file_path = cv_url.split("curriculums/")[-1].split("?")[0]
                        # Intentar eliminar del storage
                        try:
                            supabase.storage.from_("curriculums").remove([file_path])
                        except Exception:
                            pass  # Si no se puede eliminar del storage, continuar
            
            except Exception:
                pass  # Si hay error obteniendo la URL, continuar
            
            # Eliminar referencia de la base de datos
            supabase.table("tutores").update({
                "cv_url": None
            }).eq("id", tutor_id).execute()
            
            # Limpiar cache
            data_service.get_tutores_completos.clear()
            
            st.success("✅ CV eliminado.")
            # Limpiar el estado de confirmación
            st.session_state[confirmar_key] = False
            return True
        else:
            st.session_state[confirmar_key] = True
            st.warning("⚠️ Confirmar eliminación - Presiona de nuevo para confirmar")
            return False
    except Exception as e:
        st.error(f"❌ Error al eliminar CV: {e}")
        return False
