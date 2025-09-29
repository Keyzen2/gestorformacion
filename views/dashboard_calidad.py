import streamlit as st
import pandas as pd
from datetime import datetime

def render(supabase, session_state):
    st.subheader("📊 Dashboard de Calidad ISO 9001")
    st.caption("Panel visual con KPIs, objetivos y seguimiento del sistema de gestión de calidad.")
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
            df_nc = pd.DataFrame(supabase.table("no_conformidades").select("*").eq("empresa_id", empresa_id).execute().data or [])
            df_ac = pd.DataFrame(supabase.table("acciones_correctivas").select("*").eq("empresa_id", empresa_id).execute().data or [])
            df_aud = pd.DataFrame(supabase.table("auditorias").select("*").eq("empresa_id", empresa_id).execute().data or [])
            df_obj = pd.DataFrame(supabase.table("objetivos_calidad").select("*").eq("empresa_id", empresa_id).execute().data or [])
            df_seg = pd.DataFrame(supabase.table("seguimiento_objetivos").select("*").eq("empresa_id", empresa_id).execute().data or [])
        else:
            df_nc = pd.DataFrame(supabase.table("no_conformidades").select("*").execute().data or [])
            df_ac = pd.DataFrame(supabase.table("acciones_correctivas").select("*").execute().data or [])
            df_aud = pd.DataFrame(supabase.table("auditorias").select("*").execute().data or [])
            df_obj = pd.DataFrame(supabase.table("objetivos_calidad").select("*").execute().data or [])
            df_seg = pd.DataFrame(supabase.table("seguimiento_objetivos").select("*").execute().data or [])
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # Botón de actualización automática
    # =========================
    if st.button("🔄 Actualizar indicadores automáticos"):
        try:
            # NC abiertas
            objetivo_nc = [o for o in df_obj.to_dict("records") if "No Conformidades" in o["nombre"]]
            if objetivo_nc:
                valor = len(df_nc[df_nc["estado"] == "Abierta"])
                supabase.table("seguimiento_objetivos").insert({
                    "objetivo_id": objetivo_nc[0]["id"],
                    "valor_real": valor,
                    "empresa_id": empresa_id if session_state.role == "gestor" else None,
                    "observaciones": "Actualización automática desde dashboard"
                }).execute()

            # Tiempo medio de resolución NC
            objetivo_tiempo = [o for o in df_obj.to_dict("records") if "Tiempo medio" in o["nombre"]]
            if objetivo_tiempo and not df_nc.empty:
                df_nc_cerradas = df_nc[df_nc["fecha_cierre"].notna() & df_nc["fecha_detectada"].notna()]
                if not df_nc_cerradas.empty:
                    df_nc_cerradas["fecha_cierre"] = pd.to_datetime(df_nc_cerradas["fecha_cierre"], errors="coerce")
                    df_nc_cerradas["fecha_detectada"] = pd.to_datetime(df_nc_cerradas["fecha_detectada"], errors="coerce")
                    dias = (df_nc_cerradas["fecha_cierre"] - df_nc_cerradas["fecha_detectada"]).dt.days
                    valor = dias.mean()
                    supabase.table("seguimiento_objetivos").insert({
                        "objetivo_id": objetivo_tiempo[0]["id"],
                        "valor_real": valor,
                        "empresa_id": empresa_id if session_state.role == "gestor" else None,
                        "observaciones": "Actualización automática desde dashboard"
                    }).execute()

            # Acciones Correctivas cerradas
            objetivo_ac = [o for o in df_obj.to_dict("records") if "Acciones Correctivas" in o["nombre"]]
            if objetivo_ac:
                valor = len(df_ac[df_ac["estado"] == "Cerrada"])
                supabase.table("seguimiento_objetivos").insert({
                    "objetivo_id": objetivo_ac[0]["id"],
                    "valor_real": valor,
                    "empresa_id": empresa_id if session_state.role == "gestor" else None,
                    "observaciones": "Actualización automática desde dashboard"
                }).execute()

            # Cumplimiento plan de auditorías
            objetivo_aud = [o for o in df_obj.to_dict("records") if "plan de auditorías" in o["nombre"]]
            if objetivo_aud and not df_aud.empty:
                total = len(df_aud)
                cerradas = len(df_aud[df_aud["estado"] == "Cerrada"])
                valor = (cerradas / total * 100) if total > 0 else 0
                supabase.table("seguimiento_objetivos").insert({
                    "objetivo_id": objetivo_aud[0]["id"],
                    "valor_real": valor,
                    "empresa_id": empresa_id if session_state.role == "gestor" else None,
                    "observaciones": "Actualización automática desde dashboard"
                }).execute()

            st.success("✅ Indicadores automáticos actualizados y guardados en seguimiento.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar indicadores: {e}")

    # =========================
    # Filtro por fechas
    # =========================
    st.markdown("### 📅 Filtro por periodo")
    col1, col2 = st.columns(2)
    fecha_inicio = col1.date_input("Desde", datetime(datetime.now().year, 1, 1))
    fecha_fin = col2.date_input("Hasta", datetime.today())

    def filtrar(df, campo):
        if campo in df.columns:
            df[campo] = pd.to_datetime(df[campo], errors="coerce")
            return df[(df[campo] >= pd.to_datetime(fecha_inicio)) & (df[campo] <= pd.to_datetime(fecha_fin))]
        return df

    df_nc = filtrar(df_nc, "fecha_detectada")
    df_ac = filtrar(df_ac, "fecha_inicio")
    df_aud = filtrar(df_aud, "fecha")

    # =========================
    # KPIs principales
    # =========================
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("NC Abiertas", len(df_nc[df_nc["estado"] == "Abierta"]) if "estado" in df_nc else 0)
    col2.metric("NC Cerradas", len(df_nc[df_nc["estado"] == "Cerrada"]) if "estado" in df_nc else 0)
    col3.metric("AC Cerradas", len(df_ac[df_ac["estado"] == "Cerrada"]) if "estado" in df_ac else 0)
    col4.metric("Auditorías", len(df_aud))

    st.divider()

    # =========================
    # Objetivos de Calidad
    # =========================
    st.markdown("### 🎯 Objetivos de Calidad y Cumplimiento")
    if not df_obj.empty:
        for _, obj in df_obj.iterrows():
            st.markdown(f"**{obj['nombre']}** — Meta: {obj['meta']} — Responsable: {obj.get('responsable','')}")
            segs = df_seg[df_seg["objetivo_id"] == obj["id"]]
            if not segs.empty:
                ultimo = segs.sort_values("fecha", ascending=False).iloc[0]
                valor_real = ultimo["valor_real"]
                meta_num = None
                try:
                    meta_num = float(''.join([c for c in obj['meta'] if c.isdigit() or c == '.']))
                except:
                    pass

                color = "🟢"
                if meta_num is not None:
                    if "%" in obj['meta']:
                        if valor_real < meta_num:
                            color = "🔴" if valor_real < meta_num * 0.9 else "🟡"
                    else:
                        if valor_real > meta_num:
                            color = "🔴" if valor_real > meta_num * 1.1 else "🟡"

                st.write(f"{color} Último valor: {valor_real} ({ultimo['fecha']})")
            else:
                st.write("⚪ Sin registros de seguimiento.")
            st.divider()
    else:
        st.info("ℹ️ No hay objetivos definidos.")

    # =========================
    # Gráficos nativos
    # =========================
    if "estado" in df_nc.columns:
        st.markdown("#### Distribución de No Conformidades por Estado")
        st.bar_chart(df_nc["estado"].value_counts())

    if "estado" in df_ac.columns:
        st.markdown("#### Distribución de Acciones Correctivas por Estado")
        st.bar_chart(df_ac["estado"].value_counts())

    if "tipo" in df_aud.columns:
        st.markdown("#### Auditorías por Tipo")
        st.bar_chart(df_aud["tipo"].value_counts())

    # =========================
    # Tablas de detalle
    # =========================
    with st.expander("📋 No Conformidades"):
        st.dataframe(df_nc)
    with st.expander("🛠️ Acciones Correctivas"):
        st.dataframe(df_ac)
    with st.expander("📋 Auditorías"):
        st.dataframe(df_aud)
    with st.expander("🎯 Objetivos de Calidad"):
        st.dataframe(df_obj)
    with st.expander("📈 Seguimiento de Objetivos"):
        st.dataframe(df_seg)

    
