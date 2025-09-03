import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Grupos")

    # Mostrar grupos existentes
    grupos_res = supabase.table("grupos").select("*").execute()
    grupos = grupos_res.data if grupos_res.data else []
    st.dataframe(pd.DataFrame(grupos))

    st.markdown("### Crear Grupo")

    # Obtener empresas y acciones
    empresas_res = supabase.table("empresas").select("id, nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}

    acciones_res = supabase.table("acciones_formativas").select("id, nombre").execute()
    acciones_dict = {a["nombre"]: a["id"] for a in acciones_res.data} if acciones_res.data else {}

    tutores_res = supabase.table("tutores").select("id, nombre").execute()
    tutores_dict = {t["nombre"]: t["id"] for t in tutores_res.data} if tutores_res.data else {}

    empresa_nombre = st.selectbox("Empresa", options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"])
    empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

    accion_nombre = st.selectbox("Acción Formativa", options=list(acciones_dict.keys()) if acciones_dict else ["No hay acciones"])
    accion_id = acciones_dict.get(accion_nombre) if acciones_dict else None

    tutores_seleccionados = st.multiselect("Selecciona Tutores", options=list(tutores_dict.keys()) if tutores_dict else [])
    tutor_ids = [tutores_dict[t] for t in tutores_seleccionados] if tutores_dict else []

    with st.form("crear_grupo"):
        codigo_grupo = st.text_input("Código Grupo *")
        fecha_inicio = st.date_input("Fecha Inicio")
        fecha_fin = st.date_input("Fecha Fin")
        submitted = st.form_submit_button("Crear Grupo")

        if submitted:
            if not codigo_grupo or not empresa_id or not accion_id:
                st.error("⚠️ Código, empresa y acción formativa son obligatorios.")
            elif fecha_fin < fecha_inicio:
                st.error("⚠️ La fecha de fin no puede ser anterior a la de inicio.")
            else:
                try:
                    # Crear el grupo
                    result = supabase.table("grupos").insert({
                        "codigo_grupo": codigo_grupo,
                        "fecha_inicio": fecha_inicio.isoformat(),
                        "fecha_fin": fecha_fin.isoformat(),
                        "empresa_id": empresa_id,
                        "accion_formativa_id": accion_id
                    }).execute()

                    grupo_id = result.data[0]["id"]

                    # Asignar tutores al grupo
                    for tid in tutor_ids:
                        supabase.table("tutores_grupos").insert({
                            "grupo_id": grupo_id,
                            "tutor_id": tid
                        }).execute()

                    st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente con {len(tutor_ids)} tutores asignados.")
                except Exception as e:
                    st.error(f"❌ Error al crear el grupo: {str(e)}")
