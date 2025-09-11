"""
Decoradores inteligentes para gestión de cache.
"""

import streamlit as st
from functools import wraps
from typing import Optional


def smart_cache(ttl: int = 300, key_prefix: str = ""):
    """
    Decorador de cache inteligente con TTL personalizable.
    
    Args:
        ttl: Tiempo de vida en segundos
        key_prefix: Prefijo para la clave de cache (ayuda a organizar e invalidar)
    """
    def decorator(func):
        @wraps(func)
        @st.cache_data(ttl=ttl)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Añadir metadatos para gestión de cache
        wrapper._cache_prefix = key_prefix
        wrapper._cache_ttl = ttl
        
        return wrapper
    return decorator


def static_cache(ttl: int = 3600):
    """
    Cache para datos que raramente cambian (áreas profesionales, etc.)
    TTL por defecto de 1 hora.
    """
    return smart_cache(ttl=ttl, key_prefix="static")


def dynamic_cache(ttl: int = 300):
    """
    Cache para datos que cambian frecuentemente (empresas, usuarios, etc.)
    TTL por defecto de 5 minutos.
    """
    return smart_cache(ttl=ttl, key_prefix="dynamic")


def metrics_cache(ttl: int = 600):
    """
    Cache para métricas y estadísticas.
    TTL por defecto de 10 minutos.
    """
    return smart_cache(ttl=ttl, key_prefix="metrics")


def invalidate_cache_by_prefix(prefix: str):
    """
    Invalida cache por prefijo específico.
    Útil para invalidar solo cache relacionado después de operaciones CRUD.
    """
    try:
        # Por ahora limpiamos todo el cache
        # En el futuro se puede implementar invalidación selectiva
        st.cache_data.clear()
    except Exception as e:
        st.warning(f"⚠️ Error al limpiar cache: {e}")


def clear_all_cache():
    """Limpia todo el cache."""
    try:
        st.cache_data.clear()
        st.success("✅ Cache limpiado correctamente")
    except Exception as e:
        st.error(f"⚠️ Error al limpiar cache: {e}")
