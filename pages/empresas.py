import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import validar_dni_cif, export_csv, format_percentage, get_ajustes_app
from services.empresas_service_jerarquia import get_empresas_service
from components.listado_con_ficha import listado_con_ficha

# Configuración de jerarquía
TIPOS_EMPRESA = {
    "CLIENTE_SAAS": "🏢 Cliente SaaS Directo",
    "GESTORA": "🎯 Gestora de Formación", 
    "CLIENTE_GESTOR": "👥 Cliente de Gestora"
}

ICONOS_JERARQUIA = {
    1: "🏢",  # Empresa raíz
    2: "  └── 🏪"  # Empresa hija
}

def mostrar_metricas_con_jerarquia(empresas_service, session_state):
    """Muestra métricas adaptadas según el rol y con información jerárquica."""
    try:
        metricas = empresas_service.get_estadisticas_empresas()
        
        col1, col2, col3, col4 = st.columns(4)
        
        if session_state.role == "admin":
            # Admin ve métricas globales
            with col1:
                st.metric("🏢 Total Empresas", metricas.get("total_empresas", 0))
            with col2:
                st.metric("📅 Nuevas (30 días)", metricas.get("nuevas_mes", 0))
            with col3:
                st.metric("🎓 Con Formación", metricas.get("con_formacion", 0))
            with col4:
                porcentaje = metricas.get("porcentaje_activas", 0)
                st.metric("📊 % Activas", f"{porcentaje}%")
                
            # Métricas adicionales de jerarquía para admin
            st.markdown("##### Distribución Jerárquica")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Clientes SaaS", metricas.get("clientes_saas", 0))
            with col2:
                st.metric("Gestoras", metricas.get("gestoras", 0))
            with col3:
                st.metric("Clientes de Gestoras", metricas.get("clientes_gestoras", 0))
        
        elif session_state.role == "gestor":
            # Gestor ve métricas de sus clientes
            with col1:
                st.metric("👥 Mis Empresas Clientes", metricas.get("total_clientes", 0))
            with col2:
                st.metric("📅 Nuevos (30 días)", metricas.get("nuevos_clientes_mes", 0))
            with col3:
                st.metric("🎓 Con Formación", metricas.get("clientes_con_formacion", 0))
            with col4:
                st.info(f"Gestora: {metricas.get('empresa_gestora', 'N/A')}")

    except Exception as e:
        st.error(f"Error al cargar métricas: {e}")
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

