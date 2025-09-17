import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from utils import export_csv
from services.data_service import get_data_service
from services.grupos_service import get_grupos_service


def main(supabase, session_state):
    st.markdown("## 👨‍🏫 Tutores")
    st.caption("Gestión de tutores y sus currículums.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicios
    data_service = get_data_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar tutores
    # =========================
    try:
        df_tutores = data_service.get_tutores_completos()
    except Exception as e:
        st.error(f"❌ Error al cargar tutores: {e}")
        return

    # =========================
    # Métricas básicas
    # =========================
    if not df_tutores.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👨‍🏫 Total Tutores", len(df_tutores))
        with col2:
            con_cv = len(df_tutores[df_tutores["cv_url"].notna()])
            st.metric("📂 Con Currículum", con_cv)
        with col3:
            este_mes = len(df_tutores[
                pd.to_datetime(df_tutores["created_at"], errors="coerce").dt.month == datetime.now().month
            ])
            st.metric("🆕 Nuevos este mes", este_mes)

    st.divider()

    # =========================
    # Listado de tutores
    # =========================
    st.markdown("### 📊 Listado de Tutores")

    if df_tutores.empty:
        st.info("📋 No hay tutores registrados.")
    else:
        columnas = ["nif", "nombre", "apellidos", "email", "telefono", "especialidad"]
        if session_state.role == "admin" and "empresa_nombre" in df_tutores.columns:
            columnas.append("empresa_nombre")
        if "cv_url" in df_tutores.columns:
            columnas.append("cv_url")

        event = st.dataframe(
            df_tutores[columnas],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            tutor_seleccionado = df_tutores.iloc[selected_idx]
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("✏️ Editar Tutor", type="primary", use_container_width=True):
                    st.session_state.tutor_editando = tutor_seleccionado["id"]
                    st.rerun()

    st.divider()

    # =========================
    # Crear nuevo tutor
    # =========================
    if session_state.role in ["admin", "gestor"]:
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("➕ Crear Nuevo Tutor", type="primary", use_container_width=True):
                st.session_state.tutor_editando = "nuevo"
                st.rerun()

    # =========================
    # Formulario de edición/creación
    # =========================
    if hasattr(st.session_state, 'tutor_editando') and st.session_state.tutor_editando:
        mostrar_formulario_tutor(supabase, session_state, data_service, st.session_state.tutor_editando)

    # =========================
    # Bloque de gestión de currículums
    # =========================
    if session_state.role in ["admin", "gestor"]:
        st.divider()
        mostrar_gestion_curriculums(supabase, df_tutores, empresa_id)

    # =========================
    # Exportación
    # =========================
    if not df_tutores.empty:
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Exportar a CSV"):
                export_csv(df_tutores, filename="tutores.csv")
        with col2:
            st.metric("📋 Registros mostrados", len(df_tutores))


def mostrar_formulario_tutor(supabase, session_state, data_service, tutor_id):
    """Formulario unificado para crear/editar tutores."""
    es_creacion = tutor_id == "nuevo"

    if es_creacion:
        st.markdown("### ➕ Crear Nuevo Tutor")
        tutor_data = {}
    else:
        st.markdown("### ✏️ Editar Tutor")
        try:
            result = supabase.table("tutores").select("*").eq("id", tutor_id).execute()
            if result.data:
                tutor_data = result.data[0]
            else:
                st.error("Tutor no encontrado")
                return
        except Exception as e:
            st.error(f"Error al cargar tutor: {e}")
            return

    with st.expander("📋 Datos Básicos", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input("Nombre *", value=tutor_data.get("nombre", ""), key="tutor_nombre")
            apellidos = st.text_input("Apellidos *", value=tutor_data.get("apellidos", ""), key="tutor_apellidos")
            email = st.text_input("Email *", value=tutor_data.get("email", ""), key="tutor_email")
            telefono = st.text_input("Teléfono", value=tutor_data.get("telefono", ""), key="tutor_telefono")
        with col2:
            nif = st.text_input("NIF", value=tutor_data.get("nif", ""), key="tutor_nif")
            especialidad = st.text_input("Especialidad", value=tutor_data.get("especialidad", ""), key="tutor_especialidad")
            direccion = st.text_input("Dirección", value=tutor_data.get("direccion", ""), key="tutor_direccion")
            ciudad = st.text_input("Ciudad", value=tutor_data.get("ciudad", ""), key="tutor_ciudad")

    # Botones
    st.divider()
    if es_creacion:
        if st.button("➕ Crear Tutor", type="primary"):
            crear_tutor(supabase, data_service, session_state, nombre, apellidos, email, telefono, nif, especialidad, direccion, ciudad)
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Guardar Cambios", type="primary"):
                actualizar_tutor(supabase, data_service, tutor_id, nombre, apellidos, email, telefono, nif, especialidad, direccion, ciudad)
        with col2:
            if st.button("❌ Cancelar"):
                del st.session_state.tutor_editando
                st.rerun()


def crear_tutor(supabase, data_service, session_state, nombre, apellidos, email, telefono, nif, especialidad, direccion, ciudad):
    """Crear tutor nuevo."""
    try:
        datos = {
            "nombre": nombre,
            "apellidos": apellidos,
            "email": email,
            "telefono": telefono,
            "nif": nif,
            "especialidad": especialidad,
            "direccion": direccion,
            "ciudad": ciudad,
            "empresa_id": session_state.user.get("empresa_id"),
            "created_at": datetime.utcnow().isoformat()
        }
        supabase.table("tutores").insert(datos).execute()
        data_service.get_tutores_completos.clear()
        st.success("Tutor creado correctamente.")
        del st.session_state.tutor_editando
        st.rerun()
    except Exception as e:
        st.error(f"Error al crear tutor: {e}")


def actualizar_tutor(supabase, data_service, tutor_id, nombre, apellidos, email, telefono, nif, especialidad, direccion, ciudad):
    """Actualizar tutor existente."""
    try:
        datos = {
            "nombre": nombre,
            "apellidos": apellidos,
            "email": email,
            "telefono": telefono,
            "nif": nif,
            "especialidad": especialidad,
            "direccion": direccion,
            "ciudad": ciudad,
            "updated_at": datetime.utcnow().isoformat()
        }
        supabase.table("tutores").update(datos).eq("id", tutor_id).execute()
        data_service.get_tutores_completos.clear()
        st.success("Tutor actualizado correctamente.")
        del st.session_state.tutor_editando
        st.rerun()
    except Exception as e:
        st.error(f"Error al actualizar tutor: {e}")


def mostrar_gestion_curriculums(supabase, df_tutores, empresa_id):
    """Gestión independiente de currículums de tutores."""
    st.markdown("### 📂 Gestión de Currículums")

    if df_tutores.empty:
        st.info("No hay tutores disponibles para gestionar currículums.")
        return

    tutor_opciones = {f"{row['nombre']} {row['apellidos']}": row["id"] for _, row in df_tutores.iterrows()}
    tutor_seleccionado = st.selectbox("Seleccionar tutor", list(tutor_opciones.keys()))

    tutor_id = tutor_opciones[tutor_seleccionado]
    tutor_row = df_tutores[df_tutores["id"] == tutor_id].iloc[0]

    if tutor_row.get("cv_url"):
        st.success(f"📄 Currículum ya subido: [Ver archivo]({tutor_row['cv_url']})")

    archivo = st.file_uploader("Subir nuevo currículum", type=["pdf", "doc", "docx"])

    if archivo and st.button("⬆️ Subir/Actualizar CV"):
        try:
            ruta = f"curriculums/{empresa_id}/{tutor_id}/{archivo.name}"
            supabase.storage.from_("curriculums").upload(ruta, archivo.getvalue(), {"upsert": "true"})
            url = supabase.storage.from_("curriculums").get_public_url(ruta)

            supabase.table("tutores").update({"cv_url": url}).eq("id", tutor_id).execute()

            st.success("✅ Currículum subido y asignado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al subir currículum: {e}")
