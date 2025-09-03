import streamlit as st
import pandas as pd
from datetime import datetime
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
    
    # Obtener todas las acciones
    acciones_res = supabase.table("acciones_formativas").select("*").execute()
    df_acciones = pd.DataFrame(acciones_res.data) if acciones_res.data else pd.DataFrame()
    
    # Filtrado por año
    anios = list(range(2020, datetime.now().year + 2))
    anio_filtrado = st.selectbox("Filtrar por Año", options=[None] + anios)
    
    df_filtered = df_acciones.copy()
    if anio_filtrado and not df_filtered.empty:
        df_filtered["fecha_inicio"] = pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce")
        df_filtered = df_filtered[df_filtered["fecha_inicio"].dt.year == anio_filtrado]
    
    st.dataframe(df_filtered)
    
    # Crear acción formativa
    st.markdown("### Crear Acción Formativa")
    
    # Obtener empresas según rol
    if session_state.role == "admin":
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
    else:  # gestor solo su empresa
        empresa = supabase.table("empresas").select("id, nombre").eq("id", session_state.user["empresa_id"]).execute()
        empresas_dict = {empresa.data[0]["nombre"]: empresa.data[0]["id"]} if empresa.data else {}

    empresa_nombre = st.selectbox(
        "Empresa",
        options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"]
    )
    empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

    with st.form("crear_accion_formativa"):
        nombre = st.text_input("Nombre *")
        descripcion = st.text_area("Descripción *")
        objetivos = st.text_area("Objetivos")
        contenidos = st.text_area("Contenidos")
        requisitos = st.text_area("Requisitos")
        horas = st.number_input("Horas", min_value=1, max_value=1000, step=1)
        modalidad = st.selectbox("Modalidad", ["Presencial", "Online", "Mixta"])
        fecha_inicio = st.date_input("Fecha Inicio")
        fecha_fin = st.date_input("Fecha Fin")

        submitted = st.form_submit_button("Guardar")
        if submitted:
            if not nombre or not descripcion or not empresa_id:
                st.error("⚠️ Nombre, descripción y empresa son obligatorios.")
            elif fecha_fin < fecha_inicio:
                st.error("⚠️ La fecha de fin no puede ser anterior a la de inicio.")
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
                        "fecha_inicio": fecha_inicio.isoformat(),
                        "fecha_fin": fecha_fin.isoformat(),
                        "empresa_id": empresa_id
                    }).execute()
                    st.success(f"✅ Acción formativa '{nombre}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear la acción formativa: {str(e)}")
