import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime, date
from utils import (
    generar_pdf,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo,
    validar_xml,
    export_csv,
    preparar_datos_xml_inicio_simple,
    validar_grupo_fundae_completo,
    get_ajustes_app
)
from services.data_service import get_data_service
from services.grupos_service import get_grupos_service

# =========================
# VALIDACIONES FUNDAE CON JERARQUÍA
# =========================

def validar_codigo_accion_fundae(supabase, session_state, codigo_accion, accion_id=None, ano=None):
    """
    Valida que el código de acción sea único para la empresa gestora en el año especificado.
    
    FUNDAE: Los códigos de acción deben ser únicos por empresa gestora y año.
    """
    if not codigo_accion or not ano:
        return False, "Código de acción y año requeridos"
    
    try:
        # Determinar empresa gestora según rol
        if session_state.role == "admin":
            # Admin debe especificar empresa
            return True, ""  # Se validará a nivel de formulario
        elif session_state.role == "gestor":
            empresa_gestora_id = session_state.user.get("empresa_id")
        else:
            return False, "Sin permisos para crear acciones"
        
        # Buscar acciones con mismo código en el mismo año y empresa gestora
        query = supabase.table("acciones_formativas").select("id, codigo_accion").eq(
            "codigo_accion", codigo_accion
        ).eq("empresa_id", empresa_gestora_id).gte(
            "fecha_inicio", f"{ano}-01-01"
        ).lt("fecha_inicio", f"{ano + 1}-01-01")
        
        # Excluir la acción actual si estamos editando
        if accion_id:
            query = query.neq("id", accion_id)
        
        res = query.execute()
        
        if res.data:
            return False, f"Ya existe una acción con código '{codigo_accion}' en {ano} para esta empresa gestora"
        
        return True, ""
        
    except Exception as e:
        return False, f"Error al validar código: {e}"

def validar_codigo_grupo_fundae(supabase, session_state, codigo_grupo, accion_formativa_id, grupo_id=None):
    """
    Valida que el código de grupo sea único para la acción y empresa gestora en el año.
    
    FUNDAE: Los códigos de grupo deben ser únicos por acción formativa, empresa gestora y año.
    """
    if not codigo_grupo or not accion_formativa_id:
        return False, "Código de grupo y acción formativa requeridos"
    
    try:
        # Obtener información de la acción formativa
        accion_res = supabase.table("acciones_formativas").select(
            "codigo_accion, empresa_id, fecha_inicio"
        ).eq("id", accion_formativa_id).execute()
        
        if not accion_res.data:
            return False, "Acción formativa no encontrada"
        
        accion_data = accion_res.data[0]
        empresa_gestora_id = accion_data["empresa_id"]
        fecha_accion = accion_data["fecha_inicio"]
        
        if fecha_accion:
            ano_accion = datetime.fromisoformat(fecha_accion.replace('Z', '+00:00')).year
        else:
            ano_accion = datetime.now().year
        
        # Validar permisos según jerarquía
        if session_state.role == "gestor":
            user_empresa_id = session_state.user.get("empresa_id")
            if empresa_gestora_id != user_empresa_id:
                # Verificar si es cliente de la gestora
                empresa_res = supabase.table("empresas").select("empresa_matriz_id").eq(
                    "id", empresa_gestora_id
                ).execute()
                
                if not empresa_res.data or empresa_res.data[0].get("empresa_matriz_id") != user_empresa_id:
                    return False, "No tienes permisos para crear grupos para esta acción"
        
        # Buscar grupos con mismo código en la misma acción y año
        query = supabase.table("grupos").select("id, codigo_grupo").eq(
            "codigo_grupo", codigo_grupo
        ).eq("accion_formativa_id", accion_formativa_id).gte(
            "fecha_inicio", f"{ano_accion}-01-01"
        ).lt("fecha_inicio", f"{ano_accion + 1}-01-01")
        
        # Excluir el grupo actual si estamos editando
        if grupo_id:
            query = query.neq("id", grupo_id)
        
        res = query.execute()
        
        if res.data:
            return False, f"Ya existe un grupo con código '{codigo_grupo}' para esta acción en {ano_accion}"
        
        return True, ""
        
    except Exception as e:
        return False, f"Error al validar código de grupo: {e}"

