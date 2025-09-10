"""
Funciones de utilidad para el gestor de formación.
Versión mejorada con validaciones robustas y funciones optimizadas.
"""

import streamlit as st
import pandas as pd
import re
import base64
from datetime import datetime, date
from io import BytesIO

# =========================
# VALIDACIONES
# =========================

def validar_dni_cif(documento: str) -> bool:
    """
    Valida DNI, NIE o CIF.
    
    Args:
        documento: String con el documento a validar
        
    Returns:
        bool: True si es válido, False en caso contrario
    """
    if not documento:
        return False
        
    documento = documento.upper().replace('-', '').replace(' ', '')
    
    # Validar DNI (8 números + letra)
    if re.match(r'^[0-9]{8}[A-Z]$', documento):
        letras = 'TRWAGMYFPDXBNJZSQVHLCKE'
        numero = int(documento[0:8])
        letra = documento[8]
        return letras[numero % 23] == letra
        
    # Validar NIE (X/Y/Z + 7 números + letra)
    elif re.match(r'^[XYZ][0-9]{7}[A-Z]$', documento):
        tabla = {'X': 0, 'Y': 1, 'Z': 2}
        letras = 'TRWAGMYFPDXBNJZSQVHLCKE'
        
        # Sustituir la letra inicial por su valor numérico
        numero = int(str(tabla[documento[0]]) + documento[1:8])
        letra = documento[8]
        return letras[numero % 23] == letra
        
    # Validar CIF (letra + 7 números + dígito control/letra)
    elif re.match(r'^[ABCDEFGHJKLMNPQRSUVW][0-9]{7}[0-9A-J]$', documento):
        letra_ini = documento[0]
        numeros = documento[1:8]
        control = documento[8]
        
        # Algoritmo de validación de CIF
        suma_a = 0
        for i in [1, 3, 5, 7]:
            if i < len(numeros):
                suma_a += int(numeros[i-1])
                
        suma_b = 0
        for i in [2, 4, 6, 8]:
            if i-1 < len(numeros):
                digit = 2 * int(numeros[i-1])
                if digit > 9:
                    digit = digit - 9
                suma_b += digit
                
        suma = suma_a + suma_b
        unidad = 10 - (suma % 10)
        if unidad == 10:
            unidad = 0
            
        # Para CIFs que deben tener letra de control
        letras_control = 'JABCDEFGHI'
        if letra_ini in 'KPQRSNW':
            return letras_control[unidad] == control
        else:
            # Para CIFs que pueden tener número o letra
            return str(unidad) == control or letras_control[unidad] == control
    
    return False

def validar_email(email: str) -> bool:
    """
    Valida un email utilizando una expresión regular.
    
    Args:
        email: Email a validar
        
    Returns:
        bool: True si es válido, False en caso contrario
    """
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validar_telefono(telefono: str) -> bool:
    """
    Valida un número de teléfono español.
    
    Args:
        telefono: Número a validar
        
    Returns:
        bool: True si es válido, False en caso contrario
    """
    if not telefono:
        return False
    
    # Eliminar espacios y guiones
    telefono = telefono.replace(' ', '').replace('-', '')
    
    # Teléfono español: 9 dígitos empezando por 6, 7, 8 o 9
    return bool(re.match(r'^[6789]\d{8}$', telefono))

def es_fecha_valida(fecha_str: str) -> bool:
    """
    Verifica si una cadena se puede convertir a fecha.
    
    Args:
        fecha_str: Fecha en formato string
        
    Returns:
        bool: True si es una fecha válida, False en caso contrario
    """
    if not fecha_str:
        return False
        
    try:
        # Intentar convertir a formato fecha
        if isinstance(fecha_str, (date, datetime)):
            return True
            
        # Si es string, intentar convertir
        pd.to_datetime(fecha_str)
        return True
    except:
        return False

# =========================
# EXPORTACIÓN DE DATOS
# =========================

def export_csv(df: pd.DataFrame, filename: str = "export.csv"):
    """
    Genera un botón para exportar un DataFrame a CSV.
    
    Args:
        df: DataFrame a exportar
        filename: Nombre del archivo a generar
        
    Returns:
        None
    """
    if df is None or df.empty:
        return
    
    # Preparar datos para descarga
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 Descargar CSV</a>'
    st.markdown(href, unsafe_allow_html=True)

def export_excel(df: pd.DataFrame, filename: str = "export.xlsx"):
    """
    Genera un botón para exportar un DataFrame a Excel.
    
    Args:
        df: DataFrame a exportar
        filename: Nombre del archivo a generar
        
    Returns:
        None
    """
    if df is None or df.empty:
        return
    
    # Crear buffer y guardar Excel
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    
    # Autoajustar columnas
    worksheet = writer.sheets['Sheet1']
    for i, col in enumerate(df.columns):
        # Establecer ancho basado en el contenido
        max_len = max(df[col].astype(str).str.len().max(), len(str(col))) + 2
        worksheet.set_column(i, i, max_len)
    
    writer.close()
    
    # Preparar para descarga
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode('utf-8')
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 Descargar Excel</a>'
    st.markdown(href, unsafe_allow_html=True)

