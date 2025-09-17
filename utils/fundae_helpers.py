# =========================
# FUNCIONES DE APOYO PARA INTEGRACIÓN FUNDAE
# =========================

def validar_tipo_documento_nif(nif, tipo_documento):
    """
    Valida que el tipo de documento coincida con el formato del NIF.
    
    Args:
        nif (str): El documento de identidad
        tipo_documento (int): 10=NIF, 20=Pasaporte, 60=NIE
    
    Returns:
        tuple: (es_valido, mensaje_error)
    """
    import re
    
    if not nif or not tipo_documento:
        return False, "NIF y tipo de documento son obligatorios"
    
    nif = nif.upper().strip()
    
    if tipo_documento == 10:  # NIF
        patron = r'^[0-9]{8}[A-Z]$'
        if not re.match(patron, nif):
            return False, "NIF debe tener formato 12345678A"
    
    elif tipo_documento == 60:  # NIE
        patron = r'^[XYZ][0-9]{7}[A-Z]$'
        if not re.match(patron, nif):
            return False, "NIE debe tener formato X1234567A"
    
    elif tipo_documento == 20:  # Pasaporte
        # Los pasaportes pueden tener varios formatos
        if len(nif) < 6 or len(nif) > 15:
            return False, "Pasaporte debe tener entre 6 y 15 caracteres"
    
    return True, ""


def crear_horario_estructurado(grupo_id, horario_str, horas_accion, supabase):
    """
    Convierte el horario de texto actual a formato estructurado FUNDAE.
    
    Args:
        grupo_id: ID del grupo
        horario_str: String de horario actual "Mañana: 09:00-13:00 | Tarde: 15:00-18:00 | Días: L-M-X-J-V"
        horas_accion: Horas totales de la acción formativa
        supabase: Cliente de Supabase
    """
    try:
        if not horario_str:
            return False
        
        # Parsear horario actual
        from grupos import parsear_horario_fundae
        m_ini, m_fin, t_ini, t_fin, dias = parsear_horario_fundae(horario_str)
        
        # Calcular horas totales por día
        horas_dia = 0
        if m_ini and m_fin:
            h_inicio = int(m_ini.split(':')[0]) + int(m_ini.split(':')[1])/60
            h_fin = int(m_fin.split(':')[0]) + int(m_fin.split(':')[1])/60
            horas_dia += (h_fin - h_inicio)
        
        if t_ini and t_fin:
            h_inicio = int(t_ini.split(':')[0]) + int(t_ini.split(':')[1])/60
            h_fin = int(t_fin.split(':')[0]) + int(t_fin.split(':')[1])/60
            horas_dia += (h_fin - h_inicio)
        
        # Crear registro en grupos_horarios
        datos_horario = {
            "grupo_id": grupo_id,
            "horas_totales": float(horas_accion),
            "hora_inicio_tramo1": m_ini if m_ini else None,
            "hora_fin_tramo1": m_fin if m_fin else None,
            "hora_inicio_tramo2": t_ini if t_ini else None,
            "hora_fin_tramo2": t_fin if t_fin else None,
            "dias": "".join(dias) if dias else ""
        }
        
        # Eliminar horario anterior si existe
        supabase.table("grupos_horarios").delete().eq("grupo_id", grupo_id).execute()
        
        # Insertar nuevo horario
        result = supabase.table("grupos_horarios").insert(datos_horario).execute()
        return result.data is not None
        
    except Exception as e:
        print(f"Error al crear horario estructurado: {e}")
        return False


def actualizar_tipo_documento_tutores(supabase):
    """
    Función de migración para calcular tipo_documento basado en el NIF existente.
    Ejecutar una sola vez para actualizar tutores existentes.
    """
    try:
        # Obtener todos los tutores
        tutores = supabase.table("tutores").select("id, nif").execute()
        
        for tutor in tutores.data or []:
            if not tutor.get("nif"):
                continue
                
            nif = tutor["nif"].upper().strip()
            tipo_documento = None
            
            # Detectar tipo según formato
            import re
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
                
        return True
        
    except Exception as e:
        print(f"Error en migración de tipos de documento: {e}")
        return False


