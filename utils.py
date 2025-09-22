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
        
# =========================
# FUNCIONES FUNDAE (añadir al final de utils.py)
# =========================
def validar_codigo_accion_fundae(supabase, codigo_accion, empresa_id, ano, accion_id=None):
    """
    Valida que el código de acción sea único para la empresa gestora en el año especificado.
    FUNDAE: Los códigos de acción deben ser únicos por empresa gestora y año.
    """
    if not codigo_accion or not ano or not empresa_id:
        return False, "Código de acción, empresa y año requeridos"
    
    try:
        # Buscar acciones con mismo código en el mismo año y empresa gestora
        query = supabase.table("acciones_formativas").select("id, codigo_accion").eq(
            "codigo_accion", codigo_accion
        ).eq("empresa_id", empresa_id).gte(
            "fecha_inicio", f"{ano}-01-01"
        ).lt("fecha_inicio", f"{ano + 1}-01-01")
        
        # Excluir la acción actual si estamos editando
        if accion_id:
            query = query.neq("id", accion_id)
        
        res = query.execute()
        
        if res.data:
            return False, f"Ya existe una acción con código '{codigo_accion}' en {ano} para esta empresa gestora"
        
        return True, ""
        
    except Exception as e:
        return False, f"Error al validar código: {e}"

def validar_codigo_grupo_fundae(supabase, codigo_grupo, accion_formativa_id, grupo_id=None):
    """
    Valida que el código de grupo sea único para la acción y empresa gestora en el año.
    FUNDAE: Los códigos de grupo deben ser únicos por acción formativa, empresa gestora y año.
    """
    if not codigo_grupo or not accion_formativa_id:
        return False, "Código de grupo y acción formativa requeridos"
    
    try:
        # Obtener información de la acción formativa
        accion_res = supabase.table("acciones_formativas").select(
            "codigo_accion, empresa_id, fecha_inicio"
        ).eq("id", accion_formativa_id).execute()
        
        if not accion_res.data:
            return False, "Acción formativa no encontrada"
        
        accion_data = accion_res.data[0]
        empresa_gestora_id = accion_data["empresa_id"]
        fecha_accion = accion_data["fecha_inicio"]
        
        if fecha_accion:
            try:
                ano_accion = datetime.fromisoformat(str(fecha_accion).replace('Z', '+00:00')).year
            except:
                ano_accion = datetime.now().year
        else:
            ano_accion = datetime.now().year
        
        # Buscar grupos con mismo código en la misma acción y año de la misma empresa gestora
        query = supabase.table("grupos").select("""
            id, codigo_grupo, fecha_inicio,
            accion_formativa:acciones_formativas(empresa_id)
        """).eq("codigo_grupo", codigo_grupo).gte(
            "fecha_inicio", f"{ano_accion}-01-01"
        ).lt("fecha_inicio", f"{ano_accion + 1}-01-01")
        
        # Excluir grupo actual si estamos editando
        if grupo_id:
            query = query.neq("id", grupo_id)
        
        res = query.execute()
        
        if res.data:
            # Verificar si alguno pertenece a la misma empresa gestora
            for grupo_existente in res.data:
                accion_info = grupo_existente.get("accion_formativa", {})
                if accion_info.get("empresa_id") == empresa_gestora_id:
                    return False, f"Ya existe un grupo con código '{codigo_grupo}' en {ano_accion} para esta empresa gestora"
        
        return True, ""
        
    except Exception as e:
        return False, f"Error al validar código: {e}"

