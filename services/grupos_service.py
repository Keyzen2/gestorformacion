import streamlit as st
import pandas as pd
from datetime import datetime, time, date
from typing import Dict, Any, Tuple, List, Optional
import re


class GruposService:
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
        self.rol = session_state.role
        self.empresa_id = session_state.user.get("empresa_id")
        self.user_id = session_state.user.get("id")

    def _apply_empresa_filter(self, query, table_name: str, empresa_field: str = "empresa_id"):
        """Aplica filtro de empresa según el rol."""
        if self.rol == "gestor" and self.empresa_id:
            return query.eq(empresa_field, self.empresa_id)
        return query

    def _handle_query_error(self, operation: str, error: Exception) -> pd.DataFrame:
        """Manejo centralizado de errores en consultas."""
        st.error(f"Error en {operation}: {error}")
        return pd.DataFrame()

    def can_modify_data(self) -> bool:
        """Determina si el rol puede modificar datos (crear/editar/eliminar)."""
        return self.rol in ["admin", "gestor"]

    # =========================
    # VALIDACIONES FUNDAE
    # =========================

    def validar_grupo_fundae(self, datos_grupo: Dict[str, Any], tipo_xml: str = "inicio") -> Tuple[bool, List[str]]:
        """Valida que un grupo cumpla con los requisitos FUNDAE para generar XML."""
        errores = []
        
        # Campos obligatorios para XML de inicio
        campos_obligatorios = {
            "fecha_inicio": "Fecha de inicio", 
            "fecha_fin_prevista": "Fecha fin prevista",
            "horario": "Horario",
            "localidad": "Localidad",
            "n_participantes_previstos": "Participantes previstos"
        }
        
        # Verificar campos obligatorios
        for campo, nombre in campos_obligatorios.items():
            valor = datos_grupo.get(campo)
            if not valor:
                errores.append(f"{nombre} es obligatorio para FUNDAE")
        
        # Validar modalidad FUNDAE
        modalidad = datos_grupo.get("modalidad")
        if modalidad and modalidad not in ["PRESENCIAL", "TELEFORMACION", "MIXTA"]:
            errores.append("Modalidad debe ser PRESENCIAL, TELEFORMACION o MIXTA")
        
        # Validar participantes
        participantes = datos_grupo.get("n_participantes_previstos")
        if participantes:
            try:
                num_part = int(participantes)
                if num_part < 1 or num_part > 30:
                    errores.append("Participantes previstos debe estar entre 1 y 30")
            except (ValueError, TypeError):
                errores.append("Participantes previstos debe ser un número")
        
        # Validar horario FUNDAE
        horario = datos_grupo.get("horario")
        if horario:
            es_valido_horario, error_horario = self.validar_horario_fundae(horario)
            if not es_valido_horario:
                errores.append(f"Horario: {error_horario}")
        
        # Validaciones específicas de finalización
        if tipo_xml == "finalizacion":
            campos_finalizacion = {
                "fecha_fin": "Fecha de finalización real",
                "n_participantes_finalizados": "Participantes finalizados",
                "n_aptos": "Número de aptos",
                "n_no_aptos": "Número de no aptos"
            }
            
            for campo, nombre in campos_finalizacion.items():
                valor = datos_grupo.get(campo)
                if valor is None or valor == "":
                    errores.append(f"{nombre} es obligatorio para finalización FUNDAE")
            
            # Validar coherencia de participantes finalizados
            try:
                finalizados = int(datos_grupo.get("n_participantes_finalizados", 0))
                aptos = int(datos_grupo.get("n_aptos", 0))
                no_aptos = int(datos_grupo.get("n_no_aptos", 0))
                
                if aptos + no_aptos != finalizados:
                    errores.append("La suma de aptos + no aptos debe igual participantes finalizados")
                    
                if finalizados < 0 or aptos < 0 or no_aptos < 0:
                    errores.append("Los números de participantes no pueden ser negativos")
                    
            except (ValueError, TypeError):
                errores.append("Los campos de participantes deben ser números enteros")
            
            # Validar fechas
            fecha_inicio = datos_grupo.get("fecha_inicio")
            fecha_fin = datos_grupo.get("fecha_fin")
            
            if fecha_inicio and fecha_fin:
                try:
                    if isinstance(fecha_inicio, str):
                        inicio = datetime.fromisoformat(fecha_inicio.replace('Z', '+00:00'))
                    else:
                        inicio = fecha_inicio
                        
                    if isinstance(fecha_fin, str):
                        fin = datetime.fromisoformat(fecha_fin.replace('Z', '+00:00'))
                    else:
                        fin = fecha_fin
                        
                    if fin < inicio:
                        errores.append("La fecha de fin no puede ser anterior a la de inicio")
                except (ValueError, TypeError):
                    errores.append("Formato de fecha inválido")
        
        return len(errores) == 0, errores

    def validar_horario_fundae(self, horario: str) -> Tuple[bool, str]:
        """Valida que el horario cumpla formato FUNDAE."""
        if not horario or not isinstance(horario, str):
            return False, "Horario requerido en formato FUNDAE"
        
        # Verificar que contenga días
        if "Días:" not in horario:
            return False, "Debe especificar días de la semana"
        
        # Verificar formato de horas (HH:MM)
        if not re.search(r'\d{2}:\d{2}', horario):
            return False, "Debe incluir horas en formato HH:MM"
        
        return True, ""
   
    def normalizar_modalidad_fundae(self, modalidad_input: str, aula_virtual: bool = None) -> str:
        """Convierte modalidad de acciones a formato FUNDAE."""
        if not modalidad_input:
            return "TELEFORMACION" if aula_virtual else "PRESENCIAL"
    
        m = (modalidad_input or "").strip().lower()
    
        # equivalencias
        online_syns = {"online", "en línea", "en linea", "on line", "on-line", "aula virtual"}
    
        if m == "presencial":
            return "PRESENCIAL"
        if m == "mixta":
            return "MIXTA"
        if m == "teleformación" or m == "teleformacion" or m in online_syns:
            return "TELEFORMACION"
    
        # Si ya viene en formato FUNDAE, respetar
        if modalidad_input in ["PRESENCIAL", "TELEFORMACION", "MIXTA"]:
            return modalidad_input
    
        # Fallback razonable
        return "TELEFORMACION" if aula_virtual else "PRESENCIAL"

    def fecha_pasada(self, fecha_str: str) -> bool:
        """Verifica si una fecha ya pasó."""
        if not fecha_str:
            return False
        try:
            fecha = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            return fecha.date() < datetime.now().date()
        except:
            return False

    def validar_permisos_grupo(self, grupo_id: str) -> bool:
        """Valida si el usuario puede gestionar un grupo específico."""
        try:
            if self.rol == "admin":
                return True
            
            elif self.rol == "gestor" and self.empresa_id:
                # Gestor puede gestionar grupos de su empresa
                grupo_info = self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                if grupo_info.data:
                    return grupo_info.data[0]["empresa_id"] == self.empresa_id
            
            return False
        except Exception as e:
            st.error(f"Error validando permisos: {e}")
            return False

    def calcular_limite_fundae(self, modalidad: str, horas: int, participantes: int) -> Tuple[float, float]:
        """Calcula límite máximo FUNDAE según modalidad."""
        try:
            tarifa = 7.5 if modalidad in ["Teleformación", "TELEFORMACION"] else 13.0
            limite = tarifa * horas * participantes
            return limite, tarifa
        except:
            return 0, 0
            
    def validar_codigo_grupo_unico_fundae(self, codigo_grupo, accion_formativa_id, grupo_id=None):
        """
        Valida unicidad de código de grupo según normativa FUNDAE:
        - Único por acción formativa, empresa gestora y año
        - Permite reutilizar códigos en años diferentes
        """
        try:
            # Obtener información de la acción formativa
            accion_res = self.supabase.table("acciones_formativas").select(
                "codigo_accion, empresa_id, fecha_inicio"
            ).eq("id", accion_formativa_id).execute()
            
            if not accion_res.data:
                return False, "Acción formativa no encontrada"
            
            accion_data = accion_res.data[0]
            empresa_gestora_id = accion_data["empresa_id"]
            fecha_accion = accion_data["fecha_inicio"]
            
            # Determinar año de la acción
            if fecha_accion:
                try:
                    ano_accion = datetime.fromisoformat(str(fecha_accion).replace('Z', '+00:00')).year
                except:
                    ano_accion = datetime.now().year
            else:
                ano_accion = datetime.now().year
            
            # Buscar códigos duplicados en el mismo año y empresa gestora
            query = self.supabase.table("grupos").select(
                "id, codigo_grupo, fecha_inicio"
            ).eq("codigo_grupo", codigo_grupo)
            
            # Filtrar por año
            if ano_accion:
                query = query.gte("fecha_inicio", f"{ano_accion}-01-01").lt("fecha_inicio", f"{ano_accion + 1}-01-01")
            
            # Excluir grupo actual si estamos editando
            if grupo_id:
                query = query.neq("id", grupo_id)
            
            res = query.execute()
            
            if res.data:
                # Verificar si alguno pertenece a la misma empresa gestora
                for grupo_existente in res.data:
                    # Obtener empresa gestora del grupo existente
                    grupo_accion_res = self.supabase.table("grupos").select("""
                        accion_formativa:acciones_formativas(empresa_id)
                    """).eq("id", grupo_existente["id"]).execute()
                    
                    if grupo_accion_res.data:
                        empresa_existente = grupo_accion_res.data[0].get("accion_formativa", {}).get("empresa_id")
                        if empresa_existente == empresa_gestora_id:
                            return False, f"Ya existe un grupo con código '{codigo_grupo}' en {ano_accion} para esta empresa gestora"
            
            return True, ""
            
        except Exception as e:
            return False, f"Error al validar código: {e}"

