import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from utils import validar_dni_cif

class GruposService:
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
    @st.cache_data(ttl=300)
    def get_grupos_completos(_self) -> pd.DataFrame:
        """Obtiene grupos con información de acción formativa."""
        try:
            query = _self.supabase.table("grupos").select("""
                id, codigo_grupo, fecha_inicio, fecha_fin, fecha_fin_prevista,
                aula_virtual, horario, localidad, provincia, cp,
                n_participantes_previstos, n_participantes_finalizados,
                n_aptos, n_no_aptos, observaciones, empresa_id, created_at,
                accion_formativa:acciones_formativas(id, nombre, modalidad, num_horas),
                empresa:empresas(id, nombre)
            """)
            query = _self._apply_empresa_filter(query)
            
            res = query.order("fecha_inicio", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar información de acción formativa
            if not df.empty and "accion_formativa" in df.columns:
                df["accion_nombre"] = df["accion_formativa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
                df["accion_modalidad"] = df["accion_formativa"].apply(
                    lambda x: x.get("modalidad") if isinstance(x, dict) else ""
                )
                df["accion_horas"] = df["accion_formativa"].apply(
                    lambda x: x.get("num_horas") if isinstance(x, dict) else 0
                )
                
            # Aplanar información de empresa
            if not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar grupos", e)

    @st.cache_data(ttl=600)
    def get_acciones_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de acciones formativas."""
        try:
            query = _self.supabase.table("acciones_formativas").select("id, nombre")
            query = _self._apply_empresa_filter(query)
            
            res = query.execute()
            return {a["nombre"]: a["id"] for a in (res.data or [])}
        except Exception as e:
            st.error(f"❌ Error al cargar acciones formativas: {e}")
            return {}

    @st.cache_data(ttl=600)
    def get_empresas_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de empresas (solo admin)."""
        try:
            if _self.rol != "admin":
                return {}
                
            res = _self.supabase.table("empresas").select("id, nombre").execute()
            return {e["nombre"]: e["id"] for e in (res.data or [])}
        except Exception as e:
            st.error(f"❌ Error al cargar empresas: {e}")
            return {}

    # =========================
    # OPERACIONES CRUD
    # =========================
    def create_grupo(_self, datos: Dict[str, Any]) -> bool:
        """Crea un nuevo grupo con validaciones."""
        try:
            # Validaciones
            if not datos.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return False
                
            if not datos.get("accion_formativa_id"):
                st.error("⚠️ Debes seleccionar una acción formativa.")
                return False

            # Verificar código único
            codigo_existe = _self.supabase.table("grupos").select("id").eq("codigo_grupo", datos["codigo_grupo"]).execute()
            if codigo_existe.data:
                st.error("⚠️ Ya existe un grupo con ese código.")
                return False

            # Aplicar filtro de empresa si es gestor
            if _self.rol == "gestor":
                datos["empresa_id"] = _self.empresa_id

            # Añadir timestamps y estado por defecto
            datos["created_at"] = datetime.utcnow().isoformat()
            datos["estado"] = datos.get("estado", "abierto")

            # Crear grupo
            result = _self.supabase.table("grupos").insert(datos).execute()

            if result.data:
                # Limpiar cache
                _self.get_grupos_completos.clear()
                return True
            else:
                st.error("⚠️ Error al crear el grupo.")
                return False

        except Exception as e:
            st.error(f"⚠️ Error al crear grupo: {e}")
            return False

    def update_grupo(_self, grupo_id: str, datos_editados: Dict[str, Any]) -> bool:
        """Actualiza un grupo con validaciones."""
        try:
            # Validaciones
            if not datos_editados.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return False

            # Verificar código único (excluyendo el actual)
            codigo_existe = _self.supabase.table("grupos").select("id").eq("codigo_grupo", datos_editados["codigo_grupo"]).neq("id", grupo_id).execute()
            if codigo_existe.data:
                st.error("⚠️ Ya existe otro grupo con ese código.")
                return False

            # Verificar permisos
            if _self.rol == "gestor":
                grupo = _self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                if not grupo.data or grupo.data[0].get("empresa_id") != _self.empresa_id:
                    st.error("⚠️ No tienes permisos para editar este grupo.")
                    return False

            # Añadir timestamp de actualización
            datos_editados["updated_at"] = datetime.utcnow().isoformat()

            # Actualizar grupo
            _self.supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()

            # Limpiar cache
            _self.get_grupos_completos.clear()

            return True

        except Exception as e:
            st.error(f"⚠️ Error al actualizar grupo: {e}")
            return False

    def delete_grupo(_self, grupo_id: str) -> bool:
        """Elimina un grupo con validaciones."""
        try:
            # Verificar permisos
            if _self.rol == "gestor":
                grupo = _self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                if not grupo.data or grupo.data[0].get("empresa_id") != _self.empresa_id:
                    st.error("⚠️ No tienes permisos para eliminar este grupo.")
                    return False

            # Verificar dependencias (participantes asignados)
            participantes = _self.supabase.table("participantes_grupos").select("id").eq("grupo_id", grupo_id).execute()
            if participantes.data:
                st.error("⚠️ No se puede eliminar. El grupo tiene participantes asignados.")
                return False

            # Eliminar grupo
            _self.supabase.table("grupos").delete().eq("id", grupo_id).execute()

            # Limpiar cache
            _self.get_grupos_completos.clear()

            return True

        except Exception as e:
            st.error(f"⚠️ Error al eliminar grupo: {e}")
            return False

    # =========================
    # GESTIÓN DE PARTICIPANTES
    # =========================
    @st.cache_data(ttl=300)
    def get_participantes_disponibles(_self) -> pd.DataFrame:
        """Obtiene participantes disponibles según el rol."""
        try:
            query = _self.supabase.table("participantes").select("id, nombre, apellidos, dni, email, empresa_id")
            query = _self._apply_empresa_filter(query)
            
            res = query.order("nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar participantes disponibles", e)

    @st.cache_data(ttl=300)
    def get_participantes_grupo(_self, grupo_id: str) -> pd.DataFrame:
        """Obtiene participantes asignados a un grupo específico."""
        try:
            # Obtener IDs de participantes en el grupo
            pg_res = _self.supabase.table("participantes_grupos")\
                .select("participante_id, fecha_asignacion")\
                .eq("grupo_id", grupo_id)\
                .execute()
            
            if not pg_res.data:
                return pd.DataFrame()
            
            participante_ids = [p["participante_id"] for p in pg_res.data]
            
            # Obtener datos completos de participantes
            part_res = _self.supabase.table("participantes")\
                .select("id, nombre, apellidos, email, dni")\
                .in_("id", participante_ids)\
                .execute()
            
            df = pd.DataFrame(part_res.data or [])
            
            # Añadir fecha de asignación
            if not df.empty:
                asignaciones = {p["participante_id"]: p["fecha_asignacion"] for p in pg_res.data}
                df["fecha_asignacion"] = df["id"].map(asignaciones)
            
            return df
            
        except Exception as e:
            return _self._handle_query_error("cargar participantes del grupo", e)

    def asignar_participante_grupo(_self, participante_id: str, grupo_id: str) -> bool:
        """Asigna un participante a un grupo."""
        try:
            # Verificar que no esté ya asignado
            existe = _self.supabase.table("participantes_grupos")\
                .select("id")\
                .eq("participante_id", participante_id)\
                .eq("grupo_id", grupo_id)\
                .execute()
            
            if existe.data:
                st.warning("⚠️ Este participante ya está asignado a este grupo.")
                return False
            
            # Verificar permisos del grupo
            if _self.rol == "gestor":
                grupo = _self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                if not grupo.data or grupo.data[0].get("empresa_id") != _self.empresa_id:
                    st.error("⚠️ No tienes permisos para gestionar este grupo.")
                    return False
            
            # Crear asignación
            _self.supabase.table("participantes_grupos").insert({
                "participante_id": participante_id,
                "grupo_id": grupo_id,
                "fecha_asignacion": datetime.utcnow().isoformat()
            }).execute()
            
            # Limpiar cache
            _self.get_participantes_grupo.clear()
            
            return True
            
        except Exception as e:
            st.error(f"⚠️ Error al asignar participante: {e}")
            return False

    def desasignar_participante_grupo(_self, participante_id: str, grupo_id: str) -> bool:
        """Desasigna un participante de un grupo."""
        try:
            # Verificar permisos del grupo
            if _self.rol == "gestor":
                grupo = _self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                if not grupo.data or grupo.data[0].get("empresa_id") != _self.empresa_id:
                    st.error("⚠️ No tienes permisos para gestionar este grupo.")
                    return False
            
            # Eliminar asignación
            _self.supabase.table("participantes_grupos")\
                .delete()\
                .eq("participante_id", participante_id)\
                .eq("grupo_id", grupo_id)\
                .execute()
            
            # Limpiar cache
            _self.get_participantes_grupo.clear()
            
            return True
            
        except Exception as e:
            st.error(f"⚠️ Error al desasignar participante: {e}")
            return False

    # =========================
    # IMPORTACIÓN MASIVA
    # =========================
    def importar_participantes_masivo(_self, grupo_id: str, dnis_list: List[str]) -> Dict[str, Any]:
        """Importa participantes masivamente por DNI."""
        try:
            # Verificar permisos del grupo
            if _self.rol == "gestor":
                grupo = _self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                if not grupo.data or grupo.data[0].get("empresa_id") != _self.empresa_id:
                    return {"success": False, "error": "Sin permisos para gestionar este grupo"}
            
            # Validar DNIs
            dnis_validos = [d for d in dnis_list if validar_dni_cif(d)]
            dnis_invalidos = set(dnis_list) - set(dnis_validos)
            
            # Buscar participantes existentes
            if _self.rol == "gestor":
                part_res = _self.supabase.table("participantes")\
                    .select("id, dni")\
                    .eq("empresa_id", _self.empresa_id)\
                    .in_("dni", dnis_validos)\
                    .execute()
            else:
                part_res = _self.supabase.table("participantes")\
                    .select("id, dni")\
                    .in_("dni", dnis_validos)\
                    .execute()
            
            participantes_existentes = {p["dni"]: p["id"] for p in (part_res.data or [])}
            
            # Verificar asignaciones existentes
            ya_asignados_res = _self.supabase.table("participantes_grupos")\
                .select("participante_id")\
                .eq("grupo_id", grupo_id)\
                .execute()
            ya_asignados_ids = {p["participante_id"] for p in (ya_asignados_res.data or [])}
            
            # Procesar asignaciones
            creados = 0
            errores = []
            
            for dni in dnis_validos:
                participante_id = participantes_existentes.get(dni)
                
                if not participante_id:
                    errores.append(f"DNI {dni} no encontrado")
                    continue
                    
                if participante_id in ya_asignados_ids:
                    errores.append(f"DNI {dni} ya asignado")
                    continue
                    
                try:
                    _self.supabase.table("participantes_grupos").insert({
                        "participante_id": participante_id,
                        "grupo_id": grupo_id,
                        "fecha_asignacion": datetime.utcnow().isoformat()
                    }).execute()
                    creados += 1
                except Exception as e:
                    errores.append(f"DNI {dni} - Error: {str(e)}")
            
            # Limpiar cache
            _self.get_participantes_grupo.clear()
            
            return {
                "success": True,
                "creados": creados,
                "errores": errores,
                "dnis_invalidos": list(dnis_invalidos),
                "total_procesados": len(dnis_list)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================
    # ESTADÍSTICAS
    # =========================
    def get_estadisticas_grupos(_self) -> Dict[str, Any]:
        """Obtiene estadísticas de grupos."""
        try:
            df = _self.get_grupos_completos()
            
            if df.empty:
                return {
                    "total": 0,
                    "activos": 0,
                    "finalizados": 0,
                    "proximos": 0,
                    "promedio_participantes": 0
                }

            total = len(df)
            hoy = datetime.now()
            
            # Grupos activos (en curso)
            activos = len(df[
                (pd.to_datetime(df["fecha_inicio"], errors="coerce") <= hoy) & 
                (df["fecha_fin"].isna() | (pd.to_datetime(df["fecha_fin"], errors="coerce") >= hoy))
            ])
            
            # Grupos finalizados
            finalizados = len(df[
                pd.to_datetime(df["fecha_fin"], errors="coerce") < hoy
            ])
            
            # Grupos próximos (aún no empezados)
            proximos = len(df[
                pd.to_datetime(df["fecha_inicio"], errors="coerce") > hoy
            ])
            
            # Promedio de participantes previstos
            promedio_participantes = df["n_participantes_previstos"].mean() if "n_participantes_previstos" in df.columns else 0

            return {
                "total": total,
                "activos": activos,
                "finalizados": finalizados,
                "proximos": proximos,
                "promedio_participantes": round(promedio_participantes, 1)
            }

        except Exception as e:
            st.error(f"⚠️ Error al calcular estadísticas: {e}")
            return {}

    # =========================
    # PERMISOS
    # =========================
    def can_modify_data(_self) -> bool:
        """Verifica si el usuario puede modificar datos."""
        return _self.rol in ["admin", "gestor"]

# =========================
# FUNCIÓN FACTORY
# =========================
def get_grupos_service(supabase, session_state) -> GruposService:
    """Factory function para obtener instancia del servicio de grupos."""
    return GruposService(supabase, session_state)
