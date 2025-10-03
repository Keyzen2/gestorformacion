import streamlit as st
import pandas as pd
import locale
from datetime import datetime, date
from io import BytesIO
from typing import Optional, Dict
from services.participantes_service import get_participantes_service
from services.grupos_service import get_grupos_service
from services.empresas_service import get_empresas_service

# Importar reportlab
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    

# =========================
# SERVICIO DE FIRMAS
# =========================
class FirmasService:
    """Gestión de firmas digitales para diplomas."""
    
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
    
    def get_firma_empresa(self, empresa_id: str) -> Optional[Dict]:
        """Obtiene la firma digital de una empresa."""
        try:
            result = self.supabase.table("empresas_firmas_diplomas").select("*").eq(
                "empresa_id", empresa_id
            ).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            st.error(f"Error obteniendo firma: {e}")
            return None
    
    def subir_firma(self, empresa_id: str, archivo_firma) -> bool:
        """Sube una nueva firma digital."""
        try:
            if archivo_firma.size > 2 * 1024 * 1024:
                st.error("Archivo muy grande. Máximo 2MB")
                return False
            
            timestamp = int(datetime.now().timestamp())
            file_name = f"firma_{timestamp}.png"
            file_path = f"firmas_diplomas/{empresa_id}/{file_name}"
            
            self.supabase.storage.from_("diplomas").upload(
                file_path,
                archivo_firma.getvalue(),
                {"content-type": "image/png"}
            )
            
            url = self.supabase.storage.from_("diplomas").get_public_url(file_path)
            
            firma_existente = self.get_firma_empresa(empresa_id)
            
            if firma_existente:
                self.supabase.table("empresas_firmas_diplomas").update({
                    "archivo_url": url,
                    "archivo_nombre": file_name,
                    "updated_at": datetime.now().isoformat()
                }).eq("empresa_id", empresa_id).execute()
            else:
                self.supabase.table("empresas_firmas_diplomas").insert({
                    "empresa_id": empresa_id,
                    "archivo_url": url,
                    "archivo_nombre": file_name
                }).execute()
            
            return True
        
        except Exception as e:
            st.error(f"Error subiendo firma: {e}")
            return False
    
    def eliminar_firma(self, empresa_id: str) -> bool:
        """Elimina la firma digital de una empresa."""
        try:
            self.supabase.table("empresas_firmas_diplomas").delete().eq(
                "empresa_id", empresa_id
            ).execute()
            return True
        except Exception as e:
            st.error(f"Error eliminando firma: {e}")
            return False
            
# =========================
# SERVICIO DE LOGOTIPOS
# =========================
class LogosService:
    """Gestión de logotipos de empresa para diplomas."""
    
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
    
    def get_logo_empresa(self, empresa_id: str) -> Optional[Dict]:
        """Obtiene el logotipo de una empresa."""
        try:
            result = self.supabase.table("empresas_logos_diplomas").select("*").eq(
                "empresa_id", empresa_id
            ).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error obteniendo logo: {e}")
            return None
    
    def subir_logo(self, empresa_id: str, archivo_logo) -> bool:
        """Sube un nuevo logotipo."""
        try:
            # Validar tamaño (max 5MB para logos)
            if archivo_logo.size > 5 * 1024 * 1024:
                st.error("Archivo muy grande. Máximo 5MB")
                return False
            
            timestamp = int(datetime.now().timestamp())
            file_name = f"logo_{timestamp}.png"
            file_path = f"logos_diplomas/{empresa_id}/{file_name}"
            
            # Subir al bucket
            self.supabase.storage.from_("diplomas").upload(
                file_path,
                archivo_logo.getvalue(),
                {"content-type": "image/png"}
            )
            
            url = self.supabase.storage.from_("diplomas").get_public_url(file_path)
            
            # Actualizar o insertar en BD
            logo_existente = self.get_logo_empresa(empresa_id)
            
            if logo_existente:
                self.supabase.table("empresas_logos_diplomas").update({
                    "archivo_url": url,
                    "archivo_nombre": file_name,
                    "updated_at": datetime.now().isoformat()
                }).eq("empresa_id", empresa_id).execute()
            else:
                self.supabase.table("empresas_logos_diplomas").insert({
                    "empresa_id": empresa_id,
                    "archivo_url": url,
                    "archivo_nombre": file_name
                }).execute()
            
            return True
        
        except Exception as e:
            st.error(f"Error subiendo logo: {e}")
            return False
    
    def eliminar_logo(self, empresa_id: str) -> bool:
        """Elimina el logotipo de una empresa."""
        try:
            self.supabase.table("empresas_logos_diplomas").delete().eq(
                "empresa_id", empresa_id
            ).execute()
            return True
        except Exception as e:
            st.error(f"Error eliminando logo: {e}")
            return False
            
# =========================
# CANVAS PERSONALIZADO CON BORDE CLASICO
# =========================
class DiplomaCanvas(canvas.Canvas):
    """Canvas personalizado con borde decorativo."""
    
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []
    
    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()
    
    def save(self):
        page_count = len(self.pages)
        for page_num, page in enumerate(self.pages):
            self.__dict__.update(page)
            if page_num == 0:
                self.draw_border()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
    
    def draw_border(self):
        """Dibuja borde decorativo en la primera página."""
        width, height = landscape(A4)
        
        margen = 1.5 * cm
        grosor_principal = 4
        grosor_secundario = 1
        
        # Borde exterior
        self.setStrokeColor(colors.HexColor("#2c3e50"))
        self.setLineWidth(grosor_principal)
        self.rect(margen, margen, width - 2 * margen, height - 2 * margen)
        
        # Borde interior
        self.setStrokeColor(colors.HexColor("#3498db"))
        self.setLineWidth(grosor_secundario)
        margen_interno = margen + 0.3 * cm
        self.rect(margen_interno, margen_interno, width - 2 * margen_interno, height - 2 * margen_interno)

