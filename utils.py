import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Union
from io import BytesIO
import json

# ===============================
# VALIDACIONES
# ===============================

def validar_dni_cif(documento: str) -> bool:
    """
    Valida DNI, NIE y CIF españoles.
    """
    if not documento:
        return False
        
    documento = documento.upper().strip()
    
    # DNI: 8 dígitos + letra
    if re.match(r'^\d{8}[A-Z]$', documento):
        letras = "TRWAGMYFPDXBNJZSQVHLCKE"
        numero = int(documento[:8])
        letra_calculada = letras[numero % 23]
        return documento[8] == letra_calculada
    
    # NIE: X/Y/Z + 7 dígitos + letra
    if re.match(r'^[XYZ]\d{7}[A-Z]$', documento):
        # Convertir primera letra a número
        conversiones = {"X": "0", "Y": "1", "Z": "2"}
        numero_str = conversiones[documento[0]] + documento[1:8]
        numero = int(numero_str)
        letras = "TRWAGMYFPDXBNJZSQVHLCKE"
        letra_calculada = letras[numero % 23]
        return documento[8] == letra_calculada
    
    # CIF: letra + 7 dígitos + dígito/letra de control
    if re.match(r'^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$', documento):
        # Validación simplificada para CIF
        return True
    
    return False

