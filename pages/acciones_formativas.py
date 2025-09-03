import streamlit as st
import pandas as pd
from utils import (
    importar_participantes_excel,
    generar_pdf,
    validar_xml,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo
)

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # ==========================
    # Cargar acciones formativas
    # ==========================
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    acciones = acciones_res.data if acciones_res.data else []
    df_acciones = pd.DataFrame(acciones)

    st.dataframe(df_acciones)

    # ==========================
    # Crear acción formativa
    # ==========================
    st.markdown("### Crear Acción Formativa")

    # Obtener empresas según rol
    if session_state.role == "admin":
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas = empresas_res.data if empresas_res.data else []
    else:  # gestor: solo su empresa
        empresas_res = supabase.table("empresas").select("id, nombre").eq("id", session_state.user.get("empresa_id")).execute()
        empresas = empresas_res.data if empresas_res.data else []

    if not empresas:
        st.warning("No hay empresas disponibles.")
        return

    empresas_dict = {e["nombre"]: e["id"] for e in empresas}
    empresa_nombre = st.selectbox("Empresa", options=list(empresas_dict.keys()))
    empresa_id = empresas_dict.get(empresa_nombre)

    # Formulario
    with st.form("crear_accion_formativa"):
        nombre = st.text_input("Nombre *")
        descripcion = st.text_area("Descripción *")
        objetivos = st.text_area("Objetivos")
        contenidos = st.text_area("Contenidos")
        requisitos = st.text_area("Requisitos")
        horas = st.number_input("Horas", min_value=1, max_value=1000, step=1)
        modalidad = st.selectbox("Modalidad", ["Presencial", "Online", "Mixta"])

        submitted = st.form_submit_button("Guardar")
        if submitted:
            # Validaciones
            if not nombre or not descripcion or not empresa_id:
                st.error("⚠️ Nombre, descripción y empresa son obligatorios.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre,
                        "descripcion": descripcion,
                        "objetivos": objetivos,
                        "contenidos": contenidos,
                        "requisitos": requisitos,
                        "horas": horas,
                        "modalidad": modalidad,
                        "empresa_id": empresa_id
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")
