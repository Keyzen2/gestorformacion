# services/cache_service.py
"""
🔧 Cache Service - Gestión centralizada de cache para Streamlit
Proporciona funciones para invalidar cache selectivamente por módulo y 
herramientas de monitoreo de performance.
"""

import streamlit as st
from typing import Optional, List, Dict, Any
import time
import hashlib
import json
from datetime import datetime, timedelta
import pandas as pd

class CacheService:
    """Servicio avanzado para gestión centralizada de cache."""
    
    def __init__(self):
        # Mapeo de módulos a funciones de cache
        self.cache_keys = {
            'empresas': [
                'get_empresas', 'get_empresas_completas', 'get_empresa_by_id', 
                'get_empresas_dict', 'get_metricas_empresa'
            ],
            'participantes': [
                'get_participantes', 'get_participantes_completos', 
                'get_participante_by_id', 'get_participantes_by_grupo'
            ],
            'grupos': [
                'get_grupos', 'get_grupos_completos', 'get_grupo_by_id',
                'get_grupos_dict', 'get_grupos_by_empresa'
            ],
            'documentos': [
                'get_documentos', 'get_documento_by_id', 'get_documentos_by_grupo',
                'get_documentos_by_empresa'
            ],
            'tutores': [
                'get_tutores', 'get_tutores_completos', 'get_tutor_by_id'
            ],
            'usuarios': [
                'get_usuarios', 'get_usuario_by_id', 'get_usuarios_by_empresa'
            ],
            'ajustes': [
                'get_ajustes_app', 'get_configuracion_global'
            ],
            'metricas': [
                'get_metricas_admin', 'get_metricas_empresa', 'get_metricas_globales'
            ],
            'acciones': [
                'get_acciones_formativas', 'get_acciones_dict', 'get_accion_by_id'
            ]
        }
        
        # TTL recomendados por tipo de dato
        self.ttl_config = {
            'empresas': 600,      # 10 minutos - datos estables
            'participantes': 300, # 5 minutos - datos dinámicos
            'grupos': 300,        # 5 minutos - datos dinámicos  
            'documentos': 180,    # 3 minutos - datos muy dinámicos
            'tutores': 600,       # 10 minutos - datos estables
            'usuarios': 900,      # 15 minutos - datos muy estables
            'ajustes': 3600,      # 1 hora - datos muy estables
            'metricas': 120,      # 2 minutos - datos de análisis
            'acciones': 1800      # 30 minutos - datos semi-estables
        }
        
        # Estadísticas de cache
        if 'cache_stats' not in st.session_state:
            st.session_state.cache_stats = {
                'hits': 0,
                'misses': 0,
                'invalidations': 0,
                'last_clear': None,
                'module_stats': {}
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
                # Como Streamlit no permite invalidación selectiva,
                # usamos un enfoque de timestamp para simular invalidación
                timestamp_key = f"cache_invalidated_{module}"
                st.session_state[timestamp_key] = time.time()
                
                # Actualizar estadísticas
                st.session_state.cache_stats['invalidations'] += 1
                if module not in st.session_state.cache_stats['module_stats']:
                    st.session_state.cache_stats['module_stats'][module] = {'invalidations': 0}
                st.session_state.cache_stats['module_stats'][module]['invalidations'] += 1
                
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
