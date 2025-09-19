# =========================
# IMPORTS
# =========================
import streamlit as st
import pandas as pd
from datetime import datetime
from services.empresas_service import get_empresas_service
from utils import export_csv

# =========================
# MAIN
# =========================
def main(supabase, session_state):
    st.markdown("## 🏢 Empresas")
    st.caption("Gestión de empresas SaaS, gestoras y clientes de gestoras.")
    st.divider()

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    empresas_service = get_empresas_service(supabase, session_state)

    # Vista dividida: Mi empresa / Clientes
    if session_state.role == "gestor":
        tab1, tab2 = st.tabs(["🏠 Mi Empresa", "👥 Empresas Cliente"])
    else:
        tab1, tab2 = st.tabs(["📋 Listado Empresas", "➕ Nueva Empresa"])

    with tab1:
        mostrar_listado_empresas(empresas_service, session_state)

    with tab2:
        if session_state.role == "admin":
            st.subheader("➕ Crear Nueva Empresa")
            mostrar_formulario_empresa_interactivo({}, empresas_service, session_state, es_creacion=True)
        elif session_state.role == "gestor":
            st.subheader("👥 Empresas Cliente")
            mostrar_listado_empresas_clientes(empresas_service, session_state)


# =========================
# LISTADO EMPRESAS
# =========================
def mostrar_listado_empresas(empresas_service, session_state):
    """Muestra listado de empresas (admin ve todas, gestor solo la suya)."""
    try:
        df = empresas_service.get_empresas()
        if df.empty:
            st.info("No hay empresas registradas.")
            return

        # Filtros avanzados
        with st.expander("🔍 Filtros avanzados"):
            nombre_filtro = st.text_input("Buscar por nombre")
            cif_filtro = st.text_input("Buscar por CIF")
            tipo_filtro = st.selectbox("Tipo de empresa", ["", "CLIENTE_SAAS", "GESTORA", "CLIENTE_GESTOR"])

            if nombre_filtro:
                df = df[df["nombre"].str.contains(nombre_filtro, case=False, na=False)]
            if cif_filtro:
                df = df[df["cif"].str.contains(cif_filtro, case=False, na=False)]
            if tipo_filtro:
                df = df[df["tipo_empresa"] == tipo_filtro]

        st.dataframe(df, use_container_width=True, hide_index=True)

        # Exportar
        export_csv(df, "empresas_export.csv")

    except Exception as e:
        st.error(f"❌ Error al cargar empresas: {e}")


def mostrar_listado_empresas_clientes(empresas_service, session_state):
    """Gestor: muestra empresas clientes vinculadas a su empresa."""
    try:
        df = empresas_service.get_empresas_clientes()
        if df.empty:
            st.info("No tienes empresas cliente aún. Crea una nueva desde el formulario.")
            return

        st.dataframe(df, use_container_width=True, hide_index=True)
        export_csv(df, "empresas_clientes_export.csv")

    except Exception as e:
        st.error(f"❌ Error al cargar empresas cliente: {e}")


