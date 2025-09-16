import streamlit as st
import pandas as pd
from datetime import datetime, time
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
                accion_formativa:acciones_formativas(id, nombre, modalidad, num_horas),
                empresa:empresas(id, nombre)
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
            return _self._handle_query_error("cargar grupos", e)

    def get_acciones_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario de acciones formativas: nombre -> id."""
        try:
            query = _self.supabase.table("acciones_formativas").select("id, nombre")
            query = _self._apply_empresa_filter(query, "acciones_formativas")
            
            result = query.execute()
            
            if result.data:
                return {item["nombre"]: item["id"] for item in result.data}
            return {}
        except Exception as e:
            st.error(f"Error al cargar acciones: {e}")
            return {}
            
    @st.cache_data(ttl=600)
    def get_areas_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario de áreas profesionales: nombre -> código."""
        try:
            res = _self.supabase.table("areas_profesionales").select("codigo, nombre").order("nombre").execute()
            if res.data:
                return {item["nombre"]: item["codigo"] for item in res.data}
            return {}
        except Exception as e:
            st.error(f"Error al cargar áreas profesionales: {e}")
            return {}
        
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
    @st.cache_data(ttl=600)
    def get_acciones_formativas(_self) -> pd.DataFrame:
        """Obtiene listado completo de acciones formativas."""
        try:
            query = _self.supabase.table("acciones_formativas").select("""
                id, nombre, descripcion, objetivos, contenidos, requisitos,
                horas, modalidad, fecha_inicio, fecha_fin, empresa_id,
                created_at, num_horas, observaciones, codigo_accion, 
                area_profesional, nivel, certificado_profesionalidad,
                cod_area_profesional, sector, duracion_horas, certificado
            """)
            query = _self._apply_empresa_filter(query, "acciones_formativas")
            res = query.order("created_at", desc=True).execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar acciones formativas", e)
            
    # =========================
    # GRUPOS - OPERACIONES CRUD
    # =========================

    def create_grupo_completo(self, datos_grupo: Dict[str, Any], tutores_ids: List[str] = None, empresas_ids: List[str] = None) -> Tuple[bool, str]:
        """Crea un grupo completo con todas sus relaciones."""
        try:
            # Asignar empresa según rol
            if self.rol == "gestor":
                datos_grupo["empresa_id"] = self.empresa_id
            
            datos_grupo["created_at"] = datetime.utcnow().isoformat()
            datos_grupo["updated_at"] = datetime.utcnow().isoformat()
            
            res = self.supabase.table("grupos").insert(datos_grupo).execute()
            
            if not res.data:
                return False, ""
            
            grupo_id = res.data[0]["id"]
            
            # Asignar tutores
            if tutores_ids:
                for tutor_id in tutores_ids:
                    self.create_tutor_grupo(grupo_id, tutor_id)
            
            # Asignar empresas participantes
            if empresas_ids:
                for empresa_id in empresas_ids:
                    self.create_empresa_grupo(grupo_id, empresa_id)
            
            # Si es gestor, asignar su empresa automáticamente
            if self.rol == "gestor":
                self.create_empresa_grupo(grupo_id, self.empresa_id)
            
            # Limpiar cache
            self.limpiar_cache_grupos()
            
            return True, grupo_id
        except Exception as e:
            st.error(f"Error al crear grupo completo: {e}")
            return False, ""

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
            
    def delete_grupo(self, grupo_id: str) -> bool:
        """Elimina un grupo y todas sus relaciones."""
        try:
            # CORRECCIÓN: Verificar dependencias en tabla correcta
            participantes = self.supabase.table("participantes_grupos").select("id").eq("grupo_id", grupo_id).execute()
            if participantes.data:
                st.error("No se puede eliminar. El grupo tiene participantes asignados.")
                return False
    
            # Eliminar relaciones
            self.supabase.table("tutores_grupos").delete().eq("grupo_id", grupo_id).execute()
            self.supabase.table("empresas_grupos").delete().eq("grupo_id", grupo_id).execute()
            self.supabase.table("participantes_grupos").delete().eq("grupo_id", grupo_id).execute()  # AÑADIDO
            self.supabase.table("centros_gestores_grupos").delete().eq("grupo_id", grupo_id).execute()
            self.supabase.table("grupo_costes").delete().eq("grupo_id", grupo_id).execute()
            self.supabase.table("grupo_bonificaciones").delete().eq("grupo_id", grupo_id).execute()
            
            # Eliminar grupo
            self.supabase.table("grupos").delete().eq("id", grupo_id).execute()
            
            self.limpiar_cache_grupos()
            return True
        except Exception as e:
            st.error(f"Error al eliminar grupo: {e}")
            return False
    
    # =========================
    # TUTORES
    # =========================

    @st.cache_data(ttl=300)
    def get_tutores_completos(_self) -> pd.DataFrame:
        """Obtiene tutores con información completa."""
        try:
            query = _self.supabase.table("tutores").select("""
                id, nombre, apellidos, email, telefono, nif, tipo_tutor,
                direccion, ciudad, provincia, codigo_postal, cv_url, 
                especialidad, created_at, empresa_id,
                empresa:empresas(id, nombre)
            """)
            query = _self._apply_empresa_filter(query, "tutores")
            
            res = query.order("nombre").execute()
            df = pd.DataFrame(res.data or [])
            
            if not df.empty:
                # Añadir nombre_completo
                df["nombre_completo"] = df["nombre"].astype(str) + " " + df["apellidos"].fillna("").astype(str)
                df["nombre_completo"] = df["nombre_completo"].str.strip()
                
                # Aplanar empresa
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar tutores", e)

    @st.cache_data(ttl=300)
    @st.cache_data(ttl=300)
    def get_tutores_grupo(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene tutores asignados a un grupo con datos aplanados."""
        try:
            res = _self.supabase.table("tutores_grupos").select("""
                id, grupo_id, tutor_id, created_at,
                tutor:tutores!tutores_grupos_tutor_id_fkey(id, nombre, apellidos, email, especialidad)
            """).eq("grupo_id", grupo_id).execute()
    
            df = pd.DataFrame(res.data or [])
            if not df.empty and "tutor" in df.columns:
                df["tutor_nombre"] = df["tutor"].apply(
                    lambda x: f"{x.get('nombre','')} {x.get('apellidos','')}" if isinstance(x, dict) else ""
                )
                df["tutor_email"] = df["tutor"].apply(lambda x: x.get("email") if isinstance(x, dict) else "")
                df["tutor_especialidad"] = df["tutor"].apply(lambda x: x.get("especialidad") if isinstance(x, dict) else "")
            return df
        except Exception as e:
            return _self._handle_query_error("cargar tutores de grupo", e)

    def create_tutor_grupo(self, grupo_id: str, tutor_id: str) -> bool:
        """Asigna un tutor a un grupo."""
        try:
            self.supabase.table("tutores_grupos").insert({
                "grupo_id": grupo_id,
                "tutor_id": tutor_id,
                "fecha_asignacion": datetime.utcnow().isoformat()
            }).execute()
            return True
        except Exception as e:
            st.error(f"Error al asignar tutor: {e}")
            return False

    def delete_tutor_grupo(self, relacion_id: str) -> bool:
        """Elimina la relación tutor-grupo."""
        try:
            self.supabase.table("tutores_grupos").delete().eq("id", relacion_id).execute()
            return True
        except Exception as e:
            st.error(f"Error al eliminar tutor de grupo: {e}")
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

    @st.cache_data(ttl=600)
    def get_centros_para_grupo(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene centros disponibles según rol y empresas del grupo."""
        try:
            if _self.rol == "gestor":
                # Gestor: solo centros de su empresa
                query = _self.supabase.table("centros_gestores").select("*").eq("empresa_id", _self.empresa_id)
            else:
                # Admin: centros de empresas vinculadas al grupo
                empresas_grupo = _self.supabase.table("empresas_grupos").select("empresa_id").eq("grupo_id", grupo_id).execute()
                empresa_ids = [emp["empresa_id"] for emp in (empresas_grupo.data or [])]
                
                # Añadir empresa propietaria del grupo
                grupo_info = _self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                if grupo_info.data:
                    empresa_ids.append(grupo_info.data[0]["empresa_id"])
                
                if empresa_ids:
                    query = _self.supabase.table("centros_gestores").select("*").in_("empresa_id", empresa_ids)
                else:
                    query = _self.supabase.table("centros_gestores").select("*")
            
            res = query.order("razon_social").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar centros para grupo", e)

    def create_centro_gestor(self, empresa_id: str, datos: Dict[str, Any]) -> Tuple[bool, str]:
        """Crea un nuevo centro gestor."""
        try:
            datos["empresa_id"] = empresa_id
            datos["created_at"] = datetime.utcnow().isoformat()
            datos["updated_at"] = datetime.utcnow().isoformat()
            
            res = self.supabase.table("centros_gestores").insert(datos).execute()
            
            if res.data:
                centro_id = res.data[0]["id"]
                self.get_centros_para_grupo.clear()
                return True, centro_id
            return False, ""
        except Exception as e:
            st.error(f"Error al crear centro gestor: {e}")
            return False, ""

    def assign_centro_gestor_a_grupo(self, grupo_id: str, centro_id: str) -> bool:
        """Asigna un centro gestor a un grupo (upsert)."""
        try:
            datos = {
                "grupo_id": grupo_id,
                "centro_id": centro_id,
                "created_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("centros_gestores_grupos").upsert(datos, on_conflict="grupo_id").execute()
            self.get_centro_gestor_grupo.clear()
            return True
        except Exception as e:
            st.error(f"Error al asignar centro gestor: {e}")
            return False

    def unassign_centro_gestor_de_grupo(self, grupo_id: str) -> bool:
        """Elimina la asignación de centro gestor de un grupo."""
        try:
            self.supabase.table("centros_gestores_grupos").delete().eq("grupo_id", grupo_id).execute()
            self.get_centro_gestor_grupo.clear()
            return True
        except Exception as e:
            st.error(f"Error al desasignar centro gestor: {e}")
            return False

    # =========================
    # EMPRESAS
    # =========================
    @st.cache_data(ttl=300)
    def get_empresas_grupo(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene empresas asignadas a un grupo con datos aplanados."""
        try:
            res = _self.supabase.table("empresas_grupos").select("""
                id, grupo_id, empresa_id, fecha_asignacion,
                empresa:empresas(id, nombre, cif)
            """).eq("grupo_id", grupo_id).execute()
    
            df = pd.DataFrame(res.data or [])
            if not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else "")
                df["empresa_cif"] = df["empresa"].apply(lambda x: x.get("cif") if isinstance(x, dict) else "")
            return df
        except Exception as e:
            return _self._handle_query_error("cargar empresas de grupo", e)

    def create_empresa_grupo(self, grupo_id: str, empresa_id: str) -> bool:
        """Asigna una empresa a un grupo."""
        try:
            self.supabase.table("empresas_grupos").insert({
                "grupo_id": grupo_id,
                "empresa_id": empresa_id,
                "fecha_asignacion": datetime.utcnow().isoformat()
            }).execute()
            return True
        except Exception as e:
            st.error(f"Error al asignar empresa a grupo: {e}")
            return False

    def delete_empresa_grupo(self, relacion_id: str) -> bool:
        """Elimina la relación empresa-grupo."""
        try:
            self.supabase.table("empresas_grupos").delete().eq("id", relacion_id).execute()
            return True
        except Exception as e:
            st.error(f"Error al eliminar empresa de grupo: {e}")
            return False

    # =========================
    # PARTICIPANTES (1:N)
    # =========================
    @st.cache_data(ttl=300)
    @st.cache_data(ttl=300)
    def get_participantes_grupo(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene los participantes asignados a un grupo específico (N:N)."""
        try:
            query = (
                _self.supabase.table("participantes_grupos")
                .select("""
                    id, fecha_asignacion, 
                    participante:participantes(id, nif, nombre, apellidos, email, telefono)
                """)
                .eq("grupo_id", grupo_id)
            )
            res = query.order("fecha_asignacion", desc=True).execute()
        
            # Aplanar los datos de participante
            data = []
            for row in (res.data or []):
                participante = row.get("participante", {})
                if participante:
                    flat_row = {
                        "relacion_id": row.get("id"),
                        "fecha_asignacion": row.get("fecha_asignacion"),
                        **participante
                    }
                    data.append(flat_row)
        
            return pd.DataFrame(data)
        except Exception as e:
            return _self._handle_query_error("cargar participantes de grupo", e)

    @st.cache_data(ttl=300)
    def get_participantes_disponibles(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene participantes disponibles para asignar a un grupo (usa tabla intermedia)."""
        try:
            # Participantes ya asignados al grupo
            asignados_res = (
                _self.supabase.table("participantes_grupos")
                .select("participante_id")
                .eq("grupo_id", grupo_id)
                .execute()
            )
            asignados_ids = [row["participante_id"] for row in (asignados_res.data or [])]
    
            # Traer todos los participantes filtrados por empresa (si gestor)
            query = _self.supabase.table("participantes").select("*")
            query = _self._apply_empresa_filter(query, "participantes")
    
            res = query.order("nombre").execute()
            df = pd.DataFrame(res.data or [])
    
            # Excluir los ya asignados
            if not df.empty and asignados_ids:
                df = df[~df["id"].isin(asignados_ids)]
    
            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes disponibles", e)
            
    def asignar_participante_a_grupo(self, participante_id: str, grupo_id: str) -> bool:
        """Crea relación participante-grupo en la tabla intermedia (N:N)."""
        try:
            data = {
                "participante_id": participante_id,
                "grupo_id": grupo_id,
                "fecha_asignacion": datetime.now().isoformat()
            }
            self.supabase.table("participantes_grupos").insert(data).execute()
            self.get_participantes_grupo.clear()
            self.get_participantes_disponibles.clear()
            return True
        except Exception as e:
            st.error(f"Error al asignar participante: {e}")
            return False
    def desasignar_participante_de_grupo(self, relacion_id: str) -> bool:
        """Elimina la relación participante-grupo (tabla intermedia)."""
        try:
            self.supabase.table("participantes_grupos").delete().eq("id", relacion_id).execute()
            self.get_participantes_grupo.clear()
            self.get_participantes_disponibles.clear()
            return True
        except Exception as e:
            st.error(f"Error al desasignar participante: {e}")
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
            self.supabase.table("grupo_costes").insert(datos_coste).execute()
            self.get_grupo_costes.clear()
            return True
        except Exception as e:
            st.error(f"Error al crear costes de grupo: {e}")
            return False

    def update_grupo_coste(self, grupo_id: str, datos_coste: Dict[str, Any]) -> bool:
        """Actualiza costes de un grupo."""
        try:
            self.supabase.table("grupo_costes").update(datos_coste).eq("grupo_id", grupo_id).execute()
            self.get_grupo_costes.clear()
            return True
        except Exception as e:
            st.error(f"Error al actualizar costes de grupo: {e}")
            return False

    @st.cache_data(ttl=300)
    def get_grupo_bonificaciones(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene bonificaciones de un grupo."""
        try:
            res = _self.supabase.table("grupo_bonificaciones").select("*").eq("grupo_id", grupo_id).order("mes").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar bonificaciones de grupo", e)

    def create_grupo_bonificacion(self, datos_bonif: Dict[str, Any]) -> bool:
        """Crea una bonificación mensual para un grupo."""
        try:
            self.supabase.table("grupo_bonificaciones").insert(datos_bonif).execute()
            self.get_grupo_bonificaciones.clear()
            return True
        except Exception as e:
            st.error(f"Error al crear bonificación: {e}")
            return False

    def delete_grupo_bonificacion(self, bonificacion_id: str) -> bool:
        """Elimina una bonificación."""
        try:
            self.supabase.table("grupo_bonificaciones").delete().eq("id", bonificacion_id).execute()
            self.get_grupo_bonificaciones.clear()
            return True
        except Exception as e:
            st.error(f"Error al eliminar bonificación: {e}")
            return False

    def calcular_limite_fundae(self, modalidad: str, horas: int, participantes: int) -> Tuple[float, float]:
        """Calcula límite máximo FUNDAE según modalidad."""
        try:
            # FUNDAE: Presencial=13€/hora, Teleformación=7.5€/hora
            tarifa = 7.5 if modalidad in ["Teleformación", "TELEFORMACION"] else 13.0
            limite = tarifa * horas * participantes
            return limite, tarifa
        except:
            return 0, 0

    # =========================
    # HORARIOS
    # =========================

    def parse_horario(self, horario_str: str) -> Tuple:
        """Parsea string de horario a componentes."""
        try:
            if not horario_str:
                return None, None, None, None, []
            
            partes = horario_str.split(" | ")
            m_inicio, m_fin, t_inicio, t_fin, dias = None, None, None, None, []
            
            for parte in partes:
                if parte.startswith("Mañana:"):
                    horas = parte.replace("Mañana: ", "").split(" - ")
                    if len(horas) == 2:
                        m_inicio = datetime.strptime(horas[0], "%H:%M").time()
                        m_fin = datetime.strptime(horas[1], "%H:%M").time()
                elif parte.startswith("Tarde:"):
                    horas = parte.replace("Tarde: ", "").split(" - ")
                    if len(horas) == 2:
                        t_inicio = datetime.strptime(horas[0], "%H:%M").time()
                        t_fin = datetime.strptime(horas[1], "%H:%M").time()
                elif parte.startswith("Días:"):
                    dias = parte.replace("Días: ", "").split("-")
            
            return m_inicio, m_fin, t_inicio, t_fin, dias
        except Exception:
            return None, None, None, None, []

    def build_horario_string(self, m_inicio, m_fin, t_inicio, t_fin, dias) -> str:
        """Construye string de horario desde componentes."""
        try:
            partes = []
            
            if m_inicio and m_fin:
                partes.append(f"Mañana: {m_inicio.strftime('%H:%M')} - {m_fin.strftime('%H:%M')}")
            
            if t_inicio and t_fin:
                partes.append(f"Tarde: {t_inicio.strftime('%H:%M')} - {t_fin.strftime('%H:%M')}")
            
            if dias and any(dias):
                dias_sel = [d for d in dias if d]
                if dias_sel:
                    partes.append(f"Días: {'-'.join(dias_sel)}")
            
            return " | ".join(partes)
        except Exception:
            return ""
    # =========================
    # PROVINCIAS Y LOCALIDADES
    # =========================
    @st.cache_data(ttl=3600)
    def get_provincias(_self) -> list:
        """Devuelve listado de provincias ordenadas alfabéticamente."""
        try:
            res = _self.supabase.table("provincias").select("id, nombre").order("nombre").execute()
            return res.data or []
        except Exception as e:
            st.error(f"❌ Error al cargar provincias: {e}")
            return []
    
    @st.cache_data(ttl=3600)
    def get_localidades_por_provincia(_self, provincia_id: int) -> list:
        """Devuelve listado de localidades de una provincia."""
        try:
            res = _self.supabase.table("localidades").select("id, nombre").eq("provincia_id", provincia_id).order("nombre").execute()
            return res.data or []
        except Exception as e:
            st.error(f"❌ Error al cargar localidades: {e}")
            return []
            
    @st.cache_data(ttl=600)
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
    # CACHE MANAGEMENT
    # =========================

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
            if hasattr(self, 'get_participantes_disponibles'):
                self.get_participantes_disponibles.clear()
            if hasattr(self, 'get_grupo_costes'):
                self.get_grupo_costes.clear()
            if hasattr(self, 'get_grupo_bonificaciones'):
                self.get_grupo_bonificaciones.clear()
            
            # Centros gestores
            if hasattr(self, 'get_centro_gestor_grupo'):
                self.get_centro_gestor_grupo.clear()
            if hasattr(self, 'get_centros_para_grupo'):
                self.get_centros_para_grupo.clear()
                
        except Exception as e:
            # Fallar silenciosamente - el cache se limpiará eventualmente
            pass


# =========================
# FACTORY FUNCTION
# =========================

def get_grupos_service(supabase, session_state) -> GruposService:
    """Factory function para obtener instancia del servicio de grupos."""
    return GruposService(supabase, session_state)
