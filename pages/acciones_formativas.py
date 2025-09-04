import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("📚 Acciones Formativas")

    # =========================
    # Cargar empresas
    # =========================
    try:
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        st.write("DEBUG - empresas_res:", empresas_res)  # 👈 Debug
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
    except Exception as e:
        st.error(f"❌ Error al cargar empresas: {str(e)}")
        st.exception(e)
        empresas_dict = {}

    # =========================
    # Mostrar acciones existentes
    # =========================
    try:
        acciones_res = supabase.table("acciones_formativas").select("*").execute()
        st.write("DEBUG - acciones_res:", acciones_res)  # 👈 Debug

        df_acciones = pd.DataFrame(acciones_res.data) if acciones_res.data else pd.DataFrame()

        if not df_acciones.empty:
            st.markdown("### 📊 Acciones Formativas Registradas")
            st.dataframe(df_acciones)
    except Exception as e:
        st.error(f"❌ Error al cargar acciones formativas: {str(e)}")
        st.exception(e)
        df_acciones = pd.DataFrame()

    # =========================
    # Formulario para crear acción
    # =========================
    st.markdown("### ➕ Crear Acción Formativa")

    with st.form("crear_accion_formativa"):
        nombre_accion = st.text_input("Nombre de la acción *")
        modalidad = st.selectbox("Modalidad", options=["Presencial", "Online", "Mixta"])
        num_horas = st.text_input("Número de horas (solo números)", value="1")

        empresa_nombre = st.selectbox(
            "Empresa",
            options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
        )
        empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

        submitted = st.form_submit_button("Crear Acción Formativa")

        if submitted:
            # Validaciones
            if not nombre_accion or not empresa_id:
                st.error("⚠️ Nombre y empresa son obligatorios.")
            else:
                try:
                    num_horas_int = int(num_horas) if num_horas.isdigit() else None
                    if not num_horas_int or num_horas_int <= 0:
                        st.error("⚠️ El número de horas debe ser un número positivo.")
                    else:
                        insert_data = {
                            "nombre": nombre_accion,
                            "modalidad": modalidad,
                            "num_horas": num_horas_int,
                            "empresa_id": empresa_id
                        }
                        st.write("DEBUG - Insertando:", insert_data)  # 👈 Debug

                        supabase.table("acciones_formativas").insert(insert_data).execute()
                        st.success(f"✅ Acción formativa '{nombre_accion}' creada correctamente.")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")
                    st.exception(e)

    # =========================
    # Filtro por empresa
    # =========================
    if not df_acciones.empty and empresas_dict:
        empresa_filter = st.selectbox("Filtrar por empresa", options=["Todas"] + list(empresas_dict.keys()))
        if empresa_filter != "Todas":
            df_acciones = df_acciones[df_acciones["empresa_id"] == empresas_dict[empresa_filter]]
            st.dataframe(df_acciones)
