import streamlit as st
import pandas as pd
from datetime import date

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =========================
    # CREAR ACCIÓN FORMATIVA
    # =========================
    st.markdown("### Crear Acción Formativa")

    # Obtener empresas para desplegable
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}

    empresa_nombre = st.selectbox(
        "Empresa",
        options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
    )
    empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

    # Formulario
    with st.form("crear_accion_formativa"):
        nombre = st.text_input("Nombre de la acción formativa")
        modalidad = st.selectbox("Modalidad", ["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)
        objetivo = st.text_area("Objetivo")
        contenido = st.text_area("Contenido")
        requisitos_previos = st.text_area("Requisitos previos (si aplica)")
        fecha_alta = date.today()

        form_submitted = st.form_submit_button("Crear Acción Formativa")

        if form_submitted:
            if not nombre or not empresa_id:
                st.error("⚠️ Nombre y empresa son obligatorios.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre,
                        "modalidad": modalidad,
                        "num_horas": num_horas,
                        "objetivo": objetivo,
                        "contenido": contenido,
                        "requisitos_previos": requisitos_previos,
                        "empresa_id": empresa_id,
                        "fecha_alta": fecha_alta.isoformat()
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")

    # =========================
    # LISTADO DE ACCIONES
    # =========================
    st.markdown("### Acciones Formativas Existentes")
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    if acciones_res.data:
        df = pd.DataFrame(acciones_res.data)
        st.dataframe(df)
    else:
        st.info("No hay acciones formativas registradas.")
