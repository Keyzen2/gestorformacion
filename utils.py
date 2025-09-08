import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from lxml import etree
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import uuid

# =========================
# Importar participantes desde Excel
# =========================
def importar_participantes_excel(file):
    try:
        if not file:
            st.warning("⚠️ No se ha proporcionado ningún archivo.")
            return pd.DataFrame()
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"❌ Error al leer el Excel: {e}")
        return pd.DataFrame()

# =========================
# Generar PDF profesional
# =========================
def generar_pdf(nombre_archivo, contenido="Documento generado", encabezado=None):
    """
    Genera un PDF en memoria con el contenido indicado.
    Devuelve un BytesIO listo para subir o descargar.
    El encabezado es opcional.
    """
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        y = height - 2 * cm

        # Encabezado opcional
        if encabezado:
            c.setFont("Helvetica-Bold", 14)
            c.drawString(2 * cm, y, encabezado)
            y -= 0.7 * cm
            c.setFont("Helvetica", 10)
            c.drawString(2 * cm, y, f"Generado el {datetime.today().strftime('%d/%m/%Y')}")
            y -= 1.3 * cm

        # Contenido
        c.setFont("Helvetica", 10)
        for linea in contenido.split("\n"):
            if y < 2 * cm:
                c.showPage()
                y = height - 2 * cm
                c.setFont("Helvetica", 10)
            c.drawString(2 * cm, y, linea.strip())
            y -= 0.5 * cm

        c.save()
        buffer.seek(0)
        return buffer
    except Exception as e:
        st.error(f"❌ Error al generar el PDF: {e}")
        return None

# =========================
# Validación de XML con XSD
# =========================
def validar_xml(xml_string: str, xsd_string: str) -> bool:
    try:
        # Verificar que el esquema XSD comienza con una etiqueta válida
        if not xsd_string.strip().startswith("<"):
            st.error("❌ El esquema XSD no se ha cargado correctamente. Verifica la URL o el archivo.")
            return False

        # Parsear el esquema XSD
        xsd_doc = etree.XML(xsd_string.encode("utf-8"))
        schema = etree.XMLSchema(xsd_doc)

        # Parsear el XML generado
        xml_doc = etree.XML(xml_string.encode("utf-8"))

        # Validar y capturar errores detallados
        schema.assertValid(xml_doc)
        return True

    except etree.DocumentInvalid as e:
        errores = schema.error_log
        st.error("❌ El XML no es válido según el esquema XSD.")
        for err in errores:
            st.markdown(f"- 🛑 Línea {err.line}: `{err.message}`")
        return False

    except Exception as e:
        st.error(f"⚠️ Error técnico al validar XML: {e}")
        return False

# =========================
# Generador XML: Acción Formativa
# =========================
def generar_xml_accion_formativa(accion: dict) -> str:
    root = ET.Element("ACCIONES_FORMATIVAS", xmlns="http://www.fundae.es/esquemas/accion_formativa")
    af = ET.SubElement(root, "ACCION_FORMATIVA")

    datos = ET.SubElement(af, "DATOS_GENERALES")
    ET.SubElement(datos, "CODIGO_ACCION").text = str(accion.get("codigo_accion", ""))
    ET.SubElement(datos, "NOMBRE_ACCION").text = accion.get("nombre", "")
    ET.SubElement(datos, "CODIGO_AREA_PROFESIONAL").text = accion.get("cod_area_profesional", "")
    ET.SubElement(datos, "CODIGO_GRUPO_ACCION").text = accion.get("codigo_grupo_accion", "")
    ET.SubElement(datos, "SECTOR").text = accion.get("sector") or "No especificado"
    ET.SubElement(datos, "OBJETIVOS").text = accion.get("objetivos") or "No especificado"
    ET.SubElement(datos, "CONTENIDOS").text = accion.get("contenidos") or "No especificado"
    ET.SubElement(datos, "MODALIDAD").text = accion.get("modalidad", "")
    ET.SubElement(datos, "NIVEL").text = accion.get("nivel", "")
    ET.SubElement(datos, "DURACION").text = str(accion.get("num_horas") or accion.get("duracion_horas") or 0)
    ET.SubElement(datos, "CERTIFICADO_PROFESIONALIDAD").text = "S" if accion.get("certificado_profesionalidad") else "N"

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")