# =========================
# FORMATEO DE DATOS
# =========================

def formato_fecha(fecha, formato: str = "%d/%m/%Y"):
    """
    Formatea una fecha para mostrar.
    
    Args:
        fecha: Fecha a formatear (str, datetime, date)
        formato: Formato deseado
        
    Returns:
        str: Fecha formateada o cadena vacía si no es válida
    """
    if not fecha:
        return ""
        
    try:
        if isinstance(fecha, str):
            fecha = pd.to_datetime(fecha)
        return fecha.strftime(formato)
    except:
        return str(fecha)

def formato_moneda(valor, simbolo: str = "€"):
    """
    Formatea un valor como moneda.
    
    Args:
        valor: Valor numérico
        simbolo: Símbolo de la moneda
        
    Returns:
        str: Valor formateado como moneda
    """
    try:
        valor_num = float(valor)
        return f"{valor_num:,.2f} {simbolo}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(valor)

def formato_porcentaje(valor):
    """
    Formatea un valor como porcentaje.
    
    Args:
        valor: Valor numérico (0-1)
        
    Returns:
        str: Valor formateado como porcentaje
    """
    try:
        valor_num = float(valor)
        return f"{valor_num * 100:.1f}%"
    except:
        return str(valor)

# =========================
# UTILIDADES DE CACHE
# =========================

def clear_cache_by_prefix(prefix: str):
    """
    Limpia el cache para funciones que comienzan con cierto prefijo.
    
    Args:
        prefix: Prefijo para identificar funciones en cache
        
    Returns:
        int: Número de funciones limpiadas
    """
    count = 0
    for key in list(st.session_state.keys()):
        if key.startswith(f"_cache_data_{prefix}"):
            del st.session_state[key]
            count += 1
    return count

def optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optimiza un DataFrame para reducir uso de memoria.
    
    Args:
        df: DataFrame a optimizar
        
    Returns:
        pd.DataFrame: DataFrame optimizado
    """
    if df is None or df.empty:
        return df
        
    df_optimized = df.copy()
    
    # Optimizar tipos de datos
    for col in df_optimized.columns:
        # Convertir a categoría columnas con pocos valores únicos
        if df_optimized[col].dtype == 'object':
            num_unique = df_optimized[col].nunique()
            num_total = len(df_optimized)
            if num_unique / num_total < 0.5:  # Si menos del 50% son únicos
                df_optimized[col] = df_optimized[col].astype('category')
                
        # Optimizar enteros
        elif df_optimized[col].dtype == 'int64':
            if df_optimized[col].min() >= 0:
                if df_optimized[col].max() < 255:
                    df_optimized[col] = df_optimized[col].astype('uint8')
                elif df_optimized[col].max() < 65535:
                    df_optimized[col] = df_optimized[col].astype('uint16')
                else:
                    df_optimized[col] = df_optimized[col].astype('uint32')
                    
        # Optimizar flotantes
        elif df_optimized[col].dtype == 'float64':
            df_optimized[col] = df_optimized[col].astype('float32')
            
    return df_optimized

# =========================
# DEBUGGING Y DESARROLLO
# =========================

def debug_dataframe(df: pd.DataFrame, nombre: str = "DataFrame"):
    """
    Muestra información detallada sobre un DataFrame para debugging.
    
    Args:
        df: DataFrame a analizar
        nombre: Nombre para identificar el DataFrame
        
    Returns:
        None
    """
    if df is None:
        st.warning(f"⚠️ {nombre} es None")
        return
        
    if df.empty:
        st.warning(f"⚠️ {nombre} está vacío")
        return
        
    # Crear expander para mostrar debug info
    with st.expander(f"🔍 Debug: {nombre}"):
        st.write(f"Filas: {len(df)}, Columnas: {len(df.columns)}")
        
        # Información de tipos
        st.write("Tipos de datos:")
        st.write(df.dtypes)
        
        # Valores nulos
        nulos = df.isna().sum()
        if nulos.sum() > 0:
            st.write("Valores nulos:")
            st.write(nulos[nulos > 0])
            
        # Muestra primeras filas
        st.write("Primeras filas:")
        st.dataframe(df.head(3))
        
        # Estadísticas para columnas numéricas
        if any(df.select_dtypes(include=['number']).columns):
            st.write("Estadísticas numéricas:")
            st.write(df.describe())

def log_accion(accion: str, usuario_id: str, detalles: dict = None):
    """
    Registra una acción en el log de la aplicación.
    
    Args:
        accion: Nombre de la acción
        usuario_id: ID del usuario que realizó la acción
        detalles: Diccionario con detalles adicionales
        
    Returns:
        None
    """
    if not hasattr(st.session_state, "log_acciones"):
        st.session_state.log_acciones = []
        
    # Crear entrada de log
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "accion": accion,
        "usuario_id": usuario_id,
        "detalles": detalles or {}
    }
    
    # Añadir al log
    st.session_state.log_acciones.append(log_entry)
    
    # Limitar tamaño del log
    if len(st.session_state.log_acciones) > 1000:
        st.session_state.log_acciones = st.session_state.log_acciones[-1000:]

# =========================
# SEGURIDAD Y PERMISOS
# =========================

def verificar_permiso(rol: str, modulos_requeridos: list = None) -> bool:
    """
    Verifica si un rol tiene permiso para acceder a ciertos módulos.
    
    Args:
        rol: Rol del usuario (admin, gestor, alumno)
        modulos_requeridos: Lista de módulos requeridos
        
    Returns:
        bool: True si tiene permiso, False en caso contrario
    """
    if not rol:
        return False
        
    # Admin tiene acceso a todo
    if rol == "admin":
        return True
        
    # Sin módulos especificados, verificar solo rol
    if not modulos_requeridos:
        return rol in ["admin", "gestor"]
        
    # Verificar permisos específicos por rol
    permisos_por_rol = {
        "gestor": ["formacion", "iso", "rgpd", "documentos"],
        "alumno": ["cursos", "diplomas"],
        "tutor": ["grupos", "evaluaciones"],
        "comercial": ["clientes", "oportunidades"]
    }
    
    if rol not in permisos_por_rol:
        return False
        
    # Verificar si todos los módulos requeridos están permitidos
    return all(modulo in permisos_por_rol[rol] for modulo in modulos_requeridos)

def generar_password_segura(longitud: int = 10) -> str:
    """
    Genera una contraseña segura aleatoria.
    
    Args:
        longitud: Longitud de la contraseña
        
    Returns:
        str: Contraseña generada
    """
    import random
    import string
    
    # Definir conjuntos de caracteres
    minusculas = string.ascii_lowercase
    mayusculas = string.ascii_uppercase
    numeros = string.digits
    especiales = "!@#$%&*-_+=?"
    
    # Asegurar al menos un carácter de cada tipo
    pwd = [
        random.choice(minusculas),
        random.choice(mayusculas),
        random.choice(numeros),
        random.choice(especiales)
    ]
    
    # Completar hasta la longitud deseada
    caracteres = minusculas + mayusculas + numeros + especiales
    pwd.extend(random.choice(caracteres) for _ in range(longitud - 4))
    
    # Mezclar y convertir a string
    random.shuffle(pwd)
    return ''.join(pwd)

# =========================
# NOTIFICACIONES Y MENSAJES
# =========================

def mostrar_notificacion(tipo: str, mensaje: str, duracion: int = 3):
    """
    Muestra una notificación estilizada.
    
    Args:
        tipo: Tipo de notificación (success, info, warning, error)
        mensaje: Texto de la notificación
        duracion: Duración en segundos
        
    Returns:
        None
    """
    # Mapeo de tipos a iconos y colores
    estilos = {
        "success": {"icono": "✅", "color": "#28a745"},
        "info": {"icono": "ℹ️", "color": "#17a2b8"},
        "warning": {"icono": "⚠️", "color": "#ffc107"},
        "error": {"icono": "❌", "color": "#dc3545"}
    }
    
    estilo = estilos.get(tipo, estilos["info"])
    
    # Crear HTML para notificación
    html = f"""
    <div style="
        padding: 10px 15px;
        border-radius: 5px;
        background-color: {estilo['color']}22;
        border-left: 5px solid {estilo['color']};
        margin-bottom: 10px;
        animation: fadeOut {duracion}s forwards {duracion-0.5}s;
    ">
        <div style="display: flex; align-items: center;">
            <div style="font-size: 1.2rem; margin-right: 10px;">{estilo['icono']}</div>
            <div>{mensaje}</div>
        </div>
    </div>
    <style>
    @keyframes fadeOut {{
        from {{ opacity: 1; }}
        to {{ opacity: 0; display: none; }}
    }}
    </style>
    """
    
    st.markdown(html, unsafe_allow_html=True)

def confirmar_accion(mensaje: str, btn_confirmar: str = "Confirmar", btn_cancelar: str = "Cancelar"):
    """
    Muestra un diálogo de confirmación.
    
    Args:
        mensaje: Mensaje de confirmación
        btn_confirmar: Texto del botón de confirmación
        btn_cancelar: Texto del botón de cancelación
        
    Returns:
        bool: True si se confirma, False si se cancela
    """
    st.warning(mensaje)
    
    col1, col2 = st.columns(2)
    with col1:
        confirmar = st.button(btn_confirmar, type="primary")
    with col2:
        cancelar = st.button(btn_cancelar)
        
    if confirmar:
        return True
    if cancelar:
        return False
        
    # Si no se ha pulsado ningún botón, devolver None
    return None
