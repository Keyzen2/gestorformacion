import streamlit as st
import pandas as pd
from xml.etree.ElementTree import Element, SubElement, tostring
from utils import generar_pdf, generar_xml_accion_formativa, generar_xml_inicio_grupo, generar_xml_finalizacion_grupo, validar_xml
from datetime import datetime

# =========================
# Interfaz principal
# =========================

def main(supabase, session_state):
    st.subheader("📄 Documentos")
    st.caption("Generación de documentos PDF y XML para acciones formativas y grupos.")
    st.divider()

    # 🔒 Protección por rol
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # Cargar acciones formativas
    try:
        if session_state.role == "gestor":
            empresa_id_usuario = session_state.user.get("empresa_id")
            grupos_empresa = supabase.table("grupos").select("accion_formativa_id").eq("empresa_id", empresa_id_usuario).execute()
            ids_acciones_permitidas = list({g["accion_formativa_id"] for g in grupos_empresa.data})
            acciones_res = supabase.table("acciones_formativas").select("id, nombre").in_("id", ids_acciones_permitidas).execute()
        else:
            acciones_res = supabase.table("acciones_formativas").select("id, nombre").execute()
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las acciones formativas: {e}")
        acciones_res = {"data": []}

    acciones_dict = {a["nombre"]: a["id"] for a in acciones_res.data} if acciones_res.data else {}
    accion_nombre = st.selectbox("Selecciona Acción Formativa", options=list(acciones_dict.keys()) if acciones_dict else ["No hay acciones"])
    accion_id = acciones_dict.get(accion_nombre) if acciones_dict else None

    # Cargar grupos asociados
    grupos_dict = {}
    try:
        if accion_id:
            if session_state.role == "gestor":
                grupos_res = supabase.table("grupos").select("id, codigo_grupo").eq("accion_formativa_id", accion_id).eq("empresa_id", empresa_id_usuario).execute()
            else:
                grupos_res = supabase.table("grupos").select("id, codigo_grupo").eq("accion_formativa_id", accion_id).execute()
            grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data} if grupos_res.data else {}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos: {e}")

    grupo_nombre = st.selectbox("Selecciona Grupo", options=list(grupos_dict.keys()) if grupos_dict else ["No hay grupos"])
    grupo_id = grupos_dict.get(grupo_nombre) if grupos_dict else None

    st.divider()
    st.markdown("### 🧾 Generar Documentos")

    if accion_id:
        if st.button("📄 Generar PDF"):
            pdf_buffer = generar_pdf(f"{accion_nombre}.pdf", contenido=f"PDF de {accion_nombre}")
            st.download_button("⬇️ Descargar PDF", pdf_buffer, file_name=f"{accion_nombre}.pdf")

        if st.button("📤 Generar XML de Acción Formativa"):
            xml_bytes = generar_xml_accion_formativa(supabase, accion_id)
            st.download_button("⬇️ Descargar XML", xml_bytes, file_name=f"{accion_nombre}_accion_formativa.xml")

        if grupo_id:
            if st.button("📤 Generar XML de Inicio de Grupo"):
                xml_bytes = generar_xml_inicio_grupo(supabase, grupo_id)
                st.download_button("⬇️ Descargar XML Inicio Grupo", xml_bytes, file_name=f"{grupo_nombre}_inicio_grupo.xml")

            if st.button("📤 Generar XML de Finalización de Grupo"):
                xml_bytes = generar_xml_finalizacion_grupo(supabase, grupo_id)
                st.download_button("⬇️ Descargar XML Finalización Grupo", xml_bytes, file_name=f"{grupo_nombre}_finalizacion_grupo.xml")

