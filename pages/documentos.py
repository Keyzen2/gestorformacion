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

def main(supabase, session_state):
    st.subheader("📄 Gestión de Documentos")
    st.caption("Generación de documentos PDF y XML para acciones formativas y grupos según normativa FUNDAE.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # =========================
    # Cargar configuración XSD
    # =========================
    try:
        FUNDAE = st.secrets["FUNDAE"]
        xsd_accion = FUNDAE["xsd_accion_formativa"]
        xsd_inicio = FUNDAE["xsd_inicio_grupo"]
        xsd_finalizacion = FUNDAE["xsd_finalizacion_grupo"]
    except Exception as e:
        st.error(f"❌ Error al cargar configuración FUNDAE: {e}")
        st.info("💡 Verifica que las URLs XSD estén configuradas en los secrets de Streamlit.")
        return

    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar datos con mejoras
    # =========================
    try:
        # Cargar acciones formativas según rol
        if session_state.role == "gestor":
            # Gestor: solo acciones de grupos de su empresa
            grupos_empresa = supabase.table("grupos")\
                .select("accion_formativa_id")\
                .eq("empresa_id", empresa_id)\
                .execute().data or []
            
            ids_acciones = list({g["accion_formativa_id"] for g in grupos_empresa if g.get("accion_formativa_id")})
            
            if ids_acciones:
                acciones_res = supabase.table("acciones_formativas")\
                    .select("*")\
                    .in_("id", ids_acciones)\
                    .execute()
            else:
                acciones_res = {"data": []}
        else:
            # Admin: todas las acciones
            acciones_res = supabase.table("acciones_formativas").select("*").execute()
            
        acciones_data = acciones_res.data or []
        
    except Exception as e:
        st.error(f"⚠️ Error al cargar acciones formativas: {e}")
        acciones_data = []

    # =========================
    # Métricas
    # =========================
    if acciones_data:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📚 Acciones Disponibles", len(acciones_data))
        
        with col2:
            # Contar grupos asociados
            try:
                if session_state.role == "gestor":
                    grupos_count = len(supabase.table("grupos").select("id").eq("empresa_id", empresa_id).execute().data or [])
                else:
                    grupos_count = len(supabase.table("grupos").select("id").execute().data or [])
                st.metric("👥 Grupos Totales", grupos_count)
            except Exception:
                st.metric("👥 Grupos Totales", 0)
        
        with col3:
            # Documentos generados hoy
            try:
                hoy = datetime.today().strftime("%Y-%m-%d")
                docs_hoy = len(supabase.table("documentos").select("id").gte("created_at", hoy).execute().data or [])
                st.metric("📄 Docs Hoy", docs_hoy)
            except Exception:
                st.metric("📄 Docs Hoy", 0)

    st.divider()

    # =========================
    # Selección de acción formativa
    # =========================
    st.markdown("### 🎯 Selección de Acción Formativa")
    
    if not acciones_data:
        st.warning("⚠️ No hay acciones formativas disponibles para generar documentos.")
        if session_state.role == "gestor":
            st.info("💡 Asegúrate de que tu empresa tenga grupos con acciones formativas asignadas.")
        return

    # Crear diccionario con información más descriptiva
    acciones_options = {}
    for accion in acciones_data:
        label = f"{accion['codigo_accion']} - {accion['nombre']} ({accion.get('modalidad', 'Sin modalidad')})"
        acciones_options[label] = accion

    accion_seleccionada = st.selectbox(
        "🔍 Selecciona una acción formativa:",
        options=list(acciones_options.keys()),
        help="Elige la acción formativa para la cual generar documentos"
    )

    accion = acciones_options.get(accion_seleccionada)

    if not accion:
        st.info("👆 Selecciona una acción formativa para continuar.")
        return

    # Mostrar información de la acción seleccionada
    with st.expander("ℹ️ Información de la acción seleccionada"):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Código:** {accion.get('codigo_accion', 'N/A')}")
            st.write(f"**Modalidad:** {accion.get('modalidad', 'No especificada')}")
            st.write(f"**Nivel:** {accion.get('nivel', 'No especificado')}")
        with col2:
            st.write(f"**Duración:** {accion.get('num_horas', 0)} horas")
            st.write(f"**Certificado Prof.:** {'Sí' if accion.get('certificado_profesionalidad') else 'No'}")
            st.write(f"**Área:** {accion.get('area_profesional', 'No especificada')}")

    # =========================
    # Selección de grupo
    # =========================
    st.markdown("### 👥 Selección de Grupo (Opcional)")
    
    try:
        # Cargar grupos de la acción seleccionada según rol
        if session_state.role == "gestor":
            grupos_res = supabase.table("grupos")\
                .select("*")\
                .eq("empresa_id", empresa_id)\
                .eq("accion_formativa_id", accion["id"])\
                .execute()
        else:
            grupos_res = supabase.table("grupos")\
                .select("*")\
                .eq("accion_formativa_id", accion["id"])\
                .execute()
        
        grupos_data = grupos_res.data or []
        
    except Exception as e:
        st.error(f"⚠️ Error al cargar grupos: {e}")
        grupos_data = []

    grupo = None
    if grupos_data:
        # Crear opciones más descriptivas para grupos
        grupos_options = {"Ninguno (solo acción formativa)": None}
        for g in grupos_data:
            fecha_inicio = g.get('fecha_inicio', 'Sin fecha')
            estado = "🟢 Activo" if g.get('fecha_fin_prevista') and pd.to_datetime(g['fecha_fin_prevista']).date() >= datetime.today().date() else "🔴 Finalizado"
            label = f"{g['codigo_grupo']} - {fecha_inicio} ({estado})"
            grupos_options[label] = g

        grupo_seleccionado = st.selectbox(
            "🔍 Selecciona un grupo (opcional):",
            options=list(grupos_options.keys()),
            help="Selecciona un grupo para generar documentos específicos del grupo"
        )

        grupo = grupos_options.get(grupo_seleccionado)
        
        if grupo:
            # Mostrar información del grupo
            with st.expander("ℹ️ Información del grupo seleccionado"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Código:** {grupo.get('codigo_grupo')}")
                    st.write(f"**Fecha inicio:** {grupo.get('fecha_inicio', 'No definida')}")
                    st.write(f"**Fecha fin:** {grupo.get('fecha_fin_prevista', 'No definida')}")
                with col2:
                    st.write(f"**Localidad:** {grupo.get('localidad', 'No especificada')}")
                    st.write(f"**Participantes previstos:** {grupo.get('n_participantes_previstos', 0)}")
                    st.write(f"**Aula virtual:** {'Sí' if grupo.get('aula_virtual') else 'No'}")
    else:
        st.info("ℹ️ No hay grupos disponibles para esta acción formativa.")

    st.divider()

    # =========================
    # Generación de documentos
    # =========================
    st.markdown("### 🧾 Generar Documentos")

    # Organizar botones en columnas
    col1, col2 = st.columns(2)

    # 1) Generar PDF de Acción Formativa
    with col1:
        st.markdown("#### 📄 Documentos PDF")
        
        if st.button("📄 Generar PDF Acción Formativa", use_container_width=True):
            try:
                # Crear contenido más completo para el PDF
                contenido_lineas = [
                    f"ACCIÓN FORMATIVA - {accion['codigo_accion']}",
                    "",
                    f"Nombre: {accion['nombre']}",
                    f"Código: {accion['codigo_accion']}",
                    f"Modalidad: {accion.get('modalidad', 'No especificada')}",
                    f"Nivel: {accion.get('nivel', 'No especificado')}",
                    f"Duración: {accion.get('num_horas', 0)} horas",
                    f"Área profesional: {accion.get('area_profesional', 'No especificada')}",
                    f"Certificado de profesionalidad: {'Sí' if accion.get('certificado_profesionalidad') else 'No'}",
                    "",
                    f"Objetivos:",
                    f"{accion.get('objetivos', 'No especificados')}",
                    "",
                    f"Contenidos:",
                    f"{accion.get('contenidos', 'No especificados')}",
                    "",
                    f"Fecha de generación: {datetime.today().strftime('%d/%m/%Y %H:%M')}"
                ]
                
                contenido = "\n".join(contenido_lineas)
                encabezado = f"ACCIÓN FORMATIVA - {accion['codigo_accion']}"
                
                pdf_buffer = generar_pdf(
                    nombre_archivo=f"{accion['codigo_accion']}_accion_formativa.pdf",
                    contenido=contenido,
                    encabezado=encabezado
                )
                
                if pdf_buffer:
                    st.download_button(
                        "⬇️ Descargar PDF Acción Formativa",
                        data=pdf_buffer.getvalue(),
                        file_name=f"{accion['codigo_accion']}_accion_formativa_{datetime.today().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                    st.success("✅ PDF generado correctamente")
                else:
                    st.error("❌ Error al generar el PDF")
                    
            except Exception as e:
                st.error(f"❌ Error al generar PDF: {e}")

        # PDF de grupo si está seleccionado
        if grupo and st.button("📄 Generar PDF Grupo", use_container_width=True):
            try:
                # Cargar participantes del grupo
                participantes_res = supabase.table("participantes_grupos")\
                    .select("participante_id")\
                    .eq("grupo_id", grupo["id"])\
                    .execute()
                
                participantes_ids = [p["participante_id"] for p in (participantes_res.data or [])]
                participantes_count = len(participantes_ids)
                
                contenido_grupo = [
                    f"GRUPO - {grupo['codigo_grupo']}",
                    "",
                    f"Código del grupo: {grupo['codigo_grupo']}",
                    f"Acción formativa: {accion['nombre']}",
                    f"Fecha de inicio: {grupo.get('fecha_inicio', 'No definida')}",
                    f"Fecha de fin prevista: {grupo.get('fecha_fin_prevista', 'No definida')}",
                    f"Localidad: {grupo.get('localidad', 'No especificada')}",
                    f"Provincia: {grupo.get('provincia', 'No especificada')}",
                    f"Participantes previstos: {grupo.get('n_participantes_previstos', 0)}",
                    f"Participantes inscritos: {participantes_count}",
                    f"Aula virtual: {'Sí' if grupo.get('aula_virtual') else 'No'}",
                    "",
                    f"Observaciones:",
                    f"{grupo.get('observaciones', 'Sin observaciones')}",
                    "",
                    f"Fecha de generación: {datetime.today().strftime('%d/%m/%Y %H:%M')}"
                ]
                
                contenido = "\n".join(contenido_grupo)
                encabezado = f"GRUPO - {grupo['codigo_grupo']}"
                
                pdf_buffer = generar_pdf(
                    nombre_archivo=f"{grupo['codigo_grupo']}_grupo.pdf",
                    contenido=contenido,
                    encabezado=encabezado
                )
                
                if pdf_buffer:
                    st.download_button(
                        "⬇️ Descargar PDF Grupo",
                        data=pdf_buffer.getvalue(),
                        file_name=f"{grupo['codigo_grupo']}_grupo_{datetime.today().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                    st.success("✅ PDF de grupo generado correctamente")
                else:
                    st.error("❌ Error al generar el PDF del grupo")
                    
            except Exception as e:
                st.error(f"❌ Error al generar PDF del grupo: {e}")

    # 2) Generar XMLs FUNDAE
    with col2:
        st.markdown("#### 📤 Documentos XML FUNDAE")
        
        # XML de Acción Formativa
        if st.button("📤 XML Acción Formativa", use_container_width=True):
            try:
                with st.spinner("Generando XML de acción formativa..."):
                    xml_content = generar_xml_accion_formativa(accion)
                    
                    # Validar XML con XSD
                    if validar_xml(xml_content, xsd_url=xsd_accion):
                        st.download_button(
                            "⬇️ Descargar XML Acción",
                            data=xml_content.encode('utf-8'),
                            file_name=f"{accion['codigo_accion']}_accion_{datetime.today().strftime('%Y%m%d')}.xml",
                            mime="application/xml",
                            use_container_width=True
                        )
                        st.success("✅ XML de acción formativa generado y validado")
                    else:
                        st.error("❌ El XML generado no es válido según el esquema XSD")
                        
            except Exception as e:
                st.error(f"❌ Error al generar XML de acción formativa: {e}")
                st.caption("💡 Verifica que todos los campos obligatorios estén completos en la acción formativa")

        # XML de Inicio de Grupo
        if grupo and st.button("📤 XML Inicio Grupo", use_container_width=True):
            if not grupo.get("fecha_inicio") or not grupo.get("fecha_fin_prevista"):
                st.error("⚠️ El grupo debe tener fechas de inicio y fin previstas.")
            else:
                try:
                    with st.spinner("Generando XML de inicio de grupo..."):
                        # Cargar participantes del grupo
                        participantes_res = supabase.table("participantes_grupos")\
                            .select("participante_id")\
                            .eq("grupo_id", grupo["id"])\
                            .execute()
                        
                        participante_ids = [p["participante_id"] for p in (participantes_res.data or [])]
                        
                        if not participante_ids:
                            st.error("⚠️ No hay participantes asignados a este grupo.")
                        else:
                            # Cargar datos completos de participantes
                            participantes_data = supabase.table("participantes")\
                                .select("id, nombre, apellidos, email, dni")\
                                .in_("id", participante_ids)\
                                .execute().data or []
                            
                            xml_content = generar_xml_inicio_grupo(grupo, participantes_data)
                            
                            # Validar XML
                            if validar_xml(xml_content, xsd_url=xsd_inicio):
                                st.download_button(
                                    "⬇️ Descargar XML Inicio",
                                    data=xml_content.encode('utf-8'),
                                    file_name=f"{grupo['codigo_grupo']}_inicio_{datetime.today().strftime('%Y%m%d')}.xml",
                                    mime="application/xml",
                                    use_container_width=True
                                )
                                st.success("✅ XML de inicio de grupo generado y validado")
                            else:
                                st.error("❌ El XML generado no es válido según el esquema XSD")
                                
                except Exception as e:
                    st.error(f"❌ Error al generar XML de inicio: {e}")

        # XML de Finalización de Grupo
        if grupo and st.button("📤 XML Finalización Grupo", use_container_width=True):
            try:
                with st.spinner("Generando XML de finalización de grupo..."):
                    # Cargar datos completos del grupo
                    grupo_completo = supabase.table("grupos")\
                        .select("*")\
                        .eq("id", grupo["id"])\
                        .execute().data
                    
                    if not grupo_completo:
                        st.error("❌ No se pudieron cargar los datos del grupo")
                        return
                    
                    grupo_data = grupo_completo[0]
                    
                    # Cargar participantes
                    participantes_res = supabase.table("participantes_grupos")\
                        .select("participante_id")\
                        .eq("grupo_id", grupo["id"])\
                        .execute()
                    
                    participante_ids = [p["participante_id"] for p in (participantes_res.data or [])]
                    
                    participantes_data = []
                    if participante_ids:
                        participantes_data = supabase.table("participantes")\
                            .select("id, nombre, apellidos, email, dni")\
                            .in_("id", participante_ids)\
                            .execute().data or []
                    
                    xml_content = generar_xml_finalizacion_grupo(grupo_data, participantes_data)
                    
                    # Validar XML
                    if validar_xml(xml_content, xsd_url=xsd_finalizacion):
                        st.download_button(
                            "⬇️ Descargar XML Finalización",
                            data=xml_content.encode('utf-8'),
                            file_name=f"{grupo['codigo_grupo']}_finalizacion_{datetime.today().strftime('%Y%m%d')}.xml",
                            mime="application/xml",
                            use_container_width=True
                        )
                        st.success("✅ XML de finalización generado y validado")
                    else:
                        st.error("❌ El XML generado no es válido según el esquema XSD")
                        
            except Exception as e:
                st.error(f"❌ Error al generar XML de finalización: {e}")

    st.divider()

    # =========================
    # Historial de documentos generados
    # =========================
    st.markdown("### 📋 Historial de Documentos Generados")
    
    try:
        # Cargar documentos según el rol
        if session_state.role == "gestor":
            docs_res = supabase.table("documentos")\
                .select("*")\
                .eq("empresa_id", empresa_id)\
                .order("created_at", desc=True)\
                .limit(10)\
                .execute()
        else:
            docs_res = supabase.table("documentos")\
                .select("*")\
                .order("created_at", desc=True)\
                .limit(20)\
                .execute()
        
        docs_data = docs_res.data or []
        
        if docs_data:
            df_docs = pd.DataFrame(docs_data)
            
            # Mostrar tabla de documentos
            st.dataframe(
                df_docs[["tipo", "archivo_path", "created_at"]],
                column_config={
                    "tipo": "Tipo de Documento",
                    "archivo_path": "Archivo",
                    "created_at": "Fecha de Creación"
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Botón de exportación
            export_csv(df_docs, filename="historial_documentos.csv")
        else:
            st.info("ℹ️ No hay documentos generados en el historial.")
            
    except Exception as e:
        st.error(f"❌ Error al cargar historial de documentos: {e}")

    # =========================
    # Información adicional
    # =========================
    st.divider()
    
    with st.expander("ℹ️ Información sobre documentos FUNDAE"):
        st.markdown("""
        **Tipos de documentos disponibles:**
        
        📄 **PDF Acción Formativa**: Documento descriptivo con toda la información de la acción.
        
        📤 **XML Acción Formativa**: Archivo XML según esquema FUNDAE para registro de acciones.
        
        📤 **XML Inicio Grupo**: Documento para notificar el inicio de un grupo formativo.
        
        📤 **XML Finalización Grupo**: Documento para notificar la finalización y resultados de un grupo.
        
        **Validación XSD**: Todos los XMLs se validan automáticamente contra los esquemas oficiales de FUNDAE.
        """)

    st.caption("💡 Los documentos XML se generan según las especificaciones técnicas de FUNDAE y son validados automáticamente.")
    
