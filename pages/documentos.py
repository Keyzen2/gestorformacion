import streamlit as st
from utils import generar_pdf

def main(supabase, session_state):
    st.subheader("Generar Documentos")
    acciones = supabase.table("acciones_formativas").select("*").execute().data
    df_acciones = pd.DataFrame(acciones)
    accion_sel = st.selectbox("Selecciona acción formativa", options=df_acciones["id"].tolist() if not df_acciones.empty else [])
    if accion_sel:
        if st.button("Generar PDF"):
            pdf_buffer = generar_pdf("documento.pdf")
            st.download_button("Descargar PDF", pdf_buffer, file_name="documento.pdf")
        if st.button("Generar XML de prueba"):
            xml_string = "<root><accion id='{}'/></root>".format(accion_sel)
            st.code(xml_string)
