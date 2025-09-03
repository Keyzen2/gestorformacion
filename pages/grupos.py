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
    st.subheader("Grupos")
    grupos = supabase.table("grupos").select("*").execute().data
    st.dataframe(pd.DataFrame(grupos))

    st.markdown("### Crear Grupo")
    
    # Obtener empresas y acciones
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
    acciones_res = supabase.table("acciones_formativas").select("id, nombre").execute()
    acciones_dict = {a["nombre"]: a["id"] for a in acciones_res.data} if acciones_res.data else {}

    empresa_nombre = st.selectbox("Empresa", options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"])
    empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None
    accion_nombre = st.selectbox("Acción Formativa", options=list(acciones_dict.keys()) if acciones_dict else ["No hay acciones"])
    accion_id = acciones_dict.get(accion_nombre) if acciones_dict else None

    with st.form("crear_grupo"):
        codigo_grupo = st.text_input("Código Grupo *")
        fecha_inicio = st.date_input("Fecha Inicio")
        fecha_fin = st.date_input("Fecha Fin")
        submitted_grupo = st.form_submit_button("Crear Grupo")

        if submitted_grupo:
            if not codigo_grupo or not empresa_id or not accion_id:
                st.error("⚠️ Código, empresa y acción formativa son obligatorios.")
            elif fecha_fin < fecha_inicio:
                st.error("⚠️ La fecha de fin no puede ser anterior a la de inicio.")
            else:
                try:
                    supabase.table("grupos").insert({
                        "codigo_grupo": codigo_grupo,
                        "fecha_inicio": fecha_inicio.isoformat(),
                        "fecha_fin": fecha_fin.isoformat(),
                        "empresa_id": empresa_id,
                        "accion_formativa_id": accion_id
                    }).execute()
                    st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear el grupo: {str(e)}")
