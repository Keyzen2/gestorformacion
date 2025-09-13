import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from utils import (
    generar_pdf,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo,
    validar_xml,
    export_csv,
    get_ajustes_app
)
from services.data_service import get_data_service

def filtrar_grupos_por_accion(supabase, accion_formativa_id, empresa_id=None, rol="admin"):
    """
    Filtra grupos por acción formativa con verificación de campos.
    CORRECCIÓN: Verifica que las columnas existan antes de usarlas.
    """
    try:
        # Construir consulta base
        query = supabase.table("grupos").select("*")
        
        # Filtrar por acción formativa si se proporciona
        if accion_formativa_id:
            query = query.eq("accion_formativa_id", accion_formativa_id)
        
        # Filtrar por empresa según el rol
        if rol == "gestor" and empresa_id:
            query = query.eq("empresa_id", empresa_id)
        
        # Ejecutar consulta
        res = query.execute()
        grupos_data = res.data or []
        
        if not grupos_data:
            return pd.DataFrame()
        
        # Crear DataFrame y verificar columnas
        df_grupos = pd.DataFrame(grupos_data)
        
        # ✅ CORRECCIÓN: Verificar que las columnas necesarias existan
        columnas_esperadas = ['id', 'codigo_grupo', 'accion_formativa_id']
        for col in columnas_esperadas:
            if col not in df_grupos.columns:
                st.warning(f"⚠️ Columna '{col}' no encontrada en los datos de grupos")
                return pd.DataFrame()
        
        return df_grupos
        
    except Exception as e:
        st.error(f"❌ No se puede filtrar grupos por acción formativa: {e}")
        return pd.DataFrame()


