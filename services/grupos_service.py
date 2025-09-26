import streamlit as st
import pandas as pd
import uuid
import re
from utils import validar_uuid_seguro, validar_codigo_grupo_fundae
from datetime import datetime, time, date
from typing import Dict, Any, Tuple, List, Optional


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
    def generar_codigo_grupo_sugerido(self, accion_id: str, fecha_inicio=None):
        """Compatibilidad: wrapper para obtener sugerido simple."""
        try:
            fecha_ref = fecha_inicio or date.today()
            codigo, error = self.generar_codigo_grupo_sugerido_correlativo(accion_id, fecha_ref)
            return codigo, error
        except Exception as e:
            return None, str(e)
        
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
   
    def construir_horario_fundae(self, manana_inicio, manana_fin, tarde_inicio, tarde_fin, dias_seleccionados):
        """Construye string de horario en formato FUNDAE."""
        if not dias_seleccionados:
            return ""
    
        dias_str = "".join(dias_seleccionados)
        horarios = []
    
        if manana_inicio and manana_fin:
            horarios.append(f"{manana_inicio} - {manana_fin}")
    
        if tarde_inicio and tarde_fin:
            horarios.append(f"{tarde_inicio} - {tarde_fin}")
    
        if not horarios:
            return ""
    
        horarios_str = " y ".join(horarios)
        return f"Días: {dias_str} | Horario: {horarios_str}"

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
            
    def get_empresas_centro_gestor_disponibles(self) -> Dict[str, str]:
        """Obtiene empresas marcadas como centro gestor según jerarquía."""
        try:
            if self.rol == "admin":
                query = self.supabase.table("empresas").select("id, nombre").eq("es_centro_gestor", True)
            elif self.rol == "gestor" and self.empresa_id:
                # Gestor: su empresa + clientes que sean centro gestor
                empresas_permitidas = [self.empresa_id]
                clientes = self.supabase.table("empresas").select("id").eq("empresa_matriz_id", self.empresa_id).execute()
                empresas_permitidas.extend([c["id"] for c in (clientes.data or [])])
                
                query = self.supabase.table("empresas").select("id, nombre").eq("es_centro_gestor", True).in_("id", empresas_permitidas)
            else:
                return {}
            
            res = query.order("nombre").execute()
            return {emp["nombre"]: emp["id"] for emp in (res.data or [])}
        
        except Exception as e:
            st.error(f"Error cargando centros gestores: {e}")
            return {}
    
    def get_centro_gestor_empresa(self, grupo_id: str) -> dict:
        """Obtiene empresa asignada como centro gestor del grupo."""
        try:
            res = self.supabase.table("grupos").select(
                "centro_gestor_empresa_id, centro_empresa:empresas!centro_gestor_empresa_id(nombre, cif)"
            ).eq("id", grupo_id).execute()
            
            if res.data and res.data[0].get("centro_gestor_empresa_id"):
                return res.data[0]["centro_empresa"]
            return None
        except Exception as e:
            return None
    
    def asignar_empresa_como_centro_gestor(self, grupo_id: str, empresa_id: str) -> bool:
        """Asigna una empresa como centro gestor del grupo."""
        try:
            self.supabase.table("grupos").update({
                "centro_gestor_empresa_id": empresa_id,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", grupo_id).execute()
            return True
        except Exception as e:
            st.error(f"Error asignando centro gestor: {e}")
            return False
    
    def quitar_centro_gestor(self, grupo_id: str) -> bool:
        """Quita el centro gestor del grupo."""
        try:
            self.supabase.table("grupos").update({
                "centro_gestor_empresa_id": None,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", grupo_id).execute()
            return True
        except Exception as e:
            st.error(f"Error quitando centro gestor: {e}")
            return False
        
    def determinar_empresa_gestora_responsable(self, accion_formativa_id, empresa_propietaria_id):
        """
        CORREGIDO: Maneja correctamente valores None y strings "None".
        Determina qué empresa es responsable ante FUNDAE según jerarquía.
        """
        try:
            # CORRECCIÓN: Validar empresa_propietaria_id
            empresa_prop_valida = None
            if empresa_propietaria_id and str(empresa_propietaria_id).lower() != "none":
                try:
                    # Validar que sea un UUID válido
                    uuid.UUID(str(empresa_propietaria_id))
                    empresa_prop_valida = str(empresa_propietaria_id)
                except (ValueError, TypeError):
                    empresa_prop_valida = None

            # Obtener empresa de la acción formativa
            accion_res = self.supabase.table("acciones_formativas").select(
                "empresa_id"
            ).eq("id", accion_formativa_id).execute()
    
            if not accion_res.data:
                return None, "Acción formativa no encontrada"
    
            empresa_accion_id = accion_res.data[0]["empresa_id"]
    
            # Obtener información de la empresa de la acción
            empresa_res = self.supabase.table("empresas").select(
                "id, nombre, cif, tipo_empresa, empresa_matriz_id"
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
    
            # Si es cliente SaaS, usar la empresa propietaria del grupo (CORREGIDA)
            elif empresa_accion["tipo_empresa"] == "CLIENTE_SAAS":
                if empresa_prop_valida:
                    try:
                        propietaria_res = self.supabase.table("empresas").select("*").eq("id", empresa_prop_valida).execute()
                        if propietaria_res.data:
                            return propietaria_res.data[0], ""
                    except Exception as e:
                        # Si falla, usar la empresa de la acción como fallback
                        pass
                return empresa_accion, ""  # Fallback a la empresa de la acción
    
            return empresa_accion, ""
    
        except Exception as e:
            return None, f"Error al determinar empresa responsable: {e}"

    def generar_codigo_grupo_sugerido_correlativo(self, accion_formativa_id, fecha_inicio=None):
        """         
        CORREGIDO: Maneja correctamente admin vs gestor y empresa gestora vs propietaria.
        """
        try:
            # Año de referencia
            if fecha_inicio:
                if isinstance(fecha_inicio, str):
                    ano = datetime.fromisoformat(str(fecha_inicio).replace('Z', '+00:00')).year
                else:
                    ano = fecha_inicio.year
            else:
                ano = date.today().year

            # Obtener información de la acción formativa
            accion_res = self.supabase.table("acciones_formativas").select(
                "codigo_accion, empresa_id, nombre"
            ).eq("id", accion_formativa_id).execute()
        
            if not accion_res.data:
                return None, "Acción formativa no encontrada"

            accion_data = accion_res.data[0]
            empresa_gestora_accion = accion_data["empresa_id"]
        
            # 🔧 CORRECCIÓN: Para FUNDAE, lo que importa es la empresa gestora de la ACCIÓN
            # No la empresa propietaria del grupo (que puede ser diferente)
            empresa_para_validacion = empresa_gestora_accion

            # Obtener todos los grupos de esta acción en este año
            res = self.supabase.table("grupos").select("""
             codigo_grupo, fecha_inicio, empresa_id,
             accion_formativa:acciones_formativas(empresa_id)
            """).eq("accion_formativa_id", accion_formativa_id).gte(
            "fecha_inicio", f"{ano}-01-01"
            ).lt("fecha_inicio", f"{ano + 1}-01-01").execute()

            # Recopilar códigos usados de la MISMA empresa gestora de la acción
            usados = set()
            for grupo in (res.data or []):
                # La empresa gestora siempre es la de la acción formativa
                accion_formativa_grupo = grupo.get("accion_formativa", {})
                empresa_gestora_grupo = accion_formativa_grupo.get("empresa_id")
            
                # Solo considerar grupos de la misma empresa gestora
                if empresa_gestora_grupo == empresa_para_validacion:
                    try:
                        codigo = str(grupo.get("codigo_grupo", "")).strip()
                        if codigo.isdigit():
                            usados.add(int(codigo))
                    except (ValueError, TypeError, AttributeError):
                        continue

            # Encontrar siguiente número disponible
            n = 1
            while n in usados:
                n += 1

            return str(n), ""
        
        except Exception as e:
            return None, f"Error al generar código correlativo: {e}"

            
    def get_codigo_accion_numerico(self, accion_formativa_id):
        """
        Obtiene el código numérico de la acción formativa para mostrar al usuario.
        """
        try:
            accion_res = self.supabase.table("acciones_formativas").select(
                "codigo_accion"
            ).eq("id", accion_formativa_id).execute()
            
            if accion_res.data:
                return str(accion_res.data[0]["codigo_accion"])
            return "?"
        except:
            return "?"

    def generar_display_codigo_completo(self, accion_formativa_id, codigo_grupo):
        """
        Genera el código completo para mostrar al usuario: "1-1", "2-3", etc.
        """
        try:
            codigo_accion = self.get_codigo_accion_numerico(accion_formativa_id)
            return f"{codigo_accion}-{codigo_grupo}"
        except:
            return f"?-{codigo_grupo}"
    
    def validar_codigo_grupo_correlativo(self, codigo_grupo, accion_formativa_id, fecha_inicio, grupo_id=None):
        """
        Valida que el 'codigo_grupo' sea numérico y único para acción/empresa_gestora/año.
        """
        try:
            if not codigo_grupo or not str(codigo_grupo).strip().isdigit():
                return False, "El código de grupo debe ser numérico"
    
            # Delegamos en utils con la FIRMA CORRECTA
            ok, msg = validar_codigo_grupo_fundae(self.supabase, str(codigo_grupo).strip(), accion_formativa_id, grupo_id)
            return ok, msg
        except Exception as e:
            return False, f"Error al validar código correlativo: {e}"

    def validar_numero_correlativo_disponible(self, accion_formativa_id, numero_grupo, fecha_inicio):
        """
        Comprueba si un número concreto está disponible para esa acción/año.
        """
        try:
            codigo = str(numero_grupo).strip()
            fecha_ref = fecha_inicio or date.today()
            return self.validar_codigo_grupo_correlativo(codigo, accion_formativa_id, fecha_ref)
        except Exception as e:
            return False, f"Error al validar número correlativo: {e}"
    
    def obtener_siguiente_numero_grupo(self, accion_formativa_id, fecha_inicio):
        """
        Devuelve el siguiente número disponible (int) o error.
        """
        try:
            codigo_sugerido, error = self.generar_codigo_grupo_sugerido_correlativo(accion_formativa_id, fecha_inicio)
            if error:
                return None, error
            return int(codigo_sugerido), ""
        except Exception as e:
            return None, f"Error al obtener siguiente número: {e}"
    
    def generar_rango_codigos_disponibles(self, accion_formativa_id, fecha_inicio, cantidad=5):
        """
        Genera una lista de opciones con números disponibles para la UI.
        """
        try:
            inicio, error = self.obtener_siguiente_numero_grupo(accion_formativa_id, fecha_inicio)
            if error:
                return [], error
    
            opciones = []
            for i in range(inicio, inicio + cantidad):
                disponible, _ = self.validar_numero_correlativo_disponible(accion_formativa_id, i, fecha_inicio)
                opciones.append({
                    "numero": i,
                    "codigo": str(i),
                    "disponible": disponible
                })
            return opciones, ""
        except Exception as e:
            return [], f"Error al generar rango de códigos: {e}"
        
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
    # MÉTODOS NUEVOS PARA COSTES POR EMPRESA
    # Agregar al final de la clase GruposService en grupos_service.py
    # =========================
    
    def get_empresa_costes(self, empresa_grupo_id: str) -> Dict[str, Any]:
        """Obtiene costes de una empresa específica en un grupo."""
        try:
            empresa_grupo_id_limpio = validar_uuid_seguro(empresa_grupo_id)
            if not empresa_grupo_id_limpio:
                return {}
            
            res = self.supabase.table("empresa_grupo_costes").select("*").eq("empresa_grupo_id", empresa_grupo_id_limpio).execute()
            return res.data[0] if res.data else {}
        except Exception as e:
            st.error(f"Error al cargar costes de empresa: {e}")
            return {}
    
    def create_empresa_coste(self, datos_coste: Dict[str, Any]) -> bool:
        """Crea registro de costes para una empresa en un grupo."""
        try:
            datos_coste["created_at"] = datetime.utcnow().isoformat()
            datos_coste["updated_at"] = datetime.utcnow().isoformat()
            self.supabase.table("empresa_grupo_costes").insert(datos_coste).execute()
            return True
        except Exception as e:
            st.error(f"Error al crear costes de empresa: {e}")
            return False
    
    def update_empresa_coste(self, empresa_grupo_id: str, datos_coste: Dict[str, Any]) -> bool:
        """Actualiza costes de una empresa en un grupo."""
        try:
            empresa_grupo_id_limpio = validar_uuid_seguro(empresa_grupo_id)
            if not empresa_grupo_id_limpio:
                return False
                
            datos_coste["updated_at"] = datetime.utcnow().isoformat()
            self.supabase.table("empresa_grupo_costes").update(datos_coste).eq("empresa_grupo_id", empresa_grupo_id_limpio).execute()
            return True
        except Exception as e:
            st.error(f"Error al actualizar costes de empresa: {e}")
            return False
    
    def delete_empresa_coste(self, empresa_grupo_id: str) -> bool:
        """Elimina costes de una empresa en un grupo."""
        try:
            empresa_grupo_id_limpio = validar_uuid_seguro(empresa_grupo_id)
            if not empresa_grupo_id_limpio:
                return False
                
            self.supabase.table("empresa_grupo_costes").delete().eq("empresa_grupo_id", empresa_grupo_id_limpio).execute()
            return True
        except Exception as e:
            st.error(f"Error al eliminar costes de empresa: {e}")
            return False

    # =========================
    # MÉTODOS PARA BONIFICACIONES POR EMPRESA
    # =========================
    
    def get_empresa_bonificaciones(self, empresa_grupo_id: str) -> pd.DataFrame:
        """Obtiene bonificaciones de una empresa específica en un grupo."""
        try:
            empresa_grupo_id_limpio = validar_uuid_seguro(empresa_grupo_id)
            if not empresa_grupo_id_limpio:
                return pd.DataFrame()
            
            res = self.supabase.table("empresa_grupo_bonificaciones").select("*").eq("empresa_grupo_id", empresa_grupo_id_limpio).order("mes").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            st.error(f"Error al cargar bonificaciones de empresa: {e}")
            return pd.DataFrame()
    
    def create_empresa_bonificacion(self, datos_bonif: Dict[str, Any]) -> bool:
        """Crea una bonificación mensual para una empresa en un grupo."""
        try:
            # Validar empresa_grupo_id
            empresa_grupo_id_limpio = validar_uuid_seguro(datos_bonif.get("empresa_grupo_id"))
            if not empresa_grupo_id_limpio:
                st.error("ID de empresa-grupo no válido")
                return False
            
            datos_bonif["empresa_grupo_id"] = empresa_grupo_id_limpio
            datos_bonif["id"] = str(uuid.uuid4())
            datos_bonif["created_at"] = datetime.utcnow().isoformat()
            
            self.supabase.table("empresa_grupo_bonificaciones").insert(datos_bonif).execute()
            return True
        except Exception as e:
            st.error(f"Error al crear bonificación de empresa: {e}")
            return False
    
    def update_empresa_bonificacion(self, bonificacion_id: str, datos_edit: Dict[str, Any]) -> bool:
        """Actualiza una bonificación mensual de una empresa."""
        try:
            bonificacion_id_limpio = validar_uuid_seguro(bonificacion_id)
            if not bonificacion_id_limpio:
                return False
                
            datos_edit["updated_at"] = datetime.utcnow().isoformat()
            self.supabase.table("empresa_grupo_bonificaciones").update(datos_edit).eq("id", bonificacion_id_limpio).execute()
            return True
        except Exception as e:
            st.error(f"Error al actualizar bonificación de empresa: {e}")
            return False
    
    def delete_empresa_bonificacion(self, bonificacion_id: str) -> bool:
        """Elimina una bonificación de una empresa."""
        try:
            bonificacion_id_limpio = validar_uuid_seguro(bonificacion_id)
            if not bonificacion_id_limpio:
                return False
                
            self.supabase.table("empresa_grupo_bonificaciones").delete().eq("id", bonificacion_id_limpio).execute()
            return True
        except Exception as e:
            st.error(f"Error al eliminar bonificación de empresa: {e}")
            return False
    
    # =========================
    # VALIDACIONES Y ESTADÍSTICAS POR EMPRESA
    # =========================
    
    def validar_limites_bonificacion_empresa(self, empresa_grupo_id: str, mes: int, importe: float, bonificacion_id: str = None) -> Tuple[bool, str]:
        """
        Valida que una bonificación no supere los límites de la empresa específica.
        
        Args:
            empresa_grupo_id: ID de la relación empresa-grupo
            mes: Mes de la bonificación (1-12)
            importe: Importe a validar
            bonificacion_id: ID de bonificación existente (para edición)
        
        Returns:
            Tuple (es_válido, mensaje_error)
        """
        try:
            empresa_grupo_id_limpio = validar_uuid_seguro(empresa_grupo_id)
            if not empresa_grupo_id_limpio:
                return False, "ID de empresa-grupo no válido"
            
            # 1. Obtener costes de esta empresa
            costes_empresa = self.get_empresa_costes(empresa_grupo_id_limpio)
            total_costes = float(costes_empresa.get("total_costes_formacion", 0))
            
            if total_costes <= 0:
                return False, "Esta empresa no tiene costes definidos"
            
            # 2. Obtener bonificaciones existentes de esta empresa
            df_bonif = self.get_empresa_bonificaciones(empresa_grupo_id_limpio)
            
            # Excluir bonificación actual si estamos editando
            if bonificacion_id:
                df_bonif = df_bonif[df_bonif["id"] != bonificacion_id]
            
            # 3. Calcular total bonificado (excluyendo el mes actual)
            total_bonificado_otros_meses = df_bonif[df_bonif["mes"] != mes]["importe"].sum() if not df_bonif.empty else 0
            
            # 4. Calcular disponible para este importe
            disponible = total_costes - float(total_bonificado_otros_meses)
            
            if importe > disponible:
                return False, f"Importe ({importe:.2f}€) supera el disponible ({disponible:.2f}€) para esta empresa"
            
            # 5. Validar que el mes no esté ocupado por otra bonificación
            mes_ocupado = not df_bonif[df_bonif["mes"] == mes].empty
            if mes_ocupado:
                return False, f"Ya existe una bonificación para el mes {mes} en esta empresa"
            
            return True, ""
            
        except Exception as e:
            return False, f"Error al validar bonificación: {e}"
    
    def get_estadisticas_empresa_grupo(self, empresa_grupo_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas completas de una empresa específica en un grupo."""
        try:
            empresa_grupo_id_limpio = validar_uuid_seguro(empresa_grupo_id)
            if not empresa_grupo_id_limpio:
                return {}
            
            # Información de la empresa en el grupo
            empresa_info = self.supabase.table("empresas_grupos").select("""
                id, fecha_asignacion,
                empresa:empresas(id, nombre, cif, tipo_empresa)
            """).eq("id", empresa_grupo_id_limpio).execute()
            
            if not empresa_info.data:
                return {}
            
            empresa_data = empresa_info.data[0]
            
            # Costes de la empresa
            costes_empresa = self.get_empresa_costes(empresa_grupo_id_limpio)
            total_costes = float(costes_empresa.get("total_costes_formacion", 0))
            
            # Bonificaciones de la empresa
            df_bonif_empresa = self.get_empresa_bonificaciones(empresa_grupo_id_limpio)
            total_bonificado = float(df_bonif_empresa["importe"].sum()) if not df_bonif_empresa.empty else 0.0
            
            # Disponible
            disponible = total_costes - total_bonificado
            
            # Meses con bonificación
            meses_con_bonificacion = df_bonif_empresa["mes"].tolist() if not df_bonif_empresa.empty else []
            meses_disponibles = [m for m in range(1, 13) if m not in meses_con_bonificacion]
            
            return {
                "empresa_grupo_id": empresa_grupo_id_limpio,
                "empresa": empresa_data["empresa"],
                "fecha_asignacion": empresa_data["fecha_asignacion"],
                "costes": costes_empresa,
                "total_costes": total_costes,
                "total_bonificado": total_bonificado,
                "disponible": disponible,
                "porcentaje_bonificado": (total_bonificado / total_costes * 100) if total_costes > 0 else 0,
                "bonificaciones": df_bonif_empresa.to_dict("records") if not df_bonif_empresa.empty else [],
                "meses_con_bonificacion": meses_con_bonificacion,
                "meses_disponibles": meses_disponibles,
                "tiene_costes": bool(costes_empresa),
                "puede_bonificar": total_costes > 0 and len(meses_disponibles) > 0 and disponible > 0
            }
            
        except Exception as e:
            st.error(f"Error al obtener estadísticas de empresa: {e}")
            return {}
    
    def get_resumen_todas_empresas_grupo(self, grupo_id: str) -> Dict[str, Any]:
        """
        Obtiene resumen consolidado de todas las empresas de un grupo.
        Útil para reportes y validaciones generales.
        """
        try:
            grupo_id_limpio = validar_uuid_seguro(grupo_id)
            if not grupo_id_limpio:
                return {}
            
            # Obtener todas las empresas del grupo
            empresas_grupo = self.supabase.table("empresas_grupos").select("id").eq("grupo_id", grupo_id_limpio).execute()
            
            if not empresas_grupo.data:
                return {"empresas": [], "totales": {"costes": 0, "bonificado": 0, "disponible": 0}}
            
            resumen_empresas = []
            totales = {"costes": 0, "bonificado": 0, "disponible": 0, "empresas_count": 0}
            
            for empresa_grupo in empresas_grupo.data:
                estadisticas = self.get_estadisticas_empresa_grupo(empresa_grupo["id"])
                
                if estadisticas:
                    resumen_empresas.append(estadisticas)
                    totales["costes"] += estadisticas["total_costes"]
                    totales["bonificado"] += estadisticas["total_bonificado"]
                    totales["disponible"] += estadisticas["disponible"]
                    totales["empresas_count"] += 1
            
            return {
                "grupo_id": grupo_id_limpio,
                "empresas": resumen_empresas,
                "totales": totales,
                "empresas_con_costes": len([e for e in resumen_empresas if e["tiene_costes"]]),
                "empresas_pueden_bonificar": len([e for e in resumen_empresas if e["puede_bonificar"]])
            }
            
        except Exception as e:
            st.error(f"Error al obtener resumen de todas las empresas: {e}")
            return {}
    
    # =========================
    # LIMPIAR CACHE CON NUEVOS MÉTODOS
    # =========================
    
    def limpiar_cache_grupos_empresa(self):
        """Limpia caches relacionados con costes y bonificaciones por empresa."""
        try:
            # Cache original
            self.limpiar_cache_grupos()
            
            # Aquí se podrían añadir caches específicos de empresa cuando se implementen
            # por ejemplo: @st.cache_data para get_empresa_costes, etc.
            
        except Exception:
            # Fallar silenciosamente
            pass
        
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
    def get_grupos_completos(_self) -> pd.DataFrame:
        """Obtiene grupos con información completa."""
        try:
            query = _self.supabase.table("grupos").select("""
                id, codigo_grupo, fecha_inicio, fecha_fin, fecha_fin_prevista,
                modalidad, horario, localidad, provincia, cp, lugar_imparticion,
                n_participantes_previstos, n_participantes_finalizados,
                n_aptos, n_no_aptos, observaciones, empresa_id, created_at,
                empresa:empresas!fk_grupo_empresa (id, nombre, cif),
                accion_formativa:acciones_formativas!fk_grupo_accion (id, nombre, modalidad, num_horas, codigo_accion)
            """)
            query = _self._apply_empresa_filter(query, "grupos")

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
            return _self._handle_query_error("cargar grupos completos", e)

    @st.cache_data(ttl=600)
    def get_grupos_dict(_self) -> Dict[str, str]:
        """Devuelve diccionario de grupos: código -> id."""
        try:
            df = _self.get_grupos_completos()
            return {row["codigo_grupo"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}
        except Exception as e:
            st.error(f"Error al cargar grupos dict: {e}")
            return {}
        
    @st.cache_data(ttl=600)
    def get_grupos_dict_por_empresa(_self, empresa_id: str) -> Dict[str, str]:
        """Devuelve grupos de una empresa específica: código -> id."""
        try:
            df = _self.get_grupos_completos()
            if df.empty:
                return {}
    
            # Filtrar por empresa_id
            df_empresa = df[df["empresa_id"] == empresa_id]
            return {row["codigo_grupo"]: row["id"] for _, row in df_empresa.iterrows()}
    
        except Exception as e:
            st.error(f"Error al cargar grupos de empresa {empresa_id}: {e}")
            return {}
    
    @st.cache_data(ttl=600)
    def get_grupos_acciones(_self) -> pd.DataFrame:
        """Obtiene listado de grupos de acciones (catálogo auxiliar)."""
        try:
            res = _self.supabase.table("grupos_acciones").select("id, nombre, codigo, cod_area_profesional").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar grupos de acciones", e)
        
    @st.cache_data(ttl=600)
    def get_empresas_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario de empresas: nombre -> id."""
        try:
            result = _self.supabase.table("empresas").select("id, nombre").execute()
        
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
    def get_acciones_formativas(_self) -> pd.DataFrame:
        """Obtiene acciones formativas según el rol."""
        try:
            query = _self.supabase.table("acciones_formativas").select("*")
            query = _self._apply_empresa_filter(query, "acciones_formativas")
        
            res = query.order("nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar acciones formativas", e)

    def get_acciones_dict(self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de acciones."""
        df = self.get_acciones_formativas()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    @st.cache_data(ttl=3600)
    def get_provincias(_self) -> list:
        """Devuelve listado de provincias ordenadas alfabéticamente."""
        try:
            res = _self.supabase.table("provincias").select("id, nombre").order("nombre").execute()
            return res.data or []
        except Exception as e:
            st.error(f"Error al cargar provincias: {e}")
            return []

    @st.cache_data(ttl=3600) 
    def get_localidades_por_provincia(_self, provincia_id: int) -> list:
        """Devuelve listado de localidades de una provincia."""
        try:
            res = _self.supabase.table("localidades").select("id, nombre").eq("provincia_id", provincia_id).order("nombre").execute()
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
    # ÁREAS PROFESIONALES Y GRUPOS DE ACCIONES
    # =========================
    @st.cache_data(ttl=3600)
    def get_areas_profesionales(_self) -> pd.DataFrame:
        """Obtiene áreas profesionales."""
        try:
            res = _self.supabase.table("areas_profesionales").select("*").order("familia").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar áreas profesionales", e)

    def get_areas_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario de áreas profesionales."""
        df = _self.get_areas_profesionales()
        return {
            f"{row['codigo']} - {row['nombre']}": row['codigo'] 
            for _, row in df.iterrows()
        } if not df.empty else {}

    @st.cache_data(ttl=3600)
    def get_grupos_acciones(_self) -> pd.DataFrame:
        """Obtiene grupos de acciones."""
        try:
            res = _self.supabase.table("grupos_acciones").select("*").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar grupos de acciones", e)
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
    def get_empresas_grupo(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene empresas participantes de un grupo."""
        try:
            res = _self.supabase.table("empresas_grupos").select("""
                id, fecha_asignacion,
                empresa:empresas(id, nombre, cif)
            """).eq("grupo_id", grupo_id).order("fecha_asignacion").execute()
        
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar empresas de grupo", e)

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
    def get_tutores_grupo(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene tutores asignados a un grupo."""
        try:
            res = _self.supabase.table("tutores_grupos").select("""
                id, fecha_asignacion,
                tutor:tutores(id, nombre, apellidos, email, telefono, especialidad, empresa_id)
            """).eq("grupo_id", grupo_id).order("fecha_asignacion").execute()
        
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar tutores de grupo", e)

    def get_tutores_disponibles_jerarquia(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene tutores disponibles según jerarquía empresarial."""
        try:
            # Validar parámetros de entrada
            if not grupo_id or grupo_id == "None":
                return pd.DataFrame()
            
            # Validar rol y empresa para gestores
            if self.rol == "gestor" and not self.empresa_id:
                return pd.DataFrame()  # Gestor sin empresa asignada
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
    def get_participantes_grupo(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene participantes asignados a un grupo."""
        try:
            res = _self.supabase.table("participantes_grupos").select("""
                id, fecha_asignacion,
                participante:participantes(id, nif, nombre, apellidos, email, telefono, empresa_id)
            """).eq("grupo_id", grupo_id).order("fecha_asignacion").execute()
        
            df = pd.DataFrame(res.data or [])
            
            # Renombrar id → relacion_id para evitar conflictos
            if not df.empty:
                df.rename(columns={"id": "relacion_id"}, inplace=True)
    
                if "participante" in df.columns:
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
            return _self._handle_query_error("cargar participantes de grupo", e)
    
    
    def get_participantes_disponibles_jerarquia(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene participantes disponibles según jerarquía empresarial."""
        try:
            # Validar parámetros de entrada
            if not grupo_id or grupo_id == "None":
                return pd.DataFrame()
            
            if self.rol == "gestor" and not self.empresa_id:
                return pd.DataFrame()  # Gestor sin empresa asignada
    
            # Participantes ya asignados
            participantes_asignados = self.supabase.table("participantes_grupos") \
                .select("participante_id").eq("grupo_id", grupo_id).execute()
            participantes_asignados_ids = [p["participante_id"] for p in (participantes_asignados.data or [])]
    
            # Empresas participantes del grupo
            empresas_grupo = self.supabase.table("empresas_grupos").select("empresa_id").eq("grupo_id", grupo_id).execute()
            empresas_ids = [e["empresa_id"] for e in (empresas_grupo.data or [])]
    
            # Empresa propietaria
            grupo_info = self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
            if grupo_info.data:
                empresas_ids.append(grupo_info.data[0]["empresa_id"])
    
            if not empresas_ids:
                return pd.DataFrame()
    
            # Participantes de empresas participantes
            query = self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, email, telefono, empresa_id,
                empresa:empresas(nombre)
            """).in_("empresa_id", empresas_ids)
    
            # Filtro por rol
            if self.rol == "gestor" and self.empresa_id:
                query = query.or_(f"empresa_id.eq.{self.empresa_id},empresa.empresa_matriz_id.eq.{self.empresa_id}")
    
            res = query.execute()
            df = pd.DataFrame(res.data or [])
    
            if not df.empty:
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
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
    def get_centro_gestor_grupo(_self, grupo_id: str) -> Dict[str, Any]:
        """Obtiene el centro gestor asignado a un grupo."""
        try:
            res = _self.supabase.table("centros_gestores_grupos").select("""
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
            
    @st.cache_data(ttl=300)
    def get_grupo_costes(_self, grupo_id: str) -> Dict[str, Any]:
        """Obtiene costes de un grupo específico."""
        try:
            res = _self.supabase.table("grupo_costes").select("*").eq("grupo_id", grupo_id).execute()
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
    def get_grupo_bonificaciones(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene bonificaciones de un grupo."""
        try:
            grupo_id_limpio = validar_uuid_seguro(grupo_id)
            if not grupo_id_limpio:
                st.error("❌ ID de grupo no válido para cargar bonificaciones")
                return pd.DataFrame()
    
            res = (
                _self.supabase.table("grupo_bonificaciones")
                .select("*")
                .eq("grupo_id", grupo_id_limpio)
                .order("mes")
                .execute()
            )
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar bonificaciones de grupo", e)
    
    
    def create_grupo_bonificacion(self, datos_bonif: Dict[str, Any]) -> bool:
        """Crea una bonificación mensual para un grupo."""
        try:
            datos_bonif["id"] = str(uuid.uuid4())  # 🔑 generar UUID válido
            datos_bonif["created_at"] = datetime.utcnow().isoformat()
    
            self.supabase.table("grupo_bonificaciones").insert(datos_bonif).execute()
    
            # Limpiar cache
            if hasattr(self, "get_grupo_bonificaciones"):
                self.get_grupo_bonificaciones.clear()
    
            return True
        except Exception as e:
            st.error(f"❌ Error al crear bonificación de grupo: {e}")
            return False
    
    
    def update_grupo_bonificacion(self, bonificacion_id: str, datos_edit: Dict[str, Any]) -> bool:
        """Actualiza una bonificación mensual de un grupo."""
        try:
            datos_edit["updated_at"] = datetime.utcnow().isoformat()
    
            self.supabase.table("grupo_bonificaciones").update(datos_edit).eq("id", bonificacion_id).execute()
    
            # Limpiar cache
            if hasattr(self, "get_grupo_bonificaciones"):
                self.get_grupo_bonificaciones.clear()
    
            return True
        except Exception as e:
            st.error(f"❌ Error al actualizar bonificación: {e}")
            return False
    
    
    def delete_grupo_bonificacion(self, bonificacion_id: str) -> bool:
        """Elimina una bonificación de un grupo."""
        try:
            self.supabase.table("grupo_bonificaciones").delete().eq("id", bonificacion_id).execute()
    
            # Limpiar cache
            if hasattr(self, "get_grupo_bonificaciones"):
                self.get_grupo_bonificaciones.clear()
    
            return True
        except Exception as e:
            st.error(f"❌ Error al eliminar bonificación: {e}")
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
# FACTORY FUNCTION
# =========================

def get_grupos_service(supabase, session_state) -> GruposService:
    """Factory function para obtener instancia del servicio de grupos."""
    return GruposService(supabase, session_state)
