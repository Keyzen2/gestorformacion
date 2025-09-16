import streamlit as st
import pandas as pd
import re
import base64
from datetime import datetime, date
from io import BytesIO
from typing import Optional, List, Dict, Any
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from lxml import etree
import xml.etree.ElementTree as ET
import uuid
import requests

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
# SUPABASE STORAGE
# =========================

def subir_archivo_supabase(supabase, archivo, empresa_id, bucket="documentos"):
    """
    Sube un archivo a Supabase Storage en una carpeta por empresa.
    Devuelve la URL pública del archivo o None si falla.
    
    Args:
        supabase: Cliente de Supabase
        archivo: Objeto file de Streamlit
        empresa_id: ID de la empresa
        bucket: Nombre del bucket (default: "documentos")
        
    Returns:
        str: URL pública del archivo o None si falla
    """
    try:
        nombre_original = archivo.name
        extension = nombre_original.split(".")[-1]
        nombre_unico = f"{uuid.uuid4()}.{extension}"
        ruta = f"empresa_{empresa_id}/{nombre_unico}"

        res = supabase.storage.from_(bucket).upload(ruta, archivo)
        if isinstance(res, dict) and res.get("error"):
            st.error("❌ Error al subir el archivo a Supabase Storage.")
            return None

        url = supabase.storage.from_(bucket).get_public_url(ruta)
        return url
    except Exception as e:
        st.error(f"❌ Error al subir archivo: {e}")
        return None

def eliminar_archivo_supabase(supabase, url, bucket="documentos"):
    """
    Elimina un archivo de Supabase Storage a partir de su URL pública.
    
    Args:
        supabase: Cliente de Supabase
        url: URL pública del archivo
        bucket: Nombre del bucket (default: "documentos")
        
    Returns:
        bool: True si se eliminó correctamente, False en caso contrario
    """
    try:
        base_url = supabase.storage.from_(bucket).get_public_url("")
        if not url.startswith(base_url):
            st.warning("⚠️ La URL no pertenece al bucket especificado.")
            return False

        ruta = url.replace(base_url, "")
        res = supabase.storage.from_(bucket).remove([ruta])
        if isinstance(res, dict) and res.get("error"):
            st.error("❌ Error al eliminar el archivo de Supabase Storage.")
            return False

        return True
    except Exception as e:
        st.error(f"❌ Error al procesar la eliminación del archivo: {e}")
        return False

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
        
def format_percentage(valor, decimales=1):
    """
    Formatea un valor decimal como porcentaje.
    
    Args:
        valor: Valor a formatear (puede ser decimal, string, etc.)
        decimales: Número de decimales a mostrar
        
    Returns:
        str: Valor formateado como porcentaje
    """
    try:
        if valor is None or valor == "":
            return "0%"
        
        # Convertir a float si no lo es
        if isinstance(valor, str):
            valor = float(valor.replace('%', '').replace(',', '.'))
        
        # Si el valor ya es mayor a 1, asumimos que ya está en porcentaje
        if valor > 1:
            return f"{valor:.{decimales}f}%"
        else:
            # Si es decimal (0.xx), convertir a porcentaje
            return f"{valor * 100:.{decimales}f}%"
    except (ValueError, TypeError):
        return "0%"

def format_date(fecha):
    """
    Formatea una fecha para mostrar en la interfaz.
    
    Args:
        fecha: Puede ser datetime, date, string, o None
    
    Returns:
        str: Fecha formateada como "DD/MM/YYYY" o vacío si error
    
    Examples:
        format_date(datetime.now()) -> "11/09/2025"
        format_date("2025-09-11") -> "11/09/2025"
        format_date(None) -> ""
    """
    if not fecha:
        return ""
    try:
        if isinstance(fecha, str):
            # Parsear string a datetime
            if 'T' in fecha:  # ISO format con tiempo
                fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
            else:
                fecha = pd.to_datetime(fecha)
        
        # Convertir a date si es datetime
        if hasattr(fecha, 'date'):
            fecha = fecha.date()
        
        return fecha.strftime("%d/%m/%Y")
    except Exception:
        return str(fecha) if fecha else ""

