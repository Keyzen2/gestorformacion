import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import validar_dni_cif, export_csv
from services.empresas_service import get_empresas_service

# Configuración de jerarquía
TIPOS_EMPRESA = {
    "CLIENTE_SAAS": "🏢 Cliente SaaS Directo",
    "GESTORA": "🎯 Gestora de Formación", 
    "CLIENTE_GESTOR": "👥 Cliente de Gestora"
}

def mostrar_metricas_empresas(empresas_service, session_state):
    """Muestra métricas con información jerárquica usando Streamlit 1.49."""
    try:
        metricas = empresas_service.get_estadisticas_empresas()
        
        if session_state.role == "admin":
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
                
            # Distribución jerárquica
            st.markdown("##### Distribución por Tipo")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Clientes SaaS", metricas.get("clientes_saas", 0))
            with col2:
                st.metric("Gestoras", metricas.get("gestoras", 0))
            with col3:
                st.metric("Clientes de Gestoras", metricas.get("clientes_gestoras", 0))
        
        elif session_state.role == "gestor":
            col1, col2, col3, col4 = st.columns(4)
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

def mostrar_tabla_empresas(df_empresas, session_state):
    """Muestra tabla de empresas con funcionalidades modernas de Streamlit 1.49."""
    if df_empresas.empty:
        st.info("📋 No hay empresas para mostrar")
        return None
    
    # Preparar datos para mostrar
    df_display = df_empresas.copy()
    
    # Columnas según rol
    if session_state.role == "admin":
        columnas = ["nombre_display", "cif", "tipo_display", "ciudad", "telefono", "email", "matriz_nombre"]
        column_config = {
            "nombre_display": st.column_config.TextColumn("Razón Social", width="large"),
            "cif": st.column_config.TextColumn("CIF", width="small"),
            "tipo_display": st.column_config.TextColumn("Tipo", width="medium"),
            "ciudad": st.column_config.TextColumn("Ciudad", width="medium"),
            "telefono": st.column_config.TextColumn("Teléfono", width="medium"),
            "email": st.column_config.TextColumn("Email", width="large"),
            "matriz_nombre": st.column_config.TextColumn("Empresa Matriz", width="medium")
        }
    else:
        columnas = ["nombre_display", "cif", "ciudad", "telefono", "email"]
        column_config = {
            "nombre_display": st.column_config.TextColumn("Razón Social", width="large"),
            "cif": st.column_config.TextColumn("CIF", width="small"),
            "ciudad": st.column_config.TextColumn("Ciudad", width="medium"),
            "telefono": st.column_config.TextColumn("Teléfono", width="medium"),
            "email": st.column_config.TextColumn("Email", width="large")
        }
    
    # Tabla con selección
    evento = st.dataframe(
        df_display[columnas],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    # Retornar índice seleccionado
    if evento.selection.rows:
        return df_display.iloc[evento.selection.rows[0]]
    return None

def mostrar_formulario_empresa(empresa_data, empresas_service, session_state, es_creacion=False):
    """Formulario de empresa usando funcionalidades de Streamlit 1.49."""
    
    if es_creacion:
        st.subheader("➕ Crear Nueva Empresa Cliente")
        datos = {}
    else:
        st.subheader(f"✏️ Editar {empresa_data['nombre']}")
        datos = empresa_data.copy()
    
    with st.form("form_empresa", clear_on_submit=es_creacion):
        # Campos básicos en dos columnas
        col1, col2 = st.columns(2)
        
        with col1:
            # Para gestores: nombre readonly en edición, editable en creación
            if session_state.role == "gestor" and not es_creacion:
                st.text_input("Razón Social", value=datos.get("nombre", ""), disabled=True)
                nombre = datos.get("nombre", "")
            else:
                nombre = st.text_input("Razón Social", value=datos.get("nombre", ""))
            
            # CIF readonly para gestores en edición
            if session_state.role == "gestor" and not es_creacion:
                st.text_input("CIF", value=datos.get("cif", ""), disabled=True)
                cif = datos.get("cif", "")
            else:
                cif = st.text_input("CIF", value=datos.get("cif", ""))
                
            direccion = st.text_input("Dirección", value=datos.get("direccion", ""))
            ciudad = st.text_input("Ciudad", value=datos.get("ciudad", ""))
        
        with col2:
            telefono = st.text_input("Teléfono", value=datos.get("telefono", ""))
            email = st.text_input("Email", value=datos.get("email", ""))
            provincia = st.text_input("Provincia", value=datos.get("provincia", ""))
            codigo_postal = st.text_input("Código Postal", value=datos.get("codigo_postal", ""))
        
        # Campos de módulos solo para admin
        if session_state.role == "admin":
            st.markdown("#### 🔧 Configuración de Módulos")
            col3, col4, col5 = st.columns(3)
            
            with col3:
                formacion_activo = st.checkbox("📚 Formación", value=datos.get("formacion_activo", True))
                iso_activo = st.checkbox("📋 ISO 9001", value=datos.get("iso_activo", False))
            
            with col4:
                rgpd_activo = st.checkbox("🛡️ RGPD", value=datos.get("rgpd_activo", False))
                docu_avanzada_activo = st.checkbox("📁 Doc. Avanzada", value=datos.get("docu_avanzada_activo", False))
            
            with col5:
                # Tipo empresa y matriz solo en creación para admin
                if es_creacion:
                    tipo_empresa = st.selectbox("Tipo Empresa", 
                                              options=list(TIPOS_EMPRESA.keys()),
                                              format_func=lambda x: TIPOS_EMPRESA[x])
                    
                    if tipo_empresa == "CLIENTE_GESTOR":
                        gestoras_dict = empresas_service.get_empresas_gestoras_disponibles()
                        if gestoras_dict:
                            empresa_matriz_sel = st.selectbox("Empresa Gestora", 
                                                            options=[""] + list(gestoras_dict.keys()))
                        else:
                            st.warning("No hay empresas gestoras disponibles")
                            empresa_matriz_sel = ""
                    else:
                        empresa_matriz_sel = ""
                else:
                    tipo_empresa = datos.get("tipo_empresa", "CLIENTE_SAAS")
                    empresa_matriz_sel = ""
        else:
            # Valores por defecto para gestores
            formacion_activo = datos.get("formacion_activo", True)
            iso_activo = datos.get("iso_activo", False)
            rgpd_activo = datos.get("rgpd_activo", False)
            docu_avanzada_activo = datos.get("docu_avanzada_activo", False)
            tipo_empresa = "CLIENTE_GESTOR"  # Los gestores solo crean clientes
            empresa_matriz_sel = ""
        
        # Botones de acción
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        
        with col_btn1:
            submitted = st.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
        
        with col_btn2:
            if not es_creacion and session_state.role == "admin":
                eliminar = st.form_submit_button("🗑️ Eliminar", type="secondary", use_container_width=True)
            else:
                eliminar = False
        
        # Procesar formulario
        if submitted:
            # Validaciones básicas
            if not nombre or not cif:
                st.error("⚠️ Razón Social y CIF son obligatorios")
                return False
            
            if not validar_dni_cif(cif):
                st.error("⚠️ El CIF no es válido")
                return False
            
            # Preparar datos
            datos_empresa = {
                "nombre": nombre,
                "cif": cif,
                "direccion": direccion,
                "ciudad": ciudad,
                "telefono": telefono,
                "email": email,
                "provincia": provincia,
                "codigo_postal": codigo_postal,
                "formacion_activo": formacion_activo,
                "iso_activo": iso_activo,
                "rgpd_activo": rgpd_activo,
                "docu_avanzada_activo": docu_avanzada_activo
            }
            
            # Agregar campos específicos según rol y operación
            if session_state.role == "admin" and es_creacion:
                datos_empresa["tipo_empresa"] = tipo_empresa
                if empresa_matriz_sel:
                    gestoras_dict = empresas_service.get_empresas_gestoras_disponibles()
                    datos_empresa["empresa_matriz_id"] = gestoras_dict.get(empresa_matriz_sel)
            
            # DEBUG: Mostrar datos que se van a enviar
            with st.expander("🔍 Debug - Datos a enviar", expanded=False):
                st.json(datos_empresa)
                st.write(f"Es creación: {es_creacion}")
                st.write(f"Rol: {session_state.role}")
                st.write(f"Empresa ID gestor: {session_state.user.get('empresa_id')}")
            
            try:
                if es_creacion:
                    # Crear nueva empresa
                    success, empresa_id = empresas_service.crear_empresa_con_jerarquia(datos_empresa)
                    if success:
                        st.success(f"✅ Empresa cliente creada correctamente (ID: {empresa_id})")
                        # Verificar en BD inmediatamente
                        verificar_creacion_bd(empresas_service, cif)
                        st.rerun()
                    else:
                        st.error("❌ Error al crear la empresa cliente")
                else:
                    # Actualizar empresa existente
                    success = empresas_service.update_empresa_con_jerarquia(datos["id"], datos_empresa)
                    if success:
                        st.success("✅ Empresa actualizada correctamente")
                        st.rerun()
                    else:
                        st.error("❌ Error al actualizar la empresa")
                        
            except Exception as e:
                st.error(f"❌ Error procesando empresa: {e}")
                st.exception(e)  # Mostrar traceback completo para debugging
                return False
        
        # Procesar eliminación
        if eliminar:
            if st.session_state.get("confirmar_eliminar"):
                try:
                    success = empresas_service.delete_empresa_con_jerarquia(datos["id"])
                    if success:
                        st.success("✅ Empresa eliminada correctamente")
                        del st.session_state["confirmar_eliminar"]
                        st.rerun()
                    else:
                        st.error("❌ Error al eliminar la empresa")
                except Exception as e:
                    st.error(f"❌ Error eliminando empresa: {e}")
            else:
                st.session_state["confirmar_eliminar"] = True
                st.warning("⚠️ Presiona 'Eliminar' nuevamente para confirmar")
    
    return False

def verificar_creacion_bd(empresas_service, cif):
    """Función de debugging para verificar si la empresa se creó en BD."""
    try:
        result = empresas_service.supabase.table("empresas").select("*").eq("cif", cif).execute()
        if result.data:
            st.success(f"✅ Verificado: Empresa encontrada en BD")
            with st.expander("🔍 Datos en BD"):
                st.json(result.data[0])
        else:
            st.error("❌ Empresa NO encontrada en BD después de creación")
    except Exception as e:
        st.error(f"Error verificando BD: {e}")

def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas")
    
    # Título específico según rol
    if session_state.role == "admin":
        st.caption("Administración completa de empresas y configuración de módulos")
    else:
        st.caption("Gestión de empresas clientes y configuración básica")

    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("⚠️ No tienes permisos para acceder a esta sección")
        return

    # Inicializar servicio
    empresas_service = get_empresas_service(supabase, session_state)
    
    # Cargar datos con spinner
    with st.spinner("Cargando empresas..."):
        try:
            df_empresas = empresas_service.get_empresas_con_jerarquia()
        except Exception as e:
            st.error(f"❌ Error al cargar empresas: {e}")
            return

    # Métricas
    mostrar_metricas_empresas(empresas_service, session_state)
    
    st.divider()
    
    # Filtros de búsqueda
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, CIF o ciudad", placeholder="Escribe para buscar...")
    
    with col2:
        if session_state.role == "admin":
            tipo_filter = st.selectbox("📂 Filtrar por tipo", 
                                     ["Todos", "CLIENTE_SAAS", "GESTORA", "CLIENTE_GESTOR"])
        else:
            tipo_filter = "Todos"
    
    # Aplicar filtros
    df_filtered = df_empresas.copy()
    
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["cif"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["ciudad"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if tipo_filter != "Todos":
        df_filtered = df_filtered[df_filtered["tipo_empresa"] == tipo_filter]
    
    # Exportar datos
    if not df_filtered.empty:
        st.download_button(
            label="📥 Exportar CSV",
            data=df_filtered.to_csv(index=False),
            file_name=f"empresas_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    st.divider()
    
    # Tabs principales usando Streamlit 1.49
    tab1, tab2 = st.tabs(["📋 Lista de Empresas", "➕ Nueva Empresa"])
    
    with tab1:
        # Mostrar tabla y manejar selección
        empresa_seleccionada = mostrar_tabla_empresas(df_filtered, session_state)
        
        # Si hay una empresa seleccionada, mostrar formulario de edición
        if empresa_seleccionada is not None:
            with st.container(border=True):
                mostrar_formulario_empresa(empresa_seleccionada, empresas_service, session_state, es_creacion=False)
    
    with tab2:
        # Formulario de creación
        if empresas_service.can_modify_data():
            with st.container(border=True):
                mostrar_formulario_empresa({}, empresas_service, session_state, es_creacion=True)
        else:
            st.info("ℹ️ No tienes permisos para crear empresas")
    
    # Vista jerárquica para admin
    if session_state.role == "admin":
        st.divider()
        with st.expander("🌳 Vista Jerárquica", expanded=False):
            try:
                arbol = empresas_service.get_arbol_empresas()
                if not arbol.empty:
                    for _, empresa in arbol.iterrows():
                        nivel = empresa.get("nivel_jerarquico", 1)
                        if nivel == 1:
                            st.markdown(f"🏢 **{empresa['nombre']}** ({empresa.get('tipo_empresa', 'N/A')})")
                        else:
                            st.markdown(f"  └── 🏪 {empresa['nombre']} ({empresa.get('tipo_empresa', 'N/A')})")
                else:
                    st.info("No hay estructura jerárquica para mostrar")
            except Exception as e:
                st.error(f"Error cargando vista jerárquica: {e}")
    
    # Información adicional
    st.divider()
    if session_state.role == "admin":
        with st.expander("ℹ️ Información sobre Jerarquía y Módulos"):
            st.markdown("""
            **Jerarquía Multi-Tenant:**
            - **Cliente SaaS**: Empresas que contratan directamente el SaaS
            - **Gestora**: Clientes SaaS que gestionan otros clientes  
            - **Cliente Gestor**: Empresas gestionadas por una gestora
            
            **Módulos Disponibles:**
            - **Formación**: Gestión de acciones formativas, grupos, participantes
            - **ISO 9001**: Auditorías, informes y seguimiento de calidad
            - **RGPD**: Consentimientos, documentación legal y trazabilidad
            - **Doc. Avanzada**: Gestión documental avanzada y workflows
            """)
    elif session_state.role == "gestor":
        with st.expander("ℹ️ Información para Gestores"):
            st.markdown("""
            **Como gestor puedes:**
            - Crear empresas clientes que aparecerán como "Cliente de Gestora"
            - Editar la configuración básica de tus empresas clientes
            - Los campos sensibles (Razón Social y CIF) solo pueden editarse en creación
            
            **Limitaciones:**
            - No puedes modificar los módulos activos (solo admin)
            - Solo ves tus empresas clientes y tu propia empresa
            """)

if __name__ == "__main__":
    pass
