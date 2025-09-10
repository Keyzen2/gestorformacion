import streamlit as st
import pandas as pd
import re
from datetime import datetime, date
from typing import Dict, Any, Optional, List
import base64
import io

# =========================
# CONFIGURACIÓN Y CONSTANTES
# =========================
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
DNI_REGEX = r'^[0-9]{8}[TRWAGMYFPDXBNJZSQVHLCKE]$'
NIE_REGEX = r'^[XYZ][0-9]{7}[TRWAGMYFPDXBNJZSQVHLCKE]$'
CIF_REGEX = r'^[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$'

# =========================
# VALIDACIONES OPTIMIZADAS
# =========================
def validar_email(email: str) -> bool:
    """Valida formato de email."""
    if not email:
        return False
    return bool(re.match(EMAIL_REGEX, email.strip()))

def validar_dni_cif(documento: str) -> bool:
    """
    Valida DNI, NIE o CIF español.
    Optimizado y simplificado.
    """
    if not documento:
        return False
    
    doc = documento.upper().strip()
    
    # Validar DNI
    if re.match(DNI_REGEX, doc):
        letras = 'TRWAGMYFPDXBNJZSQVHLCKE'
        numero = int(doc[:8])
        letra = doc[8]
        return letras[numero % 23] == letra
    
    # Validar NIE
    if re.match(NIE_REGEX, doc):
        letras = 'TRWAGMYFPDXBNJZSQVHLCKE'
        # Convertir primera letra a número
        primer_caracter = {'X': '0', 'Y': '1', 'Z': '2'}[doc[0]]
        numero = int(primer_caracter + doc[1:8])
        letra = doc[8]
        return letras[numero % 23] == letra
    
    # Validar CIF
    if re.match(CIF_REGEX, doc):
        return True  # Validación básica de formato
    
    return False

def validar_telefono(telefono: str) -> bool:
    """Valida formato de teléfono español básico."""
    if not telefono:
        return True  # Campo opcional
    
    # Limpiar espacios y caracteres especiales
    tel = re.sub(r'[\s\-\(\)]', '', telefono)
    
    # Validar formato español básico
    return bool(re.match(r'^[6789]\d{8}$', tel) or re.match(r'^\+34[6789]\d{8}$', tel))

