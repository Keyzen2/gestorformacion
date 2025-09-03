import streamlit as st
import pandas as pd
from datetime import date

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =========================
    # Selección de empresa (solo para admin)
    # =========================
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}

    if session_state.role == "admin":
        empresa_nombre = st.selectbox("Empresa", options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"])
        empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None
    else:
        empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Crear acción formativa
    # =========================
    st.markdown("### Crear Acción Formativa")
    with st.form("crear_accion"):
        nombre = st.text_input("Nombre de la acción formativa")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)
        submitted = st.form_submit_button("Crear Acción Formativa")

        if submitted:
            if not nombre:
                st.error("⚠️ El nombre es obligatorio")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre,
                        "modalidad": modalidad,
                        "num_horas": num_horas,
                        "empresa_id": empresa_id
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre}' creada correctamente")
                except Exception as e:
                    st.error(f"❌ Error al crear acción formativa: {str(e)}")

    # =========================
    # Listado de acciones formativas
    # =========================
    query = supabase.table("acciones_formativas").select("*")
    if session_state.role != "admin":
        query = query.eq("empresa_id", empresa_id)
    acciones = query.execute().data

    if acciones:
        df = pd.DataFrame(acciones)
        st.markdown("### Acciones formativas existentes")
        st.dataframe(df)
    else:
        st.info("No hay acciones formativas disponibles.")
