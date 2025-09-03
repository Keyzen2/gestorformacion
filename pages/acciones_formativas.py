import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =======================
    # Obtener empresas
    # =======================
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}

    empresa_nombre = st.selectbox(
        "Empresa",
        options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
    )
    empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

    # =======================
    # Crear acción formativa
    # =======================
    st.markdown("### Crear Acción Formativa")
    with st.form("crear_accion_formativa"):
        nombre_accion = st.text_input("Nombre de la acción formativa")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)
        form_submitted = st.form_submit_button("Crear Acción Formativa")

        if form_submitted:
            if not nombre_accion.strip():
                st.error("⚠️ El nombre de la acción formativa es obligatorio.")
            elif not empresa_id:
                st.error("⚠️ Debes seleccionar una empresa.")
            else:
                try:
                    data = {
                        "nombre": nombre_accion.strip(),
                        "modalidad": modalidad,
                        "num_horas": int(num_horas),
                        "empresa_id": empresa_id
                    }
                    result = supabase.table("acciones_formativas").insert(data).execute()
                    if result.data:
                        st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                    else:
                        st.warning("⚠️ No se pudo crear la acción formativa.")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")

    # =======================
    # Mostrar acciones formativas existentes
    # =======================
    st.markdown("### Acciones Formativas Existentes")
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    if acciones_res.data:
        df_acciones = pd.DataFrame(acciones_res.data)
        st.dataframe(df_acciones)
    else:
        st.info("No hay acciones formativas registradas.")
