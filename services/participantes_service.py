import streamlit as st
import pandas as pd
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from utils import validar_dni_cif

class ParticipantesService:
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
        self.rol = session_state.role
        self.empresa_id = session_state.user.get("empresa_id")
        self.user_id = session_state.user.get("id")

    def _apply_empresa_filter(self, query, empresa_field: str = "empresa_id"):
        """Aplica filtro de empresa según el rol."""
        if self.rol == "gestor" and self.empresa_id:
            return query.eq(empresa_field, self.empresa_id)
        return query

    def _handle_query_error(self, operation: str, error: Exception) -> pd.DataFrame:
        """Manejo centralizado de errores en consultas."""
        st.error(f"❌ Error en {operation}: {error}")
        return pd.DataFrame()

    # =========================
    # CONSULTAS PRINCIPALES
    # =========================
    def get_participantes_completos(_self) -> pd.DataFrame:
        """CORREGIDO: Retorna siempre DataFrame válido, nunca None."""
        try:
            query = _self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, dni, email, telefono, 
                fecha_nacimiento, sexo, created_at, updated_at, grupo_id, empresa_id,
                empresa:empresas(id, nombre, cif)
            """)
            query = _self._apply_empresa_filter(query)
    
            res = query.order("created_at", desc=True).execute()
            
            # CORRECCIÓN: Manejar todos los casos None
            if not res or not res.data:
                # Retornar DataFrame vacío con columnas correctas
                return pd.DataFrame(columns=[
                    'id', 'nif', 'nombre', 'apellidos', 'dni', 'email', 'telefono',
                    'fecha_nacimiento', 'sexo', 'created_at', 'updated_at', 
                    'grupo_id', 'empresa_id', 'empresa_nombre', 'grupo_codigo'
                ])
            
            df = pd.DataFrame(res.data)
            
            # Verificar que df no esté vacío antes de procesar relaciones
            if not df.empty:
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                else:
                    df["empresa_nombre"] = ""
                    
                df["grupo_codigo"] = ""
            else:
                # DataFrame vacío - añadir columnas necesarias
                df["empresa_nombre"] = ""
                df["grupo_codigo"] = ""
            
            return df
            
        except Exception as e:
            # IMPORTANTE: Siempre retornar DataFrame, nunca None
            st.error(f"Error al cargar participantes: {e}")
            return pd.DataFrame(columns=[
                'id', 'nif', 'nombre', 'apellidos', 'dni', 'email', 'telefono',
                'fecha_nacimiento', 'sexo', 'created_at', 'updated_at', 
                'grupo_id', 'empresa_id', 'empresa_nombre', 'grupo_codigo'
            ])
            
    def get_participante_id_from_auth(self, auth_id: str) -> Optional[str]:
        """Obtiene participante_id desde auth_id usando la vista"""
        try:
            result = self.supabase.table("vw_participantes_completo").select("participante_id").eq("auth_id", auth_id).execute()
            return result.data[0]["participante_id"] if result.data else None
        except:
            return None
            
    @st.cache_data(ttl=300)
    def get_participantes_con_empresa_jerarquica(_self) -> pd.DataFrame:
        """Obtiene participantes con información jerárquica de empresa."""
        try:
            query = _self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, email, telefono, 
                fecha_nacimiento, sexo, created_at, grupo_id, empresa_id,
                grupo:grupos(id, codigo_grupo),
                empresa:empresas!fk_participante_empresa(
                    id, nombre, tipo_empresa, nivel_jerarquico,
                    empresa_matriz:empresas!empresa_matriz_id(nombre)
                )
            """)
            
            # Aplicar filtro jerárquico
            if _self.rol == "gestor":
                # Gestor ve participantes de su empresa y empresas clientes
                empresas_permitidas = _self._get_empresas_permitidas_gestor()
                if empresas_permitidas:
                    query = query.in_("empresa_id", empresas_permitidas)
                else:
                    return pd.DataFrame()
            
            res = query.order("created_at", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            if not df.empty:
                # Procesar información de empresa
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                    df["empresa_tipo"] = df["empresa"].apply(
                        lambda x: x.get("tipo_empresa") if isinstance(x, dict) else ""
                    )
                    df["empresa_matriz_nombre"] = df["empresa"].apply(
                        lambda x: x.get("empresa_matriz", {}).get("nombre") if isinstance(x, dict) else ""
                    )
                
                # Procesar información de grupo
                if "grupo" in df.columns:
                    df["grupo_codigo"] = df["grupo"].apply(
                        lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes con jerarquía", e)
    
    def _get_empresas_permitidas_gestor(_self) -> List[str]:
        """Obtiene IDs de empresas que puede gestionar el gestor."""
        try:
            # Incluir empresa propia + empresas clientes
            empresas = [_self.empresa_id] if _self.empresa_id else []
            
            clientes_res = _self.supabase.table("empresas").select("id").eq(
                "empresa_matriz_id", _self.empresa_id
            ).execute()
            
            if clientes_res.data:
                empresas.extend([cliente["id"] for cliente in clientes_res.data])
            
            return empresas
        except Exception as e:
            st.error(f"Error obteniendo empresas permitidas: {e}")
            return []
    
    def get_empresas_para_participantes(_self) -> Dict[str, str]:
        """Obtiene empresas donde se pueden crear participantes."""
        try:
            if _self.rol == "admin":
                # Admin puede asignar a cualquier empresa
                res = _self.supabase.table("empresas").select("id, nombre").execute()
                
            elif _self.rol == "gestor":
                # Gestor puede asignar a su empresa y clientes
                empresas_ids = _self._get_empresas_permitidas_gestor()
                if empresas_ids:
                    res = _self.supabase.table("empresas").select("id, nombre").in_(
                        "id", empresas_ids
                    ).execute()
                else:
                    return {}
            else:
                return {}
            
            if res.data:
                return {emp["nombre"]: emp["id"] for emp in res.data}
            return {}
            
        except Exception as e:
            st.error(f"Error al cargar empresas para participantes: {e}")
            return {}   
        
    # =========================
    # MÉTODOS CON JERARQUÍA DE EMPRESAS
    # =========================
    @st.cache_data(ttl=300)
    def get_participantes_con_jerarquia(_self) -> pd.DataFrame:
        """Obtiene participantes con información jerárquica completa."""
        try:
            query = _self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, email, telefono, fecha_nacimiento, 
                sexo, created_at, updated_at, grupo_id, empresa_id,
                grupo:grupos(id, codigo_grupo),
                empresa:empresas!fk_participante_empresa(
                    id, nombre, tipo_empresa, nivel_jerarquico,
                    empresa_matriz:empresas!empresa_matriz_id(id, nombre)
                )
            """)
            
            # Aplicar filtro jerárquico según rol
            if _self.rol == "gestor" and _self.empresa_id:
                # Gestor ve participantes de su empresa y empresas clientes
                empresas_permitidas = _self._get_empresas_gestionables()
                if empresas_permitidas:
                    query = query.in_("empresa_id", empresas_permitidas)
                else:
                    return pd.DataFrame()
            
            res = query.order("created_at", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            if not df.empty:
                # Procesar información de empresa con jerarquía
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                    df["empresa_tipo"] = df["empresa"].apply(
                        lambda x: x.get("tipo_empresa") if isinstance(x, dict) else ""
                    )
                    df["empresa_nivel"] = df["empresa"].apply(
                        lambda x: x.get("nivel_jerarquico") if isinstance(x, dict) else 1
                    )
                    
                    # Información de empresa matriz
                    df["empresa_matriz_nombre"] = df["empresa"].apply(
                        lambda x: x.get("empresa_matriz", {}).get("nombre") if isinstance(x, dict) and x.get("empresa_matriz") else ""
                    )
                    
                    # Crear display name con jerarquía
                    df["empresa_display"] = df.apply(lambda row:
                        f"{row['empresa_nombre']}" + 
                        (f" (Cliente de {row['empresa_matriz_nombre']})" if row['empresa_matriz_nombre'] else ""),
                        axis=1
                    )
                
                # Procesar información de grupo
                if "grupo" in df.columns:
                    df["grupo_codigo"] = df["grupo"].apply(
                        lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes con jerarquía", e)
    
    def _get_empresas_gestionables(_self) -> List[str]:
        """Obtiene lista de IDs de empresas que puede gestionar el usuario."""
        try:
            empresas = []
            
            if _self.rol == "admin":
                # Admin puede gestionar todas las empresas
                res = _self.supabase.table("empresas").select("id").execute()
                empresas = [emp["id"] for emp in (res.data or [])]
                
            elif _self.rol == "gestor" and _self.empresa_id:
                # Gestor puede gestionar su empresa y sus clientes
                empresas = [_self.empresa_id]
                
                # Agregar empresas clientes
                clientes_res = _self.supabase.table("empresas").select("id").eq(
                    "empresa_matriz_id", _self.empresa_id
                ).execute()
                
                if clientes_res.data:
                    empresas.extend([cliente["id"] for cliente in clientes_res.data])
            
            return empresas
        except Exception as e:
            st.error(f"Error obteniendo empresas gestionables: {e}")
            return []
    
    def get_empresas_para_participantes(_self) -> Dict[str, str]:
        """Obtiene empresas donde se pueden crear/asignar participantes."""
        try:
            if _self.rol == "admin":
                # Admin puede asignar a cualquier empresa
                res = _self.supabase.table("empresas").select("""
                    id, nombre, tipo_empresa, empresa_matriz_id,
                    empresa_matriz:empresas!empresa_matriz_id(nombre)
                """).order("nombre").execute()
                
            elif _self.rol == "gestor" and _self.empresa_id:
                # Gestor puede asignar a su empresa y clientes
                empresas_ids = _self._get_empresas_gestionables()
                if empresas_ids:
                    res = _self.supabase.table("empresas").select("""
                        id, nombre, tipo_empresa, empresa_matriz_id,
                        empresa_matriz:empresas!empresa_matriz_id(nombre)
                    """).in_("id", empresas_ids).order("nombre").execute()
                else:
                    return {}
            else:
                return {}
            
            if res.data:
                result = {}
                for emp in res.data:
                    # Crear nombre descriptivo con jerarquía
                    nombre_base = emp["nombre"]
                    tipo_empresa = emp.get("tipo_empresa", "")
                    
                    if tipo_empresa == "CLIENTE_GESTOR" and emp.get("empresa_matriz"):
                        matriz_nombre = emp["empresa_matriz"].get("nombre", "")
                        nombre_display = f"{nombre_base} (Cliente de {matriz_nombre})"
                    elif tipo_empresa == "GESTORA":
                        nombre_display = f"{nombre_base} (Gestora)"
                    else:
                        nombre_display = nombre_base
                    
                    result[nombre_display] = emp["id"]
                
                return result
            return {}
            
        except Exception as e:
            st.error(f"Error al cargar empresas para participantes: {e}")
            return {}
    
    def create_participante_con_jerarquia(_self, datos: Dict[str, Any]) -> bool:
        """Crea participante validando permisos jerárquicos."""
        try:
            # Validaciones básicas
            if not datos.get("email"):
                st.error("El email es obligatorio.")
                return False
                
            if not datos.get("nombre") or not datos.get("apellidos"):
                st.error("Nombre y apellidos son obligatorios.")
                return False
            
            # Validar empresa asignada
            empresa_id_part = datos.get("empresa_id")
            if not empresa_id_part:
                st.error("Debe asignar una empresa al participante.")
                return False
            
            # Verificar permisos sobre la empresa
            empresas_permitidas = _self._get_empresas_gestionables()
            if empresa_id_part not in empresas_permitidas:
                st.error("No tienes permisos para crear participantes en esa empresa.")
                return False
            
            # Verificar que la empresa existe y obtener información
            empresa_info = _self.supabase.table("empresas").select(
                "id, nombre, tipo_empresa"
            ).eq("id", empresa_id_part).execute()
            
            if not empresa_info.data:
                st.error("La empresa especificada no existe.")
                return False
            
            # Validar DNI/NIF si está presente
            if datos.get("nif") and not validar_dni_cif(datos["nif"]):
                st.error("NIF no válido.")
                return False
    
            # Verificar email único
            email_existe = _self.supabase.table("participantes").select("id").eq(
                "email", datos["email"]
            ).execute()
            if email_existe.data:
                st.error("Ya existe un participante con ese email.")
                return False
    
            # Verificar email único en usuarios
            usuario_existe = _self.supabase.table("usuarios").select("id").eq(
                "email", datos["email"]
            ).execute()
            if usuario_existe.data:
                st.error("Ya existe un usuario con ese email.")
                return False
    
            # Preparar datos finales
            datos_finales = datos.copy()
            datos_finales.update({
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            })
    
            # Crear participante
            result = _self.supabase.table("participantes").insert(datos_finales).execute()
    
            if result.data:
                # Limpiar cache
                _self.get_participantes_con_jerarquia.clear()
                return True
            else:
                st.error("Error al crear el participante.")
                return False
    
        except Exception as e:
            st.error(f"Error al crear participante: {e}")
            return False
    
    def update_participante_con_jerarquia(_self, participante_id: str, datos_editados: Dict[str, Any]) -> bool:
        """Actualiza participante validando permisos jerárquicos."""
        try:
            # Verificar permisos sobre el participante
            participante_actual = _self.supabase.table("participantes").select(
                "empresa_id, email"
            ).eq("id", participante_id).execute()
            
            if not participante_actual.data:
                st.error("Participante no encontrado.")
                return False
            
            empresa_actual = participante_actual.data[0]["empresa_id"]
            email_actual = participante_actual.data[0]["email"]
            
            # Verificar que puede gestionar la empresa actual
            empresas_permitidas = _self._get_empresas_gestionables()
            if empresa_actual not in empresas_permitidas:
                st.error("No tienes permisos para editar este participante.")
                return False
            
            # Si se cambia la empresa, verificar permisos sobre la nueva
            nueva_empresa = datos_editados.get("empresa_id", empresa_actual)
            if nueva_empresa != empresa_actual and nueva_empresa not in empresas_permitidas:
                st.error("No tienes permisos para asignar el participante a esa empresa.")
                return False
            
            # Validaciones básicas
            if not datos_editados.get("email"):
                st.error("El email es obligatorio.")
                return False
                
            if datos_editados.get("nif") and not validar_dni_cif(datos_editados["nif"]):
                st.error("NIF no válido.")
                return False
    
            # Verificar email único (excluyendo el actual)
            if datos_editados["email"] != email_actual:
                email_existe = _self.supabase.table("participantes").select("id").eq(
                    "email", datos_editados["email"]
                ).neq("id", participante_id).execute()
                
                if email_existe.data:
                    st.error("Ya existe otro participante con ese email.")
                    return False
    
            # Añadir timestamp de actualización
            datos_editados["updated_at"] = datetime.utcnow().isoformat()
    
            # Actualizar participante
            _self.supabase.table("participantes").update(datos_editados).eq("id", participante_id).execute()
    
            # Limpiar cache
            _self.get_participantes_con_jerarquia.clear()
    
            return True
    
        except Exception as e:
            st.error(f"Error al actualizar participante: {e}")
            return False
    
    def delete_participante_con_jerarquia(_self, participante_id: str) -> bool:
        """Elimina participante validando permisos jerárquicos."""
        try:
            # Verificar permisos sobre el participante
            participante = _self.supabase.table("participantes").select("empresa_id").eq("id", participante_id).execute()
            
            if not participante.data:
                st.error("Participante no encontrado.")
                return False
            
            empresa_id = participante.data[0]["empresa_id"]
            
            # Verificar permisos
            empresas_permitidas = _self._get_empresas_gestionables()
            if empresa_id not in empresas_permitidas:
                st.error("No tienes permisos para eliminar este participante.")
                return False
    
            # Verificar dependencias - diplomas
            diplomas = _self.supabase.table("diplomas").select("id").eq("participante_id", participante_id).execute()
            if diplomas.data:
                st.error("No se puede eliminar. El participante tiene diplomas asociados.")
                return False
    
            # Eliminar participante (esto también eliminará relaciones en cascada)
            _self.supabase.table("participantes").delete().eq("id", participante_id).execute()
    
            # Limpiar cache
            _self.get_participantes_con_jerarquia.clear()
    
            return True
    
        except Exception as e:
            st.error(f"Error al eliminar participante: {e}")
            return False
    def get_participante_id_from_auth(self, auth_id: str) -> Optional[str]:
        """Obtiene participante_id desde auth_id - CORREGIDO"""
        try:
            # Buscar directamente por auth_id en participantes
            result = self.supabase.table("participantes").select("id").eq("auth_id", auth_id).execute()
            return result.data[0]["id"] if result.data else None
        except Exception as e:
            print(f"Error obteniendo participante desde auth_id: {e}")
            return None

    def get_participante_desde_usuario_auth(self, auth_id: str) -> Optional[Dict]:
        """Obtiene participante completo desde auth_id"""
        try:
            result = self.supabase.table("participantes").select("*").eq("auth_id", auth_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error obteniendo participante completo: {e}")
            return None
        
    def get_participantes_con_grupos_nn(self) -> pd.DataFrame:
        """NUEVO: Obtiene participantes con todos sus grupos usando tabla N:N."""
        try:
            query = self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, email, telefono, 
                fecha_nacimiento, sexo, created_at, updated_at, empresa_id,
                empresa:empresas(id, nombre, cif),
                participantes_grupos(
                    id, grupo_id, fecha_asignacion,
                    grupo:grupos(id, codigo_grupo, fecha_inicio, fecha_fin_prevista,
                               accion_formativa:acciones_formativas(nombre))
                )
            """)
            
            # Aplicar filtro según rol
            query = self._apply_empresa_filter(query)
            
            res = query.order("created_at", desc=True).execute()
            
            if not res or not res.data:
                return pd.DataFrame(columns=[
                    'id', 'nif', 'nombre', 'apellidos', 'email', 'telefono',
                    'fecha_nacimiento', 'sexo', 'created_at', 'updated_at', 
                    'empresa_id', 'empresa_nombre', 'grupos_ids', 'grupos_codigos'
                ])
            
            # Procesar datos N:N
            participantes_procesados = []
            for participante in res.data:
                grupos_participante = participante.get("participantes_grupos", [])
                
                # Extraer empresa
                empresa_data = participante.get("empresa", {})
                empresa_nombre = empresa_data.get("nombre", "") if isinstance(empresa_data, dict) else ""
                
                # Procesar grupos
                grupos_ids = []
                grupos_codigos = []
                
                for grupo_rel in grupos_participante:
                    grupo_data = grupo_rel.get("grupo", {})
                    if isinstance(grupo_data, dict):
                        grupos_ids.append(grupo_data.get("id", ""))
                        grupos_codigos.append(grupo_data.get("codigo_grupo", ""))
                
                # Crear fila del participante
                participante_row = {
                    "id": participante.get("id"),
                    "nif": participante.get("nif", ""),
                    "nombre": participante.get("nombre", ""),
                    "apellidos": participante.get("apellidos", ""),
                    "email": participante.get("email", ""),
                    "telefono": participante.get("telefono", ""),
                    "fecha_nacimiento": participante.get("fecha_nacimiento"),
                    "sexo": participante.get("sexo", ""),
                    "created_at": participante.get("created_at"),
                    "updated_at": participante.get("updated_at"),
                    "empresa_id": participante.get("empresa_id"),
                    "empresa_nombre": empresa_nombre,
                    "grupos_ids": ", ".join(grupos_ids),
                    "grupos_codigos": ", ".join(grupos_codigos),
                    "num_grupos": len(grupos_ids)
                }
                
                participantes_procesados.append(participante_row)
            
            return pd.DataFrame(participantes_procesados)
            
        except Exception as e:
            return self._handle_query_error("participantes con grupos N:N", e)

    def get_grupos_de_participante(self, participante_id: str) -> pd.DataFrame:
        """NUEVO: Obtiene todos los grupos de un participante específico."""
        try:
            # Verificar permisos
            participante_check = self.supabase.table("participantes").select(
                "empresa_id"
            ).eq("id", participante_id).execute()
            
            if not participante_check.data:
                return pd.DataFrame()
            
            empresa_id = participante_check.data[0]["empresa_id"]
            empresas_permitidas = self._get_empresas_gestionables()
            
            if empresa_id not in empresas_permitidas:
                return pd.DataFrame()
            
            # Obtener grupos del participante
            res = self.supabase.table("participantes_grupos").select("""
                id, grupo_id, fecha_asignacion,
                grupo:grupos(
                    id, codigo_grupo, fecha_inicio, fecha_fin_prevista, fecha_fin,
                    modalidad, lugar_imparticion,
                    accion_formativa:acciones_formativas(nombre, horas)
                )
            """).eq("participante_id", participante_id).execute()
            
            grupos_data = []
            for rel in res.data or []:
                grupo = rel.get("grupo", {})
                accion = grupo.get("accion_formativa", {}) if isinstance(grupo, dict) else {}
                
                grupos_data.append({
                    "relacion_id": rel.get("id"),
                    "grupo_id": rel.get("grupo_id"),
                    "fecha_asignacion": rel.get("fecha_asignacion"),
                    "codigo_grupo": grupo.get("codigo_grupo", "") if isinstance(grupo, dict) else "",
                    "fecha_inicio": grupo.get("fecha_inicio") if isinstance(grupo, dict) else None,
                    "fecha_fin_prevista": grupo.get("fecha_fin_prevista") if isinstance(grupo, dict) else None,
                    "fecha_fin": grupo.get("fecha_fin") if isinstance(grupo, dict) else None,
                    "modalidad": grupo.get("modalidad", "") if isinstance(grupo, dict) else "",
                    "lugar_imparticion": grupo.get("lugar_imparticion", "") if isinstance(grupo, dict) else "",
                    "accion_nombre": accion.get("nombre", "") if isinstance(accion, dict) else "",
                    # 🔧 fuerza a int siempre, aunque venga None
                    "accion_horas": int(accion.get("horas") or 0) if isinstance(accion, dict) else 0
                })
            
            return pd.DataFrame(grupos_data)
            
        except Exception as e:
            return self._handle_query_error("grupos del participante", e)
    
    def asignar_participante_a_grupo(self, participante_id: str, grupo_id: str) -> bool:
        """NUEVO: Asigna participante a grupo usando tabla N:N."""
        try:
            # Verificar permisos sobre el participante
            participante_check = self.supabase.table("participantes").select(
                "empresa_id"
            ).eq("id", participante_id).execute()
            
            if not participante_check.data:
                st.error("Participante no encontrado")
                return False
            
            empresa_id = participante_check.data[0]["empresa_id"]
            empresas_permitidas = self._get_empresas_gestionables()
            
            if empresa_id not in empresas_permitidas:
                st.error("No tienes permisos para gestionar este participante")
                return False
            
            # Verificar que el grupo existe y es accesible
            grupo_check = self.supabase.table("grupos").select("id, empresa_id").eq("id", grupo_id).execute()
            if not grupo_check.data:
                st.error("Grupo no encontrado")
                return False
            
            # Verificar si ya existe la relación
            relacion_existe = self.supabase.table("participantes_grupos").select("id").match({
                "participante_id": participante_id,
                "grupo_id": grupo_id
            }).execute()
            
            if relacion_existe.data:
                st.warning("El participante ya está asignado a este grupo")
                return False
            
            # Crear relación
            self.supabase.table("participantes_grupos").insert({
                "participante_id": participante_id,
                "grupo_id": grupo_id,
                "fecha_asignacion": datetime.utcnow().isoformat()
            }).execute()
            
            # Limpiar caches
            self.get_participantes_con_grupos_nn.clear()
            
            return True
            
        except Exception as e:
            st.error(f"Error asignando participante a grupo: {e}")
            return False
    
    def desasignar_participante_de_grupo(self, participante_id: str, grupo_id: str) -> bool:
        """NUEVO: Desasigna participante de grupo."""
        try:
            # Verificar permisos
            participante_check = self.supabase.table("participantes").select(
                "empresa_id"
            ).eq("id", participante_id).execute()
            
            if not participante_check.data:
                st.error("Participante no encontrado")
                return False
            
            empresa_id = participante_check.data[0]["empresa_id"]
            empresas_permitidas = self._get_empresas_gestionables()
            
            if empresa_id not in empresas_permitidas:
                st.error("No tienes permisos para gestionar este participante")
                return False
            
            # Eliminar relación
            self.supabase.table("participantes_grupos").delete().match({
                "participante_id": participante_id,
                "grupo_id": grupo_id
            }).execute()
            
            # Limpiar caches
            self.get_participantes_con_grupos_nn.clear()
            
            return True
            
        except Exception as e:
            st.error(f"Error desasignando participante: {e}")
            return False
    
    def get_grupos_disponibles_para_participante(self, participante_id: str) -> Dict[str, str]:
        """NUEVO: Obtiene grupos disponibles para asignar a un participante."""
        try:
            # Verificar participante y obtener su empresa
            participante = self.supabase.table("participantes").select(
                "empresa_id"
            ).eq("id", participante_id).execute()
            
            if not participante.data:
                return {}
            
            empresa_id = participante.data[0]["empresa_id"]
            empresas_permitidas = self._get_empresas_gestionables()
            
            if empresa_id not in empresas_permitidas:
                return {}
            
            # Obtener grupos ya asignados al participante
            grupos_asignados = self.supabase.table("participantes_grupos").select(
                "grupo_id"
            ).eq("participante_id", participante_id).execute()
            
            grupos_asignados_ids = [g["grupo_id"] for g in grupos_asignados.data or []]
            
            # Obtener grupos de la empresa donde participa el participante
            empresas_grupos = self.supabase.table("empresas_grupos").select(
                "grupo_id"
            ).eq("empresa_id", empresa_id).execute()
            
            grupos_empresa_ids = [eg["grupo_id"] for eg in empresas_grupos.data or []]
            
            if not grupos_empresa_ids:
                return {}
            
            # Filtrar grupos no asignados
            grupos_disponibles_ids = [g_id for g_id in grupos_empresa_ids if g_id not in grupos_asignados_ids]
            
            if not grupos_disponibles_ids:
                return {}
            
            # Obtener información de grupos disponibles
            grupos_res = self.supabase.table("grupos").select("""
                id, codigo_grupo, fecha_inicio, fecha_fin_prevista,
                accion_formativa:acciones_formativas(nombre)
            """).in_("id", grupos_disponibles_ids).execute()
            
            grupos_options = {}
            for grupo in grupos_res.data or []:
                accion_nombre = ""
                if isinstance(grupo.get("accion_formativa"), dict):
                    accion_nombre = grupo["accion_formativa"].get("nombre", "Sin acción")
                
                fecha_inicio = grupo.get("fecha_inicio")
                fecha_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y') if fecha_inicio else "Sin fecha"
                
                display_name = f"{grupo['codigo_grupo']} - {accion_nombre} ({fecha_str})"
                grupos_options[display_name] = grupo["id"]
            
            return grupos_options
            
        except Exception as e:
            st.error(f"Error cargando grupos disponibles: {e}")
            return {}
    
    def migrar_campo_grupo_id_a_nn(self) -> bool:
        """MIGRACIÓN: Convierte datos del campo grupo_id a tabla participantes_grupos."""
        try:
            if self.rol != "admin":
                st.error("Solo administradores pueden ejecutar migraciones")
                return False
            
            # Obtener participantes con grupo_id
            participantes_con_grupo = self.supabase.table("participantes").select(
                "id, grupo_id"
            ).not_.is_("grupo_id", "null").execute()
            
            migrados = 0
            errores = []
            
            for participante in participantes_con_grupo.data or []:
                try:
                    # Verificar si ya existe en participantes_grupos
                    existe = self.supabase.table("participantes_grupos").select("id").match({
                        "participante_id": participante["id"],
                        "grupo_id": participante["grupo_id"]
                    }).execute()
                    
                    if not existe.data:
                        # Crear entrada en participantes_grupos
                        self.supabase.table("participantes_grupos").insert({
                            "participante_id": participante["id"],
                            "grupo_id": participante["grupo_id"],
                            "fecha_asignacion": datetime.utcnow().isoformat()
                        }).execute()
                        
                        migrados += 1
                    
                except Exception as e:
                    errores.append(f"Participante {participante['id']}: {e}")
            
            st.success(f"Migración completada: {migrados} relaciones creadas")
            if errores:
                st.error(f"Errores: {len(errores)}")
                for error in errores[:5]:  # Mostrar solo los primeros 5
                    st.write(error)
            
            return True
            
        except Exception as e:
            st.error(f"Error en migración: {e}")
            return False

    def get_avatar_participante(self, participante_id: str) -> Optional[Dict]:
        """Obtiene información del avatar de un participante"""
        try:
            result = self.supabase.table("participantes_avatars").select("*").eq(
                "participante_id", participante_id
            ).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            return None
    
    def subir_avatar(self, participante_id: str, archivo_imagen) -> bool:
        """Sube avatar de participante a Supabase Storage"""
        try:
            from PIL import Image
            import io
            
            # Leer archivo
            file_bytes = archivo_imagen.getvalue()
            file_name = archivo_imagen.name
            file_type = archivo_imagen.type
            
            # Validar tamaño (máximo 2MB)
            if len(file_bytes) > 2 * 1024 * 1024:
                return False
            
            # Redimensionar imagen a 150x150px
            image = Image.open(io.BytesIO(file_bytes))
            image = image.resize((150, 150), Image.Resampling.LANCZOS)
            
            # Convertir de vuelta a bytes
            output = io.BytesIO()
            format_map = {"image/jpeg": "JPEG", "image/jpg": "JPEG", "image/png": "PNG"}
            img_format = format_map.get(file_type, "JPEG")
            image.save(output, format=img_format, quality=85)
            processed_bytes = output.getvalue()
            
            # Generar nombre único
            import uuid
            extension = file_name.split('.')[-1] if '.' in file_name else 'jpg'
            nombre_unico = f"avatar_{participante_id}_{int(datetime.now().timestamp())}.{extension}"
            
            # Subir a Supabase Storage
            resultado = self.supabase.storage.from_("avatars").upload(
                nombre_unico, processed_bytes, {"content-type": file_type}
            )
            
            if resultado:
                # Obtener URL pública
                url_publica = self.supabase.storage.from_("avatars").get_public_url(nombre_unico)
                
                # Eliminar avatar anterior si existe
                self.eliminar_avatar(participante_id)
                
                # Guardar en base de datos
                datos_avatar = {
                    "id": str(uuid.uuid4()),
                    "participante_id": participante_id,
                    "archivo_nombre": file_name,
                    "archivo_url": url_publica,
                    "mime_type": file_type,
                    "tamaño_bytes": len(processed_bytes),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                resultado_db = self.supabase.table("participantes_avatars").insert(datos_avatar).execute()
                return bool(resultado_db.data)
            
            return False
            
        except Exception as e:
            return False
    
    def eliminar_avatar(self, participante_id: str) -> bool:
        """Elimina avatar existente de un participante"""
        try:
            # Obtener avatar actual
            avatar_actual = self.supabase.table("participantes_avatars").select("*").eq(
                "participante_id", participante_id
            ).execute()
            
            if avatar_actual.data:
                avatar = avatar_actual.data[0]
                
                # Eliminar de storage
                archivo_url = avatar["archivo_url"]
                nombre_archivo = archivo_url.split("/")[-1]
                try:
                    self.supabase.storage.from_("avatars").remove([nombre_archivo])
                except:
                    pass  # No fallar si el archivo ya no existe
                
                # Eliminar de base de datos
                self.supabase.table("participantes_avatars").delete().eq(
                    "participante_id", participante_id
                ).execute()
            
            return True
            
        except Exception as e:
            return False    
            
    def get_participantes_por_empresa(_self, empresa_id: str) -> pd.DataFrame:
        """Obtiene participantes de una empresa específica."""
        try:
            # Verificar permisos sobre la empresa
            empresas_permitidas = _self._get_empresas_gestionables()
            if empresa_id not in empresas_permitidas:
                return pd.DataFrame()
            
            res = _self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, email, telefono, 
                fecha_nacimiento, sexo, grupo_id, created_at,
                grupo:grupos(id, codigo_grupo)
            """).eq("empresa_id", empresa_id).order("nombre").execute()
            
            df = pd.DataFrame(res.data or [])
            
            if not df.empty and "grupo" in df.columns:
                df["grupo_codigo"] = df["grupo"].apply(
                    lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes por empresa", e)
    
    def get_participantes_asignables_a_grupo(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene participantes que pueden asignarse a un grupo específico."""
        try:
            # Obtener empresas participantes del grupo
            empresas_grupo = _self.supabase.table("empresas_grupos").select("empresa_id").eq("grupo_id", grupo_id).execute()
            empresas_participantes = [emp["empresa_id"] for emp in (empresas_grupo.data or [])]
            
            if not empresas_participantes:
                return pd.DataFrame()
            
            # Filtrar por empresas que puede gestionar el usuario
            empresas_permitidas = _self._get_empresas_gestionables()
            empresas_validas = [e for e in empresas_participantes if e in empresas_permitidas]
            
            if not empresas_validas:
                return pd.DataFrame()
            
            # Obtener participantes sin grupo de las empresas válidas
            res = _self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, email, telefono, empresa_id,
                empresa:empresas(nombre, tipo_empresa)
            """).in_("empresa_id", empresas_validas).is_("grupo_id", "null").order("nombre").execute()
            
            df = pd.DataFrame(res.data or [])
            
            if not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
                df["empresa_tipo"] = df["empresa"].apply(
                    lambda x: x.get("tipo_empresa") if isinstance(x, dict) else ""
                )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes asignables", e)
    
    def search_participantes_jerarquia(_self, filtros: Dict[str, Any]) -> pd.DataFrame:
        """Búsqueda avanzada de participantes con filtros jerárquicos."""
        try:
            df = _self.get_participantes_con_jerarquia()
            if df.empty:
                return df
    
            df_filtered = df.copy()
    
            # Filtro por texto
            if filtros.get("query"):
                q_lower = filtros["query"].lower()
                df_filtered = df_filtered[
                    df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["apellidos"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["email"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["nif"].fillna("").str.lower().str.contains(q_lower, na=False)
                ]
    
            # Filtro por empresa específica
            if filtros.get("empresa_id"):
                df_filtered = df_filtered[df_filtered["empresa_id"] == filtros["empresa_id"]]
    
            # Filtro por tipo de empresa
            if filtros.get("tipo_empresa"):
                df_filtered = df_filtered[df_filtered["empresa_tipo"] == filtros["tipo_empresa"]]
    
            # Filtro por grupo
            if filtros.get("grupo_id"):
                df_filtered = df_filtered[df_filtered["grupo_id"] == filtros["grupo_id"]]
    
            # Filtro por estado de asignación
            if filtros.get("estado_asignacion") == "con_grupo":
                df_filtered = df_filtered[df_filtered["grupo_id"].notna()]
            elif filtros.get("estado_asignacion") == "sin_grupo":
                df_filtered = df_filtered[df_filtered["grupo_id"].isna()]
    
            return df_filtered
    
        except Exception as e:
            return _self._handle_query_error("búsqueda jerárquica de participantes", e)
    
    def get_estadisticas_participantes_jerarquia(_self) -> Dict[str, Any]:
        """Obtiene estadísticas de participantes con información jerárquica."""
        try:
            df = _self.get_participantes_con_jerarquia()
            
            if df.empty:
                return {
                    "total": 0,
                    "por_tipo_empresa": {},
                    "con_grupo": 0,
                    "sin_grupo": 0,
                    "por_empresa": {}
                }
    
            total = len(df)
            con_grupo = len(df[df["grupo_id"].notna()])
            sin_grupo = total - con_grupo
            
            # Estadísticas por tipo de empresa
            por_tipo = df["empresa_tipo"].value_counts().to_dict() if "empresa_tipo" in df.columns else {}
            
            # Estadísticas por empresa
            por_empresa = df["empresa_nombre"].value_counts().head(10).to_dict() if "empresa_nombre" in df.columns else {}
    
            return {
                "total": total,
                "por_tipo_empresa": por_tipo,
                "con_grupo": con_grupo,
                "sin_grupo": sin_grupo,
                "por_empresa": por_empresa
            }
    
        except Exception as e:
            st.error(f"Error al calcular estadísticas: {e}")
            return {}
    # =========================
    # OPERACIONES CRUD
    # =========================
    def create_participante(_self, datos: Dict[str, Any]) -> bool:
        """Crea un nuevo participante y su usuario en Auth automáticamente."""
        try:
            from services.alumnos import AlumnosService
            alumnos_service = AlumnosService(_self.supabase)
    
            # Validaciones básicas
            if not datos.get("email") or not datos.get("password"):
                st.error("⚠️ Email y contraseña son obligatorios.")
                return False
            if not datos.get("nombre") or not datos.get("apellidos"):
                st.error("⚠️ Nombre y apellidos son obligatorios.")
                return False
            if datos.get("dni") and not validar_dni_cif(datos["dni"]):
                st.error("⚠️ DNI/CIF no válido.")
                return False
    
            # Ajustar empresa si es gestor
            if _self.rol == "gestor":
                datos["empresa_id"] = _self.empresa_id
    
            # Crear alumno en Auth + Participantes
            participante_id = alumnos_service.crear_alumno(datos)
            if participante_id:
                _self.get_participantes_completos.clear()
                return True
            else:
                return False
    
        except Exception as e:
            st.error(f"⚠️ Error al crear participante con Auth: {e}")
            return False
    
    def update_participante(_self, participante_id: str, datos_editados: Dict[str, Any]) -> bool:
        """Actualiza un participante y sincroniza datos con Auth."""
        try:
            from services.alumnos import AlumnosService
            alumnos_service = AlumnosService(_self.supabase)
    
            # Verificar existencia del participante
            participante = _self.supabase.table("participantes").select("auth_id, email").eq("id", participante_id).execute()
            if not participante.data:
                st.error("⚠️ Participante no encontrado.")
                return False
    
            auth_id = participante.data[0].get("auth_id")
            email_actual = participante.data[0].get("email")
    
            # Validaciones
            if not datos_editados.get("email"):
                st.error("⚠️ El email es obligatorio.")
                return False
            if datos_editados.get("dni") and not validar_dni_cif(datos_editados["dni"]):
                st.error("⚠️ DNI/CIF no válido.")
                return False
    
            # Verificar email único (excluyendo el actual)
            if datos_editados["email"] != email_actual:
                email_existe = (
                    _self.supabase.table("participantes")
                    .select("id")
                    .eq("email", datos_editados["email"])
                    .neq("id", participante_id)
                    .execute()
                )
                if email_existe.data:
                    st.error("⚠️ Ya existe otro participante con ese email.")
                    return False
    
            # Control de permisos para gestor
            if _self.rol == "gestor":
                participante_check = _self.supabase.table("participantes").select("empresa_id").eq("id", participante_id).execute()
                if not participante_check.data or participante_check.data[0].get("empresa_id") != _self.empresa_id:
                    st.error("⚠️ No tienes permisos para editar este participante.")
                    return False
    
            # --- Actualizar tabla participantes ---
            datos_editados["updated_at"] = datetime.utcnow().isoformat()
            _self.supabase.table("participantes").update(datos_editados).eq("id", participante_id).execute()
    
            # --- Sincronizar con Auth ---
            if auth_id:
                try:
                    update_data = {}
                    if "email" in datos_editados:
                        update_data["email"] = datos_editados["email"]
                    update_data["user_metadata"] = {
                        "rol": "alumno",
                        "nombre": datos_editados.get("nombre"),
                        "apellidos": datos_editados.get("apellidos"),
                    }
                    _self.supabase.auth.admin.update_user(auth_id, update_data)
                except Exception as e:
                    st.warning(f"⚠️ Participante actualizado pero no se pudo sincronizar con Auth: {e}")
    
            # Limpiar caché
            _self.get_participantes_completos.clear()
    
            return True
    
        except Exception as e:
            st.error(f"⚠️ Error al actualizar participante: {e}")
            return False

    def delete_participante(_self, participante_id: str) -> bool:
        """Elimina un participante y su usuario en Auth automáticamente."""
        try:
            from services.alumnos import AlumnosService
            alumnos_service = AlumnosService(_self.supabase)
    
            # Buscar auth_id
            res = _self.supabase.table("participantes").select("auth_id").eq("id", participante_id).execute()
            auth_id = res.data[0]["auth_id"] if res.data else None
    
            # Eliminar
            ok = alumnos_service.borrar_alumno(participante_id, auth_id)
            if ok:
                _self.get_participantes_completos.clear()
                return True
            return False
    
        except Exception as e:
            st.error(f"⚠️ Error al eliminar participante: {e}")
            return False

    # =========================
    # BÚSQUEDAS Y FILTROS
    # =========================
    def search_participantes_avanzado(_self, filtros: Dict[str, Any]) -> pd.DataFrame:
        """Búsqueda avanzada de participantes con múltiples filtros."""
        try:
            df = _self.get_participantes_completos()
            if df.empty:
                return df

            df_filtered = df.copy()

            # Filtro por texto
            if filtros.get("query"):
                q_lower = filtros["query"].lower()
                df_filtered = df_filtered[
                    df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["apellidos"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["email"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["dni"].fillna("").str.lower().str.contains(q_lower, na=False)
                ]

            # Filtro por grupo
            if filtros.get("grupo_id"):
                df_filtered = df_filtered[df_filtered["grupo_id"] == filtros["grupo_id"]]

            # Filtro por empresa (solo para admin)
            if _self.rol == "admin" and filtros.get("empresa_id"):
                df_filtered = df_filtered[df_filtered["empresa_id"] == filtros["empresa_id"]]

            return df_filtered

        except Exception as e:
            return _self._handle_query_error("búsqueda avanzada de participantes", e)

    # =========================
    # ESTADÍSTICAS
    # =========================
    def get_estadisticas_participantes(_self) -> Dict[str, Any]:
        """Alias para compatibilidad: usa la versión jerárquica por defecto."""
        return _self.get_estadisticas_participantes_jerarquia()
        try:
            df = _self.get_participantes_completos()
            
            if df.empty:
                return {
                    "total": 0,
                    "nuevos_mes": 0,
                    "en_curso": 0,
                    "finalizados": 0,
                    "con_diploma": 0
                }
    
            total = len(df)
    
            # Nuevos este mes
            nuevos_mes = 0
            if "created_at" in df.columns:
                este_mes_df = df[
                    pd.to_datetime(df["created_at"], errors="coerce").dt.month == datetime.now().month
                ]
                nuevos_mes = len(este_mes_df)
    
            # Estado formación
            en_curso = 0
            finalizados = 0
            if "grupo_fecha_fin_prevista" in df.columns:
                hoy = datetime.today().date()
                en_curso = len(df[df["grupo_fecha_fin_prevista"].notna() & (df["grupo_fecha_fin_prevista"] >= hoy)])
                finalizados = len(df[df["grupo_fecha_fin_prevista"].notna() & (df["grupo_fecha_fin_prevista"] < hoy)])
    
            # Con diploma
            con_diploma = 0
            if "tiene_diploma" in df.columns:
                con_diploma = len(df[df["tiene_diploma"] == True])
    
            return {
                "total": total,
                "nuevos_mes": nuevos_mes,
                "en_curso": en_curso,
                "finalizados": finalizados,
                "con_diploma": con_diploma
            }
    
        except Exception as e:
            st.error(f"❌ Error al calcular estadísticas de participantes: {e}")
            return {
                "total": 0,
                "nuevos_mes": 0,
                "en_curso": 0,
                "finalizados": 0,
                "con_diploma": 0
            }

    # =========================
    # PERMISOS
    # =========================
    def can_modify_data(_self) -> bool:
        """Verifica si el usuario puede modificar datos."""
        return _self.rol in ["admin", "gestor"]

# =========================
# FUNCIÓN FACTORY (FUERA DE LA CLASE)
# =========================
def get_participantes_service(supabase, session_state) -> ParticipantesService:
    """Factory function para obtener instancia del servicio de participantes."""
    return ParticipantesService(supabase, session_state)
