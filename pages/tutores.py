import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("👨‍🏫 Tutores")

    # =========================
    # Listado de tutores
    # =========================
    tutores_res = supabase.table("tutores").select("*").execute().data
    df_tutores = pd.DataFrame(tutores_res) if tutores_res else pd.DataFrame()
    st.dataframe(df_tutores)

    # =========================
# Crear nuevo tutor (versión sin bucle)
# =========================
st.markdown("### ➕ Crear Tutor")

# Inicializar bandera en session_state
if "tutor_creado" not in st.session_state:
    st.session_state.tutor_creado = False

with st.form("crear_tutor", clear_on_submit=True):
    nombre = st.text_input("Nombre *")
    apellidos = st.text_input("Apellidos *")
    email = st.text_input("Email")
    telefono = st.text_input("Teléfono")
    nif = st.text_input("NIF/DNI")
    tipo_tutor = st.selectbox("Tipo de Tutor", ["Interno", "Externo"])
    direccion = st.text_input("Dirección")
    ciudad = st.text_input("Ciudad")
    provincia = st.text_input("Provincia")
    codigo_postal = st.text_input("Código Postal")

    submitted = st.form_submit_button("Guardar Tutor")

    if submitted and not st.session_state.tutor_creado:
        if not nombre or not apellidos:
            st.error("⚠️ Nombre y Apellidos son obligatorios.")
        else:
            try:
                # Validar que no exista un tutor con el mismo email o NIF
                if email:
                    existe_email = supabase.table("tutores").select("id").eq("email", email).execute()
                    if existe_email.data:
                        st.error(f"⚠️ Ya existe un tutor con el email '{email}'.")
                        st.stop()
                if nif:
                    existe_nif = supabase.table("tutores").select("id").eq("nif", nif).execute()
                    if existe_nif.data:
                        st.error(f"⚠️ Ya existe un tutor con el NIF '{nif}'.")
                        st.stop()

                # Insertar tutor
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
                    "codigo_postal": codigo_postal
                }).execute()

                st.session_state.tutor_creado = True
                st.success(f"✅ Tutor '{nombre} {apellidos}' creado correctamente.")

                # Recargar listado de tutores
                tutores_res = supabase.table("tutores").select("*").execute().data
                df_tutores = pd.DataFrame(tutores_res) if tutores_res else pd.DataFrame()
                st.dataframe(df_tutores)

            except Exception as e:
                st.error(f"❌ Error al crear el tutor: {str(e)}")

