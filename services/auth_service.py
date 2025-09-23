import streamlit as st
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import re
import secrets
import string


class AuthService:
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state

    # =========================
    # HELPERS
    # =========================
    def _generar_password_segura(self, longitud: int = 12) -> str:
        """Genera contraseña aleatoria segura."""
        caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(caracteres) for _ in range(longitud))

    def _validar_datos_base(self, datos: Dict[str, Any], tabla: str) -> Optional[str]:
        """Validaciones comunes + específicas por tabla."""
        email = datos.get("email")
        if not email:
            return "El email es obligatorio."

        # Validar formato email
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            return "Formato de email inválido."

        # Validar duplicados
        existing = self.supabase.table(tabla).select("id").eq("email", email).execute()
        if existing.data:
            return "Ya existe un registro con ese email."

        # Validaciones específicas
        if tabla == "usuarios":
            if not datos.get("nombre_completo"):
                return "El nombre completo es obligatorio."
        elif tabla == "participantes":
            if not datos.get("nombre") or not datos.get("apellidos"):
                return "Nombre y apellidos son obligatorios."

        return None

    def _preparar_metadata(self, datos: Dict[str, Any], tabla: str) -> Dict[str, Any]:
        """Prepara metadatos para Supabase Auth según la tabla."""
        if tabla == "usuarios":
            return {
                "rol": datos.get("rol", "admin"),
                "nombre_completo": datos.get("nombre_completo"),
                "tabla": "usuarios",
            }
        elif tabla == "participantes":
            return {
                "rol": "alumno",
                "nombre": datos.get("nombre"),
                "apellidos": datos.get("apellidos"),
                "tabla": "participantes",
            }
        return {}

    def _get_schema_fields(self, tabla: str) -> Dict[str, bool]:
        """Define qué campos existen en cada tabla."""
        schemas = {
            "usuarios": {
                "created_at": True,
                "updated_at": False  # ❌ usuarios NO tiene updated_at
            },
            "participantes": {
                "created_at": True,
                "updated_at": True   # ✅ participantes SÍ tiene updated_at
            },
            "tutores": {
                "created_at": True,
                "updated_at": True   # ✅ tutores SÍ tiene updated_at  
            }
        }
        return schemas.get(tabla, {"created_at": True, "updated_at": True})

    # =========================
    # CREAR USUARIO
    # =========================
    def crear_usuario_con_auth(
        self, datos: Dict[str, Any], tabla: str, password: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Crea un usuario en Auth + tabla, con validaciones y rollback.
        Retorna (ok, id_tabla).
        """
        st.write("🔍 **DEBUG AuthService - Inicio de crear_usuario_con_auth**")
        st.write(f"📋 Tabla destino: {tabla}")
        st.write(f"📄 Datos recibidos: {datos}")
        
        # Validar datos
        error = self._validar_datos_base(datos, tabla)
        if error:
            st.error(f"❌ Validación falló: {error}")
            return False, None

        st.write("✅ Validación inicial pasada")
        
        email = datos["email"]
        if not password:
            password = self._generar_password_segura()
            st.write(f"🔑 Contraseña auto-generada (longitud: {len(password)})")

        auth_id = None
        try:
            st.write("🚀 **PASO 1: Creando usuario en Supabase Auth**")
            
            # 1. Crear en Auth
            auth_payload = {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": self._preparar_metadata(datos, tabla),
            }
            st.write(f"📤 Payload para Auth: {auth_payload}")
            
            auth_res = self.supabase.auth.admin.create_user(auth_payload)
            
            if not getattr(auth_res, "user", None):
                st.error("❌ auth_res.user es None")
                raise Exception("No se pudo crear el usuario en Auth.")

            auth_id = str(auth_res.user.id)
            st.write(f"✅ Usuario creado en Auth con ID: {auth_id}")

            st.write("🚀 **PASO 2: Insertando en tabla de BD**")
            
            # 2. Insertar en tabla CON CAMPOS CORRECTOS SEGÚN SCHEMA
            datos_finales = datos.copy()
            schema = self._get_schema_fields(tabla)
            
            st.write(f"📋 Schema detectado para {tabla}: {schema}")
            
            # Añadir campos según el schema de cada tabla
            datos_finales["auth_id"] = auth_id
            
            if schema["created_at"]:
                datos_finales["created_at"] = datetime.utcnow().isoformat()
                
            if schema["updated_at"]:
                datos_finales["updated_at"] = datetime.utcnow().isoformat()

            st.write(f"📤 Datos finales para insertar en {tabla}: {datos_finales}")
            
            res = self.supabase.table(tabla).insert(datos_finales).execute()
            
            st.write(f"📥 Respuesta de INSERT: {res}")
            st.write(f"📄 res.data: {res.data}")
            
            if res.data and len(res.data) > 0:
                registro_id = res.data[0]["id"]
                st.write(f"✅ Usuario insertado correctamente con ID: {registro_id}")
                
                if password != datos.get("password"):
                    st.info(f"🔑 Contraseña generada automáticamente: {password}")
                return True, registro_id

            st.error(f"❌ INSERT falló - res.data vacío: {res.data}")
            raise Exception(f"No se insertaron datos en la tabla {tabla}.")

        except Exception as e:
            st.error(f"🚨 **EXCEPCIÓN en crear_usuario_con_auth:** {str(e)}")
            st.write(f"🔍 Tipo de excepción: {type(e).__name__}")
            
            # Rollback completo
            if auth_id:
                try:
                    st.write(f"🔄 Intentando rollback de Auth ID: {auth_id}")
                    self.supabase.auth.admin.delete_user(auth_id)
                    st.write("✅ Rollback de Auth completado")
                except Exception as rb:
                    st.warning(f"⚠️ Error en rollback de Auth: {rb}")
            
            return False, None

    # =========================
    # ACTUALIZAR
    # =========================
    def actualizar_usuario_con_auth(
        self, tabla: str, registro_id: str, datos_editados: Dict[str, Any]
    ) -> bool:
        try:
            # CORREGIDO: Solo añadir updated_at si la tabla lo soporta
            schema = self._get_schema_fields(tabla)
            if schema["updated_at"]:
                datos_editados["updated_at"] = datetime.utcnow().isoformat()
                
            res = (
                self.supabase.table(tabla)
                .update(datos_editados)
                .eq("id", registro_id)
                .execute()
            )
            return bool(res.data)
        except Exception as e:
            st.error(f"❌ Error actualizando {tabla}: {e}")
            return False

    # =========================
    # ELIMINAR
    # =========================
    def eliminar_usuario_con_auth(
        self, tabla: str, registro_id: str, auth_id: Optional[str] = None
    ) -> bool:
        try:
            if not auth_id:
                res = (
                    self.supabase.table(tabla)
                    .select("auth_id")
                    .eq("id", registro_id)
                    .execute()
                )
                if res.data and res.data[0].get("auth_id"):
                    auth_id = res.data[0]["auth_id"]

            # Borrar en tabla
            self.supabase.table(tabla).delete().eq("id", registro_id).execute()

            # Borrar en Auth
            if auth_id:
                try:
                    self.supabase.auth.admin.delete_user(auth_id)
                except Exception as rb:
                    st.warning(f"⚠️ Error borrando en Auth: {rb}")

            return True
        except Exception as e:
            st.error(f"❌ Error eliminando usuario: {e}")
            return False


# =========================
# FACTORY
# =========================
def get_auth_service(supabase, session_state) -> AuthService:
    return AuthService(supabase, session_state)
