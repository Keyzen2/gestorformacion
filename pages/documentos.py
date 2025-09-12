import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from utils import generar_pdf, generar_xml_accion_formativa, generar_xml_inicio_grupo, generar_xml_finalizacion_grupo, validar_xml, get_ajustes_app, export_csv
from services.data_service import get_data_service

def main(supabase, session_state):
    st.title("📄 Generación de Documentos FUNDAE")
    st.caption("Genera XMLs y PDFs oficiales para comunicaciones con FUNDAE.")
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Cargar configuración
    ajustes = get_ajustes_app(supabase)
    
    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)

    # Leer URLs XSD desde secrets
    try:
        FUNDAE = st.secrets["FUNDAE"]
        xsd_urls = {
            'accion_formativa': FUNDAE["xsd_accion_formativa"],
            'inicio_grupo': FUNDAE["xsd_inicio_grupo"],
            'finalizacion_grupo': FUNDAE["xsd_finalizacion_grupo"]
        }
    except Exception as e:
        st.error("⚠️ Error al cargar configuración de esquemas XSD. Verifica la configuración en secrets.")
        return

    # =========================
    # CARGAR DATOS CON DataService
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            df_acciones = data_service.get_acciones_formativas()
            df_grupos = data_service.get_grupos_completos()
            df_participantes = data_service.get_participantes_completos()
        except Exception as e:
            st.error(f"⚠️ Error al cargar datos: {e}")
            return

    # =========================
    # MÉTRICAS DEL DASHBOARD
    # =========================
    if not df_acciones.empty or not df_grupos.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📚 Acciones Formativas", len(df_acciones))
        
        with col2:
            st.metric("👥 Grupos", len(df_grupos))
        
        with col3:
            grupos_activos = df_grupos[df_grupos['estado'] == 'activo'] if 'estado' in df_grupos.columns and not df_grupos.empty else pd.DataFrame()
            st.metric("✅ Grupos Activos", len(grupos_activos))
        
        with col4:
            grupos_cerrados = df_grupos[df_grupos['estado'] == 'cerrado'] if 'estado' in df_grupos.columns and not df_grupos.empty else pd.DataFrame()
            st.metric("🏁 Grupos Cerrados", len(grupos_cerrados))

    st.divider()

    # =========================
    # SELECCIÓN DE ACCIÓN FORMATIVA
    # =========================
    st.markdown("### 📋 Selección de Acción Formativa")
    
    if df_acciones.empty:
        st.warning("⚠️ No hay acciones formativas disponibles.")
        return

    # Preparar opciones de acciones formativas
    acciones_opciones = {}
    for _, accion in df_acciones.iterrows():
        display_name = f"{accion.get('codigo_accion', 'Sin código')} - {accion.get('nombre', 'Sin nombre')}"
        acciones_opciones[display_name] = accion

    accion_seleccionada = st.selectbox(
        "Selecciona la acción formativa:",
        options=list(acciones_opciones.keys()),
        help="Selecciona la acción formativa para generar documentos"
    )

    accion = acciones_opciones[accion_seleccionada]

    # Mostrar información de la acción seleccionada
    with st.expander("ℹ️ Información de la Acción Formativa", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Código:** {accion.get('codigo_accion', 'No especificado')}")
            st.write(f"**Nombre:** {accion.get('nombre', 'No especificado')}")
            st.write(f"**Modalidad:** {accion.get('modalidad', 'No especificada')}")
        with col2:
            st.write(f"**Duración:** {accion.get('num_horas', 0)} horas")
            st.write(f"**Nivel:** {accion.get('nivel', 'No especificado')}")
            st.write(f"**Área:** {accion.get('area_profesional', 'No especificada')}")

    # =========================
    # SELECCIÓN DE GRUPO - CORREGIDO
    # =========================
    st.markdown("### 👥 Selección de Grupo")
    
    # Función para filtrar grupos por acción - CORREGIDO
    def filtrar_grupos_por_accion(df_grupos, accion_id):
        """Filtra grupos por acción formativa con verificación de columnas."""
        if df_grupos.empty:
            return pd.DataFrame()
        
        # Verificar qué columna existe para la relación
        if 'accion_formativa_id' in df_grupos.columns:
            return df_grupos[df_grupos['accion_formativa_id'] == accion_id]
        elif 'accion_id' in df_grupos.columns:
            return df_grupos[df_grupos['accion_id'] == accion_id]
        else:
            # Si no existe relación directa, devolver DataFrame vacío
            st.warning("⚠️ No se puede filtrar grupos por acción formativa: campo de relación no encontrado")
            return pd.DataFrame()

    # Usar la función corregida
    grupos_accion = filtrar_grupos_por_accion(df_grupos, accion['id'])
    
    if grupos_accion.empty:
        st.warning("⚠️ No hay grupos disponibles para esta acción formativa.")
        grupo = None
    else:
        # Preparar opciones de grupos
        grupos_opciones = {}
        for _, grupo_row in grupos_accion.iterrows():
            display_name = f"{grupo_row.get('codigo_grupo', 'Sin código')} - {grupo_row.get('estado', 'Sin estado')}"
            grupos_opciones[display_name] = grupo_row

        grupo_seleccionado = st.selectbox(
            "Selecciona el grupo:",
            options=list(grupos_opciones.keys()),
            help="Selecciona el grupo para generar XMLs de inicio o finalización"
        )

        grupo = grupos_opciones[grupo_seleccionado]

        # Mostrar información del grupo seleccionado
        with st.expander("ℹ️ Información del Grupo", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Código:** {grupo.get('codigo_grupo', 'No especificado')}")
                st.write(f"**Estado:** {grupo.get('estado', 'No especificado')}")
                st.write(f"**Fecha Inicio:** {grupo.get('fecha_inicio', 'No especificada')}")
            with col2:
                st.write(f"**Fecha Fin:** {grupo.get('fecha_fin_prevista', 'No especificada')}")
                st.write(f"**Modalidad:** {grupo.get('modalidad', 'No especificada')}")
                st.write(f"**Participantes:** {grupo.get('n_participantes_previstos', 0)}")

    st.divider()

    # =========================
    # GENERACIÓN DE DOCUMENTOS
    # =========================
    st.markdown("### 🔧 Generar Documentos")
    
    # Organizar en tabs para mejor UX
    tab1, tab2, tab3, tab4 = st.tabs([
        "📄 PDF Acción",
        "📋 XML Acción",
        "🚀 XML Inicio Grupo",
        "🏁 XML Finalización"
    ])

    # TAB 1: PDF de Acción Formativa
    with tab1:
        st.subheader("📄 Generar PDF de Acción Formativa")
        st.caption("Genera un documento PDF con la información de la acción formativa")
        
        if st.button("🔧 Generar PDF", type="primary", use_container_width=True):
            with st.spinner("Generando PDF..."):
                try:
                    # Preparar información para el PDF
                    lines = [
                        f"ACCIÓN FORMATIVA",
                        f"",
                        f"Código: {accion.get('codigo_accion', 'No especificado')}",
                        f"Nombre: {accion.get('nombre', 'No especificado')}",
                        f"Modalidad: {accion.get('modalidad', 'No especificada')}",
                        f"Nivel: {accion.get('nivel', 'No especificado')}",
                        f"Duración: {accion.get('num_horas', 0)} horas",
                        f"Área Profesional: {accion.get('area_profesional', 'No especificada')}",
                        f"",
                        f"Objetivos: {accion.get('objetivos', 'No especificados')}",
                        f"Contenidos: {accion.get('contenidos', 'No especificados')}",
                        f"",
                        f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                    ]
                    
                    buffer = BytesIO()
                    pdf_bytes = generar_pdf(buffer, lines)
                    
                    if pdf_bytes:
                        st.success("✅ PDF generado correctamente")
                        st.download_button(
                            "📥 Descargar PDF Acción Formativa",
                            data=pdf_bytes.getvalue(),
                            file_name=f"AF_{accion.get('codigo_accion', 'sin_codigo')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    else:
                        st.error("❌ Error al generar el PDF")
                        
                except Exception as e:
                    st.error(f"❌ Error al generar PDF: {e}")

    # TAB 2: XML de Acción Formativa
    with tab2:
        st.subheader("📋 Generar XML de Acción Formativa")
        st.caption("Genera XML oficial para comunicar la acción formativa a FUNDAE")
        
        # Verificar campos obligatorios
        campos_obligatorios = ['codigo_accion', 'nombre', 'modalidad', 'num_horas']
        campos_faltantes = [c for c in campos_obligatorios if not accion.get(c)]
        
        if campos_faltantes:
            st.warning(f"⚠️ Faltan campos obligatorios: {', '.join(campos_faltantes)}")
            st.info("Completa la información de la acción formativa antes de generar el XML")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔧 Generar XML Acción", type="primary", use_container_width=True):
                    with st.spinner("Generando y validando XML..."):
                        try:
                            xml_content = generar_xml_accion_formativa(accion)
                            
                            if xml_content:
                                # Validar contra XSD
                                es_valido, errores = validar_xml(xml_content, xsd_urls['accion_formativa'])
                                
                                if es_valido:
                                    st.success("✅ XML generado y validado correctamente")
                                    st.download_button(
                                        "📥 Descargar XML Acción Formativa",
                                        data=xml_content,
                                        file_name=f"AF_{accion.get('codigo_accion', 'sin_codigo')}_{datetime.now().strftime('%Y%m%d')}.xml",
                                        mime="application/xml",
                                    )
                                else:
                                    st.error("❌ El XML no es válido según el esquema XSD")
                                    for error in errores[:5]:
                                        st.error(f"• {error}")
                            else:
                                st.error("❌ Error al generar el XML")
                                
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
            
            with col2:
                if st.button("👁️ Vista previa XML", use_container_width=True):
                    try:
                        xml_preview = generar_xml_accion_formativa(accion)
                        if xml_preview:
                            st.code(xml_preview[:1000] + "..." if len(xml_preview) > 1000 else xml_preview, language="xml")
                    except Exception as e:
                        st.error(f"❌ Error en vista previa: {e}")

    # TAB 3: XML de Inicio de Grupo
    with tab3:
        st.subheader("🚀 Generar XML de Inicio de Grupo")
        st.caption("Genera XML oficial para comunicar el inicio de grupo a FUNDAE")
        
        if not grupo:
            st.warning("⚠️ Selecciona un grupo para generar el XML de inicio")
        elif not grupo.get("fecha_inicio") or not grupo.get("fecha_fin_prevista"):
            st.error("⚠️ El grupo debe tener fechas de inicio y fin previstas")
        else:
            # Cargar participantes del grupo
            participantes_grupo = df_participantes[df_participantes['grupo_id'] == grupo['id']] if not df_participantes.empty else pd.DataFrame()
            
            if participantes_grupo.empty:
                st.warning("⚠️ No hay participantes asignados a este grupo")
                st.info("Asigna participantes al grupo antes de generar el XML")
            else:
                st.info(f"📊 Participantes encontrados: {len(participantes_grupo)}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🔧 Generar XML Inicio", type="primary", use_container_width=True):
                        with st.spinner("Generando y validando XML..."):
                            try:
                                # Convertir participantes a formato necesario
                                participantes_list = participantes_grupo.to_dict('records')
                                
                                xml_content = generar_xml_inicio_grupo(grupo, participantes_list)
                                
                                if xml_content:
                                    # Validar contra XSD
                                    es_valido, errores = validar_xml(xml_content, xsd_urls['inicio_grupo'])
                                    
                                    if es_valido:
                                        st.success("✅ XML de inicio generado y validado correctamente")
                                        st.download_button(
                                            "📥 Descargar XML Inicio Grupo",
                                            data=xml_content,
                                            file_name=f"IG_{grupo.get('codigo_grupo', 'sin_codigo')}_{datetime.now().strftime('%Y%m%d')}.xml",
                                            mime="application/xml",
                                            use_container_width=True
                                        )
                                    else:
                                        st.error("❌ El XML no es válido según el esquema XSD")
                                        for error in errores[:5]:
                                            st.error(f"• {error}")
                                else:
                                    st.error("❌ Error al generar el XML")
                                    
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                
                with col2:
                    if st.button("👁️ Vista previa XML", use_container_width=True):
                        try:
                            participantes_list = participantes_grupo.to_dict('records')
                            xml_preview = generar_xml_inicio_grupo(grupo, participantes_list)
                            if xml_preview:
                                st.code(xml_preview[:1000] + "..." if len(xml_preview) > 1000 else xml_preview, language="xml")
                        except Exception as e:
                            st.error(f"❌ Error en vista previa: {e}")

    # TAB 4: XML de Finalización de Grupo
    with tab4:
        st.subheader("🏁 Generar XML de Finalización de Grupo")
        st.caption("Genera XML oficial para comunicar la finalización de grupo a FUNDAE")
        
        if not grupo:
            st.warning("⚠️ Selecciona un grupo para generar el XML de finalización")
        elif grupo.get("estado") != "cerrado":
            st.error("⚠️ El grupo debe estar cerrado antes de generar el XML de finalización")
            st.info("Cambia el estado del grupo a 'cerrado' en la gestión de grupos")
        else:
            # Cargar participantes del grupo
            participantes_grupo = df_participantes[df_participantes['grupo_id'] == grupo['id']] if not df_participantes.empty else pd.DataFrame()
            
            if participantes_grupo.empty:
                st.warning("⚠️ No hay participantes registrados en este grupo")
            else:
                st.info(f"📊 Participantes encontrados: {len(participantes_grupo)}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🔧 Generar XML Finalización", type="primary", use_container_width=True):
                        with st.spinner("Generando y validando XML..."):
                            try:
                                # Convertir participantes a formato necesario
                                participantes_list = participantes_grupo.to_dict('records')
                                
                                xml_content = generar_xml_finalizacion_grupo(grupo, participantes_list)
                                
                                if xml_content:
                                    # Validar contra XSD
                                    es_valido, errores = validar_xml(xml_content, xsd_urls['finalizacion_grupo'])
                                    
                                    if es_valido:
                                        st.success("✅ XML de finalización generado y validado correctamente")
                                        st.download_button(
                                            "📥 Descargar XML Finalización Grupo",
                                            data=xml_content,
                                            file_name=f"FG_{grupo.get('codigo_grupo', 'sin_codigo')}_{datetime.now().strftime('%Y%m%d')}.xml",
                                            mime="application/xml",
                                            use_container_width=True
                                        )
                                    else:
                                        st.error("❌ El XML no es válido según el esquema XSD")
                                        for error in errores[:5]:
                                            st.error(f"• {error}")
                                else:
                                    st.error("❌ Error al generar el XML")
                                    
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                
                with col2:
                    if st.button("👁️ Vista previa XML", use_container_width=True):
                        try:
                            participantes_list = participantes_grupo.to_dict('records')
                            xml_preview = generar_xml_finalizacion_grupo(grupo, participantes_list)
                            if xml_preview:
                                st.code(xml_preview[:1000] + "..." if len(xml_preview) > 1000 else xml_preview, language="xml")
                        except Exception as e:
                            st.error(f"❌ Error en vista previa: {e}")

    # =========================
    # INFORMACIÓN ADICIONAL
    # =========================
    st.divider()
    st.markdown("### 📊 Resumen de Datos")
    
    if not df_acciones.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📈 Estadísticas")
            st.write(f"• **Total acciones formativas:** {len(df_acciones)}")
            st.write(f"• **Total grupos:** {len(df_grupos)}")
            st.write(f"• **Total participantes:** {len(df_participantes)}")
            
            # Exportar datos para análisis
            if st.button("📊 Exportar Datos para Análisis"):
                export_csv(df_acciones, "acciones_formativas.csv")
                export_csv(df_grupos, "grupos.csv")
                export_csv(df_participantes, "participantes.csv")
        
        with col2:
            st.markdown("#### ℹ️ Información")
            st.info("""
            **Documentos FUNDAE oficiales:**
            
            • **PDF Acción:** Documento informativo
            • **XML Acción:** Comunicación oficial de acción formativa
            • **XML Inicio:** Comunicación de inicio de grupo
            • **XML Finalización:** Comunicación de finalización
            
            Todos los XMLs se validan contra esquemas XSD oficiales.
            """)

    st.divider()
    st.caption("💡 Los documentos generados cumplen con los estándares oficiales de FUNDAE y se validan automáticamente.")
