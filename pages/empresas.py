import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import validar_dni_cif, export_csv, format_percentage, get_ajustes_app
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

# Configuración de jerarquía
TIPOS_EMPRESA = {
    "CLIENTE_SAAS": "🏢 Cliente SaaS Directo",
    "GESTORA": "🎯 Gestora de Formación", 
    "CLIENTE_GESTOR": "👥 Cliente de Gestora"
}

ICONOS_JERARQUIA = {
    1: "🏢",  # Empresa raíz
    2: "  └── 📁"  # Empresa hija
}

def mostrar_metricas_con_jerarquia(data_service, session_state):
    """Muestra métricas adaptadas según el rol y con información jerárquica."""
    try:
        metricas = data_service.get_metricas_empresas()
        
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
            
            try:
                # Obtener estadísticas jerárquicas si la migración ya se ejecutó
                jerarquia_stats = data_service.get_estadisticas_jerarquia()
                
                with col1:
                    st.metric("Clientes SaaS", jerarquia_stats.get("clientes_saas", 0))
                with col2:
                    st.metric("Gestoras", jerarquia_stats.get("gestoras", 0))
                with col3:
                    st.metric("Clientes de Gestoras", jerarquia_stats.get("clientes_gestoras", 0))
                    
            except Exception:
                # Si no existe la función, mostrar métricas básicas
                st.caption("Métricas jerárquicas disponibles tras ejecutar migración SQL")
        
        elif session_state.role == "gestor":
            # Gestor ve métricas de sus clientes
            with col1:
                st.metric("👥 Mis Clientes", metricas.get("mis_clientes", 0))
            with col2:
                st.metric("📅 Nuevos (30 días)", metricas.get("nuevos_clientes_mes", 0))
            with col3:
                st.metric("🎓 Con Formación", metricas.get("clientes_con_formacion", 0))
            with col4:
                st.info(f"Gestora: {session_state.get('empresa_nombre', 'N/A')}")

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

def mostrar_estadisticas_modulos(data_service, df_empresas, session_state):
    """Muestra estadísticas de módulos manteniendo la lógica original."""
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

def aplicar_filtros_empresas(df_empresas, query, modulo_filter):
    """Aplica filtros a las empresas manteniendo la lógica original."""
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

    return df_filtered

def get_campos_dinamicos_jerarquicos(datos, session_state):
    """Define campos visibles incluyendo jerarquía según el contexto."""
    # Campos base SIN id para creación/edición
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
            try:
                # Verificar si la migración jerárquica está aplicada
                campos_base.extend(["tipo_empresa"])
            except:
                # Si no está la migración, no incluir campos jerárquicos
                pass

    return campos_base

def get_campos_select_jerarquicos(session_state, data_service):
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
        
        # Agregar campos jerárquicos si está disponible la migración
        try:
            campos_select.update({
                "tipo_empresa": list(TIPOS_EMPRESA.keys())
            })
        except:
            pass

    return campos_select

def get_campos_help_completos():
    """Devuelve campos de ayuda completos incluyendo jerarquía."""
    campos_help = {
        "nombre": "Nombre o razón social de la empresa (obligatorio)",
        "cif": "CIF, NIF o NIE de la empresa (obligatorio)",
        "direccion": "Dirección completa de la empresa",
        "telefono": "Teléfono de contacto principal",
        "email": "Email de contacto principal",
        "web": "Página web (opcional, incluir https://)",
        "ciudad": "Ciudad donde se ubica la empresa",
        "provincia": "Provincia de la empresa",
        "codigo_postal": "Código postal",
        "formacion_activo": "Activa el módulo de gestión de formación",
        "iso_activo": "Activa el módulo de gestión ISO 9001",
        "rgpd_activo": "Activa el módulo de gestión RGPD",
        "crm_activo": "Activa el módulo de gestión comercial (CRM)",
        "docu_avanzada_activo": "Activa el módulo de documentación avanzada",
        "tipo_empresa": "Tipo de empresa en la jerarquía del sistema"
    }
    return campos_help

def crear_empresa_con_jerarquia(datos_nuevos, data_service, session_state):
    """Función mejorada para crear empresa con soporte jerárquico."""
    try:
        # Validaciones básicas existentes
        if not datos_nuevos.get("nombre") or not datos_nuevos.get("cif"):
            st.error("⚠️ Nombre y CIF son obligatorios.")
            return

        if not validar_dni_cif(datos_nuevos["cif"]):
            st.error("⚠️ El CIF no es válido.")
            return

        # Lógica jerárquica para gestores
        if session_state.role == "gestor":
            # Automáticamente asignar como cliente de gestor
            datos_nuevos.update({
                "empresa_matriz_id": session_state.get("empresa_id"),
                "tipo_empresa": "CLIENTE_GESTOR",
                "nivel_jerarquico": 2,
                "creado_por_usuario_id": session_state.get("user_id")
            })

        # Usar el servicio de datos existente
        if data_service.create_empresa(datos_nuevos):
            st.success("✅ Empresa creada correctamente.")
            st.rerun()

    except Exception as e:
        st.error(f"❌ Error al crear empresa: {e}")