def safe_date_parse(fecha_str, formato=None):
    """
    Parsea una fecha de forma segura desde string.
    
    Args:
        fecha_str: String con la fecha
        formato: Formato específico (opcional)
    
    Returns:
        date: Objeto date o None si error
    
    Examples:
        safe_date_parse("11/09/2025") -> date(2025, 9, 11)
        safe_date_parse("2025-09-11") -> date(2025, 9, 11)
        safe_date_parse("fecha inválida") -> None
    """
    if not fecha_str:
        return None
    
    try:
        if formato:
            return datetime.strptime(fecha_str, formato).date()
        else:
            # Intentar varios formatos comunes
            formatos = [
                "%d/%m/%Y",      # 11/09/2025
                "%d-%m-%Y",      # 11-09-2025
                "%Y-%m-%d",      # 2025-09-11
                "%Y/%m/%d",      # 2025/09/11
                "%d/%m/%y",      # 11/09/25
                "%d-%m-%y"       # 11-09-25
            ]
            
            for fmt in formatos:
                try:
                    return datetime.strptime(fecha_str, fmt).date()
                except ValueError:
                    continue
            
            # Si no funciona ningún formato, usar pandas
            return pd.to_datetime(fecha_str).date()
            
    except Exception:
        return None

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
# GENERACIÓN DE XML FUNDAE
# =========================

def generar_pdf(buffer, lines):
    """
    Genera un PDF con las líneas proporcionadas.
    
    Args:
        buffer: BytesIO buffer para escribir el PDF
        lines: Lista de líneas de texto para incluir en el PDF
        
    Returns:
        BytesIO: Buffer con el PDF generado
    """
    try:
        # Crear el PDF usando reportlab
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Configurar el documento
        c.setTitle("Documento FUNDAE")
        
        # Añadir líneas de texto
        y_position = height - 2*cm
        for line in lines:
            if y_position < 2*cm:  # Nueva página si es necesario
                c.showPage()
                y_position = height - 2*cm
            
            c.drawString(2*cm, y_position, str(line))
            y_position -= 0.5*cm
        
        c.save()
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        st.error(f"❌ Error al generar PDF: {e}")
        return None

def generar_xml_accion_formativa(accion):
    """
    Genera XML de acción formativa según estándares FUNDAE.
    
    Args:
        accion: Diccionario con datos de la acción formativa
        
    Returns:
        str: XML generado o None si hay error
    """
    try:
        # Crear elemento raíz
        root = ET.Element("AccionFormativa")
        root.set("xmlns", "http://www.fundae.es/schemas/accionformativa")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        
        # Información básica
        info = ET.SubElement(root, "InformacionBasica")
        
        codigo = ET.SubElement(info, "CodigoAccion")
        codigo.text = str(accion.get('codigo_accion', ''))
        
        nombre = ET.SubElement(info, "NombreAccion")
        nombre.text = str(accion.get('nombre', ''))
        
        modalidad = ET.SubElement(info, "Modalidad")
        modalidad.text = str(accion.get('modalidad', 'Presencial'))
        
        horas = ET.SubElement(info, "NumeroHoras")
        horas.text = str(accion.get('num_horas', 0))
        
        # Área profesional
        if accion.get('area_profesional') or accion.get('cod_area_profesional'):
            area = ET.SubElement(info, "AreaProfesional")
            
            if accion.get('cod_area_profesional'):
                cod_area = ET.SubElement(area, "Codigo")
                cod_area.text = str(accion.get('cod_area_profesional'))
            
            if accion.get('area_profesional'):
                nom_area = ET.SubElement(area, "Nombre")
                nom_area.text = str(accion.get('area_profesional'))
        
        # Contenidos formativos
        contenidos = ET.SubElement(root, "ContenidosFormativos")
        
        if accion.get('objetivos'):
            objetivos = ET.SubElement(contenidos, "Objetivos")
            objetivos.text = str(accion.get('objetivos'))
        
        if accion.get('contenidos'):
            contenidos_text = ET.SubElement(contenidos, "Contenidos")
            contenidos_text.text = str(accion.get('contenidos'))
        
        # Información adicional
        if accion.get('nivel'):
            nivel = ET.SubElement(root, "Nivel")
            nivel.text = str(accion.get('nivel'))
        
        if accion.get('certificado_profesionalidad'):
            cert = ET.SubElement(root, "CertificadoProfesionalidad")
            cert.text = "true" if accion.get('certificado_profesionalidad') else "false"
        
        # Convertir a string XML
        xml_str = ET.tostring(root, encoding='unicode', method='xml')
        
        # Formatear con declaración XML
        formatted_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
        
        return formatted_xml
        
    except Exception as e:
        st.error(f"❌ Error al generar XML de acción formativa: {e}")
        return None

