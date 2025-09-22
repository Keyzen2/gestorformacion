import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional
from utils import (
    validar_dni_cif,
    safe_int_conversion,
    subir_archivo_supabase,
    exportar_dataframe_csv
)
from data_service import DataService


# =========================
# CONFIGURACIÓN DE PÁGINA
# =========================
st.set_page_config(
    page_title="Gestión de Tutores",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================
# FUNCIÓN PRINCIPAL
# =========================
def main(supabase, session_state):
    st.title("👨‍🏫 Gestión de Tutores")

    data_service = DataService(supabase, session_state)

    # =========================
    # MÉTRICAS
    # =========================
    try:
        df_tutores = data_service.get_tutores_completos()
        n_total = len(df_tutores)
        n_con_cv = df_tutores["cv_url"].notna().sum() if "cv_url" in df_tutores.columns else 0

        col1, col2 = st.columns(2)
        with col1:
            st.metric("📊 Total Tutores", n_total)
        with col2:
            st.metric("📄 Tutores con CV", n_con_cv)
    except Exception as e:
        st.error(f"Error cargando métricas: {e}")
        df_tutores = pd.DataFrame()

    # =========================
    # FILTROS
    # =========================
    with st.expander("🔍 Filtros", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            filtro_nombre = st.text_input("Filtrar por nombre/apellidos")
        with col2:
            filtro_empresa = None
            if data_service.rol == "admin":
                empresas = data_service.get_empresas()
                if not empresas.empty:
                    opciones_empresas = ["Todas"] + empresas["nombre"].tolist()
                    seleccion = st.selectbox("Empresa", opciones_empresas)
                    if seleccion != "Todas":
                        filtro_empresa = seleccion

    if not df_tutores.empty:
        if filtro_nombre:
            df_tutores = df_tutores[
                df_tutores["nombre_completo"].str.contains(filtro_nombre, case=False, na=False)
            ]
        if filtro_empresa:
            df_tutores = df_tutores[df_tutores["empresa_nombre"] == filtro_empresa]

    # =========================
    # TABLA DE TUTORES
    # =========================
    st.subheader("📋 Listado de Tutores")

    if not df_tutores.empty:
        df_mostrar = df_tutores[[
            "nombre_completo", "email", "telefono", "nif", "tipo_tutor", "empresa_nombre", "especialidad"
        ]].rename(columns={
            "nombre_completo": "Nombre",
            "email": "Email",
            "telefono": "Teléfono",
            "nif": "DNI",
            "tipo_tutor": "Tipo",
            "empresa_nombre": "Empresa",
            "especialidad": "Especialidad"
        })

        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

        # Selección de fila
        st.markdown("### ✏️ Seleccionar Tutor")
        selected_id = st.selectbox(
            "Seleccione un tutor para editar",
            options=[""] + df_tutores["id"].tolist(),
            format_func=lambda x: df_tutores[df_tutores["id"] == x]["nombre_completo"].values[0]
            if x else "Ninguno"
        )
    else:
        st.info("No hay tutores registrados.")
        selected_id = None

    st.divider()

    # =========================
    # FORMULARIO DE TUTOR
    # =========================
    if selected_id:
        mostrar_formulario_tutor(data_service, tutor_id=selected_id)
    else:
        if st.button("➕ Crear nuevo tutor"):
            mostrar_formulario_tutor(data_service, tutor_id=None)


# =========================
# FORMULARIO
# =========================
def mostrar_formulario_tutor(data_service: DataService, tutor_id: Optional[str] = None):
    if tutor_id:
        df = data_service.get_tutores_completos()
        datos = df[df["id"] == tutor_id].to_dict(orient="records")[0]
        modo = "editar"
    else:
        datos = {}
        modo = "crear"

    with st.form(f"form_tutor_{tutor_id or 'nuevo'}", clear_on_submit=False):
        st.subheader("📝 Datos del Tutor")

        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("👤 Nombre *", value=datos.get("nombre", ""))
            apellidos = st.text_input("👤 Apellidos *", value=datos.get("apellidos", ""))
            dni = st.text_input("🪪 DNI *", value=datos.get("nif", ""))
            if dni and not validar_dni_cif(dni):
                st.error("❌ DNI no válido")
            email = st.text_input("📧 Email *", value=datos.get("email", ""))
            telefono = st.text_input("📞 Teléfono", value=datos.get("telefono", ""))
            tipo_tutor = st.selectbox(
                "🎓 Tipo de Tutor",
                ["Interno", "Externo"],
                index=["Interno", "Externo"].index(datos.get("tipo_tutor", "Interno"))
                if datos.get("tipo_tutor") else 0
            )
        with col2:
            direccion = st.text_input("🏠 Dirección", value=datos.get("direccion", ""))
            ciudad = st.text_input("🏙️ Ciudad", value=datos.get("ciudad", ""))
            provincia = st.text_input("🌍 Provincia", value=datos.get("provincia", ""))
            codigo_postal = st.text_input("📮 Código Postal", value=datos.get("codigo_postal", ""))
            especialidad = st.text_input("💡 Especialidad", value=datos.get("especialidad", ""))

            if data_service.rol == "admin":
                empresas = data_service.get_empresas()
                empresa_nombre = datos.get("empresa_nombre")
                seleccion = st.selectbox(
                    "🏢 Empresa",
                    options=empresas["nombre"].tolist() if not empresas.empty else [],
                    index=empresas["nombre"].tolist().index(empresa_nombre)
                    if empresa_nombre in empresas["nombre"].tolist() else 0
                )
                empresa_id = empresas[empresas["nombre"] == seleccion]["id"].values[0] if not empresas.empty else None
            else:
                empresa_id = data_service.empresa_id
                st.info(f"Empresa asignada automáticamente: {empresa_id}")

        st.divider()

        # =========================
        # BLOQUE DE CV
        # =========================
        st.subheader("📄 Currículum del Tutor")
        cv_url_actual = datos.get("cv_url")

        if cv_url_actual:
            st.markdown(f"📂 CV Actual: [Ver archivo]({cv_url_actual})")
            eliminar_cv = st.checkbox("Eliminar CV actual")
        else:
            eliminar_cv = False

        archivo_cv = st.file_uploader("Subir nuevo CV", type=["pdf", "docx"])

        if archivo_cv:
            nombre_archivo = archivo_cv.name
            carpeta = f"curriculums/empresa_{empresa_id}/tutores/{tutor_id or 'nuevo'}/"
            url_subida = subir_archivo_supabase(archivo_cv, carpeta, nombre_archivo)
            if url_subida:
                st.success("✅ CV subido correctamente")
                cv_url = url_subida
            else:
                cv_url = None
        else:
            cv_url = cv_url_actual if not eliminar_cv else None

        st.divider()

        # =========================
        # BOTONES
        # =========================
        col1, col2, col3 = st.columns(3)
        with col1:
            submitted = st.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
        with col2:
            cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
        with col3:
            eliminar = st.form_submit_button("🗑️ Eliminar", use_container_width=True)

    # =========================
    # PROCESAR FORMULARIO
    # =========================
    if submitted:
        datos_guardar = {
            "nombre": nombre,
            "apellidos": apellidos,
            "nif": dni,
            "email": email,
            "telefono": telefono,
            "tipo_tutor": tipo_tutor,
            "direccion": direccion,
            "ciudad": ciudad,
            "provincia": provincia,
            "codigo_postal": codigo_postal,
            "especialidad": especialidad,
            "empresa_id": empresa_id,
            "cv_url": cv_url
        }
        if modo == "crear":
            ok = data_service.create_tutor(datos_guardar)
            if ok:
                st.success("✅ Tutor creado correctamente")
                st.rerun()
        else:
            ok = data_service.update_tutor(tutor_id, datos_guardar)
            if ok:
                st.success("✅ Tutor actualizado correctamente")
                st.rerun()

    if cancelar:
        st.session_state.grupo_seleccionado = None
        st.rerun()

    if eliminar and tutor_id:
        ok = data_service.delete_tutor(tutor_id)
        if ok:
            st.success("✅ Tutor eliminado correctamente")
            st.rerun()


if __name__ == "__main__":
    st.warning("Ejecuta este módulo desde la aplicación principal.")
# =========================
# SECCIÓN DE EXPORTACIÓN Y PÁGINA DE RESULTADOS
# =========================

def mostrar_tabla_tutores(data_service: DataService, df_tutores: pd.DataFrame):
    """Muestra tabla con tutores y permite exportar resultados."""

    if df_tutores.empty:
        st.warning("⚠️ No hay tutores disponibles.")
        return None

    st.markdown("### 📋 Resultados de la búsqueda")

    # Mostrar tabla resumida
    df_mostrar = df_tutores[[
        "nombre_completo", "email", "telefono", "nif", "tipo_tutor",
        "empresa_nombre", "especialidad", "created_at"
    ]].rename(columns={
        "nombre_completo": "Nombre",
        "email": "Email",
        "telefono": "Teléfono",
        "nif": "DNI",
        "tipo_tutor": "Tipo",
        "empresa_nombre": "Empresa",
        "especialidad": "Especialidad",
        "created_at": "Alta"
    })

    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

    # Exportar CSV
    st.download_button(
        "⬇️ Exportar CSV",
        data=exportar_dataframe_csv(df_mostrar),
        file_name=f"tutores_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True
    )

    # Selección de fila para editar
    selected_id = st.selectbox(
        "Seleccionar tutor para edición",
        options=[""] + df_tutores["id"].tolist(),
        format_func=lambda x: df_tutores[df_tutores["id"] == x]["nombre_completo"].values[0]
        if x else "Ninguno"
    )

    return selected_id


# =========================
# SECCIÓN DE CURRÍCULUMS
# =========================

def mostrar_gestion_cv(data_service: DataService, tutor_id: str, empresa_id: str, cv_url_actual: Optional[str]):
    """Bloque independiente para gestión de CVs de tutores."""

    st.markdown("### 📄 Gestión de Currículum")

    if cv_url_actual:
        st.markdown(f"📂 CV Actual: [Abrir CV]({cv_url_actual})")
        eliminar_cv = st.checkbox("❌ Eliminar CV actual", key=f"del_cv_{tutor_id}")
    else:
        eliminar_cv = False

    archivo_cv = st.file_uploader(
        "📤 Subir nuevo CV",
        type=["pdf", "docx"],
        key=f"upload_cv_{tutor_id}"
    )

    if archivo_cv:
        nombre_archivo = archivo_cv.name
        carpeta = f"curriculums/empresa_{empresa_id}/tutores/{tutor_id}/"
        url_subida = subir_archivo_supabase(archivo_cv, carpeta, nombre_archivo)

        if url_subida:
            st.success("✅ CV subido correctamente")
            return url_subida
        else:
            st.error("❌ Error al subir CV")
            return cv_url_actual
    else:
        return None if eliminar_cv else cv_url_actual


# =========================
# FORMULARIO EXTENDIDO DE TUTOR
# =========================

def formulario_tutor_extendido(
    data_service: DataService,
    datos: Dict[str, Any],
    modo: str,
    tutor_id: Optional[str] = None
):
    """Formulario completo para crear/editar tutores."""

    errores = []
    st.markdown("### 📝 Datos del Tutor")

    c1, c2 = st.columns(2)
    with c1:
        nombre = st.text_input("👤 Nombre *", value=datos.get("nombre", ""), key=f"nombre_{tutor_id}")
        apellidos = st.text_input("👤 Apellidos *", value=datos.get("apellidos", ""), key=f"apellidos_{tutor_id}")
        dni = st.text_input("🪪 DNI *", value=datos.get("nif", ""), key=f"dni_{tutor_id}")
        if dni and not validar_dni_cif(dni):
            errores.append("DNI no válido")

        email = st.text_input("📧 Email *", value=datos.get("email", ""), key=f"email_{tutor_id}")
        telefono = st.text_input("📞 Teléfono", value=datos.get("telefono", ""), key=f"tel_{tutor_id}")
        tipo_tutor = st.selectbox(
            "🎓 Tipo de Tutor",
            ["Interno", "Externo"],
            index=["Interno", "Externo"].index(datos.get("tipo_tutor", "Interno"))
            if datos.get("tipo_tutor") else 0,
            key=f"tipo_{tutor_id}"
        )

    with c2:
        direccion = st.text_input("🏠 Dirección", value=datos.get("direccion", ""), key=f"dir_{tutor_id}")
        ciudad = st.text_input("🏙️ Ciudad", value=datos.get("ciudad", ""), key=f"ciudad_{tutor_id}")
        provincia = st.text_input("🌍 Provincia", value=datos.get("provincia", ""), key=f"prov_{tutor_id}")
        codigo_postal = st.text_input("📮 Código Postal", value=datos.get("codigo_postal", ""), key=f"cp_{tutor_id}")
        especialidad = st.text_input("💡 Especialidad", value=datos.get("especialidad", ""), key=f"esp_{tutor_id}")

        if data_service.rol == "admin":
            empresas = data_service.get_empresas()
            empresa_nombre = datos.get("empresa_nombre")
            seleccion = st.selectbox(
                "🏢 Empresa",
                options=empresas["nombre"].tolist() if not empresas.empty else [],
                index=empresas["nombre"].tolist().index(empresa_nombre)
                if empresa_nombre in empresas["nombre"].tolist() else 0,
                key=f"emp_{tutor_id}"
            )
            empresa_id = empresas[empresas["nombre"] == seleccion]["id"].values[0] if not empresas.empty else None
        else:
            empresa_id = data_service.empresa_id
            st.info(f"Empresa asignada automáticamente: {empresa_id}")

    # Bloque CV
    cv_url = mostrar_gestion_cv(data_service, tutor_id or "nuevo", empresa_id, datos.get("cv_url"))

    datos_guardar = {
        "nombre": nombre,
        "apellidos": apellidos,
        "nif": dni,
        "email": email,
        "telefono": telefono,
        "tipo_tutor": tipo_tutor,
        "direccion": direccion,
        "ciudad": ciudad,
        "provincia": provincia,
        "codigo_postal": codigo_postal,
        "especialidad": especialidad,
        "empresa_id": empresa_id,
        "cv_url": cv_url,
    }

    return datos_guardar, errores
# =========================
# CRUD DE TUTORES
# =========================

def crear_tutor(data_service: DataService, datos_guardar: Dict[str, Any]):
    """Crea un tutor en la BD."""
    ok = data_service.create_tutor(datos_guardar)
    if ok:
        st.success("✅ Tutor creado correctamente")
        st.rerun()
    else:
        st.error("❌ Error al crear tutor")


def actualizar_tutor(data_service: DataService, tutor_id: str, datos_guardar: Dict[str, Any]):
    """Actualiza un tutor existente."""
    ok = data_service.update_tutor(tutor_id, datos_guardar)
    if ok:
        st.success("✅ Tutor actualizado correctamente")
        st.rerun()
    else:
        st.error("❌ Error al actualizar tutor")


def eliminar_tutor(data_service: DataService, tutor_id: str):
    """Elimina un tutor si no está asignado a grupos."""
    ok = data_service.delete_tutor(tutor_id)
    if ok:
        st.success("🗑️ Tutor eliminado correctamente")
        st.rerun()
    else:
        st.error("❌ No se pudo eliminar el tutor")


# =========================
# GESTIÓN INTEGRAL DE TUTORES
# =========================

def gestion_tutores(data_service: DataService):
    """Vista principal de gestión de tutores."""
    st.title("👨‍🏫 Gestión de Tutores")

    # Filtros
    with st.expander("🔎 Filtros de búsqueda", expanded=True):
        colf1, colf2, colf3 = st.columns(3)

        with colf1:
            filtro_nombre = st.text_input("Filtrar por nombre", key="filtro_nombre")
        with colf2:
            filtro_email = st.text_input("Filtrar por email", key="filtro_email")
        with colf3:
            filtro_empresa = st.text_input("Filtrar por empresa", key="filtro_empresa")

    # Cargar tutores
    df_tutores = data_service.get_tutores_completos()

    if not df_tutores.empty:
        if filtro_nombre:
            df_tutores = df_tutores[df_tutores["nombre_completo"].str.contains(filtro_nombre, case=False, na=False)]
        if filtro_email:
            df_tutores = df_tutores[df_tutores["email"].str.contains(filtro_email, case=False, na=False)]
        if filtro_empresa:
            df_tutores = df_tutores[df_tutores["empresa_nombre"].str.contains(filtro_empresa, case=False, na=False)]

    # Mostrar tabla y selección
    tutor_id_seleccionado = mostrar_tabla_tutores(data_service, df_tutores)

    # Botones de acción
    st.markdown("### ➕ Crear Nuevo Tutor")
    if st.button("➕ Nuevo Tutor", use_container_width=True):
        st.session_state.tutor_editando = "nuevo"

    if tutor_id_seleccionado:
        st.session_state.tutor_editando = tutor_id_seleccionado

    tutor_editando = st.session_state.get("tutor_editando", None)

    if tutor_editando:
        if tutor_editando == "nuevo":
            datos_iniciales = {}
            st.markdown("## ➕ Nuevo Tutor")
            datos_guardar, errores = formulario_tutor_extendido(data_service, datos_iniciales, modo="crear")

            colb1, colb2 = st.columns(2)
            with colb1:
                if st.button("💾 Guardar Tutor", use_container_width=True):
                    if not errores:
                        crear_tutor(data_service, datos_guardar)
                    else:
                        st.error("⚠️ " + "; ".join(errores))
            with colb2:
                if st.button("↩️ Cancelar", use_container_width=True):
                    st.session_state.tutor_editando = None
                    st.rerun()

        else:
            tutor_seleccionado = df_tutores[df_tutores["id"] == tutor_editando].iloc[0].to_dict()
            st.markdown(f"## ✏️ Editar Tutor: {tutor_seleccionado.get('nombre_completo')}")

            datos_guardar, errores = formulario_tutor_extendido(data_service, tutor_seleccionado, modo="editar", tutor_id=tutor_editando)

            colb1, colb2, colb3 = st.columns(3)
            with colb1:
                if st.button("💾 Actualizar Tutor", use_container_width=True):
                    if not errores:
                        actualizar_tutor(data_service, tutor_editando, datos_guardar)
                    else:
                        st.error("⚠️ " + "; ".join(errores))
            with colb2:
                if st.button("🗑️ Eliminar Tutor", use_container_width=True):
                    eliminar_tutor(data_service, tutor_editando)
            with colb3:
                if st.button("↩️ Cancelar", use_container_width=True):
                    st.session_state.tutor_editando = None
                    st.rerun()


# =========================
# SECCIÓN DE ASIGNACIÓN DE TUTORES A GRUPOS
# =========================

def asignar_tutores_a_grupo(data_service: DataService, grupo_id: str):
    """Permite asignar tutores a un grupo específico (N:N)."""
    st.markdown("### 👨‍🏫 Asignación de Tutores al Grupo")

    df_tutores = data_service.get_tutores_completos()

    if df_tutores.empty:
        st.warning("⚠️ No hay tutores disponibles para asignar.")
        return

    seleccionados = st.multiselect(
        "Seleccionar tutores",
        options=df_tutores["id"].tolist(),
        format_func=lambda x: df_tutores[df_tutores["id"] == x]["nombre_completo"].values[0]
    )

    if st.button("💾 Guardar Asignaciones", use_container_width=True):
        for tid in seleccionados:
            data_service.supabase.table("tutores_grupos").upsert(
                {"grupo_id": grupo_id, "tutor_id": tid}
            ).execute()
        st.success("✅ Tutores asignados correctamente")
# =========================
# SECCIÓN DE CURRÍCULUM (CV)
# =========================

def gestion_cv_tutor(data_service: DataService, tutor_id: str, cv_url_actual: str = None):
    """Gestión integral de CV de tutores en Supabase bucket."""
    st.markdown("### 📂 Currículum del Tutor")

    if cv_url_actual:
        st.success(f"📄 CV actual: [Ver documento]({cv_url_actual})")
        if st.button("🗑️ Eliminar CV", use_container_width=True, key=f"eliminar_cv_{tutor_id}"):
            try:
                borrar_archivo_supabase(cv_url_actual)
                data_service.update_tutor(tutor_id, {"cv_url": None})
                st.success("✅ CV eliminado correctamente")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al eliminar CV: {e}")

    archivo_cv = st.file_uploader("📤 Subir nuevo CV", type=["pdf", "docx"], key=f"cv_{tutor_id}")
    if archivo_cv is not None:
        try:
            ruta = f"tutores/{data_service.empresa_id}/{tutor_id}/cv/{archivo_cv.name}"
            url_publica = subir_archivo_supabase(archivo_cv, ruta)
            data_service.update_tutor(tutor_id, {"cv_url": url_publica})
            st.success("✅ CV actualizado correctamente")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al subir CV: {e}")


# =========================
# HELPER PARA MOSTRAR TABLA
# =========================

def mostrar_tabla_tutores(data_service: DataService, df_tutores: pd.DataFrame) -> Optional[str]:
    """Muestra la tabla de tutores con selección por fila."""
    if df_tutores.empty:
        st.info("No hay tutores registrados todavía.")
        return None

    # Columnas a mostrar
    columnas = ["nombre_completo", "email", "telefono", "especialidad", "empresa_nombre"]
    df_show = df_tutores[columnas].copy()
    df_show.rename(columns={
        "nombre_completo": "Nombre Completo",
        "email": "Email",
        "telefono": "Teléfono",
        "especialidad": "Especialidad",
        "empresa_nombre": "Empresa"
    }, inplace=True)

    # Mostrar tabla interactiva
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Selector de fila
    tutor_id = st.selectbox(
        "📌 Selecciona un tutor para editar",
        options=[""] + df_tutores["id"].tolist(),
        format_func=lambda x: df_tutores[df_tutores["id"] == x]["nombre_completo"].values[0] if x else "",
        key="selector_tutor"
    )
    return tutor_id if tutor_id else None


# =========================
# MAIN
# =========================

def main(supabase, session_state):
    """Página principal de gestión de tutores."""
    data_service = DataService(supabase, session_state)

    try:
        gestion_tutores(data_service)
    except Exception as e:
        st.error(f"❌ Error en cargar tutores: {e}")