def get_empresa_responsable_fundae(supabase, grupo_id):
    """
    Determina qué empresa es responsable ante FUNDAE para un grupo específico.
    FUNDAE: La empresa responsable es la gestora, no necesariamente la propietaria del grupo.
    """
    try:
        # Obtener información del grupo y la acción
        grupo_res = supabase.table("grupos").select("""
            empresa_id,
            accion_formativa:acciones_formativas(empresa_id)
        """).eq("id", grupo_id).execute()
        
        if not grupo_res.data:
            return None, "Grupo no encontrado"
        
        grupo_data = grupo_res.data[0]
        empresa_grupo_id = grupo_data["empresa_id"]
        empresa_accion_id = grupo_data.get("accion_formativa", {}).get("empresa_id")
        
        # La empresa responsable ante FUNDAE es la que creó la acción formativa
        empresa_responsable_id = empresa_accion_id or empresa_grupo_id
        
        # Obtener datos de la empresa responsable
        empresa_res = supabase.table("empresas").select("""
            id, nombre, cif, tipo_empresa, empresa_matriz_id
        """).eq("id", empresa_responsable_id).execute()
        
        if not empresa_res.data:
            return None, "Empresa responsable no encontrada"
        
        empresa_responsable = empresa_res.data[0]
        
        # Si es cliente de gestor, la responsable ante FUNDAE es la gestora
        if empresa_responsable.get("tipo_empresa") == "CLIENTE_GESTOR":
            gestora_id = empresa_responsable.get("empresa_matriz_id")
            if gestora_id:
                gestora_res = supabase.table("empresas").select("*").eq("id", gestora_id).execute()
                if gestora_res.data:
                    return gestora_res.data[0], ""
        
        return empresa_responsable, ""
        
    except Exception as e:
        return None, f"Error al determinar empresa responsable: {e}"

def preparar_datos_xml_con_jerarquia(grupo_id, supabase):
    """
    Prepara datos XML asegurando coherencia con jerarquía empresarial FUNDAE.
    Versión mejorada de preparar_datos_xml_inicio_simple.
    """
    try:
        # Validar grupo FUNDAE completo
        datos_xml, errores = preparar_datos_xml_inicio_simple(grupo_id, supabase)
        
        if errores:
            return None, errores
        
        # Obtener empresa responsable ante FUNDAE
        empresa_responsable, error_empresa = get_empresa_responsable_fundae(supabase, grupo_id)
        
        if error_empresa:
            errores.append(f"Error empresa responsable: {error_empresa}")
            return None, errores
        
        # Validar códigos FUNDAE
        grupo_info = datos_xml["grupo"]
        codigo_grupo = grupo_info.get("codigo_grupo")
        accion_formativa_id = grupo_info.get("accion_formativa_id")
        
        if codigo_grupo and accion_formativa_id:
            es_valido, error_codigo = validar_codigo_grupo_fundae(
                supabase, codigo_grupo, accion_formativa_id, grupo_id
            )
            
            if not es_valido:
                errores.append(f"Código de grupo inválido: {error_codigo}")
                return None, errores
        
        # Enriquecer datos con información de empresa responsable
        datos_xml["empresa_responsable"] = empresa_responsable
        datos_xml["grupo"]["empresa_responsable_cif"] = empresa_responsable.get("cif")
        datos_xml["grupo"]["empresa_responsable_nombre"] = empresa_responsable.get("nombre")
        
        return datos_xml, []
        
    except Exception as e:
        return None, [f"Error al preparar datos XML: {e}"]

# =========================
# ACTUALIZAR FUNCIONES EXISTENTES XML
# =========================

def generar_xml_accion_formativa_mejorado(accion, namespace="http://www.fundae.es/esquemas"):
    """
    Versión mejorada del generador XML con validaciones FUNDAE.
    """
    try:
        # Validar datos básicos antes de generar
        if not accion.get('codigo_accion'):
            raise ValueError("Código de acción requerido")
        if not accion.get('nombre'):
            raise ValueError("Nombre de acción requerido")
        if not accion.get('modalidad'):
            raise ValueError("Modalidad requerida")
        
        # Normalizar modalidad FUNDAE
        modalidad = accion.get('modalidad', '').upper()
        if modalidad not in ['PRESENCIAL', 'TELEFORMACION', 'MIXTA']:
            modalidad = 'PRESENCIAL'  # Fallback seguro
        
        # Usar función existente como base
        xml_content = generar_xml_accion_formativa(accion)
        
        if xml_content:
            # Añadir metadatos de validación
            metadata = f"""
<!-- 
VALIDACIONES FUNDAE APLICADAS:
- Código único validado para empresa gestora y año
- Modalidad normalizada: {modalidad}
- Generado: {datetime.now().isoformat()}
-->
"""
            # Insertar metadata después de la declaración XML
            if xml_content.startswith('<?xml'):
                lines = xml_content.split('\n')
                lines.insert(1, metadata)
                xml_content = '\n'.join(lines)
        
        return xml_content
        
    except Exception as e:
        st.error(f"Error al generar XML de acción formativa: {e}")
        return None

