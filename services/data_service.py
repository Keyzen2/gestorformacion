"""
Servicios centralizados para consultas de datos optimizadas.
Unifica las consultas y aplica filtros por rol de forma consistente.
"""

import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from utils import validar_dni_cif

class DataService:
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
        self.rol = session_state.role
        self.empresa_id = session_state.user.get("empresa_id")
        self.user_id = session_state.user.get("id")

    # =========================
    # MÉTODOS HELPER PARA FILTROS
    # =========================
    def _apply_empresa_filter(self, query, table_name: str, empresa_field: str = "empresa_id"):
        """Aplica filtro de empresa según el rol."""
        if self.rol == "gestor" and self.empresa_id:
            return query.eq(empresa_field, self.empresa_id)
        return query

    def _handle_query_error(self, operation: str, error: Exception) -> pd.DataFrame:
        """Manejo centralizado de errores en consultas."""
        st.error(f"❌ Error en {operation}: {error}")
        return pd.DataFrame()

    # =========================
    # EMPRESAS
    # =========================
    @st.cache_data(ttl=300)
    def get_empresas(_self) -> pd.DataFrame:
        """Obtiene lista de empresas según el rol."""
        try:
            if _self.rol == "gestor":
                query = _self.supabase.table("empresas").select("*").eq("id", _self.empresa_id)
            else:
                query = _self.supabase.table("empresas").select("*")
            
            res = query.execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar empresas", e)

    def get_empresas_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de empresas."""
        df = _self.get_empresas()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    # =========================
    # ACCIONES FORMATIVAS
    # =========================
    @st.cache_data(ttl=300)
    def get_acciones_formativas(_self) -> pd.DataFrame:
        """Obtiene acciones formativas según el rol."""
        try:
            query = _self.supabase.table("acciones_formativas").select("*")
            query = _self._apply_empresa_filter(query, "acciones_formativas")
            
            res = query.order("nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar acciones formativas", e)

    def get_acciones_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de acciones."""
        df = _self.get_acciones_formativas()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    # =========================
    # GRUPOS
    # =========================
    @st.cache_data(ttl=300)
    def get_grupos_completos(_self) -> pd.DataFrame:
        """Obtiene grupos con información de acción formativa."""
        try:
            query = _self.supabase.table("grupos").select("""
                id, codigo_grupo, fecha_inicio, fecha_fin, fecha_fin_prevista,
                aula_virtual, horario, localidad, provincia, cp,
                n_participantes_previstos, n_participantes_finalizados,
                n_aptos, n_no_aptos, observaciones, empresa_id, created_at,
                accion_formativa:acciones_formativas(id, nombre, modalidad, num_horas)
            """)
            query = _self._apply_empresa_filter(query, "grupos")
            
            res = query.order("fecha_inicio", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar información de acción formativa
            if not df.empty and "accion_formativa" in df.columns:
                df["accion_nombre"] = df["accion_formativa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
                df["accion_modalidad"] = df["accion_formativa"].apply(
                    lambda x: x.get("modalidad") if isinstance(x, dict) else ""
                )
                df["accion_horas"] = df["accion_formativa"].apply(
                    lambda x: x.get("num_horas") if isinstance(x, dict) else 0
                )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar grupos", e)

    def get_grupos_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario codigo_grupo -> id de grupos."""
        df = _self.get_grupos_completos()
        return {row["codigo_grupo"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    # =========================
    # PARTICIPANTES
    # =========================
    @st.cache_data(ttl=300)
    def get_participantes_completos(_self) -> pd.DataFrame:
        """Obtiene participantes con información de grupo y empresa."""
        try:
            query = _self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, dni, email, telefono, 
                fecha_nacimiento, sexo, created_at, updated_at,
                grupo:grupos(id, codigo_grupo),
                empresa:empresas(id, nombre)
            """)
            query = _self._apply_empresa_filter(query, "participantes")
            
            res = query.order("created_at", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar relaciones
            if not df.empty:
                if "grupo" in df.columns:
                    df["grupo_codigo"] = df["grupo"].apply(
                        lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                    )
                    df["grupo_id"] = df["grupo"].apply(
                        lambda x: x.get("id") if isinstance(x, dict) else None
                    )
                
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes", e)

    # =========================
    # TUTORES
    # =========================
    @st.cache_data(ttl=300)
    def get_tutores_completos(_self) -> pd.DataFrame:
        """Obtiene tutores con información de empresa."""
        try:
            query = _self.supabase.table("tutores").select("""
                id, nombre, apellidos, email, telefono, nif, tipo_tutor,
                direccion, ciudad, provincia, codigo_postal, cv_url, 
                especialidad, created_at,
                empresa:empresas(id, nombre)
            """)
            query = _self._apply_empresa_filter(query, "tutores")
            
            res = query.order("nombre").execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar empresa
            if not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar tutores", e)

    # =========================
    # DOCUMENTOS
    # =========================
    @st.cache_data(ttl=300)
    def get_documentos(_self, tipo: Optional[str] = None) -> pd.DataFrame:
        """Obtiene documentos según el rol y tipo opcional."""
        try:
            query = _self.supabase.table("documentos").select("*")
            query = _self._apply_empresa_filter(query, "documentos")
            
            if tipo:
                query = query.eq("tipo", tipo)
            
            res = query.order("created_at", desc=True).execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar documentos", e)

    # =========================
    # USUARIOS
    # =========================
    @st.cache_data(ttl=300)
    def get_usuarios(_self, include_empresa=False) -> pd.DataFrame:
        """Obtiene usuarios con información opcional de empresa."""
        try:
            if include_empresa:
                query = _self.supabase.table("usuarios").select("""
                    id, email, nombre, apellidos, rol, activo, 
                    created_at, updated_at, empresa_id,
                    empresa:empresas(id, nombre, cif)
                """)
            else:
                query = _self.supabase.table("usuarios").select("*")
            
            query = _self._apply_empresa_filter(query, "usuarios")
            
            res = query.order("created_at", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            if include_empresa and not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
                df["empresa_cif"] = df["empresa"].apply(
                    lambda x: x.get("cif") if isinstance(x, dict) else ""
                )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar usuarios", e)

    # =========================
    # ÁREAS PROFESIONALES Y GRUPOS DE ACCIONES
    # =========================
    @st.cache_data(ttl=3600)
    def get_areas_profesionales(_self) -> pd.DataFrame:
        """Obtiene áreas profesionales."""
        try:
            res = _self.supabase.table("areas_profesionales").select("*").order("familia").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar áreas profesionales", e)

    def get_areas_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario de áreas profesionales."""
        df = _self.get_areas_profesionales()
        return {
            f"{row['codigo']} - {row['nombre']}": row['codigo'] 
            for _, row in df.iterrows()
        } if not df.empty else {}

    @st.cache_data(ttl=3600)
    def get_grupos_acciones(_self) -> pd.DataFrame:
        """Obtiene grupos de acciones."""
        try:
            res = _self.supabase.table("grupos_acciones").select("*").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar grupos de acciones", e)

    # =========================
    # MÉTRICAS Y ESTADÍSTICAS
    # =========================
    @st.cache_data(ttl=300)
    def get_metricas_empresa(_self, empresa_id: str) -> Dict[str, int]:
        """Obtiene métricas específicas de una empresa."""
        try:
            if _self.rol != "admin" and empresa_id != _self.empresa_id:
                return {}
            
            try:
                res = _self.supabase.rpc('get_gestor_metrics', {'empresa_uuid': empresa_id}).execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass
            
            grupos = len(_self.supabase.table("grupos").select("id").eq("empresa_id", empresa_id).execute().data or [])
            participantes = len(_self.supabase.table("participantes").select("id").eq("empresa_id", empresa_id).execute().data or [])
            documentos = len(_self.supabase.table("documentos").select("id").eq("empresa_id", empresa_id).execute().data or [])
            acciones = len(_self.supabase.table("acciones_formativas").select("id").eq("empresa_id", empresa_id).execute().data or [])
            
            return {
                "total_grupos": grupos,
                "total_participantes": participantes,
                "total_documentos": documentos,
                "total_acciones": acciones
            }
        except Exception as e:
            st.error(f"❌ Error al cargar métricas: {e}")
            return {}

    @st.cache_data(ttl=300)
    def get_metricas_admin(_self) -> Dict[str, int]:
        """Obtiene métricas globales para admin."""
        try:
            try:
                res = _self.supabase.rpc('get_admin_metrics').execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass
            
            empresas = _self.supabase.table("empresas").select("*", count="exact").execute().count or 0
            usuarios = _self.supabase.table("usuarios").select("*", count="exact").execute().count or 0
            cursos = _self.supabase.table("acciones_formativas").select("*", count="exact").execute().count or 0
            grupos = _self.supabase.table("grupos").select("*", count="exact").execute().count or 0
            
            return {
                "total_empresas": empresas,
                "total_usuarios": usuarios,
                "total_cursos": cursos,
                "total_grupos": grupos
            }
        except Exception as e:
            st.error(f"❌ Error al cargar métricas admin: {e}")
            return {}

    # =========================
    # BÚSQUEDAS OPTIMIZADAS
    # =========================
    def search_participantes(_self, search_term: str) -> pd.DataFrame:
        """Búsqueda optimizada de participantes."""
        if not search_term:
            return _self.get_participantes_completos()
        
        try:
            try:
                res = _self.supabase.rpc('search_usuarios', {'search_term': search_term}).execute()
                return pd.DataFrame(res.data or [])
            except Exception:
                pass
            
            df = _self.get_participantes_completos()
            if df.empty:
                return df
            
            search_lower = search_term.lower()
            mask = (
                df["nombre"].str.lower().str.contains(search_lower, na=False) |
                df["apellidos"].str.lower().str.contains(search_lower, na=False) |
                df["email"].str.lower().str.contains(search_lower, na=False) |
                df["dni"].str.lower().str.contains(search_lower, na=False)
            )
            return df[mask]
        except Exception as e:
            return _self._handle_query_error("buscar participantes", e)

    # =========================
    # OPERACIONES DE ESCRITURA
    # =========================
    def create_accion_formativa(_self, data: Dict[str, Any]) -> bool:
        """Crea una nueva acción formativa."""
        try:
            if _self.rol == "gestor":
                data["empresa_id"] = _self.empresa_id
            
            _self.supabase.table("acciones_formativas").insert(data).execute()
            _self.get_acciones_formativas.clear()
            return True
        except Exception as e:
            st.error(f"❌ Error al crear acción formativa: {e}")
            return False

    def update_accion_formativa(_self, accion_id: str, data: Dict[str, Any]) -> bool:
        """Actualiza una acción formativa."""
        try:
            _self.supabase.table("acciones_formativas").update(data).eq("id", accion_id).execute()
            _self.get_acciones_formativas.clear()
            return True
        except Exception as e:
            st.error(f"❌ Error al actualizar acción formativa: {e}")
            return False

    def delete_accion_formativa(_self, accion_id: str) -> bool:
        """Elimina una acción formativa."""
        try:
            _self.supabase.table("acciones_formativas").delete().eq("id", accion_id).execute()
            _self.get_acciones_formativas.clear()
            return True
        except Exception as e:
            st.error(f"❌ Error al eliminar acción formativa: {e}")
            return False

    # =========================
    # VALIDACIÓN DE PERMISOS
    # =========================
    def can_access_empresa_data(_self, empresa_id: str) -> bool:
        """Verifica si el usuario puede acceder a datos de una empresa."""
        if _self.rol == "admin":
            return True
        if _self.rol == "gestor":
            return empresa_id == _self.empresa_id
        return False

    def can_modify_data(_self) -> bool:
        """Verifica si el usuario puede modificar datos."""
        return _self.rol in ["admin", "gestor"]

    def can_create_users(_self) -> bool:
        """Verifica si el usuario puede crear usuarios."""
        return _self.rol == "admin"

# =========================
# FUNCIONES DE UTILIDAD
# =========================
def get_data_service(supabase, session_state) -> DataService:
    """Factory function para obtener instancia del servicio."""
    return DataService(supabase, session_state)

def clear_all_cache():
    """Limpia todo el cache de datos."""
    st.cache_data.clear()