# =========================
# Generador XML: Inicio de Grupo
# =========================
def generar_xml_inicio_grupo(grupo: dict) -> str:
    root = ET.Element("INICIO_GRUPO", xmlns="http://www.fundae.es/esquemas/InicioGrupos_Organizadora")
    datos = ET.SubElement(root, "DATOS_GRUPO")

    ET.SubElement(datos, "CODIGO_GRUPO").text = grupo.get("codigo_grupo", "")
    ET.SubElement(datos, "CODIGO_ACCION").text = grupo.get("accion_formativa_id", "")
    ET.SubElement(datos, "FECHA_INICIO").text = grupo.get("fecha_inicio", "")
    ET.SubElement(datos, "AULA_VIRTUAL").text = "S" if grupo.get("aula_virtual") else "N"
    ET.SubElement(datos, "LOCALIDAD").text = grupo.get("localidad") or "No especificado"
    ET.SubElement(datos, "PROVINCIA").text = grupo.get("provincia") or "No especificado"
    ET.SubElement(datos, "CP").text = grupo.get("cp") or "00000"
    ET.SubElement(datos, "N_PARTICIPANTES_PREVISTOS").text = str(grupo.get("n_participantes_previstos") or 0)
    ET.SubElement(datos, "OBSERVACIONES").text = grupo.get("observaciones") or ""

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")

# =========================
# Generador XML: Finalización de Grupo
# =========================
def generar_xml_finalizacion_grupo(grupo: dict) -> str:
    root = ET.Element("FINALIZACION_GRUPO", xmlns="http://www.fundae.es/esquemas/FinalizacionGrupo_Organizadora")
    datos = ET.SubElement(root, "DATOS_FINALIZACION")

    ET.SubElement(datos, "CODIGO_GRUPO").text = grupo.get("codigo_grupo", "")
    ET.SubElement(datos, "CODIGO_ACCION").text = grupo.get("accion_formativa_id", "")
    ET.SubElement(datos, "FECHA_FIN").text = grupo.get("fecha_fin", "")
    ET.SubElement(datos, "N_PARTICIPANTES_FINALIZADOS").text = str(grupo.get("n_participantes_finalizados") or 0)
    ET.SubElement(datos, "N_APTOS").text = str(grupo.get("n_aptos") or 0)
    ET.SubElement(datos, "N_NO_APTOS").text = str(grupo.get("n_no_aptos") or 0)
    ET.SubElement(datos, "OBSERVACIONES").text = grupo.get("observaciones") or ""

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")
# =========================
# Ajustes globales de la app
# =========================
def get_ajustes_app(supabase, campos=None):
    """
    Devuelve los ajustes globales desde la tabla ajustes_app.
    Si se especifican campos, se hace un select parcial.
    """
    try:
        query = supabase.table("ajustes_app")
        if campos:
            query = query.select(",".join(campos))
        else:
            query = query.select("*")
        res = query.eq("id", 1).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        st.error(f"❌ Error al cargar ajustes de la app: {e}")
        return {}

