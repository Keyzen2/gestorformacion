"""
Utilidades y funciones auxiliares para el gestor de formación.
Versión corregida sin problemas de cache.
"""

import streamlit as st
import pandas as pd
import re
from datetime import datetime, date
from typing import Dict, Any, Optional, List


# =========================
# VALIDACIONES
# =========================

def validar_dni_cif(documento: str) -> bool:
    """Valida DNI, NIE o CIF español."""
    if not documento:
        return False
    
    documento = documento.upper().strip()
    
    # DNI: 8 dígitos + letra
    dni_pattern = r'^\d{8}[A-Z]$'
    if re.match(dni_pattern, documento):
        return validar_dni_letra(documento)
    
    # NIE: X/Y/Z + 7 dígitos + letra
    nie_pattern = r'^[XYZ]\d{7}[A-Z]$'
    if re.match(nie_pattern, documento):
        return validar_nie_letra(documento)
    
    # CIF: Letra + 7 dígitos + letra/dígito
    cif_pattern = r'^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$'
    if re.match(cif_pattern, documento):
        return True  # Validación básica de formato
    
    return False

def validar_dni_letra(dni: str) -> bool:
    """Valida la letra del DNI."""
    letras = "TRWAGMYFPDXBNJZSQVHLCKE"
    numero = int(dni[:-1])
    letra_calculada = letras[numero % 23]
    return dni[-1] == letra_calculada

def validar_nie_letra(nie: str) -> bool:
    """Valida la letra del NIE."""
    letras = "TRWAGMYFPDXBNJZSQVHLCKE"
    prefijos = {'X': '0', 'Y': '1', 'Z': '2'}
    numero = int(prefijos[nie[0]] + nie[1:-1])
    letra_calculada = letras[numero % 23]
    return nie[-1] == letra_calculada

def validar_email(email: str) -> bool:
    """Valida formato de email."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None

def validar_telefono(telefono: str) -> bool:
    """Valida formato de teléfono español."""
    if not telefono:
        return True  # Teléfono es opcional
    
    # Limpiar espacios y caracteres especiales
    telefono_limpio = re.sub(r'[^\d+]', '', telefono.strip())
    
    # Patrones válidos
    patterns = [
        r'^\d{9}$',          # 123456789
        r'^[6-9]\d{8}$',     # Móvil español
        r'^\+34\d{9}$',      # +34123456789
        r'^0034\d{9}$'       # 0034123456789
    ]
    
    return any(re.match(pattern, telefono_limpio) for pattern in patterns)


# =========================
# AJUSTES DE LA APLICACIÓN (SIN CACHE)
# =========================

def get_ajustes_app(supabase, campos: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Obtiene ajustes de la app SIN cache para evitar problemas con objetos Supabase.
    """
    try:
        if campos:
            sel = ",".join(campos)
            res = supabase.table("ajustes_app").select(sel).single().execute()
        else:
            res = supabase.table("ajustes_app").select("*").single().execute()
        return res.data or {}
    except Exception as e:
        print(f"Error al cargar ajustes: {e}")
        return {}

def update_ajustes_app(supabase, datos: Dict[str, Any]) -> bool:
    """Actualiza ajustes de la aplicación."""
    try:
        # Verificar si existe registro
        existing = supabase.table("ajustes_app").select("id").limit(1).execute()
        
        if existing.data:
            # Actualizar registro existente
            supabase.table("ajustes_app").update(datos).eq("id", existing.data[0]["id"]).execute()
        else:
            # Crear nuevo registro
            supabase.table("ajustes_app").insert(datos).execute()
        
        return True
    except Exception as e:
        st.error(f"Error al actualizar ajustes: {e}")
        return False


# =========================
# UTILIDADES DE DATOS
# =========================