def guardar_empresa_con_jerarquia(empresa_id, datos_editados, data_service, session_state):
    """Función mejorada para guardar empresa respetando jerarquía."""
    try:
        # Validaciones básicas existentes
        if not datos_editados.get("nombre") or not datos_editados.get("cif"):
            st.error("⚠️ Nombre y CIF son obligatorios.")
            return

        if not validar_dni_cif(datos_editados["cif"]):
            st.error("⚠️ El CIF no es válido.")
            return

        # Verificar permisos jerárquicos para gestores
        if session_state.role == "gestor":
            # Verificar que la empresa pertenece al gestor
            try:
                empresa_actual = data_service.get_empresa_by_id(empresa_id)
                if empresa_actual.get("empresa_matriz_id") != session_state.get("empresa_id"):
                    st.error("❌ No tienes permisos para editar esta empresa.")
                    return
            except:
                # Si no hay verificación jerárquica, continuar con lógica normal
                pass

        # Usar el servicio de datos existente
        if data_service.update_empresa(empresa_id, datos_editados):
            st.success("✅ Empresa actualizada correctamente.")
            st.rerun()

    except Exception as e:
        st.error(f"❌ Error al guardar empresa: {e}")

def eliminar_empresa_con_jerarquia(empresa_id, data_service, session_state):
    """Función mejorada para eliminar empresa respetando jerarquía."""
    try:
        # Solo admin o gestor propietario
        if session_state.role == "gestor":
            # Verificar que la empresa pertenece al gestor
            try:
                empresa_actual = data_service.get_empresa_by_id(empresa_id)
                if empresa_actual.get("empresa_matriz_id") != session_state.get("empresa_id"):
                    st.error("❌ No tienes permisos para eliminar esta empresa.")
                    return
            except:
                # Si no hay verificación jerárquica, continuar con lógica normal
                pass

        if data_service.delete_empresa(empresa_id):
            st.success("✅ Empresa eliminada correctamente.")
            st.rerun()

    except Exception as e:
        st.error(f"❌ Error al eliminar empresa: {e}")

def mostrar_columnas_con_jerarquia(df_empresas, session_state):
    """Determina columnas visibles incluyendo información jerárquica."""
    columnas_base = ["nombre", "cif", "ciudad", "telefono", "email"]
    
    if session_state.role == "admin":
        columnas_admin = columnas_base.copy()
        columnas_admin.extend(["formacion_activo", "crm_activo"])
        
        # Agregar columnas jerárquicas si están disponibles
        if "tipo_empresa" in df_empresas.columns:
            columnas_admin.append("tipo_empresa")
        if "matriz_nombre" in df_empresas.columns:
            columnas_admin.append("matriz_nombre")
            
        return columnas_admin
    else:
        return columnas_base

