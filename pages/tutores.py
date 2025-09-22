import streamlit as st
import pandas as pd
from datetime import datetime
from services.grupos_service import GruposService
from utils import validar_dni_cif, safe_int_conversion
import uuid

# =========================
# CARGA INICIAL Y CONFIG
# =========================

def main(supabase, session_state):
    """Página principal para la gestión de tutores."""
    st.markdown("## 👨‍🏫 Gestión de Tutores")

    grupos_service = GruposService(supabase, session_state)

    # Control de edición (similar a grupos.py)
    if "tutor_editando" not in st.session_state:
        st.session_state.tutor_editando = None  # None = listado, "nuevo" = creación, id = edición

    # Vista principal
    if st.session_state.tutor_editando is None:
        mostrar_listado_tutores(grupos_service)
    elif st.session_state.tutor_editando == "nuevo":
        mostrar_formulario_tutor(grupos_service, es_creacion=True)
    else:
        tutor_id = st.session_state.tutor_editando
        tutor = grupos_service.get_tutor_por_id(tutor_id)
        if tutor:
            mostrar_formulario_tutor(grupos_service, tutor, es_creacion=False)
        else:
            st.error("❌ No se encontró el tutor seleccionado")
            st.session_state.tutor_editando = None
# =========================
# LISTADO DE TUTORES
# =========================

def mostrar_listado_tutores(grupos_service: GruposService):
    """Muestra el listado de tutores en tabla editable."""

    st.markdown("### 📋 Listado de Tutores")

    try:
        df = grupos_service.get_tutores()
    except Exception as e:
        st.error(f"❌ Error en cargar tutores: {e}")
        return

    if df.empty:
        st.info("ℹ️ No hay tutores registrados todavía.")
    else:
        # Mostrar tabla en formato Streamlit 1.49
        st.dataframe(
            df[["nombre", "apellidos", "dni", "email", "telefono", "empresa_nombre"]],
            hide_index=True,
            use_container_width=True
        )

        # Acción: seleccionar tutor
        tutor_ids = df["id"].tolist()
        selected = st.selectbox(
            "✏️ Seleccione un tutor para editar",
            options=[""] + tutor_ids,
            format_func=lambda x: "Seleccione..." if x == "" else f"Tutor {x}",
            key="tutor_select"
        )

        if selected:
            st.session_state.tutor_editando = selected
            st.rerun()

    # Botones de acción
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        if st.button("➕ Nuevo Tutor", type="primary", use_container_width=True):
            st.session_state.tutor_editando = "nuevo"
            st.rerun()

    with col2:
        if not df.empty:
            if st.button("🗑️ Eliminar Tutor Seleccionado", use_container_width=True):
                if selected:
                    exito = grupos_service.delete_tutor(selected)
                    if exito:
                        st.success("✅ Tutor eliminado correctamente")
                        st.session_state.tutor_editando = None
                        st.rerun()
                    else:
                        st.error("❌ No se pudo eliminar el tutor")
# =========================
# FORMULARIO DE CREACIÓN/EDICIÓN DE TUTOR
# =========================

