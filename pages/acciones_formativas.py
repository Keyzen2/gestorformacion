import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =========================
    # Cargar empresas
    # =========================
    try:
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
    except Exception as e:
        st.error(f"Error al cargar empresas: {str(e)}")
        empresas_dict = {}

    # =========================
    # Mostrar acciones existentes
    # =========================
    try:
        acciones_res = supabase.table("acciones_formativas").select("*").execute()
        df_acciones = pd.DataFrame(acciones_res.data) if acciones_res.data else pd.DataFrame()
        st.write("Columnas cargadas:", df_acciones.columns.tolist())

        # Manejar columnas de fechas si existen
        if "fecha_inicio" in df_acciones.columns:
            df_acciones["fecha_inicio"] = pd.to_datetime(df_acciones["fecha_inicio"], errors="coerce")
        if "fecha_fin" in df_acciones.columns:
            df_acciones["fecha_fin"] = pd.to_datetime(df_acciones["fecha_fin"], errors="coerce")

        st.dataframe(df_acciones)
    except Exception as e:
        st.error(f"Error al cargar acciones formativas: {str(e)}")
        df_acciones = pd.DataFrame()

    st.markdown("### Crear Acción Formativa")

    # =========================
    # Formulario de creación
    # =========================
    with st.form("crear_accion_formativa"):
        nombre_accion = st.text_input("Nombre de la acción *")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)
        empresa_nombre = st.selectbox(
            "Empresa",
            options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
        )
        empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

        submitted = st.form_submit_button("Crear Acción Formativa")

        if submitted:
            if not nombre_accion or not empresa_id:
                st.error("⚠️ Nombre y empresa son obligatorios.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre_accion,
                        "modalidad": modalidad,
                        "num_horas": num_horas,
                        "empresa_id": empresa_id
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")

    # =========================
    # Filtro por empresa
    # =========================
    if not df_acciones.empty and empresas_dict:
        empresa_filter = st.selectbox("Filtrar por empresa", options=["Todas"] + list(empresas_dict.keys()))
        if empresa_filter != "Todas":
            df_acciones = df_acciones[df_acciones["empresa_id"] == empresas_dict[empresa_filter]]
            st.dataframe(df_acciones)