def generar_xml_inicio_grupo(grupo, participantes):
    """
    Genera XML de inicio de grupo según estándares FUNDAE.
    
    Args:
        grupo: Diccionario con datos del grupo
        participantes: Lista de participantes del grupo
        
    Returns:
        str: XML generado o None si hay error
    """
    try:
        # Crear elemento raíz
        root = ET.Element("InicioGrupo")
        root.set("xmlns", "http://www.fundae.es/schemas/iniciogrupo")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        
        # Información del grupo
        info_grupo = ET.SubElement(root, "InformacionGrupo")
        
        codigo = ET.SubElement(info_grupo, "CodigoGrupo")
        codigo.text = str(grupo.get('codigo_grupo', ''))
        
        fecha_inicio = ET.SubElement(info_grupo, "FechaInicio")
        fecha_inicio.text = str(grupo.get('fecha_inicio', ''))
        
        fecha_fin = ET.SubElement(info_grupo, "FechaFinPrevista")
        fecha_fin.text = str(grupo.get('fecha_fin_prevista', ''))
        
        if grupo.get('localidad'):
            localidad = ET.SubElement(info_grupo, "Localidad")
            localidad.text = str(grupo.get('localidad'))
        
        if grupo.get('provincia'):
            provincia = ET.SubElement(info_grupo, "Provincia")
            provincia.text = str(grupo.get('provincia'))
        
        # Modalidad
        if grupo.get('modalidad') or grupo.get('accion_modalidad'):
            modalidad = ET.SubElement(info_grupo, "Modalidad")
            modalidad.text = str(grupo.get('modalidad') or grupo.get('accion_modalidad', 'Presencial'))
        
        # Participantes
        if participantes:
            lista_participantes = ET.SubElement(root, "ListaParticipantes")
            
            for participante in participantes:
                part_elem = ET.SubElement(lista_participantes, "Participante")
                
                if participante.get('dni') or participante.get('nif'):
                    dni = ET.SubElement(part_elem, "DNI")
                    dni.text = str(participante.get('dni') or participante.get('nif', ''))
                
                if participante.get('nombre'):
                    nombre = ET.SubElement(part_elem, "Nombre")
