import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Importar Participantes")
    uploaded_file = st.file_uploader("Selecciona archivo .xlsx", type=["xlsx"])
    if uploaded_file:
        df_part = pd.read_excel(uploaded_file)
        batch_size = 50
        for i in range(0, len(df_part), batch_size):
            batch = df_part.iloc[i:i+batch_size].to_dict(orient="records")
            supabase.table("participantes").insert(batch).execute()
        st.success(f"Importados {len(df_part)} participantes en batches de {batch_size}")