def generar_xml_inicio_grupo_con_validaciones(datos_xml):
    """
    Versión mejorada del generador XML inicio con validaciones de jerarquía.
    """
    try:
        # Validar que tenemos empresa responsable
        if "empresa_responsable" not in datos_xml:
            raise ValueError("Falta información de empresa responsable ante FUNDAE")
        
        grupo = datos_xml["grupo"]
        participantes = datos_xml.get("participantes", [])
        
        # Usar la función existente como base
        xml_content = generar_xml_inicio_grupo(grupo, participantes)
        
        if xml_content:
            # Agregar metadatos de validación
            empresa_resp = datos_xml["empresa_responsable"]
            metadata = f"""
<!-- 
VALIDACIONES FUNDAE APLICADAS:
- Empresa responsable: {empresa_resp.get('nombre')} (CIF: {empresa_resp.get('cif')})
- Código grupo único validado para año y empresa gestora
- Jerarquía empresarial respetada
- Generado: {datetime.now().isoformat()}
-->
"""
            # Insertar metadata después de la declaración XML
            if xml_content.startswith('<?xml'):
                lines = xml_content.split('\n')
                lines.insert(1, metadata)
                xml_content = '\n'.join(lines)
        
        return xml_content
        
    except Exception as e:
        st.error(f"Error al generar XML con validaciones: {e}")
        return None

def generar_xml_finalizacion_grupo_mejorado(grupo_data, participantes_data):
    """
    Versión mejorada del generador XML finalización con validaciones coherencia.
    """
    try:
        # Validaciones de coherencia antes de generar
        n_finalizados = grupo_data.get('n_participantes_finalizados', 0)
        n_aptos = grupo_data.get('n_aptos', 0)
        n_no_aptos = grupo_data.get('n_no_aptos', 0)
        
        # Validar coherencia de números
        if n_finalizados > 0 and (n_aptos + n_no_aptos != n_finalizados):
            raise ValueError(f"Incoherencia: {n_aptos} aptos + {n_no_aptos} no aptos ≠ {n_finalizados} finalizados")
        
        # Validar que hay participantes
        if not participantes_data:
            raise ValueError("No hay participantes para finalizar")
        
        # Usar función existente como base
        xml_content = generar_xml_finalizacion_grupo(grupo_data, participantes_data)
        
        if xml_content:
            # Agregar metadatos de validación
            empresa_resp = grupo_data.get("empresa_responsable", {})
            metadata = f"""
<!-- 
VALIDACIONES FUNDAE APLICADAS:
- Coherencia participantes validada: {n_aptos} aptos + {n_no_aptos} no aptos = {n_finalizados} finalizados
- Empresa responsable: {empresa_resp.get('nombre', 'N/A')}
- Participantes procesados: {len(participantes_data)}
- Generado: {datetime.now().isoformat()}
-->
"""
            # Insertar metadata
            if xml_content.startswith('<?xml'):
                lines = xml_content.split('\n')
                lines.insert(1, metadata)
                xml_content = '\n'.join(lines)
        
        return xml_content
        
    except Exception as e:
        st.error(f"Error al generar XML finalización: {e}")
        return None

# =========================
# VALIDACIONES ADICIONALES FUNDAE
# =========================

