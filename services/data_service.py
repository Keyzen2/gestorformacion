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

    @dynamic_cache(ttl=300)
    def get_participantes_completos(self) -> pd.DataFrame:
        """Obtiene participantes con información de grupo y empresa."""
        try:
            query = self.supabase.table("participantes").select("""
                id, nombre, apellidos, email, telefono, dni, 
                fecha_alta, estado, grupo_id,
                grupo:grupos(id, nombre, empresa_id,
                    empresa:empresas(id, nombre)
                )
            """)
            
            # Aplicar filtro según rol
            if self.rol == "gestor" and self.empresa_id:
                # Para gestores, filtrar por empresa a través del grupo
                grupos_empresa = self.supabase.table("grupos").select("id").eq("empresa_id", self.empresa_id).execute()
                if grupos_empresa.data:
                    grupo_ids = [g["id"] for g in grupos_empresa.data]
                    query = query.in_("grupo_id", grupo_ids)
                else:
                    # No hay grupos para esta empresa
                    return pd.DataFrame()
            
            res = query.order("apellidos", "nombre").execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar datos relacionados
            if not df.empty and "grupo" in df.columns:
                df["grupo_nombre"] = df["grupo"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
                df["empresa_nombre"] = df["grupo"].apply(
                    lambda x: x.get("empresa", {}).get("nombre") if isinstance(x, dict) else ""
                )
                df["empresa_id"] = df["grupo"].apply(
                    lambda x: x.get("empresa_id") if isinstance(x, dict) else ""
                )
            
            return df
        except Exception as e:
            return self._handle_query_error("cargar participantes", e)

    @dynamic_cache(ttl=300)
    def get_participantes(self) -> pd.DataFrame:
        """Obtiene participantes básicos según el rol."""
        try:
            query = self.supabase.table("participantes").select("*")
            
            # Aplicar filtro según rol
            if self.rol == "gestor" and self.empresa_id:
                # Para gestores, filtrar por empresa a través del grupo
                grupos_empresa = self.supabase.table("grupos").select("id").eq("empresa_id", self.empresa_id).execute()
                if grupos_empresa.data:
                    grupo_ids = [g["id"] for g in grupos_empresa.data]
                    query = query.in_("grupo_id", grupo_ids)
                else:
                    return pd.DataFrame()
            
            res = query.order("apellidos", "nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar participantes", e)

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
