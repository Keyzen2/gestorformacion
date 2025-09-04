import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("📚 Acciones Formativas")

    # =========================
    # Cargar empresas
    # =========================
    try:
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
    except Exception as e:
        st.error(f"Error al cargar empresas: {str(e)}")
        empresas_dict = {}

    if not empresas_dict:
        st.warning("No hay empresas disponibles. Crea primero una empresa.")
        st.stop()

    # =========================
    # Mostrar acciones existentes
    # =========================
    try:
        acciones_res = supabase.table("acciones_formativas").select("*").execute()
        df_acciones = pd.DataFrame(acciones_res.data) if acciones_res.data else pd.DataFrame()

        if not df_acciones.empty:
            for col in ["fecha_inicio", "fecha_fin"]:
                if col in df_acciones.columns:
                    df_acciones[col] = pd.to_datetime(df_acciones[col], errors="coerce").dt.strftime("%d/%m/%Y")

        st.dataframe(df_acciones)
    except Exception as e:
        st.error(f"Error al cargar acciones formativas: {str(e)}")
        df_acciones = pd.DataFrame()

    st.markdown("### ➕ Crear Acción Formativa")

    # =========================
    # Formulario creación acción
    # =========================
    with st.form("crear_accion_formativa"):
        nombre_accion = st.text_input("Nombre de la acción *")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)
        fecha_inicio = st.date_input("Fecha de inicio *")
        fecha_fin = st.date_input("Fecha de fin *")
        empresa_nombre = st.selectbox("Empresa", options=list(empresas_dict.keys()))
        empresa_id = empresas_dict.get(empresa_nombre)

        submitted = st.form_submit_button("Crear Acción Formativa")

        if submitted:
            if not nombre_accion or not empresa_id:
                st.error("⚠️ Nombre y empresa son obligatorios.")
            elif fecha_fin <= fecha_inicio:
                st.error("⚠️ La fecha de fin debe ser posterior a la fecha de inicio.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre_accion,
                        "modalidad": modalidad,
                        "num_horas": int(num_horas),
                        "empresa_id": empresa_id,
                        "fecha_inicio": fecha_inicio.isoformat(),
                        "fecha_fin": fecha_fin.isoformat()
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")

    # =========================
    # Filtro por empresa
    # =========================
    if not df_acciones.empty:
        empresa_filter = st.selectbox("Filtrar por empresa", options=["Todas"] + list(empresas_dict.keys()))
        df_acciones_filtrado = df_acciones[df_acciones["empresa_id"].notnull()]
        if empresa_filter != "Todas":
            df_acciones_filtrado = df_acciones_filtrado[df_acciones_filtrado["empresa_id"] == empresas_dict[empresa_filter]]
        st.dataframe(df_acciones_filtrado)