def validar_email(email: str) -> bool:
    """Valida formato de email."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validar_telefono(telefono: str) -> bool:
    """Valida formato de teléfono español."""
    if not telefono:
        return False
    # Eliminar espacios y caracteres especiales
    tel_clean = re.sub(r'[^\d]', '', telefono)
    # Debe tener 9 dígitos y empezar por 6, 7, 8 o 9
    return bool(re.match(r'^[6789]\d{8}$', tel_clean))

# ===============================
# GESTIÓN DE FECHAS
# ===============================

def safe_date_parse(date_value, default_value=None):
    """
    Convierte de forma segura un valor a fecha, manejando diferentes formatos.
    """
    if pd.isna(date_value) or date_value is None:
        return default_value
        
    if isinstance(date_value, str):
        try:
            # Intentar diferentes formatos
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']:
                try:
                    return pd.to_datetime(date_value, format=fmt)
                except ValueError:
                    continue
            # Si no funciona ningún formato específico, usar pandas
            return pd.to_datetime(date_value)
        except Exception:
            return default_value
    
    if isinstance(date_value, (pd.Timestamp, datetime)):
        # Si es timezone-aware, convertir a naive para comparaciones
        if hasattr(date_value, 'tz') and date_value.tz is not None:
            return date_value.tz_localize(None)
        return date_value
    
    try:
        return pd.to_datetime(date_value)
    except Exception:
        return default_value

def format_date(date_value, format_str='%d/%m/%Y'):
    """Formatea una fecha de forma segura."""
    parsed_date = safe_date_parse(date_value)
    if parsed_date is None:
        return ""
    try:
        return parsed_date.strftime(format_str)
    except Exception:
        return str(date_value)

def get_date_range_filter(df: pd.DataFrame, date_column: str, days_back: int = 30):
    """Filtra un DataFrame por rango de fechas de forma segura."""
    if date_column not in df.columns or df.empty:
        return df
    
    try:
        # Convertir fechas de forma segura
        df[date_column] = df[date_column].apply(safe_date_parse)
        
        # Calcular fecha límite
        fecha_limite = datetime.now() - timedelta(days=days_back)
        
        # Filtrar registros válidos
        mask = df[date_column].notna() & (df[date_column] >= fecha_limite)
        return df[mask]
    except Exception as e:
        st.warning(f"Error al filtrar por fechas: {e}")
        return df

# ===============================
# FORMATEO Y PRESENTACIÓN
# ===============================

def format_currency(amount: Union[int, float, str], currency: str = "€") -> str:
    """Formatea una cantidad como moneda."""
    try:
        if pd.isna(amount) or amount == "":
            return "0,00 €"
        amount_float = float(amount)
        return f"{amount_float:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 €"

def format_percentage(value: Union[int, float, str], decimals: int = 1) -> str:
    """Formatea un valor como porcentaje."""
    try:
        if pd.isna(value) or value == "":
            return "0,0%"
        value_float = float(value)
        return f"{value_float:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0,0%"

def safe_int(value, default=0):
    """Convierte de forma segura a entero."""
    try:
        if pd.isna(value) or value == "":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    """Convierte de forma segura a float."""
    try:
        if pd.isna(value) or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

# ===============================
# EXPORTACIÓN DE DATOS
# ===============================

def export_csv(df: pd.DataFrame, filename: str = "export.csv", 
               show_button: bool = True, button_text: str = "📥 Descargar CSV"):
    """
    Crea un botón de descarga para exportar DataFrame a CSV.
    """
    if df.empty:
        if show_button:
            st.info("No hay datos para exportar.")
        return None
    
    try:
        # Preparar datos para exportación
        df_export = df.copy()
        
        # Convertir fechas a formato legible
        for col in df_export.columns:
            if df_export[col].dtype == 'datetime64[ns]' or 'fecha' in col.lower():
                df_export[col] = df_export[col].apply(lambda x: format_date(x) if pd.notna(x) else "")
        
        # Generar CSV
        csv_buffer = BytesIO()
        df_export.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_data = csv_buffer.getvalue()
        
        if show_button:
            st.download_button(
                label=button_text,
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                use_container_width=True
            )
        
        return csv_data
        
    except Exception as e:
        st.error(f"Error al generar CSV: {e}")
        return None

def export_excel(df: pd.DataFrame, filename: str = "export.xlsx", 
                 sheet_name: str = "Datos", show_button: bool = True):
    """
    Crea un botón de descarga para exportar DataFrame a Excel.
    """
    if df.empty:
        if show_button:
            st.info("No hay datos para exportar.")
        return None
    
    try:
        # Preparar datos
        df_export = df.copy()
        
        # Convertir fechas
        for col in df_export.columns:
            if df_export[col].dtype == 'datetime64[ns]' or 'fecha' in col.lower():
                df_export[col] = df_export[col].apply(lambda x: format_date(x) if pd.notna(x) else "")
        
        # Generar Excel
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, sheet_name=sheet_name, index=False)
        
        excel_data = excel_buffer.getvalue()
        
        if show_button:
            st.download_button(
                label="📊 Descargar Excel",
                data=excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        return excel_data
        
    except Exception as e:
        st.error(f"Error al generar Excel: {e}")
        return None

# ===============================
# GESTIÓN DE ARCHIVOS SUPABASE
# ===============================

def subir_archivo_supabase(supabase, file_content: bytes, filename: str, 
                          bucket: str = "documentos") -> Optional[str]:
    """
    Sube un archivo a Supabase Storage y retorna la URL pública.
    """
    try:
        # Limpiar nombre de archivo
        clean_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Generar nombre único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{clean_filename}"
        
        # Subir archivo
        result = supabase.storage.from_(bucket).upload(unique_filename, file_content)
        
        if result.error:
            st.error(f"Error al subir archivo: {result.error}")
            return None
        
        # Obtener URL pública
        url_result = supabase.storage.from_(bucket).get_public_url(unique_filename)
        return url_result
        
    except Exception as e:
        st.error(f"Error al subir archivo: {e}")
        return None

# ===============================
# GESTIÓN DE AJUSTES DE APP
# ===============================

@st.cache_data(ttl=300)
def get_ajustes_app(supabase, campos: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Obtiene los ajustes de la aplicación desde la base de datos.
    """
    try:
        query = supabase.table("ajustes_app").select("*").limit(1)
        result = query.execute()
        
        if result.data:
            ajustes = result.data[0]
            # Filtrar solo los campos solicitados si se especifican
            if campos:
                ajustes = {k: v for k, v in ajustes.items() if k in campos}
            return ajustes
        else:
            # Valores por defecto
            defaults = {
                "color_primario": "#4285F4",
                "color_secundario": "#34A853", 
                "color_exito": "#0F9D58",
                "color_advertencia": "#FF9800",
                "color_error": "#F44336",
                "mensaje_login": "Accede al gestor con tus credenciales.",
                "mensaje_admin": "Panel de administración completo.",
                "mensaje_gestor": "Gestiona tu empresa de forma eficiente.",
                "mensaje_alumno": "Accede a tus cursos y diplomas.",
                "logo_url": "",
                "favicon_url": "",
                "tema_oscuro": False,
                "mostrar_version": True
            }
            if campos:
                defaults = {k: v for k, v in defaults.items() if k in campos}
            return defaults
    except Exception as e:
        st.error(f"Error al cargar ajustes: {e}")
        return {}

def update_ajustes_app(supabase, ajustes: Dict[str, Any]) -> bool:
    """
    Actualiza los ajustes de la aplicación en la base de datos.
    """
    try:
        # Verificar si existe un registro
        result = supabase.table("ajustes_app").select("id").limit(1).execute()
        
        if result.data:
            # Actualizar registro existente
            supabase.table("ajustes_app").update(ajustes).eq("id", result.data[0]["id"]).execute()
        else:
            # Crear nuevo registro
            supabase.table("ajustes_app").insert(ajustes).execute()
        
        # Limpiar cache
        get_ajustes_app.clear()
        return True
        
    except Exception as e:
        st.error(f"Error al actualizar ajustes: {e}")
        return False

# ===============================
# VERIFICACIÓN DE MÓDULOS
# ===============================

