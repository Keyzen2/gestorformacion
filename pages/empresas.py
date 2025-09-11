import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import validar_dni_cif, export_csv, format_percentage, get_ajustes_app
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha


def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas")
    st.caption("Administración de empresas cliente y configuración de módulos.")

    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)
    with st.spinner("Cargando datos de empresas..."):
        df_empresas = data_service.get_empresas_con_modulos()
        metricas = data_service.get_metricas_empresas()

    # =========================
    # MÉTRICAS PRINCIPALES
    # =========================
    try:
        metricas = data_service.get_metricas_empresas()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏢 Total Empresas", metricas.get("total_empresas", 0))
        with col2:
            st.metric("📅 Nuevas (30 días)", metricas.get("nuevas_mes", 0))
        with col3:
            st.metric("🎓 Con Formación", metricas.get("con_formacion", 0))
        with col4:
            porcentaje = metricas.get("porcentaje_activas", 0)
            st.metric("📊 % Activas", f"{porcentaje}%")

    except Exception as e:
        st.error(f"❌ Error al cargar métricas: {e}")
        # Métricas por defecto en caso de error
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏢 Total Empresas", "0")
        with col2:
            st.metric("📅 Nuevas (30 días)", "0")
        with col3:
            st.metric("🎓 Con Formación", "0")
        with col4:
            st.metric("📊 % Activas", "0%")

    # =========================
    # ESTADÍSTICAS DE MÓDULOS
    # =========================
    if session_state.role == "admin":
        st.divider()
        st.markdown("### 📊 Uso de Módulos por Empresa")

        try:
            # Verificar que tenemos datos de empresas antes de calcular estadísticas
            if not df_empresas.empty:
                stats_modulos = data_service.get_estadisticas_modulos(df_empresas)

                if stats_modulos:
                    cols = st.columns(len(stats_modulos))
                    for i, (modulo, data) in enumerate(stats_modulos.items()):
                        with cols[i]:
                            activos = data.get("activos", 0)
                            porcentaje = data.get("porcentaje", 0)
                            st.metric(
                                f"📋 {modulo}",
                                f"{activos}",
                                delta=f"{porcentaje:.1f}%"
                            )
                else:
                    st.info("No hay estadísticas de módulos disponibles.")
            else:
                st.info("No hay empresas registradas para mostrar estadísticas de módulos.")

        except Exception as e:
            st.warning(f"No se pudieron cargar las estadísticas de módulos: {e}")

    # =========================
    # CARGAR DATOS PRINCIPALES
    # =========================
    try:
        df_empresas = data_service.get_empresas_con_modulos()
    except Exception as e:
        st.error(f"❌ Error al cargar empresas: {e}")
        return

    # =========================
    # FILTROS DE BÚSQUEDA
    # =========================
    st.divider()
    st.markdown("### 🔍 Buscar y Filtrar Empresas")

    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("🔍 Buscar por nombre, CIF o ciudad")
    with col2:
        modulo_filter = st.selectbox(
            "Filtrar por módulo activo",
            ["Todos", "Formación", "ISO 9001", "RGPD", "CRM", "Sin módulos"]
        )

    # Aplicar filtros
    df_filtered = df_empresas.copy()

    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["cif"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["ciudad"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]

    if modulo_filter != "Todos":
        if modulo_filter == "Sin módulos":
            # Empresas sin ningún módulo activo
            modulos = ["formacion_activo", "iso_activo", "rgpd_activo", "crm_activo"]
            mask = pd.Series([True] * len(df_filtered))
            for modulo in modulos:
                if modulo in df_filtered.columns:
                    mask &= (df_filtered[modulo] != True)
            df_filtered = df_filtered[mask]
        else:
            # Filtrar por módulo específico
            modulo_mapping = {
                "Formación": "formacion_activo",
                "ISO 9001": "iso_activo",
                "RGPD": "rgpd_activo",
                "CRM": "crm_activo"
            }
            campo_modulo = modulo_mapping.get(modulo_filter)
            if campo_modulo and campo_modulo in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[campo_modulo] == True]

    # Botón de exportación
    if not df_filtered.empty:
        export_csv(df_filtered, filename="empresas.csv")

    st.divider()

    # =========================
    # DEFINIR CAMPOS PARA FORMULARIOS
    # =========================
    def get_campos_dinamicos(datos):
        """Define campos visibles según el contexto."""
        campos_base = [
            "id", "nombre", "cif", "direccion", "ciudad", "provincia",
            "codigo_postal", "telefono", "email", "web"
        ]

        # Solo admin puede ver/editar módulos
        if session_state.role == "admin":
            campos_base.extend([
                "formacion_activo", "iso_activo", "rgpd_activo",
                "crm_activo", "docu_avanzada_activo"
            ])

        return campos_base

    # Campos para select (solo admin puede modificar módulos)
    campos_select = {}
    if session_state.role == "admin":
        campos_select.update({
            "formacion_activo": [True, False],
            "iso_activo": [True, False],
            "rgpd_activo": [True, False],
            "crm_activo": [True, False],
            "docu_avanzada_activo": [True, False]
        })

    # Campos de ayuda
    campos_help = {
        "nombre": "Nombre o razón social de la empresa",
        "cif": "CIF, NIF o NIE de la empresa (obligatorio)",
        "direccion": "Dirección completa de la empresa",
        "telefono": "Teléfono de contacto principal",
        "email": "Email de contacto principal",
        "web": "Página web (opcional, incluir https://)",
        "formacion_activo": "Activa el módulo de gestión de formación",
        "iso_activo": "Activa el módulo de gestión ISO 9001",
        "rgpd_activo": "Activa el módulo de gestión RGPD",
        "crm_activo": "Activa el módulo de gestión comercial (CRM)"
    }

    # Campos obligatorios
    campos_obligatorios = ["nombre", "cif"]

    # Columnas visibles en la tabla
    columnas_visibles = ["nombre", "cif", "ciudad", "telefono", "email"]
    if session_state.role == "admin":
        columnas_visibles.extend(["formacion_activo", "crm_activo"])

    # =========================
    # FUNCIONES CRUD
    # =========================
    def guardar_empresa(empresa_id, datos_editados):
        """Función para guardar cambios en una empresa."""
        try:
            # Validaciones básicas
            if not datos_editados.get("nombre") or not datos_editados.get("cif"):
                st.error("⚠️ Nombre y CIF son obligatorios.")
                return

            if not validar_dni_cif(datos_editados["cif"]):
                st.error("⚠️ El CIF no es válido.")
                return

            # Usar el servicio de datos para actualizar
            if data_service.update_empresa(empresa_id, datos_editados):
                st.success("✅ Empresa actualizada correctamente.")
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error al guardar empresa: {e}")

    def crear_empresa(datos_nuevos):
        """Función para crear una nueva empresa."""
        try:
            # Usar el servicio de datos para crear
            if data_service.create_empresa(datos_nuevos):
                st.success("✅ Empresa creada correctamente.")
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error al crear empresa: {e}")

    def eliminar_empresa(empresa_id):
        """Función para eliminar una empresa."""
        try:
            if data_service.delete_empresa(empresa_id):
                st.success("✅ Empresa eliminada correctamente.")
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error al eliminar empresa: {e}")

    # =========================
    # RENDERIZAR COMPONENTE PRINCIPAL
    # =========================
    if df_filtered.empty and query:
        st.warning(f"🔍 No se encontraron empresas que coincidan con '{query}'.")
    elif df_filtered.empty:
        st.info("ℹ️ No hay empresas registradas. Crea la primera empresa usando el formulario de abajo.")
    else:
        # Usar el componente listado_con_ficha corregido
        listado_con_ficha(
            df=df_filtered,
            columnas_visibles=columnas_visibles,
            titulo="Empresa",
            on_save=guardar_empresa,
            on_create=crear_empresa if data_service.can_modify_data() else None,
            on_delete=eliminar_empresa if session_state.role == "admin" else None,
            id_col="id",
            campos_select=campos_select,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=data_service.can_modify_data(),
            campos_help=campos_help,
        )

    st.divider()
    st.caption("💡 Las empresas son la unidad organizativa principal. Cada empresa puede tener múltiples módulos activos y usuarios asignados.")

    # =========================
    # INFORMACIÓN ADICIONAL PARA ADMIN
    # =========================
    if session_state.role == "admin":
        with st.expander("ℹ️ Información sobre Módulos"):
            st.markdown("""
            **Módulos disponibles:**
            - **🎓 Formación**: Gestión de acciones formativas, grupos, participantes y diplomas
            - **📋 ISO 9001**: Auditorías, informes y seguimiento de calidad
            - **🔐 RGPD**: Consentimientos, documentación legal y trazabilidad
            - **📈 CRM**: Gestión de clientes, oportunidades y tareas comerciales
            - **📄 Doc. Avanzada**: Gestión documental avanzada y workflows

            **Nota**: Solo los administradores pueden activar/desactivar módulos para las empresas.
            """)

        # Acciones rápidas para admin
        st.markdown("### ⚡ Acciones Rápidas")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🗑️ Limpiar Cache", help="Limpia el cache para actualizar datos"):
                st.cache_data.clear()
                st.success("Cache limpiada correctamente")
                st.rerun()

        with col2:
            if st.button("📊 Recalcular Métricas", help="Fuerza el recálculo de métricas"):
                data_service.get_metricas_empresas.clear()
                st.success("Métricas recalculadas")
                st.rerun()

        with col3:
            empresas_activas = len(df_empresas[df_empresas.get("formacion_activo", pd.Series([False])) == True])
            st.metric("🎯 Empresas con Formación", empresas_activas)
