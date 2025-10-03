import streamlit as st
from supabase import Client
from typing import Dict, Any, Optional
from datetime import datetime


class AlumnosService:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    # =========================
    # CREAR ALUMNO (Participante + Auth)
    # =========================
    def crear_alumno(self, datos: Dict[str, Any]) -> Optional[str]:
        """
        Crea un alumno en Supabase Auth y lo vincula a participantes.

        Args:
            datos: {
                "email": str,
                "password": str,
                "nombre": str,
                "apellidos": str,
                "telefono": str,
                "empresa_id": str,
                "grupo_id": str
            }

        Returns:
            str | None -> ID del participante creado o None en error
        """
        try:
            email = datos.get("email")
            password = datos.get("password")

            if not email or not password:
                st.error("❌ Email y contraseña son obligatorios para crear un alumno")
                return None

            # 1. Crear usuario en Supabase Auth
            auth_res = self.supabase.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "rol": "alumno",
                        "nombre": datos.get("nombre"),
                        "apellidos": datos.get("apellidos"),
                    },
                }
            )

            if not auth_res or not auth_res.user:
                st.error("❌ No se pudo crear el usuario en Auth")
                return None

            auth_id = str(auth_res.user.id)

            # 2. Insertar en tabla participantes
            participante = {
                "nombre": datos.get("nombre"),
                "apellidos": datos.get("apellidos"),
                "email": email,
                "telefono": datos.get("telefono"),
                "empresa_id": datos.get("empresa_id"),
                "grupo_id": datos.get("grupo_id"),
                "auth_id": auth_id,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            res = self.supabase.table("participantes").insert(participante).execute()

            if res.data:
                return res.data[0]["id"]
            else:
                st.error("❌ Error insertando en participantes")
                return None

        except Exception as e:
            st.error(f"❌ Error creando alumno: {e}")
            return None

    # =========================
    # BORRAR ALUMNO (Participante + Auth)
    # =========================
    def borrar_alumno(self, participante_id: str, auth_id: Optional[str] = None) -> bool:
        """Elimina un alumno tanto de participantes como de Auth."""
        try:
            # 1. Obtener auth_id si no lo pasan
            if not auth_id:
                res = self.supabase.table("participantes").select("auth_id").eq("id", participante_id).execute()
                if res.data:
                    auth_id = res.data[0].get("auth_id")

            # 2. Eliminar de participantes
            self.supabase.table("participantes").delete().eq("id", participante_id).execute()

            # 3. Eliminar también de Auth
            if auth_id:
                self.supabase.auth.admin.delete_user(auth_id)

            return True
        except Exception as e:
            st.error(f"❌ Error borrando alumno: {e}")
            return False

    # =========================
    # OBTENER ALUMNOS
    # =========================
    def get_alumnos(self, grupo_id: Optional[str] = None):
        """Devuelve los alumnos desde vw_participantes."""
        try:
            query = self.supabase.table("vw_participantes").select("*")
            if grupo_id:
                query = query.eq("grupo_id", grupo_id)
            res = query.execute()
            return res.data or []
        except Exception as e:
            st.error(f"❌ Error cargando alumnos: {e}")
            return []