def determinar_empresa_gestora_responsable(self, accion_formativa_id, empresa_propietaria_id):
    """
    Determina qué empresa es responsable ante FUNDAE según jerarquía:
    1. Si la acción es de una gestora, la gestora es responsable
    2. Si la acción es de un cliente, su gestora matriz es responsable
    """
    try:
        # Obtener empresa de la acción formativa
        accion_res = self.supabase.table("acciones_formativas").select(
            "empresa_id"
        ).eq("id", accion_formativa_id).execute()
        
        if not accion_res.data:
            return None, "Acción formativa no encontrada"
        
        empresa_accion_id = accion_res.data[0]["empresa_id"]
        
        # Obtener información de la empresa de la acción
        empresa_res = self.supabase.table("empresas").select(
            "id, nombre, tipo_empresa, empresa_matriz_id"
        ).eq("id", empresa_accion_id).execute()
        
        if not empresa_res.data:
            return None, "Empresa de la acción no encontrada"
        
        empresa_accion = empresa_res.data[0]
        
        # Si es una gestora, ella es responsable
        if empresa_accion["tipo_empresa"] == "GESTORA":
            return empresa_accion, ""
        
        # Si es cliente de gestor, buscar la gestora matriz
        elif empresa_accion["tipo_empresa"] == "CLIENTE_GESTOR":
            gestora_id = empresa_accion["empresa_matriz_id"]
            if gestora_id:
                gestora_res = self.supabase.table("empresas").select("*").eq("id", gestora_id).execute()
                if gestora_res.data:
                    return gestora_res.data[0], ""
                else:
                    return None, "Gestora matriz no encontrada"
            else:
                return None, "Cliente sin gestora matriz asignada"
        
        # Si es cliente SaaS, usar la empresa propietaria del grupo
        elif empresa_accion["tipo_empresa"] == "CLIENTE_SAAS":
            # Para clientes SaaS, la responsable es la empresa propietaria del grupo
            if empresa_propietaria_id:
                propietaria_res = self.supabase.table("empresas").select("*").eq("id", empresa_propietaria_id).execute()
                if propietaria_res.data:
                    return propietaria_res.data[0], ""
            return empresa_accion, ""  # Fallback a la empresa de la acción
        
        return empresa_accion, ""
        
    except Exception as e:
        return None, f"Error al determinar empresa responsable: {e}"

def generar_codigo_grupo_sugerido(self, accion_formativa_id, ano=None):
    """
    Genera un código de grupo sugerido basado en la secuencia existente para el año.
    Formato sugerido: [CODIGO_ACCION]-G[NUMERO] (ej: FORM001-G1, FORM001-G2)
    """
    try:
        if not ano:
            ano = datetime.now().year
        
        # Obtener información de la acción
        accion_res = self.supabase.table("acciones_formativas").select(
            "codigo_accion, empresa_id"
        ).eq("id", accion_formativa_id).execute()
        
        if not accion_res.data:
            return None, "Acción formativa no encontrada"
        
        codigo_accion = accion_res.data[0]["codigo_accion"]
        empresa_gestora_id = accion_res.data[0]["empresa_id"]
        
        # Buscar grupos existentes para esta acción en el año actual
        grupos_existentes = self.supabase.table("grupos").select("""
            codigo_grupo,
            accion_formativa:acciones_formativas(empresa_id)
        """).eq("accion_formativa_id", accion_formativa_id).gte(
            "fecha_inicio", f"{ano}-01-01"
        ).lt("fecha_inicio", f"{ano + 1}-01-01").execute()
        
        # Filtrar por empresa gestora
        grupos_empresa = []
        for grupo in grupos_existentes.data or []:
            if grupo.get("accion_formativa", {}).get("empresa_id") == empresa_gestora_id:
                grupos_empresa.append(grupo["codigo_grupo"])
        
        # Determinar siguiente número
        patron_base = f"{codigo_accion}-G"
        numeros_usados = []
        
        for codigo_grupo in grupos_empresa:
            if codigo_grupo.startswith(patron_base):
                try:
                    numero_str = codigo_grupo[len(patron_base):]
                    numero = int(numero_str)
                    numeros_usados.append(numero)
                except ValueError:
                    continue
        
        # Encontrar el siguiente número disponible
        siguiente_numero = 1
        while siguiente_numero in numeros_usados:
            siguiente_numero += 1
        
        codigo_sugerido = f"{patron_base}{siguiente_numero}"
        return codigo_sugerido, ""
        
    except Exception as e:
        return None, f"Error al generar código sugerido: {e}"

