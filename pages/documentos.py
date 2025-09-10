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
    export_csv
)
import os

def main(supabase, session_state):
    st.title("📄 Generación de Documentos FUNDAE")
    st.caption("Genera XMLs y PDFs oficiales para FUNDAE")
    
    # Verificar que el módulo está activo
    empresa_id = session_state.get("empresa_id")
    user_role = session_state.get("user_role", "alumno")
    
    # URLs de los esquemas XSD desde secrets
    xsd_urls = {
        'accion_formativa': st.secrets.get("FUNDAE", {}).get("xsd_accion_formativa"),
        'inicio_grupo': st.secrets.get("FUNDAE", {}).get("xsd_inicio_grupo"),
        'finalizacion_grupo': st.secrets.get("FUNDAE", {}).get("xsd_finalizacion_grupo")
    }
    
    # Verificar que tenemos las URLs
    if not all(xsd_urls.values()):
        st.error("⚠️ Faltan las URLs de los esquemas XSD en la configuración")
        st.info("Por favor, verifica que estén configuradas las URLs en los secrets de Streamlit")
        return
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        # Consultar datos según rol
        if user_role == "admin":
            acciones = supabase.table("acciones_formativas").select("*").execute().data or []
            grupos = supabase.table("grupos").select("*").execute().data or []
        elif user_role == "gestor" and empresa_id:
            acciones = supabase.table("acciones_formativas").select("*").eq("empresa_id", empresa_id).execute().data or []
            grupos = supabase.table("grupos").select("*").eq("empresa_id", empresa_id).execute().data or []
        else:
            st.warning("No tienes permisos para generar documentos")
            return
        
        # Obtener historial de documentos generados (si existe la tabla)
        try:
            historial = supabase.table("documentos_generados").select("*").order("created_at", desc=True).limit(10).execute().data or []
        except:
            historial = []
        
        with col1:
            st.metric("📚 Acciones Formativas", len(acciones))
        with col2:
            st.metric("👥 Grupos", len(grupos))
        with col3:
            grupos_activos = [g for g in grupos if g.get('estado') == 'activo']
            st.metric("✅ Grupos Activos", len(grupos_activos))
        with col4:
            st.metric("📄 Documentos Generados", len(historial))
        
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        return
    
    st.divider()
    
    # Tabs para diferentes tipos de documentos
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 XML Acción Formativa",
        "🚀 XML Inicio Grupo", 
        "🏁 XML Finalización Grupo",
        "📄 PDFs",
        "📊 Historial"
    ])
    
    # =========================
    # TAB 1: XML ACCIÓN FORMATIVA
    # =========================
    with tab1:
        st.subheader("📋 Generar XML de Acción Formativa")
        st.caption("Genera el XML de inicio de acción formativa para FUNDAE")
        
        if acciones:
            # Preparar opciones para el selectbox
            opciones_acciones = {
                f"{a['codigo']} - {a['denominacion']}": a 
                for a in acciones
            }
            
            accion_seleccionada = st.selectbox(
                "Selecciona la acción formativa:",
                options=list(opciones_acciones.keys()),
                help="Selecciona la acción formativa para generar su XML"
            )
            
            if accion_seleccionada:
                accion = opciones_acciones[accion_seleccionada]
                
                # Mostrar información de la acción
                with st.expander("ℹ️ Información de la Acción Formativa", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Código:** {accion.get('codigo', '')}")
                        st.write(f"**Denominación:** {accion.get('denominacion', '')}")
                        st.write(f"**Modalidad:** {accion.get('modalidad', '')}")
                    with col2:
                        st.write(f"**Horas:** {accion.get('horas', 0)}")
                        st.write(f"**Área:** {accion.get('area_profesional', '')}")
                        st.write(f"**Fecha Inicio:** {accion.get('fecha_inicio', '')}")
                
                # Validar que la acción tiene los campos obligatorios
                campos_obligatorios = ['codigo', 'denominacion', 'modalidad', 'horas']
                campos_faltantes = [c for c in campos_obligatorios if not accion.get(c)]
                
                if campos_faltantes:
                    st.warning(f"⚠️ Faltan campos obligatorios: {', '.join(campos_faltantes)}")
                    st.info("Por favor, completa la información de la acción formativa antes de generar el XML")
                else:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🔧 Generar XML Acción Formativa", type="primary", use_container_width=True):
                            with st.spinner("Generando XML..."):
                                try:
                                    # Generar XML con namespace correcto para FUNDAE
                                    # Ajustar el namespace según el esquema
                                    xml_content = generar_xml_accion_formativa(accion, namespace="http://www.fundae.es/esquemas")
                                    
                                    if xml_content:
                                        # Validar contra XSD
                                        es_valido, errores = validar_xml(xml_content, xsd_urls['accion_formativa'])
                                        
                                        if es_valido:
                                            st.success("✅ XML generado y validado correctamente")
                                            
                                            # Botón de descarga
                                            st.download_button(
                                                label="📥 Descargar XML Acción Formativa",
                                                data=xml_content,
                                                file_name=f"AF_{accion['codigo']}_{datetime.now().strftime('%Y%m%d')}.xml",
                                                mime="application/xml"
                                            )
                                            
                                            # Guardar en historial
                                            try:
                                                supabase.table("documentos_generados").insert({
                                                    "tipo": "XML_ACCION_FORMATIVA",
                                                    "referencia": accion['codigo'],
                                                    "empresa_id": empresa_id,
                                                    "usuario_id": session_state.get("user_id"),
                                                    "validado": True
                                                }).execute()
                                            except:
                                                pass
                                        else:
                                            st.error("❌ El XML no es válido según el esquema XSD")
                                            for error in errores[:5]:  # Mostrar máximo 5 errores
                                                st.error(f"• {error}")
                                            st.info("💡 Revisa que el namespace sea correcto y los campos cumplan con el esquema FUNDAE")
                                    else:
                                        st.error("Error al generar el XML")
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
                    
                    with col2:
                        # Mostrar preview del XML si existe
                        if st.button("👁️ Vista previa", use_container_width=True):
                            try:
                                xml_preview = generar_xml_accion_formativa(accion, namespace="http://www.fundae.es/esquemas")
                                if xml_preview:
                                    st.code(xml_preview[:1000] + "...", language="xml")
                            except Exception as e:
                                st.error(f"Error al generar vista previa: {str(e)}")
        else:
            st.info("No hay acciones formativas disponibles")
    
    # =========================
    # TAB 2: XML INICIO GRUPO
    # =========================
    with tab2:
        st.subheader("🚀 Generar XML de Inicio de Grupo")
        st.caption("Genera el XML de comunicación de inicio de grupo para FUNDAE")
        
        if grupos:
            # Preparar opciones
            opciones_grupos = {
                f"{g['codigo_grupo']} - {g.get('denominacion', 'Sin nombre')}": g 
                for g in grupos
            }
            
            grupo_seleccionado = st.selectbox(
                "Selecciona el grupo:",
                options=list(opciones_grupos.keys()),
                help="Selecciona el grupo para generar su XML de inicio"
            )
            
            if grupo_seleccionado:
                grupo = opciones_grupos[grupo_seleccionado]
                
                # Mostrar información del grupo
                with st.expander("ℹ️ Información del Grupo", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Código:** {grupo.get('codigo_grupo', '')}")
                        st.write(f"**Fecha Inicio:** {grupo.get('fecha_inicio', '')}")
                        st.write(f"**Fecha Fin:** {grupo.get('fecha_fin', '')}")
                    with col2:
                        st.write(f"**Modalidad:** {grupo.get('modalidad', '')}")
                        st.write(f"**Horario:** {grupo.get('horario', '')}")
                        st.write(f"**Estado:** {grupo.get('estado', 'activo')}")
                
                # Obtener participantes del grupo
                try:
                    participantes = supabase.table("participantes").select("*").eq("grupo_id", grupo['id']).execute().data or []
                    st.info(f"👥 El grupo tiene {len(participantes)} participantes")
                except:
                    participantes = []
                
                # Validar campos obligatorios
                campos_obligatorios = ['codigo_grupo', 'fecha_inicio', 'fecha_fin', 'modalidad']
                campos_faltantes = [c for c in campos_obligatorios if not grupo.get(c)]
                
                if campos_faltantes:
                    st.warning(f"⚠️ Faltan campos obligatorios: {', '.join(campos_faltantes)}")
                elif len(participantes) == 0:
                    st.warning("⚠️ El grupo no tiene participantes asignados")
                else:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🔧 Generar XML Inicio Grupo", type="primary", use_container_width=True):
                            with st.spinner("Generando XML de inicio..."):
                                try:
                                    # Generar XML de inicio
                                    xml_content = generar_xml_inicio_grupo(grupo, participantes)
                                    
                                    if xml_content:
                                        # Validar contra XSD
                                        es_valido, errores = validar_xml(xml_content, xsd_urls['inicio_grupo'])
                                        
                                        if es_valido:
                                            st.success("✅ XML de inicio generado y validado correctamente")
                                            
                                            # Botón de descarga
                                            st.download_button(
                                                label="📥 Descargar XML Inicio Grupo",
                                                data=xml_content,
                                                file_name=f"IG_{grupo['codigo_grupo']}_{datetime.now().strftime('%Y%m%d')}.xml",
                                                mime="application/xml"
                                            )
                                            
                                            # Guardar en historial
                                            try:
                                                supabase.table("documentos_generados").insert({
                                                    "tipo": "XML_INICIO_GRUPO",
                                                    "referencia": grupo['codigo_grupo'],
                                                    "empresa_id": empresa_id,
                                                    "usuario_id": session_state.get("user_id"),
                                                    "validado": True
                                                }).execute()
                                            except:
                                                pass
                                        else:
                                            st.error("❌ El XML no es válido según el esquema XSD")
                                            for error in errores[:5]:
                                                st.error(f"• {error}")
                                    else:
                                        st.error("Error al generar el XML")
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
                    
                    with col2:
                        if st.button("👁️ Vista previa", use_container_width=True):
                            try:
                                xml_preview = generar_xml_inicio_grupo(grupo, participantes)
                                if xml_preview:
                                    st.code(xml_preview[:1000] + "...", language="xml")
                            except Exception as e:
                                st.error(f"Error en vista previa: {str(e)}")
        else:
            st.info("No hay grupos disponibles")
    
    # =========================
    # TAB 3: XML FINALIZACIÓN GRUPO
    # =========================
    with tab3:
        st.subheader("🏁 Generar XML de Finalización de Grupo")
        st.caption("Genera el XML de comunicación de finalización de grupo para FUNDAE")
        
        # Filtrar solo grupos que puedan finalizarse
        grupos_finalizables = [g for g in grupos if g.get('estado') in ['activo', 'finalizado']]
        
        if grupos_finalizables:
            opciones_grupos_fin = {
                f"{g['codigo_grupo']} - {g.get('denominacion', 'Sin nombre')}": g 
                for g in grupos_finalizables
            }
            
            grupo_fin_seleccionado = st.selectbox(
                "Selecciona el grupo a finalizar:",
                options=list(opciones_grupos_fin.keys()),
                help="Selecciona el grupo para generar su XML de finalización"
            )
            
            if grupo_fin_seleccionado:
                grupo_fin = opciones_grupos_fin[grupo_fin_seleccionado]
                
                # Mostrar información
                with st.expander("ℹ️ Información del Grupo", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Código:** {grupo_fin.get('codigo_grupo', '')}")
                        st.write(f"**Fecha Inicio:** {grupo_fin.get('fecha_inicio', '')}")
                        st.write(f"**Fecha Fin:** {grupo_fin.get('fecha_fin', '')}")
                    with col2:
                        st.write(f"**Estado:** {grupo_fin.get('estado', '')}")
                        st.write(f"**Modalidad:** {grupo_fin.get('modalidad', '')}")
                
                # Obtener participantes con resultados
                try:
                    participantes_fin = supabase.table("participantes").select("*").eq("grupo_id", grupo_fin['id']).execute().data or []
                    
                    # Contar participantes por resultado
                    aptos = len([p for p in participantes_fin if p.get('resultado') == 'APTO'])
                    no_aptos = len([p for p in participantes_fin if p.get('resultado') == 'NO APTO'])
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Participantes", len(participantes_fin))
                    with col2:
                        st.metric("✅ Aptos", aptos)
                    with col3:
                        st.metric("❌ No Aptos", no_aptos)
                except:
                    participantes_fin = []
                
                # Validaciones
                if not participantes_fin:
                    st.warning("⚠️ El grupo no tiene participantes")
                elif grupo_fin.get('estado') != 'finalizado':
                    st.warning("⚠️ El grupo debe estar en estado 'finalizado'")
                else:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🔧 Generar XML Finalización", type="primary", use_container_width=True):
                            with st.spinner("Generando XML de finalización..."):
                                try:
                                    # Generar XML de finalización
                                    xml_content = generar_xml_finalizacion_grupo(grupo_fin, participantes_fin)
                                    
                                    if xml_content:
                                        # Validar contra XSD
                                        es_valido, errores = validar_xml(xml_content, xsd_urls['finalizacion_grupo'])
                                        
                                        if es_valido:
                                            st.success("✅ XML de finalización generado y validado")
                                            
                                            # Botón de descarga
                                            st.download_button(
                                                label="📥 Descargar XML Finalización",
                                                data=xml_content,
                                                file_name=f"FG_{grupo_fin['codigo_grupo']}_{datetime.now().strftime('%Y%m%d')}.xml",
                                                mime="application/xml"
                                            )
                                            
                                            # Guardar en historial
                                            try:
                                                supabase.table("documentos_generados").insert({
                                                    "tipo": "XML_FINALIZACION_GRUPO",
                                                    "referencia": grupo_fin['codigo_grupo'],
                                                    "empresa_id": empresa_id,
                                                    "usuario_id": session_state.get("user_id"),
                                                    "validado": True
                                                }).execute()
                                            except:
                                                pass
                                        else:
                                            st.error("❌ El XML no es válido")
                                            for error in errores[:5]:
                                                st.error(f"• {error}")
                                    else:
                                        st.error("Error al generar el XML")
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
                    
                    with col2:
                        if st.button("👁️ Vista previa", use_container_width=True):
                            try:
                                xml_preview = generar_xml_finalizacion_grupo(grupo_fin, participantes_fin)
                                if xml_preview:
                                    st.code(xml_preview[:1000] + "...", language="xml")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
        else:
            st.info("No hay grupos disponibles para finalizar")
    
    # =========================
    # TAB 4: GENERACIÓN DE PDFs
    # =========================
    with tab4:
        st.subheader("📄 Generar PDFs")
        st.caption("Genera documentos PDF para acciones formativas y grupos")
        
        tipo_pdf = st.radio(
            "Selecciona el tipo de PDF:",
            ["Acción Formativa", "Grupo", "Participantes"]
        )
        
        if tipo_pdf == "Acción Formativa" and acciones:
            accion_pdf = st.selectbox(
                "Selecciona la acción:",
                options=[f"{a['codigo']} - {a['denominacion']}" for a in acciones]
            )
            
            if st.button("📄 Generar PDF Acción", type="primary"):
                with st.spinner("Generando PDF..."):
                    try:
                        # Obtener la acción seleccionada
                        accion_data = next((a for a in acciones if f"{a['codigo']} - {a['denominacion']}" == accion_pdf), None)
                        
                        if accion_data:
                            pdf_content = generar_pdf(accion_data, tipo="accion_formativa")
                            
                            if pdf_content:
                                st.success("✅ PDF generado correctamente")
                                st.download_button(
                                    label="📥 Descargar PDF",
                                    data=pdf_content,
                                    file_name=f"AF_{accion_data['codigo']}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf"
                                )
                    except Exception as e:
                        st.error(f"Error al generar PDF: {str(e)}")
        
        elif tipo_pdf == "Grupo" and grupos:
            grupo_pdf = st.selectbox(
                "Selecciona el grupo:",
                options=[f"{g['codigo_grupo']} - {g.get('denominacion', '')}" for g in grupos]
            )
            
            if st.button("📄 Generar PDF Grupo", type="primary"):
                with st.spinner("Generando PDF..."):
                    try:
                        # Obtener el grupo seleccionado
                        grupo_data = next((g for g in grupos if f"{g['codigo_grupo']} - {g.get('denominacion', '')}" == grupo_pdf), None)
                        
                        if grupo_data:
                            # Obtener participantes
                            participantes_grupo = supabase.table("participantes").select("*").eq("grupo_id", grupo_data['id']).execute().data or []
                            
                            pdf_content = generar_pdf(
                                {"grupo": grupo_data, "participantes": participantes_grupo},
                                tipo="grupo"
                            )
                            
                            if pdf_content:
                                st.success("✅ PDF generado correctamente")
                                st.download_button(
                                    label="📥 Descargar PDF",
                                    data=pdf_content,
                                    file_name=f"Grupo_{grupo_data['codigo_grupo']}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf"
                                )
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        
        elif tipo_pdf == "Participantes" and grupos:
            grupo_part = st.selectbox(
                "Selecciona el grupo:",
                options=[f"{g['codigo_grupo']} - {g.get('denominacion', '')}" for g in grupos],
                key="grupo_participantes_pdf"
            )
            
            if st.button("📄 Generar Lista Participantes", type="primary"):
                with st.spinner("Generando PDF..."):
                    try:
                        grupo_data = next((g for g in grupos if f"{g['codigo_grupo']} - {g.get('denominacion', '')}" == grupo_part), None)
                        
                        if grupo_data:
                            participantes = supabase.table("participantes").select("*").eq("grupo_id", grupo_data['id']).execute().data or []
                            
                            if participantes:
                                pdf_content = generar_pdf(
                                    {"grupo": grupo_data, "participantes": participantes},
                                    tipo="lista_participantes"
                                )
                                
                                if pdf_content:
                                    st.success("✅ PDF generado")
                                    st.download_button(
                                        label="📥 Descargar Lista",
                                        data=pdf_content,
                                        file_name=f"Participantes_{grupo_data['codigo_grupo']}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                        mime="application/pdf"
                                    )
                            else:
                                st.warning("El grupo no tiene participantes")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
    
    # =========================
    # TAB 5: HISTORIAL
    # =========================
    with tab5:
        st.subheader("📊 Historial de Documentos Generados")
        
        if historial:
            df_historial = pd.DataFrame(historial)
            
            # Formatear columnas
            if 'created_at' in df_historial.columns:
                df_historial['Fecha'] = pd.to_datetime(df_historial['created_at']).dt.strftime('%d/%m/%Y %H:%M')
            
            # Mostrar tabla
            columnas_mostrar = ['Fecha', 'tipo', 'referencia', 'validado']
            columnas_disponibles = [c for c in columnas_mostrar if c in df_historial.columns]
            
            if columnas_disponibles:
                st.dataframe(
                    df_historial[columnas_disponibles],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Exportar
                export_csv(df_historial, "historial_documentos.csv")
            else:
                st.info("No hay historial disponible")
        else:
            st.info("No hay documentos generados todavía")
