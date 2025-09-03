import streamlit as st
import pandas as pd
from datetime import date

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =========================
    # Obtener empresas
    # =========================
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}

    empresa_nombre = st.selectbox(
        "Empresa",
        options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
    )
    empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

    # =========================
    # Crear nueva acción formativa
    # =========================
    st.markdown("### Crear Acción Formativa")
    with st.form("crear_accion_formativa"):
        nombre_accion = st.text_input("Nombre de la acción *")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1)
        anio = st.number_input("Año", min_value=2000, max_value=2100, value=date.today().year)
        submitted = st.form_submit_button("Crear Acción")

        if submitted:
            if not nombre_accion or not empresa_id:
                st.error("⚠️ Nombre y empresa son obligatorios.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre_accion,
                        "modalidad": modalidad,
                        "num_horas": num_horas,
                        "anio": anio,
                        "empresa_id": empresa_id
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción: {str(e)}")

    # =========================
    # Listado y filtrado
    # =========================
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    if acciones_res.data:
        df = pd.DataFrame(acciones_res.data)
        df_filtered = df.copy()
        if "anio" in df.columns:
            anio_filtrado = st.selectbox("Filtrar por año", options=sorted(df["anio"].unique(), reverse=True))
            df_filtered = df_filtered[df_filtered["anio"] == anio_filtrado]
        st.dataframe(df_filtered)
    else:
        st.info("No hay acciones formativas registradas.")
