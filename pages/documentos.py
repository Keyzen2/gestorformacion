import streamlit as st
import pandas as pd
from xml.etree.ElementTree import Element, SubElement, tostring
from utils import generar_pdf

# =========================
# Generadores XML FUNDAE
# =========================

def generar_xml_accion_formativa(supabase, accion_id):
    accion = supabase.table("acciones_formativas").select("*").eq("id", accion_id).execute().data[0]

    root = Element("ACCIONES_FORMATIVAS")
    accion_tag = SubElement(root, "ACCION_FORMATIVA")
    # Usamos el código de acción que guardas en la tabla, no el id interno
    SubElement(accion_tag, "CODIGO_ACCION").text = accion.get("codigo_accion", "")
    SubElement(accion_tag, "NOMBRE_ACCION").text = accion.get("nombre", "")
    # Aquí el cambio clave: código oficial del área profesional
    SubElement(accion_tag, "CODIGO_AREA_PROFESIONAL").text = accion.get("cod_area_profesional", "")
    SubElement(accion_tag, "SECTOR").text = accion.get("sector", "")
    SubElement(accion_tag, "OBJETIVOS").text = accion.get("objetivos", "")
    SubElement(accion_tag, "CONTENIDOS").text = accion.get("contenidos", "")
    SubElement(accion_tag, "MODALIDAD").text = accion.get("modalidad", "")
    SubElement(accion_tag, "NIVEL").text = accion.get("nivel", "")
    # Ajuste: usamos num_horas que es como lo guardas en acciones_formativas.py
    SubElement(accion_tag, "DURACION").text = str(accion.get("num_horas", ""))
    # Ajuste: usamos certificado_profesionalidad (booleano) para generar S/N
    SubElement(accion_tag, "CERTIFICADO_PROFESIONALIDAD").text = "S" if accion.get("certificado_profesionalidad") else "N"

    return tostring(root, encoding="utf-8", xml_declaration=True)

def generar_xml_inicio_grupo(supabase, grupo_id):
    grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
    accion = supabase.table("acciones_formativas").select("nombre, codigo_accion").eq("id", grupo["accion_formativa_id"]).execute().data[0]

    root = Element("INICIO_GRUPOS")
    grupo_tag = SubElement(root, "GRUPO")
    SubElement(grupo_tag, "CODIGO_GRUPO").text = grupo.get("codigo_grupo", "")
    SubElement(grupo_tag, "CODIGO_ACCION").text = accion.get("codigo_accion", "")
    SubElement(grupo_tag, "NOMBRE_ACCION").text = accion.get("nombre", "")
    SubElement(grupo_tag, "FECHA_INICIO").text = str(grupo.get("fecha_inicio", ""))
    SubElement(grupo_tag, "FECHA_FIN").text = str(grupo.get("fecha_fin", ""))
    SubElement(grupo_tag, "HORARIO").text = grupo.get("horario", "")
    SubElement(grupo_tag, "LOCALIDAD").text = grupo.get("localidad", "")
    SubElement(grupo_tag, "PROVINCIA").text = grupo.get("provincia", "")
    SubElement(grupo_tag, "CODIGO_POSTAL").text = grupo.get("cp", "")
    SubElement(grupo_tag, "PARTICIPANTES_PREVISTOS").text = str(grupo.get("n_participantes_previstos", ""))

    return tostring(root, encoding="utf-8", xml_declaration=True)

def generar_xml_finalizacion_grupo(supabase, grupo_id):
    grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
    accion = supabase.table("acciones_formativas").select("nombre, codigo_accion").eq("id", grupo["accion_formativa_id"]).execute().data[0]

    root = Element("FINALIZACION_GRUPOS")
    grupo_tag = SubElement(root, "GRUPO")
    SubElement(grupo_tag, "CODIGO_GRUPO").text = grupo.get("codigo_grupo", "")
    SubElement(grupo_tag, "CODIGO_ACCION").text = accion.get("codigo_accion", "")
    SubElement(grupo_tag, "NOMBRE_ACCION").text = accion.get("nombre", "")
    SubElement(grupo_tag, "FECHA_FIN").text = str(grupo.get("fecha_fin", ""))
    SubElement(grupo_tag, "PARTICIPANTES_FINALIZADOS").text = str(grupo.get("n_participantes_finalizados", ""))
    SubElement(grupo_tag, "APTOS").text = str(grupo.get("n_aptos", ""))
    SubElement(grupo_tag, "NO_APTOS").text = str(grupo.get("n_no_aptos", ""))
    SubElement(grupo_tag, "OBSERVACIONES").text = grupo.get("observaciones", "")

    return tostring(root, encoding="utf-8", xml_declaration=True)

# =========================
# Interfaz principal
# =========================

def main(supabase, session_state):
    st.subheader("📄 Documentos")

    # Cargar acciones formativas
    if session_state.role == "gestor":
        empresa_id_usuario = session_state.user.get("empresa_id")
        grupos_empresa = supabase.table("grupos").select("accion_formativa_id").eq("empresa_id", empresa_id_usuario).execute()
        ids_acciones_permitidas = list({g["accion_formativa_id"] for g in grupos_empresa.data})
        acciones_res = supabase.table("acciones_formativas").select("id, nombre").in_("id", ids_acciones_permitidas).execute()
    else:
        acciones_res = supabase.table("acciones_formativas").select("id, nombre").execute()

    acciones_dict = {a["nombre"]: a["id"] for a in acciones_res.data} if acciones_res.data else {}
    accion_nombre = st.selectbox("Selecciona Acción Formativa", options=list(acciones_dict.keys()) if acciones_dict else ["No hay acciones"])
    accion_id = acciones_dict.get(accion_nombre) if acciones_dict else None

    # Cargar grupos asociados
    grupos_dict = {}
    if accion_id:
        if session_state.role == "gestor":
            empresa_id_usuario = session_state.user.get("empresa_id")
            grupos_res = supabase.table("grupos").select("id, codigo_grupo").eq("accion_formativa_id", accion_id).eq("empresa_id", empresa_id_usuario).execute()
        else:
            grupos_res = supabase.table("grupos").select("id, codigo_grupo").eq("accion_formativa_id", accion_id).execute()

        grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data} if grupos_res.data else {}

    grupo_nombre = st.selectbox("Selecciona Grupo", options=list(grupos_dict.keys()) if grupos_dict else ["No hay grupos"])
    grupo_id = grupos_dict.get(grupo_nombre) if grupos_dict else None

    # Botones de generación
    if accion_id:
        if st.button("Generar PDF"):
            pdf_buffer = generar_pdf(f"{accion_nombre}.pdf", contenido=f"PDF de {accion_nombre}")
            st.download_button("Descargar PDF", pdf_buffer, file_name=f"{accion_nombre}.pdf")

        if st.button("Generar XML de Acción Formativa"):
            xml_bytes = generar_xml_accion_formativa(supabase, accion_id)
            st.download_button("Descargar XML", xml_bytes, file_name=f"{accion_nombre}_accion_formativa.xml")

        if grupo_id:
            if st.button("Generar XML de Inicio de Grupo"):
                xml_bytes = generar_xml_inicio_grupo(supabase, grupo_id)
                st.download_button("Descargar XML Inicio Grupo", xml_bytes, file_name=f"{grupo_nombre}_inicio_grupo.xml")

            if st.button("Generar XML de Finalización de Grupo"):
                xml_bytes = generar_xml_finalizacion_grupo(supabase, grupo_id)
                st.download_button("Descargar XML Finalización Grupo", xml_bytes, file_name=f"{grupo_nombre}_finalizacion_grupo.xml")