def mostrar_formulario_tutor(grupos_service: GruposService, tutor_id: Optional[str] = None):
    """Formulario para crear o editar un tutor."""

    es_creacion = tutor_id == "nuevo" or tutor_id is None
    datos_tutor = {}

    if not es_creacion:
        try:
            datos_tutor = grupos_service.get_tutor_by_id(tutor_id)
        except Exception as e:
            st.error(f"❌ Error al cargar tutor: {e}")
            return

    # Título
    if es_creacion:
        st.markdown("### ➕ Crear Nuevo Tutor")
    else:
        nombre = datos_tutor.get("nombre", "")
        apellidos = datos_tutor.get("apellidos", "")
        st.markdown(f"### ✏️ Editar Tutor: {nombre} {apellidos}")

    # Formulario
    with st.form(f"form_tutor_{tutor_id or 'nuevo'}", clear_on_submit=es_creacion):
        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input(
                "👤 Nombre *",
                value=datos_tutor.get("nombre", "")
            )
            apellidos = st.text_input(
                "👤 Apellidos *",
                value=datos_tutor.get("apellidos", "")
            )
            dni = st.text_input(
                "🪪 DNI *",
                value=datos_tutor.get("dni", "")
            )
            email = st.text_input(
                "📧 Email *",
                value=datos_tutor.get("email", "")
            )

        with col2:
            telefono = st.text_input(
                "📞 Teléfono",
                value=datos_tutor.get("telefono", "")
            )
            especialidad = st.text_input(
                "🎓 Especialidad",
                value=datos_tutor.get("especialidad", "")
            )
            experiencia = st.text_area(
                "💼 Experiencia",
                value=datos_tutor.get("experiencia", ""),
                height=80
            )

            # Subida de currículum (PDF u otro formato)
            st.markdown("📄 **Currículum del Tutor**")
            archivo_cv = st.file_uploader(
                "Subir archivo",
                type=["pdf", "docx"],
                key=f"cv_{tutor_id or 'nuevo'}"
            )

        # Validaciones mínimas
        errores = []
        if not nombre:
            errores.append("Nombre requerido")
        if not apellidos:
            errores.append("Apellidos requeridos")
        if not dni:
            errores.append("DNI requerido")
        if not email:
            errores.append("Email requerido")

        # Botones
        st.divider()
        col1, col2 = st.columns([2, 1])

        with col1:
            submitted = st.form_submit_button(
                "💾 Guardar Tutor",
                type="primary",
                use_container_width=True,
                disabled=len(errores) > 0
            )
        with col2:
            cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

        # Procesar
        if submitted and not errores:
            datos_guardar = {
                "nombre": nombre,
                "apellidos": apellidos,
                "dni": dni,
                "email": email,
                "telefono": telefono,
                "especialidad": especialidad,
                "experiencia": experiencia,
                "empresa_id": grupos_service.empresa_id
            }

            # Subir currículum si se seleccionó
            if archivo_cv:
                try:
                    import uuid
                    extension = archivo_cv.name.split(".")[-1]
                    cv_path = f"tutores/{grupos_service.empresa_id}/{uuid.uuid4()}.{extension}"

                    res = grupos_service.supabase.storage.from_("documentos").upload(
                        cv_path,
                        archivo_cv,
                        {"content-type": archivo_cv.type}
                    )

                    if res.get("error"):
                        st.error(f"❌ Error al subir CV: {res['error']['message']}")
                    else:
                        datos_guardar["curriculum_url"] = cv_path
                        st.success("📄 Currículum subido correctamente")

                except Exception as e:
                    st.error(f"❌ Error en subida de CV: {e}")

            # Guardar tutor
            try:
                if es_creacion:
                    exito = grupos_service.create_tutor(datos_guardar)
                    if exito:
                        st.success("✅ Tutor creado correctamente")
                        st.session_state.tutor_editando = None
                        st.rerun()
                else:
                    exito = grupos_service.update_tutor(tutor_id, datos_guardar)
                    if exito:
                        st.success("✅ Tutor actualizado correctamente")
                        st.session_state.tutor_editando = None
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar tutor: {e}")

        elif cancelar:
            st.session_state.tutor_editando = None
            st.rerun()

        # Mostrar CV actual si ya existe
        if not es_creacion and datos_tutor.get("curriculum_url"):
            url_cv = datos_tutor["curriculum_url"]
            st.markdown(f"📎 [Ver CV Actual]({url_cv})")
# =========================
# ASIGNACIÓN DE TUTORES A GRUPOS (N:N)
# =========================

def gestionar_asignacion_tutores(grupos_service: GruposService, tutor_id: str):
    """Permite asignar un tutor a uno o varios grupos (N:N)."""

    st.markdown("### 👥 Asignar Tutor a Grupos")

    try:
        # Cargar datos
        grupos = grupos_service.get_grupos_completos()
        asignaciones = grupos_service.get_asignaciones_tutor(tutor_id)

        grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos}
        asignados_ids = [a["grupo_id"] for a in asignaciones]

        # Selector múltiple
        seleccionados = st.multiselect(
            "Seleccionar grupos",
            options=list(grupos_dict.keys()),
            default=[codigo for codigo, gid in grupos_dict.items() if gid in asignados_ids],
            help="Seleccione los grupos donde impartirá este tutor"
        )

        # Botón guardar
        if st.button("💾 Guardar Asignaciones", type="primary", use_container_width=True):
            try:
                nuevos_ids = [grupos_dict[c] for c in seleccionados]
                exito = grupos_service.update_asignaciones_tutor(tutor_id, nuevos_ids)

                if exito:
                    st.success("✅ Asignaciones actualizadas correctamente")
                    st.rerun()
                else:
                    st.error("❌ Error al actualizar asignaciones")
            except Exception as e:
                st.error(f"❌ Error al guardar asignaciones: {e}")

    except Exception as e:
        st.error(f"❌ Error al cargar asignaciones: {e}")