def update_ajustes_app(supabase, data_dict):
    """
    Actualiza los ajustes globales en la tabla ajustes_app.
    """
    try:
        data_dict["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("ajustes_app").update(data_dict).eq("id", 1).execute()
    except Exception as e:
        st.error(f"❌ Error al guardar ajustes de la app: {e}")
        
# =========================
# Subida de archivos a Supabase Storage por empresa
# =========================
def subir_archivo_supabase(supabase, archivo, empresa_id, bucket="documentos"):
    """
    Sube un archivo a Supabase Storage en una carpeta por empresa.
    Devuelve la URL pública del archivo o None si falla.
    """
    try:
        nombre_original = archivo.name
        extension = nombre_original.split(".")[-1]
        nombre_unico = f"{uuid.uuid4()}.{extension}"
        ruta = f"empresa_{empresa_id}/{nombre_unico}"

        res = supabase.storage.from_(bucket).upload(ruta, archivo)
        if res.get("error"):
            st.error("❌ Error al subir el archivo a Supabase Storage.")
            return None

        url = supabase.storage.from_(bucket).get_public_url(ruta)
        return url
    except Exception as e:
        st.error(f"❌ Error al subir archivo: {e}")
        return None
        
# =========================
# Eliminación de archivos en Supabase Storage
# =========================
def eliminar_archivo_supabase(supabase, url, bucket="documentos"):
    """
    Elimina un archivo de Supabase Storage a partir de su URL pública.
    """
    try:
        # Extraer ruta interna desde la URL pública
        base_url = supabase.storage.from_(bucket).get_public_url("")
        if not url.startswith(base_url):
            st.warning("⚠️ La URL no pertenece al bucket especificado.")
            return False

        ruta = url.replace(base_url, "")
        res = supabase.storage.from_(bucket).remove([ruta])
        if res.get("error"):
            st.error("❌ Error al eliminar el archivo de Supabase Storage.")
            return False

        return True
    except Exception as e:
        st.error(f"❌ Error al procesar la eliminación del archivo: {e}")
        return False
        
# =========================
# Renderizado seguro de textos
# =========================
def render_texto(texto: str, modo="markdown"):
    """
    Renderiza texto en Streamlit según el modo indicado.
    - markdown: usa st.markdown()
    - html: usa st.markdown(..., unsafe_allow_html=True)
    """
    if not isinstance(texto, str) or not texto.strip():
        return
    try:
        if modo == "html":
            st.markdown(texto, unsafe_allow_html=True)
        else:
            st.markdown(texto)
    except Exception as e:
        st.error(f"❌ Error al renderizar texto: {e}")
        
# =========================
# Verificación de módulo activo por empresa
# =========================
def is_module_active(empresa: dict, empresa_crm: dict, modulo: str, fecha: date, rol: str) -> bool:
    """
    Verifica si un módulo está activo para una empresa en una fecha determinada y para un rol específico.
    """

    if rol == "alumno":
        return False

    if not empresa or not modulo:
        return False

    # Verificación directa por campo *_activo
    if empresa.get(f"{modulo}_activo") is True:
        fecha_inicio = empresa.get(f"{modulo}_inicio")
        if fecha_inicio:
            try:
                inicio = pd.to_datetime(fecha_inicio).date()
                if inicio > fecha:
                    return False
            except Exception:
                return False
        return True

    # Verificación por rango de fechas
    fecha_inicio = empresa.get(f"{modulo}_inicio")
    fecha_fin = empresa.get(f"{modulo}_fin")
    if fecha_inicio and fecha_fin:
        try:
            inicio = pd.to_datetime(fecha_inicio).date()
            fin = pd.to_datetime(fecha_fin).date()
            return inicio <= fecha <= fin
        except Exception:
            return False

    # Verificación por CRM si aplica
    if modulo == "crm" and empresa_crm:
        if empresa_crm.get("crm_activo") is True:
            crm_inicio = empresa_crm.get("crm_inicio")
            if crm_inicio:
                try:
                    inicio = pd.to_datetime(crm_inicio).date()
                    if inicio > fecha:
                        return False
                except Exception:
                    return False
            return True

    return False
    
# =========================
# Validación de DNI/NIE/CIF español
# =========================
def validar_dni_cif(valor: str) -> bool:
    if not valor:
        return False
    valor = valor.upper().strip()

    dni_regex = r'^\d{8}[A-Z]$'
    nie_regex = r'^[XYZ]\d{7}[A-Z]$'
    cif_regex = r'^[ABCDEFGHJKLMNPQRSUVW]\d{7}[0-9A-J]$'

    letras_dni = "TRWAGMYFPDXBNJZSQVHLCKE"

    if re.match(dni_regex, valor):
        numero = int(valor[:-1])
        letra = valor[-1]
        return letras_dni[numero % 23] == letra

    elif re.match(nie_regex, valor):
        mapa = {'X': '0', 'Y': '1', 'Z': '2'}
        numero = int(mapa[valor[0]] + valor[1:-1])
        letra = valor[-1]
        return letras_dni[numero % 23] == letra

    elif re.match(cif_regex, valor):
        return True

    return False
