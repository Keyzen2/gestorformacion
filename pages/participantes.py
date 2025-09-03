import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("Participantes")

    # ----------------------
    # Selección de grupo
    # ----------------------
    grupos_res = supabase.table("grupos").select("id, codigo_grupo, empresa_id").execute()
    grupos_data = grupos_res.data if grupos_res.data else []

    # Filtrar grupos según empresa si el usuario es gestor
    if session_state.role == "gestor":
        grupos_data = [g for g in grupos_data if g["empresa_id"] == session_state.user["empresa_id"]]

    grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_data}
    grupo_nombre = st.selectbox("Selecciona Grupo", options=list(grupos_dict.keys()) if grupos_dict else ["No hay grupos"])
    grupo_id = grupos_dict.get(grupo_nombre) if grupos_dict else None

    # ----------------------
    # Filtro de participantes existentes
    # ----------------------
    if grupo_id:
        participantes_res = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute()
        df_participantes = pd.DataFrame(participantes_res.data) if participantes_res.data else pd.DataFrame()
        if not df_participantes.empty:
            search = st.text_input("Buscar participante por nombre/apellidos")
            if search:
                df_participantes = df_participantes[
                    df_participantes["nombre"].str.contains(search, case=False, na=False) |
                    df_participantes["apellidos"].str.contains(search, case=False, na=False)
                ]
            st.dataframe(df_participantes)

    st.markdown("---")
    st.markdown("### Dar de alta participante manualmente")
    with st.form("crear_participante"):
        nombre = st.text_input("Nombre *")
        apellidos = st.text_input("Apellidos *")
        dni = st.text_input("DNI/NIE *")
        email = st.text_input("Email")
        telefono = st.text_input("Teléfono")
        submitted_manual = st.form_submit_button("Crear participante")

        if submitted_manual:
            if not nombre or not apellidos or not dni or not grupo_id:
                st.error("⚠️ Nombre, apellidos, DNI y grupo son obligatorios.")
            else:
                try:
                    supabase.table("participantes").insert({
                        "nombre": nombre,
                        "apellidos": apellidos,
                        "dni": dni,
                        "email": email,
                        "telefono": telefono,
                        "grupo_id": grupo_id,
                        "empresa_id": session_state.user.get("empresa_id")
                    }).execute()
                    st.success(f"✅ Participante '{nombre} {apellidos}' creado correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear el participante: {str(e)}")

    st.markdown("---")
    st.markdown("### Importar participantes desde Excel (.xlsx)")
    uploaded_file = st.file_uploader("Selecciona archivo .xlsx con participantes", type=["xlsx"])
    if uploaded_file and grupo_id:
        try:
            df_excel = pd.read_excel(uploaded_file)
            required_cols = {"nombre", "apellidos", "dni"}
            if not required_cols.issubset(set(df_excel.columns.str.lower())):
                st.error(f"El archivo debe contener las columnas: {', '.join(required_cols)}")
            else:
                batch_size = 50
                for i in range(0, len(df_excel), batch_size):
                    batch = df_excel.iloc[i:i+batch_size].to_dict(orient="records")
                    for item in batch:
                        # Normalizamos nombres de columnas a minúsculas
                        item = {k.lower(): v for k, v in item.items()}
                        item["grupo_id"] = grupo_id
                        item["empresa_id"] = session_state.user.get("empresa_id")
                    supabase.table("participantes").insert(batch).execute()
                st.success(f"✅ Importados {len(df_excel)} participantes en batches de {batch_size}")
        except Exception as e:
            st.error(f"❌ Error al importar participantes: {str(e)}")
