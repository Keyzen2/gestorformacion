import random
import string
import uuid
from datetime import datetime
from utils import validar_dni_cif
from services.users import create_user, delete_user

def alta_alumno(
    supabase,
    *,
    email: str,
    password: str = None,
    nombre: str,
    dni: str = None,
    apellidos: str = None,
    telefono: str = None,
    empresa_id: str = None,
    grupo_id: str = None
) -> bool:
    """
    Crea un alumno en Auth, en la tabla usuarios y en participantes.
    Si falla un paso, revierte los anteriores.
    Devuelve True si todo OK, o lanza excepción.
    """

    # Validaciones mínimas
    if not email or not nombre:
        raise ValueError("Email y nombre son obligatorios para crear un alumno.")
    if dni and not validar_dni_cif(dni):
        raise ValueError("El DNI/NIE/CIF no es válido.")

    # Generar contraseña si no se proporciona
    if not password:
        alphabet = string.ascii_letters + string.digits
        password = "".join(random.choices(alphabet, k=12))

    try:
        # Crear usuario en Auth y tabla usuarios
        usuario = create_user(
            supabase,
            email=email,
            password=password,
            nombre=nombre,
            rol="alumno",
            grupo_id=grupo_id,
            empresa_id=empresa_id,
            dni=dni
        )

        # Insertar en tabla participantes
        participante_payload = {
            "id": str(uuid.uuid4()),
            "email": email,
            "nombre": nombre,
            "apellidos": apellidos or "",
            "dni": dni or "",
            "telefono": telefono or "",
            "created_at": datetime.utcnow().isoformat()
        }
        if empresa_id:
            participante_payload["empresa_id"] = empresa_id
        if grupo_id:
            participante_payload["grupo_id"] = grupo_id

        p_res = supabase.table("participantes").insert(participante_payload).execute()
        if getattr(p_res, "error", None) or not p_res.data:
            # Rollback completo
            delete_user(supabase, auth_id=usuario["auth_id"])
            raise RuntimeError(f"Error al insertar en participantes: {p_res.error or 'sin data'}")

        return True

    except Exception:
        # Si falla create_user ya hace rollback en Auth
        raise
