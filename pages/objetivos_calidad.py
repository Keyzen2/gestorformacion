import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("🎯 Objetivos de Calidad (ISO 9001)")
    st.caption("Definición, seguimiento y evaluación de objetivos anuales de calidad para el centro de formación.")
    st.divider()

    # 🔒 Protección por rol y módulo ISO activo
    if session_state.role == "gestor":
        empresa_id = session_state.user.get("empresa_id")
        empresa_res = supabase.table("empresas").select("iso_activo", "iso_inicio", "iso_fin").eq("id", empresa_id).execute()
        empresa = empresa_res.data[0] if empresa_res.data else {}
        hoy = datetime.today().date()

        iso_permitido = (
            empresa.get("iso_activo") and
            (empresa.get("iso_inicio") is None or pd.to_datetime(empresa["iso_inicio"]).date() <= hoy) and
            (empresa.get("iso_fin") is None or pd.to_datetime(empresa["iso_fin"]).date() >= hoy)
        )

        if not iso_permitido:
            st.warning("🔒 Tu empresa no tiene activado el módulo ISO 9001.")
            st.stop()

    elif session_state.role != "admin":
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # =========================
    # Cargar datos
    # =========================
    try:
        if session_state.role == "gestor":
            df_obj = pd.DataFrame(supabase.table("objetivos_calidad").select("*").eq("empresa_id", empresa_id).execute().data or [])
            df_seg = pd.DataFrame(supabase.table("seguimiento_objetivos").select("*").eq("empresa_id", empresa_id).execute().data or [])
        else:
            df_obj = pd.DataFrame(supabase.table("objetivos_calidad").select("*").execute().data or [])
            df_seg = pd.DataFrame(supabase.table("seguimiento_objetivos").select("*").execute().data or [])
    except Exception as e:
        st.error(f"❌ Error al cargar los datos: {e}")
        return

    # =========================
    # Mostrar objetivos
    # =========================
    st.markdown("### 📋 Objetivos definidos")
    if not df_obj.empty:
        for _, row in df_obj.iterrows():
            st.markdown(f"**{row['nombre']}** — Meta: {row['meta']} — Responsable: {row.get('responsable','')}")
            st.caption(f"Fuente: {row.get('fuente_datos','')} | Frecuencia: {row.get('frecuencia','')} | Año: {row.get('ano','')}")

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
                        seguimiento_data = {
                            "objetivo_id": row["id"],
                            "valor_real": valor_real,
                            "observaciones": observaciones
                        }
                        if session_state.role == "gestor":
                            seguimiento_data["empresa_id"] = empresa_id
                        supabase.table("seguimiento_objetivos").insert(seguimiento_data).execute()
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
            objetivo_data = {
                "nombre": nombre,
                "meta": meta,
                "responsable": responsable,
                "fuente_datos": fuente_datos,
                "frecuencia": frecuencia,
                "ano": ano
            }
            if session_state.role == "gestor":
                objetivo_data["empresa_id"] = empresa_id
            supabase.table("objetivos_calidad").insert(objetivo_data).execute()
            st.success("✅ Objetivo añadido.")
            st.experimental_rerun()
      
