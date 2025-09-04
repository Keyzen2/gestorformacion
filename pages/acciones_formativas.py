import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =========================
    # Cargar empresas
    # =========================
    empresas_dict = {}
    try:
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        if empresas_res.data:
            empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data}
    except Exception as e:
        st.error(f"Error al cargar empresas: {str(e)}")

    # =========================
    # Cargar acciones existentes
    # =========================
    df_acciones = pd.DataFrame(columns=["id", "nombre", "modalidad", "num_horas", "empresa_id", "fecha_inicio", "fecha_fin"])
    try:
        acciones_res = supabase.table("acciones_formativas").select("*").execute()
        if acciones_res.data:
            df_acciones = pd.DataFrame(acciones_res.data)
            # Convertir fechas a datetime si existen
            if "fecha_inicio" in df_acciones.columns:
                df_acciones["fecha_inicio"] = pd.to_datetime(df_acciones["fecha_inicio"], errors="coerce")
            if "fecha_fin" in df_acciones.columns:
                df_acciones["fecha_fin"] = pd.to_datetime(df_acciones["fecha_fin"], errors="coerce")
    except Exception as e:
        st.error(f"Error al cargar acciones formativas: {str(e)}")

    # =========================
    # Filtros de visualización
    # =========================
    if not df_acciones.empty and empresas_dict:
        col1, col2 = st.columns(2)
        with col1:
            empresa_filter = st.selectbox("Filtrar por empresa", options=["Todas"] + list(empresas_dict.keys()))
        with col2:
            anio_filter = st.selectbox(
                "Filtrar por año",
                options=["Todos"] + sorted(
                    df_acciones["fecha_inicio"].dt.year.dropna().unique().tolist(),
                    reverse=True
                )
            )

        df_filtered = df_acciones.copy()
        if empresa_filter != "Todas":
            df_filtered = df_filtered[df_filtered["empresa_id"] == empresas_dict[empresa_filter]]
        if anio_filter != "Todos":
            df_filtered = df_filtered[df_filtered["fecha_inicio"].dt.year == int(anio_filter)]

        st.dataframe(df_filtered)

    else:
        st.info("No hay acciones formativas registradas.")

    # =========================
    # Crear acción formativa
    # =========================
    st.markdown("### Crear Acción Formativa")
    with st.form("crear_accion_formativa"):
        nombre_accion = st.text_input("Nombre de la acción *")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1)
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
                    st.experimental_rerun()  # Refresca la app automáticamente
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")
