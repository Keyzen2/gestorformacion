import streamlit as st
import pandas as pd
from utils import (
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo
)

def main(supabase, session_state):
    st.subheader("Acciones Formativas")

    # =========================
    # Obtener empresas
    # =========================
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_data = empresas_res.data if empresas_res.data else []
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_data}

    empresa_nombre = st.selectbox(
        "Empresa",
        options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
    )
    empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

    # =========================
    # Listado de acciones
    # =========================
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    acciones_data = acciones_res.data if acciones_res.data else []
    df_acciones = pd.DataFrame(acciones_data)

    st.markdown("### Acciones Formativas Existentes")
    if not df_acciones.empty:
        st.dataframe(df_acciones)
    else:
        st.info("No hay acciones formativas registradas.")

    # =========================
    # Crear nueva acción formativa
    # =========================
    st.markdown("### Crear Acción Formativa")
    with st.form("crear_accion_formativa"):
        nombre = st.text_input("Nombre de la acción *")
        codigo = st.text_input("Código *")
        modalidad_options = ["Presencial", "Online", "Mixta"]
        modalidad = st.selectbox("Modalidad", options=modalidad_options)
        submitted = st.form_submit_button("Crear Acción Formativa")

        if submitted:
            if not nombre or not codigo:
                st.error("⚠️ Nombre y Código son obligatorios.")
            else:
                try:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre,
                        "codigo": codigo,
                        "modalidad": modalidad,
                        "empresa_id": empresa_id
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")

    # =========================
    # Exportar XML
    # =========================
    if df_acciones.empty:
        return

    accion_nombre = st.selectbox("Selecciona Acción Formativa para exportar XML", options=df_acciones["nombre"].tolist())
    accion_id = df_acciones.loc[df_acciones["nombre"] == accion_nombre, "id"].values[0]

    # Obtener grupos asociados
    grupos_res = supabase.table("grupos").select("*").eq("accion_formativa_id", accion_id).execute()
    grupos_data = grupos_res.data if grupos_res.data else []

    grupo_nombre = None
    grupo_id = None
    if grupos_data:
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_data}
        grupo_nombre = st.selectbox("Selecciona Grupo para exportar XML Inicio/Fin", options=list(grupos_dict.keys()))
        grupo_id = grupos_dict.get(grupo_nombre)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Exportar XML Acción Formativa"):
            xml = generar_xml_accion_formativa(accion_id)
            st.download_button("Descargar XML", xml, file_name=f"{accion_nombre}.xml")

    with col2:
        if grupo_id and st.button("Exportar XML Inicio Grupo"):
            xml = generar_xml_inicio_grupo(grupo_id)
            st.download_button("Descargar XML Inicio Grupo", xml, file_name=f"{grupo_nombre}_inicio.xml")

    with col3:
        if grupo_id and st.button("Exportar XML Finalización Grupo"):
            xml = generar_xml_finalizacion_grupo(grupo_id)
            st.download_button("Descargar XML Fin Grupo", xml, file_name=f"{grupo_nombre}_fin.xml")