# =========================
# GENERADOR DE PDF
# =========================
def generar_diploma_pdf(participante, grupo, accion, firma_url=None, logo_url=None, datos_personalizados=None) -> BytesIO:
    """Genera el PDF del diploma con diseño profesional y borde decorativo."""
    if not REPORTLAB_AVAILABLE:
        st.error("reportlab no está instalado")
        return None
    
    # Aplicar datos personalizados
    if datos_personalizados:
        if 'nombre_completo' in datos_personalizados:
            partes = datos_personalizados['nombre_completo'].split(' ', 1)
            participante['nombre'] = partes[0]
            participante['apellidos'] = partes[1] if len(partes) > 1 else ''
        for key in ['tipo_documento', 'nif']:
            if key in datos_personalizados:
                participante[key] = datos_personalizados[key]
        if 'accion_nombre' in datos_personalizados:
            accion['nombre'] = datos_personalizados['accion_nombre']
        for key in ['horas', 'modalidad']:
            if key in datos_personalizados:
                if key == 'horas':
                    accion['horas'] = datos_personalizados[key]
                else:
                    grupo[key] = datos_personalizados[key]
        for key in ['fecha_inicio', 'fecha_fin']:
            if key in datos_personalizados:
                grupo[key] = datos_personalizados[key]
        if 'contenidos' in datos_personalizados:
            accion['contenidos'] = datos_personalizados['contenidos']
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=3*cm, rightMargin=3*cm,
                            topMargin=3*cm, bottomMargin=3*cm)
    
    elementos = []
    styles = getSampleStyleSheet()
    
    style_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'],
        fontSize=48, textColor=colors.HexColor("#2c3e50"),
        alignment=TA_CENTER, spaceAfter=30, fontName='Helvetica-Bold')
    
    style_accion = ParagraphStyle('Accion', parent=styles['Heading2'],
        fontSize=36, textColor=colors.HexColor("#3498db"),
        alignment=TA_CENTER, spaceAfter=20, fontName='Helvetica-Bold')
    
    style_datos = ParagraphStyle('Datos', parent=styles['Normal'],
        fontSize=14, alignment=TA_CENTER, spaceAfter=12, fontName='Helvetica')
    
    style_contenidos = ParagraphStyle('Contenidos', parent=styles['Normal'],
        fontSize=11, alignment=TA_JUSTIFY, spaceAfter=8, leading=14, fontName='Helvetica')
    
    # CARA A
    elementos.append(Spacer(1, 0.3*cm))
    
    # Añadir logotipo si existe
    if logo_url:
        elementos.append(Spacer(1, 0.2*cm))  # Menos espacio inicial
        try:
            logo = Image(logo_url, width=6*cm, height=2*cm, kind='proportional')
            logo.hAlign = 'CENTER'
            elementos.append(logo)
            elementos.append(Spacer(1, 0.3*cm))
        except Exception as e:
            print(f"Error cargando logo: {e}")
    else:
        elementos.append(Spacer(1, 0.5*cm))
    elementos.append(Spacer(1, 0.5*cm))
    elementos.append(Paragraph("DIPLOMA", style_titulo))
    elementos.append(Spacer(1, 0.8*cm))
    
    nombre_completo = f"{participante.get('nombre', '')} {participante.get('apellidos', '')}".strip()
    tipo_doc = participante.get('tipo_documento', 'NIF')
    num_doc = participante.get('nif', 'Sin documento')
    
    elementos.append(Paragraph(f"<b>{nombre_completo}</b>", style_datos))
    elementos.append(Paragraph(f"con {tipo_doc} <b>{num_doc}</b>", style_datos))
    elementos.append(Spacer(1, 0.8*cm))
    elementos.append(Paragraph("ha realizado con aprovechamiento este curso:", style_datos))
    elementos.append(Spacer(1, 0.3*cm))
    
    accion_nombre = accion.get('nombre', 'Curso no especificado')
    elementos.append(Paragraph(accion_nombre, style_accion))
    elementos.append(Spacer(1, 0.8*cm))
    
    horas = accion.get('horas', 0) or accion.get('num_horas', 0)
    modalidad = grupo.get('modalidad', 'PRESENCIAL')
    fecha_inicio = grupo.get('fecha_inicio')
    fecha_fin = grupo.get('fecha_fin') or grupo.get('fecha_fin_prevista')
    
    fecha_inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y') if fecha_inicio else "No especificada"
    fecha_fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y') if fecha_fin else "No especificada"
    
    texto_detalles = (
        f"con una duración de <b>{horas} horas</b>, "
        f"en modalidad <b>{modalidad}</b>, "
        f"entre el <b>{fecha_inicio_str}</b> y el <b>{fecha_fin_str}</b>."
    )
    elementos.append(Paragraph(texto_detalles, style_datos))
    elementos.append(Spacer(1, 1*cm))

    from utils import formato_fecha
    meses = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
        5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
        9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    hoy = datetime.now()
    fecha_emision = f"{hoy.day} de {meses[hoy.month]} de {hoy.year}"
    elementos.append(Paragraph(f"Firmado a {fecha_emision}", style_datos))
    
        # CARA B
    elementos.append(PageBreak())
    style_titulo_b = ParagraphStyle('TituloB', parent=styles['Heading1'],
        fontSize=32, textColor=colors.HexColor("#2c3e50"),
        alignment=TA_CENTER, spaceAfter=20, fontName='Helvetica-Bold')
    elementos.append(Paragraph("CONTENIDOS", style_titulo_b))
    elementos.append(Spacer(1, 0.5*cm))
    
    contenidos = accion.get('contenidos', '')
    if contenidos and contenidos.strip():
        contenidos_texto = contenidos.replace('\n\n', '<br/><br/>').replace('\n', '<br/>')
        elementos.append(Paragraph(contenidos_texto, style_contenidos))
    else:
        elementos.append(Paragraph("Los contenidos de este curso no han sido especificados.", style_contenidos))
        
    # === FUNCIÓN INTERNA PARA DIBUJAR FIRMA ===
    def dibujar_firma(canvas, doc, firma_url=firma_url):
        if firma_url:
            try:
                canvas.drawImage(
                    firma_url,
                    x=doc.pagesize[0] / 2 - 60,  # centrado horizontal
                    y=80,                       # 120 pt desde abajo
                    width=160,
                    height=60,
                    mask="auto"
                )
            except Exception as e:
                print("Error dibujando firma:", e)
                
    # === CONSTRUIR DOCUMENTO ===
    doc.build(
        elementos,
        onFirstPage=lambda c, d: dibujar_firma(c, d, firma_url),
        canvasmaker=DiplomaCanvas
    )
    buffer.seek(0)
    return buffer
    
