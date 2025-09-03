import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("Acciones Formativas")
    
    # Mostrar acciones
    acciones = supabase.table("acciones_formativas").select("*").execute().data
    df_acciones = pd.DataFrame(acciones)
    
    anios = list(range(2020, datetime.now().year + 2))
    anio_filtrado = st.selectbox("Filtrar por Año", options=[None] + anios)
    
    df_filtered = df_acciones.copy() if not df_acciones.empty else pd.DataFrame()
    if anio_filtrado and not df_filtered.empty:
        df_filtered = df_filtered[df_acciones["fecha_inicio"].dt.year == anio_filtrado]
    st.dataframe(df_filtered)

    # Crear acción formativa
    st.markdown("### Crear Acción Formativa")
    
    # Obtener empresas para el desplegable
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas = empresas_res.data if empresas_res.data else []
    empresas_dict = {e["nombre"]: e["id"] for e in empresas}
    
    empresa_nombre = st.selectbox("Empresa", options=list(empresas_dict.keys()) if empresas else ["No hay empresas"])
    empresa_id = empresas_dict.get(empresa_nombre) if empresas else None

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

def empresa_panel(supabase, session_state):
    st.subheader("Panel Empresa")
    acciones = supabase.table("acciones_formativas").select("*").eq("empresa_id", session_state.user["empresa_id"]).execute().data
    st.dataframe(pd.DataFrame(acciones))
