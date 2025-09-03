import streamlit as st
import pandas as pd
from utils import (
    generar_pdf,
    generar_xml_accion_formativa,
)

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =======================
    # Listado de acciones
    # =======================
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    df_acciones = pd.DataFrame(acciones_res.data) if acciones_res.data else pd.DataFrame()
    
    if not df_acciones.empty:
        st.markdown("### Acciones Formativas Registradas")
        st.dataframe(df_acciones)

    st.markdown("### Crear Nueva Acción Formativa")
    
    with st.form("crear_accion_formativa"):
        nombre = st.text_input("Nombre de la acción formativa *")
        descripcion = st.text_area("Descripción")
        codigo = st.text_input("Código")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        duracion_horas = st.number_input("Duración en horas", min_value=1, step=1)
        submitted = st.form_submit_button("Crear Acción")
        
        if submitted:
            if not nombre:
                st.error("⚠️ El nombre es obligatorio")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre,
                        "descripcion": descripcion,
                        "codigo": codigo,
                        "modalidad": modalidad,
                        "duracion_horas": duracion_horas
                    }).execute()
                    st.success(f"✅ Acción Formativa '{nombre}' creada correctamente")
                except Exception as e:
                    st.error(f"❌ Error al crear acción: {str(e)}")

    # =======================
    # Exportar XML de acción formativa
    # =======================
    if not df_acciones.empty:
        accion_nombre = st.selectbox("Selecciona acción para exportar XML", options=list(df_acciones["nombre"]))
        accion_id = df_acciones[df_acciones["nombre"] == accion_nombre]["id"].values[0]
        if st.button("Generar XML"):
            xml_string = generar_xml_accion_formativa(accion_id)
            st.download_button("Descargar XML", xml_string, file_name=f"{accion_nombre}.xml")