def validar_coherencia_temporal_grupo(self, fecha_inicio: date, fecha_fin_prevista: date, accion_formativa_id: str) -> List[str]:
    """
    Valida coherencia temporal del grupo con la acción formativa.
    """
    errores = []
    
    if fecha_inicio and fecha_fin_prevista:
        if fecha_fin_prevista <= fecha_inicio:
            errores.append("La fecha de fin debe ser posterior a la fecha de inicio")
    
    if fecha_inicio and accion_formativa_id:
        try:
            # Verificar que el grupo esté dentro del periodo de la acción
            accion_res = self.supabase.table("acciones_formativas").select(
                "fecha_inicio, fecha_fin"
            ).eq("id", accion_formativa_id).execute()
            
            if accion_res.data:
                accion_data = accion_res.data[0]
                accion_inicio = accion_data.get("fecha_inicio")
                accion_fin = accion_data.get("fecha_fin")
                
                if accion_inicio:
                    accion_inicio_dt = datetime.fromisoformat(str(accion_inicio).replace('Z', '+00:00')).date()
                    if fecha_inicio < accion_inicio_dt:
                        errores.append(f"El grupo no puede iniciar antes que la acción formativa ({accion_inicio_dt})")
                
                if accion_fin and fecha_fin_prevista:
                    accion_fin_dt = datetime.fromisoformat(str(accion_fin).replace('Z', '+00:00')).date()
                    if fecha_fin_prevista > accion_fin_dt:
                        errores.append(f"El grupo no puede finalizar después que la acción formativa ({accion_fin_dt})")
        
        except Exception as e:
            errores.append(f"Error al validar coherencia temporal: {e}")
    
    return errores

def verificar_codigos_duplicados_por_ano(self, df_grupos: pd.DataFrame) -> List[str]:
    """
    Verifica códigos de grupo duplicados en el mismo año para la misma empresa gestora.
    """
    duplicados = []
    
    if df_grupos.empty:
        return duplicados
    
    try:
        # Enriquecer con información de empresa gestora
        grupos_enriquecidos = []
        for _, grupo in df_grupos.iterrows():
            accion_id = grupo.get('accion_formativa_id')
            if accion_id:
                empresa_resp, _ = self.determinar_empresa_gestora_responsable(accion_id, grupo.get('empresa_id'))
                if empresa_resp:
                    grupos_enriquecidos.append({
                        'codigo_grupo': grupo.get('codigo_grupo'),
                        'fecha_inicio': grupo.get('fecha_inicio'),
                        'empresa_gestora_id': empresa_resp.get('id'),
                        'empresa_gestora_nombre': empresa_resp.get('nombre')
                    })
        
        if not grupos_enriquecidos:
            return duplicados
        
        df_enriquecido = pd.DataFrame(grupos_enriquecidos)
        df_enriquecido['ano'] = pd.to_datetime(df_enriquecido['fecha_inicio'], errors='coerce').dt.year
        
        # Agrupar por año y empresa gestora
        for (ano, empresa_id), grupo_ano_empresa in df_enriquecido.groupby(['ano', 'empresa_gestora_id']):
            if pd.isna(ano):
                continue
                
            # Buscar duplicados dentro del mismo año y empresa gestora
            duplicados_grupo = grupo_ano_empresa.groupby('codigo_grupo').size()
            duplicados_grupo = duplicados_grupo[duplicados_grupo > 1]
            
            if not duplicados_grupo.empty:
                empresa_nombre = grupo_ano_empresa.iloc[0]['empresa_gestora_nombre']
                for codigo, count in duplicados_grupo.items():
                    duplicados.append(f"Código '{codigo}' repetido {count} veces en {int(ano)} para empresa gestora {empresa_nombre}")
    
    except Exception as e:
        duplicados.append(f"Error al verificar duplicados: {e}")
    
    return duplicados