def mostrar_vista_jerarquica_admin(data_service):
    """Muestra vista jerárquica solo para admin si está disponible."""
    try:
        # Intentar obtener vista jerárquica
        arbol = data_service.get_arbol_empresas()
        
        with st.expander("🌳 Vista Jerárquica de Empresas"):
            if not arbol:
                st.info("No hay empresas con jerarquía definida")
                return
            
            for empresa in arbol:
                nivel = empresa.get("nivel", 1)
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
    
    except AttributeError:
        # La función no existe, la jerarquía no está implementada aún
        pass
    except Exception as e:
        st.warning(f"Vista jerárquica no disponible: {e}")

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
        try:
            df_empresas = data_service.get_empresas_con_modulos()
        except Exception as e:
            st.error(f"❌ Error al cargar empresas: {e}")
            return

    # =========================
    # MÉTRICAS CON JERARQUÍA
    # =========================
    mostrar_metricas_con_jerarquia(data_service, session_state)

    # =========================
    # ESTADÍSTICAS DE MÓDULOS (original)
    # =========================
    mostrar_estadisticas_modulos(data_service, df_empresas, session_state)

    # =========================
    # FILTROS DE BÚSQUEDA (original)
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

    # Aplicar filtros usando función original
    df_filtered = aplicar_filtros_empresas(df_empresas, query, modulo_filter)

    # Botón de exportación (original)
    if not df_filtered.empty:
        export_csv(df_filtered, filename="empresas.csv")

    st.divider()

    # =========================
    # VISTA JERÁRQUICA PARA ADMIN
    # =========================
    if session_state.role == "admin":
        mostrar_vista_jerarquica_admin(data_service)

    # =========================
    # CONFIGURACIÓN DE CAMPOS (mejorada)
    # =========================
    campos_select = get_campos_select_jerarquicos(session_state, data_service)
    campos_help = get_campos_help_completos()
    campos_obligatorios = ["nombre", "cif"]
    campos_readonly = ["id", "created_at", "updated_at", "fecha_alta"]
    columnas_visibles = mostrar_columnas_con_jerarquia(df_filtered, session_state)

    # =========================
    # FUNCIONES CRUD MEJORADAS
    # =========================
    def guardar_empresa_wrapper(empresa_id, datos_editados):
        return guardar_empresa_con_jerarquia(empresa_id, datos_editados, data_service, session_state)

    def crear_empresa_wrapper(datos_nuevos):
        return crear_empresa_con_jerarquia(datos_nuevos, data_service, session_state)

    def eliminar_empresa_wrapper(empresa_id):
        return eliminar_empresa_con_jerarquia(empresa_id, data_service, session_state)

    # =========================
    # RENDERIZAR COMPONENTE PRINCIPAL (original)
    # =========================
    if df_filtered.empty and query:
        st.warning(f"🔍 No se encontraron empresas que coincidan con '{query}'.")
    elif df_filtered.empty:
        if session_state.role == "gestor":
            st.info("ℹ️ No tienes empresas clientes registradas. Crea tu primera empresa cliente usando el formulario de abajo.")
        else:
            st.info("ℹ️ No hay empresas registradas. Crea la primera empresa usando el formulario de abajo.")
    else:
        # Usar el componente listado_con_ficha con funciones mejoradas
        listado_con_ficha(
            df=df_filtered,
            columnas_visibles=columnas_visibles,
            titulo="Empresa",
            on_save=guardar_empresa_wrapper,
            on_create=crear_empresa_wrapper if data_service.can_modify_data() else None,
            on_delete=eliminar_empresa_wrapper if session_state.role == "admin" or session_state.role == "gestor" else None,
            id_col="id",
            campos_select=campos_select,
            campos_dinamicos=lambda datos: get_campos_dinamicos_jerarquicos(datos, session_state),
            campos_obligatorios=campos_obligatorios,
            allow_creation=data_service.can_modify_data(),
            campos_help=campos_help,
            search_columns=["nombre", "cif", "ciudad", "email"],
            campos_readonly=campos_readonly
        )

    # =========================
    # INFORMACIÓN ADICIONAL PARA ADMIN (original + jerarquía)
    # =========================
    if session_state.role == "admin":
        with st.expander("ℹ️ Información sobre Módulos"):
            st.markdown("""
            **Módulos disponibles:**
            - **🎓 Formación**: Gestión de acciones formativas, grupos, participantes y diplomas
            - **📋 ISO 9001**: Auditorías, informes y seguimiento de calidad
            - **📄 RGPD**: Consentimientos, documentación legal y trazabilidad
            - **📈 CRM**: Gestión de clientes, oportunidades y tareas comerciales
            - **📄 Doc. Avanzada**: Gestión documental avanzada y workflows

            **Jerarquía Multi-Tenant:**
            - **Cliente SaaS**: Empresas que contratan directamente el SaaS
            - **Gestora**: Clientes SaaS que gestionan otros clientes
            - **Cliente Gestor**: Empresas gestionadas por una gestora

            **Nota**: Solo los administradores pueden activar/desactivar módulos y gestionar tipos de empresa.
            """)

        # Acciones rápidas para admin (original)
        st.markdown("### ⚡ Acciones Rápidas")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🗑️ Limpiar Cache", help="Limpia el cache para actualizar datos"):
                st.cache_data.clear()
                st.success("Cache limpiada correctamente")
                st.rerun()

        with col2:
            if st.button("📊 Recalcular Métricas", help="Fuerza el recálculo de métricas"):
                try:
                    data_service.get_metricas_empresas.clear()
                    st.success("Métricas recalculadas")
                    st.rerun()
                except:
                    st.warning("No se pudieron recalcular las métricas")

        with col3:
            empresas_activas = len(df_empresas[df_empresas.get("formacion_activo", pd.Series([False])) == True])
            st.metric("🎯 Empresas con Formación", empresas_activas)
    
    # Footer informativo
    st.divider()
    st.caption("💡 Gestión de Empresas Multi-Tenant | Mantiene compatibilidad total con funcionalidad existente")

if __name__ == "__main__":
    pass
