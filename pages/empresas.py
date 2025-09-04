import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("🏢 Empresas")

    # Solo admin puede gestionar empresas
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden gestionar empresas.")
        st.stop()

    # =========================
    # Cargar empresas
    # =========================
    empresas_res = supabase.table("empresas").select("*").execute()
    df_empresas = pd.DataFrame(empresas_res.data) if empresas_res.data else pd.DataFrame()

    # =========================
    # Listado
    # =========================
    if not df_empresas.empty:
        search_query = st.text_input("🔍 Buscar por nombre o CIF")
        if search_query:
            df_empresas = df_empresas[
                df_empresas["nombre"].str.contains(search_query, case=False, na=False) |
                df_empresas["cif"].str.contains(search_query, case=False, na=False)
            ]
        st.dataframe(df_empresas)
    else:
        st.info("ℹ️ No hay empresas registradas.")

    # =========================
# Crear nueva empresa (versión sin bucle)
# =========================
st.markdown("### ➕ Crear Empresa")

# Inicializar bandera en session_state
if "empresa_creada" not in st.session_state:
    st.session_state.empresa_creada = False

with st.form("crear_empresa", clear_on_submit=True):
    nombre = st.text_input("Nombre *")
    cif = st.text_input("CIF *")
    direccion = st.text_input("Dirección")
    telefono = st.text_input("Teléfono")
    email = st.text_input("Email")
    representante_nombre = st.text_input("Nombre del representante")
    representante_dni = st.text_input("DNI del representante")
    ciudad = st.text_input("Ciudad")
    provincia = st.text_input("Provincia")
    codigo_postal = st.text_input("Código Postal")

    submitted = st.form_submit_button("Crear Empresa")

    if submitted and not st.session_state.empresa_creada:
        if not nombre or not cif:
            st.error("⚠️ Nombre y CIF son obligatorios.")
        else:
            # Verificar si ya existe una empresa con ese CIF
            existe = supabase.table("empresas").select("id").eq("cif", cif).execute()
            if existe.data:
                st.error(f"⚠️ Ya existe una empresa con el CIF '{cif}'.")
            else:
                try:
                    nueva_empresa = {
                        "nombre": nombre,
                        "cif": cif,
                        "direccion": direccion,
                        "telefono": telefono,
                        "email": email,
                        "representante_nombre": representante_nombre,
                        "representante_dni": representante_dni,
                        "ciudad": ciudad,
                        "provincia": provincia,
                        "codigo_postal": codigo_postal,
                        "fecha_alta": datetime.utcnow().isoformat()
                    }
                    supabase.table("empresas").insert(nueva_empresa).execute()
                    st.session_state.empresa_creada = True
                    st.success(f"✅ Empresa '{nombre}' creada correctamente.")

                    # Recargar datos para que aparezca la nueva empresa
                    empresas_res = supabase.table("empresas").select("*").execute()
                    df_empresas = pd.DataFrame(empresas_res.data) if empresas_res.data else pd.DataFrame()

                except Exception as e:
                    st.error(f"❌ Error al crear la empresa: {str(e)}")
