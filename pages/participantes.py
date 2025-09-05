import streamlit as st
import pandas as pd
from services.alumnos import alta_alumno
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 🧑‍🎓 Participantes")
    st.caption("Gestión de participantes/alumnos y vinculación con empresas y grupos.")
    st.divider()

    # 🔒 Protección por rol
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    try:
        if session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
            empresas_res = supabase.table("empresas").select("id,nombre").eq("id", empresa_id).execute()
        else:
            empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las empresas: {e}")
        empresas_dict = {}

    try:
        if session_state.role == "gestor":
            grupos_res = supabase.table("grupos").select("id,codigo_grupo").eq("empresa_id", empresa_id).execute()
        else:
            grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in (grupos_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos: {e}")
        grupos_dict = {}

    try:
        if session_state.role == "gestor":
            part_res = supabase.table("participantes").select("*").eq("empresa_id", empresa_id).execute()
        else:
            part_res = supabase.table("participantes").select("*").execute()
        df_part = pd.DataFrame(part_res.data or [])
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los participantes: {e}")
        df_part = pd.DataFrame()

    # Solo el admin puede crear participantes
    if session_state.role == "admin":
        st.markdown("### ➕ Añadir Participante")
        with st.form("crear_participante", clear_on_submit=True):
            nombre = st.text_input("Nombre *")
            apellidos = st.text_input("Apellidos")
            dni = st.text_input("DNI/NIF")
            email = st.text_input("Email *")
            telefono = st.text_input("Teléfono")
            empresa_sel = st.selectbox("Empresa", sorted(list(empresas_dict.keys())) if empresas_dict else [])
            grupo_sel = st.selectbox("Grupo", sorted(list(grupos_dict.keys())) if grupos_dict else [])
            submitted = st.form_submit_button("➕ Añadir Participante")

        if submitted:
            if not nombre or not email:
                st.error("⚠️ Nombre y email son obligatorios.")
            else:
                creado = alta_alumno(
                    supabase,
                    email=email,
                    password=None,
                    nombre=nombre,
                    dni=dni,
                    apellidos=apellidos,
                    telefono=telefono,
                    empresa_id=empresas_dict.get(empresa_sel),
                    grupo_id=grupos_dict.get(grupo_sel)
                )
                if creado:
                    st.success("✅ Participante creado correctamente.")
                    st.rerun()

    st.divider()

    if not df_part.empty:
        for _, row in df_part.iterrows():
            with st.expander(f"{row.get('nombre','')} {row.get('apellidos','')}"):
                st.write(f"**Email:** {row.get('email','')}")
                st.write(f"**Teléfono:** {row.get('telefono','')}")
                st.write(f"**DNI/NIF:** {row.get('dni','')}")
                st.write(f"**Empresa ID:** {row.get('empresa_id','')}")
                st.write(f"**Grupo ID:** {row.get('grupo_id','')}")
                st.write(f"**Fecha Alta:** {row.get('fecha_alta','')}")

                if session_state.role == "admin":
                    with st.form(f"edit_part_{row['id']}", clear_on_submit=True):
                        nuevo_nombre = st.text_input("Nombre", value=row.get("nombre", ""))
                        nuevos_apellidos = st.text_input("Apellidos", value=row.get("apellidos", ""))
                        nuevo_email = st.text_input("Email", value=row.get("email", ""))
                        guardar = st.form_submit_button("💾 Guardar cambios")

                    if guardar:
                        try:
                            if nuevo_email != row.get("email", ""):
                                usuario_res = supabase.table("usuarios").select("auth_id").eq("email", row.get("email", "")).execute()
                                if usuario_res.data:
                                    auth_id = usuario_res.data[0]["auth_id"]
                                    try:
                                        supabase.auth.admin.update_user_by_id(auth_id, {"email": nuevo_email})
                                        st.info("📧 Email actualizado en Auth.")
                                    except Exception as e:
                                        st.error(f"❌ No se pudo actualizar el email en Auth: {e}")
                                    try:
                                        supabase.table("usuarios").update({"email": nuevo_email}).eq("auth_id", auth_id).execute()
                                        st.info("📧 Email actualizado en tabla 'usuarios'.")
                                    except Exception as e:
                                        st.error(f"❌ No se pudo actualizar el email en 'usuarios': {e}")

                            supabase.table("participantes").update({
                                "nombre": nuevo_nombre,
                                "apellidos": nuevos_apellidos,
                                "email": nuevo_email
                            }).eq("id", row["id"]).execute()
                            st.success("✅ Cambios guardados.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al actualizar: {e}")
