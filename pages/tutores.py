import streamlit as st
import pandas as pd
from utils import export_csv
from components.listado_con_ficha import listado_con_ficha
import uuid
from datetime import datetime
from services.data_service import get_data_service

def main(supabase, session_state):
    st.subheader("👨‍🏫 Tutores")
    st.caption("Gestión de tutores internos y externos vinculados a grupos formativos.")

    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # =========================
    # Cargar datos
    # =========================
    try:
        ds = get_data_service(supabase, session_state)

        # Carga de tutores con empresa aplanada
        df = ds.get_tutores(include_empresa=True)

        # Asegurar columna empresa_nombre
        if "empresa_nombre" not in df.columns:
            df["empresa_nombre"] = ""

        # Cargar empresas para selects (solo admin)
        if session_state.role == "admin":
            empresas_dict = ds.get_empresas_dict()
            empresas_opciones = [""] + sorted(empresas_dict.keys())
        else:
            empresas_dict = {}
            empresas_opciones = []

    except Exception as e:
        st.error(f"❌ Error al cargar tutores: {e}")
        return

    # =========================
    # Métricas
    # =========================
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("👨‍🏫 Total Tutores", len(df))
        
        with col2:
            internos = len(df[df["tipo_tutor"] == "Interno"]) if "tipo_tutor" in df.columns else 0
            st.metric("🏢 Internos", internos)
        
        with col3:
            externos = len(df[df["tipo_tutor"] == "Externo"]) if "tipo_tutor" in df.columns else 0
            st.metric("🌐 Externos", externos)
        
        with col4:
            con_cv = len(df[df["cv_url"].notna()]) if "cv_url" in df.columns else 0
            st.metric("📄 Con CV", con_cv)

    st.divider()

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filtro_nombre = st.text_input("🔍 Buscar por nombre, apellidos o NIF")
    
    with col2:
        tipo_filter = st.selectbox("Filtrar por tipo", ["Todos", "Interno", "Externo"])
    
    with col3:
        if not df.empty and "especialidad" in df.columns:
            especialidades = ["Todas"] + sorted(df["especialidad"].dropna().unique())
        else:
            especialidades = ["Todas"]
        especialidad_filter = st.selectbox("Filtrar por especialidad", especialidades)

    # Aplicar filtros
    df_filtered = df.copy()
    
    if filtro_nombre:
        sq = filtro_nombre.lower()
        df_filtered = df_filtered[
            df_filtered.get("nombre", pd.Series(dtype=str)).str.lower().str.contains(sq, na=False) |
            df_filtered.get("apellidos", pd.Series(dtype=str)).fillna("").str.lower().str.contains(sq, na=False) |
            df_filtered.get("nif", pd.Series(dtype=str)).fillna("").str.lower().str.contains(sq, na=False)
        ]
    
    if tipo_filter != "Todos" and "tipo_tutor" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["tipo_tutor"] == tipo_filter]
    
    if especialidad_filter != "Todas" and "especialidad" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["especialidad"] == especialidad_filter]

    # Exportar CSV
    if not df_filtered.empty:
        export_csv(df_filtered, filename="tutores_filtrados.csv")
    
    st.divider()

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_tutor(tutor_id, datos_editados):
        """Función para guardar cambios en un tutor."""
        try:
            # Validaciones
            if not datos_editados.get("nombre") or not datos_editados.get("email"):
                st.error("⚠️ Nombre y email son obligatorios.")
                return

            # Procesar empresa
            if session_state.role == "gestor":
                datos_editados["empresa_id"] = session_state.user.get("empresa_id")
            elif session_state.role == "admin" and "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if empresa_sel:
                    datos_editados["empresa_id"] = empresas_dict.get(empresa_sel)

            # Procesar archivo CV
            if "cv_file" in datos_editados and datos_editados["cv_file"] is not None:
                cv_file = datos_editados.pop("cv_file")
                empresa_id_tutor = datos_editados.get("empresa_id") or session_state.user.get("empresa_id")
                
                if empresa_id_tutor:
                    try:
                        file_path = f"empresa_{empresa_id_tutor}/tutores/{tutor_id}_{cv_file.name}"
                        
                        supabase.storage.from_("curriculums").upload(
                            file_path,
                            cv_file.getvalue(),
                            {"upsert": True}
                        )
                        public_url = supabase.storage.from_("curriculums").get_public_url(file_path)
                        datos_editados["cv_url"] = public_url
                    except Exception as e:
                        st.warning(f"⚠️ Error al subir CV: {e}")

            # Actualizar tutor
            supabase.table("tutores").update(datos_editados).eq("id", tutor_id).execute()
            st.success("✅ Tutor actualizado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar tutor: {e}")

    def crear_tutor(datos_nuevos):
        """Función para crear un nuevo tutor."""
        try:
            # Validaciones
            if not datos_nuevos.get("nombre") or not datos_nuevos.get("email"):
                st.error("⚠️ Nombre y email son obligatorios.")
                return

            # Procesar empresa
            if session_state.role == "gestor":
                datos_nuevos["empresa_id"] = session_state.user.get("empresa_id")
            elif session_state.role == "admin" and datos_nuevos.get("empresa_sel"):
                empresa_sel = datos_nuevos.pop("empresa_sel")
                datos_nuevos["empresa_id"] = empresas_dict.get(empresa_sel)

            if not datos_nuevos.get("empresa_id"):
                st.error("⚠️ Debes especificar una empresa.")
                return

            # Procesar archivo CV
            if "cv_file" in datos_nuevos and datos_nuevos["cv_file"] is not None:
                cv_file = datos_nuevos.pop("cv_file")
                tutor_temp_id = str(uuid.uuid4())
                file_path = f"empresa_{datos_nuevos['empresa_id']}/tutores/{tutor_temp_id}_{cv_file.name}"
                
                try:
                    supabase.storage.from_("curriculums").upload(
                        file_path,
                        cv_file.getvalue()
                    )
                    public_url = supabase.storage.from_("curriculums").get_public_url(file_path)
                    datos_nuevos["cv_url"] = public_url
                except Exception as e:
                    st.warning(f"⚠️ Error al subir CV: {e}")

            # Añadir fecha de creación
            datos_nuevos["created_at"] = datetime.utcnow().isoformat()

            # Crear tutor
            result = supabase.table("tutores").insert(datos_nuevos).execute()
            if result.data:
                st.success("✅ Tutor creado correctamente.")
                st.rerun()
            else:
                st.error("❌ Error al crear el tutor.")
        except Exception as e:
            st.error(f"❌ Error al crear tutor: {e}")

    # =========================
    # Campos dinámicos
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos_base = [
            "nombre", "apellidos", "email", "telefono", "nif", 
            "tipo_tutor", "especialidad", "direccion", "ciudad", 
            "provincia", "codigo_postal", "cv_file"
        ]
        if session_state.role == "admin":
            campos_base.insert(-1, "empresa_sel")
        return campos_base

    # =========================
    # Configuración de campos
    # =========================
    especialidades_genericas = [
        "", "Matemáticas", "Lengua", "Inglés", "Informática", "Ciencias",
        "Historia", "Arte", "Educación Física", "Música",
        "Formación Profesional", "Tecnología", "Administración", 
        "Comercio y Marketing", "Sanidad", "Servicios Socioculturales",
        "Hostelería y Turismo", "Otro"
    ]

    campos_select = {
        "tipo_tutor": ["Interno", "Externo"],
        "especialidad": especialidades_genericas
    }
    if session_state.role == "admin":
        campos_select["empresa_sel"] = empresas_opciones

    campos_readonly = ["created_at"]

    campos_file = {
        "cv_file": {"label": "📄 Curriculum Vitae (PDF)", "type": ["pdf"]}
    }

    campos_help = {
        "email": "Email único del tutor (obligatorio)",
        "nif": "NIF/DNI del tutor",
        "tipo_tutor": "Interno (empleado) o Externo (colaborador)",
        "especialidad": "Área de especialización del tutor",
        "cv_file": "Archivo PDF con el curriculum vitae",
        "empresa_sel": "Empresa a la que pertenece el tutor (solo admin)"
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
        df_display = df_filtered.copy()
        if session_state.role == "admin":
            df_display["empresa_sel"] = df_display["empresa_nombre"]

        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "id", "nombre", "apellidos", "email", "telefono",
                "nif", "tipo_tutor", "especialidad", "cv_url", "empresa_nombre"
            ],
            titulo="Tutor",
            on_save=guardar_tutor,
            on_create=crear_tutor,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_file=campos_file,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=True,
            campos_help=campos_help
        )

    st.divider()

    # =========================
    # FUNCIONALIDADES ADICIONALES
    # =========================
    if not df.empty:
        st.markdown("### 👥 Asignación de Tutores a Grupos")
        try:
            if session_state.role == "gestor":
                grupos_res = supabase.table("grupos").select(
                    "id, codigo_grupo, accion_formativa:acciones_formativas(nombre)"
                ).eq("empresa_id", session_state.user.get("empresa_id")).execute()
            else:
                grupos_res = supabase.table("grupos").select(
                    "id, codigo_grupo, accion_formativa:acciones_formativas(nombre)"
                ).execute()
            grupos_disponibles = grupos_res.data or []
            
            if grupos_disponibles:
                col1, col2 = st.columns(2)
                with col1:
                    tutor_options = df.apply(
                        lambda t: f"{t['nombre']} {t.get('apellidos','')} ({t.get('tipo_tutor','')})", axis=1
                    ).tolist()
                    if tutor_options:
                        tutor_sel = st.selectbox("Seleccionar tutor", tutor_options)
                        tutor_idx = tutor_options.index(tutor_sel)
                        tutor_data = df.iloc[tutor_idx]
                with col2:
                    grupo_options = [
                        f"{g['codigo_grupo']} - {g['accion_formativa']['nombre'] if g.get('accion_formativa') else 'Sin acción'}"
                        for g in grupos_disponibles
                    ]
                    if grupo_options:
                        grupo_sel = st.selectbox("Seleccionar grupo", grupo_options)
                        grupo_idx = grupo_options.index(grupo_sel)
                        grupo_data = grupos_disponibles[grupo_idx]

                if st.button("✅ Asignar tutor al grupo"):
                    try:
                        existe = supabase.table("tutores_grupos")\
                            .select("id")\
                            .eq("tutor_id", tutor_data["id"])\
                            .eq("grupo_id", grupo_data["id"])\
                            .execute()
                        if existe.data:
                            st.warning("⚠️ Este tutor ya está asignado a este grupo.")
                        else:
                            supabase.table("tutores_grupos").insert({
                                "tutor_id": tutor_data["id"],
                                "grupo_id": grupo_data["id"],
                                "created_at": datetime.utcnow().isoformat()
                            }).execute()
                            st.success("✅ Tutor asignado al grupo correctamente.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al asignar tutor: {e}")
        except Exception as e:
            st.error(f"❌ Error al cargar grupos: {e}")

    if not df.empty:
        st.markdown("### 📋 Asignaciones Actuales")
        try:
            if session_state.role == "gestor":
                asignaciones_query = """
                    id, created_at,
                    tutor:tutores(id, nombre, apellidos, tipo_tutor),
                    grupo:grupos(id, codigo_grupo, empresa_id, accion_formativa:acciones_formativas(nombre))
                """
                asignaciones_res = supabase.table("tutores_grupos").select(asignaciones_query).execute()
                asignaciones_empresa = []
                for asig in (asignaciones_res.data or []):
                    if asig.get("grupo") and isinstance(asig["grupo"], dict):
                        if asig["grupo"].get("empresa_id") == session_state.user.get("empresa_id"):
                            asignaciones_empresa.append(asig)
                asignaciones_data = asignaciones_empresa
            else:
                asignaciones_query = """
                    id, created_at,
                    tutor:tutores(id, nombre, apellidos, tipo_tutor),
                    grupo:grupos(id, codigo_grupo, accion_formativa:acciones_formativas(nombre))
                """
                asignaciones_res = supabase.table("tutores_grupos").select(asignaciones_query).execute()
                asignaciones_data = asignaciones_res.data or []

            if asignaciones_data:
                for asig in asignaciones_data:
                    tutor_info = asig.get("tutor", {})
                    grupo_info = asig.get("grupo", {})
                    accion_info = grupo_info.get("accion_formativa", {}) if grupo_info else {}
                    
                    with st.expander(f"👨‍🏫 {tutor_info.get('nombre', '')} {tutor_info.get('apellidos', '')} → 📚 {grupo_info.get('codigo_grupo', '')}"):
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            st.write(f"**Tutor:** {tutor_info.get('nombre', '')} {tutor_info.get('apellidos', '')}")
                            st.write(f"**Tipo:** {tutor_info.get('tipo_tutor', '')}")
                        with col2:
                            st.write(f"**Grupo:** {grupo_info.get('codigo_grupo', '')}")
                            st.write(f"**Acción:** {accion_info.get('nombre', 'No especificada')}")
                        with col3:
                            if st.button("🗑️ Eliminar", key=f"remove_asig_{asig['id']}"):
                                try:
                                    supabase.table("tutores_grupos").delete().eq("id", asig["id"]).execute()
                                    st.success("✅ Asignación eliminada.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al eliminar: {e}")
            else:
                st.info("ℹ️ No hay asignaciones de tutores a grupos.")
        except Exception as e:
            st.error(f"❌ Error al cargar asignaciones: {e}")

    if not df.empty:
        st.divider()
        st.markdown("### 📊 Estadísticas de Tutores")
        col1, col2 = st.columns(2)
        with col1:
            if "tipo_tutor" in df.columns:
                tipo_counts = df["tipo_tutor"].value_counts()
                st.markdown("#### 👥 Distribución por tipo")
                for tipo, count in tipo_counts.items():
                    st.write(f"• **{tipo}:** {count} tutores")
        with col2:
            if "especialidad" in df.columns:
                esp_counts = df["especialidad"].dropna().value_counts().head(5)
                st.markdown("#### 🎯 Top 5 especialidades")
                for esp, count in esp_counts.items():
                    st.write(f"• **{esp}:** {count} tutores")

    st.divider()
    st.caption("💡 Los tutores pueden ser internos (empleados) o externos (colaboradores) y se asignan a grupos formativos específicos.")
    