def main(supabase, session_state):
    st.title("📄 Generación de Documentos FUNDAE")
    st.caption("Genera XMLs y PDFs oficiales para FUNDAE")
    
    # Obtener datos del usuario
    empresa_id = session_state.user.get("empresa_id")
    user_role = session_state.role
    
    # Verificar permisos
    if user_role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para generar documentos FUNDAE")
        return
    
    # Inicializar data service
    data_service = get_data_service(supabase, session_state)
    
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
    # Cargar datos
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            # Usar DataService para obtener datos
            df_acciones = data_service.get_acciones_formativas()
            df_grupos = data_service.get_grupos_completos()
            
            # Filtrar por empresa según el rol
            if user_role == "gestor" and empresa_id:
                if not df_acciones.empty and "empresa_id" in df_acciones.columns:
                    df_acciones = df_acciones[df_acciones["empresa_id"] == empresa_id]
                if not df_grupos.empty and "empresa_id" in df_grupos.columns:
                    df_grupos = df_grupos[df_grupos["empresa_id"] == empresa_id]
            
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return
    
    # =========================
    # Métricas
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
        # Intentar obtener documentos generados
        try:
            documentos_count = len(data_service.get_documentos())
            st.metric("📄 Documentos", documentos_count)
        except:
            st.metric("📄 Documentos", 0)
    
    st.divider()
    
    # =========================
    # Selector de tipo de documento
    # =========================
    tipo_documento = st.selectbox(
        "🎯 Selecciona el tipo de documento a generar:",
        ["Seleccionar...", "XML Acción Formativa", "XML Inicio de Grupo", "XML Finalización de Grupo"],
        key="tipo_documento"
    )
    
    if tipo_documento == "Seleccionar...":
        st.info("👆 Selecciona un tipo de documento para comenzar")
        return
    
    # =========================
    # XML ACCIÓN FORMATIVA
    # =========================
    elif tipo_documento == "XML Acción Formativa":
        st.markdown("### 📚 Generar XML de Acción Formativa")
        
        if df_acciones.empty:
            st.warning("⚠️ No hay acciones formativas disponibles")
            return
        
        # Crear diccionario de acciones para el selectbox
        acciones_dict = {}
        for _, accion in df_acciones.iterrows():
            nombre_mostrar = f"{accion.get('codigo_accion', 'Sin código')} - {accion.get('nombre', 'Sin nombre')}"
            acciones_dict[nombre_mostrar] = accion.to_dict()
        
        accion_seleccionada = st.selectbox(
            "Selecciona una acción formativa:",
            ["Seleccionar..."] + list(acciones_dict.keys()),
            key="accion_xml"
        )
        
        if accion_seleccionada != "Seleccionar...":
            accion_data = acciones_dict[accion_seleccionada]
            
            # Mostrar vista previa
            with st.expander("👀 Vista previa de datos", expanded=False):
                st.json(accion_data)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 Generar XML", type="primary", key="generar_xml_accion"):
                    with st.spinner("Generando XML..."):
                        xml_content = generar_xml_accion_formativa(accion_data)
                        
                        if xml_content:
                            st.success("✅ XML generado correctamente")
                            
                            # Mostrar XML generado
                            st.text_area("XML Generado:", xml_content, height=200)
                            
                            # Botón de descarga
                            st.download_button(
                                label="💾 Descargar XML",
                                data=xml_content,
                                file_name=f"accion_formativa_{accion_data.get('codigo_accion', 'sin_codigo')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml",
                                mime="application/xml"
                            )
                        else:
                            st.error("❌ Error al generar el XML")
            
            with col2:
                if st.button("✅ Validar XML", key="validar_xml_accion") and xsd_urls['accion_formativa']:
                    with st.spinner("Validando XML..."):
                        xml_content = generar_xml_accion_formativa(accion_data)
                        
                        if xml_content:
                            es_valido, errores = validar_xml(xml_content, xsd_urls['accion_formativa'])
                            
                            if es_valido:
                                st.success("✅ El XML es válido según el esquema FUNDAE")
                            else:
                                st.error("❌ El XML no es válido según el esquema XSD")
                                for error in errores[:5]:  # Mostrar solo los primeros 5 errores
                                    st.caption(f"• {error}")
                                if len(errores) > 5:
                                    st.caption(f"... y {len(errores) - 5} errores más")
    
    # =========================
    # XML INICIO DE GRUPO
    # =========================
    elif tipo_documento == "XML Inicio de Grupo":
        st.markdown("### 👥 Generar XML de Inicio de Grupo")
        
        if df_grupos.empty:
            st.warning("⚠️ No hay grupos disponibles")
            return
        
        # Crear diccionario de grupos para el selectbox
        grupos_dict = {}
        for _, grupo in df_grupos.iterrows():
            # ✅ CORRECCIÓN: Verificar que las columnas existan antes de usarlas
            codigo = grupo.get('codigo_grupo', 'Sin código')
            accion_nombre = grupo.get('accion_nombre', 'Sin acción')
            if not accion_nombre or accion_nombre == 'Sin acción':
                # Intentar obtener de otras columnas posibles
                accion_nombre = grupo.get('accion_formativa_nombre', 'Acción no disponible')
            
            nombre_mostrar = f"{codigo} - {accion_nombre}"
            grupos_dict[nombre_mostrar] = grupo.to_dict()
        
        grupo_seleccionado = st.selectbox(
            "Selecciona un grupo:",
            ["Seleccionar..."] + list(grupos_dict.keys()),
            key="grupo_inicio_xml"
        )
        
        if grupo_seleccionado != "Seleccionar...":
            grupo_data = grupos_dict[grupo_seleccionado]
            grupo_id = grupo_data.get('id')
            
            # ✅ CORRECCIÓN: Usar función corregida para obtener participantes
            with st.spinner("Cargando participantes del grupo..."):
                try:
                    # Obtener participantes del grupo de forma segura
                    participantes_res = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute()
                    participantes_data = participantes_res.data or []
                    
                    if not participantes_data:
                        st.warning(f"⚠️ No hay participantes en el grupo {grupo_data.get('codigo_grupo', 'seleccionado')}")
                    else:
                        st.info(f"📊 Encontrados {len(participantes_data)} participantes en el grupo")
                        
                        # Mostrar vista previa
                        with st.expander("👀 Vista previa de datos", expanded=False):
                            st.subheader("Datos del Grupo:")
                            st.json(grupo_data)
                            st.subheader("Participantes:")
                            st.json(participantes_data[:3])  # Mostrar solo los primeros 3
                            if len(participantes_data) > 3:
                                st.caption(f"... y {len(participantes_data) - 3} participantes más")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("📄 Generar XML", type="primary", key="generar_xml_inicio"):
                                with st.spinner("Generando XML..."):
                                    xml_content = generar_xml_inicio_grupo(grupo_data, participantes_data)
                                    
                                    if xml_content:
                                        st.success("✅ XML generado correctamente")
                                        
                                        # Mostrar XML generado
                                        st.text_area("XML Generado:", xml_content, height=200)
                                        
                                        # Botón de descarga
                                        st.download_button(
                                            label="💾 Descargar XML",
                                            data=xml_content,
                                            file_name=f"inicio_grupo_{grupo_data.get('codigo_grupo', 'sin_codigo')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml",
                                            mime="application/xml"
                                        )
                                    else:
                                        st.error("❌ Error al generar el XML")
                        
                        with col2:
                            if st.button("✅ Validar XML", key="validar_xml_inicio") and xsd_urls['inicio_grupo']:
                                with st.spinner("Validando XML..."):
                                    xml_content = generar_xml_inicio_grupo(grupo_data, participantes_data)
                                    
                                    if xml_content:
                                        es_valido, errores = validar_xml(xml_content, xsd_urls['inicio_grupo'])
                                        
                                        if es_valido:
                                            st.success("✅ El XML es válido según el esquema FUNDAE")
                                        else:
                                            st.error("❌ El XML no es válido según el esquema XSD")
                                            for error in errores[:5]:
                                                st.caption(f"• {error}")
                                            if len(errores) > 5:
                                                st.caption(f"... y {len(errores) - 5} errores más")
                                    
                except Exception as e:
                    st.error(f"❌ Error al cargar participantes: {e}")
    
    # =========================
    # XML FINALIZACIÓN DE GRUPO
    # =========================
    elif tipo_documento == "XML Finalización de Grupo":
        st.markdown("### 🏁 Generar XML de Finalización de Grupo")
        
        if df_grupos.empty:
            st.warning("⚠️ No hay grupos disponibles")
            return
        
        # Filtrar solo grupos que han terminado o están cerca de terminar
        grupos_finalizables = df_grupos.copy()
        if "fecha_fin" in grupos_finalizables.columns:
            # Mostrar grupos que ya terminaron o están por terminar
            fecha_limite = pd.Timestamp.now() - pd.Timedelta(days=30)  # Últimos 30 días
            mask = pd.to_datetime(grupos_finalizables["fecha_fin"], errors='coerce') >= fecha_limite
            grupos_finalizables = grupos_finalizables[mask]
        
        if grupos_finalizables.empty:
            st.warning("⚠️ No hay grupos disponibles para finalización")
            return
        
        # Crear diccionario de grupos
        grupos_dict = {}
        for _, grupo in grupos_finalizables.iterrows():
            codigo = grupo.get('codigo_grupo', 'Sin código')
            accion_nombre = grupo.get('accion_nombre', grupo.get('accion_formativa_nombre', 'Sin acción'))
            fecha_fin = grupo.get('fecha_fin', 'Sin fecha')
            
            nombre_mostrar = f"{codigo} - {accion_nombre} (Fin: {fecha_fin})"
            grupos_dict[nombre_mostrar] = grupo.to_dict()
        
        grupo_seleccionado = st.selectbox(
            "Selecciona un grupo finalizado:",
            ["Seleccionar..."] + list(grupos_dict.keys()),
            key="grupo_fin_xml"
        )
        
        if grupo_seleccionado != "Seleccionar...":
            grupo_data = grupos_dict[grupo_seleccionado]
            grupo_id = grupo_data.get('id')
            
            # Obtener participantes del grupo
            with st.spinner("Cargando participantes del grupo..."):
                try:
                    participantes_res = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute()
                    participantes_data = participantes_res.data or []
                    
                    if not participantes_data:
                        st.warning(f"⚠️ No hay participantes en el grupo {grupo_data.get('codigo_grupo', 'seleccionado')}")
                    else:
                        st.info(f"📊 Encontrados {len(participantes_data)} participantes en el grupo")
                        
                        # Campos adicionales para finalización
                        st.markdown("#### 📝 Información de Finalización")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            n_aptos = st.number_input("Participantes APTOS:", min_value=0, max_value=len(participantes_data), value=len(participantes_data))
                        with col2:
                            n_no_aptos = st.number_input("Participantes NO APTOS:", min_value=0, max_value=len(participantes_data), value=0)
                        
                        # Actualizar datos del grupo
                        grupo_data['n_participantes_finalizados'] = len(participantes_data)
                        grupo_data['n_aptos'] = n_aptos
                        grupo_data['n_no_aptos'] = n_no_aptos
                        
                        # Mostrar vista previa
                        with st.expander("👀 Vista previa de datos", expanded=False):
                            st.subheader("Datos del Grupo:")
                            st.json(grupo_data)
                            st.subheader("Participantes:")
                            st.json(participantes_data[:3])
                            if len(participantes_data) > 3:
                                st.caption(f"... y {len(participantes_data) - 3} participantes más")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("📄 Generar XML", type="primary", key="generar_xml_fin"):
                                with st.spinner("Generando XML..."):
                                    xml_content = generar_xml_finalizacion_grupo(grupo_data, participantes_data)
                                    
                                    if xml_content:
                                        st.success("✅ XML generado correctamente")
                                        
                                        # Mostrar XML generado
                                        st.text_area("XML Generado:", xml_content, height=200)
                                        
                                        # Botón de descarga
                                        st.download_button(
                                            label="💾 Descargar XML",
                                            data=xml_content,
                                            file_name=f"fin_grupo_{grupo_data.get('codigo_grupo', 'sin_codigo')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml",
                                            mime="application/xml"
                                        )
                                    else:
                                        st.error("❌ Error al generar el XML")
                        
                        with col2:
                            if st.button("✅ Validar XML", key="validar_xml_fin") and xsd_urls['finalizacion_grupo']:
                                with st.spinner("Validando XML..."):
                
