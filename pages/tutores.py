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
            st.metric("🌍 Externos", externos)
        with col4:
            st.metric("📄 Con CV", con_cv)

    st.divider()

    # =========================
    # FUNCIONES CRUD SIMPLIFICADAS
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
            if session_state.role == "admin" and datos_editados.get("empresa_sel"):
                datos_editados["empresa_id"] = empresas_dict.get(datos_editados["empresa_sel"])
                datos_editados.pop("empresa_sel", None)
            elif session_state.role == "gestor":
                datos_editados["empresa_id"] = session_state.user.get("empresa_id")

            if not datos_editados.get("empresa_id"):
                st.error("⚠️ Debes especificar una empresa válida.")
                return False

            # Manejar subida de CV
            if "cv_file" in datos_editados and datos_editados["cv_file"] is not None:
                cv_file = datos_editados.pop("cv_file")
                try:
                    # Generar path del archivo
                    empresa_id_tutor = datos_editados.get("empresa_id")
                    file_extension = cv_file.name.split(".")[-1] if "." in cv_file.name else "pdf"
                    file_path = f"empresa_{empresa_id_tutor}/tutores/{tutor_id}_{cv_file.name}"
                    
                    # Subir archivo
                    upload_res = supabase.storage.from_("curriculums").upload(
                        file_path,
                        cv_file.getvalue(),
                        {"upsert": True}
                    )
                    
                    # Obtener URL pública
                    public_url = supabase.storage.from_("curriculums").get_public_url(file_path)
                    datos_editados["cv_url"] = public_url
                    
                except Exception as e:
                    st.warning(f"⚠️ Error al subir CV: {e}")

            # Limpiar campos auxiliares
            datos_limpios = {k: v for k, v in datos_editados.items() 
                           if not k.endswith("_sel") and k != "cv_file"}

            # Actualizar en base de datos
            success = supabase.table("tutores").update(datos_limpios).eq("id", tutor_id).execute()
            
            if success:
                st.success("✅ Tutor actualizado correctamente.")
                st.rerun()
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
            if session_state.role == "admin" and datos_nuevos.get("empresa_sel"):
                datos_nuevos["empresa_id"] = empresas_dict.get(datos_nuevos["empresa_sel"])
                datos_nuevos.pop("empresa_sel", None)
            elif session_state.role == "gestor":
                datos_nuevos["empresa_id"] = session_state.user.get("empresa_id")

            if not datos_nuevos.get("empresa_id"):
                st.error("⚠️ Debes especificar una empresa válida.")
                return False

            # Generar ID para el tutor
            tutor_id = str(uuid.uuid4())
            datos_nuevos["id"] = tutor_id

            # Manejar subida de CV
            if "cv_file" in datos_nuevos and datos_nuevos["cv_file"] is not None:
                cv_file = datos_nuevos.pop("cv_file")
                try:
                    # Generar path del archivo
                    empresa_id_tutor = datos_nuevos.get("empresa_id")
                    file_path = f"empresa_{empresa_id_tutor}/tutores/{tutor_id}_{cv_file.name}"
                    
                    # Subir archivo
                    upload_res = supabase.storage.from_("curriculums").upload(
                        file_path,
                        cv_file.getvalue(),
                        {"upsert": True}
                    )
                    
                    # Obtener URL pública
                    public_url = supabase.storage.from_("curriculums").get_public_url(file_path)
                    datos_nuevos["cv_url"] = public_url
                    
                except Exception as e:
                    st.warning(f"⚠️ Error al subir CV: {e}")

            # Limpiar campos auxiliares
            datos_limpios = {k: v for k, v in datos_nuevos.items() 
                           if not k.endswith("_sel") and k != "cv_file"}
            
            # Añadir timestamp
            datos_limpios["created_at"] = datetime.utcnow().isoformat()

            # Crear en base de datos
            success = supabase.table("tutores").insert(datos_limpios).execute()
            
            if success:
                st.success("✅ Tutor creado correctamente.")
                st.rerun()
                return True
            else:
                st.error("❌ Error al crear tutor.")
                return False
                
        except Exception as e:
            st.error(f"❌ Error al crear tutor: {e}")
            return False

    # =========================
    # CONFIGURACIÓN DE CAMPOS
    # =========================
    def get_campos_dinamicos(datos):
        """Campos a mostrar dinámicamente."""
        campos_base = [
            "nombre", "apellidos", "nif", "email", "telefono",
            "tipo_tutor", "especialidad", "titulacion", 
            "experiencia_profesional", "experiencia_docente",
            "direccion", "ciudad", "provincia", "codigo_postal",
            "cv_file"
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
        "especialidad": especialidades_opciones
    }
    
    if session_state.role == "admin":
        empresas_opciones = [""] + sorted(empresas_dict.keys()) if empresas_dict else [""]
        campos_select["empresa_sel"] = empresas_opciones

    campos_readonly = ["id", "created_at"]
    
    campos_file = {
        "cv_file": {
            "label": "📄 Curriculum Vitae", 
            "type": ["pdf", "doc", "docx"], 
            "help": "Subir CV del tutor (PDF recomendado, máximo 10MB)"
        }
    }
    
    campos_obligatorios = ["nombre", "apellidos", "tipo_tutor"]
    
    campos_help = {
        "nombre": "Nombre del tutor (obligatorio)",
        "apellidos": "Apellidos del tutor (obligatorio)", 
        "email": "Email de contacto del tutor",
        "telefono": "Teléfono de contacto",
        "nif": "NIF/DNI del tutor (opcional)",
        "tipo_tutor": "Tipo: interno (empleado) o externo (colaborador) - obligatorio",
        "especialidad": "Área de especialización del tutor",
        "empresa_sel": "Empresa a la que pertenece (solo admin)",
        "cv_file": "Subir CV del tutor (PDF, DOC o DOCX)",
        "direccion": "Dirección completa",
        "ciudad": "Ciudad de residencia",
        "provincia": "Provincia",
        "codigo_postal": "Código postal",
        "titulacion": "Titulación académica del tutor",
        "experiencia_profesional": "Años de experiencia profesional",
        "experiencia_docente": "Años de experiencia en docencia/formación"
    }

    # =========================
    # LISTADO PRINCIPAL DE TUTORES
    # =========================
    if not df_tutores.empty:
        # Preparar campos calculados para formulario
        df_display = df_tutores.copy()
        
        if session_state.role == "admin" and empresas_dict:
            # Mapear empresa_id a nombre para admin
            df_display["empresa_sel"] = df_display["empresa_id"].map(
                {v: k for k, v in empresas_dict.items()}
            ).fillna("")

        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "nombre", "apellidos", "email", "telefono",
                "tipo_tutor", "especialidad", "empresa_nombre"
            ],
            titulo="Tutores",  # Plural correcto
            on_save=guardar_tutor,
            on_create=None,  # Creación manejada abajo
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_file=campos_file,
            campos_dinamicos=get_campos_dinamicos,
            campos_obligatorios=campos_obligatorios,
            allow_creation=False,  # Deshabilitado para evitar duplicación
            campos_help=campos_help,
            search_columns=["nombre", "apellidos", "email", "especialidad"]
        )
    else:
        st.info("ℹ️ No hay tutores registrados.")

    st.divider()

    # =========================
    # FORMULARIO DE CREACIÓN (AL FINAL)
    # =========================
    allow_creation = data_service.can_modify_data()
    
    if allow_creation:
        with st.expander("➕ Crear nuevo tutor", expanded=False):
            st.markdown("**Complete los datos básicos del tutor**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nuevo_nombre = st.text_input(
                    "Nombre *",
                    help="Nombre del tutor",
                    key="nuevo_nombre"
                )
                nuevo_apellidos = st.text_input(
                    "Apellidos *",
                    help="Apellidos del tutor",
                    key="nuevo_apellidos"
                )
                nuevo_email = st.text_input(
                    "Email",
                    help="Email de contacto",
                    key="nuevo_email"
                )
                nuevo_telefono = st.text_input(
                    "Teléfono",
                    help="Teléfono de contacto",
                    key="nuevo_telefono"
                )

            with col2:
                nuevo_nif = st.text_input(
                    "NIF/DNI",
                    help="Documento de identidad",
                    key="nuevo_nif"
                )
                nuevo_tipo = st.selectbox(
                    "Tipo de tutor *",
                    ["", "interno", "externo"],
                    key="nuevo_tipo"
                )
                nueva_especialidad = st.selectbox(
                    "Especialidad",
                    especialidades_opciones,
                    key="nueva_especialidad"
                )
                
                # Solo admin puede seleccionar empresa
                nueva_empresa = None
                if session_state.role == "admin":
                    nueva_empresa = st.selectbox(
                        "Empresa *",
                        empresas_opciones if empresas_dict else [""],
                        key="nueva_empresa"
                    )

            # Información académica y profesional
            col1, col2 = st.columns(2)
            with col1:
                nueva_titulacion = st.text_area(
                    "Titulación académica",
                    height=60,
                    help="Formación académica del tutor",
                    key="nueva_titulacion"
                )
                nueva_exp_profesional = st.text_input(
                    "Experiencia profesional (años)",
                    help="Años de experiencia profesional",
                    key="nueva_exp_prof"
                )
                
            with col2:
                nueva_exp_docente = st.text_input(
                    "Experiencia docente (años)",
                    help="Años de experiencia en formación",
                    key="nueva_exp_doc"
                )
                nuevo_cv = st.file_uploader(
                    "📄 Curriculum Vitae",
                    type=["pdf", "doc", "docx"],
                    help="Subir CV (máximo 10MB)",
                    key="nuevo_cv"
                )

            # Información de contacto
            nueva_direccion = st.text_input(
                "Dirección",
                help="Dirección completa",
                key="nueva_direccion"
            )
            
            col1, col2, col3 = st.columns(3)
            with col1:
                nueva_ciudad = st.text_input(
                    "Ciudad",
                    key="nueva_ciudad"
                )
            with col2:
                nueva_provincia = st.text_input(
                    "Provincia",
                    key="nueva_provincia"
                )
            with col3:
                nuevo_cp = st.text_input(
                    "Código Postal",
                    key="nuevo_cp"
                )

            # Botones de acción
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("➕ Crear tutor", type="primary", use_container_width=True):
                    if not nuevo_nombre or not nuevo_apellidos or not nuevo_tipo:
                        st.error("⚠️ Nombre, apellidos y tipo son obligatorios")
                    else:
                        datos_nuevos = {
                            "nombre": nuevo_nombre,
                            "apellidos": nuevo_apellidos,
                            "email": nuevo_email,
                            "telefono": nuevo_telefono,
                            "nif": nuevo_nif,
                            "tipo_tutor": nuevo_tipo,
                            "especialidad": nueva_especialidad,
                            "titulacion": nueva_titulacion,
                            "experiencia_profesional": nueva_exp_profesional,
                            "experiencia_docente": nueva_exp_docente,
                            "direccion": nueva_direccion,
                            "ciudad": nueva_ciudad,
                            "provincia": nueva_provincia,
                            "codigo_postal": nuevo_cp,
                            "cv_file": nuevo_cv
                        }
                        
                        if session_state.role == "admin":
                            datos_nuevos["empresa_sel"] = nueva_empresa

                        crear_tutor(datos_nuevos)
            
            with col2:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.rerun()
    else:
        st.info("ℹ️ No tienes permisos para crear nuevos tutores.")

    # =========================
    # EXPORTACIÓN DE DATOS
    # =========================
    if not df_tutores.empty:
        st.divider()
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
    # INFORMACIÓN FINAL
    # =========================
    with st.expander("ℹ️ Información sobre Tutores", expanded=False):
        st.markdown("""
        **Gestión de Tutores FUNDAE**
        
        - **Tutores internos**: Empleados de la empresa que imparten formación
        - **Tutores externos**: Colaboradores externos especializados
        - **Especialidades**: Según catálogo oficial de familias profesionales
        - **CV requerido**: Para cumplir requisitos FUNDAE de cualificación
        
        **Flujo recomendado:**
        1. Registrar tutores con sus especialidades
        2. Subir CV para validar cualificación
        3. Asignar a grupos formativos según especialidad
        4. Generar documentación FUNDAE
        """)
        
    st.caption("💡 Los tutores son esenciales para la validación FUNDAE de los grupos formativos.")