def limpiar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia un DataFrame eliminando columnas con datos complejos."""
    if df.empty:
        return df
    
    df_limpio = df.copy()
    
    # Eliminar columnas que contengan diccionarios o listas
    for col in df_limpio.columns:
        if df_limpio[col].dtype == 'object':
            # Verificar si contiene diccionarios o listas
            sample = df_limpio[col].dropna().iloc[0] if not df_limpio[col].dropna().empty else None
            if isinstance(sample, (dict, list)):
                df_limpio = df_limpio.drop(columns=[col])
    
    return df_limpio

def convertir_fechas(df: pd.DataFrame, columnas_fecha: List[str] = None) -> pd.DataFrame:
    """Convierte columnas de fecha en un DataFrame."""
    if df.empty:
        return df
    
    df_convertido = df.copy()
    
    if columnas_fecha is None:
        # Detectar columnas que podrían ser fechas
        columnas_fecha = [col for col in df.columns if 'fecha' in col.lower() or 'created_at' in col.lower() or 'updated_at' in col.lower()]
    
    for col in columnas_fecha:
        if col in df_convertido.columns:
            try:
                df_convertido[col] = pd.to_datetime(df_convertido[col], errors='coerce')
            except Exception:
                continue  # Si no se puede convertir, mantener original
    
    return df_convertido

def formatear_fecha(fecha, formato: str = "%d/%m/%Y") -> str:
    """Formatea una fecha para mostrar."""
    if pd.isna(fecha) or fecha is None:
        return ""
    
    try:
        if isinstance(fecha, str):
            fecha = pd.to_datetime(fecha)
        return fecha.strftime(formato)
    except Exception:
        return str(fecha)


# =========================
# UTILIDADES DE UI
# =========================

def mostrar_metricas(metricas: Dict[str, Any], columnas: int = 4):
    """Muestra métricas en columnas."""
    cols = st.columns(columnas)
    
    for i, (clave, valor) in enumerate(metricas.items()):
        with cols[i % columnas]:
            # Formatear clave para mostrar
            clave_formateada = clave.replace("_", " ").title()
            
            # Añadir emoji según el tipo de métrica
            emoji = "📊"
            if "empresa" in clave.lower():
                emoji = "🏢"
            elif "usuario" in clave.lower():
                emoji = "👥"
            elif "grupo" in clave.lower():
                emoji = "📚"
            elif "participante" in clave.lower():
                emoji = "🎓"
            
            st.metric(f"{emoji} {clave_formateada}", valor)

def crear_filtros_busqueda(df: pd.DataFrame, columnas_busqueda: List[str] = None) -> str:
    """Crea un widget de búsqueda para filtrar DataFrames."""
    if columnas_busqueda is None:
        columnas_busqueda = ["nombre", "email", "descripcion"]
    
    # Determinar columnas disponibles para búsqueda
    columnas_disponibles = [col for col in columnas_busqueda if col in df.columns]
    
    if not columnas_disponibles:
        return ""
    
    # Widget de búsqueda
    busqueda = st.text_input(
        "🔍 Buscar",
        placeholder=f"Buscar en: {', '.join(columnas_disponibles)}",
        help=f"Busca en las columnas: {', '.join(columnas_disponibles)}"
    )
    
    return busqueda.strip()

def aplicar_filtro_busqueda(df: pd.DataFrame, busqueda: str, columnas_busqueda: List[str] = None) -> pd.DataFrame:
    """Aplica filtro de búsqueda a un DataFrame."""
    if not busqueda or df.empty:
        return df
    
    if columnas_busqueda is None:
        columnas_busqueda = ["nombre", "email", "descripcion"]
    
    # Determinar columnas disponibles
    columnas_disponibles = [col for col in columnas_busqueda if col in df.columns]
    
    if not columnas_disponibles:
        return df
    
    # Aplicar filtro
    busqueda_lower = busqueda.lower()
    mask = pd.Series([False] * len(df))
    
    for col in columnas_disponibles:
        mask = mask | df[col].astype(str).str.lower().str.contains(busqueda_lower, na=False)
    
    return df[mask]


# =========================
# UTILIDADES DE ARCHIVOS
# =========================

def generar_nombre_archivo(prefijo: str, extension: str = "xlsx") -> str:
    """Genera un nombre de archivo con timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefijo}_{timestamp}.{extension}"

def preparar_dataframe_exportacion(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara un DataFrame para exportación limpiando datos problemáticos."""
    if df.empty:
        return df
    
    df_export = df.copy()
    
    # Limpiar columnas con datos complejos
    df_export = limpiar_dataframe(df_export)
    
    # Convertir fechas a formato legible
    df_export = convertir_fechas(df_export)
    
    # Formatear fechas para export
    for col in df_export.columns:
        if df_export[col].dtype.name.startswith('datetime'):
            df_export[col] = df_export[col].apply(lambda x: formatear_fecha(x) if pd.notna(x) else "")
    
    # Reemplazar valores nulos
    df_export = df_export.fillna("")
    
    return df_export


# =========================
# DEBUGGING Y LOGS
# =========================

def debug_dataframe(df: pd.DataFrame, nombre: str = "DataFrame"):
    """Muestra información de debug de un DataFrame."""
    if st.checkbox(f"🐛 Debug {nombre}"):
        st.write(f"**Shape:** {df.shape}")
        st.write(f"**Columnas:** {list(df.columns)}")
        st.write(f"**Tipos:** {df.dtypes.to_dict()}")
        st.write(f"**Memoria:** {df.memory_usage(deep=True).sum()} bytes")
        
        if not df.empty:
            st.write("**Muestra:**")
            st.dataframe(df.head(3))

def log_error(operation: str, error: Exception, user_id: str = None):
    """Log de errores para debugging."""
    timestamp = datetime.now().isoformat()
    error_msg = f"[{timestamp}] {operation}: {str(error)}"
    
    if user_id:
        error_msg += f" (User: {user_id})"
    
    # Por ahora solo print, en el futuro se puede guardar en BD
    print(error_msg)


# =========================
# CONSTANTES
# =========================

ESTADOS_PARTICIPANTE = ["activo", "inactivo", "finalizado", "baja"]
ROLES_USUARIO = ["admin", "gestor", "alumno", "comercial"]
TIPOS_TUTOR = ["empresa", "externo", "online"]
MODALIDADES_FORMACION = ["presencial", "online", "mixta"]

# Configuración de paginación por defecto
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