def generar_xml_inicio_grupo(grupo, participantes):
    """
    Genera XML de inicio de grupo según estándares FUNDAE 2020+ (SIN namespace).
    
    Args:
        grupo: Diccionario con datos del grupo
        participantes: Lista de participantes del grupo
        
    Returns:
        str: XML generado o None si hay error
    """
    try:
        # Crear elemento raíz SIN namespace (cambio clave FUNDAE 2020+)
        root = ET.Element("InicioGrupo")
        
        # Información del grupo
        info_grupo = ET.SubElement(root, "InformacionGrupo")
        
        codigo = ET.SubElement(info_grupo, "CodigoGrupo")
        codigo.text = str(grupo.get('codigo_grupo', ''))
        
        fecha_inicio = ET.SubElement(info_grupo, "FechaInicio")
        fecha_inicio.text = str(grupo.get('fecha_inicio', ''))
        
        fecha_fin = ET.SubElement(info_grupo, "FechaFinPrevista")
        fecha_fin.text = str(grupo.get('fecha_fin_prevista', ''))
        
        if grupo.get('localidad'):
            localidad = ET.SubElement(info_grupo, "Localidad")
            localidad.text = str(grupo.get('localidad'))
        
        if grupo.get('provincia'):
            provincia = ET.SubElement(info_grupo, "Provincia")
            provincia.text = str(grupo.get('provincia'))
        
        # Modalidad
        modalidad = ET.SubElement(info_grupo, "Modalidad")
        modalidad_valor = grupo.get('modalidad') or grupo.get('accion_modalidad', 'PRESENCIAL')
        # Asegurar formato FUNDAE correcto
        if modalidad_valor.upper() in ['PRESENCIAL', 'TELEFORMACION', 'MIXTA']:
            modalidad.text = modalidad_valor.upper()
        else:
            modalidad.text = 'PRESENCIAL'
        
        # Número de participantes previstos
        n_participantes = ET.SubElement(info_grupo, "NumeroParticipantesPrevistos")
        n_participantes.text = str(grupo.get('n_participantes_previstos', len(participantes)))
        
        # Horario (si existe)
        if grupo.get('horario'):
            horario = ET.SubElement(info_grupo, "Horario")
            horario.text = str(grupo.get('horario'))
        
        # Participantes
        if participantes:
            lista_participantes = ET.SubElement(root, "ListaParticipantes")
            
            for participante in participantes:
                part_elem = ET.SubElement(lista_participantes, "Participante")
                
                # NIF/DNI (obligatorio)
                nif_value = participante.get('nif') or participante.get('dni', '')
                if nif_value:
                    nif = ET.SubElement(part_elem, "NIF")
                    nif.text = str(nif_value)
                
                # Nombre (obligatorio)
                if participante.get('nombre'):
                    nombre = ET.SubElement(part_elem, "Nombre")
                    nombre.text = str(participante.get('nombre'))
                
                # Apellidos (obligatorio)
                if participante.get('apellidos'):
                    apellidos = ET.SubElement(part_elem, "Apellidos")
                    apellidos.text = str(participante.get('apellidos'))
                
                # Email (obligatorio FUNDAE)
                if participante.get('email'):
                    email = ET.SubElement(part_elem, "Email")
                    email.text = str(participante.get('email'))
                
                # Teléfono (opcional)
                if participante.get('telefono'):
                    telefono = ET.SubElement(part_elem, "Telefono")
                    telefono.text = str(participante.get('telefono'))
        
        # Convertir a string XML
        xml_str = ET.tostring(root, encoding='unicode', method='xml')
        
        # Formatear con declaración XML
        formatted_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
        
        return formatted_xml
        
    except Exception as e:
        st.error(f"❌ Error al generar XML de inicio de grupo: {e}")
        return None


def generar_xml_finalizacion_grupo(grupo, participantes):
    """
    Genera XML de finalización de grupo según estándares FUNDAE 2020+ (SIN namespace).
    
    Args:
        grupo: Diccionario con datos del grupo
        participantes: Lista de participantes del grupo
        
    Returns:
        str: XML generado o None si hay error
    """
    try:
        # Crear elemento raíz SIN namespace
    
# =========================
# GENERACIÓN DE XML FUNDAE
# =========================

def generar_pdf(buffer, lines):
    """
    Genera un PDF con las líneas proporcionadas.
    
    Args:
        buffer: BytesIO buffer para escribir el PDF
        lines: Lista de líneas de texto para incluir en el PDF
        
    Returns:
        BytesIO: Buffer con el PDF generado
    """
    try:
        # Crear el PDF usando reportlab
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Configurar el documento
        c.setTitle("Documento FUNDAE")
        
        # Añadir líneas de texto
        y_position = height - 2*cm
        for line in lines:
            if y_position < 2*cm:  # Nueva página si es necesario
                c.showPage()
                y_position = height - 2*cm
            
            c.drawString(2*cm, y_position, str(line))
            y_position -= 0.5*cm
        
        c.save()
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        st.error(f"❌ Error al generar PDF: {e}")
        return None

