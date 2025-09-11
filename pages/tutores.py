import streamlit as st
import pandas as pd
from utils import export_csv, validar_dni_cif
from components.listado_con_ficha import listado_con_ficha
from services.data_service import get_data_service
import uuid
from datetime import datetime

def main(supabase, session_state):
    st.subheader("👨‍🏫 Tutores")
    st.caption("Gestión de tutores internos y externos vinculados a grupos formativos.")

    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # =========================
    # Inicializar DataService
    # =========================
    try:
        data_service = get_data_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error al inicializar servicio de datos: {e}")
        return

    # =========================
    # Cargar datos usando DataService
    # =========================
    try:
        # Usar método mejorado del DataService
        df = data_service.get_tutores_completos()
        
        # Cargar empresas para selects si es admin
        empresas_dict = {}
        empresas_opciones = [""]
        
        if session_state.role == "admin":
            try:
                empresas_res = supabase.table("empresas").select("id, nombre").execute()
                empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
                empresas_opciones = [""] + sorted(empresas_dict.keys())
            except Exception as e:
                st.warning(f"⚠️ Error al cargar empresas: {e}")

    except Exception as e:
        st.error(f"❌ Error al cargar tutores: {e}")
        return

    # =========================
    # Filtros avanzados
    # =========================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        search_text = st.text_input("🔍 Buscar", placeholder="Nombre, email, especialidad...")
    
    with col2:
        filter_tipo = st.selectbox("Tipo de tutor", ["Todos", "interno", "externo"])
    
    with col3:
        if session_state.role == "admin" and not df.empty:
            empresas_filtro = ["Todas"] + df["empresa_nombre"].dropna().unique().tolist()
            filter_empresa = st.selectbox("Empresa", empresas_filtro)
        else:
            filter_empresa = "Todas"
    
    with col4:
        if not df.empty:
            specialties = df["especialidad"].dropna().unique().tolist()
            filter_especialidad = st.selectbox("Especialidad", ["Todas"] + specialties)
        else:
            filter_especialidad = "Todas"

    # Aplicar filtros
    df_filtered = df.copy()
    
    if search_text:
        mask = (
            df_filtered["nombre"].str.contains(search_text, case=False, na=False) |
            df_filtered["apellidos"].str.contains(search_text, case=False, na=False) |
            df_filtered["email"].str.contains(search_text, case=False, na=False) |
            df_filtered["especialidad"].str.contains(search_text, case=False, na=False)
        )
        df_filtered = df_filtered[mask]
    
    if filter_tipo != "Todos":
        df_filtered = df_filtered[df_filtered["tipo_tutor"] == filter_tipo]
    
    if filter_empresa != "Todas" and session_state.role == "admin":
        df_filtered = df_filtered[df_filtered["empresa_nombre"] == filter_empresa]
    
    if filter_especialidad != "Todas":
        df_filtered = df_filtered[df_filtered["especialidad"] == filter_especialidad]

    # =========================
    # Métricas rápidas
    # =========================
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Tutores", len(df))
        with col2:
            internos = len(df[df["tipo_tutor"] == "interno"])
            st.metric("🏢 Internos", internos)
        with col3:
            externos = len(df[df["tipo_tutor"] == "externo"])
            st.metric("🌐 Externos", externos)
        with col4:
            con_cv = len(df[df["cv_url"].notna() & (df["cv_url"] != "")])
            st.metric("📄 Con CV", con_cv)

    # =========================
    # Funciones de gestión de tutores
    # =========================
    def guardar_tutor(datos):
        """Guarda o actualiza un tutor."""
        try:
            # Validaciones básicas
            if not datos.get("nombre") or not datos.get("apellidos"):
                st.error("⚠️ Nombre y apellidos son obligatorios.")
                return False
                
            if not datos.get("tipo_tutor"):
                st.error("⚠️ El tipo de tutor es obligatorio.")
                return False
                
            if datos.get("email") and "@" not in datos.get("email", ""):
                st.error("⚠️ Email no válido.")
                return False
                
            if datos.get("nif") and not validar_dni_cif(datos["nif"]):
                st.error("⚠️ NIF/DNI no válido.")
                return False
            
            # Procesar empresa según rol
            if session_state.role == "admin" and datos.get("empresa_sel"):
                datos["empresa_id"] = empresas_dict.get(datos["empresa_sel"])
                datos.pop("empresa_sel", None)  # Remover campo temporal
            elif session_state.role == "gestor":
                datos["empresa_id"] = session_state.user.get("empresa_id")
            
            if not datos.get("empresa_id"):
                st.error("⚠️ Debes especificar una empresa válida.")
                return False
            
            # Procesar archivo CV si existe
            if "cv_file" in datos and datos["cv_file"] is not None:
                cv_file = datos.pop("cv_file")
                tutor_id = datos.get("id") or str(uuid.uuid4())
                empresa_id_tutor = datos.get("empresa_id")
                
                try:
                    # Crear ruta única para el archivo
                    file_extension = cv_file.name.split(".")[-1] if "." in cv_file.name else "pdf"
                    file_path = f"empresa_{empresa_id_tutor}/tutores/{tutor_id}_{cv_file.name}"
                    
                    # Subir archivo a Supabase Storage
                    upload_res = supabase.storage.from_("curriculums").upload(
                        file_path,
                        cv_file.getvalue(),
                        {"upsert": True}
                    )
                    
                    # Obtener URL pública
                    public_url = supabase.storage.from_("curriculums").get_public_url(file_path)
                    datos["cv_url"] = public_url
                    
                except Exception as e:
                    st.warning(f"⚠️ Error al subir CV: {e}")
            
            # Limpiar campos temporales
            datos_limpios = {k: v for k, v in datos.items() 
                           if not k.endswith("_sel") and k != "cv_file"}
            
            # Usar DataService para guardar
            if datos_limpios.get("id"):
                # Actualizar tutor existente
                success = data_service.update_tutor(datos_limpios["id"], datos_limpios)
                if success:
                    st.success("✅ Tutor actualizado correctamente.")
                    st.rerun()
            else:
                # Crear nuevo tutor
                success = data_service.create_tutor(datos_limpios)
                if success:
                    st.success("✅ Tutor creado correctamente.")
                    st.rerun()
            
            return success
            
        except Exception as e:
            st.error(f"❌ Error al guardar tutor: {e}")
            return False

    def crear_tutor(datos):
        """Crea un nuevo tutor."""
        # Asegurar que no tiene ID para creación
        datos.pop("id", None)
        return guardar_tutor(datos)

    # =========================
    # Configuración de campos para listado_con_ficha
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos_base = [
            "nombre", "apellidos", "email", "telefono", "nif", 
            "tipo_tutor", "especialidad", "direccion", "ciudad", 
            "provincia", "codigo_postal"
        ]
        
        # Solo admin puede seleccionar empresa
        if session_state.role == "admin":
            campos_base.append("empresa_sel")
            
        # CV siempre al final
        campos_base.append("cv_file")
            
        return campos_base

    # Especialidades disponibles
    especialidades_opciones = [
        "", "Administración y Gestión", "Comercio y Marketing", "Informática y Comunicaciones",
        "Sanidad", "Servicios Socioculturales", "Hostelería y Turismo", "Educación",
        "Industrias Alimentarias", "Química", "Imagen Personal", "Industrias Extractivas",
        "Fabricación Mecánica", "Instalación y Mantenimiento", "Electricidad y Electrónica",
        "Energía y Agua", "Transporte y Mantenimiento de Vehículos", "Edificación y Obra Civil",
        "Vidrio y Cerámica", "Madera, Mueble y Corcho", "Textil, Confección y Piel",
        "Artes Gráficas", "Imagen y Sonido", "Actividades Físicas y Deportivas",
        "Marítimo-Pesquera", "Industrias Agroalimentarias", "Agraria", "Seguridad y Medio Ambiente"
    ]

    campos_select = {
        "tipo_tutor": ["", "interno", "externo"],
        "especialidad": especialidades_opciones
    }
    
    if session_state.role == "admin":
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
        "codigo_postal": "Código postal"
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        if df.empty:
            st.info("ℹ️ No hay tutores registrados.")
        else:
            st.warning(f"🔍 No hay tutores que coincidan con los filtros aplicados.")
    else:
        # Preparar datos para mostrar - ¡AQUÍ ESTABA EL ERROR!
        df_display = df_filtered.copy()
        
        # Solo añadir empresa_sel si el usuario es admin Y existe la columna empresa_nombre
        if session_state.role == "admin" and "empresa_nombre" in df_display.columns:
            df_display["empresa_sel"] = df_display["empresa_nombre"]

        # Mostrar tabla con componente optimizado
        # Mostrar tabla con componente optimizado
        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "nombre", "apellidos", "email", "telefono",
                "nif", "tipo_tutor", "especialidad", "cv_url", "empresa_nombre"
            ],  # ✅ REMOVIDO "id" de columnas_visibles ya que se añade automáticamente
            titulo="Tutor",
            on_save=guardar_tutor,
            on_create=crear_tutor,
            id_col="id",  # ✅ Se añade automáticamente, no debe estar en columnas_visibles
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_file=campos_file,
            campos_dinamicos=get_campos_dinamicos,
            campos_obligatorios=campos_obligatorios,
            allow_creation=True,
            campos_help=campos_help,
            search_columns=["nombre", "apellidos", "email", "especialidad"]
        )

    st.divider()

    # =========================
    # FUNCIONALIDADES ADICIONALES
    # =========================
    
    # Asignación de tutores a grupos
    if not df.empty:
        st.markdown("### 👥 Asignación de Tutores a Grupos")
        
        try:
            # Cargar grupos usando DataService
            df_grupos = data_service.get_grupos_completos()
            
            if not df_grupos.empty:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Selector de tutor
                    tutor_options = df.apply(
                        lambda t: f"{t['nombre']} {t.get('apellidos', '')} ({t.get('tipo_tutor', 'N/A')})", axis=1
                    ).tolist()
                    
                    if tutor_options:
                        tutor_sel = st.selectbox("Seleccionar tutor", tutor_options)
                        tutor_idx = tutor_options.index(tutor_sel)
                        tutor_data = df.iloc[tutor_idx]
                
                with col2:
                    # Selector de grupo
                    grupo_options = df_grupos.apply(
                        lambda g: f"{g.get('codigo_grupo', 'Sin código')} - {g.get('accion_nombre', 'Sin acción')}", axis=1
                    ).tolist()
                    
                    if grupo_options:
                        grupo_sel = st.selectbox("Seleccionar grupo", grupo_options)
                        grupo_idx = grupo_options.index(grupo_sel)
                        grupo_data = df_grupos.iloc[grupo_idx]
                
                with col3:
                    st.write("")  # Espaciado
                    st.write("")  # Espaciado
                    
                    if st.button("🔗 Asignar Tutor al Grupo", use_container_width=True):
                        try:
                            # Verificar si ya existe la asignación
                            existing = supabase.table("tutores_grupos").select("id").eq(
                                "tutor_id", tutor_data["id"]
                            ).eq("grupo_id", grupo_data["id"]).execute()
                            
                            if existing.data:
                                st.warning("⚠️ Este tutor ya está asignado a este grupo.")
                            else:
                                # Crear nueva asignación
                                res = supabase.table("tutores_grupos").insert({
                                    "tutor_id": tutor_data["id"],
                                    "grupo_id": grupo_data["id"],
                                    "created_at": datetime.now().isoformat()
                                }).execute()
                                
                                if res.data:
                                    st.success("✅ Tutor asignado al grupo correctamente.")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al asignar tutor al grupo.")
                        
                        except Exception as e:
                            st.error(f"❌ Error al asignar tutor: {e}")
            else:
                st.info("ℹ️ No hay grupos disponibles para asignación.")
        
        except Exception as e:
            st.warning(f"⚠️ Error al cargar grupos: {e}")

        # Mostrar asignaciones actuales
        try:
            st.markdown("#### 📋 Asignaciones Actuales")
            
            asignaciones_res = supabase.table("tutores_grupos").select("""
                id, created_at,
                tutor:tutores(id, nombre, apellidos, tipo_tutor),
                grupo:grupos(id, codigo_grupo, accion_formativa:acciones_formativas(nombre))
            """).execute()
            
            if asignaciones_res.data:
                asignaciones_df = pd.DataFrame(asignaciones_res.data)
                
                # Aplanar datos para mostrar
                asignaciones_display = []
                for _, row in asignaciones_df.iterrows():
                    tutor_info = row.get("tutor", {})
                    grupo_info = row.get("grupo", {})
                    accion_info = grupo_info.get("accion_formativa", {}) if grupo_info else {}
                    
                    asignaciones_display.append({
                        "ID": row["id"],
                        "Tutor": f"{tutor_info.get('nombre', 'N/A')} {tutor_info.get('apellidos', '')}",
                        "Tipo": tutor_info.get("tipo_tutor", "N/A"),
                        "Grupo": grupo_info.get("codigo_grupo", "N/A"),
                        "Acción Formativa": accion_info.get("nombre", "N/A"),
                        "Fecha Asignación": row.get("created_at", "N/A")[:10]
                    })
                
                if asignaciones_display:
                    st.dataframe(
                        pd.DataFrame(asignaciones_display),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Opción para eliminar asignaciones
                    with st.expander("🗑️ Eliminar Asignación"):
                        asignacion_ids = [str(a["ID"]) for a in asignaciones_display]
                        asignacion_names = [f"{a['Tutor']} → {a['Grupo']}" for a in asignaciones_display]
                        
                        if asignacion_names:
                            sel_asignacion = st.selectbox(
                                "Seleccionar asignación a eliminar",
                                asignacion_names
                            )
                            
                            if st.button("🗑️ Eliminar Asignación", type="secondary"):
                                try:
                                    idx = asignacion_names.index(sel_asignacion)
                                    asignacion_id = asignacion_ids[idx]
                                    
                                    supabase.table("tutores_grupos").delete().eq("id", asignacion_id).execute()
                                    st.success("✅ Asignación eliminada correctamente.")
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Error al eliminar asignación: {e}")
            else:
                st.info("ℹ️ No hay asignaciones de tutores a grupos.")
        
        except Exception as e:
            st.warning(f"⚠️ Error al cargar asignaciones: {e}")

    # =========================
    # EXPORTAR DATOS
    # =========================
    if not df.empty:
        st.markdown("### 📊 Exportar Datos")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Exportar Tutores CSV", use_container_width=True):
                export_csv(df_filtered, "tutores_export")
        
        with col2:
            # Estadísticas rápidas
            st.write("**Resumen:**")
            st.write(f"- Total tutores: {len(df)}")
            st.write(f"- Filtrados: {len(df_filtered)}")
            if not df.empty:
                internos_pct = (len(df[df["tipo_tutor"] == "interno"]) / len(df)) * 100
                st.write(f"- Internos: {internos_pct:.1f}%")
