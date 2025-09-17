import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
from utils import export_csv, validar_dni_cif
from components.listado_con_ficha import listado_con_ficha
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
    # MÉTRICAS UNIFICADAS (UNA SOLA VEZ)
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

        # Sin barra de progreso - ya está en las métricas

    st.divider()

    # =========================
    # FILTROS DE BÚSQUEDA UNIFICADOS
    # =========================
    st.markdown("### 🔍 Filtros de Búsqueda")
    col1, col2, col3, col4 = st.columns(4)
    
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

    # Mostrar resultados de filtros
    if len(df_filtrado) != len(df_tutores):
        st.info(f"🎯 {len(df_filtrado)} de {len(df_tutores)} tutores mostrados")

    st.divider()

    # =========================
    # DEFINIR PERMISOS
    # =========================
    puede_modificar = data_service.can_modify_data()

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
                    datos_editados["empresa_id"] = None
            elif session_state.role == "gestor":
                datos_editados["empresa_id"] = session_state.user.get("empresa_id")

            if not datos_editados.get("empresa_id"):
                st.error("⚠️ Los tutores deben tener una empresa asignada.")
                return False

            # Limpiar campos auxiliares
            datos_limpios = {k: v for k, v in datos_editados.items() 
                           if not k.endswith("_sel")}

            # Actualizar en base de datos
            result = supabase.table("tutores").update(datos_limpios).eq("id", tutor_id).execute()
            
            if result and not (hasattr(result, 'error') and result.error):
                # Limpiar cache
                data_service.get_tutores_completos.clear()
                st.success("✅ Tutor actualizado correctamente.")
                return True
            else:
                st.error("❌ Error al actualizar tutor.")
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

            # Limpiar campos auxiliares
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
    # CONFIGURACIÓN DE CAMPOS PARA LISTADO_CON_FICHA
    # =========================
    def get_campos_dinamicos(datos):
        """Campos a mostrar dinámicamente."""
        campos_base = [
            "nombre", "apellidos", "nif", "email", "telefono",
            "tipo_tutor", "especialidad", "tipo_documento", "titulacion", 
            "experiencia_profesional", "experiencia_docente",
            "direccion", "ciudad", "provincia", "codigo_postal"
        ]
        
        # Solo admin puede seleccionar empresa
        if session_state.role == "admin":
            campos_base.insert(-1, "empresa_sel")
            
        return campos_base

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

    campos_select = {
        "tipo_tutor": ["", "interno", "externo"],
        "especialidad": especialidades_opciones,
        "tipo_documento": [
            ("", "Seleccionar tipo"),
            ("NIF", "NIF"),
            ("Pasaporte", "Pasaporte"), 
            ("NIE", "NIE")
        ]
    }
    
    if session_state.role == "admin" and empresas_dict:
        empresas_opciones = [""] + sorted(empresas_dict.keys())
        campos_select["empresa_sel"] = empresas_opciones

    campos_readonly = ["id", "created_at", "cv_url"]
    campos_obligatorios = ["nombre", "apellidos", "tipo_tutor"]
    
    campos_help = {
        "nombre": "Nombre del tutor (obligatorio)",
        "apellidos": "Apellidos del tutor (obligatorio)", 
        "email": "Email de contacto del tutor",
        "telefono": "Teléfono de contacto",
        "nif": "NIF/DNI del tutor (obligatorio para FUNDAE)",
        "tipo_documento": "Tipo de documento de identidad (obligatorio FUNDAE)",
        "tipo_tutor": "Tipo: interno (empleado) o externo (colaborador) - obligatorio",
        "especialidad": "Área de especialización del tutor",
        "empresa_sel": "Empresa a la que pertenece (solo admin)",
        "direccion": "Dirección completa",
        "ciudad": "Ciudad de residencia",
        "provincia": "Provincia",
        "codigo_postal": "Código postal",
        "titulacion": "Titulación académica del tutor",
        "experiencia_profesional": "Años de experiencia profesional",
        "experiencia_docente": "Años de experiencia en docencia/formación"
    }

    # =========================
    # LISTADO PRINCIPAL CON GESTIÓN DE CV INTEGRADA
    # =========================
    st.markdown("### 📊 Listado de Tutores")
    
    if df_filtrado.empty:
        if df_tutores.empty:
            st.info("ℹ️ No hay tutores registrados.")
        else:
            st.warning("🔍 No se encontraron tutores con los filtros aplicados.")
            if st.button("🔄 Limpiar filtros"):
                st.rerun()
    else:
        # Preparar datos para display
        df_display = df_filtrado.copy()
        
        # Convertir relaciones a campos de selección
        if session_state.role == "admin" and empresas_dict:
            # Mapear empresa_id a nombre para admin
            df_display["empresa_sel"] = df_display["empresa_id"].map(
                {v: k for k, v in empresas_dict.items()}
            ).fillna("")

        # Columnas visibles en la tabla + gestión CV
        columnas_visibles = [
            "nombre", "apellidos", "email", "telefono",
            "tipo_tutor", "especialidad", "cv_status"
        ]
        
        # Añadir columna de estado del CV
        df_display["cv_status"] = df_display["cv_url"].apply(
            lambda x: "✅ Con CV" if pd.notna(x) and x != "" else "⏳ Sin CV"
        )
        
        if "empresa_nombre" in df_display.columns:
            columnas_visibles.insert(-1, "empresa_nombre")

        # Función para convertir selects a IDs antes de guardar
        def preparar_datos_para_guardar(datos):
            # Convertir empresa_sel a empresa_id si es admin
            if session_state.role == "admin" and "empresa_sel" in datos:
                empresa_sel = datos.get("empresa_sel", "")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos["empresa_id"] = empresas_dict[empresa_sel]
                datos.pop("empresa_sel", None)
            elif session_state.role == "gestor":
                # Para gestor, usar su empresa automáticamente
                datos["empresa_id"] = session_state.user.get("empresa_id")
            
            return datos

        def guardar_wrapper(tutor_id, datos):
            datos = preparar_datos_para_guardar(datos)
            return guardar_tutor(tutor_id, datos)
            
        def crear_wrapper(datos):
            datos = preparar_datos_para_guardar(datos)
            return crear_tutor(datos)

        # Mensaje informativo según rol
        if session_state.role == "gestor":
            st.info("💡 **Información:** Como gestor, solo puedes gestionar tutores de tu empresa.")
        else:
            st.info("💡 **Información:** Los tutores deben tener CV y especialización para cumplir requisitos FUNDAE.")

        # =========================
        # TABLA PRINCIPAL CON GESTIÓN CV INTEGRADA
        # =========================
        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Tutor",
            on_save=guardar_wrapper,
            on_create=None,  # Creación abajo
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            campos_obligatorios=campos_obligatorios,
            allow_creation=False,
            campos_help=campos_help,
            search_columns=[]  # Sin búsqueda - ya filtrado arriba
        )

        # =========================
        # CREAR NUEVO TUTOR (DEBAJO DE LA TABLA)
        # =========================
        if puede_modificar:
            with st.expander("➕ Crear Nuevo Tutor", expanded=False):
                st.markdown("**Formulario de creación de tutor**")
                
                # Crear DataFrame vacío para el formulario
                df_vacio = pd.DataFrame()
                
                listado_con_ficha(
                    df=df_vacio,
                    columnas_visibles=[],
                    titulo="Tutor",
                    on_save=None,
                    on_create=crear_wrapper,
                    id_col="id",
                    campos_select=campos_select,
                    campos_readonly=campos_readonly,
                    campos_dinamicos=get_campos_dinamicos,
                    campos_obligatorios=campos_obligatorios,
                    allow_creation=True,
                    campos_help=campos_help,
                    search_columns=[]
                )

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
                                if eliminar_cv_tutor(supabase, data_service, tutor["id"]):
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
            # Eliminar referencia de la base de datos
            supabase.table("tutores").update({
                "cv_url": None
            }).eq("id", tutor_id).execute()
            
            # Limpiar cache
            data_service.get_tutores_completos.clear()
            
            st.success("✅ CV eliminado.")
            return True
        else:
            st.session_state[confirmar_key] = True
            st.warning("⚠️ Confirmar eliminación - Presiona de nuevo para confirmar")
            return False
    except Exception as e:
        st.error(f"❌ Error al eliminar CV: {e}")
        return False