# =========================
# VISTA PRINCIPAL DE TUTORES
# =========================

def mostrar_listado_tutores(grupos_service: GruposService):
    """Muestra tabla de tutores con opciones de edición y asignación."""

    st.markdown("### 📋 Listado de Tutores")

    try:
        tutores = grupos_service.get_tutores_completos()

        if tutores.empty:
            st.info("ℹ️ No hay tutores registrados todavía")
        else:
            # Tabla con selección de filas
            st.dataframe(
                tutores[["nombre", "apellidos", "dni", "email", "telefono", "empresa_nombre"]],
                use_container_width=True,
                hide_index=True
            )

            # Selección de fila
            selected_row = st.selectbox(
                "Selecciona un tutor para editar o gestionar asignaciones:",
                options=[""] + tutores["nombre"].astype(str).tolist(),
                index=0
            )

            if selected_row:
                tutor = tutores[tutores["nombre"] == selected_row].iloc[0].to_dict()

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("✏️ Editar", use_container_width=True):
                        st.session_state.tutor_editando = tutor["id"]
                        st.rerun()

                with col2:
                    if st.button("📂 Asignar a Grupos", use_container_width=True):
                        gestionar_asignacion_tutores(grupos_service, tutor["id"])

                with col3:
                    if st.button("🗑️ Eliminar", use_container_width=True):
                        if grupos_service.delete_tutor(tutor["id"]):
                            st.success("✅ Tutor eliminado correctamente")
                            st.rerun()
                        else:
                            st.error("❌ No se pudo eliminar el tutor")

    except Exception as e:
        st.error(f"❌ Error al cargar tutores: {e}")

    st.divider()

    # Botón para crear nuevo tutor
    if st.button("➕ Crear Nuevo Tutor", type="primary", use_container_width=True):
        st.session_state.tutor_editando = "nuevo"
        st.rerun()
# =========================
# GESTIÓN DE CURRÍCULUM TUTOR
# =========================

def gestionar_curriculum_tutor(grupos_service: GruposService, tutor: Dict[str, Any]):
    """Subida y gestión del currículum del tutor en Supabase Storage."""

    st.markdown("### 📂 Currículum del Tutor")

    bucket_name = "tutores"
    empresa_id = tutor.get("empresa_id")
    tutor_id = tutor.get("id")

    if not empresa_id or not tutor_id:
        st.warning("⚠️ No se puede gestionar currículum sin empresa o tutor asociado")
        return

    # Path en el bucket: empresa_id/tutor_id/cv_nombre.pdf
    carpeta_tutor = f"{empresa_id}/{tutor_id}/"

    # Mostrar CV existente si hay URL guardada
    cv_url = tutor.get("cv_url")
    if cv_url:
        st.success("✅ Currículum ya disponible")
        st.markdown(f"[📄 Ver CV actual]({cv_url})", unsafe_allow_html=True)

        if st.button("🗑️ Eliminar CV", use_container_width=True):
            try:
                # Obtener nombre del archivo desde la URL
                nombre_archivo = cv_url.split("/")[-1]
                ruta_storage = f"{carpeta_tutor}{nombre_archivo}"

                grupos_service.supabase.storage.from_(bucket_name).remove([ruta_storage])

                # Actualizar tutor en BD
                grupos_service.update_tutor(tutor_id, {"cv_url": None})

                st.success("✅ Currículum eliminado correctamente")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al eliminar CV: {e}")
    else:
        st.info("ℹ️ No hay currículum cargado")

    st.divider()

    # Subir nuevo archivo
    archivo_cv = st.file_uploader(
        "📤 Subir nuevo Currículum (PDF/DOCX)",
        type=["pdf", "docx"],
        key=f"cv_upload_{tutor_id}"
    )

    if archivo_cv is not None:
        try:
            nombre_archivo = archivo_cv.name
            ruta_storage = f"{carpeta_tutor}{nombre_archivo}"

            # Guardar en Supabase Storage
            grupos_service.supabase.storage.from_(bucket_name).upload(
                ruta_storage, archivo_cv, {"upsert": True}
            )

            # Obtener URL pública
            public_url = grupos_service.supabase.storage.from_(bucket_name).get_public_url(ruta_storage)

            # Actualizar BD
            grupos_service.update_tutor(tutor_id, {"cv_url": public_url})

            st.success("✅ Currículum subido correctamente")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al subir CV: {e}")
