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
                grupo:grupos(id, codigo_grupo),
                empresa:empresas(id, nombre)
            """)
            query = _self._apply_empresa_filter(query)
            
            res = query.order("created_at", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar relaciones
            if not df.empty:
                if "grupo" in df.columns:
                    df["grupo_codigo"] = df["grupo"].apply(
                        lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                    )
                    df["grupo_id"] = df["grupo"].apply(
                        lambda x: x.get("id") if isinstance(x, dict) else None
                    )
                
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes", e)

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
                    df_filtered["dni"].str.lower().str.contains(q_lower, na=False)
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
# CÓMO USAR EN LOS ARCHIVOS .PY
# =========================

# En pages/grupos.py - NUEVO IMPORT:
"""
# ❌ CAMBIAR ESTO:
from services.data_service import get_data_service

# ✅ POR ESTO:
from services.grupos_service import get_grupos_service

def main(supabase, session_state):
    # ❌ CAMBIAR ESTO:
    data_service = get_data_service(supabase, session_state)
    
    # ✅ POR ESTO:
    grupos_service = get_grupos_service(supabase, session_state)
    
    # Usar métodos específicos:
    df_grupos = grupos_service.get_grupos_completos()
    acciones_dict = grupos_service.get_acciones_dict()
    empresas_dict = grupos_service.get_empresas_dict()
    
    # Funciones CRUD:
    def guardar_grupo(grupo_id, datos_editados):
        success = grupos_service.update_grupo(grupo_id, datos_editados)
        if success:
            st.success("✅ Grupo actualizado correctamente.")
            st.rerun()
    
    def crear_grupo(datos_nuevos):
        success = grupos_service.create_grupo(datos_nuevos)
        if success:
            st.success("✅ Grupo creado correctamente.")
            st.rerun()
"""

# En pages/participantes.py - NUEVO IMPORT:
"""
# ❌ CAMBIAR ESTO:
from services.data_service import get_data_service

# ✅ POR ESTO:
from services.participantes_service import get_participantes_service

def main(supabase, session_state):
    # ❌ CAMBIAR ESTO:
    data_service = get_data_service(supabase, session_state)
    
    # ✅ POR ESTO:
    participantes_service = get_participantes_service(supabase, session_state)
    
    # Usar métodos específicos:
    df_participantes = participantes_service.get_participantes_completos()
    
    # Funciones CRUD:
    def guardar_participante(datos):
        if datos.get("id"):
            success = participantes_service.update_participante(datos["id"], datos)
        else:
            success = participantes_service.create_participante(datos)
        
        if success:
            st.success("✅ Participante guardado correctamente.")
            st.rerun()
"""