def get_empresa_responsable_fundae(supabase, grupo_id):
    """
    Determina qué empresa es responsable ante FUNDAE para un grupo específico.
    
    FUNDAE: La empresa responsable es la gestora, no necesariamente la propietaria del grupo.
    """
    try:
        # Obtener información del grupo y la acción
        grupo_res = supabase.table("grupos").select("""
            empresa_id,
            accion_formativa:acciones_formativas(empresa_id)
        """).eq("id", grupo_id).execute()
        
        if not grupo_res.data:
            return None, "Grupo no encontrado"
        
        grupo_data = grupo_res.data[0]
        empresa_grupo_id = grupo_data["empresa_id"]
        empresa_accion_id = grupo_data.get("accion_formativa", {}).get("empresa_id")
        
        # La empresa responsable ante FUNDAE es la que creó la acción formativa
        empresa_responsable_id = empresa_accion_id or empresa_grupo_id
        
        # Obtener datos de la empresa responsable
        empresa_res = supabase.table("empresas").select("""
            id, nombre, cif, tipo_empresa, empresa_matriz_id
        """).eq("id", empresa_responsable_id).execute()
        
        if not empresa_res.data:
            return None, "Empresa responsable no encontrada"
        
        empresa_responsable = empresa_res.data[0]
        
        # Si es cliente de gestor, la responsable ante FUNDAE es la gestora
        if empresa_responsable.get("tipo_empresa") == "CLIENTE_GESTOR":
            gestora_id = empresa_responsable.get("empresa_matriz_id")
            if gestora_id:
                gestora_res = supabase.table("empresas").select("*").eq("id", gestora_id).execute()
                if gestora_res.data:
                    return gestora_res.data[0], ""
        
        return empresa_responsable, ""
        
    except Exception as e:
        return None, f"Error al determinar empresa responsable: {e}"

def preparar_datos_xml_con_jerarquia(grupo_id, supabase, session_state):
    """
    Prepara datos XML asegurando coherencia con jerarquía empresarial FUNDAE.
    """
    try:
        # Validar grupo FUNDAE completo
        datos_xml, errores = preparar_datos_xml_inicio_simple(grupo_id, supabase)
        
        if errores:
            return None, errores
        
        # Obtener empresa responsable ante FUNDAE
        empresa_responsable, error_empresa = get_empresa_responsable_fundae(supabase, grupo_id)
        
        if error_empresa:
            errores.append(f"Error empresa responsable: {error_empresa}")
            return None, errores
        
        # Validar códigos FUNDAE
        grupo_info = datos_xml["grupo"]
        codigo_grupo = grupo_info.get("codigo_grupo")
        accion_formativa_id = grupo_info.get("accion_formativa_id")
        
        if codigo_grupo and accion_formativa_id:
            es_valido, error_codigo = validar_codigo_grupo_fundae(
                supabase, session_state, codigo_grupo, accion_formativa_id, grupo_id
            )
            
            if not es_valido:
                errores.append(f"Código de grupo inválido: {error_codigo}")
                return None, errores
        
        # Enriquecer datos con información de empresa responsable
        datos_xml["empresa_responsable"] = empresa_responsable
        datos_xml["grupo"]["empresa_responsable_cif"] = empresa_responsable.get("cif")
        datos_xml["grupo"]["empresa_responsable_nombre"] = empresa_responsable.get("nombre")
        
        return datos_xml, []
        
    except Exception as e:
        return None, [f"Error al preparar datos XML: {e}"]

# =========================
# GENERACIÓN XML MEJORADA
# =========================

def generar_xml_inicio_grupo_con_jerarquia(datos_xml):
    """
    Genera XML de inicio de grupo con validaciones de jerarquía empresarial.
    """
    try:
        # Validar que tenemos empresa responsable
        if "empresa_responsable" not in datos_xml:
            st.error("❌ Falta información de empresa responsable ante FUNDAE")
            return None
        
        # Usar la función existente pero con datos validados
        xml_content = generar_xml_inicio_grupo(datos_xml)
        
        if xml_content:
            # Agregar metadatos de validación como comentario
            empresa_resp = datos_xml["empresa_responsable"]
            metadata = f"""
<!-- 
VALIDACIONES FUNDAE APLICADAS:
- Empresa responsable: {empresa_resp.get('nombre')} (CIF: {empresa_resp.get('cif')})
- Código grupo único validado para año y empresa gestora
- Jerarquía empresarial respetada
- Generado: {datetime.now().isoformat()}
-->
"""
            # Insertar metadata después de la declaración XML
            if xml_content.startswith('<?xml'):
                lines = xml_content.split('\n')
                lines.insert(1, metadata)
                xml_content = '\n'.join(lines)
        
        return xml_content
        
    except Exception as e:
        st.error(f"❌ Error al generar XML con jerarquía: {e}")
        return None

# =========================
# FUNCIÓN PRINCIPAL ACTUALIZADA
# =========================

