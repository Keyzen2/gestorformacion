import streamlit as st
import pandas as pd
from utils.crud import crud_tabla

def main(supabase, session_state):
    st.subheader("Tutores")

    # =========================
    # CRUD unificado para tutores
    # =========================
    crud_tabla(
        supabase,
        nombre_tabla="tutores",
        campos_visibles=["nombre", "apellidos", "email", "telefono", "tipo_tutor"],
        campos_editables=[
            "nombre", "apellidos", "email", "telefono", "nif",
            "tipo_tutor", "direccion", "ciudad", "provincia", "codigo_postal"
        ]
    )

    # =========================
    # Mostrar tutores existentes (vista rápida)
    # =========================
    tutores_res = supabase.table("tutores").select("*").execute().data
    df_tutores = pd.DataFrame(tutores_res) if tutores_res else pd.DataFrame()
    if not df_tutores.empty:
        st.dataframe(df_tutores)
    else:
        st.info("ℹ️ No hay tutores registrados.")

    # =========================
    # Crear nuevo tutor (manteniendo tu validación)
    # =========================
    st.markdown("### ➕ Crear Tutor")
    with st.form("crear_tutor"):
        nombre = st.text_input("Nombre *")
        apellidos = st.text_input("Apellidos *")
        email = st.text_input("Email")
        telefono = st.text_input("Teléfono")
        nif = st.text_input("NIF/DNI")
        tipo_tutor = st.selectbox("Tipo de Tutor", ["Interno", "Externo"])
        direccion = st.text_input("Dirección")
        ciudad = st.text_input("Ciudad")
        provincia = st.text_input("Provincia")
        cod_postal = st.text_input("Código Postal")

        submitted = st.form_submit_button("Guardar Tutor")

        if submitted:
            if not nombre or not apellidos:
                st.error("⚠️ Nombre y Apellidos son obligatorios.")
            else:
                try:
                    supabase.table("tutores").insert({
                        "nombre": nombre,
                        "apellidos": apellidos,
                        "email": email,
                        "telefono": telefono,
                        "nif": nif,
                        "tipo_tutor": tipo_tutor,
                        "direccion": direccion,
                        "ciudad": ciudad,
                        "provincia": provincia,
                        "codigo_postal": cod_postal
                    }).execute()
                    st.success(f"✅ Tutor '{nombre} {apellidos}' creado correctamente.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear el tutor: {str(e)}")

