# pages/acciones_formativas.py
import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =======================
    # Cargar empresas
    # =======================
    try:
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
    except Exception as e:
        st.error(f"Error al cargar empresas: {str(e)}")
        empresas_dict = {}

    # =======================
    # Mostrar acciones existentes
    # =======================
    try:
        acciones_res = supabase.table("acciones_formativas").select("*").execute()
        df_acciones = pd.DataFrame(acciones_res.data) if acciones_res.data else pd.DataFrame()
        if not df_acciones.empty:
            st.dataframe(df_acciones)
    except Exception as e:
        st.error(f"Error al cargar acciones formativas: {str(e)}")

    # =======================
    # Crear nueva acción formativa
    # =======================
    st.markdown("### Crear Acción Formativa")
    with st.form("crear_accion_formativa"):
        nombre_accion = st.text_input("Nombre de la acción *")
        descripcion = st.text_area("Descripción")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)
        empresa_nombre = st.selectbox(
            "Empresa", options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
        )
        empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

        form_submitted = st.form_submit_button("Crear Acción Formativa")

        if form_submitted:
            if not nombre_accion or not empresa_id:
                st.error("⚠️ Nombre de acción y empresa son obligatorios.")
            else:
                try:
                    result = supabase.table("acciones_formativas").insert({
                        "nombre": nombre_accion,
                        "descripcion": descripcion,
                        "modalidad": modalidad,
                        "num_horas": num_horas,
                        "empresa_id": empresa_id
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")
