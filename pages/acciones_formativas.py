import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =========================
    # Filtrado y listado
    # =========================
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    acciones = acciones_res.data if acciones_res.data else []

    if acciones:
        df = pd.DataFrame(acciones)
        # Filtrado por empresa si existe
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["id"]: e["nombre"] for e in empresas_res.data} if empresas_res.data else {}
        df["empresa_nombre"] = df["empresa_id"].map(empresas_dict)

        st.markdown("### Filtrar Acciones Formativas")
        empresa_filtrada = st.selectbox(
            "Filtrar por empresa",
            options=["Todas"] + list(empresas_dict.values())
        )
        if empresa_filtrada != "Todas":
            df = df[df["empresa_nombre"] == empresa_filtrada]

        st.dataframe(df)
    else:
        st.info("No hay acciones formativas registradas.")

    # =========================
    # Crear nueva acción formativa
    # =========================
    st.markdown("### Crear Acción Formativa")
    empresas_dict_rev = {v: k for k, v in empresas_dict.items()}  # nombre -> id

    with st.form("crear_accion"):
        nombre_accion = st.text_input("Nombre de la Acción Formativa *")
        descripcion = st.text_area("Descripción")
        modalidad = st.selectbox("Modalidad", ["Presencial", "Online", "Mixta"])
        empresa_nombre = st.selectbox(
            "Empresa", options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
        )
        empresa_id = empresas_dict_rev.get(empresa_nombre)
        num_horas = st.number_input("Número de horas", min_value=1, value=1, step=1)

        submitted = st.form_submit_button("Crear Acción Formativa")

        if submitted:
            if not nombre_accion or not empresa_id:
                st.error("⚠️ El nombre y la empresa son obligatorios.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre_accion,
                        "descripcion": descripcion,
                        "modalidad": modalidad,
                        "empresa_id": empresa_id,
                        "num_horas": num_horas
                    }).execute()
                    st.success(f"✅ Acción Formativa '{nombre_accion}' creada correctamente.")
                    st.experimental_rerun()  # refresca la página para mostrar la nueva acción
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")
