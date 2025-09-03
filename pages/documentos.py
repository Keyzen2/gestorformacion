import streamlit as st
import pandas as pd
from utils import generar_pdf, generar_xml_accion_formativa, generar_xml_inicio_grupo, generar_xml_finalizacion_grupo

def main(supabase, session_state):
    st.subheader("Documentos")
    acciones_res = supabase.table("acciones_formativas").select("id, nombre").execute()
    acciones_dict = {a["nombre"]: a["id"] for a in acciones_res.data} if acciones_res.data else {}
    accion_nombre = st.selectbox("Selecciona Acción Formativa", options=list(acciones_dict.keys()) if acciones_dict else ["No hay acciones"])
    accion_id = acciones_dict.get(accion_nombre) if acciones_dict else None

    if accion_id:
        if st.button("Generar PDF"):
            pdf_buffer = generar_pdf(f"{accion_nombre}.pdf", contenido=f"PDF de {accion_nombre}")
            st.download_button("Descargar PDF", pdf_buffer, file_name=f"{accion_nombre}.pdf")

        if st.button("Generar XML de Acción Formativa"):
            xml_string = generar_xml_accion_formativa(accion_id)
            st.download_button("Descargar XML", xml_string, file_name=f"{accion_nombre}.xml")

        if st.button("Generar XML de Inicio de Grupo"):
            xml_string = generar_xml_inicio_grupo(accion_id)
            st.download_button("Descargar XML Inicio Grupo", xml_string, file_name=f"{accion_nombre}_inicio_grupo.xml")

        if st.button("Generar XML de Finalización de Grupo"):
            xml_string = generar_xml_finalizacion_grupo(accion_id)
            st.download_button("Descargar XML Finalización Grupo", xml_string, file_name=f"{accion_nombre}_finalizacion_grupo.xml")