# =========================
# PLANTILLA MODERNA
# =========================
def generar_diploma_moderno(participante, grupo, accion, firma_url=None, logo_url=None, datos_personalizados=None) -> BytesIO:
    """Genera diploma con diseño moderno y minimalista."""
    if not REPORTLAB_AVAILABLE:
        return None
    
    # Aplicar datos personalizados (igual que clásico)
    if datos_personalizados:
        if 'nombre_completo' in datos_personalizados:
            partes = datos_personalizados['nombre_completo'].split(' ', 1)
            participante['nombre'] = partes[0]
            participante['apellidos'] = partes[1] if len(partes) > 1 else ''
        for key in ['tipo_documento', 'nif']:
            if key in datos_personalizados:
                participante[key] = datos_personalizados[key]
        if 'accion_nombre' in datos_personalizados:
            accion['nombre'] = datos_personalizados['accion_nombre']
        for key in ['horas', 'modalidad']:
            if key in datos_personalizados:
                if key == 'horas':
                    accion['horas'] = datos_personalizados[key]
                else:
                    grupo[key] = datos_personalizados[key]
        for key in ['fecha_inicio', 'fecha_fin']:
            if key in datos_personalizados:
                grupo[key] = datos_personalizados[key]
        if 'contenidos' in datos_personalizados:
            accion['contenidos'] = datos_personalizados['contenidos']
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    elementos = []
    styles = getSampleStyleSheet()
    
    # Estilos modernos (sin serif, colores más neutros)
    style_titulo = ParagraphStyle('TituloModerno',
        fontSize=56,
        textColor=colors.HexColor("#1a1a1a"),
        alignment=TA_CENTER,
        fontName='Helvetica',
        spaceAfter=15,
        leading=60
    )
    
    style_subtitulo = ParagraphStyle('SubtituloModerno',
        fontSize=18,
        textColor=colors.HexColor("#666666"),
        alignment=TA_CENTER,
        fontName='Helvetica',
        spaceAfter=25
    )
    
    style_nombre = ParagraphStyle('NombreModerno',
        fontSize=32,
        textColor=colors.HexColor("#2563eb"),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=10
    )
    
    style_accion = ParagraphStyle('AccionModerno',
        fontSize=24,
        textColor=colors.HexColor("#1a1a1a"),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=15,
        leading=28
    )
    
    style_datos = ParagraphStyle('DatosModerno',
        fontSize=13,
        textColor=colors.HexColor("#4b5563"),
        alignment=TA_CENTER,
        fontName='Helvetica',
        spaceAfter=8
    )
    
    style_contenidos = ParagraphStyle('ContenidosModerno',
        fontSize=11,
        textColor=colors.HexColor("#374151"),
        alignment=TA_JUSTIFY,
        fontName='Helvetica',
        spaceAfter=8,
        leading=14
    )
    
    # CARA A - Diseño moderno
    elementos.append(Spacer(1, 1*cm))
    
    # Logo más grande y prominente
    if logo_url:
        try:
            logo = Image(logo_url, width=10*cm, height=3.5*cm, kind='proportional')
            logo.hAlign = 'CENTER'
            elementos.append(logo)
            elementos.append(Spacer(1, 1*cm))
        except Exception as e:
            print(f"Error cargando logo: {e}")
            elementos.append(Spacer(1, 0.5*cm))
    
    # Título sin "DIPLOMA" - más moderno
    elementos.append(Paragraph("CERTIFICADO DE FORMACIÓN", style_titulo))
    elementos.append(Paragraph("Se certifica que", style_subtitulo))
    elementos.append(Spacer(1, 0.5*cm))
    
    # Nombre destacado
    nombre_completo = f"{participante.get('nombre', '')} {participante.get('apellidos', '')}".strip()
    elementos.append(Paragraph(nombre_completo, style_nombre))
    
    tipo_doc = participante.get('tipo_documento', 'NIF')
    num_doc = participante.get('nif', 'Sin documento')
    elementos.append(Paragraph(f"{tipo_doc}: {num_doc}", style_datos))
    elementos.append(Spacer(1, 0.8*cm))
    
    # Acción formativa
    elementos.append(Paragraph("ha completado satisfactoriamente", style_datos))
    elementos.append(Spacer(1, 0.3*cm))
    
    accion_nombre = accion.get('nombre', 'Curso no especificado')
    elementos.append(Paragraph(accion_nombre, style_accion))
    elementos.append(Spacer(1, 0.8*cm))
    
    # Detalles en formato moderno (tabla limpia)
    horas = accion.get('horas', 0) or accion.get('num_horas', 0)
    modalidad = grupo.get('modalidad', 'PRESENCIAL')
    fecha_inicio = grupo.get('fecha_inicio')
    fecha_fin = grupo.get('fecha_fin') or grupo.get('fecha_fin_prevista')
    
    fecha_inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y') if fecha_inicio else "No especificada"
    fecha_fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y') if fecha_fin else "No especificada"
    
    # Tabla de detalles minimalista
    datos_tabla = [
        ["Duración:", f"{horas} horas"],
        ["Modalidad:", modalidad],
        ["Período:", f"{fecha_inicio_str} - {fecha_fin_str}"]
    ]
    
    tabla = Table(datos_tabla, colWidths=[6*cm, 10*cm])
    tabla.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#4b5563")),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    tabla.hAlign = 'CENTER'
    elementos.append(tabla)
    elementos.append(Spacer(1, 1*cm))
    
    # Fecha de emisión
    meses = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
        5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
        9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    hoy = datetime.now()
    fecha_emision = f"{hoy.day} de {meses[hoy.month]} de {hoy.year}"
    elementos.append(Paragraph(fecha_emision, style_datos))
    
    # CARA B - Contenidos
    elementos.append(PageBreak())
    
    style_titulo_contenidos = ParagraphStyle('TituloContenidosModerno',
        fontSize=28,
        textColor=colors.HexColor("#1a1a1a"),
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        spaceAfter=20
    )
    
    elementos.append(Spacer(1, 1*cm))
    elementos.append(Paragraph("Contenidos del programa", style_titulo_contenidos))
    elementos.append(Spacer(1, 0.5*cm))
    
    contenidos = accion.get('contenidos', '')
    if contenidos and contenidos.strip():
        contenidos_texto = contenidos.replace('\n\n', '<br/><br/>').replace('\n', '<br/>')
        elementos.append(Paragraph(contenidos_texto, style_contenidos))
    else:
        elementos.append(Paragraph("Los contenidos de este programa no han sido especificados.", style_contenidos))
    
    # Función para dibujar firma (sin borde)
    def dibujar_firma(canvas, doc, firma_url=firma_url):
        if firma_url:
            try:
                canvas.drawImage(
                    firma_url,
                    x=doc.pagesize[0] / 2 - 60,
                    y=60,
                    width=160,
                    height=60,
                    mask="auto"
                )
            except Exception as e:
                print("Error dibujando firma:", e)
    
    doc.build(
        elementos,
        onFirstPage=lambda c, d: dibujar_firma(c, d, firma_url)
    )
    buffer.seek(0)
    return buffer

