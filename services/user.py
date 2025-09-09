# services/users.py

from datetime import datetime

def create_user(supabase, *, email, password, nombre, rol, empresa_id=None, grupo_id=None):
    """Crea en Auth y en tabla usuarios. Si falla, revierte Auth."""
    auth_res = supabase.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True
    })
    if not auth_res.user:
        raise RuntimeError("Error al crear usuario en Auth")

    auth_id = auth_res.user.id
    payload = {
        "auth_id": auth_id,
        "email": email,
        "nombre": nombre,
        "rol": rol,
        "created_at": datetime.utcnow().isoformat()
    }
    if rol == "gestor":
        payload["empresa_id"] = empresa_id
    if rol == "alumno":
        payload["grupo_id"] = grupo_id

    db_res = supabase.table("usuarios").insert(payload).execute()
    if db_res.error:
        # rollback Auth
        supabase.auth.admin.delete_user(auth_id)
        raise RuntimeError("Error al insertar usuario en base de datos")

    return db_res.data[0]

def update_user(supabase, *, auth_id, email=None, nombre=None, rol=None, empresa_id=None, grupo_id=None):
    """Actualiza Auth y tabla usuarios."""
    if email:
        supabase.auth.admin.update_user_by_id(auth_id, {"email": email})
    update_payload = {k: v for k, v in {
        "email": email,
        "nombre": nombre,
        "rol": rol,
        "empresa_id": empresa_id,
        "grupo_id": grupo_id
    }.items() if v is not None}
    supabase.table("usuarios").update(update_payload).eq("auth_id", auth_id).execute()

def delete_user(supabase, *, auth_id):
    """Borra de tabla usuarios y de Auth."""
    supabase.table("usuarios").delete().eq("auth_id", auth_id).execute()
    supabase.auth.admin.delete_user(auth_id)