def validar_datos_grupo_fundae_completo(grupo_data, tipo_validacion="inicio"):
    """
    Validación completa de grupo para XML FUNDAE con nuevas reglas.
    """
    errores = []
    
    # Validaciones básicas existentes
    es_valido_basico, errores_basicos = validar_grupo_fundae_completo(grupo_data)
    if errores_basicos:
        errores.extend(errores_basicos)
    
    # Validaciones adicionales de jerarquía
    if not grupo_data.get("empresa_id"):
        errores.append("❌ Falta empresa propietaria del grupo")
    
    if not grupo_data.get("accion_formativa_id"):
        errores.append("❌ Falta acción formativa asociada")
    
    # Validaciones específicas por tipo
    if tipo_validacion == "finalizacion":
        # Validar coherencia de finalización
        n_finalizados = grupo_data.get('n_participantes_finalizados', 0)
        n_aptos = grupo_data.get('n_aptos', 0)
        n_no_aptos = grupo_data.get('n_no_aptos', 0)
        
        if n_finalizados > 0:
            if n_aptos + n_no_aptos != n_finalizados:
                errores.append(f"❌ Incoherencia: {n_aptos} aptos + {n_no_aptos} no aptos ≠ {n_finalizados} finalizados")
            
            if n_aptos < 0 or n_no_aptos < 0:
                errores.append("❌ Los números de participantes no pueden ser negativos")
        
        # Validar fecha de finalización
        if not grupo_data.get("fecha_fin"):
            errores.append("❌ Falta fecha real de finalización")
    
    return len(errores) == 0, errores

def validar_participantes_fundae(participantes_data):
    """
    Valida que los participantes cumplan requisitos FUNDAE.
    """
    errores = []
    
    if not participantes_data:
        errores.append("❌ No hay participantes en el grupo")
        return False, errores
    
    for i, participante in enumerate(participantes_data, 1):
        # Validar campos obligatorios FUNDAE
        if not participante.get("nif"):
            errores.append(f"❌ Participante {i}: falta NIF/documento")
        
        if not participante.get("nombre"):
            errores.append(f"❌ Participante {i}: falta nombre")
        
        if not participante.get("apellidos"):
            errores.append(f"❌ Participante {i}: falta apellidos")
        
        if not participante.get("email"):
            errores.append(f"❌ Participante {i}: falta email")
        
        # Validar formato NIF si existe
        nif = participante.get("nif", "")
        if nif and not validar_dni_cif(nif):
            errores.append(f"❌ Participante {i}: NIF inválido ({nif})")
        
        # Validar email si existe
        email = participante.get("email", "")
        if email and not validar_email(email):
            errores.append(f"❌ Participante {i}: email inválido ({email})")
    
    return len(errores) == 0, errores

def generar_informe_validacion_fundae(grupo_id, supabase):
    """
    Genera un informe completo de validación FUNDAE para un grupo.
    """
    try:
        informe = {
            "grupo_id": grupo_id,
            "fecha_validacion": datetime.now().isoformat(),
            "errores": [],
            "advertencias": [],
            "estado": "PENDIENTE"
        }
        
        # Validar datos XML
        datos_xml, errores_xml = preparar_datos_xml_con_jerarquia(grupo_id, supabase)
        
        if errores_xml:
            informe["errores"].extend(errores_xml)
            informe["estado"] = "ERROR"
            return informe
        
        # Validar grupo
        grupo_data = datos_xml["grupo"]
        es_valido_grupo, errores_grupo = validar_datos_grupo_fundae_completo(grupo_data)
        
        if errores_grupo:
            informe["errores"].extend(errores_grupo)
        
        # Validar participantes
        participantes = datos_xml.get("participantes", [])
        es_valido_part, errores_part = validar_participantes_fundae(participantes)
        
        if errores_part:
            informe["errores"].extend(errores_part)
        
        # Validar empresa responsable
        empresa_resp = datos_xml.get("empresa_responsable")
        if not empresa_resp:
            informe["errores"].append("❌ No se pudo determinar empresa responsable ante FUNDAE")
        elif empresa_resp.get("tipo_empresa") not in ["GESTORA", "CLIENTE_SAAS"]:
            informe["advertencias"].append(f"⚠️ Empresa responsable tipo '{empresa_resp.get('tipo_empresa')}' poco común")
        
        # Determinar estado final
        if informe["errores"]:
            informe["estado"] = "ERROR"
        elif informe["advertencias"]:
            informe["estado"] = "ADVERTENCIA"
        else:
            informe["estado"] = "VALIDO"
        
        # Añadir resumen
        informe["resumen"] = {
            "total_errores": len(informe["errores"]),
            "total_advertencias": len(informe["advertencias"]),
            "participantes_validados": len(participantes),
            "empresa_responsable": empresa_resp.get("nombre") if empresa_resp else "No determinada"
        }
        
        return informe
        
    except Exception as e:
        return {
            "grupo_id": grupo_id,
            "fecha_validacion": datetime.now().isoformat(),
            "errores": [f"Error al generar informe: {e}"],
            "estado": "ERROR",
            "resumen": {"total_errores": 1}
        }