def generar_xml_accion_formativa(accion):
    """
    Genera XML de acción formativa según estándares FUNDAE 2020+ (SIN namespace).
    
    Args:
        accion: Diccionario con datos de la acción formativa
        
    Returns:
        str: XML generado o None si hay error
    """
    try:
        # Crear elemento raíz SIN namespace
        root = ET.Element("AccionFormativa")
        
        # Información básica
        info = ET.SubElement(root, "InformacionBasica")
        
        codigo = ET.SubElement(info, "CodigoAccion")
        codigo.text = str(accion.get('codigo_accion', ''))
        
        nombre = ET.SubElement(info, "NombreAccion")
        nombre.text = str(accion.get('nombre', ''))
        
        modalidad = ET.SubElement(info, "Modalidad")
        modalidad_valor = accion.get('modalidad', 'PRESENCIAL')
        # Asegurar formato FUNDAE correcto
        if modalidad_valor.upper() in ['PRESENCIAL', 'TELEFORMACION', 'MIXTA']:
            modalidad.text = modalidad_valor.upper()
        else:
            modalidad.text = 'PRESENCIAL'
        
        horas = ET.SubElement(info, "NumeroHoras")
        horas.text = str(accion.get('num_horas', 0))
        
        # Área profesional
        if accion.get('area_profesional') or accion.get('cod_area_profesional'):
            area = ET.SubElement(info, "AreaProfesional")
            
            if accion.get('cod_area_profesional'):
                cod_area = ET.SubElement(area, "Codigo")
                cod_area.text = str(accion.get('cod_area_profesional'))
            
            if accion.get('area_profesional'):
                nom_area = ET.SubElement(area, "Nombre")
                nom_area.text = str(accion.get('area_profesional'))
        
        # Contenidos formativos
        contenidos = ET.SubElement(root, "ContenidosFormativos")
        
        if accion.get('objetivos'):
            objetivos = ET.SubElement(contenidos, "Objetivos")
            objetivos.text = str(accion.get('objetivos'))
        
        if accion.get('contenidos'):
            contenidos_text = ET.SubElement(contenidos, "Contenidos")
            contenidos_text.text = str(accion.get('contenidos'))
        
        # Información adicional
        if accion.get('nivel'):
            nivel = ET.SubElement(root, "Nivel")
            nivel.text = str(accion.get('nivel'))
        
        if accion.get('certificado_profesionalidad'):
            cert = ET.SubElement(root, "CertificadoProfesionalidad")
            cert.text = "true" if accion.get('certificado_profesionalidad') else "false"
        
        # Convertir a string XML
        xml_str = ET.tostring(root, encoding='unicode', method='xml')
        
        # Formatear con declaración XML
        formatted_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
        
        return formatted_xml
        
    except Exception as e:
        st.error(f"❌ Error al generar XML de acción formativa: {e}")
        return None

