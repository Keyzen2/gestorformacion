import streamlit as st
import pandas as pd
from datetime import datetime
from utils.crud import crud_tabla

def main(supabase, session_state):
    st.subheader("🏢 Empresas")

    # Solo admin puede gestionar empresas
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden gestionar empresas.")
        st.stop()

    # =========================
    # Búsqueda previa (opcional)
    # =========================
    search_query = st.text_input("🔍 Buscar por nombre o CIF")

    # Si quieres filtrar antes de pasar al CRUD
    if search_query:
        empresas_res = supabase.table("empresas").select("*").execute()
        df_empresas = pd.DataFrame(empresas_res.data) if empresas_res.data else pd.DataFrame()
        if not df_empresas.empty:
            df_empresas = df_empresas[
                df_empresas["nombre"].str.contains(search_query, case=False, na=False) |
                df_empresas["cif"].str.contains(search_query, case=False, na=False)
            ]
            st.dataframe(df_empresas)
        else:
            st.info("ℹ️ No hay empresas registradas con ese criterio.")

    # =========================
    # CRUD unificado
    # =========================
    crud_tabla(
        supabase,
        nombre_tabla="empresas",
        campos_visibles=["nombre", "cif", "telefono", "email", "ciudad", "provincia"],
        campos_editables=[
            "nombre", "cif", "direccion", "telefono", "email",
            "representante_nombre", "representante_dni",
            "ciudad", "provincia", "codigo_postal"
        ]
    )

    # =========================
    # Crear nueva empresa (manteniendo tu validación)
    # =========================
    st.markdown("### ➕ Crear Empresa")
    with st.form("crear_empresa"):
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

        if submitted:
            if not nombre or not cif:
                st.error("⚠️ Nombre y CIF son obligatorios.")
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
                    st.success(f"✅ Empresa '{nombre}' creada correctamente.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear la empresa: {str(e)}")

