import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 📂 Oportunidades CRM")
    st.caption("Gestión de oportunidades comerciales.")
    st.divider()

    rol = session_state.role
    empresa_id = session_state.user.get("empresa_id")

    if rol not in ["admin", "gestor", "comercial"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # --- Cargar comerciales para filtros y asignación ---
    comerciales_dict = {}
    try:
        if rol == "gestor":
            comerciales_res = supabase.table("comerciales").select("id,nombre").eq("empresa_id", empresa_id).execute()
        else:
            comerciales_res = supabase.table("comerciales").select("id,nombre").execute()
        comerciales_dict = {c["nombre"]: c["id"] for c in (comerciales_res.data or [])}
    except Exception as e:
        st.error(f"❌ Error al cargar comerciales: {e}")

    # --- Filtros ---
    st.markdown("### 🔍 Filtros")
    col1, col2 = st.columns(2)
    filtro_estado = col1.selectbox("Estado", ["Todos", "Abierta", "Ganada", "Perdida"])
    filtro_comercial = col2.selectbox("Comercial", ["Todos"] + list(comerciales_dict.keys()))

    # --- Cargar oportunidades ---
    try:
        query = supabase.table("crm_oportunidades").select("*")
        if rol == "gestor":
            query = query.eq("empresa_id", empresa_id)
        elif rol == "comercial":
            comercial_id = session_state.user.get("comercial_id")
            query = query.eq("comercial_id", comercial_id)

        oportunidades = query.execute().data or []

        # Aplicar filtros
        if filtro_estado != "Todos":
            oportunidades = [o for o in oportunidades if o.get("estado") == filtro_estado]
        if filtro_comercial != "Todos":
            oportunidades = [o for o in oportunidades if o.get("comercial_id") == comerciales_dict[filtro_comercial]]

        if oportunidades:
            df = pd.DataFrame(oportunidades)
            st.dataframe(df[["titulo", "valor_estimado", "importe", "estado", "fecha_cierre_prevista", "fecha_cierre_real"]])
        else:
            st.info("No hay oportunidades registradas.")
    except Exception as e:
        st.error(f"❌ Error al cargar oportunidades: {e}")
        oportunidades = []

    st.divider()

    # --- Nueva oportunidad ---
    st.markdown("### ➕ Nueva oportunidad")
    with st.form("nueva_oportunidad", clear_on_submit=True):
        titulo = st.text_input("Título *")
        valor_estimado = st.number_input("Valor estimado (€)", min_value=0.0, step=100.0)
        estado = st.selectbox("Estado", ["Abierta", "Ganada", "Perdida"])
        fecha_prevista = st.date_input("Fecha de cierre prevista", value=datetime.today())
        importe = st.number_input("Importe real (€)", min_value=0.0, step=100.0)
        fecha_real = st.date_input("Fecha de cierre real", value=datetime.today())
        if rol in ["gestor", "admin"]:
            comercial_sel = st.selectbox("Asignar a comercial", list(comerciales_dict.keys()))
            comercial_id = comerciales_dict.get(comercial_sel)
        else:
            comercial_id = session_state.user.get("comercial_id")
        enviar = st.form_submit_button("Guardar")

    if enviar:
        if not titulo:
            st.warning("⚠️ El título es obligatorio.")
        else:
            try:
                supabase.table("crm_oportunidades").insert({
                    "empresa_id": empresa_id if rol != "admin" else None,
                    "titulo": titulo,
                    "valor_estimado": valor_estimado,
                    "estado": estado,
                    "fecha_cierre_prevista": fecha_prevista.isoformat(),
                    "importe": importe if estado == "Ganada" else None,
                    "fecha_cierre_real": fecha_real.isoformat() if estado != "Abierta" else None,
                    "comercial_id": comercial_id
                }).execute()
                st.success("✅ Oportunidad creada.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al crear oportunidad: {e}")

    st.divider()

    # --- Estadísticas ---
    st.markdown("### 📊 Estadísticas")
    try:
        df = pd.DataFrame(oportunidades)
        if not df.empty:
            df_ganadas = df[df["estado"] == "Ganada"]
            if not df_ganadas.empty:
                df_ganadas["mes"] = pd.to_datetime(df_ganadas["fecha_cierre_real"]).dt.to_period("M")
                mensual = df_ganadas.groupby("mes").agg(
                    oportunidades_cerradas=("id", "count"),
                    total_ganado=("importe", "sum")
                ).reset_index()
                st.markdown("#### 📅 Mensual")
                st.dataframe(mensual)

                anual = df_ganadas.groupby(pd.to_datetime(df_ganadas["fecha_cierre_real"]).dt.year).agg(
                    oportunidades_cerradas=("id", "count"),
                    total_ganado=("importe", "sum")
                ).reset_index().rename(columns={"fecha_cierre_real": "año"})
                st.markdown("#### 📆 Anual")
                st.dataframe(anual)
            else:
                st.info("No hay oportunidades ganadas para mostrar estadísticas.")
        else:
            st.info("No hay datos para estadísticas.")
    except Exception as e:
        st.error(f"❌ Error al calcular estadísticas: {e}")
      
