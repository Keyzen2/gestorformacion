import streamlit as st
import pandas as pd
from utils import export_csv, validar_dni_cif
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
        query = supabase.table("tutores").select("*")
        if session_state.role == "gestor":
            query = query.eq("empresa_id", session_state.user.get("empresa_id"))
        tutores_res = query.execute().data
        df = pd.DataFrame(tutores_res) if tutores_res else pd.DataFrame()
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
    tipo_filter   = st.selectbox("Filtrar por tipo", ["Todos", "Interno", "Externo"])
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
            # Subida de CV si se adjunta archivo
            if "cv_file" in datos and datos["cv_file"] is not None:
                file_path = f"{tutor_id}.pdf"
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
            if "cv_file" in datos and datos["cv_file"] is not None:
                file_path = f"{tutor_id}.pdf"
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
    # Llamada al CRUD
    # =========================
    listado_crud(
        df,
        columnas_visibles=[
            "id", "nombre", "apellidos", "email", "telefono",
            "nif", "tipo_tutor", "especialidad", "cv_url"
        ],
        titulo="Tutor",
        on_save=guardar_tutor,
        on_create=crear_tutor,
        id_col="id",
        campos_select={
            "tipo_tutor": ["Interno", "Externo"]
        },
        campos_file={
            "cv_file": {"label": "📄 Subir CV (PDF)", "type": ["pdf"]}
        }
    )
    