# =========================
# PLANTILLA FUNDAE (OFICIAL)
# =========================
def generar_diploma_fundae(participante, grupo, accion, firma_url=None, logo_url=None, datos_personalizados=None) -> BytesIO:
    """Genera diploma con diseño oficial FUNDAE."""
    if not REPORTLAB_AVAILABLE:
        return None
    
    # Aplicar datos personalizados (igual que otras plantillas)
    if datos_personalizados:
        if 'nombre_completo' in datos_personalizados:
            partes = datos_personalizados['nombre_completo'].split(' ', 1)
            participante['nombre'] = partes[0]
            participante['apellidos'] = partes[1] if len(partes) > 1 else ''
        for key in ['tipo_documento', 'nif']:
            if key in datos_personalizados:
                participante[key] = datos_personalizados[key]
        if 'accion_nombre' in datos_personalizados:
            accion['nombre'] = datos_personalizados['accion_nombre']
        for key in ['horas', 'modalidad']:
            if key in datos_personalizados:
                if key == 'horas':
                    accion['horas'] = datos_personalizados[key]
                else:
                    grupo[key] = datos_personalizados[key]
        for key in ['fecha_inicio', 'fecha_fin']:
            if key in datos_personalizados:
                grupo[key] = datos_personalizados[key]
        if 'contenidos' in datos_personalizados:
            accion['contenidos'] = datos_personalizados['contenidos']
    
    buffer = BytesIO()
    
    # Canvas personalizado para dibujar elementos decorativos
    class FundaeCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self.pages = []
        
        def showPage(self):
            self.pages.append(dict(self.__dict__))
            self._startPage()
        
        def save(self):
            for page_num, page in enumerate(self.pages):
                self.__dict__.update(page)
                if page_num == 0:
                    self.draw_decorations()
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)
        
        def draw_decorations(self):
            """Dibuja líneas diagonales decorativas y bordes."""
            width, height = landscape(A4)
            
            # Borde doble azul
            self.setStrokeColor(colors.HexColor("#003d7a"))
            self.setLineWidth(3)
            margen = 1*cm
            self.rect(margen, margen, width - 2*margen, height - 2*margen)
            
            self.setLineWidth(1)
            margen_interno = margen + 0.2*cm
            self.rect(margen_interno, margen_interno, width - 2*margen_interno, height - 2*margen_interno)
            
            # Líneas diagonales decorativas (izquierda)
            colores_lineas = ["#003d7a", "#f39200", "#e63946"]
            x_start = 2*cm
            y_start = height - 3*cm
            
            for i, color in enumerate(colores_lineas * 3):
                self.setStrokeColor(colors.HexColor(color))
                self.setLineWidth(2)
                offset = i * 0.3*cm
                self.line(x_start + offset, y_start, x_start + offset + 3*cm, y_start - 6*cm)
    
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2.5*cm, bottomMargin=2*cm)
    
    elementos = []
    styles = getSampleStyleSheet()
    
    # Estilos FUNDAE
    style_titulo = ParagraphStyle('TituloFundae',
        fontSize=42,
        textColor=colors.HexColor("#003d7a"),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=5,
        leading=45
    )
    
    style_subtitulo = ParagraphStyle('SubtituloFundae',
        fontSize=24,
        textColor=colors.HexColor("#999999"),
        alignment=TA_CENTER,
        fontName='Helvetica',
        spaceAfter=20
    )
    
    style_label = ParagraphStyle('LabelFundae',
        fontSize=11,
        textColor=colors.HexColor("#333333"),
        alignment=TA_LEFT,
        fontName='Helvetica',
        spaceAfter=3
    )
    
    style_valor = ParagraphStyle('ValorFundae',
        fontSize=13,
        textColor=colors.HexColor("#000000"),
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        spaceAfter=8
    )
    
    style_contenidos = ParagraphStyle('ContenidosFundae',
        fontSize=10,
        textColor=colors.HexColor("#333333"),
        alignment=TA_JUSTIFY,
        fontName='Helvetica',
        spaceAfter=6,
        leading=12
    )
    
    # CARA A
    # Logos en tabla (empresa izquierda, FUNDAE derecha)
    logos_tabla = []
    
    if logo_url:
        try:
            logo_empresa = Image(logo_url, width=6*cm, height=2*cm, kind='proportional')
        except:
            logo_empresa = Paragraph("", style_label)
    else:
        logo_empresa = Paragraph("", style_label)
    
    # Logo FUNDAE (siempre fijo)
    try:
        logo_fundae = Paragraph(
            '<para align="right"><b><font size="14" color="#003d7a">Fundación Estatal</font></b><br/>'
            '<font size="10" color="#f39200">PARA LA FORMACIÓN EN EL EMPLEO</font></para>',
            style_label
        )
    except:
        logo_fundae = Paragraph("", style_label)
    
    logos_tabla.append([logo_empresa, logo_fundae])
    
    tabla_logos = Table(logos_tabla, colWidths=[12*cm, 12*cm])
    tabla_logos.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    elementos.append(tabla_logos)
    elementos.append(Spacer(1, 0.5*cm))
    
    # Título
    elementos.append(Paragraph("DIPLOMA", style_titulo))
    elementos.append(Paragraph("ACREDITATIVO", style_subtitulo))
    elementos.append(Spacer(1, 0.5*cm))
    
    # Datos en formato tabla (como el original)
    nombre_completo = f"{participante.get('nombre', '')} {participante.get('apellidos', '')}".strip()
    tipo_doc = participante.get('tipo_documento', 'NIF')
    num_doc = participante.get('nif', 'Sin documento')
    
    # Obtener empresa (puede ser diferente a la gestora)
    try:
        empresa_participante = grupo.get('centro_gestor_empresa_id') or grupo.get('empresa_id')
        if empresa_participante:
            from services.empresas_service import get_empresas_service
            # Nota: necesitarías pasar estos servicios como parámetro
            empresa_info = {"nombre": "Empresa", "cif": ""}
        else:
            empresa_info = {"nombre": "Empresa", "cif": ""}
    except:
        empresa_info = {"nombre": "Empresa", "cif": ""}
    
    datos = [
        [Paragraph("D./Dña.", style_label), 
         Paragraph(f"<b>{nombre_completo.upper()}</b>", style_valor),
         Paragraph("con NIF", style_label),
         Paragraph(f"<b>{num_doc}</b>", style_valor)],
        
        [Paragraph("que presta sus servicios en la Empresa", style_label),
         Paragraph(f"<b>{empresa_info['nombre']}</b>", style_valor),
         Paragraph("con CIF", style_label),
         Paragraph(f"<b>{empresa_info.get('cif', 'N/A')}</b>", style_valor)]
    ]
    
    tabla_datos = Table(datos, colWidths=[4*cm, 10*cm, 2*cm, 4*cm])
    tabla_datos.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla_datos)
    elementos.append(Spacer(1, 0.4*cm))
    
    # Acción formativa
    accion_nombre = accion.get('nombre', 'Curso no especificado')
    elementos.append(Paragraph(f"Ha superado con evaluación positiva la Acción Formativa <b>{accion_nombre}</b>", style_label))
    elementos.append(Spacer(1, 0.3*cm))
    
    # Código AF/Grupo y fechas
    codigo_grupo = grupo.get('codigo_grupo', 'N/A')
    fecha_inicio = grupo.get('fecha_inicio')
    fecha_fin = grupo.get('fecha_fin') or grupo.get('fecha_fin_prevista')
    
    fecha_inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y') if fecha_inicio else "N/A"
    fecha_fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y') if fecha_fin else "N/A"
    
    # Desglose de horas
    horas_totales = accion.get('horas', 0) or accion.get('num_horas', 0)
    modalidad = grupo.get('modalidad', 'PRESENCIAL')
    
    if modalidad == 'TELEFORMACION':
        horas_tele = horas_totales
        horas_pres = 0
    elif modalidad == 'PRESENCIAL':
        horas_pres = horas_totales
        horas_tele = 0
    else:  # MIXTA
        horas_pres = horas_totales // 2
        horas_tele = horas_totales - horas_pres
    
    datos_curso = [
        [Paragraph(f"Código AF / Grupo <b>{codigo_grupo}</b>", style_label),
         Paragraph(f"Durante los días <b>{fecha_inicio_str}</b> al <b>{fecha_fin_str}</b>", style_label)],
        
        [Paragraph(f"con una duración total de <b>{horas_totales}</b> horas en la modalidad formativa <b>Teleformación</b>", style_label),
         Paragraph("", style_label)],
        
        [Paragraph(f"<b>{horas_pres}</b> horas en la modalidad formativa <b>Presencial</b>", style_label),
         Paragraph("", style_label)]
    ]
    
    tabla_curso = Table(datos_curso, colWidths=[14*cm, 10*cm])
    tabla_curso.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_curso)
    elementos.append(Spacer(1, 0.5*cm))
    
    elementos.append(Paragraph("Contenidos impartidos (Ver dorso)", style_label))
    elementos.append(Spacer(1, 0.8*cm))
    
    # Pie de página con firma y fecha
    fecha_expedicion = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y') if fecha_fin else datetime.now().strftime('%d/%m/%Y')
    
    pie_datos = [
        [Paragraph("Firma y sello de la entidad responsable de<br/>impartir la formación", style_label),
         Paragraph(f"Fecha de expedición<br/><b>{fecha_expedicion}</b>", style_label),
         Paragraph("Firma del trabajador/a", style_label)]
    ]
    
    tabla_pie = Table(pie_datos, colWidths=[8*cm, 8*cm, 8*cm])
    tabla_pie.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
    ]))
    elementos.append(tabla_pie)
    
    # CARA B - Contenidos
    elementos.append(PageBreak())
    
    style_titulo_contenidos = ParagraphStyle('TituloContenidosFundae',
        fontSize=16,
        textColor=colors.HexColor("#003d7a"),
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        spaceAfter=15
    )
    
    elementos.append(Spacer(1, 1*cm))
    elementos.append(Paragraph("Contenidos impartidos:", style_titulo_contenidos))
    elementos.append(Spacer(1, 0.5*cm))
    
    contenidos = accion.get('contenidos', '')
    if contenidos and contenidos.strip():
        # Formatear contenidos con estilo de unidades didácticas
        contenidos_html = contenidos.replace('\n\n', '<br/><br/>').replace('\n', '<br/>')
        elementos.append(Paragraph(contenidos_html, style_contenidos))
    else:
        elementos.append(Paragraph("Los contenidos de este programa no han sido especificados.", style_contenidos))
    
    # Función para dibujar firma
    def dibujar_firma(canvas, doc, firma_url=firma_url):
        if firma_url:
            try:
                canvas.drawImage(
                    firma_url,
                    x=3*cm,
                    y=4*cm,
                    width=4*cm,
                    height=2*cm,
                    preserveAspectRatio=True,
                    mask="auto"
                )
            except Exception as e:
                print("Error dibujando firma:", e)
    
    doc.build(
        elementos,
        onFirstPage=lambda c, d: dibujar_firma(c, d, firma_url),
        canvasmaker=FundaeCanvas
    )
    buffer.seek(0)
    return buffer
