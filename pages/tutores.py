import streamlit as st
import pandas as pd
from utils import export_csv
from components.listado_crud import listado_crud
import uuid
from datetime import datetime

def main(supabase, session_state):
    st.subheader("👨‍🏫 Tutores")
    st.caption("Gestión de tutores internos y externos vinculados a grupos formativos.")
    st.divider()

    # Permisos
    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # =========================
    # Cargar tutores
    # =========================
    try:
        base_select = (
            "id, nombre, apellidos, email, telefono, nif, tipo_tutor, "
            "especialidad, cv_url, empresa:empresas(nombre)"
        )

        if session_state.role == "gestor":
            query = supabase.table("tutores").select(base_select).eq(
                "empresa_id", session_state.user.get("empresa_id")
            )
        else:  # admin
            query = supabase.table("tutores").select(base_select)

        tutores_res = query.execute().data
        df = pd.DataFrame(tutores_res) if tutores_res else pd.DataFrame()

        # Aplanar la columna empresa para mostrar solo el nombre
        if "empresa" in df.columns:
            df["empresa"] = df["empresa"].apply(
                lambda x: x.get("nombre") if isinstance(x, dict) else x
            )

    except Exception as e:
        st.error(f"❌ Error al cargar tutores: {e}")
        return

    if df.empty:
        st.info("ℹ️ No hay tutores registrados.")
        return

    # =========================
    # Filtros
    # =========================
    st.markdown("### 🔍 Filtros")
    filtro_nombre = st.text_input("Buscar por nombre, apellidos o NIF")
    tipo_filter = st.selectbox("Filtrar por tipo", ["Todos", "Interno", "Externo"])
    especialidades = ["Todas"] + sorted(df["especialidad"].dropna().unique()) if "especialidad" in df else ["Todas"]
    especialidad_filter = st.selectbox("Filtrar por especialidad", especialidades)

    if filtro_nombre:
        sq = filtro_nombre.lower()
        df = df[
            df["nombre"].str.lower().str.contains(sq, na=False) |
            df["apellidos"].str.lower().str.contains(sq, na=False) |
            df["nif"].str.lower().str.contains(sq, na=False)
        ]
    if tipo_filter != "Todos":
        df = df[df["tipo_tutor"] == tipo_filter]
    if especialidad_filter != "Todas":
        df = df[df["especialidad"] == especialidad_filter]

    # =========================
    # Exportar CSV filtrado
    # =========================
    if not df.empty:
        export_csv(df, filename="tutores_filtrados.csv")
        st.divider()

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_tutor(tutor_id, datos):
        try:
            # Determinar empresa_id para la ruta del CV
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                datos["empresa_id"] = empresa_id
            else:
                if "empresa_id" in datos and datos["empresa_id"]:
                    empresa_id = empresas_dict[datos["empresa_id"]]
                    datos["empresa_id"] = empresa_id
                else:
                    empresa_id = None

            # Subida de CV si se adjunta archivo
            if "cv_file" in datos and datos["cv_file"] is not None and empresa_id:
                file_path = f"{empresa_id}/{tutor_id}.pdf"
                supabase.storage.from_("currículums").upload(
                    file_path,
                    datos["cv_file"].getvalue(),
                    {"upsert": True}
                )
                public_url = supabase.storage.from_("currículums").get_public_url(file_path)
                datos["cv_url"] = public_url
                del datos["cv_file"]

            supabase.table("tutores").update(datos).eq("id", tutor_id).execute()
            st.success("✅ Cambios guardados correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar tutor: {e}")

    def crear_tutor(datos):
        try:
            tutor_id = str(uuid.uuid4())

            # Determinar empresa_id para la ruta del CV
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                datos["empresa_id"] = empresa_id
            else:
                if "empresa_id" in datos and datos["empresa_id"]:
                    empresa_id = empresas_dict[datos["empresa_id"]]
                    datos["empresa_id"] = empresa_id
                else:
                    empresa_id = None

            # Subida de CV
            if "cv_file" in datos and datos["cv_file"] is not None and empresa_id:
                file_path = f"{empresa_id}/{tutor_id}.pdf"
                supabase.storage.from_("currículums").upload(
                    file_path,
                    datos["cv_file"].getvalue(),
                    {"upsert": True}
                )
                public_url = supabase.storage.from_("currículums").get_public_url(file_path)
                datos["cv_url"] = public_url
                del datos["cv_file"]

            datos["id"] = tutor_id
            datos["created_at"] = datetime.utcnow().isoformat()
            supabase.table("tutores").insert(datos).execute()
            st.success("✅ Tutor creado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al crear tutor: {e}")

    # =========================
    # Campos select según rol
    # =========================
    especialidades_genericas = [
        "Matemáticas", "Lengua", "Inglés", "Informática", "Ciencias",
        "Historia", "Arte", "Educación Física", "Música",
        "Formación Profesional", "Otro"
    ]

    campos_select = {
        "tipo_tutor": ["Interno", "Externo"],
        "especialidad": especialidades_genericas
    }

    if session_state.role == "admin":
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data}
        campos_select["empresa_id"] = list(empresas_dict.keys())

    # =========================
    # Llamada al CRUD
    # =========================
    listado_crud(
        df,
        columnas_visibles=[
            "id", "nombre", "apellidos", "email", "telefono",
            "nif", "tipo_tutor", "especialidad", "cv_url", "empresa"
        ],
        titulo="Tutor",
        on_save=guardar_tutor,
        on_create=crear_tutor,
        id_col="id",
        campos_select=campos_select,
        campos_file={
            "cv_file": {"label": "📄 Subir CV (PDF)", "type": ["pdf"]}
        }
                )