# =========================
# CACHE Y OPTIMIZACIÓN
# =========================
@st.cache_data(ttl=300)
def get_ajustes_app(supabase, campos: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Obtiene ajustes de la aplicación con cache optimizado.
    
    Args:
        supabase: Cliente de Supabase
        campos: Lista específica de campos a obtener (None = todos)
    
    Returns:
        Dict con los ajustes de la aplicación
    """
    try:
        query = supabase.table("ajustes_app").select("*")
        
        # Si se especifican campos, optimizar la consulta
        if campos:
            campos_str = ",".join(campos)
            query = supabase.table("ajustes_app").select(campos_str)
        
        res = query.execute()
        
        if res.data and len(res.data) > 0:
            return res.data[0]
        else:
            # Valores por defecto si no existen ajustes
            return {
                "nombre_app": "Gestor de Formación",
                "color_primario": "#4285F4",
                "color_secundario": "#5f6368",
                "mensaje_login": "Accede al gestor con tus credenciales.",
                "mensaje_footer": "© 2025 Gestor de Formación · Streamlit + Supabase"
            }
    except Exception as e:
        st.error(f"⚠️ Error al cargar ajustes: {e}")
        return {}

def update_ajustes_app(supabase, datos: Dict[str, Any]) -> bool:
    """
    Actualiza ajustes de la aplicación y limpia cache.
    
    Args:
        supabase: Cliente de Supabase
        datos: Diccionario con los datos a actualizar
    
    Returns:
        bool: True si se actualizó correctamente
    """
    try:
        # Preparar datos para actualización
        datos_limpios = {k: v for k, v in datos.items() if v is not None}
        datos_limpios["updated_at"] = datetime.now().isoformat()
        
        # Intentar actualizar primero
        res = supabase.table("ajustes_app").update(datos_limpios).execute()
        
        # Si no existe registro, crear uno nuevo
        if not res.data:
            datos_limpios["created_at"] = datetime.now().isoformat()
            supabase.table("ajustes_app").insert(datos_limpios).execute()
        
        # Limpiar cache
        get_ajustes_app.clear()
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error al actualizar ajustes: {e}")
        return False

# =========================
# FUNCIONES DE EXPORTACIÓN
# =========================
def export_csv(df: pd.DataFrame, filename: str = "datos.csv") -> None:
    """
    Crea botón de descarga optimizado para CSV.
    
    Args:
        df: DataFrame a exportar
        filename: Nombre del archivo
    """
    if df.empty:
        return
    
    try:
        # Preparar CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_data = csv_buffer.getvalue()
        
        # Crear botón de descarga
        st.download_button(
            label=f"📥 Exportar {len(df)} registros a CSV",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            help=f"Descarga {len(df)} registros en formato CSV"
        )
        
    except Exception as e:
        st.error(f"⚠️ Error al exportar: {e}")

def export_excel(df: pd.DataFrame, filename: str = "datos.xlsx", sheet_name: str = "Datos") -> None:
    """
    Crea botón de descarga para Excel.
    
    Args:
        df: DataFrame a exportar
        filename: Nombre del archivo
        sheet_name: Nombre de la hoja
    """
    if df.empty:
        return
    
    try:
        # Crear archivo Excel en memoria
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        excel_data = excel_buffer.getvalue()
        
        # Crear botón de descarga
        st.download_button(
            label=f"📊 Exportar {len(df)} registros a Excel",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help=f"Descarga {len(df)} registros en formato Excel"
        )
        
    except Exception as e:
        st.error(f"⚠️ Error al exportar Excel: {e}")

# =========================
# FUNCIONES DE FORMATEO
# =========================
def format_date(fecha: Any, formato: str = "%d/%m/%Y") -> str:
    """
    Formatea fechas de manera segura.
    
    Args:
        fecha: Fecha en cualquier formato
        formato: Formato de salida
    
    Returns:
        str: Fecha formateada o cadena vacía si hay error
    """
    if not fecha:
        return ""
    
    try:
        if isinstance(fecha, str):
            # Intentar parsear string
            fecha_obj = pd.to_datetime(fecha, errors='coerce')
            if pd.isna(fecha_obj):
                return ""
            return fecha_obj.strftime(formato)
        elif isinstance(fecha, (date, datetime)):
            return fecha.strftime(formato)
        else:
            return str(fecha)
    except Exception:
        return ""

def format_currency(amount: Any, currency: str = "€") -> str:
    """
    Formatea cantidades monetarias.
    
    Args:
        amount: Cantidad a formatear
        currency: Símbolo de moneda
    
    Returns:
        str: Cantidad formateada
    """
    try:
        if amount is None or amount == "":
            return "0,00 " + currency
        
        amount_float = float(amount)
        return f"{amount_float:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 " + currency

def format_percentage(value: Any, decimals: int = 1) -> str:
    """
    Formatea porcentajes.
    
    Args:
        value: Valor a formatear
        decimals: Número de decimales
    
    Returns:
        str: Porcentaje formateado
    """
    try:
        if value is None or value == "":
            return "0%"
        
        value_float = float(value)
        return f"{value_float:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0%"

# =========================
# FUNCIONES DE UI
# =========================
def show_success(message: str, icon: str = "✅") -> None:
    """Muestra mensaje de éxito estandarizado."""
    st.success(f"{icon} {message}")

def show_error(message: str, icon: str = "❌") -> None:
    """Muestra mensaje de error estandarizado."""
    st.error(f"{icon} {message}")

def show_warning(message: str, icon: str = "⚠️") -> None:
    """Muestra mensaje de advertencia estandarizado."""
    st.warning(f"{icon} {message}")

def show_info(message: str, icon: str = "ℹ️") -> None:
    """Muestra mensaje informativo estandarizado."""
    st.info(f"{icon} {message}")

def create_metric_card(title: str, value: Any, delta: Any = None, icon: str = "📊") -> str:
    """
    Crea tarjeta de métrica HTML personalizada.
    
    Args:
        title: Título de la métrica
        value: Valor principal
        delta: Cambio o valor secundario
        icon: Icono a mostrar
    
    Returns:
        str: HTML de la tarjeta
    """
    delta_html = ""
    if delta is not None:
        delta_html = f'<p style="font-size: 0.8em; color: #666; margin: 0;">{delta}</p>'
    
    return f"""
    <div style="
        border: 1px solid #e1e5e9;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    ">
        <h3 style="margin: 0; font-size: 1.2em; color: #1f2937;">
            {icon} {title}
        </h3>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.8em; font-weight: bold; color: #4285f4;">
            {value}
        </p>
        {delta_html}
    </div>
    """

# =========================
# FUNCIONES DE SESIÓN
# =========================
def init_session_state() -> None:
    """Inicializa variables de sesión por defecto."""
    defaults = {
        "authenticated": False,
        "role": None,
        "user": {},
        "empresa": {},
        "empresa_crm": {},
        "page": "home",
        "last_activity": datetime.now()
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def clear_session_state() -> None:
    """Limpia todas las variables de sesión."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]

def check_session_timeout(timeout_minutes: int = 30) -> bool:
    """
    Verifica si la sesión ha caducado.
    
    Args:
        timeout_minutes: Minutos de timeout
    
    Returns:
        bool: True si ha caducado
    """
    if "last_activity" not in st.session_state:
        return True
    
    last_activity = st.session_state.get("last_activity")
    if not last_activity:
        return True
    
    now = datetime.now()
    time_diff = (now - last_activity).total_seconds() / 60
    
    return time_diff > timeout_minutes

def update_last_activity() -> None:
    """Actualiza timestamp de última actividad."""
    st.session_state.last_activity = datetime.now()

# =========================
# FUNCIONES DE DATOS
# =========================
def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Obtiene valor de diccionario de manera segura.
    
    Args:
        data: Diccionario de datos
        key: Clave a buscar
        default: Valor por defecto
    
    Returns:
        Valor encontrado o default
    """
    try:
        return data.get(key, default) if data else default
    except (AttributeError, TypeError):
        return default

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia DataFrame eliminando valores nulos y optimizando tipos.
    
    Args:
        df: DataFrame a limpiar
    
    Returns:
        DataFrame limpio
    """
    if df.empty:
        return df
    
    try:
        # Limpiar valores nulos
        df_clean = df.copy()
        
        # Reemplazar None y NaN por valores apropiados
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                df_clean[col] = df_clean[col].fillna("")
            elif df_clean[col].dtype in ['int64', 'float64']:
                df_clean[col] = df_clean[col].fillna(0)
            elif df_clean[col].dtype == 'bool':
                df_clean[col] = df_clean[col].fillna(False)
        
        return df_clean
    except Exception as e:
        st.error(f"⚠️ Error al limpiar datos: {e}")
        return df

def optimize_dataframe_memory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optimiza uso de memoria del DataFrame.
    
    Args:
        df: DataFrame a optimizar
    
    Returns:
        DataFrame optimizado
    """
    if df.empty:
        return df
    
    try:
        df_opt = df.copy()
        
        for col in df_opt.columns:
            col_type = df_opt[col].dtype
            
            if col_type != 'object':
                c_min = df_opt[col].min()
                c_max = df_opt[col].max()
                
                if str(col_type)[:3] == 'int':
                    if c_min > -128 and c_max < 127:
                        df_opt[col] = df_opt[col].astype('int8')
                    elif c_min > -32768 and c_max < 32767:
                        df_opt[col] = df_opt[col].astype('int16')
                    elif c_min > -2147483648 and c_max < 2147483647:
                        df_opt[col] = df_opt[col].astype('int32')
                
                elif str(col_type)[:5] == 'float':
                    df_opt[col] = df_opt[col].astype('float32')
        
        return df_opt
    except Exception as e:
        st.error(f"⚠️ Error al optimizar memoria: {e}")
        return df

# =========================
# FUNCIONES DE LOGGING
# =========================
def log_user_action(action: str, details: str = "", user_id: str = None) -> None:
    """
    Registra acciones del usuario (simplificado para desarrollo).
    
    Args:
        action: Tipo de acción realizada
        details: Detalles adicionales
        user_id: ID del usuario (opcional)
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = user_id or st.session_state.get("user", {}).get("id", "unknown")
        
        # En desarrollo, solo log en consola
        print(f"[{timestamp}] USER:{user} ACTION:{action} DETAILS:{details}")
        
        # En producción, aquí se guardaría en base de datos
        # supabase.table("user_logs").insert({
        #     "user_id": user,
        #     "action": action,
        #     "details": details,
        #     "timestamp": timestamp
        # }).execute()
        
    except Exception as e:
        print(f"Error logging action: {e}")

# =========================
# FUNCIONES DE NOTIFICACIÓN
# =========================
def send_notification(
    tipo: str,
    titulo: str, 
    mensaje: str,
    user_id: str = None,
    email: str = None
) -> bool:
    """
    Sistema de notificaciones simplificado.
    
    Args:
        tipo: Tipo de notificación (info, success, warning, error)
        titulo: Título de la notificación
        mensaje: Mensaje completo
        user_id: ID del usuario destinatario
        email: Email del destinatario
    
    Returns:
        bool: True si se envió correctamente
    """
    try:
        # Por ahora solo mostramos en UI
        icon_map = {
            "info": "ℹ️",
            "success": "✅", 
            "warning": "⚠️",
            "error": "❌"
        }
        
        icon = icon_map.get(tipo, "📢")
        
        if tipo == "success":
            st.success(f"{icon} **{titulo}** - {mensaje}")
        elif tipo == "warning":
            st.warning(f"{icon} **{titulo}** - {mensaje}")
        elif tipo == "error":
            st.error(f"{icon} **{titulo}** - {mensaje}")
        else:
            st.info(f"{icon} **{titulo}** - {mensaje}")
        
        # Log de la notificación
        log_user_action(
            action="notification_sent",
            details=f"Tipo:{tipo} Titulo:{titulo}",
            user_id=user_id
        )
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error al enviar notificación: {e}")
        return False

# =========================
# FUNCIONES DE SEGURIDAD
# =========================
def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitiza entrada de texto del usuario.
    
    Args:
        text: Texto a sanitizar
        max_length: Longitud máxima permitida
    
    Returns:
        str: Texto sanitizado
    """
    if not text:
        return ""
    
    # Limpiar texto básico
    sanitized = str(text).strip()[:max_length]
    
    # Eliminar caracteres potencialmente peligrosos
    sanitized = re.sub(r'[<>"\']', '', sanitized)
    
    return sanitized

def check_permission(required_role: str, user_role: str = None) -> bool:
    """
    Verifica permisos de usuario.
    
    Args:
        required_role: Rol requerido
        user_role: Rol actual del usuario
    
    Returns:
        bool: True si tiene permisos
    """
    if not user_role:
        user_role = st.session_state.get("role")
    
    if not user_role:
        return False
    
    # Jerarquía de roles
    role_hierarchy = {
        "admin": 4,
        "gestor": 3,
        "comercial": 2,
        "alumno": 1
    }
    
    user_level = role_hierarchy.get(user_role, 0)
    required_level = role_hierarchy.get(required_role, 99)
    
    return user_level >= required_level

# =========================
# FUNCIONES DE MÉTRICAS BÁSICAS
# =========================
@st.cache_data(ttl=300)
def get_metricas_admin() -> Dict[str, int]:
    """Obtiene métricas para el panel de admin (versión simplificada)."""
    try:
        # Esta función se debe implementar según la estructura de tu BD
        # Por ahora retornamos valores de ejemplo
        return {
            "empresas": 25,
            "usuarios": 150,
            "cursos": 42,
            "grupos": 67
        }
    except Exception as e:
        st.error(f"⚠️ Error al cargar métricas de admin: {e}")
        return {"empresas": 0, "usuarios": 0, "cursos": 0, "grupos": 0}

@st.cache_data(ttl=300)
def get_metricas_gestor(empresa_id: str) -> Dict[str, int]:
    """Obtiene métricas para el panel del gestor."""
    try:
        # Esta función se debe implementar según la estructura de tu BD
        # Por ahora retornamos valores de ejemplo
        return {
            "grupos": 8,
            "participantes": 45,
            "documentos": 23,
            "diplomas": 12
        }
    except Exception as e:
        st.error(f"⚠️ Error al cargar métricas de gestor: {e}")
        return {"grupos": 0, "participantes": 0, "documentos": 0, "diplomas": 0}

# =========================
# FUNCIONES AUXILIARES
# =========================
def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Trunca texto a longitud específica.
    
    Args:
        text: Texto a truncar
        max_length: Longitud máxima
        suffix: Sufijo para texto truncado
    
    Returns:
        str: Texto truncado
    """
    if not text:
        return ""
    
    text_str = str(text)
    if len(text_str) <= max_length:
        return text_str
    
    return text_str[:max_length - len(suffix)] + suffix

def generate_slug(text: str) -> str:
    """
    Genera slug URL-friendly desde texto.
    
    Args:
        text: Texto original
    
    Returns:
        str: Slug generado
    """
    if not text:
        return ""
    
    # Convertir a minúsculas y reemplazar espacios/caracteres especiales
    slug = str(text).lower()
    slug = re.sub(r'[àáâãäå]', 'a', slug)
    slug = re.sub(r'[èéêë]', 'e', slug)
    slug = re.sub(r'[ìíîï]', 'i', slug)
    slug = re.sub(r'[òóôõö]', 'o', slug)
    slug = re.sub(r'[ùúûü]', 'u', slug)
    slug = re.sub(r'[ñ]', 'n', slug)
    slug = re.sub(r'[ç]', 'c', slug)
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    
    return slug

def get_file_extension(filename: str) -> str:
    """
    Obtiene extensión de archivo.
    
    Args:
        filename: Nombre del archivo
    
    Returns:
        str: Extensión del archivo
    """
    if not filename or '.' not in filename:
        return ""
    
    return filename.split('.')[-1].lower()

def is_valid_file_type(filename: str, allowed_types: List[str]) -> bool:
    """
    Verifica si el tipo de archivo está permitido.
    
    Args:
        filename: Nombre del archivo
        allowed_types: Lista de extensiones permitidas
    
    Returns:
        bool: True si está permitido
    """
    if not filename or not allowed_types:
        return False
    
    extension = get_file_extension(filename)
    return extension in [t.lower() for t in allowed_types]

# =========================
# FUNCIONES DE DEBUGGING
# =========================
def debug_session_state() -> None:
    """Muestra información de depuración del estado de sesión."""
    if st.checkbox("🐛 Mostrar debug info"):
        st.subheader("Debug - Session State")
        st.json(dict(st.session_state))

def debug_dataframe(df: pd.DataFrame, name: str = "DataFrame") -> None:
    """
    Muestra información de depuración de un DataFrame.
    
    Args:
        df: DataFrame a analizar
        name: Nombre descriptivo
    """
    if st.checkbox(f"🐛 Debug {name}"):
        st.subheader(f"Debug - {name}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Filas", len(df))
        with col2:
            st.metric("Columnas", len(df.columns))
        with col3:
            memory_usage = df.memory_usage(deep=True).sum() / 1024**2
            st.metric("Memoria (MB)", f"{memory_usage:.2f}")
        
        st.subheader("Tipos de datos")
        st.dataframe(df.dtypes.to_frame("Tipo"))
        
        st.subheader("Valores nulos")
        nulls = df.isnull().sum()
        if nulls.sum() > 0:
            st.dataframe(nulls[nulls > 0].to_frame("Nulos"))
        else:
            st.success("No hay valores nulos")
        
        if not df.empty:
            st.subheader("Muestra de datos")
            st.dataframe(df.head())

# =========================
# INICIALIZACIÓN
# =========================
def init_utils():
    """Inicializa utilidades básicas al cargar el módulo."""
    # Configurar pandas para mejor rendimiento
    pd.options.mode.chained_assignment = None
    pd.options.display.max_columns = None
    pd.options.display.max_colwidth = 100
    
    # Inicializar session state si no existe
    init_session_state()

# Llamar inicialización automáticamente
init_utils()


