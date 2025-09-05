import streamlit as st

def alta_alumno(supabase, email, password, nombre, dni=None, apellidos=None, telefono=None, empresa_id=None, grupo_id=None):
    """Crea un usuario con rol alumno en Auth, lo inserta en 'usuarios' y crea su ficha en 'participantes'."""
    try:
        # Buscar si el usuario ya existe en Auth
        auth_user = None
        try:
            users_list = supabase.auth.admin.list_users()
            for u in users_list:
                if u.email.lower() == email.lower():
                    auth_user = u
                    break
        except Exception as e:
            st.error(f"❌ Error al listar usuarios en Auth: {e}")
            return False

        # Si no existe, crear en Auth
        if not auth_user:
            try:
                auth_res = supabase.auth.admin.create_user({
                    "email": email,
                    "password": password or "temporal123",
                    "email_confirm": True
                })
                auth_user = auth_res.user
            except Exception as e:
                st.error(f"❌ Error al crear usuario en Auth: {e}")
                return False

        # Insertar en tabla usuarios
        try:
            supabase.table("usuarios").insert({
                "auth_id": auth_user.id,
                "email": email,
                "rol": "alumno",
                "nombre": nombre,
                "empresa_id": empresa_id
            }).execute()
        except Exception as e:
            st.error(f"❌ Error al insertar en 'usuarios': {e}")
            return False

        # Insertar en tabla participantes
        try:
            supabase.table("participantes").insert({
                "email": email,
                "nombre": nombre,
                "apellidos": apellidos,
                "dni": dni,
                "telefono": telefono,
                "empresa_id": empresa_id,
                "grupo_id": grupo_id
            }).execute()
        except Exception as e:
            st.error(f"❌ Error al insertar en 'participantes': {e}")
            return False

        return True
    except Exception as e:
        st.error(f"❌ Error general en alta_alumno: {e}")
        return False
