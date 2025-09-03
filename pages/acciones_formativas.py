import streamlit as st

def main(supabase, session_state):
    st.title("Acciones Formativas")

    # =======================
    # Selección de empresa
    # =======================
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}

    empresa_nombre = st.selectbox(
        "Empresa",
        options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
    )
    empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

    st.markdown("---")
    st.markdown("### Crear Acción Formativa")

    with st.form("crear_accion_formativa"):
        nombre_accion = st.text_input("Nombre Acción Formativa *")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas_str = st.text_input("Número de horas *")

        # Validar número de horas
        try:
            num_horas = int(num_horas_str)
            if num_horas < 1:
                st.error("⚠️ El número de horas debe ser mayor que 0")
        except ValueError:
            if num_horas_str:
                st.error("⚠️ Introduce un número válido")

        form_submitted = st.form_submit_button("Crear Acción Formativa")

        if form_submitted:
            if not nombre_accion or not empresa_id or not num_horas_str:
                st.error("⚠️ Todos los campos son obligatorios")
            else:
                try:
                    # Insertar en la tabla acciones_formativas
                    result = supabase.table("acciones_formativas").insert({
                        "nombre": nombre_accion,
                        "modalidad": modalidad,
                        "num_horas": num_horas,
                        "empresa_id": empresa_id
                    }).execute()

                    if result.data:
                        st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente")
                    else:
                        st.error("❌ Error al crear la acción formativa")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")

    # =======================
    # Listado de acciones
    # =======================
    st.markdown("---")
    st.subheader("Acciones Formativas existentes")
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    if acciones_res.data:
        st.dataframe(acciones_res.data)
    else:
        st.info("No hay acciones formativas registradas.")