# =========================
# REGISTRO DE PLANTILLAS
# =========================
PLANTILLAS_DISPONIBLES = {
    'clasica': {
        'nombre': 'Clásica',
        'descripcion': 'Diseño tradicional con borde decorativo y tipografía serif',
        'funcion': generar_diploma_pdf,
        'preview': '🎓 Estilo formal con marcos'
    },
    'moderna': {
        'nombre': 'Moderna',
        'descripcion': 'Diseño minimalista con tipografía sans-serif y colores neutros',
        'funcion': generar_diploma_moderno,
        'preview': '✨ Estilo limpio y contemporáneo'
    },
    'fundae': {
        'nombre': 'FUNDAE Oficial',
        'descripcion': 'Formato oficial FUNDAE con líneas decorativas y estructura reglamentaria',
        'funcion': generar_diploma_fundae,
        'preview': '📋 Cumplimiento normativo FUNDAE'
    }
}        
# =========================
# SERVICIO DE PLANTILLAS
# =========================
class PlantillasService:
    """Gestión de plantillas de diplomas por empresa."""
    
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
    
    def get_plantilla_activa(self, empresa_id: str) -> str:
        """Obtiene el código de la plantilla activa de una empresa."""
        try:
            result = self.supabase.table("empresas_plantillas_diplomas").select("codigo").eq(
                "empresa_id", empresa_id
            ).eq("activa", True).limit(1).execute()
            
            return result.data[0]["codigo"] if result.data else "clasica"
        except:
            return "clasica"
    
    def set_plantilla_activa(self, empresa_id: str, codigo_plantilla: str) -> bool:
        """Establece una plantilla como activa."""
        try:
            # Desactivar todas las plantillas de la empresa
            self.supabase.table("empresas_plantillas_diplomas").update({
                "activa": False
            }).eq("empresa_id", empresa_id).execute()
            
            # Buscar si ya existe registro para esta plantilla
            existing = self.supabase.table("empresas_plantillas_diplomas").select("id").eq(
                "empresa_id", empresa_id
            ).eq("codigo", codigo_plantilla).execute()
            
            if existing.data:
                # Activar existente
                self.supabase.table("empresas_plantillas_diplomas").update({
                    "activa": True
                }).eq("id", existing.data[0]["id"]).execute()
            else:
                # Crear nuevo
                self.supabase.table("empresas_plantillas_diplomas").insert({
                    "empresa_id": empresa_id,
                    "nombre": PLANTILLAS_DISPONIBLES[codigo_plantilla]["nombre"],
                    "codigo": codigo_plantilla,
                    "activa": True
                }).execute()
            
            return True
        except Exception as e:
            print(f"Error estableciendo plantilla: {e}")
            return False
