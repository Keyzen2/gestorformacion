import streamlit as st
import random
import string
import uuid
from datetime import datetime

def alta_alumno(supabase,
                *,
                email: str,
                password: str = None,
                nombre: str,
                dni: str = None,
                apellidos: str = None,
                telefono: str = None,
                empresa_id: str = None,
                grupo_id: str = None) -> bool:
    """
    Crea un alumno en Auth, en la tabla usuarios y en participantes.
    Si falla un paso, revierte los anteriores.
    Devuelve True si todo OK, o lanza excepción para que la UI la muestre.
    """

    # 1. Validaciones mínimas
    if not email or not nombre:
        raise ValueError("Email y nombre son obligatorios para crear un alumno.")

    # 2. Generar contraseña si no se proporciona
    if not password:
        alphabet = string.ascii_letters + string.digits
        password = "".join(random.choices(alphabet, k=12))

    auth_id = None
    try:
        # 3. Crear usuario en Auth
        auth_res = supabase.auth.admin.create_user({
            "email":        email,
            "password":     password,
            "email_confirm": True
        })
        if not getattr(auth_res, "user", None):
            raise RuntimeError("No se pudo crear el usuario en Auth.")
        auth_id = auth_res.user.id

        # 4. Insert en tabla `usuarios`
        usuario_payload = {
            "id":         str(uuid.uuid4()),
            "auth_id":    auth_id,
            "email":      email,
            "nombre":     nombre,
            "nombre_completo": f"{nombre} {apellidos or ''}".strip(),
            "rol":        "alumno",
            "created_at": datetime.utcnow().isoformat()
        }
        if empresa_id:
            usuario_payload["empresa_id"] = empresa_id
        if grupo_id:
            usuario_payload["grupo_id"] = grupo_id

        u_res = supabase.table("usuarios").insert(usuario_payload).execute()
        if u_res.error or not u_res.data:
            raise RuntimeError(f"Error al insertar en usuarios: {u_res.error or 'sin data'}")

        # 5. Insert en tabla `participantes`
        participante_payload = {
            "id":           str(uuid.uuid4()),
            "email":        email,
            "nombre":       nombre,
            "apellidos":    apellidos or "",
            "dni":          dni or "",
            "telefono":     telefono or "",
            "created_at":   datetime.utcnow().isoformat()
        }
        if empresa_id:
            participante_payload["empresa_id"] = empresa_id
        if grupo_id:
            participante_payload["grupo_id"] = grupo_id

        p_res = supabase.table("participantes").insert(participante_payload).execute()
        if p_res.error or not p_res.data:
            raise RuntimeError(f"Error al insertar en participantes: {p_res.error or 'sin data'}")

        return True

    except Exception as exc:
        # 6. Rollback en Auth si creamos el usuario allí
        if auth_id:
            try:
                supabase.auth.admin.delete_user(auth_id)
            except Exception:
                pass
        # Propaga la excepción para que la UI la capture con st.error()
        raise
