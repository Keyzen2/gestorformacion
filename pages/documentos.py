import streamlit as st
import io
from utils import (
    generar_pdf,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo,
)

def main(supabase, session_state):
    st.subheader("Documentos")

    # 1. Obtener acciones formativas accesibles
    if session_state.role == "admin":
        acciones_res = supabase.table("acciones_formativas").select("id, nombre, empresa_id").execute()
    else:  # gestor -> solo las de su empresa
        acciones_res = supabase.table("acciones_formativas").select("id, nombre, empresa_id").eq("empresa_id", session_state.user["empresa_id"]).execute()

    acciones = acciones_res.data if acciones_res.data else []
    acciones_dict = {a["nombre"]: a for a in acciones}

    accion_nombre = st.selectbox("Selecciona Acción Formativa", options=list(acciones_dict.keys()) if acciones_dict else ["No hay acciones"])
    accion = acciones_dict.get(accion_nombre)

    if not accion:
        return

    empresa_id = accion["empresa_id"]
    accion_id = accion["id"]

    # 2. Botones para generar documentos
    if st.button("Generar PDF"):
        pdf_buffer = generar_pdf(f"{accion_nombre}.pdf", contenido=f"PDF de {accion_nombre}")
        file_path = f"documentos/{empresa_id}/{accion_id}/{accion_nombre}.pdf"
        supabase.storage.from_("documentos").upload(file_path, pdf_buffer, {"content-type": "application/pdf", "upsert": True})
        st.success("✅ PDF subido a Storage")

    if st.button("Generar XML de Acción Formativa"):
        xml_string = generar_xml_accion_formativa(accion_id)
        file_path = f"documentos/{empresa_id}/{accion_id}/{accion_nombre}.xml"
        supabase.storage.from_("documentos").upload(file_path, io.BytesIO(xml_string.encode("utf-8")), {"content-type": "application/xml", "upsert": True})
        st.success("✅ XML de Acción Formativa subido a Storage")

    if st.button("Generar XML de Inicio de Grupo"):
        xml_string = generar_xml_inicio_grupo(accion_id)
        file_path = f"documentos/{empresa_id}/{accion_id}/{accion_nombre}_inicio_grupo.xml"
        supabase.storage.from_("documentos").upload(file_path, io.BytesIO(xml_string.encode("utf-8")), {"content-type": "application/xml", "upsert": True})
        st.success("✅ XML Inicio Grupo subido a Storage")

    if st.button("Generar XML de Finalización de Grupo"):
        xml_string = generar_xml_finalizacion_grupo(accion_id)
        file_path = f"documentos/{empresa_id}/{accion_id}/{accion_nombre}_finalizacion_grupo.xml"
        supabase.storage.from_("documentos").upload(file_path, io.BytesIO(xml_string.encode("utf-8")), {"content-type": "application/xml", "upsert": True})
        st.success("✅ XML Finalización Grupo subido a Storage")

    # 3. Listar documentos ya almacenados en Storage
st.markdown("### 📂 Documentos en Storage")
try:
    lista = supabase.storage.from_("documentos").list(f"{empresa_id}/{accion_id}")
    if not lista:
        st.info("No hay documentos almacenados todavía.")
    else:
        for doc in lista:
            file_path = f"{empresa_id}/{accion_id}/{doc['name']}"
            signed_url = supabase.storage.from_("documentos").create_signed_url(file_path, 0)  # sin caducidad
            st.markdown(f"📄 [{doc['name']}]({signed_url['signedURL']})")
except Exception as e:
    st.error(f"❌ Error al listar documentos: {str(e)}")
