import streamlit as st
import pandas as pd
from datetime import date

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # Obtener empresas
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}

    empresa_nombre = st.selectbox("Empresa", options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"])
    empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

    # Listado de acciones formativas
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    df_acciones = pd.DataFrame(acciones_res.data) if acciones_res.data else pd.DataFrame()
    st.dataframe(df_acciones)

    st.markdown("### Crear Acción Formativa")
    with st.form("crear_accion"):
        nombre_accion = st.text_input("Nombre de la acción *")
        descripcion = st.text_area("Descripción")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        duracion = st.number_input("Duración (horas)", min_value=1)
        submitted = st.form_submit_button("Crear Acción Formativa")

        if submitted:
            if not nombre_accion or not empresa_id:
                st.error("⚠️ Nombre y empresa son obligatorios.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre_accion,
                        "descripcion": descripcion,
                        "modalidad": modalidad,
                        "duracion": duracion,
                        "empresa_id": empresa_id
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")
