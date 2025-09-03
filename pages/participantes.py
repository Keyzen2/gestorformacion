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
    st.subheader("Participantes")

    # Selección de grupo
    grupos_res = supabase.table("grupos").select("id, codigo_grupo").execute()
    grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data} if grupos_res.data else {}
    grupo_nombre = st.selectbox("Selecciona Grupo", options=list(grupos_dict.keys()) if grupos_dict else ["No hay grupos"])
    grupo_id = grupos_dict.get(grupo_nombre) if grupos_dict else None

    # Subida de archivo Excel
    uploaded_file = st.file_uploader("Selecciona archivo .xlsx con participantes", type=["xlsx"])
    if uploaded_file and grupo_id:
        df_part = pd.read_excel(uploaded_file)
        batch_size = 50
        for i in range(0, len(df_part), batch_size):
            batch = df_part.iloc[i:i+batch_size].to_dict(orient="records")
            # Agregamos el grupo_id y empresa_id de forma automática
            for item in batch:
                item["grupo_id"] = grupo_id
                item["empresa_id"] = session_state.user.get("empresa_id")
            supabase.table("participantes").insert(batch).execute()
        st.success(f"✅ Importados {len(df_part)} participantes en batches de {batch_size}")