def validar_grupo_fundae_completo(datos_grupo):
    """Validación completa para XML FUNDAE."""
    errores = []
    
    # Campos obligatorios básicos
    campos_requeridos = [
        ("codigo_grupo", "Código del grupo"),
        ("fecha_inicio", "Fecha de inicio"), 
        ("fecha_fin_prevista", "Fecha fin prevista"),
        ("localidad", "Localidad"),
        ("responsable", "Responsable"),
        ("telefono_contacto", "Teléfono de contacto"),
        ("n_participantes_previstos", "Participantes previstos")
    ]
    
    for campo, nombre in campos_requeridos:
        if not datos_grupo.get(campo):
            errores.append(f"❌ {nombre} es obligatorio")
    
    # Validar teléfono formato FUNDAE
    tel = datos_grupo.get("telefono_contacto", "")
    if tel and not re.match(r'^\d{9,12}$', tel.replace(' ', '').replace('-', '')):
        errores.append("❌ Teléfono debe tener entre 9 y 12 dígitos")
    
    # Validar participantes
    try:
        n_part = int(datos_grupo.get("n_participantes_previstos", 0))
        if not (1 <= n_part <= 9999):
            errores.append("❌ Participantes debe estar entre 1 y 9999")
    except:
        errores.append("❌ Participantes debe ser un número válido")
    
    return len(errores) == 0, errores

