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
    # MÉTRICAS UNIFICADAS
    # =========================
    if not df_tutores.empty:
        # Calcular métricas
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
            st.metric("📄 Con CV", con_cv)

    st.divider()

    # =========================
    # Definir permisos de creación/edición
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
            
        # Ya no incluimos cv_file aquí - se gestiona por separado
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
            (10, "NIF"),
            (20, "Pasaporte"), 
            (60, "NIE")
        ]
    }
    
    if session_state.role == "admin" and empresas_dict:
        empresas_opciones = [""] + sorted(empresas_dict.keys())
        campos_select["empresa_sel"] = empresas_opciones

    campos_readonly = ["id", "created_at", "cv_url"]
    
    # Configuración de archivos
    campos_file = ["cv_file"]
    
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
        "cv_file": "Subir CV del tutor (PDF, DOC o DOCX, máximo 10MB)",
        "direccion": "Dirección completa",
        "ciudad": "Ciudad de residencia",
        "provincia": "Provincia",
        "codigo_postal": "Código postal",
        "titulacion": "Titulación académica del tutor",
        "experiencia_profesional": "Años de experiencia profesional",
        "experiencia_docente": "Años de experiencia en docencia/formación"
    }

    # =========================
    # LISTADO PRINCIPAL CON LISTADO_CON_FICHA
    # =========================
    st.markdown("### 📊 Listado de Tutores")
    
    if df_tutores.empty:
        st.info("ℹ️ No hay tutores registrados.")
    else:
        # Preparar datos para display
        df_display = df_tutores.copy()
        
        # Convertir relaciones a campos de selección
        if session_state.role == "admin" and empresas_dict:
            # Mapear empresa_id a nombre para admin
            df_display["empresa_sel"] = df_display["empresa_id"].map(
                {v: k for k, v in empresas_dict.items()}
            ).fillna("")

        # Columnas visibles en la tabla
        columnas_visibles = [
            "nombre", "apellidos", "email", "telefono",
            "tipo_tutor", "especialidad"
        ]
        if "empresa_nombre" in df_display.columns:
            columnas_visibles.append("empresa_nombre")

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

        # Usar listado_con_ficha con toda la funcionalidad integrada
        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Tutor",
            on_save=guardar_wrapper,
            on_create=crear_wrapper if puede_modificar else None,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            campos_obligatorios=campos_obligatorios,
            allow_creation=puede_modificar,
            campos_help=campos_help,
            search_columns=["nombre", "apellidos", "email", "especialidad"]
        )

    st.divider()

    # =========================
    # GESTIÓN DE CURRÍCULUMS
    # =========================
    if session_state.role in ["admin", "gestor"]:
        mostrar_seccion_curriculums(supabase, session_state, data_service, puede_modificar)

    # =========================
    # EXPORTACIÓN Y RESUMEN
    # =========================
    if not df_tutores.empty:
        with st.expander("📊 Exportar y Resumen", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 Exportar Tutores CSV", use_container_width=True):
                    export_csv(df_tutores, "tutores_export")
                    
            with col2:
                st.markdown("**Resumen de tutores:**")
                st.write(f"- Total tutores: {len(df_tutores)}")
                
                if len(df_tutores) > 0:
                    internos_pct = (len(df_tutores[df_tutores["tipo_tutor"] == "interno"]) / len(df_tutores)) * 100
                    st.write(f"- Tutores internos: {internos_pct:.1f}%")
                    
                    con_cv_pct = (len(df_tutores[df_tutores["cv_url"].notna() & (df_tutores["cv_url"] != "")]) / len(df_tutores)) * 100
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


def mostrar_seccion_curriculums(supabase, session_state, data_service, puede_modificar):
    """Gestión completa de currículums con filtros y subida de archivos."""
    st.markdown("### 📄 Gestión de Currículums")
    st.caption("Subir y gestionar currículums de tutores.")
    
    try:
        # Obtener todos los tutores según rol
        if session_state.role == "admin":
            tutores_query = supabase.table("tutores").select("""
                id, nombre, apellidos, email, nif, especialidad, cv_url, empresa_id,
                empresa:empresas(nombre)
            """).execute()
        else:
            # Gestor: solo tutores de su empresa
            empresa_id = session_state.user.get("empresa_id")
            if not empresa_id:
                st.warning("No tienes empresa asignada.")
                return
            
            tutores_query = supabase.table("tutores").select("""
                id, nombre, apellidos, email, nif, especialidad, cv_url, empresa_id,
                empresa:empresas(nombre)
            """).eq("empresa_id", empresa_id).execute()
        
        tutores_data = tutores_query.data or []
        
        if not tutores_data:
            st.info("ℹ️ No hay tutores disponibles.")
            return

        # Métricas
        total_tutores = len(tutores_data)
        con_cv = len([t for t in tutores_data if t.get("cv_url")])
        sin_cv = total_tutores - con_cv
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👨‍🏫 Total Tutores", total_tutores)
        with col2:
            st.metric("📄 Con CV", con_cv)
        with col3:
            st.metric("⏳ Sin CV", sin_cv)

        # FILTROS DE BÚSQUEDA
        st.markdown("#### 🔍 Filtros de Búsqueda")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            buscar_tutor = st.text_input(
                "🔍 Buscar tutor",
                placeholder="Nombre, email o NIF...",
                key="buscar_cv_tutor"
            )
        
        with col2:
            # Filtro por empresa (solo admin)
            if session_state.role == "admin":
                empresas_unicas = list(set([t.get("empresa", {}).get("nombre", "Sin empresa") for t in tutores_data]))
                empresa_filtro = st.selectbox(
                    "Filtrar por empresa",
                    ["Todas"] + sorted(empresas_unicas),
                    key="filtro_empresa_cv"
                )
            else:
                empresa_filtro = "Todas"
        
        with col3:
            estado_cv = st.selectbox(
                "Estado CV",
                ["Todos", "Con CV", "Sin CV"],
                key="filtro_estado_cv"
            )

        # Aplicar filtros
        tutores_filtrados = tutores_data.copy()
        
        # Filtro de búsqueda
        if buscar_tutor:
            buscar_lower = buscar_tutor.lower()
            tutores_filtrados = [
                t for t in tutores_filtrados 
                if (buscar_lower in t.get("nombre", "").lower() or 
                    buscar_lower in t.get("apellidos", "").lower() or 
                    buscar_lower in t.get("email", "").lower() or
                    buscar_lower in t.get("nif", "").lower())
            ]
        
        # Filtro por empresa
        if session_state.role == "admin" and empresa_filtro != "Todas":
            tutores_filtrados = [
                t for t in tutores_filtrados 
                if t.get("empresa", {}).get("nombre") == empresa_filtro
            ]
        
        # Filtro por estado de CV
        if estado_cv == "Con CV":
            tutores_filtrados = [t for t in tutores_filtrados if t.get("cv_url")]
        elif estado_cv == "Sin CV":
            tutores_filtrados = [t for t in tutores_filtrados if not t.get("cv_url")]

        st.markdown(f"#### 🎯 Tutores encontrados: {len(tutores_filtrados)}")

        if not tutores_filtrados:
            st.warning("🔍 No se encontraron tutores con los filtros aplicados.")
            return

        # Lista de tutores con paginación
        items_por_pagina = 10
        total_paginas = (len(tutores_filtrados) + items_por_pagina - 1) // items_por_pagina
        
        if total_paginas > 1:
            pagina_actual = st.selectbox(
                "Página",
                range(1, total_paginas + 1),
                key="pagina_curriculums"
            )
            inicio = (pagina_actual - 1) * items_por_pagina
            fin = inicio + items_por_pagina
            tutores_pagina = tutores_filtrados[inicio:fin]
        else:
            tutores_pagina = tutores_filtrados

        # Mostrar tutores
        for i, tutor in enumerate(tutores_pagina):
            tiene_cv = bool(tutor.get("cv_url"))
            
            # Crear expander con información del tutor
            nombre_completo = f"{tutor['nombre']} {tutor.get('apellidos', '')}".strip()
            empresa_nombre = tutor.get("empresa", {}).get("nombre", "Sin empresa") if tutor.get("empresa") else "Sin empresa"
            
            status_emoji = "✅" if tiene_cv else "⏳"
            status_text = "Con CV" if tiene_cv else "Pendiente"
            
            with st.expander(
                f"{status_emoji} {nombre_completo} - {empresa_nombre} ({status_text})",
                expanded=False
            ):
                col_info, col_actions = st.columns([2, 1])
                
                with col_info:
                    st.markdown(f"**📧 Email:** {tutor['email']}")
                    st.markdown(f"**🆔 NIF:** {tutor.get('nif', 'No disponible')}")
                    st.markdown(f"**🎯 Especialidad:** {tutor.get('especialidad', 'No especificada')}")
                    st.markdown(f"**🏢 Empresa:** {empresa_nombre}")
                
                with col_actions:
                    if tiene_cv:
                        # Mostrar CV existente
                        st.markdown("**📄 CV:**")
                        if st.button("👁️ Ver CV", key=f"ver_cv_{tutor['id']}"):
                            st.markdown(f"[🔗 Abrir CV]({tutor['cv_url']})")
                        
                        if st.button("🗑️ Eliminar", key=f"delete_cv_{tutor['id']}"):
                            confirmar_key = f"confirm_delete_cv_{tutor['id']}"
                            if st.session_state.get(confirmar_key, False):
                                try:
                                    # Eliminar referencia de la base de datos
                                    supabase.table("tutores").update({
                                        "cv_url": None
                                    }).eq("id", tutor["id"]).execute()
                                    
                                    # Limpiar cache
                                    data_service.get_tutores_completos.clear()
                                    
                                    st.success("✅ CV eliminado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al eliminar CV: {e}")
                            else:
                                st.session_state[confirmar_key] = True
                                st.warning("⚠️ Confirmar eliminación")
                    else:
                        if puede_modificar:
                            # Subir CV
                            st.markdown("**📤 Subir CV**")
                            
                            st.info("📱 **Para móviles:** Asegúrate de que el archivo esté guardado en tu dispositivo")
                            
                            cv_file = st.file_uploader(
                                "Seleccionar CV",
                                type=["pdf", "doc", "docx"],
                                key=f"upload_cv_{tutor['id']}",
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
                                        key=f"btn_upload_cv_{tutor['id']}", 
                                        type="primary",
                                        use_container_width=True
                                    ):
                                        try:
                                            with st.spinner("📤 Subiendo CV..."):
                                                # Validar que el archivo se puede leer
                                                try:
                                                    file_bytes = cv_file.getvalue()
                                                    if len(file_bytes) == 0:
                                                        raise ValueError("El archivo está vacío")
                                                except Exception as e:
                                                    st.error(f"❌ Error al leer el archivo: {e}")
                                                    continue
                                                
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
                                                    
                                                    # Recargar página
                                                    import time
                                                    time.sleep(2)
                                                    st.rerun()
                                                    
                                                except Exception as upload_error:
                                                    st.error(f"❌ Error al subir archivo: {upload_error}")
                                                    
                                                    st.info("""
                                                    🔧 **Soluciones:**
                                                    - Verifica que el bucket 'curriculums' existe en Supabase
                                                    - Asegúrate de que tienes permisos de subida
                                                    - Intenta con un archivo más pequeño
                                                    - Contacta al administrador si persiste el error
                                                    """)
                                        
                                        except Exception as e:
                                            st.error(f"❌ Error general: {e}")
                            else:
                                st.info("📂 Selecciona un archivo para continuar")
                        else:
                            st.info("ℹ️ No tienes permisos para subir CVs")

        # Estadísticas finales
        if tutores_filtrados:
            st.markdown("#### 📊 Estadísticas")
            total_mostrados = len(tutores_filtrados)
            con_cv_filtrados = sum(1 for t in tutores_filtrados if t.get("cv_url"))
            sin_cv_filtrados = total_mostrados - con_cv_filtrados
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("👥 Mostrados", total_mostrados)
            with col2:
                st.metric("✅ Con CV", con_cv_filtrados)
            with col3:
                st.metric("⏳ Sin CV", sin_cv_filtrados)
            
            if total_mostrados > 0:
                progreso = (con_cv_filtrados / total_mostrados) * 100
                st.progress(con_cv_filtrados / total_mostrados, f"Progreso: {progreso:.1f}%")
        
    except Exception as e:
        st.error(f"❌ Error al cargar gestión de currículums: {e}")


    # =========================
    # VERIFICACIONES DE CONFIGURACIÓN (Solo para admin)
    # =========================
    if session_state.role == "admin":
        with st.expander("🔧 Configuración del Sistema (Admin)", expanded=False):
            st.markdown("**Verificar configuración de buckets de Supabase:**")
            
            # Verificar bucket curriculums
            try:
                bucket_list = supabase.storage.list_buckets()
                bucket_names = [b.name for b in bucket_list if hasattr(b, 'name')]
                
                if "curriculums" in bucket_names:
                    st.success("✅ Bucket 'curriculums' configurado correctamente")
                else:
                    st.error("❌ Bucket 'curriculums' no encontrado")
                    st.info("💡 Crear bucket 'curriculums' en Supabase Storage")
                    
            except Exception as e:
                st.warning(f"⚠️ No se pudo verificar buckets: {e}")
                
            # Mostrar estadísticas de archivos
            if not df_tutores.empty:
                tutores_con_cv = df_tutores[df_tutores["cv_url"].notna() & (df_tutores["cv_url"] != "")]
                st.info(f"📄 {len(tutores_con_cv)} de {len(df_tutores)} tutores tienen CV subido ({len(tutores_con_cv)/len(df_tutores)*100:.1f}%)")
