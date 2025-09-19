import streamlit as st
import pandas as pd
from typing import Dict, Any, List
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
    @st.cache_data(ttl=300)
    def get_participantes_completos(_self) -> pd.DataFrame:
        """Obtiene participantes con información de grupo y empresa."""
        try:
            query = _self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, dni, email, telefono, 
                fecha_nacimiento, sexo, created_at, updated_at,
                grupo:grupos!fk_participante_grupo (id, codigo_grupo),
                empresa:empresas!fk_participante_empresa (id, nombre, cif)
            """)
            query = _self._apply_empresa_filter(query)

            res = query.order("created_at", desc=True).execute()
            df = pd.DataFrame(res.data or [])

            # Aplanar relaciones
            if not df.empty:
                # Relación con grupos
                if "grupos" in df.columns:
                    df["grupo_codigo"] = df["grupos"].apply(
                        lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                    )
                    df["grupo_id"] = df["grupos"].apply(
                        lambda x: x.get("id") if isinstance(x, dict) else None
                    )
                else:
                    df["grupo_codigo"] = ""
                    df["grupo_id"] = None

                # Relación con empresas
                if "empresas" in df.columns:
                    df["empresa_nombre"] = df["empresas"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                    df["empresa_id"] = df["empresas"].apply(
                        lambda x: x.get("id") if isinstance(x, dict) else None
                    )
                else:
                    df["empresa_nombre"] = ""
                    df["empresa_id"] = None

            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes", e)
            
    @st.cache_data(ttl=300)
    def get_participantes_con_empresa_jerarquica(_self) -> pd.DataFrame:
        """Obtiene participantes con información jerárquica de empresa."""
        try:
            query = _self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, email, telefono, 
                fecha_nacimiento, sexo, created_at, grupo_id, empresa_id,
                grupo:grupos(id, codigo_grupo),
                empresa:empresas!participantes_empresa_id_fkey(
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
    # OPERACIONES CRUD
    # =========================
    def create_participante(_self, datos: Dict[str, Any]) -> bool:
        """Crea un nuevo participante con validaciones."""
        try:
            # Validaciones básicas
            if not datos.get("email"):
                st.error("⚠️ El email es obligatorio.")
                return False
                
            if not datos.get("nombre") or not datos.get("apellidos"):
                st.error("⚠️ Nombre y apellidos son obligatorios.")
                return False
                
            if datos.get("dni") and not validar_dni_cif(datos["dni"]):
                st.error("⚠️ DNI/CIF no válido.")
                return False

            # Verificar email único
            email_existe = _self.supabase.table("participantes").select("id").eq("email", datos["email"]).execute()
            if email_existe.data:
                st.error("⚠️ Ya existe un participante con ese email.")
                return False

            # Aplicar filtro de empresa si es gestor
            if _self.rol == "gestor":
                datos["empresa_id"] = _self.empresa_id

            # Añadir timestamps
            datos["created_at"] = datetime.utcnow().isoformat()
            datos["updated_at"] = datetime.utcnow().isoformat()

            # Crear participante
            result = _self.supabase.table("participantes").insert(datos).execute()

            if result.data:
                # Limpiar cache
                _self.get_participantes_completos.clear()
                return True
            else:
                st.error("⚠️ Error al crear el participante.")
                return False

        except Exception as e:
            st.error(f"⚠️ Error al crear participante: {e}")
            return False

    def update_participante(_self, participante_id: str, datos_editados: Dict[str, Any]) -> bool:
        """Actualiza un participante con validaciones."""
        try:
            # Validaciones
            if not datos_editados.get("email"):
                st.error("⚠️ El email es obligatorio.")
                return False
                
            if datos_editados.get("dni") and not validar_dni_cif(datos_editados["dni"]):
                st.error("⚠️ DNI/CIF no válido.")
                return False

            # Verificar email único (excluyendo el actual)
            email_existe = _self.supabase.table("participantes").select("id").eq("email", datos_editados["email"]).neq("id", participante_id).execute()
            if email_existe.data:
                st.error("⚠️ Ya existe otro participante con ese email.")
                return False

            # Verificar permisos
            if _self.rol == "gestor":
                participante = _self.supabase.table("participantes").select("empresa_id").eq("id", participante_id).execute()
                if not participante.data or participante.data[0].get("empresa_id") != _self.empresa_id:
                    st.error("⚠️ No tienes permisos para editar este participante.")
                    return False

            # Añadir timestamp de actualización
            datos_editados["updated_at"] = datetime.utcnow().isoformat()

            # Actualizar participante
            _self.supabase.table("participantes").update(datos_editados).eq("id", participante_id).execute()

            # Limpiar cache
            _self.get_participantes_completos.clear()

            return True

        except Exception as e:
            st.error(f"⚠️ Error al actualizar participante: {e}")
            return False

    def delete_participante(_self, participante_id: str) -> bool:
        """Elimina un participante con validaciones."""
        try:
            # Verificar permisos
            if _self.rol == "gestor":
                participante = _self.supabase.table("participantes").select("empresa_id").eq("id", participante_id).execute()
                if not participante.data or participante.data[0].get("empresa_id") != _self.empresa_id:
                    st.error("⚠️ No tienes permisos para eliminar este participante.")
                    return False

            # Eliminar asignaciones a grupos primero
            _self.supabase.table("participantes_grupos").delete().eq("participante_id", participante_id).execute()
            
            # Eliminar participante
            _self.supabase.table("participantes").delete().eq("id", participante_id).execute()

            # Limpiar cache
            _self.get_participantes_completos.clear()

            return True

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
        """Obtiene estadísticas de participantes."""
        try:
            df = _self.get_participantes_completos()
            
            if df.empty:
                return {
                    "total": 0,
                    "con_grupo": 0,
                    "sin_grupo": 0,
                    "este_mes": 0,
                    "datos_completos": 0
                }

            total = len(df)
            con_grupo = len(df[df["grupo_id"].notna()])
            sin_grupo = total - con_grupo
            
            # Participantes de este mes
            este_mes = 0
            if "created_at" in df.columns:
                este_mes_df = df[
                    pd.to_datetime(df["created_at"], errors="coerce").dt.month == datetime.now().month
                ]
                este_mes = len(este_mes_df)
            
            # Participantes con datos completos
            datos_completos = len(df[
                (df["email"].notna()) & 
                (df["nombre"].notna()) & 
                (df["apellidos"].notna())
            ])

            return {
                "total": total,
                "con_grupo": con_grupo,
                "sin_grupo": sin_grupo,
                "este_mes": este_mes,
                "datos_completos": datos_completos
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
# FUNCIÓN FACTORY (FUERA DE LA CLASE)
# =========================
def get_participantes_service(supabase, session_state) -> ParticipantesService:
    """Factory function para obtener instancia del servicio de participantes."""
    return ParticipantesService(supabase, session_state)
