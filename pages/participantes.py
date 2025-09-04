import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.markdown("## 🧑‍🎓 Participantes")
    st.caption("Gestión de participantes/alumnos y vinculación con empresas y grupos.")
    st.divider()

    # =========================
    # Cargar empresas y grupos
    # =========================
    try:
        empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las empresas: {e}")
        empresas_dict = {}

    try:
        grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in (grupos_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos: {e}")
        grupos_dict = {}

    # =========================
    # Cargar participantes
    # =========================
    try:
        part_res = supabase.table("participantes").select("*").execute()
        df_part = pd.DataFrame(part_res.data or [])
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los participantes: {e}")
        df_part = pd.DataFrame()

    # =========================
    # Formulario para añadir participante
    # =========================
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
            try:
                # 1. Buscar usuario en Auth
                auth_user = None
                try:
                    users_list = supabase.auth.admin.list_users()
                    for u in users_list.users:
                        if u.email.lower() == email.lower():
                            auth_user = u
                            break
                except Exception as e:
                    st.error(f"⚠️ No se pudo consultar Auth: {e}")
                    return

                # 2. Si no existe, crearlo
                if not auth_user:
                    try:
                        new_user = supabase.auth.admin.create_user({
                            "email": email,
                            "password": "Temporal1234",  # Contraseña temporal
                            "email_confirm": True,
                            "user_metadata": {"rol": "alumno"}
                        })
                        auth_id = new_user.user.id
                        st.info(f"👤 Usuario creado en Auth con ID {auth_id}")
                    except Exception as e:
                        st.error(f"❌ No se pudo crear el usuario en Auth: {e}")
                        return
                else:
                    auth_id = auth_user.id
                    st.info(f"👤 Usuario ya existente en Auth con ID {auth_id}")

                # 3. Insertar en tabla usuarios si no existe
                try:
                    existe_usuario = supabase.table("usuarios").select("id").eq("email", email).execute()
                    if not existe_usuario.data:
                        supabase.table("usuarios").insert({
                            "auth_id": auth_id,
                            "email": email,
                            "rol": "alumno",
                            "dni": dni,
                            "nombre": nombre
                        }).execute()
                        st.success("✅ Usuario añadido a la tabla 'usuarios'.")
                except Exception as e:
                    st.error(f"❌ Error al insertar en usuarios: {e}")

                # 4. Insertar en participantes
                try:
                    supabase.table("participantes").insert({
                        "nombre": nombre,
                        "apellidos": apellidos,
                        "dni": dni,
                        "email": email,
                        "telefono": telefono,
                        "empresa_id": empresas_dict.get(empresa_sel),
                        "grupo_id": grupos_dict.get(grupo_sel)
                    }).execute()
                    st.success(f"✅ Participante '{nombre}' añadido correctamente.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Error al insertar en participantes: {e}")

            except Exception as e:
                st.error(f"❌ Error general al vincular: {e}")

    st.divider()

    # =========================
    # Listado y edición
    # =========================
    if not df_part.empty:
        for _, row in df_part.iterrows():
            with st.expander(f"{row.get('nombre','')} {row.get('apellidos','')}"):
                st.write(row)
                with st.form(f"edit_part_{row['id']}", clear_on_submit=True):
                    nuevo_nombre = st.text_input("Nombre", value=row.get("nombre", ""))
                    nuevos_apellidos = st.text_input("Apellidos", value=row.get("apellidos", ""))
                    nuevo_email = st.text_input("Email", value=row.get("email", ""))
                    guardar = st.form_submit_button("💾 Guardar cambios")

                if guardar:
                    try:
                        # Si el email ha cambiado, actualizar en Auth y en usuarios
                        if nuevo_email != row.get("email", ""):
                            # Buscar auth_id en usuarios
                            usuario_res = supabase.table("usuarios").select("auth_id").eq("email", row.get("email", "")).execute()
                            if usuario_res.data:
                                auth_id = usuario_res.data[0]["auth_id"]
                                # Actualizar en Auth
                                try:
                                    supabase.auth.admin.update_user_by_id(auth_id, {"email": nuevo_email})
                                    st.info("📧 Email actualizado en Auth.")
                                except Exception as e:
                                    st.error(f"❌ No se pudo actualizar el email en Auth: {e}")
                                # Actualizar en usuarios
                                try:
                                    supabase.table("usuarios").update({"email": nuevo_email}).eq("auth_id", auth_id).execute()
                                    st.info("📧 Email actualizado en tabla 'usuarios'.")
                                except Exception as e:
                                    st.error(f"❌ No se pudo actualizar el email en 'usuarios': {e}")

                        # Actualizar en participantes
                        supabase.table("participantes").update({
                            "nombre": nuevo_nombre,
                            "apellidos": nuevos_apellidos,
                            "email": nuevo_email
                        }).eq("id", row["id"]).execute()
                        st.success("✅ Cambios guardados.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"❌ Error al actualizar: {e}")
