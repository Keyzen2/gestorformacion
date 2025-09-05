import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 📈 Panel CRM")
    st.caption("Resumen de actividad comercial y accesos rápidos.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    # --- KPIs ---
    col1, col2, col3, col4 = st.columns(4)

    # Clientes
    clientes_res = supabase.table("participantes").select("id").eq("empresa_id", empresa_id).execute()
    total_clientes = len(clientes_res.data or [])
    col1.metric("👥 Clientes", total_clientes)

    # Oportunidades
    oportunidades_res = supabase.table("crm_oportunidades").select("*").eq("empresa_id", empresa_id).execute()
    oportunidades = oportunidades_res.data or []
    abiertas = [o for o in oportunidades if o.get("estado") == "Abierta"]
    ganadas = [o for o in oportunidades if o.get("estado") == "Ganada"]
    col2.metric("📂 Oportunidades abiertas", len(abiertas))
    col3.metric("🏆 Oportunidades ganadas", len(ganadas))

    # Tareas pendientes
    tareas_res = supabase.table("crm_tareas").select("*").eq("empresa_id", empresa_id).execute()
    tareas = tareas_res.data or []
    pendientes = [t for t in tareas if t.get("estado") != "Completada"]
    col4.metric("📝 Tareas pendientes", len(pendientes))

    st.divider()

    # --- Últimas comunicaciones ---
    st.markdown("### 📬 Últimas comunicaciones")
    comms_res = supabase.table("crm_comunicaciones").select("*").eq("empresa_id", empresa_id).order("fecha", desc=True).limit(5).execute()
    comunicaciones = comms_res.data or []
    if comunicaciones:
        df = pd.DataFrame(comunicaciones)
        st.table(df[["tipo", "asunto", "fecha"]])
    else:
        st.info("No hay comunicaciones registradas.")

    st.divider()

    # --- Accesos rápidos ---
    st.markdown("### 🚀 Accesos rápidos")
    col_a, col_b, col_c = st.columns(3)
    col_a.page_link("pages/crm_clientes.py", label="👥 Clientes", icon="👥")
    col_b.page_link("pages/crm_oportunidades.py", label="📂 Oportunidades", icon="📂")
    col_c.page_link("pages/crm_tareas.py", label="📝 Tareas", icon="📝")
    col_a.page_link("pages/crm_comunicaciones.py", label="📬 Comunicaciones", icon="📬")
    col_b.page_link("pages/crm_campanas.py", label="📢 Campañas", icon="📢")
  
