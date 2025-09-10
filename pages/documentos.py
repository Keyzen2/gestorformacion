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
    
    # Roles y empresa alineados con el resto de módulos
    empresa_id = session_state.user.get("empresa_id") if getattr(session_state, "user", None) else None
    user_role = getattr(session_state, "role", "alumno")
    
    xsd_urls = {
        'accion_formativa': st.secrets.get("FUNDAE", {}).get("xsd_accion_formativa"),
        'inicio_grupo': st.secrets.get("FUNDAE", {}).get("xsd_inicio_grupo"),
        'finalizacion_grupo': st.secrets.get("FUNDAE", {}).get("xsd_finalizacion_grupo")
    }
    
    if not all(xsd_urls.values()):
        st.error("⚠️ Faltan las URLs de los esquemas XSD en la configuración")
        st.info("Por favor, verifica que estén configuradas las URLs en los secrets de Streamlit")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        if user_role == "admin":
            acciones = supabase.table("acciones_formativas").select("*").execute().data or []
            grupos = supabase.table("grupos").select("*").execute().data or []
        elif user_role == "gestor" and empresa_id:
            acciones = supabase.table("acciones_formativas").select("*").eq("empresa_id", empresa_id).execute().data or []
            grupos = supabase.table("grupos").select("*").eq("empresa_id", empresa_id).execute().data or []
        else:
            st.warning("No tienes permisos para generar documentos")
            return
        
        try:
            historial = supabase.table("documentos_generados").select("*").order("created_at", desc=True).limit(10).execute().data or []
        except Exception:
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
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 XML Acción Formativa",
        "🚀 XML Inicio Grupo", 
        "🏁 XML Finalización Grupo",
        "📄 PDFs",
        "📊 Historial"
    ])
    
    # TAB 1: XML ACCIÓN FORMATIVA
    with tab1:
        st.subheader("📋 Generar XML de Acción Formativa")
        st.caption("Genera el XML de inicio de acción formativa para FUNDAE")
        
        if acciones:
            opciones_acciones = {f"{a.get('codigo','')} - {a.get('denominacion', a.get('nombre',''))}": a for a in acciones}
            accion_seleccionada = st.selectbox(
                "Selecciona la acción formativa:",
                options=list(opciones_acciones.keys()),
                help="Selecciona la acción formativa para generar su XML"
            )
            if accion_seleccionada:
                accion = opciones_acciones[accion_seleccionada]
                with st.expander("ℹ️ Información de la Acción Formativa", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Código:** {accion.get('codigo', accion.get('codigo_accion',''))}")
                        st.write(f"**Denominación:** {accion.get('denominacion', accion.get('nombre',''))}")
                        st.write(f"**Modalidad:** {accion.get('modalidad', '')}")
                    with col2:
                        st.write(f"**Horas:** {accion.get('horas', accion.get('num_horas',0))}")
                        st.write(f"**Área:** {accion.get('area_profesional', '')}")
                        st.write(f"**Fecha Inicio:** {accion.get('fecha_inicio', '')}")
                
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
                                    xml_content = generar_xml_accion_formativa(accion, namespace="http://www.fundae.es/esquemas")
                                    if xml_content:
                                        es_valido, errores = validar_xml(xml_content, xsd_urls['accion_formativa'])
                                        if es_valido:
                                            st.success("✅ XML generado y validado correctamente")
                                            st.download_button(
                                                label="📥 Descargar XML Acción Formativa",
                                                data=xml_content,
                                                file_name=f"AF_{accion.get('codigo', accion.get('codigo_accion','SIN_COD'))}_{datetime.now().strftime('%Y%m%d')}.xml",
                                                mime="application/xml"
                                            )
                                            try:
                                                supabase.table("documentos_generados").insert({
                                                    "tipo": "XML_ACCION_FORMATIVA",
                                                    "referencia": accion.get('codigo', accion.get('codigo_accion','')),
                                                    "empresa_id": empresa_id,
                                                    "usuario_id": session_state.user.get("id") if getattr(session_state, "user", None) else None,
                                                    "validado": True
                                                }).execute()
                                            except Exception:
                                                pass
                                        else:
                                            st.error("❌ El XML no es válido según el esquema XSD")
                                            for error in (errores[:5] if errores else []):
                                                st.error(f"• {error}")
                                            st.info("💡 Revisa que el namespace sea correcto y los campos cumplan con el esquema FUNDAE")
                                    else:
                                        st.error("Error al generar el XML")
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
                    with col2:
                        if st.button("👁️ Vista previa", use_container_width=True):
                            try:
                                xml_preview = generar_xml_accion_formativa(accion, namespace="http://www.fundae.es/esquemas")
                                st.code(xml_preview, language="xml")
                            except Exception as e:
                                st.error(f"Error al generar vista previa: {e}")
        else:
            st.info("ℹ️ No hay acciones formativas disponibles para generar XML.")
    
    # TAB 2: XML INICIO GRUPO
    with tab2:
        st.subheader("🚀 Generar XML de Inicio de Grupo")
        st.caption("Genera el XML de inicio de grupo para FUNDAE")
        
        if grupos:
            opciones_grupos = {f"{g.get('codigo_grupo','')} - {g.get('accion_formativa_id','')}": g for g in grupos}
            grupo_seleccionado = st.selectbox(
                "Selecciona el grupo:",
                options=list(opciones_grupos.keys())
            )
            if grupo_seleccionado:
                grupo = opciones_grupos[grupo_seleccionado]
                with st.expander("ℹ️ Información del Grupo", expanded=False):
                    st.write(grupo)
                
                if st.button("🔧 Generar XML Inicio Grupo", type="primary"):
                    with st.spinner("Generando XML..."):
                        try:
                            xml_content = generar_xml_inicio_grupo(grupo, namespace="http://www.fundae.es/esquemas")
                            if xml_content:
                                es_valido, errores = validar_xml(xml_content, xsd_urls['inicio_grupo'])
                                if es_valido:
                                    st.success("✅ XML generado y validado correctamente")
                                    st.download_button(
                                        label="📥 Descargar XML Inicio Grupo",
                                        data=xml_content,
                                        file_name=f"IG_{grupo.get('codigo_grupo','SIN_COD')}_{datetime.now().strftime('%Y%m%d')}.xml",
                                        mime="application/xml"
                                    )
                                else:
                                    st.error("❌ El XML no es válido según el esquema XSD")
                                    for error in (errores[:5] if errores else []):
                                        st.error(f"• {error}")
                            else:
                                st.error("Error al generar el XML")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        else:
            st.info("ℹ️ No hay grupos disponibles para generar XML.")
    
    # TAB 3: XML FINALIZACIÓN GRUPO
    with tab3:
        st.subheader("🏁 Generar XML de Finalización de Grupo")
        st.caption("Genera el XML de finalización de grupo para FUNDAE")
        
        if grupos:
            opciones_grupos = {f"{g.get('codigo_grupo','')} - {g.get('accion_formativa_id','')}": g for g in grupos}
            grupo_seleccionado = st.selectbox(
                "Selecciona el grupo:",
                options=list(opciones_grupos.keys()),
                key="finalizacion_grupo"
            )
            if grupo_seleccionado:
                grupo = opciones_grupos[grupo_seleccionado]
                with st.expander("ℹ️ Información del Grupo", expanded=False):
                    st.write(grupo)
                
                if st.button("🔧 Generar XML Finalización Grupo", type="primary"):
                    with st.spinner("Generando XML..."):
                        try:
                            xml_content = generar_xml_finalizacion_grupo(grupo, namespace="http://www.fundae.es/esquemas")
                            if xml_content:
                                es_valido, errores = validar_xml(xml_content, xsd_urls['finalizacion_grupo'])
                                if es_valido:
                                    st.success("✅ XML generado y validado correctamente")
                                    st.download_button(
                                        label="📥 Descargar XML Finalización Grupo",
                                        data=xml_content,
                                        file_name=f"FG_{grupo.get('codigo_grupo','SIN_COD')}_{datetime.now().strftime('%Y%m%d')}.xml",
                                        mime="application/xml"
                                    )
                                else:
                                    st.error("❌ El XML no es válido según el esquema XSD")
                                    for error in (errores[:5] if errores else []):
                                        st.error(f"• {error}")
                            else:
                                st.error("Error al generar el XML")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        else:
            st.info("ℹ️ No hay grupos disponibles para generar XML.")
    
    # TAB 4: PDFs
    with tab4:
        st.subheader("📄 Generar PDFs")
        st.caption("Genera documentos PDF oficiales para FUNDAE")
        
        tipo_pdf = st.selectbox("Selecciona el tipo de PDF", ["Acta de inicio", "Acta de finalización", "Lista de asistencia"])
        if tipo_pdf and st.button("Generar PDF", type="primary"):
            with st.spinner("Generando PDF..."):
                try:
                    pdf_content = generar_pdf(tipo_pdf)
                    if pdf_content:
                        st.download_button(
                            label=f"📥 Descargar {tipo_pdf}",
                            data=pdf_content,
                            file_name=f"{tipo_pdf.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("Error al generar el PDF")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    # TAB 5: Historial
    with tab5:
        st.subheader("📊 Historial de Documentos Generados")
        if historial:
            df_historial = pd.DataFrame(historial)
            export_csv(df_historial, filename="historial_documentos.csv")
            st.dataframe(df_historial)
        else:
            st.info("ℹ️ No hay historial de documentos generados.")
