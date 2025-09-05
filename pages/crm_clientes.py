import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 👥 Clientes CRM")
    st.caption("Base de clientes vinculada al módulo CRM.")
    st.divider()

    rol = session_state.role
    empresa_id = session_state.user.get("empresa_id")

    if rol not in ["admin", "gestor", "comercial"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # --- Cargar clientes (participantes) ---
    try:
        query = supabase.table("participantes").select("*")
        if rol == "gestor":
            query = query.eq("empresa_id", empresa_id)
        elif rol == "comercial":
            # Filtrar solo clientes con oportunidades asignadas a este comercial
            comercial_id = session_state.user.get("comercial_id")
            opps = supabase.table("crm_oportunidades").select("cliente_id").eq("comercial_id", comercial_id).execute()
            cliente_ids = list({o["cliente_id"] for o in (opps.data or [])})
            if cliente_ids:
                query = query.in_("id", cliente_ids)
            else:
                query = query.eq("id", None)  # vacío
        clientes = query.execute().data or []
    except Exception as e:
        st.error(f"❌ Error al cargar clientes: {e}")
        clientes = []

    # --- Filtros ---
    st.markdown("### 🔍 Filtros")
    col1, col2 = st.columns(2)
    filtro_nombre = col1.text_input("Filtrar por nombre")
    filtro_email = col2.text_input("Filtrar por email")

    if filtro_nombre:
        clientes = [c for c in clientes if filtro_nombre.lower() in (c.get("nombre") or "").lower()]
    if filtro_email:
        clientes = [c for c in clientes if filtro_email.lower() in (c.get("email") or "").lower()]

    if not clientes:
        st.info("No hay clientes que coincidan con los filtros.")
        return

    df = pd.DataFrame(clientes)
    st.dataframe(df[["nombre", "apellidos", "email", "telefono"]])

    st.divider()

    # --- Ficha de cliente ---
    st.markdown("### 📄 Ficha de cliente")
    for cliente in clientes:
        with st.expander(f"{cliente.get('nombre','')} {cliente.get('apellidos','')}"):
            st.write(f"**Email:** {cliente.get('email','')}")
            st.write(f"**Teléfono:** {cliente.get('telefono','')}")
            st.write(f"**DNI/NIF:** {cliente.get('dni','')}")
            st.write(f"**Fecha Alta:** {cliente.get('fecha_alta','')}")

            # --- Resumen de oportunidades ---
            st.markdown("#### 📂 Oportunidades")
            opps = supabase.table("crm_oportunidades").select("*").eq("cliente_id", cliente["id"]).execute().data or []
            if opps:
                df_opps = pd.DataFrame(opps)
                st.dataframe(df_opps[["titulo", "estado", "valor_estimado", "importe"]])
            else:
                st.info("No hay oportunidades registradas para este cliente.")

            # --- Resumen de tareas ---
            st.markdown("#### 📝 Tareas")
            tareas = supabase.table("crm_tareas").select("*").eq("cliente_id", cliente["id"]).execute().data or []
            if tareas:
                df_tareas = pd.DataFrame(tareas)
                st.dataframe(df_tareas[["descripcion", "estado", "fecha_vencimiento"]])
            else:
                st.info("No hay tareas registradas para este cliente.")

            # --- Resumen de comunicaciones ---
            st.markdown("#### 📬 Comunicaciones")
            comms = supabase.table("crm_comunicaciones").select("*").eq("cliente_id", cliente["id"]).execute().data or []
            if comms:
                df_comms = pd.DataFrame(comms)
                st.dataframe(df_comms[["tipo", "asunto", "fecha"]])
            else:
                st.info("No hay comunicaciones registradas para este cliente.")

            # --- Acciones rápidas ---
            st.markdown("#### ➕ Acciones rápidas")
            col_a, col_b, col_c = st.columns(3)
            if col_a.button("Nueva oportunidad", key=f"opp_{cliente['id']}"):
                st.session_state.page = "crm_oportunidades"
                st.session_state.cliente_preseleccionado = cliente["id"]
                st.rerun()
            if col_b.button("Nueva tarea", key=f"tarea_{cliente['id']}"):
                st.session_state.page = "crm_tareas"
                st.session_state.cliente_preseleccionado = cliente["id"]
                st.rerun()
            if col_c.button("Nueva comunicación", key=f"comm_{cliente['id']}"):
                st.session_state.page = "crm_comunicaciones"
                st.session_state.cliente_preseleccionado = cliente["id"]
                st.rerun()
              
