import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("🎯 Objetivos de Calidad (ISO 9001)")
    st.caption("Definición, seguimiento y evaluación de objetivos anuales de calidad para el centro de formación.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 Solo administradores o gestores pueden acceder a esta sección.")
        st.stop()

    # =========================
    # Cargar datos
    # =========================
    obj_res = supabase.table("objetivos_calidad").select("*").execute()
    df_obj = pd.DataFrame(obj_res.data) if obj_res.data else pd.DataFrame()

    seg_res = supabase.table("seguimiento_objetivos").select("*").execute()
    df_seg = pd.DataFrame(seg_res.data) if seg_res.data else pd.DataFrame()

    # =========================
    # Mostrar objetivos
    # =========================
    st.markdown("### 📋 Objetivos definidos")
    if not df_obj.empty:
        for _, row in df_obj.iterrows():
            st.markdown(f"**{row['nombre']}** — Meta: {row['meta']} — Responsable: {row.get('responsable','')}")
            st.caption(f"Fuente: {row.get('fuente_datos','')} | Frecuencia: {row.get('frecuencia','')} | Año: {row.get('ano','')}")
            
            # Mostrar seguimiento
            segs = df_seg[df_seg["objetivo_id"] == row["id"]]
            if not segs.empty:
                ultimo_valor = segs.sort_values("fecha", ascending=False).iloc[0]
                valor_real = ultimo_valor["valor_real"]
                meta_num = None
                try:
                    meta_num = float(''.join([c for c in row['meta'] if c.isdigit() or c == '.']))
                except:
                    pass

                color = "🟢"
                if meta_num is not None:
                    if "%" in row['meta']:
                        if valor_real < meta_num:
                            color = "🔴" if valor_real < meta_num * 0.9 else "🟡"
                    else:
                        if valor_real > meta_num:
                            color = "🔴" if valor_real > meta_num * 1.1 else "🟡"

                st.write(f"{color} Último valor registrado: {valor_real} ({ultimo_valor['fecha']})")
            else:
                st.write("⚪ Sin registros de seguimiento.")

            with st.expander("➕ Registrar avance"):
                with st.form(f"form_seg_{row['id']}", clear_on_submit=True):
                    valor_real = st.number_input("Valor real", step=0.01)
                    observaciones = st.text_area("Observaciones")
                    submitted = st.form_submit_button("Guardar")
                    if submitted:
                        supabase.table("seguimiento_objetivos").insert({
                            "objetivo_id": row["id"],
                            "valor_real": valor_real,
                            "observaciones": observaciones
                        }).execute()
                        st.success("✅ Avance registrado.")
                        st.experimental_rerun()

            st.divider()
    else:
        st.info("ℹ️ No hay objetivos definidos.")

    # =========================
    # Añadir nuevo objetivo
    # =========================
    st.markdown("### ➕ Añadir nuevo objetivo")
    with st.form("form_obj", clear_on_submit=True):
        nombre = st.text_input("Nombre del objetivo *")
        meta = st.text_input("Meta (ej: ≥ 90%) *")
        responsable = st.text_input("Responsable")
        fuente_datos = st.text_input("Fuente de datos")
        frecuencia = st.selectbox("Frecuencia", ["Mensual", "Trimestral", "Semestral", "Anual"])
        ano = st.number_input("Año", value=datetime.today().year, step=1)
        submitted = st.form_submit_button("Guardar")
        if submitted:
            supabase.table("objetivos_calidad").insert({
                "nombre": nombre,
                "meta": meta,
                "responsable": responsable,
                "fuente_datos": fuente_datos,
                "frecuencia": frecuencia,
                "ano": ano
            }).execute()
            st.success("✅ Objetivo añadido.")
            st.experimental_rerun()
      
