import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils import validar_dni_cif, export_csv
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

    # Exportar CSV
    if not df_filtered.empty:
        export_csv(df_filtered, filename="empresas.csv")
    
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
            st.error(f"⌛ Error al actualizar empresa: {e}")

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
            st.error(f"⌛ Error al crear empresa: {e}")

    def eliminar_empresa(empresa_id):
        """Función para eliminar una empresa."""
        try:
            success = data_service.delete_empresa(empresa_id)
            if success:
                st.success("✅ Empresa eliminada correctamente.")
                st.rerun()
        except Exception as e:
            st.error(f"⌛ Error al eliminar empresa: {e}")

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

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        if df_empresas.empty:
            st.info("ℹ️ No hay empresas registradas en el sistema.")
            st.markdown("### ➕ Crear primera empresa")
        else:
            st.warning("🔍 No se encontraron empresas que coincidan con los filtros aplicados.")
        
        # Mostrar formulario de creación incluso si no hay datos
        if st.button("➕ Crear nueva empresa", key="btn_crear_empresa"):
            st.session_state["mostrar_formulario_empresa"] = True
    else:
        # Preparar datos para mostrar con columnas correctas
        df_display = data_service.prepare_empresas_display(df_filtered)
        
        # Mostrar tabla interactiva con configuración correcta
        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "id", "nombre", "cif", "ciudad", "provincia", "telefono", "email",
                "formacion_activo", "iso_activo", "rgpd_activo", "crm_activo"
            ],
            titulo="Empresa",
            on_save=guardar_empresa,
            on_create=crear_empresa,
            on_delete=eliminar_empresa,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_obligatorios=campos_obligatorios,
            campos_help=campos_help,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=True,
            allow_deletion=True,
            search_columns=["nombre", "cif", "ciudad", "provincia"]
        )

    # =========================
    # Formulario de creación rápida mejorado
    # =========================
    if st.session_state.get("mostrar_formulario_empresa", False) or df_empresas.empty:
        st.divider()
        st.subheader("➕ Crear nueva empresa")
        
        with st.form("crear_empresa_rapida", clear_on_submit=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🏢 Datos básicos")
                nombre = st.text_input("Nombre *", help="Nombre completo de la empresa")
                cif = st.text_input("CIF *", help="CIF válido de la empresa")
                email = st.text_input("Email", help="Email de contacto")
                telefono = st.text_input("Teléfono", help="Teléfono de contacto")
                
            with col2:
                st.markdown("#### 🌍 Ubicación")
                direccion = st.text_input("Dirección")
                ciudad = st.text_input("Ciudad")
                provincia = st.text_input("Provincia")
                codigo_postal = st.text_input("Código Postal")

            st.markdown("#### 👤 Representante legal")
            col3, col4 = st.columns(2)
            with col3:
                rep_nombre = st.text_input("Nombre representante")
            with col4:
                rep_dni = st.text_input("DNI representante")

            st.markdown("#### 📋 Módulos a activar")
            col5, col6, col7, col8 = st.columns(4)
            
            with col5:
                formacion_activo = st.checkbox("🎓 Formación", value=True)
                if formacion_activo:
                    formacion_inicio = st.date_input("Inicio Formación", value=date.today())
            
            with col6:
                iso_activo = st.checkbox("📋 ISO 9001")
                if iso_activo:
                    iso_inicio = st.date_input("Inicio ISO", value=date.today())
            
            with col7:
                rgpd_activo = st.checkbox("🛡️ RGPD")
                if rgpd_activo:
                    rgpd_inicio = st.date_input("Inicio RGPD", value=date.today())
            
            with col8:
                crm_activo = st.checkbox("📈 CRM")
                if crm_activo:
                    crm_inicio = st.date_input("Inicio CRM", value=date.today())

            # Botones de acción
            col_submit1, col_submit2 = st.columns([1, 3])
            with col_submit1:
                crear_empresa_btn = st.form_submit_button("✅ Crear empresa", use_container_width=True)
            with col_submit2:
                cancelar_btn = st.form_submit_button("❌ Cancelar", use_container_width=True)

        # Manejar acciones del formulario
        if cancelar_btn:
            st.session_state["mostrar_formulario_empresa"] = False
            st.rerun()

        if crear_empresa_btn:
            if not nombre or not cif:
                st.error("⚠️ Nombre y CIF son obligatorios.")
            elif not validar_dni_cif(cif):
                st.error("⚠️ CIF inválido.")
            else:
                # Preparar datos para crear empresa
                empresa_data = {
                    "nombre": nombre,
                    "cif": cif,
                    "direccion": direccion,
                    "telefono": telefono,
                    "email": email,
                    "representante_nombre": rep_nombre,
                    "representante_dni": rep_dni,
                    "ciudad": ciudad,
                    "provincia": provincia,
                    "codigo_postal": codigo_postal,
                    "formacion_activo": formacion_activo,
                    "iso_activo": iso_activo,
                    "rgpd_activo": rgpd_activo,
                    "docu_avanzada_activo": False,  # Por defecto desactivado
                    "crm_activo": crm_activo
                }

                # Añadir fechas de inicio si los módulos están activos
                if formacion_activo:
                    empresa_data["formacion_inicio"] = formacion_inicio.isoformat()
                if iso_activo:
                    empresa_data["iso_inicio"] = iso_inicio.isoformat()
                if rgpd_activo:
                    empresa_data["rgpd_inicio"] = rgpd_inicio.isoformat()
                if crm_activo:
                    empresa_data["crm_inicio"] = crm_inicio.isoformat()

                # Crear empresa usando DataService
                try:
                    success = data_service.create_empresa_completa(empresa_data)
                    if success:
                        st.success("✅ Empresa creada exitosamente.")
                        st.session_state["mostrar_formulario_empresa"] = False
                        st.rerun()
                except Exception as e:
                    st.error(f"⌛ Error al crear la empresa: {e}")

    # =========================
    # Estadísticas adicionales
    # =========================
    if not df_empresas.empty:
        st.divider()
        st.markdown("### 📊 Estadísticas Detalladas")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🏢 Distribución por Provincia")
            if "provincia" in df_empresas.columns:
                provincia_counts = df_empresas["provincia"].value_counts().head(10)
                if not provincia_counts.empty:
                    for prov, count in provincia_counts.items():
                        st.write(f"📍 {prov}: {count} empresas")
                else:
                    st.info("No hay datos de provincia disponibles")
        
        with col2:
            st.markdown("#### 📈 Módulos más Utilizados")
            modulos_stats = data_service.get_modulos_stats(df_empresas)
            for modulo, stats in modulos_stats.items():
                st.write(f"🔧 {modulo}: {stats['activos']} activos ({stats['porcentaje']:.1f}%)")

    st.divider()
    st.caption("💡 Las empresas son la unidad organizativa principal. Cada empresa puede tener múltiples módulos activos.")