# =========================
# EDITOR INTERACTIVO
# =========================
def mostrar_editor_diploma(participante, grupo, accion):
    st.markdown("### ✏️ Editor de Diploma")
    st.caption("Personaliza los datos antes de generar el diploma")
    
    datos_editados = {}
    
    with st.expander("👤 Datos del Participante", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            nombre_completo = st.text_input("Nombre completo",
                value=f"{participante.get('nombre', '')} {participante.get('apellidos', '')}".strip(),
                key="edit_nombre")
            datos_editados['nombre_completo'] = nombre_completo
        with col2:
            tipo_doc = st.selectbox("Tipo documento",
                ["DNI", "NIE", "PASAPORTE"],
                index=["DNI", "NIE", "PASAPORTE"].index(participante.get('tipo_documento', 'DNI')) if participante.get('tipo_documento') in ["DNI", "NIE", "PASAPORTE"] else 0,
                key="edit_tipo_doc")
            datos_editados['tipo_documento'] = tipo_doc
            num_doc = st.text_input("Número documento",
                value=participante.get('nif', ''), key="edit_nif")
            datos_editados['nif'] = num_doc
    
    with st.expander("📚 Datos del Curso", expanded=True):
        accion_nombre = st.text_area("Nombre del curso", value=accion.get('nombre', ''), height=80, key="edit_accion")
        datos_editados['accion_nombre'] = accion_nombre
        col1, col2 = st.columns(2)
        with col1:
            horas = st.number_input("Horas del curso", min_value=1, max_value=1000,
                value=int(accion.get('horas', 0) or accion.get('num_horas', 0) or 0), key="edit_horas")
            datos_editados['horas'] = horas
        with col2:
            modalidad = st.selectbox("Modalidad", ["PRESENCIAL", "TELEFORMACION", "MIXTA"],
                index=["PRESENCIAL", "TELEFORMACION", "MIXTA"].index(grupo.get('modalidad', 'PRESENCIAL')) if grupo.get('modalidad') in ["PRESENCIAL", "TELEFORMACION", "MIXTA"] else 0,
                key="edit_modalidad")
            datos_editados['modalidad'] = modalidad
    
    with st.expander("📅 Fechas del Curso", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio_val = grupo.get('fecha_inicio')
            fecha_inicio_val = pd.to_datetime(fecha_inicio_val).date() if fecha_inicio_val else date.today()
            fecha_inicio = st.date_input("Fecha inicio", value=fecha_inicio_val, key="edit_fecha_inicio")
            datos_editados['fecha_inicio'] = fecha_inicio
        with col2:
            fecha_fin_val = grupo.get('fecha_fin') or grupo.get('fecha_fin_prevista')
            fecha_fin_val = pd.to_datetime(fecha_fin_val).date() if fecha_fin_val else date.today()
            fecha_fin = st.date_input("Fecha fin", value=fecha_fin_val, key="edit_fecha_fin")
            datos_editados['fecha_fin'] = fecha_fin
    
    with st.expander("📝 Contenidos del Curso", expanded=False):
        contenidos = st.text_area("Contenidos (aparecerán en la cara B del diploma)",
            value=accion.get('contenidos', ''), height=200, key="edit_contenidos")
        datos_editados['contenidos'] = contenidos
    
    return datos_editados

# =========================
# FILTROS
# =========================
def mostrar_filtros(empresas_service, grupos_service, participantes_service, session_state):
    st.markdown("### 🔍 Filtros de Selección")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if session_state.role == "admin":
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            empresas_dict = {row["nombre"]: row["id"] for _, row in df_empresas.iterrows()}
            empresa_sel = st.selectbox("🏢 Empresa", ["Todas"] + list(empresas_dict.keys()))
            empresa_id = empresas_dict.get(empresa_sel) if empresa_sel != "Todas" else None
        else:
            empresa_id = session_state.user.get("empresa_id")
    
    with col2:
        años_disponibles = list(range(datetime.now().year, datetime.now().year - 10, -1))
        año_sel = st.selectbox("📅 Año", ["Todos"] + años_disponibles)
    
    with col3:
        df_grupos = grupos_service.get_grupos_completos()
        if empresa_id:
            df_grupos = df_grupos[df_grupos["empresa_id"] == empresa_id]
        if año_sel != "Todos":
            df_grupos = df_grupos[df_grupos["ano_inicio"] == año_sel]
        grupos_dict = {row["codigo_grupo"]: row["id"] for _, row in df_grupos.iterrows()}
        grupo_sel = st.selectbox("📚 Grupo", ["Todos"] + list(grupos_dict.keys()))
        grupo_id = grupos_dict.get(grupo_sel) if grupo_sel != "Todos" else None
    
    with col4:
        participante_buscar = st.text_input("👤 Buscar participante", placeholder="Nombre o NIF")
    
    return {
        "empresa_id": empresa_id,
        "año": año_sel if año_sel != "Todos" else None,
        "grupo_id": grupo_id,
        "participante_buscar": participante_buscar
    }

# =========================
# GESTIÓN DE FIRMAS
# =========================
def mostrar_gestion_firmas(firmas_service, empresa_id, session_state):
    """Interfaz para gestionar firma digital."""
    st.markdown("### ✍️ Firma Digital para Diplomas")
    
    firma_actual = firmas_service.get_firma_empresa(empresa_id)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if firma_actual and firma_actual.get("archivo_url"):
            st.image(firma_actual["archivo_url"], width=200, caption="Firma actual")
            
            if st.button("🗑️ Eliminar firma", use_container_width=True):
                if firmas_service.eliminar_firma(empresa_id):
                    st.success("✅ Firma eliminada")
                    st.rerun()
        else:
            st.info("📝 Sin firma configurada")
    
    with col2:
        st.markdown("**📤 Subir/Actualizar Firma**")
        archivo_firma = st.file_uploader(
            "Seleccionar imagen PNG",
            type=["png"],
            key=f"firma_{empresa_id}",
            help="Imagen de tu firma. Máximo 2MB. Fondo transparente recomendado."
        )
        if archivo_firma:
            st.image(archivo_firma, width=200, caption="Vista previa")
            if st.button("💾 Guardar firma", type="primary", use_container_width=True):
                if firmas_service.subir_firma(empresa_id, archivo_firma):
                    st.success("✅ Firma guardada correctamente")
                    st.rerun()
                    
# =========================
# GESTIÓN DE LOGOTIPOS
# =========================
def mostrar_gestion_logos(logos_service, empresa_id, session_state):
    """Interfaz para gestionar logotipo de empresa."""
    st.markdown("### 🏢 Logotipo de Empresa para Diplomas")
    
    logo_actual = logos_service.get_logo_empresa(empresa_id)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if logo_actual and logo_actual.get("archivo_url"):
            st.image(logo_actual["archivo_url"], width=200, caption="Logotipo actual")
            
            if st.button("🗑️ Eliminar logotipo", use_container_width=True, key="eliminar_logo"):
                if logos_service.eliminar_logo(empresa_id):
                    st.success("✅ Logotipo eliminado")
                    st.rerun()
        else:
            st.info("🖼️ Sin logotipo configurado")
    
    with col2:
        st.markdown("**📤 Subir/Actualizar Logotipo**")
        archivo_logo = st.file_uploader(
            "Seleccionar imagen PNG",
            type=["png"],
            key=f"logo_{empresa_id}",
            help="Logotipo de tu empresa. Máximo 5MB. Fondo transparente recomendado."
        )
        if archivo_logo:
            st.image(archivo_logo, width=200, caption="Vista previa")
            if st.button("💾 Guardar logotipo", type="primary", use_container_width=True, key="guardar_logo"):
                if logos_service.subir_logo(empresa_id, archivo_logo):
                    st.success("✅ Logotipo guardado correctamente")
                    st.rerun()
                    
# =========================
# GESTIÓN DE PLANTILLAS
# =========================
def mostrar_selector_plantillas(plantillas_service, empresa_id):
    """Interfaz para seleccionar plantilla de diploma."""
    st.markdown("### 🎨 Seleccionar Plantilla de Diploma")
    st.caption("Elige el diseño que mejor se adapte a tu marca")
    
    plantilla_activa_codigo = plantillas_service.get_plantilla_activa(empresa_id)
    
    cols = st.columns(len(PLANTILLAS_DISPONIBLES))
    
    for idx, (codigo, plantilla) in enumerate(PLANTILLAS_DISPONIBLES.items()):
        with cols[idx]:
            es_activa = plantilla_activa_codigo == codigo
            
            # Contenedor con borde si está activa
            if es_activa:
                st.success(f"✅ **{plantilla['nombre']}** (Activa)")
            else:
                st.markdown(f"**{plantilla['nombre']}**")
            
            st.caption(plantilla['descripcion'])
            st.info(plantilla['preview'])
            
            if not es_activa:
                if st.button(f"Usar {plantilla['nombre']}", key=f"btn_plantilla_{codigo}", use_container_width=True):
                    if plantillas_service.set_plantilla_activa(empresa_id, codigo):
                        st.success(f"Plantilla '{plantilla['nombre']}' activada")
                        st.rerun()
            else:
                st.button("En uso", disabled=True, use_container_width=True) 
                
# =========================
# MAIN
# =========================
def render(supabase, session_state):
    st.title("📜 Generador de Diplomas Profesional")
    st.caption("Generación de diplomas PDF con editor interactivo y previsualización")
    
    if not REPORTLAB_AVAILABLE:
        st.error("⚠️ reportlab no está instalado. Ejecuta: pip install reportlab")
        return
    
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para generar diplomas")
        return
    
    empresas_service = get_empresas_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    participantes_service = get_participantes_service(supabase, session_state)
    firmas_service = FirmasService(supabase, session_state)
    logos_service = LogosService(supabase, session_state)
    plantillas_service = PlantillasService(supabase, session_state)
    
    tabs = st.tabs([
        "📜 Generar Diplomas",
        "✏️ Gestionar Firma",
        "🏢 Gestionar Logotipo",
        "🎨 Plantillas"
    ])
    
    # --- TAB 0: GENERAR DIPLOMAS ---
    with tabs[0]:
        filtros = mostrar_filtros(empresas_service, grupos_service, participantes_service, session_state)
        st.divider()
        
        df_participantes = participantes_service.get_participantes_completos()
        
        if filtros["empresa_id"]:
            df_participantes = df_participantes[df_participantes["empresa_id"] == filtros["empresa_id"]]
        if filtros["grupo_id"]:
            participantes_grupo = participantes_service.supabase.table("participantes_grupos").select(
                "participante_id"
            ).eq("grupo_id", filtros["grupo_id"]).execute()
            ids_grupo = [p["participante_id"] for p in (participantes_grupo.data or [])]
            df_participantes = df_participantes[df_participantes["id"].isin(ids_grupo)]
        if filtros["participante_buscar"]:
            buscar = filtros["participante_buscar"].lower()
            df_participantes = df_participantes[
                df_participantes["nombre"].str.lower().str.contains(buscar, na=False) |
                df_participantes["apellidos"].str.lower().str.contains(buscar, na=False) |
                df_participantes["nif"].str.lower().str.contains(buscar, na=False)
            ]
        
        if df_participantes.empty:
            st.info("📋 No se encontraron participantes con los filtros aplicados")
            return
        
        st.success(f"✅ {len(df_participantes)} participante(s) encontrado(s)")
        
        participante_sel = st.selectbox(
            "Seleccionar participante",
            df_participantes.apply(lambda x: f"{x['nombre']} {x['apellidos']} - {x['nif']}", axis=1).tolist()
        )
        participante_idx = df_participantes.apply(
            lambda x: f"{x['nombre']} {x['apellidos']} - {x['nif']}", axis=1
        ).tolist().index(participante_sel)
        participante = df_participantes.iloc[participante_idx].to_dict()
        
        grupos_part = participantes_service.get_grupos_de_participante(participante["id"])
        if grupos_part.empty:
            st.warning("⚠️ Este participante no está asignado a ningún grupo")
            return
        
        grupo_sel = st.selectbox(
            "Seleccionar grupo/curso",
            grupos_part.apply(lambda x: f"{x['codigo_grupo']} - {x['accion_nombre']}", axis=1).tolist()
        )
        grupo_idx = grupos_part.apply(
            lambda x: f"{x['codigo_grupo']} - {x['accion_nombre']}", axis=1
        ).tolist().index(grupo_sel)
        grupo = grupos_part.iloc[grupo_idx].to_dict()
        
        grupo_completo = grupos_service.supabase.table("grupos").select("*").eq(
            "id", grupo["grupo_id"]
        ).execute().data[0]
        accion_completa = grupos_service.supabase.table("acciones_formativas").select("*").eq(
            "id", grupo_completo["accion_formativa_id"]
        ).execute().data[0]
        
        # Obtener empresa_id, firma Y logo
        empresa_id = participante.get("empresa_id")
        
        firma = firmas_service.get_firma_empresa(empresa_id)
        firma_url = firma["archivo_url"] if firma else None

        logo = logos_service.get_logo_empresa(empresa_id)
        logo_url = logo["archivo_url"] if logo else None
    
        plantilla_codigo = plantillas_service.get_plantilla_activa(empresa_id)
        plantilla_info = PLANTILLAS_DISPONIBLES[plantilla_codigo]
        
        st.info(f"🎨 Plantilla: **{plantilla_info['nombre']}**")
        st.divider()
        
        datos_personalizados = mostrar_editor_diploma(participante, grupo_completo, accion_completa)
        st.divider()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("👁️ Previsualizar", type="secondary", use_container_width=True):
                with st.spinner("Generando previsualización..."):
                    # ✅ AÑADIR logo_url como parámetro
                    pdf_buffer = generar_diploma_pdf(
                        participante, grupo_completo, accion_completa,
                        firma_url, logo_url, datos_personalizados
                    )
                    if pdf_buffer:
                        st.success("✅ Previsualización generada")
                        st.download_button(
                            "📥 Descargar Previsualización",
                            data=pdf_buffer,
                            file_name=f"preview_{participante['nif']}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
        
        with col2:
            if st.button("🔄 Restablecer", use_container_width=True):
                for key in list(st.session_state.keys()):
                    if key.startswith('edit_'):
                        del st.session_state[key]
                st.rerun()
        
        with col3:
            if st.button("📜 Generar Diploma Final", type="primary", use_container_width=True):
                with st.spinner("Generando diploma final..."):
                    # ✅ AÑADIR logo_url como parámetro
                    pdf_buffer = generar_diploma_pdf(
                        participante, grupo_completo, accion_completa,
                        firma_url, logo_url, datos_personalizados
                    )
        
                    if pdf_buffer:
                        # Validar si ya existe diploma
                        diploma_existente = supabase.table("diplomas").select("*").eq(
                            "participante_id", participante["id"]
                        ).eq("grupo_id", grupo_completo["id"]).execute()
        
                        if diploma_existente.data:
                            st.warning("⚠️ Este participante ya tiene un diploma generado para este grupo.")
                            st.info("Puedes descargarlo de todos modos o eliminarlo desde Participantes > Diplomas")
                        
                        # Preparar datos para la ruta
                        codigo_accion = accion_completa.get("codigo_accion", "sin_codigo")
                        accion_id = accion_completa.get("id", "sin_id")
                        empresa_id_diploma = grupo_completo.get("empresa_id", "sin_empresa")
                        ano_inicio = grupo_completo.get("ano_inicio", datetime.now().year)
                        grupo_id_completo = grupo_completo.get("id")
                        
                        grupo_id_corto = str(grupo_id_completo)[-8:] if grupo_id_completo else "sin_id"
                        grupo_numero = grupo_completo.get("codigo_grupo", "0").split("_")[-1] if grupo_completo.get("codigo_grupo") else "0"
                        
                        nif = participante.get("nif", "sin_nif").replace(" ", "_")
                        timestamp = int(datetime.now().timestamp())
                        file_name = f"diploma_{nif}_{timestamp}.pdf"
                        
                        file_path = (
                            f"diplomas/"
                            f"gestora_{empresa_id_diploma}/"
                            f"ano_{ano_inicio}/"
                            f"accion_{codigo_accion}_{accion_id}/"
                            f"grupo_{grupo_numero}_{grupo_id_corto}/"
                            f"{file_name}"
                        )
        
                        # Subir al bucket (solo si no existe)
                        if not diploma_existente.data:
                            try:
                                supabase.storage.from_("diplomas").upload(
                                    file_path,
                                    pdf_buffer.getvalue(),
                                    {"content-type": "application/pdf"}
                                )
        
                                url = supabase.storage.from_("diplomas").get_public_url(file_path)
        
                                # Registrar en BD
                                supabase.table("diplomas").insert({
                                    "participante_id": participante["id"],
                                    "grupo_id": grupo_completo["id"],
                                    "url": url,
                                    "archivo_nombre": file_name,
                                    "fecha_subida": datetime.now().isoformat()
                                }).execute()
                                
                                st.success("✅ Diploma generado y registrado correctamente")
                            
                            except Exception as e:
                                st.error(f"❌ Error subiendo diploma: {e}")
                        
                        # Siempre ofrecer descarga
                        st.download_button(
                            "📥 Descargar Diploma",
                            data=pdf_buffer,
                            file_name=file_name,
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )

    # --- TAB 1: GESTIONAR FIRMAS ---
    with tabs[1]:
        if session_state.role == "admin":
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            empresas_dict = {row["nombre"]: row["id"] for _, row in df_empresas.iterrows()}
            empresa_firma_sel = st.selectbox("Seleccionar empresa", list(empresas_dict.keys()))
            empresa_firma_id = empresas_dict[empresa_firma_sel]
        else:
            empresa_firma_id = session_state.user.get("empresa_id")
        
        mostrar_gestion_firmas(firmas_service, empresa_firma_id, session_state)
        
        st.divider()
        with st.expander("💡 Consejos para una buena firma"):
            st.markdown("""
            **Recomendaciones para la imagen de firma:**
            1. **Formato PNG** con fondo transparente
            2. **Resolución**: mínimo 300 DPI
            3. **Tamaño recomendado**: 500x200 píxeles
            4. **Color**: Azul oscuro o negro
            5. **Peso máximo**: 2MB
            """)
            
    # --- TAB 2: GESTIONAR LOGOTIPOS (NUEVO) ---
    with tabs[2]:
        if session_state.role == "admin":
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            empresas_dict = {row["nombre"]: row["id"] for _, row in df_empresas.iterrows()}
            empresa_logo_sel = st.selectbox("Seleccionar empresa", list(empresas_dict.keys()), key="sel_empresa_logo")
            empresa_logo_id = empresas_dict[empresa_logo_sel]
        else:
            empresa_logo_id = session_state.user.get("empresa_id")
        
        mostrar_gestion_logos(logos_service, empresa_logo_id, session_state)
        
        st.divider()
        with st.expander("💡 Consejos para un buen logotipo"):
            st.markdown("""
            **Recomendaciones para la imagen del logotipo:**
            1. **Formato PNG** con fondo transparente
            2. **Resolución**: mínimo 300 DPI
            3. **Tamaño recomendado**: 1000x400 píxeles (horizontal)
            4. **Orientación**: Horizontal preferiblemente
            5. **Peso máximo**: 5MB
            6. **Colores**: Alta calidad, evitar pixelación
            """)
    # --- TAB 3: PLANTILLAS ---
    with tabs[3]:
        if session_state.role == "admin":
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            empresas_dict = {row["nombre"]: row["id"] for _, row in df_empresas.iterrows()}
            empresa_plantilla_sel = st.selectbox("Seleccionar empresa", list(empresas_dict.keys()), key="sel_empresa_plantilla")
            empresa_plantilla_id = empresas_dict[empresa_plantilla_sel]
        else:
            empresa_plantilla_id = session_state.user.get("empresa_id")
        
        mostrar_selector_plantillas(plantillas_service, empresa_plantilla_id)