def aplicar_filtros_empresas(df_empresas, query, tipo_filter):
    """Aplica filtros a las empresas con soporte para jerarquía."""
    df_filtered = df_empresas.copy()

    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[ 
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["cif"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["ciudad"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]

    if tipo_filter != "Todos":
        if tipo_filter in ["CLIENTE_SAAS", "GESTORA", "CLIENTE_GESTOR"]:
            df_filtered = df_filtered[df_filtered["tipo_empresa"] == tipo_filter]

    return df_filtered

def get_campos_dinamicos_jerarquicos(datos, session_state):
    """Define campos visibles incluyendo jerarquía según el contexto."""
    # Campos base para creación/edición
    campos_base = [
        "nombre", "cif", "direccion", "ciudad", "provincia",
        "codigo_postal", "telefono", "email"
    ]

    # Solo admin puede ver/editar módulos
    if session_state.role == "admin":
        campos_base.extend([
            "formacion_activo", "iso_activo", "rgpd_activo",
            "crm_activo", "docu_avanzada_activo"
        ])
        
        # Campos jerárquicos solo para admin en creación
        if not datos or not datos.get("id"):  # Es creación
            campos_base.extend(["tipo_empresa", "empresa_matriz_sel"])

    return campos_base

def get_campos_select_jerarquicos(session_state, empresas_service):
    """Configura campos select incluyendo opciones jerárquicas."""
    campos_select = {}
    
    if session_state.role == "admin":
        campos_select.update({
            "formacion_activo": [True, False],
            "iso_activo": [True, False],
            "rgpd_activo": [True, False],
            "crm_activo": [True, False],
            "docu_avanzada_activo": [True, False]
        })
        
        # Agregar campos jerárquicos
        campos_select.update({
            "tipo_empresa": list(TIPOS_EMPRESA.keys()),
            "empresa_matriz_sel": [""] + list(empresas_service.get_empresas_gestoras_disponibles().keys())
        })

    return campos_select

def get_campos_help_completos():
    """Devuelve campos de ayuda completos incluyendo jerarquía."""
    campos_help = {
        "nombre": "Nombre o razón social de la empresa (obligatorio)",
        "cif": "CIF, NIF o NIE de la empresa (obligatorio)",
        "direccion": "Dirección completa de la empresa",
        "telefono": "Teléfono de contacto principal",
        "email": "Email de contacto principal",
        "ciudad": "Ciudad donde se ubica la empresa",
        "provincia": "Provincia de la empresa",
        "codigo_postal": "Código postal",
        "formacion_activo": "Activa el módulo de gestión de formación",
        "iso_activo": "Activa el módulo de gestión ISO 9001",
        "rgpd_activo": "Activa el módulo de gestión RGPD",
        "crm_activo": "Activa el módulo de gestión comercial (CRM)",
        "docu_avanzada_activo": "Activa el módulo de documentación avanzada",
        "tipo_empresa": "Tipo de empresa en la jerarquía del sistema",
        "empresa_matriz_sel": "Empresa gestora de la que depende (solo para CLIENTE_GESTOR)"
    }
    return campos_help

def crear_empresa_con_jerarquia(datos_nuevos, empresas_service, session_state):
    """Función mejorada para crear empresa con soporte jerárquico."""
    try:
        # Validaciones básicas existentes
        if not datos_nuevos.get("nombre") or not datos_nuevos.get("cif"):
            st.error("Nombre y CIF son obligatorios.")
            return

        if not validar_dni_cif(datos_nuevos["cif"]):
            st.error("El CIF no es válido.")
            return

        # Convertir empresa_matriz_sel a empresa_matriz_id si es admin
        if session_state.role == "admin" and "empresa_matriz_sel" in datos_nuevos:
            matriz_sel = datos_nuevos.pop("empresa_matriz_sel", "")
            gestoras_dict = empresas_service.get_empresas_gestoras_disponibles()
            if matriz_sel and matriz_sel in gestoras_dict:
                datos_nuevos["empresa_matriz_id"] = gestoras_dict[matriz_sel]

        # Usar el servicio con jerarquía
        success, empresa_id = empresas_service.crear_empresa_con_jerarquia(datos_nuevos)
        if success:
            st.success("Empresa creada correctamente.")
            st.rerun()

    except Exception as e:
        st.error(f"Error al crear empresa: {e}")

def guardar_empresa_con_jerarquia(empresa_id, datos_editados, empresas_service, session_state):
    """Función mejorada para guardar empresa respetando jerarquía."""
    try:
        # Validaciones básicas existentes
        if not datos_editados.get("nombre") or not datos_editados.get("cif"):
            st.error("Nombre y CIF son obligatorios.")
            return

        if not validar_dni_cif(datos_editados["cif"]):
            st.error("El CIF no es válido.")
            return

        # Convertir empresa_matriz_sel a empresa_matriz_id si es admin
        if session_state.role == "admin" and "empresa_matriz_sel" in datos_editados:
            matriz_sel = datos_editados.pop("empresa_matriz_sel", "")
            gestoras_dict = empresas_service.get_empresas_gestoras_disponibles()
            if matriz_sel and matriz_sel in gestoras_dict:
                datos_editados["empresa_matriz_id"] = gestoras_dict[matriz_sel]

        # Usar el servicio con jerarquía
        if empresas_service.update_empresa_con_jerarquia(empresa_id, datos_editados):
            st.success("Empresa actualizada correctamente.")
            st.rerun()

    except Exception as e:
        st.error(f"Error al guardar empresa: {e}")

def eliminar_empresa_con_jerarquia(empresa_id, empresas_service, session_state):
    """Función mejorada para eliminar empresa respetando jerarquía."""
    try:
        if empresas_service.delete_empresa_con_jerarquia(empresa_id):
            st.success("Empresa eliminada correctamente.")
            st.rerun()
    except Exception as e:
        st.error(f"Error al eliminar empresa: {e}")

def mostrar_columnas_con_jerarquia(df_empresas, session_state):
    """Determina columnas visibles incluyendo información jerárquica."""
    columnas_base = ["nombre_display", "cif", "ciudad", "telefono", "email"]
    
    if session_state.role == "admin":
        columnas_admin = columnas_base.copy()
        columnas_admin.extend(["tipo_display", "matriz_nombre"])
        return columnas_admin
    else:
        # Gestor ve columnas básicas + tipo si está disponible
        if "tipo_display" in df_empresas.columns:
            columnas_base.append("tipo_display")
        return columnas_base

def mostrar_vista_jerarquica_admin(empresas_service):
    """Muestra vista jerárquica solo para admin si está disponible."""
    try:
        # Intentar obtener vista jerárquica
        arbol = empresas_service.get_arbol_empresas()
        
        with st.expander("Vista Jerárquica de Empresas"):
            if arbol.empty:
                st.info("No hay empresas con jerarquía definida")
                return
            
            for _, empresa in arbol.iterrows():
                nivel = empresa.get("nivel_jerarquico", 1)
                icono = ICONOS_JERARQUIA.get(nivel, "📄")
                
                # Mostrar con indentación visual
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"{icono} **{empresa['nombre']}**")
                    if nivel > 1:
                        st.caption(f"Ruta: {empresa.get('ruta', '')}")
                
                with col2:
                    tipo_badge = TIPOS_EMPRESA.get(empresa.get('tipo_empresa', ''), empresa.get('tipo_empresa', ''))
                    st.caption(tipo_badge)
                
                with col3:
                    st.caption(f"CIF: {empresa.get('cif', 'N/A')}")
    
    except Exception as e:
        st.warning(f"Vista jerárquica no disponible: {e}")

def main(supabase, session_state):
    st.title("Gestión de Empresas")
    
    # Título específico según rol
    if session_state.role == "admin":
        st.caption("Administración de empresas cliente y configuración de módulos.")
    else:
        st.caption("Gestión de tus empresas clientes.")

    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio de empresas con jerarquía
    empresas_service = get_empresas_service(supabase, session_state)
    
    with st.spinner("Cargando datos de empresas..."):
        try:
            df_empresas = empresas_service.get_empresas_con_jerarquia()
        except Exception as e:
            st.error(f"Error al cargar empresas: {e}")
            return

    # =========================
    # MÉTRICAS CON JERARQUÍA
    # =========================
    mostrar_metricas_con_jerarquia(empresas_service, session_state)

    # =========================
    # FILTROS DE BÚSQUEDA
    # =========================
    st.divider()
    st.markdown("### Buscar y Filtrar Empresas")

    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("Buscar por nombre, CIF o ciudad")
    with col2:
        # Filtros según rol
        if session_state.role == "admin":
            tipo_filter = st.selectbox(
                "Filtrar por tipo",
                ["Todos", "CLIENTE_SAAS", "GESTORA", "CLIENTE_GESTOR"]
            )
        else:
            # Gestor solo ve sus tipos relevantes
            tipo_filter = st.selectbox(
                "Filtrar por tipo",
                ["Todos", "CLIENTE_GESTOR"]
            )

    # Aplicar filtros usando función con jerarquía
    df_filtered = aplicar_filtros_empresas(df_empresas, query, tipo_filter)

    # Botón de exportación
    if not df_filtered.empty:
        export_csv(df_filtered, filename="empresas_jerarquia.csv")

    st.divider()

    # =========================
    # VISTA JERÁRQUICA PARA ADMIN
    # =========================
    if session_state.role == "admin":
        mostrar_vista_jerarquica_admin(empresas_service)

    # =========================
    # CONFIGURACIÓN DE CAMPOS MEJORADA
    # =========================
    gestoras_dict = empresas_service.get_empresas_gestoras_disponibles()
    campos_select = get_campos_select_jerarquicos(session_state, empresas_service)
    campos_help = get_campos_help_completos()
    campos_obligatorios = ["nombre", "cif"]
    campos_readonly = ["id", "created_at", "updated_at", "fecha_creacion", "nivel_jerarquico", "empresa_matriz_id"]
    columnas_visibles = mostrar_columnas_con_jerarquia(df_filtered, session_state)

    # =========================
    # FUNCIONES CRUD MEJORADAS
    # =========================
    def guardar_empresa_wrapper(empresa_id, datos_editados):
        # Preparar datos para display si es admin
        if session_state.role == "admin" and "empresa_matriz_sel" not in datos_editados:
            # Convertir empresa_matriz_id a empresa_matriz_sel para display
            if datos_editados.get("empresa_matriz_id") and gestoras_dict:
                for nombre, id_matriz in gestoras_dict.items():
                    if id_matriz == datos_editados["empresa_matriz_id"]:
                        datos_editados["empresa_matriz_sel"] = nombre
                        break
        
        return guardar_empresa_con_jerarquia(empresa_id, datos_editados, empresas_service, session_state)

    def crear_empresa_wrapper(datos_nuevos):
        return crear_empresa_con_jerarquia(datos_nuevos, empresas_service, session_state)

    def eliminar_empresa_wrapper(empresa_id):
        return eliminar_empresa_con_jerarquia(empresa_id, empresas_service, session_state)

    # =========================
    # RENDERIZAR COMPONENTE PRINCIPAL
    # =========================
    if df_filtered.empty and query:
        st.warning(f"No se encontraron empresas que coincidan con '{query}'.")
    elif df_filtered.empty:
        if session_state.role == "gestor":
            st.info("No tienes empresas clientes registradas. Crea tu primera empresa cliente usando el formulario de abajo.")
        else:
            st.info("No hay empresas registradas. Crea la primera empresa usando el formulario de abajo.")
    else:
        # Preparar datos para display con campos de selección
        df_display = df_filtered.copy()
        
        # Convertir empresa_matriz_id a empresa_matriz_sel para display (admin)
        if session_state.role == "admin" and "empresa_matriz_id" in df_display.columns and gestoras_dict:
            df_display["empresa_matriz_sel"] = df_display["empresa_matriz_id"].apply(
                lambda x: next((nombre for nombre, id_val in gestoras_dict.items() if id_val == x), "") if x else ""
            )
        
        # Mensaje informativo según rol
        if session_state.role == "gestor":
            st.info("Como gestor, puedes crear empresas clientes que dependerán de tu empresa.")
        else:
            st.info("Gestiona la jerarquía completa de empresas del sistema.")

        # Usar el componente listado_con_ficha con funciones mejoradas
        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Empresa",
            on_save=guardar_empresa_wrapper,
            on_create=crear_empresa_wrapper if empresas_service.can_modify_data() else None,
            on_delete=eliminar_empresa_wrapper if session_state.role == "admin" else None,
            id_col="id",
            campos_select=campos_select,
            campos_dinamicos=lambda datos: get_campos_dinamicos_jerarquicos(datos, session_state),
            campos_obligatorios=campos_obligatorios,
            allow_creation=empresas_service.can_modify_data(),
            campos_help=campos_help,
            search_columns=["nombre", "cif", "ciudad", "email"],
            campos_readonly=campos_readonly
        )

    # =========================
    # INFORMACIÓN ADICIONAL
    # =========================
    if session_state.role == "admin":
        with st.expander("Información sobre Módulos y Jerarquía"):
            st.markdown("""
            **Módulos disponibles:**
            - **Formación**: Gestión de acciones formativas, grupos, participantes y diplomas
            - **ISO 9001**: Auditorías, informes y seguimiento de calidad
            - **RGPD**: Consentimientos, documentación legal y trazabilidad
            - **CRM**: Gestión de clientes, oportunidades y tareas comerciales
            - **Doc. Avanzada**: Gestión documental avanzada y workflows

            **Jerarquía Multi-Tenant:**
            - **Cliente SaaS**: Empresas que contratan directamente el SaaS
            - **Gestora**: Clientes SaaS que gestionan otros clientes
            - **Cliente Gestor**: Empresas gestionadas por una gestora

            **Nota**: Solo los administradores pueden activar/desactivar módulos y gestionar tipos de empresa.
            """)
    elif session_state.role == "gestor":
        with st.expander("Información para Gestores"):
            st.markdown("""
            **Como gestor puedes:**
            - Crear empresas clientes que dependerán de tu empresa
            - Gestionar grupos de formación para tus clientes
            - Asignar participantes de tus empresas clientes a grupos
            - Generar diplomas organizados por empresa cliente
            
            **Las empresas que crees:**
            - Aparecerán como "Cliente de Gestora" en el sistema
            - Podrán ser asignadas a grupos de formación
            - Sus participantes podrán inscribirse en cursos
            - Se mantendrá la trazabilidad jerárquica completa
            """)

        # Acciones rápidas para gestor
        st.markdown("### Acciones Rápidas")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Limpiar Cache", help="Limpia el cache para actualizar datos"):
                empresas_service.get_empresas_con_jerarquia.clear()
                st.success("Cache limpiada correctamente")
                st.rerun()

        with col2:
            clientes_count = len(df_empresas[df_empresas.get("tipo_empresa", pd.Series([""])) == "CLIENTE_GESTOR"])
            st.metric("Mis Empresas Clientes", clientes_count)
    
    # Footer informativo
    st.divider()
    if session_state.role == "admin":
        st.caption("Gestión de Empresas Multi-Tenant | Control completo del sistema")
    else:
        st.caption("Gestión de Empresas Clientes | Crea y gestiona tus empresas clientes")

if __name__ == "__main__":
    pass