# =========================
# FORMULARIO EMPRESA
# =========================
def mostrar_formulario_empresa_interactivo(datos, empresas_service, session_state, es_creacion=False):
    """Formulario interactivo para crear/editar empresa."""
    with st.form("form_empresa", clear_on_submit=es_creacion):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre *", value=datos.get("nombre", ""))
            cif = st.text_input("CIF *", value=datos.get("cif", ""))
            telefono = st.text_input("Teléfono", value=datos.get("telefono", ""))
            email = st.text_input("Email", value=datos.get("email", ""))
        with col2:
            direccion = st.text_area("Dirección", value=datos.get("direccion", ""))
            ciudad = st.text_input("Ciudad", value=datos.get("ciudad", ""))
            provincia = st.text_input("Provincia", value=datos.get("provincia", ""))
            cp = st.text_input("Código Postal", value=datos.get("codigo_postal", ""))

        # Información adicional
        with st.expander("📌 Información adicional"):
            representante_nombre = st.text_input("Representante", value=datos.get("representante_nombre", ""))
            representante_dni = st.text_input("DNI Representante", value=datos.get("representante_dni", ""))

        # Configuración de módulos (solo admin)
        if session_state.role == "admin":
            st.markdown("### ⚙️ Configuración de Módulos")
            formacion_activo = st.checkbox("Formación", value=datos.get("formacion_activo", False))
            iso_activo = st.checkbox("ISO 9001", value=datos.get("iso_activo", False))
            rgpd_activo = st.checkbox("RGPD", value=datos.get("rgpd_activo", False))
            crm_activo = st.checkbox("CRM", value=datos.get("crm_activo", False))
            docu_avanzada_activo = st.checkbox("Documentación Avanzada", value=datos.get("docu_avanzada_activo", False))
        else:
            formacion_activo = datos.get("formacion_activo", False)
            iso_activo = datos.get("iso_activo", False)
            rgpd_activo = datos.get("rgpd_activo", False)
            crm_activo = datos.get("crm_activo", False)
            docu_avanzada_activo = datos.get("docu_avanzada_activo", False)

        # Botones
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("💾 Guardar", type="primary")
        with col2:
            cancelar = st.form_submit_button("❌ Cancelar")

        if submitted:
            datos_empresa = {
                "nombre": nombre.strip(),
                "cif": cif.strip(),
                "telefono": telefono.strip(),
                "email": email.strip(),
                "direccion": direccion.strip(),
                "ciudad": ciudad.strip(),
                "provincia": provincia.strip(),
                "codigo_postal": cp.strip(),
                "representante_nombre": representante_nombre.strip(),
                "representante_dni": representante_dni.strip(),
                "formacion_activo": formacion_activo,
                "iso_activo": iso_activo,
                "rgpd_activo": rgpd_activo,
                "crm_activo": crm_activo,
                "docu_avanzada_activo": docu_avanzada_activo,
            }

            try:
                if es_creacion:
                    exito = empresas_service.create_empresa(datos_empresa)
                    if exito:
                        st.success(f"✅ Empresa '{nombre}' creada correctamente")
                        st.session_state.empresa_recien_creada = True
                        st.rerun()
                else:
                    empresa_id = datos.get("id")
                    if empresas_service.update_empresa(empresa_id, datos_empresa):
                        st.success("✅ Empresa actualizada correctamente")
                        st.session_state.empresa_actualizada = True
                        st.rerun()
                    else:
                        st.error("❌ Error al actualizar empresa")
            except Exception as e:
                st.error(f"❌ Error: {e}")

        if cancelar:
            st.info("Edición cancelada")
            st.session_state.empresa_editando = None
            st.rerun()
# =========================
# BLOQUE PARA GESTORES: MI EMPRESA Y CLIENTES
# =========================
def mostrar_mi_empresa(empresas_service, session_state):
    """Muestra la empresa principal del gestor (Mi Empresa)."""
    try:
        empresa = empresas_service.get_mi_empresa()
        if not empresa:
            st.error("❌ No se encontró tu empresa principal")
            return

        st.subheader("🏠 Mi Empresa")
        st.info("Esta es la empresa principal que contrató el SaaS.")

        # Mostrar en dataframe simplificado
        df = pd.DataFrame([empresa])
        st.dataframe(df[["nombre", "cif", "telefono", "email"]], use_container_width=True, hide_index=True)

        # Botón editar
        if st.button("✏️ Editar mi empresa", key="editar_mi_empresa"):
            st.session_state.empresa_editando = empresa
            st.rerun()

        # Si está en edición, mostrar formulario
        if st.session_state.get("empresa_editando") and st.session_state.empresa_editando["id"] == empresa["id"]:
            mostrar_formulario_empresa_interactivo(st.session_state.empresa_editando, empresas_service, session_state, es_creacion=False)

    except Exception as e:
        st.error(f"❌ Error al cargar mi empresa: {e}")


def mostrar_empresas_clientes(empresas_service, session_state):
    """Muestra listado de empresas cliente del gestor con opción de creación y edición."""
    st.subheader("👥 Empresas Cliente")

    try:
        df = empresas_service.get_empresas_clientes()
        if df.empty:
            st.info("No tienes empresas cliente aún. Crea una nueva usando el formulario.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Exportar
            export_csv(df, "empresas_clientes_export.csv")

            # Seleccionar empresa para edición
            seleccion = st.selectbox(
                "Selecciona empresa cliente para editar:",
                options=[""] + list(df["nombre"]),
                key="select_editar_empresa_cliente"
            )
            if seleccion:
                empresa_sel = df[df["nombre"] == seleccion].iloc[0].to_dict()
                mostrar_formulario_empresa_interactivo(empresa_sel, empresas_service, session_state, es_creacion=False)

        # Crear nueva empresa cliente
        with st.expander("➕ Crear Empresa Cliente"):
            mostrar_formulario_empresa_interactivo({}, empresas_service, session_state, es_creacion=True)

    except Exception as e:
        st.error(f"❌ Error al cargar empresas cliente: {e}")
