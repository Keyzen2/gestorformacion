import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Tutores")

    # Mostrar tutores existentes
    tutores_res = supabase.table("tutores").select("*").execute()
    tutores = tutores_res.data if tutores_res.data else []
    st.dataframe(pd.DataFrame(tutores))

    st.markdown("### Crear Tutor")
    with st.form("crear_tutor"):
        nombre = st.text_input("Nombre *")
        email = st.text_input("Email")
        telefono = st.text_input("Teléfono")
        submitted = st.form_submit_button("Guardar")

        if submitted:
            if not nombre:
                st.error("⚠️ El nombre es obligatorio.")
            else:
                try:
                    supabase.table("tutores").insert({
                        "nombre": nombre,
                        "email": email,
                        "telefono": telefono
                    }).execute()
                    st.success(f"✅ Tutor '{nombre}' creado correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear el tutor: {str(e)}")
