"""
Módulo para la gestión de empresas.
Integrado con DataService y el componente listado_con_ficha.
"""

import streamlit as st
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas")
    st.caption("Administración de empresas y configuración de módulos activos.")

    # Permisos: solo admin
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    ds = get_data_service(supabase, session_state)

    # =========================
    # Carga de datos y métricas
    # =========================
    with st.spinner("Cargando empresas..."):
        df_empresas = ds.get_empresas_con_modulos()
        metricas = ds.get_metricas_empresas()

    # =========================
    # Métricas rápidas
    # =========================
    if not df_empresas.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏢 Total empresas", metricas.get("total_empresas", 0))
        with col2:
            st.metric("🆕 Nuevas este mes", metricas.get("nuevas_mes", 0))
        with col3:
            st.metric("🌍 Provincia principal", metricas.get("provincia_top", "N/D"))
        with col4:
            st.metric("📊 Módulos activos", metricas.get("modulos_activos", 0))

    st.divider()

    # =========================
    # Filtros
    # =========================
    st.markdown("### 🔍 Buscar y filtrar")
    colf1, colf2 = st.columns(2)
    with colf1:
        query = st.text_input("Buscar por nombre, CIF, email, provincia o ciudad")
    with colf2:
        modulo_filter = st.selectbox(
            "Filtrar por módulo activo",
            ["Todos", "Formación", "ISO 9001", "RGPD", "CRM", "Doc. Avanzada"]
        )

    df_filtered = ds.filter_empresas(df_empresas, query, modulo_filter)

    # =========================
    # CRUD callbacks
    # =========================
    def guardar_empresa(empresa_id, datos_editados):
        try:
            ok = ds.update_empresa(empresa_id, datos_editados)
            if ok:
                st.success("✅ Empresa actualizada correctamente.")
                st.rerun()
            else:
                st.error("⚠️ Revisa los datos. No se pudo actualizar.")
        except Exception as e:
            st.error(f"❌ Error al actualizar: {e}")

    def crear_empresa(datos_nuevos):
        try:
            ok = ds.create_empresa(datos_nuevos)
            if ok:
                st.success("✅ Empresa creada correctamente.")
                st.rerun()
            else:
                st.error("⚠️ Revisa los datos. No se pudo crear.")
        except Exception as e:
            st.error(f"❌ Error al crear: {e}")

    def eliminar_empresa(empresa_id):
        try:
            ok = ds.delete_empresa(empresa_id)
            if ok:
                st.success("✅ Empresa eliminada.")
                st.rerun()
            else:
                st.error("⚠️ No se pudo eliminar. Revisa dependencias (usuarios, grupos).")
        except Exception as e:
            st.error(f"❌ Error al eliminar: {e}")

    # =========================
    # Configuración de formulario
    # =========================
    def get_campos_dinamicos(_fila_o_vacio):
        campos_base = [
            "nombre", "cif", "direccion", "telefono", "email",
            "representante_nombre", "representante_dni",
            "ciudad", "provincia", "codigo_postal"
        ]
        campos_modulos = [
            "formacion_activo", "formacion_inicio", "formacion_fin",
            "iso_activo", "iso_inicio", "iso_fin",
            "rgpd_activo", "rgpd_inicio", "rgpd_fin",
            "docu_avanzada_activo", "docu_avanzada_inicio", "docu_avanzada_fin",
            "crm_activo", "crm_inicio", "crm_fin"
        ]
        # Añade CRM si no existe en DF (por seguridad visual)
        return [c for c in (campos_base + campos_modulos) if c in df_empresas.columns or c in campos_modulos]

    campos_select = {
        "formacion_activo": [True, False],
        "iso_activo": [True, False],
        "rgpd_activo": [True, False],
        "docu_avanzada_activo": [True, False],
        "crm_activo": [True, False]
    }

    campos_readonly = ["id", "fecha_alta", "created_at"]

    campos_help = {
        "nombre": "Nombre completo de la empresa (obligatorio)",
        "cif": "CIF válido (obligatorio y único)",
        "email": "Email de contacto",
        "telefono": "Teléfono de contacto",
        "representante_nombre": "Nombre del representante legal",
        "representante_dni": "DNI del representante legal",
        "formacion_activo": "Activa el módulo de formación",
        "iso_activo": "Activa el módulo ISO 9001",
        "rgpd_activo": "Activa el módulo RGPD",
        "docu_avanzada_activo": "Activa documentación avanzada",
        "crm_activo": "Activa CRM comercial"
    }

    campos_obligatorios = ["nombre", "cif"]

    reactive_fields = {
        "formacion_activo": ["formacion_inicio", "formacion_fin"],
        "iso_activo": ["iso_inicio", "iso_fin"],
        "rgpd_activo": ["rgpd_inicio", "rgpd_fin"],
        "docu_avanzada_activo": ["docu_avanzada_inicio", "docu_avanzada_fin"],
        "crm_activo": ["crm_inicio", "crm_fin"]
    }

    # =========================
    # Interfaz principal
    # =========================
    if df_empresas.empty:
        st.info("ℹ️ No hay empresas registradas.")
    elif df_filtered.empty:
        st.warning("🔍 No hay resultados con los filtros aplicados.")

    columnas_visibles = [c for c in [
        "nombre", "cif", "ciudad", "provincia", "email", "telefono",
        "formacion_activo", "iso_activo", "rgpd_activo", "docu_avanzada_activo"
    ] if c in df_empresas.columns]

    listado_con_ficha(
        df=df_filtered if not df_filtered.empty else df_empresas,
        columnas_visibles=columnas_visibles,
        titulo="Empresa",
        on_save=guardar_empresa,
        on_create=crear_empresa,
        on_delete=eliminar_empresa,
        id_col="id",
        campos_select=campos_select,
        campos_readonly=campos_readonly,
        campos_dinamicos=get_campos_dinamicos,
        campos_help=campos_help,
        campos_obligatorios=campos_obligatorios,
        reactive_fields=reactive_fields,
        search_columns=["nombre", "cif", "ciudad", "provincia", "email", "telefono"]
    )
