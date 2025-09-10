"""
Módulo para la gestión de empresas.
Versión mejorada con integración completa de DataService y listado_con_ficha.
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils import validar_dni_cif, export_csv, export_excel, formato_fecha, mostrar_notificacion
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas")
    st.caption("Administración de empresas y configuración de módulos activos.")

    # Verificar permisos
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)

    # =========================
    # Cargar datos con DataService
    # =========================
    with st.spinner("Cargando datos de empresas..."):
        df_empresas = data_service.get_empresas_con_modulos()
        metricas = data_service.get_metricas_empresas()

    # =========================
    # Métricas mejoradas
    # =========================
    if not df_empresas.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🏢 Total Empresas", metricas.get("total_empresas", 0))
        
        with col2:
            st.metric("🆕 Nuevas este mes", metricas.get("nuevas_mes", 0))
        
        with col3:
            st.metric("🌍 Provincia principal", metricas.get("provincia_top", "N/D"))
        
        with col4:
            st.metric("📊 Módulos activos", metricas.get("modulos_activos", 0))

    st.divider()

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, CIF, email, provincia o ciudad")
    with col2:
        modulo_filter = st.selectbox(
            "Filtrar por módulo activo", 
            ["Todos", "Formación", "ISO 9001", "RGPD", "CRM", "Doc. Avanzada"]
        )

    # Aplicar filtros
    df_filtered = data_service.filter_empresas(df_empresas, query, modulo_filter)

    # Exportar datos
    if not df_filtered.empty:
        col1, col2 = st.columns(2)
        with col1:
            export_csv(df_filtered, filename="empresas.csv")
        with col2:
            export_excel(df_filtered, filename="empresas.xlsx")
    
    st.divider()

    # =========================
    # Funciones CRUD optimizadas
    # =========================
    def guardar_empresa(empresa_id, datos_editados):
        """Función para guardar cambios en una empresa."""
        try:
            # Usar DataService para validar y guardar
            success = data_service.update_empresa(empresa_id, datos_editados)
            if success:
                st.success("✅ Empresa actualizada correctamente.")
                st.rerun()
            else:
                st.error("⚠️ Error en validación de datos.")
        except Exception as e:
            st.error(f"⚠️ Error al actualizar empresa: {e}")

    def crear_empresa(datos_nuevos):
        """Función para crear una nueva empresa."""
        try:
            # Usar DataService para validar y crear
            success = data_service.create_empresa(datos_nuevos)
            if success:
                st.success("✅ Empresa creada correctamente.")
                st.rerun()
            else:
                st.error("⚠️ Error en validación de datos.")
        except Exception as e:
            st.error(f"⚠️ Error al crear empresa: {e}")

    def eliminar_empresa(empresa_id):
        """Función para eliminar una empresa."""
        try:
            success = data_service.delete_empresa(empresa_id)
            if success:
                st.success("✅ Empresa eliminada correctamente.")
                st.rerun()
            else:
                st.error("⚠️ No se pudo eliminar la empresa. Verifique que no tenga datos relacionados.")
        except Exception as e:
            st.error(f"⚠️ Error al eliminar empresa: {e}")

    # =========================
    # Configuración de campos para listado_con_ficha
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
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
        
        return campos_base + campos_modulos

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
        "cif": "CIF válido de la empresa (obligatorio)",
        "email": "Email de contacto principal",
        "telefono": "Teléfono de contacto",
        "formacion_activo": "Activar módulo de gestión de formación",
        "iso_activo": "Activar módulo de gestión ISO 9001",
        "rgpd_activo": "Activar módulo de gestión RGPD",
        "crm_activo": "Activar módulo de CRM comercial",
        "docu_avanzada_activo": "Activar módulo de documentación avanzada",
        "representante_nombre": "Nombre del representante legal",
        "representante_dni": "DNI del representante legal"
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
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        if df_empresas.empty:
            st.info("ℹ️ No hay empresas registradas en el sistema.")
            st.markdown("### ➕ Crear primera empresa")
        else:
            st.warning("🔍 No se encontraron empresas que coincidan con los filtros aplicados.")
    
    # Mostrar el listado con ficha
    listado_con_ficha(
        df=df_filtered,
        columnas_visibles=["nombre", "cif", "ciudad", "provincia", "email", "telefono", "formacion_activo", "iso_activo", "rgpd_activo"],
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
        search_columns=["nombre", "cif", "ciudad", "provincia"]
    )
