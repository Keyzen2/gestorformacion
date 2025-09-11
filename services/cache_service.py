# services/cache_service.py
"""
🔧 Cache Service - Gestión centralizada de cache para Streamlit
Proporciona funciones para invalidar cache selectivamente por módulo
"""

import streamlit as st
from typing import Optional, List
import time

class CacheService:
    """Servicio para gestión centralizada de cache."""
    
    def __init__(self):
        self.cache_keys = {
            'empresas': ['get_empresas', 'get_empresa_by_id', 'get_metricas_empresa'],
            'participantes': ['get_participantes', 'get_participante_by_id'],
            'grupos': ['get_grupos', 'get_grupos_completos', 'get_grupo_by_id'],
            'documentos': ['get_documentos', 'get_documento_by_id'],
            'tutores': ['get_tutores', 'get_tutor_by_id'],
            'usuarios': ['get_usuarios', 'get_usuario_by_id'],
            'ajustes': ['get_ajustes_app'],
            'metricas': ['get_metricas_admin', 'get_metricas_empresa']
        }
    
    def invalidate_module_cache(self, module: str) -> bool:
        """
        Invalida el cache de un módulo específico.
        
        Args:
            module: Nombre del módulo ('empresas', 'participantes', etc.)
        
        Returns:
            bool: True si se invalidó correctamente
        """
        try:
            if module in self.cache_keys:
                # Streamlit no permite invalidar funciones específicas por nombre,
                # pero podemos limpiar todo el cache o usar una estrategia de keys
                st.cache_data.clear()
                return True
            return False
        except Exception as e:
            st.error(f"⚠️ Error al invalidar cache del módulo {module}: {e}")
            return False
    
    def invalidate_all_cache(self) -> bool:
        """Invalida todo el cache de la aplicación."""
        try:
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"⚠️ Error al invalidar cache global: {e}")
            return False
    
    def get_cache_info(self) -> dict:
        """Obtiene información sobre el estado del cache."""
        # Streamlit no expone información detallada del cache,
        # pero podemos proporcionar información básica
        return {
            'modules': list(self.cache_keys.keys()),
            'total_functions': sum(len(funcs) for funcs in self.cache_keys.values()),
            'last_cleared': getattr(self, '_last_cleared', 'Never')
        }
    
    def schedule_cache_refresh(self, module: str, delay_seconds: int = 1) -> None:
        """
        Programa la invalidación del cache después de un delay.
        Útil para operaciones CRUD que necesitan refrescar datos.
        """
        try:
            # En un entorno real, esto sería async, pero para simplicidad:
            time.sleep(delay_seconds)
            self.invalidate_module_cache(module)
        except Exception as e:
            st.error(f"⚠️ Error en refresh programado: {e}")

# Función de conveniencia para obtener la instancia
@st.cache_resource
def get_cache_service() -> CacheService:
    """Obtiene la instancia singleton del CacheService."""
    return CacheService()

# Decorador personalizado para cache con invalidación automática
def smart_cache(ttl: int = 300, module: str = None):
    """
    Decorador que combina @st.cache_data con invalidación inteligente.
    
    Args:
        ttl: Time to live en segundos
        module: Módulo al que pertenece (para invalidación selectiva)
    """
    def decorator(func):
        # Aplicar el cache de Streamlit
        cached_func = st.cache_data(ttl=ttl)(func)
        
        # Añadir metadata para el cache service
        cached_func._cache_module = module
        cached_func._cache_ttl = ttl
        
        return cached_func
    return decorator

# Funciones de utilidad para uso directo
def invalidate_after_crud(module: str):
    """Invalida cache después de operaciones CRUD."""
    cache_service = get_cache_service()
    return cache_service.invalidate_module_cache(module)

def clear_all_cache():
    """Limpia todo el cache - usar con cuidado."""
    cache_service = get_cache_service()
    return cache_service.invalidate_all_cache()

# Ejemplo de uso en DataService:
"""
# En data_service.py, cambiar:
@st.cache_data(ttl=300)
def get_empresas(self):
    # ...

# Por:
@smart_cache(ttl=300, module='empresas')  
def get_empresas(self):
    # ...

# Y después de operaciones CRUD:
def create_empresa(self, data):
    # ... operación de creación ...
    if success:
        invalidate_after_crud('empresas')
    return success
"""
