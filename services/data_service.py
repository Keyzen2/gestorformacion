"""
DataService principal - Coordinador de módulos especializados.
Mantiene compatibilidad con el código existente mientras delega a servicios especializados.
"""

import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import date, datetime

# Importar módulos especializados
from .base.base_service import BaseService
from .modules.empresas_service import EmpresasService
from .cache.cache_decorators import dynamic_cache, static_cache, metrics_cache, clear_all_cache

# Mantener función de caché para ajustes (compatibilidad)
@st.cache_data(ttl=300, hash_funcs={object: lambda _: "X"})
def cached_get_ajustes_app(campos: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Obtiene ajustes de la app con caché segura.
    """
    sb = (
        st.session_state.get("supabase_public")
        or st.session_state.get("supabase_admin")
        or st.session_state.get("supabase")
    )
    if not sb:
        return {}

    try:
        if campos:
            sel = ",".join(campos)
            res = sb.table("ajustes_app").select(sel).single().execute()
        else:
            res = sb.table("ajustes_app").select("*").single().execute()
        return res.data or {}
    except Exception as e:
        st.error(f"⚠️ Error al cargar ajustes: {e}")
        return {}


class DataService(BaseService):
    """
    Servicio principal que coordina todos los módulos especializados.
    Mantiene compatibilidad total con el código existente.
    """
    def __init__(self, supabase, session_state):
        super().__init__(supabase, session_state)
        
        # Inicializar módulos especializados
        self.empresas = EmpresasService(supabase, session_state)

    # =========================================
    # MÉTODOS DE COMPATIBILIDAD - EMPRESAS
    # =========================================
    
    def get_empresas_con_modulos(self):
        """Compatibilidad: delega al módulo empresas"""
        return self.empresas.get_empresas_con_modulos()
    
    def get_empresas(self):
        """Compatibilidad: delega al módulo empresas"""
        return self.empresas.get_empresas()
    
    def get_empresas_dict(self):
        """Compatibilidad: delega al módulo empresas"""
        return self.empresas.get_empresas_dict()
    
    def get_metricas_empresas(self):
        """Compatibilidad: delega al módulo empresas"""
        return self.empresas.get_metricas_empresas()
    
    def filter_empresas(self, df: pd.DataFrame, query: str = "", modulo_filter: str = "Todos"):
        """Compatibilidad: delega al módulo empresas"""
        return self.empresas.filter_empresas(df, query, modulo_filter)
    
    def create_empresa(self, datos_empresa: Dict[str, Any]):
        """Compatibilidad: delega al módulo empresas"""
        return self.empresas.create_empresa(datos_empresa)
    
    def update_empresa(self, empresa_id: str, datos_empresa: Dict[str, Any]):
        """Compatibilidad: delega al módulo empresas"""
        return self.empresas.update_empresa(empresa_id, datos_empresa)
    
    def delete_empresa(self, empresa_id: str):
        """Compatibilidad: delega al módulo empresas"""
        return self.empresas.delete_empresa(empresa_id)

    # =========================================
    # MÉTODOS RESTANTES (temporalmente aquí hasta migrar)
    # =========================================

    @dynamic_cache(ttl=300)
    def get_acciones_formativas(self) -> pd.DataFrame:
        """Obtiene acciones formativas según el rol."""
        try:
            query = self.supabase.table("acciones_formativas").select("*")
            query = self._apply_empresa_filter(query, "acciones_formativas")
            
            res = query.order("nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar acciones formativas", e)

    def get_acciones_dict(self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de acciones."""
        df = self.get_acciones_formativas()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    @dynamic_cache(ttl=300)
    def get_grupos_completos(self) -> pd.DataFrame:
        """Obtiene grupos con información de empresa y acción formativa."""
        try:
            query = self.supabase.table("grupos").select("""
                id, nombre, fecha_inicio, fecha_fin, estado, modalidad,
                empresa_id, accion_formativa_id,
                empresa:empresas(id, nombre),
                accion_formativa:acciones_formativas(id, nombre)
            """)
            query = self._apply_empresa_filter(query, "grupos")
            
            res = query.order("fecha_inicio", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar datos relacionados
            if not df.empty:
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                if "accion_formativa" in df.columns:
                    df["accion_nombre"] = df["accion_formativa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return self._handle_query_error("cargar grupos", e)

    @dynamic_cache(ttl=300)
    def get_grupos(self) -> pd.DataFrame:
        """Obtiene grupos básicos según el rol."""
        try:
            query = self.supabase.table("grupos").select("*")
            query = self._apply_empresa_filter(query, "grupos")
            
            res = query.order("nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar grupos", e)

    def get_grupos_dict(self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de grupos."""
        df = self.get_grupos()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    # NOTA: Los métodos de participantes ahora están delegados al módulo especializado
    # Se mantienen los métodos antiguos comentados por compatibilidad temporal

    @dynamic_cache(ttl=300)
    def get_tutores_completos(self) -> pd.DataFrame:
        """Obtiene tutores con información de empresa."""
        try:
            query = self.supabase.table("tutores").select("""
                id, nombre, apellidos, email, telefono, nif, tipo_tutor,
                direccion, ciudad, provincia, codigo_postal, cv_url, 
                especialidad, created_at, empresa_id,
                empresa:empresas(id, nombre)
            """)
            query = self._apply_empresa_filter(query, "tutores")
            
            res = query.order("nombre").execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar empresa
            if not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
            else:
                df["empresa_nombre"] = ""
            
            return df
        except Exception as e:
            return self._handle_query_error("cargar tutores", e)

    def create_tutor(self, data: Dict[str, Any]) -> bool:
        """Crea un nuevo tutor."""
        try:
            # Validaciones básicas
            if not data.get("nombre") or not data.get("apellidos"):
                st.error("⚠️ Nombre y apellidos son obligatorios.")
                return False
            
            if not data.get("tipo_tutor"):
                st.error("⚠️ Tipo de tutor es obligatorio.")
                return False
            
            # Verificar permisos
            if self.rol == "gestor" and not self.empresa_id:
                st.error("⚠️ Error: Gestor sin empresa asignada.")
                return False
            
            # Asegurar empresa_id para gestores
            if self.rol == "gestor":
                data["empresa_id"] = self.empresa_id
            
            # Verificar si ya existe tutor con mismo email
            if data.get("email"):
                existing = self.supabase.table("tutores").select("id").eq("email", data["email"]).execute()
                if existing.data:
                    st.error("⚠️ Ya existe un tutor con este email.")
                    return False
            
            # Crear tutor
            data["created_at"] = datetime.now().isoformat()
            res = self.supabase.table("tutores").insert(data).execute()
            
            if res.data:
                # Invalidar cache
                st.cache_data.clear()
                return True
            else:
                st.error("⌛ Error al crear tutor.")
                return False
                
        except Exception as e:
            st.error(f"⌛ Error al crear tutor: {e}")
            return False

    def update_tutor(self, tutor_id: str, data: Dict[str, Any]) -> bool:
        """Actualiza un tutor existente."""
        try:
            # Verificar permisos
            if self.rol == "gestor":
                # Verificar que el tutor pertenece a su empresa
                tutor_check = self.supabase.table("tutores").select("empresa_id").eq("id", tutor_id).execute()
                if not tutor_check.data or tutor_check.data[0]["empresa_id"] != self.empresa_id:
                    st.error("⚠️ No tienes permisos para editar este tutor.")
                    return False
            
            # Verificar email único (excluyendo el tutor actual)
            if data.get("email"):
                existing = self.supabase.table("tutores").select("id").eq("email", data["email"]).neq("id", tutor_id).execute()
                if existing.data:
                    st.error("⚠️ Ya existe otro tutor con este email.")
                    return False
            
            # Actualizar
            data["updated_at"] = datetime.now().isoformat()
            res = self.supabase.table("tutores").update(data).eq("id", tutor_id).execute()
            
            if res.data:
                # Invalidar cache
                st.cache_data.clear()
                return True
            else:
                st.error("⌛ Error al actualizar tutor.")
                return False
                
        except Exception as e:
            st.error(f"⌛ Error al actualizar tutor: {e}")
            return False

    def delete_tutor(self, tutor_id: str) -> bool:
        """Elimina un tutor."""
        try:
            # Verificar permisos
            if self.rol == "gestor":
                # Verificar que el tutor pertenece a su empresa
                tutor_check = self.supabase.table("tutores").select("empresa_id").eq("id", tutor_id).execute()
                if not tutor_check.data or tutor_check.data[0]["empresa_id"] != self.empresa_id:
                    st.error("⚠️ No tienes permisos para eliminar este tutor.")
                    return False
            
            # Verificar si el tutor está asignado a algún grupo
            tutores_grupos = self.supabase.table("tutores_grupos").select("id").eq("tutor_id", tutor_id).execute()
            if tutores_grupos.data:
                st.error("⚠️ No se puede eliminar: el tutor está asignado a uno o más grupos.")
                return False
            
            # Eliminar tutor
            res = self.supabase.table("tutores").delete().eq("id", tutor_id).execute()
            
            if res.data:
                # Invalidar cache
                st.cache_data.clear()
                return True
            else:
                st.error("⌛ Error al eliminar tutor.")
                return False
                
        except Exception as e:
            st.error(f"⌛ Error al eliminar tutor: {e}")
            return False

    # =========================================
    # ÁREAS PROFESIONALES Y DATOS ESTÁTICOS
    # =========================================
    
    @static_cache(ttl=3600)
    def get_areas_profesionales(self) -> pd.DataFrame:
        """Obtiene áreas profesionales."""
        try:
            res = self.supabase.table("areas_profesionales").select("*").order("familia").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar áreas profesionales", e)

    def get_areas_dict(self) -> Dict[str, str]:
        """Obtiene diccionario de áreas profesionales."""
        df = self.get_areas_profesionales()
        return {
            f"{row['codigo']} - {row['nombre']}": row['codigo'] 
            for _, row in df.iterrows()
        } if not df.empty else {}

    @static_cache(ttl=3600)
    def get_grupos_acciones(self) -> pd.DataFrame:
        """Obtiene grupos de acciones."""
        try:
            res = self.supabase.table("grupos_acciones").select("*").order("codigo").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar grupos de acciones", e)

    def get_grupos_acciones_dict(self) -> Dict[str, str]:
        """Obtiene diccionario de grupos de acciones."""
        df = self.get_grupos_acciones()
        return {
            f"{row['codigo']} - {row['nombre']}": row['codigo'] 
            for _, row in df.iterrows()
        } if not df.empty else {}

    # =========================================
    # USUARIOS Y ADMINISTRACIÓN
    # =========================================

    @dynamic_cache(ttl=300)
    def get_usuarios_completos(self) -> pd.DataFrame:
        """Obtiene usuarios con información de empresa y grupo."""
        try:
            query = self.supabase.table("usuarios").select("""
                id, auth_id, email, rol, dni, nombre_completo, telefono, 
                nombre, created_at, empresa_id, grupo_id,
                empresa:empresas(id, nombre),
                grupo:grupos(id, nombre)
            """)
            
            # Aplicar filtro según rol
            if self.rol == "gestor" and self.empresa_id:
                query = query.eq("empresa_id", self.empresa_id)
            
            res = query.order("nombre_completo").execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar datos relacionados
            if not df.empty:
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                if "grupo" in df.columns:
                    df["grupo_nombre"] = df["grupo"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return self._handle_query_error("cargar usuarios", e)

    @dynamic_cache(ttl=300)
    def get_usuarios(self) -> pd.DataFrame:
        """Obtiene usuarios básicos según el rol."""
        try:
            query = self.supabase.table("usuarios").select("*")
            
            # Aplicar filtro según rol
            if self.rol == "gestor" and self.empresa_id:
                query = query.eq("empresa_id", self.empresa_id)
            
            res = query.order("nombre_completo").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar usuarios", e)

    # =========================================
    # MÉTRICAS Y ESTADÍSTICAS
    # =========================================
    
    @metrics_cache(ttl=600)
    def get_metricas_admin(self) -> Dict[str, int]:
        """Obtiene métricas principales para admin."""
        try:
            # Contar empresas
            empresas_res = self.supabase.table("empresas").select("id", count="exact").execute()
            total_empresas = empresas_res.count or 0
            
            # Contar usuarios
            usuarios_res = self.supabase.table("usuarios").select("id", count="exact").execute()
            total_usuarios = usuarios_res.count or 0
            
            # Contar grupos
            grupos_res = self.supabase.table("grupos").select("id", count="exact").execute()
            total_grupos = grupos_res.count or 0
            
            # Contar participantes
            participantes_res = self.supabase.table("participantes").select("id", count="exact").execute()
            total_participantes = participantes_res.count or 0
            
            return {
                "empresas": total_empresas,
                "usuarios": total_usuarios,
                "grupos": total_grupos,
                "participantes": total_participantes
            }
        except Exception as e:
            st.error(f"⚠️ Error al calcular métricas: {e}")
            return {"empresas": 0, "usuarios": 0, "grupos": 0, "participantes": 0}

    @metrics_cache(ttl=600)
    def get_metricas_gestor(self) -> Dict[str, int]:
        """Obtiene métricas para gestores (filtradas por empresa)."""
        try:
            if not self.empresa_id:
                return {"grupos": 0, "participantes": 0, "tutores": 0}
            
            # Contar grupos de la empresa
            grupos_res = self.supabase.table("grupos").select("id", count="exact").eq("empresa_id", self.empresa_id).execute()
            total_grupos = grupos_res.count or 0
            
            # Contar tutores de la empresa
            tutores_res = self.supabase.table("tutores").select("id", count="exact").eq("empresa_id", self.empresa_id).execute()
            total_tutores = tutores_res.count or 0
            
            # Contar participantes (a través de grupos)
            grupos_ids_res = self.supabase.table("grupos").select("id").eq("empresa_id", self.empresa_id).execute()
            if grupos_ids_res.data:
                grupo_ids = [g["id"] for g in grupos_ids_res.data]
                participantes_res = self.supabase.table("participantes").select("id", count="exact").in_("grupo_id", grupo_ids).execute()
                total_participantes = participantes_res.count or 0
            else:
                total_participantes = 0
            
            return {
                "grupos": total_grupos,
                "participantes": total_participantes,
                "tutores": total_tutores
            }
        except Exception as e:
            st.error(f"⚠️ Error al calcular métricas: {e}")
            return {"grupos": 0, "participantes": 0, "tutores": 0}

    # =========================================
    # OPERACIONES CRUD BÁSICAS
    # =========================================

    def create_accion_formativa(self, data: Dict[str, Any]) -> bool:
        """Crea una nueva acción formativa."""
        try:
            if self.rol == "gestor":
                data["empresa_id"] = self.empresa_id
            
            self.supabase.table("acciones_formativas").insert(data).execute()
            # Limpiar cache
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"⚠️ Error al crear acción formativa: {e}")
            return False

    def update_accion_formativa(self, accion_id: str, data: Dict[str, Any]) -> bool:
        """Actualiza una acción formativa."""
        try:
            self.supabase.table("acciones_formativas").update(data).eq("id", accion_id).execute()
            # Limpiar cache
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"⚠️ Error al actualizar acción formativa: {e}")
            return False

    def delete_accion_formativa(self, accion_id: str) -> bool:
        """Elimina una acción formativa."""
        try:
            self.supabase.table("acciones_formativas").delete().eq("id", accion_id).execute()
            # Limpiar cache
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"⚠️ Error al eliminar acción formativa: {e}")
            return False

    # =========================================
    # MÉTODOS DE UTILIDAD
    # =========================================
    
    def get_empresa_actual(self) -> Optional[Dict[str, Any]]:
        """Obtiene información de la empresa actual del gestor."""
        if self.rol == "gestor" and self.empresa_id:
            try:
                res = self.supabase.table("empresas").select("*").eq("id", self.empresa_id).single().execute()
                return res.data
            except Exception:
                return None
        return None

    def invalidate_cache(self, cache_keys: Optional[List[str]] = None):
        """Invalida caché específico o todo el caché."""
        if cache_keys:
            # En el futuro implementar invalidación selectiva
            clear_all_cache()
        else:
            clear_all_cache()

    def refresh_user_session(self):
        """Refresca la sesión del usuario actual."""
        try:
            # Recargar información del usuario desde la base de datos
            if self.user_id:
                user_res = self.supabase.table("usuarios").select("*").eq("id", self.user_id).single().execute()
                if user_res.data:
                    # Actualizar session_state con nueva información
                    self.session_state.user.update(user_res.data)
                    self.empresa_id = user_res.data.get("empresa_id")
                    self.rol = user_res.data.get("rol")
        except Exception as e:
            st.error(f"⚠️ Error al refrescar sesión: {e}")


# =========================================
# FUNCIÓN FACTORY (NO CAMBIAR - COMPATIBILIDAD)
# =========================================

def get_data_service(supabase, session_state) -> DataService:
    """Factory function para obtener instancia del servicio."""
    return DataService(supabase, session_state)


def clear_all_cache():
    """Limpia todo el cache de datos."""
    st.cache_data.clear()


def refresh_cache_for_table(table_name: str):
    """Refresca el cache para una tabla específica."""
    # Esta función se puede expandir para invalidar cachés específicos
    st.cache_data.clear()