def is_module_active(empresa: Optional[Dict], empresa_crm: Optional[Dict], 
                    modulo: str, fecha_actual: datetime, rol: str) -> bool:
    """
    Verifica si un módulo está activo para la empresa del usuario.
    """
    # Admin siempre tiene acceso
    if rol == "admin":
        return True
    
    # Si no hay empresa, no hay acceso
    if not empresa:
        return False
    
    # Mapeo de módulos a campos de base de datos
    modulo_mapping = {
        "formacion": "formacion_activo",
        "iso": "iso_activo", 
        "rgpd": "rgpd_activo",
        "crm": "crm_activo",
        "docu_avanzada": "docu_avanzada_activo"
    }
    
    campo_activo = modulo_mapping.get(modulo)
    if not campo_activo:
        return False
    
    # Verificar si el módulo está activo
    return empresa.get(campo_activo, False) is True

# ===============================
# GESTIÓN DE SESIÓN Y SEGURIDAD
# ===============================

def verify_user_session(supabase, session_state) -> bool:
    """
    Verifica que la sesión del usuario es válida.
    """
    try:
        if not hasattr(session_state, 'auth_session') or not session_state.auth_session:
            return False
        
        # Verificar que el token no ha expirado
        auth_session = session_state.auth_session
        if hasattr(auth_session, 'expires_at'):
            if datetime.now().timestamp() > auth_session.expires_at:
                return False
        
        return True
        
    except Exception:
        return False

def logout_user(session_state):
    """
    Cierra la sesión del usuario y limpia los datos.
    """
    try:
        # Limpiar session state
        for key in list(session_state.keys()):
            del session_state[key]
        
        # Limpiar cache
        st.cache_data.clear()
        
        st.success("Sesión cerrada correctamente.")
        st.rerun()
        
    except Exception as e:
        st.error(f"Error al cerrar sesión: {e}")

# ===============================
# NOTIFICACIONES Y MENSAJES
# ===============================

def show_success(message: str, duration: int = 3):
    """Muestra un mensaje de éxito."""
    st.success(f"✅ {message}")

def show_error(message: str, duration: int = 5):
    """Muestra un mensaje de error."""
    st.error(f"❌ {message}")

def show_warning(message: str, duration: int = 4):
    """Muestra un mensaje de advertencia."""
    st.warning(f"⚠️ {message}")

def show_info(message: str, duration: int = 3):
    """Muestra un mensaje informativo."""
    st.info(f"ℹ️ {message}")

# ===============================
# OPTIMIZACIÓN DE MEMORIA
# ===============================

def optimize_dataframe_memory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optimiza el uso de memoria de un DataFrame.
    """
    if df.empty:
        return df
    
    df_optimized = df.copy()
    
    # Optimizar columnas numéricas
    for col in df_optimized.select_dtypes(include=['int64']).columns:
        df_optimized[col] = pd.to_numeric(df_optimized[col], downcast='integer')
    
    for col in df_optimized.select_dtypes(include=['float64']).columns:
        df_optimized[col] = pd.to_numeric(df_optimized[col], downcast='float')
    
    # Optimizar columnas de texto
    for col in df_optimized.select_dtypes(include=['object']).columns:
        if df_optimized[col].nunique() / len(df_optimized) < 0.5:  # Si hay muchos valores repetidos
            df_optimized[col] = df_optimized[col].astype('category')
    
    return df_optimized

# ===============================
# HERRAMIENTAS DE DEBUGGING
# ===============================

def debug_info(obj, name: str = "Object"):
    """Muestra información de debugging sobre un objeto."""
    if st.checkbox(f"🐛 Debug: {name}"):
        st.write(f"**Tipo:** {type(obj)}")
        if hasattr(obj, 'shape'):
            st.write(f"**Shape:** {obj.shape}")
        if hasattr(obj, 'columns'):
            st.write(f"**Columnas:** {list(obj.columns)}")
        st.write(f"**Contenido:**")
        st.write(obj)

def performance_timer():
    """Context manager para medir tiempo de ejecución."""
    class Timer:
        def __enter__(self):
            self.start = datetime.now()
            return self
        
        def __exit__(self, *args):
            self.end = datetime.now()
            self.duration = (self.end - self.start).total_seconds()
            st.caption(f"⏱️ Tiempo de ejecución: {self.duration:.2f} segundos")
    
    return Timer()

# ===============================
# CACHE INTELIGENTE
# ===============================

def smart_cache_key(*args, **kwargs) -> str:
    """Genera una clave de cache inteligente basada en los argumentos."""
    import hashlib
    
    # Convertir argumentos a string
    args_str = str(args) + str(sorted(kwargs.items()))
    
    # Generar hash
    return hashlib.md5(args_str.encode()).hexdigest()[:16]

def cache_with_ttl(ttl_seconds: int = 300):
    """Decorador para cache con TTL personalizado."""
    def decorator(func):
        return st.cache_data(ttl=ttl_seconds)(func)
    return decorator