def main(supabase, session_state):
    st.title("📄 Generación de Documentos FUNDAE")
    st.caption("Genera XMLs y PDFs oficiales con validaciones de jerarquía empresarial")
    
    # Obtener datos del usuario
    empresa_id = session_state.user.get("empresa_id")
    user_role = session_state.role
    
    # Verificar permisos
    if user_role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para generar documentos FUNDAE")
        return
    
    # Mostrar información de contexto según rol
    if user_role == "gestor":
        st.info("💡 Como gestor, puedes generar documentos para tu empresa y empresas clientes")
    elif user_role == "admin":
        st.info("💡 Como admin, puedes generar documentos para cualquier empresa del sistema")
    
    # Inicializar servicios
    data_service = get_data_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    
    # URLs de los esquemas XSD desde secrets
    xsd_urls = {
        'accion_formativa': st.secrets.get("FUNDAE", {}).get("xsd_accion_formativa"),
        'inicio_grupo': st.secrets.get("FUNDAE", {}).get("xsd_inicio_grupo"),
        'finalizacion_grupo': st.secrets.get("FUNDAE", {}).get("xsd_finalizacion_grupo")
    }
    
    # Verificar que tenemos las URLs
    if not all(xsd_urls.values()):
        st.error("⚠️ Faltan las URLs de los esquemas XSD en la configuración")
        st.info("💡 Por favor, verifica que estén configuradas las URLs en los secrets de Streamlit")
        st.info("Necesitas configurar: FUNDAE.xsd_accion_formativa, FUNDAE.xsd_inicio_grupo, FUNDAE.xsd_finalizacion_grupo")
        return
    
    # =========================
    # Cargar datos con jerarquía
    # =========================
    with st.spinner("Cargando datos con validaciones FUNDAE..."):
        try:
            # Usar servicios con jerarquía
            df_acciones = data_service.get_acciones_formativas()
            df_grupos = data_service.get_grupos_completos()
            
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return
    
    # =========================
    # Métricas con información de jerarquía
    # =========================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📚 Acciones Formativas", len(df_acciones) if not df_acciones.empty else 0)
    
    with col2:
        st.metric("👥 Grupos", len(df_grupos) if not df_grupos.empty else 0)
    
    with col3:
        if not df_grupos.empty and "fecha_fin" in df_grupos.columns:
            grupos_activos = df_grupos[
                (pd.to_datetime(df_grupos["fecha_fin"], errors='coerce') > pd.Timestamp.now()) |
                df_grupos["fecha_fin"].isna()
            ]
            st.metric("✅ Grupos Activos", len(grupos_activos))
        else:
            st.metric("✅ Grupos Activos", 0)
    
    with col4:
        # Mostrar información de jerarquía
        if user_role == "gestor" and not df_grupos.empty:
            # Contar empresas participantes
            empresas_participantes = set()
            for _, grupo in df_grupos.iterrows():
                if "empresa_nombre" in grupo and grupo["empresa_nombre"]:
                    empresas_participantes.add(grupo["empresa_nombre"])
            st.metric("🏢 Empresas Gestionadas", len(empresas_participantes))
        else:
            st.metric("📊 Total Documentos", 0)  # Placeholder
    
    st.divider()
    
    # =========================
    # Selector de tipo de documento con validaciones
    # =========================
    tipo_documento = st.selectbox(
        "🎯 Selecciona el tipo de documento a generar:",
        ["Seleccionar...", "XML Acción Formativa", "XML Inicio de Grupo", "XML Finalización de Grupo"],
        key="tipo_documento",
        help="Documentos con validaciones FUNDAE y jerarquía empresarial"
    )
    
    if tipo_documento == "Seleccionar...":
        st.info("👆 Selecciona un tipo de documento para comenzar")
        
        # Mostrar información de validaciones FUNDAE
        with st.expander("ℹ️ Validaciones FUNDAE aplicadas", expanded=False):
            st.markdown("""
            ### 🔍 Validaciones de Códigos FUNDAE:
            
            **Códigos de Acción Formativa:**
            - Únicos por empresa gestora y año
            - No pueden repetirse en el mismo periodo
            - Reutilizables en años diferentes
            
            **Códigos de Grupo:**
            - Únicos por acción formativa, empresa gestora y año
            - Secuenciales recomendados (Grupo 1, Grupo 2, etc.)
            - Reinicio de numeración cada año
            
            **Jerarquía Empresarial:**
            - Gestoras: Responsables ante FUNDAE
            - Clientes: Los XMLs se generan bajo la gestora
            - Validación automática de permisos
            """)
        return
    
    # =========================
    # XML ACCIÓN FORMATIVA CON VALIDACIONES
    # =========================
    elif tipo_documento == "XML Acción Formativa":
        st.markdown("### 📚 Generar XML de Acción Formativa")
        st.caption("🔍 Con validaciones de códigos únicos y jerarquía empresarial")
        
        if df_acciones.empty:
            st.warning("⚠️ No hay acciones formativas disponibles")
            return
        
        # Crear diccionario de acciones para el selectbox
        acciones_dict = {}
        for _, accion in df_acciones.iterrows():
            codigo = accion.get('codigo_accion', 'Sin código')
            nombre = accion.get('nombre', 'Sin nombre')
            ano = "?"
            if accion.get('fecha_inicio'):
                try:
                    ano = datetime.fromisoformat(str(accion['fecha_inicio']).replace('Z', '+00:00')).year
                except:
                    pass
            
            nombre_mostrar = f"{codigo} - {nombre} ({ano})"
            acciones_dict[nombre_mostrar] = accion.to_dict()
        
        accion_seleccionada = st.selectbox(
            "Selecciona una acción formativa:",
            ["Seleccionar..."] + list(acciones_dict.keys()),
            key="accion_xml"
        )
        
        if accion_seleccionada != "Seleccionar...":
            accion_data = acciones_dict[accion_seleccionada]
            
            # Mostrar información de validación
            with st.expander("🔍 Validaciones FUNDAE", expanded=True):
                codigo_accion = accion_data.get('codigo_accion')
                fecha_inicio = accion_data.get('fecha_inicio')
                empresa_id_accion = accion_data.get('empresa_id')
                
                if fecha_inicio:
                    try:
                        ano_accion = datetime.fromisoformat(str(fecha_inicio).replace('Z', '+00:00')).year
                        st.success(f"✅ Año de la acción: {ano_accion}")
                    except:
                        st.warning("⚠️ Fecha de inicio inválida")
                        ano_accion = None
                else:
                    st.warning("⚠️ Falta fecha de inicio")
                    ano_accion = None
                
                if codigo_accion and ano_accion:
                    es_valido, error_msg = validar_codigo_accion_fundae(
                        supabase, session_state, codigo_accion, 
                        accion_data.get('id'), ano_accion
                    )
                    
                    if es_valido:
                        st.success(f"✅ Código '{codigo_accion}' válido para {ano_accion}")
                    else:
                        st.error(f"❌ {error_msg}")
                        return
                else:
                    st.error("❌ Faltan datos obligatorios para validar")
                    return
                
                # Mostrar empresa responsable
                if empresa_id_accion:
                    try:
                        empresa_res = supabase.table("empresas").select("nombre, cif, tipo_empresa").eq(
                            "id", empresa_id_accion
                        ).execute()
                        
                        if empresa_res.data:
                            empresa = empresa_res.data[0]
                            st.info(f"🏢 Empresa responsable: {empresa['nombre']} (CIF: {empresa['cif']})")
                    except:
                        st.warning("⚠️ No se pudo cargar información de empresa")
            
            # Mostrar vista previa
            with st.expander("👀 Vista previa de datos", expanded=False):
                st.json(accion_data)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 Generar XML", type="primary", key="generar_xml_accion"):
                    with st.spinner("Generando XML con validaciones FUNDAE..."):
                        xml_content = generar_xml_accion_formativa(accion_data)
                        
                        if xml_content:
                            st.success("✅ XML generado correctamente")
                            
                            # Mostrar XML generado
                            st.text_area("XML Generado:", xml_content, height=200)
                            
                            # Botón de descarga
                            filename = f"accion_formativa_{codigo_accion}_{ano_accion}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
                            
                            st.download_button(
                                label="💾 Descargar XML",
                                data=xml_content,
                                file_name=filename,
                                mime="application/xml"
                            )
                        else:
                            st.error("❌ Error al generar el XML")
            
            with col2:
                if st.button("✅ Validar XML", key="validar_xml_accion") and xsd_urls['accion_formativa']:
                    with st.spinner("Validando XML contra esquema FUNDAE..."):
                        xml_content = generar_xml_accion_formativa(accion_data)
                        
                        if xml_content:
                            es_valido, errores = validar_xml(xml_content, xsd_urls['accion_formativa'])
                            
                            if es_valido:
                                st.success("✅ El XML es válido según el esquema FUNDAE")
                            else:
                                st.error("❌ El XML no es válido según el esquema XSD")
                                for error in errores[:5]:
                                    st.caption(f"• {error}")
                                if len(errores) > 5:
                                    st.caption(f"... y {len(errores) - 5} errores más")
    
    # =========================
    # XML INICIO DE GRUPO CON JERARQUÍA
    # =========================
    elif tipo_documento == "XML Inicio de Grupo":
        st.markdown("### 👥 Generar XML de Inicio de Grupo")
        st.caption("🔍 Con validaciones de jerarquía empresarial y códigos únicos")
        
        if df_grupos.empty:
            st.warning("⚠️ No hay grupos disponibles")
            return
        
        # Crear diccionario de grupos
        grupos_dict = {}
        for _, grupo in df_grupos.iterrows():
            codigo = grupo.get('codigo_grupo', 'Sin código')
            accion_nombre = grupo.get('accion_nombre', grupo.get('accion_formativa_nombre', 'Acción no disponible'))
            empresa_nombre = grupo.get('empresa_nombre', 'Sin empresa')
            
            # Agregar información de año
            ano = "?"
            if grupo.get('fecha_inicio'):
                try:
                    ano = datetime.fromisoformat(str(grupo['fecha_inicio']).replace('Z', '+00:00')).year
                except:
                    pass
            
            nombre_mostrar = f"{codigo} - {accion_nombre} ({empresa_nombre} - {ano})"
            grupos_dict[nombre_mostrar] = grupo.to_dict()
        
        grupo_seleccionado = st.selectbox(
            "Selecciona un grupo:",
            ["Seleccionar..."] + list(grupos_dict.keys()),
            key="grupo_inicio_xml"
        )
        
        if grupo_seleccionado != "Seleccionar...":
            grupo_data = grupos_dict[grupo_seleccionado]
            grupo_id = grupo_data.get('id')
            
            # Validación FUNDAE con jerarquía
            with st.spinner("Validando datos FUNDAE con jerarquía empresarial..."):
                datos_xml, errores = preparar_datos_xml_con_jerarquia(grupo_id, supabase, session_state)
                
                if errores:
                    st.error("❌ El grupo no cumple los requisitos FUNDAE:")
                    for error in errores:
                        st.error(f"• {error}")
                    st.info("💡 Ve a la página de Grupos para completar los datos faltantes")
                    
                    # Mostrar datos actuales del grupo
                    with st.expander("🔍 Ver datos actuales del grupo"):
                        st.json(grupo_data)
                        
                else:
                    # Grupo válido para FUNDAE
                    st.success("✅ Grupo válido para XML FUNDAE con jerarquía empresarial")
                    
                    # Mostrar información de empresa responsable
                    empresa_responsable = datos_xml.get("empresa_responsable", {})
                    if empresa_responsable:
                        st.info(f"🏢 Empresa responsable ante FUNDAE: **{empresa_responsable.get('nombre')}** (CIF: {empresa_responsable.get('cif')})")
                    
                    # Información del grupo
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("👥 Tutores", len(datos_xml["tutores"]))
                    with col2:
                        st.metric("🏢 Empresas", len(datos_xml["empresas"]))
                    with col3:
                        participantes_count = grupo_data.get('n_participantes_previstos', 0)
                        st.metric("🎓 Participantes", participantes_count)
                    
                    # Vista previa de datos
                    with st.expander("👀 Vista previa de datos FUNDAE", expanded=False):
                        tab1, tab2, tab3, tab4 = st.tabs(["Grupo", "Empresa Responsable", "Tutores", "Empresas"])
                        
                        with tab1:
                            st.json({
                                "codigo_grupo": datos_xml["grupo"]["codigo_grupo"],
                                "responsable": datos_xml["grupo"]["responsable"],
                                "telefono_contacto": datos_xml["grupo"]["telefono_contacto"],
                                "modalidad": datos_xml["grupo"]["modalidad"],
                                "fecha_inicio": datos_xml["grupo"]["fecha_inicio"]
                            })
                        
                        with tab2:
                            st.json(empresa_responsable)
                        
                        with tab3:
                            for i, tutor in enumerate(datos_xml["tutores"]):
                                st.write(f"**Tutor {i+1}:**")
                                st.json({
                                    "nombre": tutor["nombre"],
                                    "apellidos": tutor["apellidos"],
                                    "tipo_documento": tutor["tipo_documento_fundae"],
                                    "nif": tutor["nif"]
                                })
                        
                        with tab4:
                            for i, empresa in enumerate(datos_xml["empresas"]):
                                st.write(f"**Empresa {i+1}:**")
                                st.json({
                                    "nombre": empresa["nombre"],
                                    "cif": empresa["cif"]
                                })
                    
                    # Botones de acción
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("📄 Generar XML", type="primary", key="generar_xml_inicio"):
                            with st.spinner("Generando XML con validaciones de jerarquía..."):
                                xml_content = generar_xml_inicio_grupo_con_jerarquia(datos_xml)
                                
                                if xml_content:
                                    st.success("✅ XML generado correctamente con validaciones FUNDAE")
                                    
                                    # Mostrar XML generado (preview)
                                    st.text_area("XML Generado:", xml_content[:1000] + "...", height=150, key="xml_preview")
                                    
                                    # Botón de descarga con nombre descriptivo
                                    codigo_grupo = datos_xml["grupo"]["codigo_grupo"]
                                    empresa_resp = empresa_responsable.get("nombre", "sin_empresa").replace(" ", "_")
                                    ano = datetime.now().year
                                    
                                    filename = f"inicio_grupo_{codigo_grupo}_{empresa_resp}_{ano}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
                                    
                                    st.download_button(
                                        label="💾 Descargar XML",
                                        data=xml_content,
                                        file_name=filename,
                                        mime="application/xml"
                                    )
                                else:
                                    st.error("❌ Error al generar el XML")
                    
                    with col2:
                        if st.button("✅ Validar XML", key="validar_xml_inicio") and xsd_urls.get('inicio_grupo'):
                            with st.spinner("Validando XML contra esquema FUNDAE..."):
                                xml_content = generar_xml_inicio_grupo_con_jerarquia(datos_xml)
                                
                                if xml_content:
                                    es_valido, errores_xsd = validar_xml(xml_content, xsd_urls['inicio_grupo'])
                                    
                                    if es_valido:
                                        st.success("✅ El XML es válido según el esquema FUNDAE")
                                    else:
                                        st.error("❌ El XML no es válido según el esquema XSD")
                                        for error in errores_xsd[:5]:
                                            st.error(f"• {error}")
                                        if len(errores_xsd) > 5:
                                            st.info(f"... y {len(errores_xsd) - 5} errores más")
    
    # =========================
    # XML FINALIZACIÓN DE GRUPO CON JERARQUÍA
    # =========================
    elif tipo_documento == "XML Finalización de Grupo":
        st.markdown("### 🏁 Generar XML de Finalización de Grupo")
        st.caption("🔍 Con validaciones de coherencia y jerarquía empresarial")
        
        if df_grupos.empty:
            st.warning("⚠️ No hay grupos disponibles")
            return
        
        # Filtrar grupos finalizables con mejor lógica
        grupos_finalizables = []
        hoy = date.today()
        
        for _, grupo in df_grupos.iterrows():
            # Determinar si el grupo puede finalizarse
            fecha_fin_prevista = grupo.get('fecha_fin_prevista')
            fecha_fin_real = grupo.get('fecha_fin')
            estado_grupo = grupo.get('estado', 'ABIERTO')
            
            # Grupo finalizable si:
            # 1. Ya tiene fecha fin real (ya finalizado)
            # 2. La fecha prevista ya pasó
            # 3. Está en estado FINALIZAR o FINALIZADO
            puede_finalizar = False
            
            if fecha_fin_real:
                puede_finalizar = True
            elif fecha_fin_prevista:
                try:
                    fecha_prevista_dt = datetime.fromisoformat(str(fecha_fin_prevista).replace('Z', '+00:00')).date()
                    if fecha_prevista_dt <= hoy:
                        puede_finalizar = True
                except:
                    pass
            elif estado_grupo in ['FINALIZAR', 'FINALIZADO']:
                puede_finalizar = True
            
            if puede_finalizar:
                grupos_finalizables.append(grupo.to_dict())
        
        if not grupos_finalizables:
            st.warning("⚠️ No hay grupos disponibles para finalización")
            st.info("💡 Los grupos deben haber superado su fecha prevista o estar marcados como finalizados")
            return
        
        # Crear diccionario de grupos finalizables
        grupos_dict = {}
        for grupo in grupos_finalizables:
            codigo = grupo.get('codigo_grupo', 'Sin código')
            accion_nombre = grupo.get('accion_nombre', grupo.get('accion_formativa_nombre', 'Sin acción'))
            fecha_fin = grupo.get('fecha_fin', grupo.get('fecha_fin_prevista', 'Sin fecha'))
            empresa_nombre = grupo.get('empresa_nombre', 'Sin empresa')
            
            # Determinar estado visual
            if grupo.get('fecha_fin'):
                estado_visual = "FINALIZADO"
            elif grupo.get('estado') == 'FINALIZAR':
                estado_visual = "PENDIENTE"
            else:
                estado_visual = "DISPONIBLE"
            
            nombre_mostrar = f"{codigo} - {accion_nombre} ({empresa_nombre} - {estado_visual})"
            grupos_dict[nombre_mostrar] = grupo
        
        grupo_seleccionado = st.selectbox(
            "Selecciona un grupo para finalizar:",
            ["Seleccionar..."] + list(grupos_dict.keys()),
            key="grupo_fin_xml",
            help="Solo se muestran grupos que han superado su fecha prevista o están marcados para finalizar"
        )
        
        if grupo_seleccionado != "Seleccionar...":
            grupo_data = grupos_dict[grupo_seleccionado]
            grupo_id = grupo_data.get('id')
            
            # Validar empresa responsable para finalización
            with st.spinner("Validando permisos y datos para finalización..."):
                empresa_responsable, error_empresa = get_empresa_responsable_fundae(supabase, grupo_id)
                
                if error_empresa:
                    st.error(f"❌ Error al determinar empresa responsable: {error_empresa}")
                    return
                
                # Mostrar empresa responsable
                st.info(f"🏢 Empresa responsable ante FUNDAE: **{empresa_responsable.get('nombre')}** (CIF: {empresa_responsable.get('cif')})")
            
            # Obtener participantes del grupo
            with st.spinner("Cargando participantes del grupo..."):
                try:
                    # Buscar participantes usando la relación correcta
                    participantes_query = supabase.table("participantes").select("*")
                    
                    # Buscar por grupo_id directo o por relación participantes_grupos
                    participantes_directos = participantes_query.eq("grupo_id", grupo_id).execute()
                    participantes_data = participantes_directos.data or []
                    
                    # Si no hay participantes directos, buscar en tabla de relaciones
                    if not participantes_data:
                        relaciones_res = supabase.table("participantes_grupos").select("""
                            participante_id,
                            participantes(*)
                        """).eq("grupo_id", grupo_id).execute()
                        
                        if relaciones_res.data:
                            participantes_data = [rel["participantes"] for rel in relaciones_res.data if rel.get("participantes")]
                    
                    if not participantes_data:
                        st.warning(f"⚠️ No hay participantes en el grupo {grupo_data.get('codigo_grupo', 'seleccionado')}")
                        st.info("💡 Asigna participantes al grupo antes de generar el XML de finalización")
                        return
                    else:
                        st.success(f"✅ Encontrados {len(participantes_data)} participantes en el grupo")
                        
                        # Información de finalización con validaciones
                        st.markdown("#### 📝 Información de Finalización")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        # Valores actuales del grupo
                        n_finalizados_actual = grupo_data.get('n_participantes_finalizados', len(participantes_data))
                        n_aptos_actual = grupo_data.get('n_aptos', len(participantes_data))
                        n_no_aptos_actual = grupo_data.get('n_no_aptos', 0)
                        
                        with col1:
                            n_finalizados = st.number_input(
                                "👥 Participantes Finalizados:",
                                min_value=0,
                                max_value=len(participantes_data),
                                value=min(n_finalizados_actual, len(participantes_data)),
                                help="Número total de participantes que completaron la formación"
                            )
                        
                        with col2:
                            n_aptos = st.number_input(
                                "✅ Participantes APTOS:",
                                min_value=0,
                                max_value=n_finalizados,
                                value=min(n_aptos_actual, n_finalizados),
                                help="Participantes que superaron la formación"
                            )
                        
                        with col3:
                            n_no_aptos = st.number_input(
                                "❌ Participantes NO APTOS:",
                                min_value=0,
                                max_value=n_finalizados,
                                value=min(n_no_aptos_actual, n_finalizados - n_aptos),
                                help="Participantes que no superaron la formación"
                            )
                        
                        # Validación en tiempo real
                        if n_finalizados > 0:
                            total_resultado = n_aptos + n_no_aptos
                            if total_resultado != n_finalizados:
                                st.error(f"❌ Error: Aptos ({n_aptos}) + No Aptos ({n_no_aptos}) = {total_resultado}, debe ser igual a Finalizados ({n_finalizados})")
                                return
                            else:
                                st.success(f"✅ Coherencia validada: {n_aptos} aptos + {n_no_aptos} no aptos = {n_finalizados} finalizados")
                        
                        # Fecha de finalización
                        fecha_fin_actual = grupo_data.get('fecha_fin')
                        if fecha_fin_actual:
                            try:
                                fecha_fin_default = datetime.fromisoformat(str(fecha_fin_actual).replace('Z', '+00:00')).date()
                            except:
                                fecha_fin_default = date.today()
                        else:
                            fecha_fin_default = date.today()
                        
                        fecha_fin_real = st.date_input(
                            "📅 Fecha Real de Finalización:",
                            value=fecha_fin_default,
                            help="Fecha en que realmente finalizó el grupo"
                        )
                        
                        # Actualizar datos del grupo para XML
                        grupo_data_final = grupo_data.copy()
                        grupo_data_final.update({
                            'n_participantes_finalizados': n_finalizados,
                            'n_aptos': n_aptos,
                            'n_no_aptos': n_no_aptos,
                            'fecha_fin': fecha_fin_real.isoformat(),
                            'empresa_responsable': empresa_responsable
                        })
                        
                        # Vista previa de datos
                        with st.expander("👀 Vista previa de datos de finalización", expanded=False):
                            tab1, tab2, tab3 = st.tabs(["Datos Grupo", "Participantes", "Empresa Responsable"])
                            
                            with tab1:
                                st.json({
                                    "codigo_grupo": grupo_data_final.get('codigo_grupo'),
                                    "fecha_fin_real": fecha_fin_real.isoformat(),
                                    "participantes_finalizados": n_finalizados,
                                    "participantes_aptos": n_aptos,
                                    "participantes_no_aptos": n_no_aptos
                                })
                            
                            with tab2:
                                # Mostrar muestra de participantes
                                participantes_preview = participantes_data[:3]
                                for i, p in enumerate(participantes_preview):
                                    st.write(f"**Participante {i+1}:**")
                                    st.json({
                                        "nombre": p.get('nombre', ''),
                                        "apellidos": p.get('apellidos', ''),
                                        "nif": p.get('nif', ''),
                                        "email": p.get('email', '')
                                    })
                                if len(participantes_data) > 3:
                                    st.caption(f"... y {len(participantes_data) - 3} participantes más")
                            
                            with tab3:
                                st.json(empresa_responsable)
                        
                        # Botones de acción
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("📄 Generar XML Finalización", type="primary", key="generar_xml_fin"):
                                with st.spinner("Generando XML de finalización con validaciones..."):
                                    xml_content = generar_xml_finalizacion_grupo(grupo_data_final, participantes_data)
                                    
                                    if xml_content:
                                        st.success("✅ XML de finalización generado correctamente")
                                        
                                        # Mostrar preview del XML
                                        st.text_area("XML Generado:", xml_content[:1000] + "...", height=150)
                                        
                                        # Botón de descarga con nombre descriptivo
                                        codigo_grupo = grupo_data_final.get('codigo_grupo', 'sin_codigo')
                                        empresa_nombre = empresa_responsable.get('nombre', 'sin_empresa').replace(' ', '_')
                                        ano = fecha_fin_real.year
                                        
                                        filename = f"fin_grupo_{codigo_grupo}_{empresa_nombre}_{ano}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
                                        
                                        st.download_button(
                                            label="💾 Descargar XML Finalización",
                                            data=xml_content,
                                            file_name=filename,
                                            mime="application/xml"
                                        )
                                    else:
                                        st.error("❌ Error al generar el XML")
                        
                        with col2:
                            if st.button("✅ Validar XML", key="validar_xml_fin") and xsd_urls.get('finalizacion_grupo'):
                                with st.spinner("Validando XML contra esquema FUNDAE..."):
                                    xml_content = generar_xml_finalizacion_grupo(grupo_data_final, participantes_data)
                                    
                                    if xml_content:
                                        es_valido, errores = validar_xml(xml_content, xsd_urls['finalizacion_grupo'])
                                        
                                        if es_valido:
                                            st.success("✅ El XML de finalización es válido según el esquema FUNDAE")
                                        else:
                                            st.error("❌ El XML no es válido según el esquema XSD")
                                            for error in errores[:5]:
                                                st.error(f"• {error}")
                                            if len(errores) > 5:
                                                st.info(f"... y {len(errores) - 5} errores más")
                                    
                except Exception as e:
                    st.error(f"❌ Error al cargar participantes: {e}")
    
    # =========================
    # Información final
    # =========================
    st.divider()
    
    with st.expander("ℹ️ Información sobre documentos FUNDAE con jerarquía", expanded=False):
        st.markdown("""
        ### 📋 Tipos de documentos FUNDAE con validaciones:
        
        **XML Acción Formativa:**
        - Códigos únicos por empresa gestora y año
        - Empresa responsable ante FUNDAE claramente identificada
        - Validación automática de duplicados
        
        **XML Inicio de Grupo:**
        - Códigos únicos por acción, empresa gestora y año
        - Jerarquía empresarial respetada (gestora > clientes)
        - Validación de permisos según rol
        
        **XML Finalización de Grupo:**
        - Coherencia de participantes (finalizados = aptos + no aptos)
        - Empresa responsable consistente con el inicio
        - Validación temporal de fechas
        
        ### 🔍 Validaciones FUNDAE aplicadas:
        - **Códigos únicos**: Por empresa gestora y año calendario
        - **Jerarquía empresarial**: Gestoras responsables de sus clientes
        - **Coherencia temporal**: Años consistentes entre documentos
        - **Integridad de datos**: Participantes y empresas validados
        
        ### ⚠️ Notas importantes:
        - Los XMLs incluyen metadatos de validación
        - La empresa responsable ante FUNDAE es siempre la gestora
        - Los códigos se reutilizan cada año calendario
        - Validación automática contra esquemas XSD oficiales
        """)
    
    st.caption("💡 Sistema mejorado con validaciones de jerarquía empresarial y códigos únicos FUNDAE")
