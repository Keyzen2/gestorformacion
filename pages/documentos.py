import streamlit as st
import pandas as pd
import requests
from utils import (
    generar_pdf,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo,
    validar_xml
)
from datetime import datetime

def main(supabase, session_state):
    st.subheader("📄 Documentos")
    st.caption("Generación de documentos PDF y XML para acciones formativas y grupos.")
    st.divider()

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # Cargar acciones formativas
    try:
        if session_state.role == "gestor":
            empresa_id_usuario = session_state.user.get("empresa_id")
            grupos_empresa = supabase.table("grupos").select("accion_formativa_id").eq("empresa_id", empresa_id_usuario).execute()
            ids_acciones_permitidas = list({g["accion_formativa_id"] for g in grupos_empresa.data})
            acciones_res = supabase.table("acciones_formativas").select("*").in_("id", ids_acciones_permitidas).execute()
        else:
            acciones_res = supabase.table("acciones_formativas").select("*").execute()
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las acciones formativas: {e}")
        acciones_res = {"data": []}

    acciones_dict = {a["nombre"]: a["id"] for a in acciones_res.data} if acciones_res.data else {}
    accion_nombre = st.selectbox("Selecciona Acción Formativa", options=list(acciones_dict.keys()) if acciones_dict else ["No hay acciones"])
    accion_id = acciones_dict.get(accion_nombre) if acciones_dict else None
    accion = next((a for a in acciones_res.data if a["id"] == accion_id), None)

    # Cargar grupos asociados
    grupos_dict = {}
    grupo = None
    try:
        if accion_id:
            if session_state.role == "gestor":
                grupos_res = supabase.table("grupos").select("*").eq("accion_formativa_id", accion_id).eq("empresa_id", empresa_id_usuario).execute()
            else:
                grupos_res = supabase.table("grupos").select("*").eq("accion_formativa_id", accion_id).execute()
            grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data} if grupos_res.data else {}
            grupo_nombre = st.selectbox("Selecciona Grupo", options=list(grupos_dict.keys()) if grupos_dict else ["No hay grupos"])
            grupo_id = grupos_dict.get(grupo_nombre)
            grupo = next((g for g in grupos_res.data if g["id"] == grupo_id), None)
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos: {e}")

    st.divider()
    st.markdown("### 🧾 Generar Documentos")

    if accion:
        if st.button("📄 Generar PDF"):
            contenido = f"""
            Acción Formativa: {accion['nombre']}
            Código: {accion['codigo_accion']}
            Modalidad: {accion.get('modalidad', 'No especificada')}
            Nivel: {accion.get('nivel', 'No especificado')}
            Duración: {accion.get('num_horas', '0')} horas
            Fecha de generación: {datetime.today().strftime('%d/%m/%Y')}
            """
            pdf_buffer = generar_pdf(f"{accion['nombre']}.pdf", contenido=contenido)
            if pdf_buffer:
                st.download_button(
                    "⬇️ Descargar PDF",
                    pdf_buffer.getvalue(),
                    file_name=f"{accion['codigo_accion']}_accion_formativa.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("❌ No se pudo generar el PDF.")

        if st.button("📤 Generar XML de Acción Formativa"):
            xml_str = generar_xml_accion_formativa(accion)
            xsd_url = st.secrets["FUNDAE"]["xsd_accion_formativa"]
            xsd_string = requests.get(xsd_url).text
            if not xsd_string:
                st.error("❌ No se pudo cargar el esquema XSD de Fundae.")
            elif validar_xml(xml_str, xsd_string):
                st.download_button(
                    "⬇️ Descargar XML Acción Formativa",
                    xml_str.encode("utf-8"),
                    file_name=f"{accion['codigo_accion']}_accion_formativa.xml",
                    mime="application/xml"
                )
            else:
                st.error("❌ El XML no cumple con el esquema oficial de Fundae.")

        if grupo:
            if st.button("📤 Generar XML de Inicio de Grupo"):
                xml_str = generar_xml_inicio_grupo(grupo)
                xsd_url = st.secrets["FUNDAE"]["xsd_inicio_grupo"]
                xsd_string = requests.get(xsd_url).text
                if not xsd_string:
                    st.error("❌ No se pudo cargar el esquema XSD de Fundae.")
                elif validar_xml(xml_str, xsd_string):
                    st.download_button(
                        "⬇️ Descargar XML Inicio Grupo",
                        xml_str.encode("utf-8"),
                        file_name=f"{grupo['codigo_grupo']}_inicio_grupo.xml",
                        mime="application/xml"
                    )
                else:
                    st.error("❌ El XML de inicio de grupo no cumple con el esquema oficial.")

            if st.button("📤 Generar XML de Finalización de Grupo"):
                xml_str = generar_xml_finalizacion_grupo(grupo)
                xsd_url = st.secrets["FUNDAE"]["xsd_finalizacion_grupo"]
                xsd_string = requests.get(xsd_url).text
                if not xsd_string:
                    st.error("❌ No se pudo cargar el esquema XSD de Fundae.")
                elif validar_xml(xml_str, xsd_string):
                    st.download_button(
                        "⬇️ Descargar XML Finalización Grupo",
                        xml_str.encode("utf-8"),
                        file_name=f"{grupo['codigo_grupo']}_finalizacion_grupo.xml",
                        mime="application/xml"
                    )
                else:
                    st.error("❌ El XML de finalización de grupo no cumple con el esquema oficial.")
                    