def get_avisos_fundae(self, df_grupos: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Genera avisos específicos de FUNDAE para mostrar en la interfaz.
    """
    avisos = []
    
    # Verificar códigos duplicados
    codigos_duplicados = self.verificar_codigos_duplicados_por_ano(df_grupos)
    if codigos_duplicados:
        avisos.append({
            "tipo": "error",
            "titulo": "Códigos Duplicados FUNDAE",
            "mensaje": f"Se encontraron {len(codigos_duplicados)} códigos de grupo duplicados",
            "detalles": codigos_duplicados,
            "accion": "Revisar y corregir códigos duplicados por año y empresa gestora"
        })
    
    # Verificar grupos sin empresa responsable clara
    grupos_problematicos = []
    for _, grupo in df_grupos.iterrows():
        accion_id = grupo.get('accion_formativa_id')
        if accion_id:
            empresa_resp, error = self.determinar_empresa_gestora_responsable(accion_id, grupo.get('empresa_id'))
            if error or not empresa_resp:
                codigo_grupo = grupo.get('codigo_grupo', 'Sin código')
                grupos_problematicos.append(f"Grupo '{codigo_grupo}': {error or 'Sin empresa responsable'}")
    
    if grupos_problematicos:
        avisos.append({
            "tipo": "warning",
            "titulo": "Empresas Responsables FUNDAE",
            "mensaje": f"{len(grupos_problematicos)} grupo(s) sin empresa responsable clara ante FUNDAE",
            "detalles": grupos_problematicos,
            "accion": "Verificar configuración de empresas y jerarquía"
        })
    
    # Verificar grupos con fechas incoherentes
    grupos_fechas_problematicas = []
    for _, grupo in df_grupos.iterrows():
        fecha_inicio = grupo.get('fecha_inicio')
        fecha_fin = grupo.get('fecha_fin_prevista')
        accion_id = grupo.get('accion_formativa_id')
        
        if fecha_inicio and fecha_fin and accion_id:
            try:
                fecha_inicio_dt = pd.to_datetime(fecha_inicio).date()
                fecha_fin_dt = pd.to_datetime(fecha_fin).date()
                
                errores_temporales = self.validar_coherencia_temporal_grupo(
                    fecha_inicio_dt, fecha_fin_dt, accion_id
                )
                
                if errores_temporales:
                    codigo = grupo.get('codigo_grupo', 'Sin código')
                    grupos_fechas_problematicas.append(f"Grupo '{codigo}': {'; '.join(errores_temporales)}")
            except:
                pass
    
    if grupos_fechas_problematicas:
        avisos.append({
            "tipo": "warning", 
            "titulo": "Coherencia Temporal",
            "mensaje": f"{len(grupos_fechas_problematicas)} grupo(s) con fechas incoherentes",
            "detalles": grupos_fechas_problematicas,
            "accion": "Verificar fechas de grupos vs acciones formativas"
        })
    
    return avisos

# =========================
# ACTUALIZACIÓN DEL MÉTODO CREATE_GRUPO_CON_JERARQUIA EXISTENTE
# =========================

def create_grupo_con_jerarquia_mejorado(self, datos_grupo: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Versión mejorada que incluye todas las validaciones FUNDAE.
    """
    try:
        # Validaciones FUNDAE previas
        codigo_grupo = datos_grupo.get("codigo_grupo")
        accion_formativa_id = datos_grupo.get("accion_formativa_id")
        
        if not codigo_grupo or not accion_formativa_id:
            st.error("Código de grupo y acción formativa son obligatorios")
            return False, ""
        
        # Validar código único FUNDAE
        es_valido, error_codigo = self.validar_codigo_grupo_unico_fundae(
            codigo_grupo, accion_formativa_id
        )
        
        if not es_valido:
            st.error(f"Código FUNDAE inválido: {error_codigo}")
            return False, ""
        
        # Validar coherencia temporal si hay fechas
        fecha_inicio = datos_grupo.get("fecha_inicio")
        fecha_fin = datos_grupo.get("fecha_fin_prevista")
        
        if fecha_inicio and fecha_fin:
            try:
                fecha_inicio_dt = datetime.fromisoformat(str(fecha_inicio)).date()
                fecha_fin_dt = datetime.fromisoformat(str(fecha_fin)).date()
                
                errores_temporales = self.validar_coherencia_temporal_grupo(
                    fecha_inicio_dt, fecha_fin_dt, accion_formativa_id
                )
                
                if errores_temporales:
                    for error in errores_temporales:
                        st.error(f"Error temporal: {error}")
                    return False, ""
            except Exception as e:
                st.error(f"Error en validación temporal: {e}")
                return False, ""
        
        # Determinar empresa responsable FUNDAE
        empresa_responsable, error_empresa = self.determinar_empresa_gestora_responsable(
            accion_formativa_id, datos_grupo.get("empresa_id")
        )
        
        if error_empresa:
            st.error(f"Error empresa responsable: {error_empresa}")
            return False, ""
        
        # Continuar con el método original pero con validaciones añadidas
        return self.create_grupo_con_jerarquia(datos_grupo)
        
    except Exception as e:
        st.error(f"Error al crear grupo con validaciones FUNDAE: {e}")
        return False, ""
        
    # =========================
    # GRUPOS - CONSULTAS PRINCIPALES
    # =========================

    @st.cache_data(ttl=300)
    def get_grupos_completos(self) -> pd.DataFrame:
        """Obtiene grupos con información completa."""
        try:
            query = self.supabase.table("grupos").select("""
                id, codigo_grupo, fecha_inicio, fecha_fin, fecha_fin_prevista,
                modalidad, horario, localidad, provincia, cp, lugar_imparticion,
                n_participantes_previstos, n_participantes_finalizados,
                n_aptos, n_no_aptos, observaciones, empresa_id, created_at,
                empresa:empresas!fk_grupo_empresa (id, nombre, cif),
                accion_formativa:acciones_formativas!fk_grupo_accion (id, nombre, modalidad, num_horas, codigo_accion)
            """)
            query = self._apply_empresa_filter(query, "grupos")

            res = query.order("fecha_inicio", desc=True).execute()
            df = pd.DataFrame(res.data or [])

            if not df.empty:
                # Procesar acción formativa
                if "accion_formativa" in df.columns:
                    df["accion_nombre"] = df["accion_formativa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                    df["accion_modalidad"] = df["accion_formativa"].apply(
                        lambda x: x.get("modalidad") if isinstance(x, dict) else ""
                    )
                    df["accion_horas"] = df["accion_formativa"].apply(
                        lambda x: x.get("num_horas") if isinstance(x, dict) else 0
                    )
            
                # Procesar empresa
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )

            return df
        except Exception as e:
            return self._handle_query_error("cargar grupos completos", e)
    
    @st.cache_data(ttl=600)
    def get_grupos_dict(self) -> Dict[str, str]:
        """Devuelve diccionario de grupos: código -> id."""
        try:
            df = self.get_grupos_completos()
            return {row["codigo_grupo"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}
        except Exception as e:
            st.error(f"Error al cargar grupos dict: {e}")
            return {}
            
    @st.cache_data(ttl=600)
    def get_grupos_dict_por_empresa(self, empresa_id: str) -> Dict[str, str]:
        """Devuelve grupos de una empresa específica: código -> id."""
        try:
            df = self.get_grupos_completos()
            if df.empty:
                return {}
        
            # Filtrar por empresa_id
            df_empresa = df[df["empresa_id"] == empresa_id]
            return {row["codigo_grupo"]: row["id"] for _, row in df_empresa.iterrows()}
        
        except Exception as e:
            st.error(f"Error al cargar grupos de empresa {empresa_id}: {e}")
            return {}
        
    @st.cache_data(ttl=600)
    def get_grupos_acciones(self) -> pd.DataFrame:
        """Obtiene listado de grupos de acciones (catálogo auxiliar)."""
        try:
            res = self.supabase.table("grupos_acciones").select("id, nombre, codigo, cod_area_profesional").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar grupos de acciones", e)
            
    @st.cache_data(ttl=600)
    def get_empresas_dict(self) -> Dict[str, str]:
        """Obtiene diccionario de empresas: nombre -> id."""
        try:
            result = self.supabase.table("empresas").select("id, nombre").execute()
            
            if result.data:
                return {item["nombre"]: item["id"] for item in result.data}
            return {}
        except Exception as e:
            st.error(f"Error al cargar empresas: {e}")
            return {}

    def update_grupo(self, grupo_id: str, datos_editados: Dict[str, Any]) -> bool:
        """Actualiza un grupo existente."""
        try:
            datos_editados["updated_at"] = datetime.utcnow().isoformat()
            self.supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            self.limpiar_cache_grupos()
            return True
        except Exception as e:
            st.error(f"Error al actualizar grupo: {e}")
            return False

    def limpiar_cache_grupos(self):
        """Limpia todos los caches relacionados con grupos."""
        try:
            # Caches principales
            if hasattr(self, 'get_grupos_completos'):
                self.get_grupos_completos.clear()
            if hasattr(self, 'get_tutores_completos'):
                self.get_tutores_completos.clear()
            if hasattr(self, 'get_acciones_dict'):
                self.get_acciones_dict.clear()
            if hasattr(self, 'get_empresas_dict'):
                self.get_empresas_dict.clear()
            
            # Caches específicos de grupos
            if hasattr(self, 'get_tutores_grupo'):
                self.get_tutores_grupo.clear()
            if hasattr(self, 'get_empresas_grupo'):
                self.get_empresas_grupo.clear()
            if hasattr(self, 'get_participantes_grupo'):
                self.get_participantes_grupo.clear()
            if hasattr(self, 'get_participantes_disponibles_jerarquia'):
                self.get_participantes_disponibles_jerarquia.clear()
            if hasattr(self, 'get_grupo_costes'):
                self.get_grupo_costes.clear()
            if hasattr(self, 'get_grupo_bonificaciones'):
                self.get_grupo_bonificaciones.clear()
            
            # Centros gestores
            if hasattr(self, 'get_centro_gestor_grupo'):
                self.get_centro_gestor_grupo.clear()
            if hasattr(self, 'get_centros_gestores_jerarquia'):
                self.get_centros_gestores_jerarquia.clear()
                
        except Exception as e:
            # Fallar silenciosamente - el cache se limpiará eventualmente
            pass

    # =========================
    # ACCIONES FORMATIVAS
    # =========================
    @st.cache_data(ttl=300)
    def get_acciones_formativas(self) -> pd.DataFrame:
        """Obtiene acciones formativas según el rol."""
        try:
            query = self.supabase.table("acciones_formativas").select("*")
            query = self._apply_empresa_filter(query, "acciones_formativas")
            
            res = query.order("nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar acciones formativas", e)

    def get_acciones_dict(self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de acciones."""
        df = self.get_acciones_formativas()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    @st.cache_data(ttl=3600)
    def get_provincias(self) -> list:
        """Devuelve listado de provincias ordenadas alfabéticamente."""
        try:
            res = self.supabase.table("provincias").select("id, nombre").order("nombre").execute()
            return res.data or []
        except Exception as e:
            st.error(f"Error al cargar provincias: {e}")
            return []

    @st.cache_data(ttl=3600) 
    def get_localidades_por_provincia(self, provincia_id: int) -> list:
        """Devuelve listado de localidades de una provincia."""
        try:
            res = self.supabase.table("localidades").select("id, nombre").eq("provincia_id", provincia_id).order("nombre").execute()
            return res.data or []
        except Exception as e:
            st.error(f"Error al cargar localidades: {e}")
            return []

    def get_accion_modalidad(self, accion_id: str) -> str:
        """Devuelve la modalidad de una acción formativa concreta."""
        try:
            res = self.supabase.table("acciones_formativas").select("modalidad").eq("id", accion_id).execute()
            if res.data:
                return res.data[0].get("modalidad", "")
            return ""
        except Exception as e:
            st.error(f"Error al obtener modalidad de acción formativa: {e}")
            return ""

    # =========================
    # MÉTODOS DE EMPRESAS CON JERARQUÍA
    # =========================

    def get_empresas_para_grupos(self) -> Dict[str, str]:
        """Obtiene empresas que pueden asignarse a grupos según jerarquía."""
        try:
            if self.rol == "admin":
                # Admin puede asignar cualquier empresa
                res = self.supabase.table("empresas").select("id, nombre, tipo_empresa").order("nombre").execute()
                
            elif self.rol == "gestor" and self.empresa_id:
                # Gestor puede asignar su empresa y sus clientes
                res = self.supabase.table("empresas").select("id, nombre, tipo_empresa").or_(
                    f"id.eq.{self.empresa_id},empresa_matriz_id.eq.{self.empresa_id}"
                ).order("nombre").execute()
            else:
                return {}
            
            if res.data:
                # Agregar indicador de tipo para claridad
                result = {}
                for emp in res.data:
                    tipo_display = {
                        "CLIENTE_SAAS": "",
                        "GESTORA": " (Gestora)",
                        "CLIENTE_GESTOR": " (Cliente)"
                    }.get(emp.get("tipo_empresa", ""), "")
                    
                    result[f"{emp['nombre']}{tipo_display}"] = emp["id"]
                return result
            return {}
            
        except Exception as e:
            st.error(f"Error al cargar empresas para grupos: {e}")
            return {}

    def create_grupo_con_jerarquia(self, datos_grupo: Dict[str, Any]) -> Tuple[bool, str]:
        """Crea grupo respetando jerarquía de empresas."""
        try:
            # Asignar empresa propietaria según rol
            if self.rol == "gestor" and self.empresa_id:
                datos_grupo["empresa_id"] = self.empresa_id
            elif self.rol == "admin":
                # Admin debe especificar empresa propietaria
                if not datos_grupo.get("empresa_id"):
                    st.error("Debe especificar empresa propietaria del grupo")
                    return False, ""
                
                # Validar que la empresa existe
                empresa_check = self.supabase.table("empresas").select("id").eq("id", datos_grupo["empresa_id"]).execute()
                if not empresa_check.data:
                    st.error("La empresa especificada no existe")
                    return False, ""
            else:
                st.error("Sin permisos para crear grupos")
                return False, ""
            
            # Crear grupo con validaciones FUNDAE
            errores_validacion = self.validar_grupo_fundae(datos_grupo)
            if errores_validacion[1]:  # Si hay errores
                for error in errores_validacion[1]:
                    st.error(f"Error FUNDAE: {error}")
                return False, ""
            
            # Preparar datos finales
            datos_grupo.update({
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            })
            
            # Crear grupo
            res = self.supabase.table("grupos").insert(datos_grupo).execute()
            
            if not res.data:
                st.error("Error al crear el grupo en la base de datos")
                return False, ""
            
            grupo_id = res.data[0]["id"]
            
            # Auto-asignar empresa propietaria como empresa participante
            self.create_empresa_grupo(grupo_id, datos_grupo["empresa_id"])
            
            # Limpiar caches
            self.limpiar_cache_grupos()
            
            return True, grupo_id
            
        except Exception as e:
            st.error(f"Error al crear grupo: {e}")
            return False, ""

    def get_empresas_asignables_a_grupo(self, grupo_id: str) -> Dict[str, str]:
        """Obtiene empresas que pueden asignarse como participantes de un grupo específico."""
        try:
            # Obtener empresa propietaria del grupo
            grupo_info = self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
            if not grupo_info.data:
                return {}
            
            empresa_propietaria = grupo_info.data[0]["empresa_id"]
            
            # Obtener empresas ya asignadas
            empresas_ya_asignadas = self.supabase.table("empresas_grupos").select("empresa_id").eq("grupo_id", grupo_id).execute()
            empresas_asignadas_ids = [e["empresa_id"] for e in (empresas_ya_asignadas.data or [])]
            
            # Obtener empresas disponibles según jerarquía
            if self.rol == "admin":
                # Admin puede asignar cualquier empresa
                res = self.supabase.table("empresas").select("id, nombre").order("nombre").execute()
                
            elif self.rol == "gestor" and self.empresa_id:
                # Gestor solo puede gestionar grupos de su empresa
                if empresa_propietaria != self.empresa_id:
                    return {}
                
                # Puede asignar su empresa y empresas clientes
                res = self.supabase.table("empresas").select("id, nombre").or_(
                    f"id.eq.{self.empresa_id},empresa_matriz_id.eq.{self.empresa_id}"
                ).order("nombre").execute()
            else:
                return {}
            
            if res.data:
                # Filtrar empresas ya asignadas
                empresas_disponibles = {}
                for emp in res.data:
                    if emp["id"] not in empresas_asignadas_ids:
                        empresas_disponibles[emp["nombre"]] = emp["id"]
                return empresas_disponibles
            
            return {}
            
        except Exception as e:
            st.error(f"Error al cargar empresas asignables: {e}")
            return {}

    @st.cache_data(ttl=300)
    def get_empresas_grupo(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene empresas participantes de un grupo."""
        try:
            res = self.supabase.table("empresas_grupos").select("""
                id, fecha_asignacion,
                empresa:empresas(id, nombre, cif)
            """).eq("grupo_id", grupo_id).order("fecha_asignacion").execute()
            
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar empresas de grupo", e)

    def create_empresa_grupo(self, grupo_id: str, empresa_id: str) -> bool:
        """Asigna una empresa como participante de un grupo."""
        try:
            datos = {
                "grupo_id": grupo_id,
                "empresa_id": empresa_id,
                "fecha_asignacion": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("empresas_grupos").insert(datos).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_empresas_grupo'):
                self.get_empresas_grupo.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al asignar empresa al grupo: {e}")
            return False

    def delete_empresa_grupo(self, relacion_id: str) -> bool:
        """Elimina una empresa de un grupo."""
        try:
            self.supabase.table("empresas_grupos").delete().eq("id", relacion_id).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_empresas_grupo'):
                self.get_empresas_grupo.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al eliminar empresa del grupo: {e}")
            return False

    # =========================
    # MÉTODOS DE TUTORES CON JERARQUÍA
    # =========================

    @st.cache_data(ttl=300)
    def get_tutores_grupo(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene tutores asignados a un grupo."""
        try:
            res = self.supabase.table("tutores_grupos").select("""
                id, fecha_asignacion,
                tutor:tutores(id, nombre, apellidos, email, telefono, especialidad, empresa_id)
            """).eq("grupo_id", grupo_id).order("fecha_asignacion").execute()
            
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar tutores de grupo", e)

    def get_tutores_disponibles_jerarquia(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene tutores disponibles según jerarquía empresarial."""
        try:
            # Obtener tutores ya asignados
            tutores_asignados = self.supabase.table("tutores_grupos").select("tutor_id").eq("grupo_id", grupo_id).execute()
            tutores_asignados_ids = [t["tutor_id"] for t in (tutores_asignados.data or [])]
            
            # Obtener empresas participantes del grupo
            empresas_grupo = self.supabase.table("empresas_grupos").select("empresa_id").eq("grupo_id", grupo_id).execute()
            empresas_ids = [e["empresa_id"] for e in (empresas_grupo.data or [])]
            
            # Añadir empresa propietaria del grupo
            grupo_info = self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
            if grupo_info.data:
                empresas_ids.append(grupo_info.data[0]["empresa_id"])
            
            if not empresas_ids:
                return pd.DataFrame()
            
            # Obtener tutores de empresas participantes
            query = self.supabase.table("tutores").select("""
                id, nombre, apellidos, email, especialidad, empresa_id,
                empresa:empresas(nombre)
            """).in_("empresa_id", empresas_ids)
            
            # Filtrar por rol
            if self.rol == "gestor" and self.empresa_id:
                # Gestor solo ve tutores de empresas bajo su gestión
                query = query.or_(f"empresa_id.eq.{self.empresa_id},empresa.empresa_matriz_id.eq.{self.empresa_id}")
            
            res = query.execute()
            df = pd.DataFrame(res.data or [])
            
            if not df.empty:
                # Añadir información de empresa
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
                df["nombre_completo"] = df["nombre"] + " " + df["apellidos"]
                
                # Filtrar tutores ya asignados
                df = df[~df["id"].isin(tutores_asignados_ids)]
            
            return df
            
        except Exception as e:
            return self._handle_query_error("cargar tutores disponibles", e)

    def create_tutor_grupo(self, grupo_id: str, tutor_id: str) -> bool:
        """Asigna un tutor a un grupo."""
        try:
            datos = {
                "grupo_id": grupo_id,
                "tutor_id": tutor_id,
                "fecha_asignacion": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("tutores_grupos").insert(datos).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_tutores_grupo'):
                self.get_tutores_grupo.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al asignar tutor al grupo: {e}")
            return False

    def delete_tutor_grupo(self, relacion_id: str) -> bool:
        """Elimina un tutor de un grupo."""
        try:
            self.supabase.table("tutores_grupos").delete().eq("id", relacion_id).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_tutores_grupo'):
                self.get_tutores_grupo.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al eliminar tutor del grupo: {e}")
            return False

    # =========================
    # PARTICIPANTES CON JERARQUÍA
    # =========================

    @st.cache_data(ttl=300)
    def get_participantes_grupo(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene participantes asignados a un grupo."""
        try:
            res = self.supabase.table("participantes_grupos").select("""
                id as relacion_id, fecha_asignacion,
                participante:participantes(id, nif, nombre, apellidos, email, telefono, empresa_id)
            """).eq("grupo_id", grupo_id).order("fecha_asignacion").execute()
            
            df = pd.DataFrame(res.data or [])
            
            if not df.empty and "participante" in df.columns:
                # Extraer datos del participante
                participante_data = []
                for _, row in df.iterrows():
                    p = row.get("participante", {})
                    if isinstance(p, dict):
                        participante_data.append({
                            "relacion_id": row["relacion_id"],
                            "fecha_asignacion": row["fecha_asignacion"],
                            "id": p.get("id"),
                            "nif": p.get("nif"),
                            "nombre": p.get("nombre"),
                            "apellidos": p.get("apellidos"),
                            "email": p.get("email"),
                            "telefono": p.get("telefono"),
                            "empresa_id": p.get("empresa_id")
                        })
                
                return pd.DataFrame(participante_data)
            
            return pd.DataFrame()
        except Exception as e:
            return self._handle_query_error("cargar participantes de grupo", e)

    def get_participantes_disponibles_jerarquia(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene participantes disponibles según jerarquía empresarial."""
        try:
            # Obtener participantes ya asignados
            participantes_asignados = self.supabase.table("participantes_grupos").select("participante_id").eq("grupo_id", grupo_id).execute()
            participantes_asignados_ids = [p["participante_id"] for p in (participantes_asignados.data or [])]
            
            # Obtener empresas participantes del grupo
            empresas_grupo = self.supabase.table("empresas_grupos").select("empresa_id").eq("grupo_id", grupo_id).execute()
            empresas_ids = [e["empresa_id"] for e in (empresas_grupo.data or [])]
            
            # Añadir empresa propietaria del grupo
            grupo_info = self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
            if grupo_info.data:
                empresas_ids.append(grupo_info.data[0]["empresa_id"])
            
            if not empresas_ids:
                return pd.DataFrame()
            
            # Obtener participantes de empresas participantes
            query = self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, email, telefono, empresa_id,
                empresa:empresas(nombre)
            """).in_("empresa_id", empresas_ids)
            
            # Filtrar por rol
            if self.rol == "gestor" and self.empresa_id:
                # Gestor solo ve participantes de empresas bajo su gestión
                query = query.or_(f"empresa_id.eq.{self.empresa_id},empresa.empresa_matriz_id.eq.{self.empresa_id}")
            
            res = query.execute()
            df = pd.DataFrame(res.data or [])
            
            if not df.empty:
                # Añadir información de empresa
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
                
                # Filtrar participantes ya asignados
                df = df[~df["id"].isin(participantes_asignados_ids)]
            
            return df
            
        except Exception as e:
            return self._handle_query_error("cargar participantes disponibles", e)

    def asignar_participante_a_grupo(self, participante_id: str, grupo_id: str) -> bool:
        """Asigna un participante a un grupo."""
        try:
            datos = {
                "grupo_id": grupo_id,
                "participante_id": participante_id,
                "fecha_asignacion": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("participantes_grupos").insert(datos).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_participantes_grupo'):
                self.get_participantes_grupo.clear()
            if hasattr(self, 'get_participantes_disponibles_jerarquia'):
                self.get_participantes_disponibles_jerarquia.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al asignar participante al grupo: {e}")
            return False

    def desasignar_participante_de_grupo(self, relacion_id: str) -> bool:
        """Desasigna un participante de un grupo."""
        try:
            self.supabase.table("participantes_grupos").delete().eq("id", relacion_id).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_participantes_grupo'):
                self.get_participantes_grupo.clear()
            if hasattr(self, 'get_participantes_disponibles_jerarquia'):
                self.get_participantes_disponibles_jerarquia.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al desasignar participante del grupo: {e}")
            return False

    # =========================
    # CENTROS GESTORES
    # =========================

    @st.cache_data(ttl=600)
    def get_centro_gestor_grupo(self, grupo_id: str) -> Dict[str, Any]:
        """Obtiene el centro gestor asignado a un grupo."""
        try:
            res = self.supabase.table("centros_gestores_grupos").select("""
                id, grupo_id, centro_id, created_at,
                centro:centros_gestores(*)
            """).eq("grupo_id", grupo_id).execute()
            
            if res.data:
                return res.data[0]
            return {}
        except Exception as e:
            st.error(f"Error al cargar centro gestor: {e}")
            return {}

    def get_centros_gestores_jerarquia(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene centros gestores disponibles según jerarquía empresarial."""
        try:
            # Obtener empresas participantes del grupo
            empresas_grupo = self.supabase.table("empresas_grupos").select("empresa_id").eq("grupo_id", grupo_id).execute()
            empresas_ids = [e["empresa_id"] for e in (empresas_grupo.data or [])]
            
            # Añadir empresa propietaria del grupo
            grupo_info = self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
            if grupo_info.data:
                empresas_ids.append(grupo_info.data[0]["empresa_id"])
            
            if not empresas_ids:
                return pd.DataFrame()
            
            # Obtener centros gestores de empresas participantes
            if self.rol == "admin":
                # Admin puede ver todos los centros de empresas participantes
                query = self.supabase.table("centros_gestores").select("*").in_("empresa_id", empresas_ids)
            elif self.rol == "gestor" and self.empresa_id:
                # Gestor solo ve centros de empresas bajo su gestión
                query = self.supabase.table("centros_gestores").select("*").in_("empresa_id", empresas_ids).eq("empresa_id", self.empresa_id)
            else:
                return pd.DataFrame()
            
            res = query.order("razon_social").execute()
            return pd.DataFrame(res.data or [])
            
        except Exception as e:
            return self._handle_query_error("cargar centros gestores", e)

    def assign_centro_gestor_a_grupo(self, grupo_id: str, centro_id: str) -> bool:
        """Asigna un centro gestor a un grupo."""
        try:
            # Eliminar centro gestor anterior si existe
            self.supabase.table("centros_gestores_grupos").delete().eq("grupo_id", grupo_id).execute()
            
            # Asignar nuevo centro gestor
            datos = {
                "grupo_id": grupo_id,
                "centro_id": centro_id,
                "created_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("centros_gestores_grupos").insert(datos).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_centro_gestor_grupo'):
                self.get_centro_gestor_grupo.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al asignar centro gestor: {e}")
            return False

    def unassign_centro_gestor_de_grupo(self, grupo_id: str) -> bool:
        """Desasigna el centro gestor de un grupo."""
        try:
            self.supabase.table("centros_gestores_grupos").delete().eq("grupo_id", grupo_id).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_centro_gestor_grupo'):
                self.get_centro_gestor_grupo.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al desasignar centro gestor: {e}")
            return False

    # =========================
    # COSTES FUNDAE
    # =========================
    @st.cache_data(ttl=3600)
    def get_provincias(self) -> list:
        """Devuelve listado de provincias ordenadas alfabéticamente."""
        try:
            res = self.supabase.table("provincias").select("id, nombre").order("nombre").execute()
            return res.data or []
        except Exception as e:
            st.error(f"Error al cargar provincias: {e}")
            return []
    
    @st.cache_data(ttl=3600) 
    def get_localidades_por_provincia(self, provincia_id: int) -> list:
        """Devuelve listado de localidades de una provincia."""
        try:
            res = self.supabase.table("localidades").select("id, nombre").eq("provincia_id", provincia_id).order("nombre").execute()
            return res.data or []
        except Exception as e:
            st.error(f"Error al cargar localidades: {e}")
            return []
    
    def calcular_limite_fundae(self, modalidad: str, horas: int, participantes: int) -> Tuple[float, float]:
        """Calcula límite máximo FUNDAE según modalidad."""
        try:
            tarifa = 7.5 if modalidad in ["Teleformación", "TELEFORMACION"] else 13.0
            limite = tarifa * horas * participantes
            return limite, tarifa
        except:
            return 0, 0
            
    @st.cache_data(ttl=300)
    def get_grupo_costes(self, grupo_id: str) -> Dict[str, Any]:
        """Obtiene costes de un grupo específico."""
        try:
            res = self.supabase.table("grupo_costes").select("*").eq("grupo_id", grupo_id).execute()
            return res.data[0] if res.data else {}
        except Exception as e:
            st.error(f"Error al cargar costes de grupo: {e}")
            return {}
    
    def create_grupo_coste(self, datos_coste: Dict[str, Any]) -> bool:
        """Crea registro de costes para un grupo."""
        try:
            datos_coste["created_at"] = datetime.utcnow().isoformat()
            self.supabase.table("grupo_costes").insert(datos_coste).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_grupo_costes'):
                self.get_grupo_costes.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al crear costes de grupo: {e}")
            return False
    
    def update_grupo_coste(self, grupo_id: str, datos_coste: Dict[str, Any]) -> bool:
        """Actualiza costes de un grupo."""
        try:
            datos_coste["updated_at"] = datetime.utcnow().isoformat()
            self.supabase.table("grupo_costes").update(datos_coste).eq("grupo_id", grupo_id).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_grupo_costes'):
                self.get_grupo_costes.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al actualizar costes de grupo: {e}")
            return False
    
    @st.cache_data(ttl=300)
    def get_grupo_bonificaciones(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene bonificaciones de un grupo."""
        try:
            res = self.supabase.table("grupo_bonificaciones").select("*").eq("grupo_id", grupo_id).order("mes").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar bonificaciones de grupo", e)
    
    def create_grupo_bonificacion(self, datos_bonif: Dict[str, Any]) -> bool:
        """Crea una bonificación mensual para un grupo."""
        try:
            datos_bonif["created_at"] = datetime.utcnow().isoformat()
            self.supabase.table("grupo_bonificaciones").insert(datos_bonif).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_grupo_bonificaciones'):
                self.get_grupo_bonificaciones.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al crear bonificación de grupo: {e}")
            return False
    
    def delete_grupo_bonificacion(self, bonificacion_id: str) -> bool:
        """Elimina una bonificación de un grupo."""
        try:
            self.supabase.table("grupo_bonificaciones").delete().eq("id", bonificacion_id).execute()
            
            # Limpiar cache
            if hasattr(self, 'get_grupo_bonificaciones'):
                self.get_grupo_bonificaciones.clear()
            
            return True
        except Exception as e:
            st.error(f"Error al eliminar bonificación: {e}")
            return False


    # =========================
    # MÉTODOS ADICIONALES PARA RESPONSABLE Y TELEFONO
    # =========================

    def update_grupo_responsable(self, grupo_id: str, responsable: str, telefono: str) -> bool:
        """Actualiza responsable y teléfono de contacto del grupo."""
        try:
            datos = {
                "responsable": responsable,
                "telefono_contacto": telefono,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("grupos").update(datos).eq("id", grupo_id).execute()
            self.limpiar_cache_grupos()
            
            return True
        except Exception as e:
            st.error(f"Error al actualizar responsable del grupo: {e}")
            return False
    # =========================
    # AVISOS Y ALERTAS MEJORADOS
    # =========================
    
    def mostrar_avisos_fundae_en_grupos(df_grupos, grupos_service):
        """
        Muestra avisos específicos de FUNDAE en la página de grupos.
        """
        avisos = []
        
        # Verificar códigos duplicados
        codigos_duplicados = verificar_codigos_duplicados_por_ano(df_grupos)
        if codigos_duplicados:
            avisos.append({
                "tipo": "error",
                "mensaje": f"Se encontraron {len(codigos_duplicados)} códigos de grupo duplicados en el mismo año",
                "detalles": codigos_duplicados
            })
        
        # Verificar grupos sin empresa responsable clara
        grupos_sin_responsable = verificar_grupos_sin_empresa_responsable(df_grupos, grupos_service)
        if grupos_sin_responsable:
            avisos.append({
                "tipo": "warning", 
                "mensaje": f"{len(grupos_sin_responsable)} grupo(s) sin empresa responsable clara ante FUNDAE",
                "detalles": grupos_sin_responsable
            })
        
        # Mostrar avisos
        for aviso in avisos:
            if aviso["tipo"] == "error":
                st.error(f"❌ {aviso['mensaje']}")
            else:
                st.warning(f"⚠️ {aviso['mensaje']}")
            
            with st.expander("Ver detalles", expanded=False):
                for detalle in aviso["detalles"][:5]:  # Mostrar máximo 5
                    st.write(f"• {detalle}")
                if len(aviso["detalles"]) > 5:
                    st.caption(f"... y {len(aviso['detalles']) - 5} más")
        
    # =========================
    # MÉTODOS DE ESTADÍSTICAS Y REPORTES
    # =========================

    def get_estadisticas_grupo(self, grupo_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas completas de un grupo."""
        try:
            # Datos básicos del grupo
            grupo_info = self.supabase.table("grupos").select("*").eq("id", grupo_id).execute()
            if not grupo_info.data:
                return {}
            
            grupo = grupo_info.data[0]
            
            # Contar relaciones
            tutores_count = len(self.supabase.table("tutores_grupos").select("id").eq("grupo_id", grupo_id).execute().data or [])
            empresas_count = len(self.supabase.table("empresas_grupos").select("id").eq("grupo_id", grupo_id).execute().data or [])
            participantes_count = len(self.supabase.table("participantes_grupos").select("id").eq("grupo_id", grupo_id).execute().data or [])
            
            # Costes
            costes_info = self.get_grupo_costes(grupo_id)
            total_costes = costes_info.get("total_costes_formacion", 0) if costes_info else 0
            
            # Bonificaciones
            bonificaciones_df = self.get_grupo_bonificaciones(grupo_id)
            total_bonificado = bonificaciones_df["importe"].sum() if not bonificaciones_df.empty else 0
            
            return {
                "grupo": grupo,
                "tutores_asignados": tutores_count,
                "empresas_participantes": empresas_count,
                "participantes_inscritos": participantes_count,
                "total_costes": total_costes,
                "total_bonificado": float(total_bonificado),
                "estado_completitud": {
                    "datos_basicos": bool(grupo.get("codigo_grupo") and grupo.get("fecha_inicio")),
                    "horarios": bool(grupo.get("horario")),
                    "tutores": tutores_count > 0,
                    "empresas": empresas_count > 0,
                    "participantes": participantes_count > 0,
                    "costes": bool(costes_info)
                }
       }
        except Exception as e:
            st.error(f"Error al obtener estadísticas del grupo: {e}")
            return {}

    def validar_grupo_para_xml(self, grupo_id: str, tipo_xml: str = "inicio") -> Tuple[bool, List[str]]:
        """Valida si un grupo está listo para generar XML FUNDAE."""
        try:
            grupo_info = self.supabase.table("grupos").select("*").eq("id", grupo_id).execute()
            if not grupo_info.data:
                return False, ["Grupo no encontrado"]
            
            grupo = grupo_info.data[0]
            return self.validar_grupo_fundae(grupo, tipo_xml)
        except Exception as e:
            return False, [f"Error al validar grupo: {e}"]
# =========================
# CONFIGURACIÓN ADICIONAL PARA GRUPOS_SERVICE
# =========================

def inicializar_configuracion_fundae(self):
    """
    Configuración adicional para validaciones FUNDAE en grupos_service.
    Añadir al método __init__ de GruposService.
    """
    self.modalidades_fundae = ["PRESENCIAL", "TELEFORMACION", "MIXTA"]
    self.max_participantes_grupo = 30
    self.min_participantes_grupo = 1
    self.cache_empresas_responsables = {}

def limpiar_cache_fundae(self):
    """
    Limpieza específica de caches FUNDAE.
    Integrar en limpiar_cache_grupos existente.
    """
    self.cache_empresas_responsables = {}
    
    # Limpiar caches adicionales si existen
    if hasattr(self, 'get_avisos_fundae'):
        try:
            self.get_avisos_fundae.clear()
        except:
            pass

# =========================
# FACTORY FUNCTION
# =========================

def get_grupos_service(supabase, session_state) -> GruposService:
    """Factory function para obtener instancia del servicio de grupos."""
    return GruposService(supabase, session_state)

# TEMPORAL - para debug
if __name__ == "__main__":
    print("Métodos disponibles en GruposService:")
    for attr in dir(GruposService):
        if not attr.startswith('_'):
            print(f"  - {attr}")