def generar_xml_inicio_grupo(grupo, participantes):
    """
    Genera XML de inicio de grupo según estándares FUNDAE 2020+ (SIN namespace).
    
    Args:
        grupo: Diccionario con datos del grupo
        participantes: Lista de participantes del grupo
        
    Returns:
        str: XML generado o None si hay error
    """
    try:
        # Crear elemento raíz SIN namespace (cambio clave FUNDAE 2020+)
        root = ET.Element("InicioGrupo")
        
        # Información del grupo
        info_grupo = ET.SubElement(root, "InformacionGrupo")
        
        codigo = ET.SubElement(info_grupo, "CodigoGrupo")
        codigo.text = str(grupo.get('codigo_grupo', ''))
        
        fecha_inicio = ET.SubElement(info_grupo, "FechaInicio")
        fecha_inicio.text = str(grupo.get('fecha_inicio', ''))
        
        fecha_fin = ET.SubElement(info_grupo, "FechaFinPrevista")
        fecha_fin.text = str(grupo.get('fecha_fin_prevista', ''))
        
        if grupo.get('localidad'):
            localidad = ET.SubElement(info_grupo, "Localidad")
            localidad.text = str(grupo.get('localidad'))
        
        if grupo.get('provincia'):
            provincia = ET.SubElement(info_grupo, "Provincia")
            provincia.text = str(grupo.get('provincia'))
        
        # Modalidad
        modalidad = ET.SubElement(info_grupo, "Modalidad")
        modalidad_valor = grupo.get('modalidad') or grupo.get('accion_modalidad', 'PRESENCIAL')
        # Asegurar formato FUNDAE correcto
        if modalidad_valor.upper() in ['PRESENCIAL', 'TELEFORMACION', 'MIXTA']:
            modalidad.text = modalidad_valor.upper()
        else:
            modalidad.text = 'PRESENCIAL'
        
        # Número de participantes previstos
        n_participantes = ET.SubElement(info_grupo, "NumeroParticipantesPrevistos")
        n_participantes.text = str(grupo.get('n_participantes_previstos', len(participantes)))
        
        # Horario (si existe)
        if grupo.get('horario'):
            horario = ET.SubElement(info_grupo, "Horario")
            horario.text = str(grupo.get('horario'))
        
        # Participantes
        if participantes:
            lista_participantes = ET.SubElement(root, "ListaParticipantes")
            
            for participante in participantes:
                part_elem = ET.SubElement(lista_participantes, "Participante")
                
                # NIF/DNI (obligatorio)
                nif_value = participante.get('nif') or participante.get('dni', '')
                if nif_value:
                    nif = ET.SubElement(part_elem, "NIF")
                    nif.text = str(nif_value)
                
                # Nombre (obligatorio)
                if participante.get('nombre'):
                    nombre = ET.SubElement(part_elem, "Nombre")
                    nombre.text = str(participante.get('nombre'))
                
                # Apellidos (obligatorio)
                if participante.get('apellidos'):
                    apellidos = ET.SubElement(part_elem, "Apellidos")
                    apellidos.text = str(participante.get('apellidos'))
                
                # Email (obligatorio FUNDAE)
                if participante.get('email'):
                    email = ET.SubElement(part_elem, "Email")
                    email.text = str(participante.get('email'))
                
                # Teléfono (opcional)
                if participante.get('telefono'):
                    telefono = ET.SubElement(part_elem, "Telefono")
                    telefono.text = str(participante.get('telefono'))
        
        # Convertir a string XML
        xml_str = ET.tostring(root, encoding='unicode', method='xml')
        
        # Formatear con declaración XML
        formatted_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
        
        return formatted_xml
        
    except Exception as e:
        st.error(f"❌ Error al generar XML de inicio de grupo: {e}")
        return None

def generar_xml_finalizacion_grupo(grupo, participantes):
    """
    Genera XML de finalización de grupo según estándares FUNDAE 2020+ (SIN namespace).
    
    Args:
        grupo: Diccionario con datos del grupo
        participantes: Lista de participantes del grupo
        
    Returns:
        str: XML generado o None si hay error
    """
    try:
        # Crear elemento raíz SIN namespace
        root = ET.Element("FinalizacionGrupo")
        
        # Información del grupo
        info_grupo = ET.SubElement(root, "InformacionGrupo")
        
        codigo = ET.SubElement(info_grupo, "CodigoGrupo")
        codigo.text = str(grupo.get('codigo_grupo', ''))
        
        fecha_inicio = ET.SubElement(info_grupo, "FechaInicio")
        fecha_inicio.text = str(grupo.get('fecha_inicio', ''))
        
        fecha_fin = ET.SubElement(info_grupo, "FechaFinReal")
        fecha_fin.text = str(grupo.get('fecha_fin') or grupo.get('fecha_fin_prevista', ''))
        
        # Resultados del grupo
        resultados = ET.SubElement(root, "Resultados")
        
        n_previstos = ET.SubElement(resultados, "ParticipantesPrevistos")
        n_previstos.text = str(grupo.get('n_participantes_previstos', len(participantes)))
        
        n_finalizados = ET.SubElement(resultados, "ParticipantesFinalizados")
        n_finalizados.text = str(grupo.get('n_participantes_finalizados', len(participantes)))
        
        n_aptos = ET.SubElement(resultados, "ParticipantesAptos")
        n_aptos.text = str(grupo.get('n_aptos', 0))
        
        n_no_aptos = ET.SubElement(resultados, "ParticipantesNoAptos")
        n_no_aptos.text = str(grupo.get('n_no_aptos', 0))
        
        # Participantes finalizados
        if participantes:
            lista_participantes = ET.SubElement(root, "ParticipantesFinalizados")
            
            for participante in participantes:
                part_elem = ET.SubElement(lista_participantes, "Participante")
                
                # NIF/DNI (obligatorio)
                nif_value = participante.get('nif') or participante.get('dni', '')
                if nif_value:
                    nif = ET.SubElement(part_elem, "NIF")
                    nif.text = str(nif_value)
                
                # Nombre (obligatorio)
                if participante.get('nombre'):
                    nombre = ET.SubElement(part_elem, "Nombre")
                    nombre.text = str(participante.get('nombre'))
                
                # Apellidos (obligatorio)
                if participante.get('apellidos'):
                    apellidos = ET.SubElement(part_elem, "Apellidos")
                    apellidos.text = str(participante.get('apellidos'))
                
                # Resultado del participante (APTO/NO_APTO)
                resultado = ET.SubElement(part_elem, "Resultado")
                resultado.text = participante.get('resultado', 'APTO')  # Por defecto APTO
                
                # Calificación si existe
                if participante.get('calificacion'):
                    calificacion = ET.SubElement(part_elem, "Calificacion")
                    calificacion.text = str(participante.get('calificacion'))
                
                # Categoría profesional (campo FUNDAE 2024)
                if participante.get('categoria_profesional'):
                    categoria = ET.SubElement(part_elem, "CategoriaProfesional")
                    categoria.text = str(participante.get('categoria_profesional'))
                
                # Grupo de cotización (campo FUNDAE 2024)
                if participante.get('grupo_cotizacion'):
                    cotizacion = ET.SubElement(part_elem, "GrupoCotizacion")
                    cotizacion.text = str(participante.get('grupo_cotizacion'))
        
        # Observaciones
        if grupo.get('observaciones'):
            observaciones = ET.SubElement(root, "Observaciones")
            observaciones.text = str(grupo.get('observaciones'))
        
        # Convertir a string XML
        xml_str = ET.tostring(root, encoding='unicode', method='xml')
        
        # Formatear con declaración XML
        formatted_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
        
        return formatted_xml
        
    except Exception as e:
        st.error(f"❌ Error al generar XML de finalización de grupo: {e}")
        return None

