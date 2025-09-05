# services/alumnos.py
import streamlit as st

def alta_alumno(supabase, email, password, nombre, dni=None, apellidos=None, telefono=None, empresa_id=None, grupo_id=None):
    """Crea un usuario con rol alumno en Auth, lo inserta en 'usuarios' y crea su ficha en 'participantes'."""
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
            return False

        # 2. Si no existe, crearlo
        if not auth_user:
            try:
                new_user = supabase.auth.admin.create_user({
                    "email": email,
                    "password": password or "Temporal1234",
                    "email_confirm": True,
                    "user_metadata": {"rol": "alumno"}
                })
                auth_id = new_user.user.id
                st.info(f"👤 Usuario creado en Auth con ID {auth_id}")
            except Exception as e:
                st.error(f"❌ No se pudo crear el usuario en Auth: {e}")
                return False
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
            return False

        # 4. Insertar en participantes si no existe
        try:
            existe_part = supabase.table("participantes").select("id").eq("email", email).execute()
            if not existe_part.data:
                supabase.table("participantes").insert({
                    "nombre": nombre,
                    "apellidos": apellidos,
                    "dni": dni,
                    "email": email,
                    "telefono": telefono,
                    "empresa_id": empresa_id,
                    "grupo_id": grupo_id
                }).execute()
                st.success("✅ Participante añadido correctamente.")
        except Exception as e:
            st.error(f"❌ Error al insertar en participantes: {e}")
            return False

        return True

    except Exception as e:
        st.error(f"❌ Error general al dar de alta al alumno: {e}")
        return False
