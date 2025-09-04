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
            st.error