def validar_xml(xml_content, xsd_url):
    """
    Valida un XML contra un esquema XSD remoto.
    
    Args:
        xml_content: Contenido XML a validar
        xsd_url: URL del esquema XSD
        
    Returns:
        tuple: (es_valido: bool, errores: list)
    """
    try:
        # Descargar el esquema XSD
        response = requests.get(xsd_url, timeout=10)
        if response.status_code != 200:
            return False, [f"No se pudo descargar el esquema XSD desde {xsd_url}"]
        
        # Parsear el esquema XSD
        xsd_doc = etree.fromstring(response.content)
        xsd_schema = etree.XMLSchema(xsd_doc)
        
        # Parsear el XML a validar
        xml_doc = etree.fromstring(xml_content.encode('utf-8'))
        
        # Validar
        if xsd_schema.validate(xml_doc):
            return True, []
        else:
            errores = [str(error) for error in xsd_schema.error_log]
            return False, errores
            
    except requests.RequestException as e:
        return False, [f"Error al acceder al esquema XSD: {e}"]
    except etree.XMLSyntaxError as e:
        return False, [f"Error de sintaxis XML: {e}"]
    except Exception as e:
        return False, [f"Error de validación: {e}"]
        
# =========================
# AJUSTES GLOBALES DE LA APP
# =========================

def get_ajustes_app(supabase, campos=None):
    """
    Obtiene ajustes globales de la aplicación.
    
    Args:
        supabase: Cliente de Supabase
        campos: Lista de campos específicos a obtener (opcional)
        
    Returns:
        dict: Diccionario con los ajustes
    """
    try:
        query = supabase.table("ajustes_app")
        query = query.select(",".join(campos)) if campos else query.select("*")
        res = query.eq("id", 1).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        st.error(f"❌ Error al cargar ajustes de la app: {e}")
        return {}

def update_ajustes_app(supabase, data_dict):
    """
    Actualiza los ajustes globales en la tabla ajustes_app.
    
    Args:
        supabase: Cliente de Supabase
        data_dict: Diccionario con los datos a actualizar
        
    Returns:
        None
    """
    try:
        data_dict["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("ajustes_app").update(data_dict).eq("id", 1).execute()
    except Exception as e:
        st.error(f"❌ Error al guardar ajustes de la app: {e}")
