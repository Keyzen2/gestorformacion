import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import uuid
from utils import export_csv, validar_dni_cif
from components.listado_con_ficha import listado_con_ficha
from services.data_service import get_data_service

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
    # Cargar datos
    # =========================
    try:
        df = data_service.get_tutores_completos()
        
        # Empresas para admin
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
    # Filtros
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
    # Funciones de gestión
    # =========================
    def guardar_tutor(datos):
        try:
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
            if session_state.role == "admin" and datos.get("empresa_sel"):
                datos["empresa_id"] = empresas_dict.get(datos["empresa_sel"])
                datos.pop("empresa_sel", None)
            elif session_state.role == "gestor":
                datos["empresa_id"] = session_state.user.get("empresa_id")
            if not datos.get("empresa_id"):
                st.error("⚠️ Debes especificar una empresa válida.")
                return False
            if "cv_file" in datos and datos["cv_file"] is not None:
                cv_file = datos.pop("cv_file")
                tutor_id = datos.get("id") or str(uuid.uuid4())
                empresa_id_tutor = datos.get("empresa_id")
                try:
                    file_extension = cv_file.name.split(".")[-1] if "." in cv_file.name else "pdf"
                    file_path = f"empresa_{empresa_id_tutor}/tutores/{tutor_id}_{cv_file.name}"
                    upload_res = supabase.storage.from_("curriculums").upload(
                        file_path,
                        cv_file.getvalue(),
                        {"upsert": True}
                    )
                    public_url = supabase.storage.from_("curriculums").get_public_url(file_path)
                    datos["cv_url"] = public_url
                except Exception as e:
                    st.warning(f"⚠️ Error al subir CV: {e}")
            datos_limpios = {k: v for k, v in datos.items() if not k.endswith("_sel") and k != "cv_file"}
            if datos_limpios.get("id"):
                success = data_service.update_tutor(datos_limpios["id"], datos_limpios)
                if success:
                    st.success("✅ Tutor actualizado correctamente.")
                    st.rerun()
            else:
                success = data_service.create_tutor(datos_limpios)
                if success:
                    st.success("✅ Tutor creado correctamente.")
                    st.rerun()
            return True
        except Exception as e:
            st.error(f"❌ Error al guardar tutor: {e}")
            return False

    def crear_tutor(datos):
        datos.pop("id", None)
        return guardar_tutor(datos)

    def get_campos_dinamicos(datos):
        campos_base = [
            "nombre", "apellidos", "nif", "email", "telefono",
            "tipo_tutor", "especialidad",
            "titulacion", "experiencia_profesional", "experiencia_docente",
            "direccion", "ciudad", "provincia", "codigo_postal",
            "cv_file"
        ]
        if session_state.role == "admin":
            campos_base.insert(-1, "empresa_sel")
        return campos_base

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
        "cv_file": {"label": "📄 Curriculum Vitae", "type": ["pdf", "doc", "docx"], "help": "Subir CV del tutor (PDF recomendado, máximo 10MB)"}
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
    # Mostrar listado y formulario
    # =========================
    listado_con_ficha(
        df_filtered,
        columnas_visibles=[
            "nombre", "apellidos", "email", "telefono",
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
        campos_obligatorios=campos_obligatorios,
        allow_creation=True,
        campos_help=campos_help,
        search_columns=["nombre", "apellidos", "email", "especialidad"]
    )

    st.divider()

    # =========================
    # Exportar datos
    # =========================
    if not df.empty:
        st.markdown("### 📊 Exportar Datos")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Exportar Tutores CSV", use_container_width=True):
                export_csv(df_filtered, "tutores_export")
        with col2:
            st.write("**Resumen:**")
            st.write(f"- Total tutores: {len(df)}")
            st.write(f"- Filtrados: {len(df_filtered)}")
            internos_pct = (len(df[df["tipo_tutor"] == "interno"]) / len(df)) * 100 if len(df) else 0
            st.write(f"- Internos: {internos_pct:.1f}%")
