import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =======================
    # Listar acciones existentes
    # =======================
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    acciones_data = acciones_res.data if acciones_res.data else []

    if acciones_data:
        df_acciones = pd.DataFrame(acciones_data)
        st.dataframe(df_acciones)
    else:
        st.info("No hay acciones formativas registradas aún.")

    # =======================
    # Crear nueva acción formativa
    # =======================
    st.markdown("### Crear Nueva Acción Formativa")
    with st.form("crear_accion_formativa"):
        nombre = st.text_input("Nombre *")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)
        form_submitted = st.form_submit_button("Crear Acción Formativa")

        if form_submitted:
            if not nombre:
                st.error("⚠️ El nombre es obligatorio.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre,
                        "modalidad": modalidad,
                        "num_horas": num_horas
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre}' creada correctamente.")
                    st.experimental_rerun()  # Recarga la página para mostrar la nueva acción
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")
