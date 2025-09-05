import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 👨‍🏫 Grupos")
    st.caption("Gestión de grupos de formación y su vinculación con empresas y acciones formativas.")
    st.divider()

    # 🔒 Protección por rol
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    try:
        empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las empresas: {e}")
        empresas_dict = {}

    try:
        acciones_res = supabase.table("acciones_formativas").select("id,nombre").execute()
        acciones_dict = {a["nombre"]: a["id"] for a in (acciones_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las acciones formativas: {e}")
        acciones_dict = {}

    try:
        if session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
            grupos_res = supabase.table("grupos").select("*").eq("empresa_id", empresa_id).execute()
        else:
            grupos_res = supabase.table("grupos").select("*").execute()
        df_grupos = pd.DataFrame(grupos_res.data or [])
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos: {e}")
        df_grupos = pd.DataFrame()

    col1, col2 = st.columns(2)
    col1.metric("Total grupos", len(df_grupos))
    col2.metric("Participantes previstos", int(df_grupos.get("n_participantes_previstos", pd.Series()).sum()) if "n_participantes_previstos" in df_grupos.columns else 0)
    st.divider()

    if not df_grupos.empty:
        search_query = st.text_input("🔍 Buscar por código, empresa o acción formativa")
        if search_query:
            sq = search_query.lower()
            for col in ["codigo_grupo", "empresa_nombre", "accion_formativa_nombre"]:
                if col not in df_grupos.columns:
                    df_grupos[col] = ""
            df_grupos = df_grupos[
                df_grupos["codigo_grupo"].str.lower().str.contains(sq) |
                df_grupos["empresa_nombre"].str.lower().str.contains(sq) |
                df_grupos["accion_formativa_nombre"].str.lower().str.contains(sq)
            ]
    st.divider()

    # Solo el admin puede crear grupos
    if session_state.role == "admin":
        st.markdown("### ➕ Crear Grupo")
        with st.form("crear_grupo", clear_on_submit=True):
            codigo_grupo = st.text_input("Código del grupo *")
            empresa_sel = st.selectbox("Empresa", sorted(list(empresas_dict.keys())) if empresas_dict else [])
            accion_sel = st.selectbox("Acción formativa", sorted(list(acciones_dict.keys())) if acciones_dict else [])
            fecha_inicio = st.date_input("Fecha inicio")
            fecha_fin = st.date_input("Fecha fin")
            localidad = st.text_input("Localidad")
            provincia = st.text_input("Provincia")
            cp = st.text_input("Código postal")
            n_previstos = st.number_input("Nº participantes previstos", min_value=0, step=1)
            observaciones = st.text_area("Observaciones")
            submitted_new = st.form_submit_button("➕ Crear Grupo")

        if submitted_new:
            if not codigo_grupo:
                st.error("⚠️ El código del grupo es obligatorio.")
            else:
                try:
                    supabase.table("grupos").insert({
                        "codigo_grupo": codigo_grupo,
                        "empresa_id": empresas_dict.get(empresa_sel),
                        "accion_formativa_id": acciones_dict.get(accion_sel),
                        "fecha_inicio": fecha_inicio.isoformat() if fecha_inicio else None,
                        "fecha_fin": fecha_fin.isoformat() if fecha_fin else None,
                        "localidad": localidad,
                        "provincia": provincia,
                        "cp": cp,
                        "n_participantes_previstos": int(n_previstos),
                        "observaciones": observaciones
                    }).execute()
                    st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear el grupo: {e}")

    st.divider()

    if not df_grupos.empty:
        for _, row in df_grupos.iterrows():
            with st.expander(f"{row.get('codigo_grupo','')}"):
                st.write(f"**Empresa:** {row.get('empresa_nombre','')}")
                st.write(f"**Acción formativa:** {row.get('accion_formativa_nombre','')}")
                st.write(f"**Fechas:** {row.get('fecha_inicio','')} → {row.get('fecha_fin','')}")
                st.write(f"**Localidad:** {row.get('localidad','')}")
                st.write(f"**Provincia:** {row.get('provincia','')}")
                st.write(f"**CP:** {row.get('cp','')}")
                st.write(f"**Participantes previstos:** {row.get('n_participantes_previstos','')}")
                st.write(f"**Observaciones:** {row.get('observaciones','')}")

                if session_state.role == "admin":
                    col1, col2 = st.columns(2)

                    if f"edit_done_{row['id']}" not in st.session_state:
                        st.session_state[f"edit_done_{row['id']}"] = False

                    with col1:
                        with st.form(f"edit_grupo_{row['id']}", clear_on_submit=True):
                            nuevo_codigo = st.text_input("Código del grupo", value=row.get("codigo_grupo",""))
                            nueva_empresa = st.selectbox(
                                "Empresa",
                                sorted(list(empresas_dict.keys())),
                                index=sorted(list(empresas_dict.keys())).index(row.get("empresa_nombre","")) if row.get("empresa_nombre","") in empresas_dict else 0
                            )
                            nueva_accion = st.selectbox(
                                "Acción formativa",
                                sorted(list(acciones_dict.keys())),
                                index=sorted(list(acciones_dict.keys())).index(row.get("accion_formativa_nombre","")) if row.get("accion_formativa_nombre","") in acciones_dict else 0
                            )
                            guardar = st.form_submit_button("💾 Guardar cambios")

                        if guardar and not st.session_state[f"edit_done_{row['id']}"]:
                            try:
                                supabase.table("grupos").update({
                                    "codigo_grupo": nuevo_codigo,
                                    "empresa_id": empresas_dict.get(nueva_empresa),
                                    "accion_formativa_id": acciones_dict.get(nueva_accion)
                                }).eq("id", row["id"]).execute()
                                st.session_state[f"edit_done_{row['id']}"] = True
                                st.success("✅ Cambios guardados correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al actualizar: {e}")

                    with col2:
                        confirmar = st.checkbox("Confirmar eliminación", key=f"confirm_{row['id']}")
                        if st.button("🗑️ Eliminar", key=f"delete_{row['id']}") and confirmar:
                            try:
                                supabase.table("grupos").delete().eq("id", row["id"]).execute()
                                st.success("✅ Grupo eliminado correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al eliminar: {e}")
                            
