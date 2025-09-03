import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Grupos")
    grupos = supabase.table("grupos").select("*").execute().data
    st.dataframe(pd.DataFrame(grupos))

    st.markdown("### Crear Grupo")
    with st.form("crear_grupo"):
        codigo_grupo = st.text_input("Código Grupo")
        fecha_inicio = st.date_input("Fecha Inicio")
        fecha_fin = st.date_input("Fecha Fin")
        accion_formativa_id = st.text_input("ID Acción Formativa")
        empresa_id_sel = st.text_input("Empresa ID")
        submitted_grupo = st.form_submit_button("Crear Grupo")
        if submitted_grupo:
            supabase.table("grupos").insert({
                "codigo_grupo": codigo_grupo,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "accion_formativa_id": accion_formativa_id,
                "empresa_id": empresa_id_sel
            }).execute()
            st.success("Grupo creado")