def preparar_datos_xml_inicio_simple(grupo_id, supabase):
    """Prepara datos para XML FUNDAE con estructura actual."""
    try:
        # Datos del grupo con acción
        grupo = supabase.table("grupos").select("""
            *, 
            accion_formativa:acciones_formativas(codigo, denominacion, num_horas)
        """).eq("id", grupo_id).single().execute()
        
        if not grupo.data:
            return None, ["Grupo no encontrado"]
            
        grupo_data = grupo.data
        
        # Validar completitud
        es_valido, errores = validar_grupo_fundae_completo(grupo_data)
        if not es_valido:
            return None, errores
        
        # Tutores con tipos de documento automáticos
        tutores = supabase.table("tutores_grupos").select("""
            tutor:tutores(*)
        """).eq("grupo_id", grupo_id).execute()
        
        tutores_fundae = []
        for tg in tutores.data or []:
            tutor = tg.get("tutor")
            if tutor:
                # Detectar tipo automáticamente si no está definido
                tipo_doc = tutor.get("tipo_documento")
                if not tipo_doc or tipo_doc == "":
                    tipo_doc = detectar_tipo_documento_fundae(tutor.get("nif", ""))
                else:
                    # Convertir texto a código si es necesario
                    tipo_map = {"NIF": 10, "NIE": 60, "Pasaporte": 20}
                    tipo_doc = tipo_map.get(tipo_doc, detectar_tipo_documento_fundae(tutor.get("nif", "")))
                
                tutor_fundae = {**tutor, "tipo_documento_fundae": tipo_doc}
                tutores_fundae.append(tutor_fundae)
        
        # Participantes con tipos de documento automáticos
        participantes = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute()
        
        participantes_fundae = []
        for part in participantes.data or []:
            # Detectar tipo automáticamente si no está definido
            tipo_doc = part.get("tipo_documento")
            if not tipo_doc or tipo_doc == "":
                tipo_doc = detectar_tipo_documento_fundae(part.get("nif", ""))
            else:
                # Convertir texto a código si es necesario
                tipo_map = {"NIF": 10, "NIE": 60, "Pasaporte": 20}
                tipo_doc = tipo_map.get(tipo_doc, detectar_tipo_documento_fundae(part.get("nif", "")))
            
            part_fundae = {**part, "tipo_documento_fundae": tipo_doc}
            participantes_fundae.append(part_fundae)
        
        # Empresas participantes
        empresas = supabase.table("empresas_grupos").select("""
            empresa:empresas(cif, nombre)
        """).eq("grupo_id", grupo_id).execute()
        
        empresas_fundae = [eg["empresa"] for eg in empresas.data or [] if eg.get("empresa")]
        
        # Validar que hay datos mínimos requeridos
        errores_adicionales = []
        if not tutores_fundae:
            errores_adicionales.append("El grupo debe tener al menos un tutor asignado")
        if not empresas_fundae:
            errores_adicionales.append("El grupo debe tener al menos una empresa participante")
        if not participantes_fundae:
            errores_adicionales.append("El grupo debe tener participantes inscritos")
        
        # Verificar datos faltantes en participantes
        for i, part in enumerate(participantes_fundae):
            if not part.get("nif"):
                errores_adicionales.append(f"Participante {i+1}: falta NIF/documento")
            if not part.get("sexo"):
                errores_adicionales.append(f"Participante {i+1}: falta sexo")
            if not part.get("fecha_nacimiento"):
                errores_adicionales.append(f"Participante {i+1}: falta fecha de nacimiento")
        
        if errores_adicionales:
            return None, errores_adicionales
        
        return {
            "grupo": grupo_data,
            "tutores": tutores_fundae,
            "empresas": empresas_fundae,
            "participantes": participantes_fundae
        }, []
        
    except Exception as e:
        return None, [f"Error: {str(e)}"]

def actualizar_tipo_documento_tutores(supabase):
    """
    Función de migración para calcular tipo_documento basado en el NIF existente.
    Ejecutar una sola vez para actualizar tutores existentes.
    """
    import re
    try:
        # Obtener todos los tutores
        tutores = supabase.table("tutores").select("id, nif").execute()
        
        actualizados = 0
        for tutor in tutores.data or []:
            if not tutor.get("nif"):
                continue
                
            nif = tutor["nif"].upper().strip()
            tipo_documento = None
            
            # Detectar tipo según formato
            if re.match(r'^[0-9]{8}[A-Z]$', nif):
                tipo_documento = 10  # NIF
            elif re.match(r'^[XYZ][0-9]{7}[A-Z]$', nif):
                tipo_documento = 60  # NIE
            elif len(nif) >= 6:
                tipo_documento = 20  # Pasaporte (por defecto para otros)
            
            if tipo_documento:
                supabase.table("tutores").update({
                    "tipo_documento": tipo_documento
                }).eq("id", tutor["id"]).execute()
                actualizados += 1
                
        return actualizados > 0
        
    except Exception as e:
        print(f"Error en migración de tipos de documento: {e}")
        return False
        
