import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from lxml import etree
import xml.etree.ElementTree as ET
import re
from datetime import datetime, date
import uuid
import requests

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
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 2 * cm

        if encabezado:
            c.setFont("Helvetica-Bold", 14)
            c.drawString(2 * cm, y, encabezado)
            y -= 0.7 * cm
            c.setFont("Helvetica", 10)
            c.drawString(2 * cm, y, f"Generado el {datetime.today().strftime('%d/%m/%Y')}")
            y -= 1.3 * cm

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
# Validación de XML con XSD (desde string o URL)
# =========================
def validar_xml(xml_string: str, xsd_string: str = None, xsd_url: str = None) -> bool:
    try:
        if xsd_url:
            r = requests.get(xsd_url)
            xsd_string = r.text

        if not xsd_string or not xsd_string.strip().startswith("<"):
            st.error("❌ El esquema XSD no se ha cargado correctamente.")
            return False

        xsd_doc = etree.XML(xsd_string.encode("utf-8"))
        schema = etree.XMLSchema(xsd_doc)
        xml_doc = etree.XML(xml_string.encode("utf-8"))
        schema.assertValid(xml_doc)
        return True

    except etree.DocumentInvalid:
        errores = schema.error_log
        st.error("❌ El XML no es válido según el esquema XSD.")
        for err in errores:
            st.markdown(f"- 🛑 Línea {err.line}: `{err.message}`")
        return False
    except Exception as e:
        st.error(f"⚠️ Error técnico al validar XML: {e}")
        return False

# =========================
# Generadores XML FUNDAE (versión antigua con ElementTree)
# =========================
def generar_xml_accion_formativa_et(accion: dict) -> str:
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
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

# =========================
# Generadores XML FUNDAE (versión nueva con lxml)
# =========================
def generar_xml_accion_formativa(accion, namespace="http://www.fundae.es/esquemas"):
    nsmap = {None: namespace, 'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}
    root = etree.Element("ACCIONES_FORMATIVAS", nsmap=nsmap)
    root.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", f"{namespace} AAFF_Inicio.xsd")
    accion_elem = etree.SubElement(root, "ACCION_FORMATIVA")
    etree.SubElement(accion_elem, "CODIGO_ACCION").text = str(accion.get('codigo', ''))
    etree.SubElement(accion_elem, "DENOMINACION").text = str(accion.get('denominacion', ''))
    etree.SubElement(accion_elem, "MODALIDAD").text = str(accion.get('modalidad', 'PRESENCIAL'))
    etree.SubElement(accion_elem, "HORAS").text = str(accion.get('horas', 0))
    if accion.get('area_profesional'):
        etree.SubElement(accion_elem, "AREA_PROFESIONAL").text = str(accion['area_profesional'])
    if accion.get('fecha_inicio'):
        etree.SubElement(accion_elem, "FECHA_INICIO").text = str(accion['fecha_inicio'])
    if accion.get('fecha_fin'):
        etree.SubElement(accion_elem, "FECHA_FIN").text = str(accion['fecha_fin'])
    if accion.get('contenidos'):
        etree.SubElement(accion_elem, "CONTENIDOS").text = str(accion['contenidos'])
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode('utf-8')

# =========================
# Ajustes globales de la app
# =========================
def get_ajustes_app(supabase, campos=None):
    try:
        query = supabase.table("ajustes_app")
        query = query.select(",".join(campos)) if campos else query.select("*")
        res = query.eq("id", 1).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        st.error(f"❌ Error al cargar ajustes de la app: {e}")
        return {}

def update_ajustes_app(supabase, data_dict):
    try:
        data_dict["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("ajustes_app").update(data_dict).eq("id", 1).execute()
    except Exception as e:
        st.error(f"❌ Error al guardar ajustes de la app: {e}")

# =========================
# Subida y eliminación de archivos en Supabase
# =========================
def subir_archivo_supabase(supabase, archivo, empresa_id, bucket="documentos"):
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
# Renderizado seguro de textos
# =========================
def render_texto(texto: str, modo="markdown"):
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
    if rol == "alumno":
        return False
    if not empresa or not modulo:
        return False

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

    fecha_inicio = empresa.get(f"{modulo}_inicio")
    fecha_fin = empresa.get(f"{modulo}_fin")
    if fecha_inicio and fecha_fin:
        try:
            inicio = pd.to_datetime(fecha_inicio).date()
            fin = pd.to_datetime(fecha_fin).date()
            return inicio <= fecha <= fin
        except Exception:
            return False

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

# =========================
# Export CSV helper
# =========================
def export_csv(df, filename="data.csv"):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("💾 Descargar CSV", data=csv, file_name=filename, mime="text/csv")