def validar_campos_fundae_grupo(datos_grupo):
    """
    Validación completa de campos FUNDAE para un grupo.
    
    Args:
        datos_grupo (dict): Datos del grupo a validar
        
    Returns:
        tuple: (es_valido, lista_errores)
    """
    errores = []
    
    # Campos básicos obligatorios
    campos_obligatorios = {
        "codigo_grupo": "Código del grupo",
        "fecha_inicio": "Fecha de inicio",
        "fecha_fin_prevista": "Fecha fin prevista", 
        "localidad": "Localidad",
        "responsable": "Responsable del grupo",
        "telefono_contacto": "Teléfono de contacto",
        "n_participantes_previstos": "Número de participantes"
    }
    
    for campo, nombre in campos_obligatorios.items():
        if not datos_grupo.get(campo):
            errores.append(f"{nombre} es obligatorio")
    
    # Validar formato de teléfono
    telefono = datos_grupo.get("telefono_contacto", "")
    if telefono and not re.match(r'^\d{9,12}$', telefono.replace(' ', '').replace('-', '')):
        errores.append("Teléfono de contacto debe tener entre 9 y 12 dígitos")
    
    # Validar participantes
    try:
        n_part = int(datos_grupo.get("n_participantes_previstos", 0))
        if n_part < 1 or n_part > 9999:
            errores.append("Participantes previstos debe estar entre 1 y 9999")
    except:
        errores.append("Participantes previstos debe ser un número")
    
    # Validar modalidad
    modalidad = datos_grupo.get("modalidad")
    if modalidad and modalidad not in ["PRESENCIAL", "TELEFORMACION", "MIXTA"]:
        errores.append("Modalidad debe ser PRESENCIAL, TELEFORMACION o MIXTA")
    
    return len(errores) == 0, errores


def preparar_datos_xml_inicio_grupo(grupo_id, supabase):
    """
    Prepara todos los datos necesarios para generar el XML de inicio de grupo FUNDAE.
    
    Args:
        grupo_id: ID del grupo
        supabase: Cliente de Supabase
        
    Returns:
        dict: Datos estructurados para el XML o None si hay errores
    """
    try:
        # 1. Datos del grupo con acción formativa
        grupo_query = supabase.table("grupos").select("""
            *, 
            accion_formativa:acciones_formativas(codigo, denominacion, num_horas)
        """).eq("id", grupo_id).execute()
        
        if not grupo_query.data:
            return None
            
        grupo = grupo_query.data[0]
        
        # 2. Horarios estructurados
        horarios = supabase.table("grupos_horarios").select("*").eq("grupo_id", grupo_id).execute()
        horario = horarios.data[0] if horarios.data else None
        
        # 3. Tutores del grupo
        tutores_query = supabase.table("tutores_grupos").select("""
            *, 
            tutor:tutores(*)
        """).eq("grupo_id", grupo_id).execute()
        
        tutores = []
        for tg in tutores_query.data or []:
            if tg.get("tutor"):
                tutores.append(tg["tutor"])
        
        # 4. Empresas participantes
        empresas_query = supabase.table("empresas_grupos").select("""
            *, 
            empresa:empresas(cif, nombre)
        """).eq("grupo_id", grupo_id).execute()
        
        empresas = []
        for eg in empresas_query.data or []:
            if eg.get("empresa"):
                empresas.append(eg["empresa"])
        
        # 5. Centro gestor (si existe)
        centro_query = supabase.table("centros_gestores_grupos").select("""
            centro_gestor:centros_gestores(*)
        """).eq("grupo_id", grupo_id).execute()
        
        centro = None
        if centro_query.data and centro_query.data[0].get("centro_gestor"):
            centro = centro_query.data[0]["centro_gestor"]
        
        # Estructurar datos para XML
        datos_xml = {
            "grupo": grupo,
            "accion_formativa": grupo.get("accion_formativa"),
            "horario": horario,
            "tutores": tutores,
            "empresas": empresas,
            "centro_gestor": centro
        }
        
        return datos_xml
        
    except Exception as e:
        print(f"Error al preparar datos XML: {e}")
        return None


