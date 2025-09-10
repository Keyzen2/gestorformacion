def generar_xml_accion_formativa(accion, namespace="http://www.fundae.es/esquemas"):
    """
    Genera XML de acción formativa para FUNDAE con el namespace correcto
    """
    from lxml import etree
    
    # Definir namespaces
    nsmap = {
        None: namespace,  # Default namespace
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }
    
    # Crear elemento raíz con el namespace correcto
    root = etree.Element(
        "ACCIONES_FORMATIVAS",  # Sin prefijo de namespace en el nombre
        nsmap=nsmap
    )
    
    # Añadir atributo schemaLocation si es necesario
    root.set(
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
        f"{namespace} AAFF_Inicio.xsd"
    )
    
    # Crear estructura del XML
    accion_elem = etree.SubElement(root, "ACCION_FORMATIVA")
    
    # Añadir elementos obligatorios
    etree.SubElement(accion_elem, "CODIGO_ACCION").text = str(accion.get('codigo', ''))
    etree.SubElement(accion_elem, "DENOMINACION").text = str(accion.get('denominacion', ''))
    etree.SubElement(accion_elem, "MODALIDAD").text = str(accion.get('modalidad', 'PRESENCIAL'))
    etree.SubElement(accion_elem, "HORAS").text = str(accion.get('horas', 0))
    
    # Elementos opcionales
    if accion.get('area_profesional'):
        etree.SubElement(accion_elem, "AREA_PROFESIONAL").text = str(accion['area_profesional'])
    
    if accion.get('fecha_inicio'):
        etree.SubElement(accion_elem, "FECHA_INICIO").text = str(accion['fecha_inicio'])
    
    if accion.get('fecha_fin'):
        etree.SubElement(accion_elem, "FECHA_FIN").text = str(accion['fecha_fin'])
    
    if accion.get('contenidos'):
        etree.SubElement(accion_elem, "CONTENIDOS").text = str(accion['contenidos'])
    
    # Convertir a string con formato bonito
    xml_string = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding='UTF-8'
    )
    
    return xml_string.decode('utf-8')


def generar_xml_inicio_grupo(grupo, participantes, namespace="http://www.fundae.es/esquemas"):
    """
    Genera XML de inicio de grupo para FUNDAE
    """
    from lxml import etree
    
    nsmap = {
        None: namespace,
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }
    
    root = etree.Element(
        "INICIO_GRUPOS",
        nsmap=nsmap
    )
    
    root.set(
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
        f"{namespace} InicioGrupos_Organizadora.xsd"
    )
    
    # Información del grupo
    grupo_elem = etree.SubElement(root, "GRUPO")
    
    etree.SubElement(grupo_elem, "CODIGO_GRUPO").text = str(grupo.get('codigo_grupo', ''))
    etree.SubElement(grupo_elem, "FECHA_INICIO").text = str(grupo.get('fecha_inicio', ''))
    etree.SubElement(grupo_elem, "FECHA_FIN").text = str(grupo.get('fecha_fin', ''))
    etree.SubElement(grupo_elem, "MODALIDAD").text = str(grupo.get('modalidad', 'PRESENCIAL'))
    
    if grupo.get('horario'):
        etree.SubElement(grupo_elem, "HORARIO").text = str(grupo['horario'])
    
    if grupo.get('lugar_imparticion'):
        etree.SubElement(grupo_elem, "LUGAR_IMPARTICION").text = str(grupo['lugar_imparticion'])
    
    # Añadir participantes
    if participantes:
        participantes_elem = etree.SubElement(grupo_elem, "PARTICIPANTES")
        
        for p in participantes:
            part_elem = etree.SubElement(participantes_elem, "PARTICIPANTE")
            
            etree.SubElement(part_elem, "DNI").text = str(p.get('dni', ''))
            etree.SubElement(part_elem, "NOMBRE").text = str(p.get('nombre', ''))
            etree.SubElement(part_elem, "APELLIDOS").text = str(p.get('apellidos', ''))
            
            if p.get('email'):
                etree.SubElement(part_elem, "EMAIL").text = str(p['email'])
            
            if p.get('telefono'):
                etree.SubElement(part_elem, "TELEFONO").text = str(p['telefono'])
    
    xml_string = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding='UTF-8'
    )
    
    return xml_string.decode('utf-8')


def generar_xml_finalizacion_grupo(grupo, participantes, namespace="http://www.fundae.es/esquemas"):
    """
    Genera XML de finalización de grupo para FUNDAE
    """
    from lxml import etree
    
    nsmap = {
        None: namespace,
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }
    
    root = etree.Element(
        "FINALIZACION_GRUPOS",
        nsmap=nsmap
    )
    
    root.set(
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
        f"{namespace} FinalizacionGrupo_Organizadora.xsd"
    )
    
    # Información del grupo
    grupo_elem = etree.SubElement(root, "GRUPO")
    
    etree.SubElement(grupo_elem, "CODIGO_GRUPO").text = str(grupo.get('codigo_grupo', ''))
    etree.SubElement(grupo_elem, "FECHA_FINALIZACION").text = str(grupo.get('fecha_fin', ''))
    
    # Resultados de participantes
    if participantes:
        resultados_elem = etree.SubElement(grupo_elem, "RESULTADOS")
        
        for p in participantes:
            part_elem = etree.SubElement(resultados_elem, "PARTICIPANTE")
            
            etree.SubElement(part_elem, "DNI").text = str(p.get('dni', ''))
            etree.SubElement(part_elem, "NOMBRE").text = str(p.get('nombre', ''))
            etree.SubElement(part_elem, "APELLIDOS").text = str(p.get('apellidos', ''))
            
            # Resultado: APTO o NO APTO
            resultado = p.get('resultado', 'NO APTO')
            if resultado not in ['APTO', 'NO APTO']:
                resultado = 'NO APTO'
            etree.SubElement(part_elem, "RESULTADO").text = resultado
            
            # Horas realizadas
            etree.SubElement(part_elem, "HORAS_REALIZADAS").text = str(p.get('horas_realizadas', 0))
    
    xml_string = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding='UTF-8'
    )
    
    return xml_string.decode('utf-8')


def validar_xml(xml_content, xsd_url):
    """
    Valida un XML contra un esquema XSD desde una URL
    """
    from lxml import etree
    import requests
    
    try:
        # Descargar el XSD
        response = requests.get(xsd_url, timeout=10)
        response.raise_for_status()
        
        # Parsear el XSD
        xsd_doc = etree.fromstring(response.content)
        xsd_schema = etree.XMLSchema(xsd_doc)
        
        # Parsear el XML
        xml_doc = etree.fromstring(xml_content.encode('utf-8'))
        
        # Validar
        es_valido = xsd_schema.validate(xml_doc)
        
        if es_valido:
            return True, []
        else:
            # Obtener errores
            errores = []
            for error in xsd_schema.error_log:
                errores.append(f"Línea {error.line}: {error.message}")
            return False, errores
            
    except requests.exceptions.RequestException as e:
        return False, [f"Error al descargar esquema XSD: {str(e)}"]
    except etree.XMLSyntaxError as e:
        return False, [f"Error de sintaxis XML: {str(e)}"]
    except Exception as e:
        return False, [f"Error de validación: {str(e)}"]
