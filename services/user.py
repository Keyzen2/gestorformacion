from datetime import datetime
from utils import validar_dni_cif  # Si quieres validar documentos

def create_user(supabase, *, email, password, nombre, rol, empresa_id=None, grupo_id=None, dni=None):
    """
    Crea un usuario en Supabase Auth y en la tabla 'usuarios'.
    Si falla la inserción en la base de datos, revierte la creación en Auth.
    """
    # Validaciones básicas
    if not email or not password or not nombre or not rol:
        raise ValueError("Email, contraseña, nombre y rol son obligatorios.")
    if rol not in {"admin", "gestor", "alumno"}:
        raise ValueError("Rol no válido.")
    if rol == "gestor" and not empresa_id:
        raise ValueError("Un gestor debe tener empresa asignada.")
    if rol == "alumno" and not grupo_id:
        raise ValueError("Un alumno debe tener grupo asignado.")
    if dni and not validar_dni_cif(dni):
        raise ValueError("El DNI/NIE/CIF no es válido.")

    # Crear en Auth
    auth_res = supabase.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True
    })
    if not getattr(auth_res, "user", None):
        raise RuntimeError("Error al crear usuario en Auth.")

    auth_id = auth_res.user.id

    # Insertar en tabla usuarios
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
    if dni:
        payload["dni"] = dni

    db_res = supabase.table("usuarios").insert(payload).execute()
    if getattr(db_res, "error", None):
        # rollback Auth
        supabase.auth.admin.delete_user(auth_id)
        raise RuntimeError(f"Error al insertar usuario en base de datos: {db_res.error}")

    return db_res.data[0]

def update_user(supabase, *, auth_id, email=None, nombre=None, rol=None, empresa_id=None, grupo_id=None, dni=None):
    """
    Actualiza datos en Auth y en la tabla 'usuarios'.
    """
    if not auth_id:
        raise ValueError("auth_id es obligatorio para actualizar un usuario.")

    if dni and not validar_dni_cif(dni):
        raise ValueError("El DNI/NIE/CIF no es válido.")

    # Actualizar en Auth
    if email:
        supabase.auth.admin.update_user_by_id(auth_id, {"email": email})

    # Actualizar en tabla usuarios
    update_payload = {k: v for k, v in {
        "email": email,
        "nombre": nombre,
        "rol": rol,
        "empresa_id": empresa_id,
        "grupo_id": grupo_id,
        "dni": dni
    }.items() if v is not None}

    if update_payload:
        supabase.table("usuarios").update(update_payload).eq("auth_id", auth_id).execute()

def delete_user(supabase, *, auth_id):
    """
    Elimina un usuario de la tabla 'usuarios' y de Auth.
    """
    if not auth_id:
        raise ValueError("auth_id es obligatorio para eliminar un usuario.")

    supabase.table("usuarios").delete().eq("auth_id", auth_id).execute()
    supabase.auth.admin.delete_user(auth_id)
    