def generar_calendario_automatico(grupo_id, fecha_inicio, fecha_fin, horario, dias_semana, supabase):
    """
    Genera automáticamente el calendario de impartición basado en las fechas y horarios.
    
    Args:
        grupo_id: ID del grupo
        fecha_inicio: Fecha de inicio del grupo
        fecha_fin: Fecha de fin del grupo  
        horario: Datos de horario estructurado
        dias_semana: Lista de días (L, M, X, J, V, S, D)
        supabase: Cliente de Supabase
    """
    try:
        from datetime import datetime, timedelta
        
        # Mapear días
        dias_map = {"L": 0, "M": 1, "X": 2, "J": 3, "V": 4, "S": 5, "D": 6}
        dias_nums = [dias_map[d] for d in dias_semana if d in dias_map]
        
        if not dias_nums:
            return False
        
        # Generar fechas de impartición
        fecha_actual = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
        fecha_limite = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
        
        fechas_imparticion = []
        
        while fecha_actual <= fecha_limite:
            if fecha_actual.weekday() in dias_nums:
                fecha_calendario = {
                    "grupo_id": grupo_id,
                    "fecha_imparticion": fecha_actual.isoformat(),
                    "horario_inicio_tramo1": horario.get("hora_inicio_tramo1"),
                    "horario_fin_tramo1": horario.get("hora_fin_tramo1"),
                    "horario_inicio_tramo2": horario.get("hora_inicio_tramo2"),
                    "horario_fin_tramo2": horario.get("hora_fin_tramo2")
                }
                fechas_imparticion.append(fecha_calendario)
            
            fecha_actual += timedelta(days=1)
        
        if fechas_imparticion:
            # Eliminar calendario anterior
            supabase.table("grupos_calendario").delete().eq("grupo_id", grupo_id).execute()
            
            # Insertar nuevo calendario (en lotes si es necesario)
            if len(fechas_imparticion) <= 100:
                supabase.table("grupos_calendario").insert(fechas_imparticion).execute()
            else:
                # Insertar en lotes de 100
                for i in range(0, len(fechas_imparticion), 100):
                    lote = fechas_imparticion[i:i+100]
                    supabase.table("grupos_calendario").insert(lote).execute()
        
        return True
        
    except Exception as e:
        print(f"Error al generar calendario: {e}")
        return False


# =========================
# FUNCIONES DE VALIDACIÓN ESPECÍFICA FUNDAE
# =========================

def validar_tutor_fundae(tutor_data):
    """Validaciones específicas FUNDAE para tutores."""
    errores = []
    
    # Campos obligatorios
    if not tutor_data.get("nombre"):
        errores.append("Nombre es obligatorio")
    if not tutor_data.get("apellidos"):
        errores.append("Apellidos son obligatorios")
    if not tutor_data.get("nif"):
        errores.append("NIF/documento es obligatorio para FUNDAE")
    if not tutor_data.get("email"):
        errores.append("Email es obligatorio")
    if not tutor_data.get("telefono"):
        errores.append("Teléfono es obligatorio")
    if not tutor_data.get("tipo_documento"):
        errores.append("Tipo de documento es obligatorio")
    
    # Validar coherencia NIF-tipo
    if tutor_data.get("nif") and tutor_data.get("tipo_documento"):
        es_valido, error = validar_tipo_documento_nif(
            tutor_data["nif"], 
            tutor_data["tipo_documento"]
        )
        if not es_valido:
            errores.append(error)
    
    # Validar teléfono
    telefono = tutor_data.get("telefono", "")
    if telefono and not re.match(r'^\d{9,12}$', telefono.replace(' ', '').replace('-', '')):
        errores.append("Teléfono debe tener entre 9 y 12 dígitos")
    
    return len(errores) == 0, errores


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
            horas_accion = 0
            
            if grupo.get("accion_formativa"):
                horas_accion = grupo["accion_formativa"].get("num_horas", 0)
            
            if crear_horario_estructurado(grupo["id"], horario_str, horas_accion, supabase):
                migrados += 1
            else:
                errores += 1
        
        return migrados, errores
        
    except Exception as e:
        print(f"Error en migración de horarios: {e}")
        return 0, 1
