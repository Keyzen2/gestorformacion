import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Tutores")
    if st.button("Ver Tutores"):
        tutores = supabase.table("tutores").select("*").execute().data
        st.dataframe(pd.DataFrame(tutores))

    st.markdown("### Crear Tutor")
    with st.form("crear_tutor"):
        nombre = st.text_input("Nombre *")
        email = st.text_input("Email")
        telefono = st.text_input("Teléfono")
        submitted = st.form_submit_button("Guardar")

        if submitted:
            if not nombre or not email:
                st.error("⚠️ Nombre y email son obligatorios.")
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