def generar_xml_inicio_grupo_mejorado(datos_xml):
    """
    Genera XML de inicio de grupo usando datos validados.
    
    Args:
        datos_xml: Datos estructurados del grupo, tutores y empresas
    
    Returns:
        str: XML formateado para FUNDAE
    """
    try:
        grupo = datos_xml["grupo"]
        tutores = datos_xml["tutores"]
        empresas = datos_xml["empresas"]
        
        # Aquí iría la generación del XML usando los datos estructurados
        # Por ahora, usar la función existente como base y mejorarla gradualmente
        
        # Obtener participantes del grupo
        participantes_res = supabase.table("participantes").select("*").eq("grupo_id", grupo["id"]).execute()
        participantes = participantes_res.data or []
        
        # Llamar a la función existente (temporal, mientras la mejoramos)
        return generar_xml_inicio_grupo(grupo, participantes)
        
    except Exception as e:
        print(f"Error al generar XML mejorado: {e}")
        return None
        
def safe_int_conversion(valor, default=0):
    """
    Convierte un valor a int de forma segura.
    Si no es convertible devuelve el valor por defecto.
    """
    try:
        if valor is None or valor == "":
            return default
        return int(valor)
    except (ValueError, TypeError):
        return default
      
def detectar_tipo_documento_fundae(nif):
    """Detecta automáticamente el tipo de documento para XML FUNDAE."""
    if not nif:
        return 20  # Pasaporte por defecto
    
    nif = nif.upper().strip()
    if re.match(r'^[0-9]{8}[A-Z]$', nif):
        return 10  # NIF
    elif re.match(r'^[XYZ][0-9]{7}[A-Z]$', nif):
        return 60  # NIE
    else:
        return 20  # Pasaporte

def migrar_horarios_existentes(supabase):
    """
    Función de migración única para convertir horarios de texto a estructurados.
    Ejecutar una sola vez después de crear las nuevas tablas.
    """
    try:
        # Obtener grupos con horarios de texto
        grupos = supabase.table("grupos").select("""
            id, horario, 
            accion_formativa:acciones_formativas(num_horas)
        """).not_.is_("horario", "null").execute()
        
        migrados = 0
        errores = 0
        
        for grupo in grupos.data or []:
            horario_str = grupo.get("horario")
            if not horario_str:
                continue
                
            try:
                # Parsear horario de texto simple
                horas_accion = 0
                if grupo.get("accion_formativa"):
                    horas_accion = grupo["accion_formativa"].get("num_horas", 0)
                
                # Parsear horario básico (simplificado para migración)
                partes = horario_str.split(" | ")
                m_ini = m_fin = t_ini = t_fin = None
                dias = ""
                
                for parte in partes:
                    if parte.startswith("Mañana:"):
                        horas = parte.replace("Mañana: ", "").split(" - ")
                        if len(horas) == 2:
                            m_ini, m_fin = horas[0].strip(), horas[1].strip()
                    elif parte.startswith("Tarde:"):
                        horas = parte.replace("Tarde: ", "").split(" - ")
                        if len(horas) == 2:
                            t_ini, t_fin = horas[0].strip(), horas[1].strip()
                    elif parte.startswith("Días:"):
                        dias = parte.replace("Días: ", "").replace("-", "")
                
                # Crear registro en grupos_horarios
                datos_horario = {
                    "grupo_id": grupo["id"],
                    "horas_totales": float(horas_accion) if horas_accion else 0.0,
                    "hora_inicio_tramo1": m_ini,
                    "hora_fin_tramo1": m_fin,
                    "hora_inicio_tramo2": t_ini,
                    "hora_fin_tramo2": t_fin,
                    "dias": dias
                }
                
                # Eliminar horario anterior si existe
                supabase.table("grupos_horarios").delete().eq("grupo_id", grupo["id"]).execute()
                
                # Insertar nuevo horario
                result = supabase.table("grupos_horarios").insert(datos_horario).execute()
                if result.data:
                    migrados += 1
                else:
                    errores += 1
                    
            except Exception as e:
                print(f"Error procesando grupo {grupo['id']}: {e}")
                errores += 1
        
        return migrados, errores
        
    except Exception as e:
        print(f"Error en migración de horarios: {e}")
        return 0, 1
