"""
Clase base para todos los servicios de datos.
Contiene funcionalidad común y métodos helper.
"""

import streamlit as st
import pandas as pd
from typing import Optional


class BaseService:
    """Clase base para todos los servicios de datos"""
    
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
        self.rol = session_state.role
        self.empresa_id = session_state.user.get("empresa_id")
        self.user_id = session_state.user.get("id")
    
    def _apply_empresa_filter(self, query, table_name: str, empresa_field: str = "empresa_id"):
        """Aplica filtro de empresa según el rol."""
        if self.rol == "gestor" and self.empresa_id:
            return query.eq(empresa_field, self.empresa_id)
        return query

    def _handle_query_error(self, operation: str, error: Exception) -> pd.DataFrame:
        """Manejo centralizado de errores en consultas."""
        st.error(f"⚠️ Error en {operation}: {error}")
        return pd.DataFrame()

    def can_access_empresa_data(self, empresa_id: str) -> bool:
        """Verifica si el usuario puede acceder a datos de una empresa."""
        if self.rol == "admin":
            return True
        if self.rol == "gestor":
            return empresa_id == self.empresa_id
        return False

    def can_modify_data(self) -> bool:
        """Verifica si el usuario puede modificar datos."""
        return self.rol in ["admin", "gestor"]

    def can_create_users(self) -> bool:
        """Verifica si el usuario puede crear usuarios."""
        return self.rol == "admin"

    def can_access_admin_features(self) -> bool:
        """Verifica si el usuario puede acceder a funciones de admin."""
        return self.rol == "admin"

    def can_delete_data(self) -> bool:
        """Verifica si el usuario puede eliminar datos."""
        return self.rol in ["admin", "gestor"]
