"""
Servicio especializado para gestión de participantes.
Maneja CRUD, filtros y relaciones con grupos y empresas.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from ..base.base_service import BaseService
from ..cache.cache_decorators import dynamic_cache, invalidate_cache_by_prefix


class ParticipantesService(BaseService):
    """Servicio especializado para gestión de participantes"""
    
    @dynamic_cache(ttl=300)
    def get_participantes_completos(self) -> pd.DataFrame:
        """Obtiene participantes con información de grupo y empresa."""
        try:
            query = self.supabase.table("participantes").select("""
                id, nombre, apellidos, email, telefono, dni, 
                fecha_alta, estado, grupo_id, created_at,
                grupo:grupos(id, nombre, codigo_grupo, empresa_id,
                    empresa:empresas(id, nombre)
                )
            """)
            
            # Aplicar filtro según rol
            if self.rol == "gestor" and self.empresa_id:
                # Para gestores, filtrar por empresa a través del grupo
                grupos_empresa = self.supabase.table("grupos").select("id").eq("empresa_id", self.empresa_id).execute()
                if grupos_empresa.data:
                    grupo_ids = [g["id"] for g in grupos_empresa.data]
                    query = query.in_("grupo_id", grupo_ids)
                else:
                    # No hay grupos para esta empresa
                    return pd.DataFrame()
            
            res = query.order("apellidos", "nombre").execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar datos relacionados
            if not df.empty and "grupo" in df.columns:
                df["grupo_nombre"] = df["grupo"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
                df["grupo_codigo"] = df["grupo"].apply(
                    lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                )
                df["empresa_nombre"] = df["grupo"].apply(
                    lambda x: x.get("empresa", {}).get("nombre") if isinstance(x, dict) else ""
                )
                df["empresa_id_rel"] = df["grupo"].apply(
                    lambda x: x.get("empresa_id") if isinstance(x, dict) else ""
                )
            else:
                df["grupo_nombre"] = ""
                df["grupo_codigo"] = ""
                df["empresa_nombre"] = ""
                df["empresa_id_rel"] = ""
            
            return df
        except Exception as e:
            return self._handle_query_error("cargar participantes completos", e)

    @dynamic_cache(ttl=300)
    def get_participantes(self) -> pd.DataFrame:
        """Obtiene participantes básicos según el rol."""
        try:
            query = self.supabase.table("participantes").select("*")
            
            # Aplicar filtro según rol
            if self.rol == "gestor" and self.empresa_id:
                # Para gestores, filtrar por empresa a través del grupo
                grupos_empresa = self.supabase.table("grupos").select("id").eq("empresa_id", self.empresa_id).execute()
                if grupos_empresa.data:
                    grupo_ids = [g["id"] for g in grupos_empresa.data]
                    query = query.in_("grupo_id", grupo_ids)
                else:
                    return pd.DataFrame()
            
            res = query.order("apellidos", "nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar participantes", e)

    def filter_participantes(self, df: pd.DataFrame, search_query: str = "", grupo_filter: str = "Todos", empresa_filter: str = "Todos") -> pd.DataFrame:
        """Filtra participantes por búsqueda, grupo y empresa."""
        if df.empty:
            return df

        df_filtered = df.copy()

        # Filtrar por búsqueda de texto
        if search_query:
            search_lower = search_query.lower()
            mask = (
                df_filtered["nombre"].astype(str).str.lower().str.contains(search_lower, na=False) |
                df_filtered["apellidos"].astype(str).str.lower().str.contains(search_lower, na=False) |
                df_filtered["email"].astype(str).str.lower().str.contains(search_lower, na=False) |
                df_filtered["dni"].astype(str).str.lower().str.contains(search_lower, na=False)
            )
            df_filtered = df_filtered[mask]

        # Filtrar por grupo
        if grupo_filter != "Todos" and "grupo_codigo" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["grupo_codigo"] == grupo_filter]

        # Filtrar por empresa (solo admin)
        if empresa_filter != "Todos" and self.rol == "admin" and "empresa_nombre" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["empresa_nombre"] == empresa_filter]

        return df_filtered

    def create_participante(self, data: Dict[str, Any]) -> bool:
        """Crea un nuevo participante con validaciones."""
        try:
            # Validaciones básicas
            if not data.get("nombre") or not data.get("apellidos"):
                st.error("⚠️ Nombre y apellidos son obligatorios.")
                return False
            
            if not data.get("email"):
                st.error("⚠️ Email es obligatorio.")
                return False

            # Validar email único
            existing = self.supabase.table("participantes").select("id").eq("email", data["email"]).execute()
            if existing.data:
                st.error("⚠️ Ya existe un participante con este email.")
                return False

            # Verificar permisos de grupo
            if data.get("grupo_id"):
                if self.rol == "gestor":
                    # Verificar que el grupo pertenece a su empresa
                    grupo_check = self.supabase.table("grupos").select("empresa_id").eq("id", data["grupo_id"]).execute()
                    if not grupo_check.data or grupo_check.data[0]["empresa_id"] != self.empresa_id:
                        st.error("⚠️ No tienes permisos para asignar participantes a este grupo.")
                        return False

            # Validar DNI si se proporciona
            if data.get("dni"):
                from utils import validar_dni_cif
                if not validar_dni_cif(data["dni"]):
                    st.error("⚠️ El DNI/NIE proporcionado no es válido.")
                    return False

            # Añadir metadatos
            data["created_at"] = datetime.now().isoformat()
            data["fecha_alta"] = datetime.now().date().isoformat()
            data["estado"] = data.get("estado", "activo")

            # Crear participante
            result = self.supabase.table("participantes").insert(data).execute()
            if not result.data:
                st.error("⚠️ Error al crear el participante.")
                return False

            # Invalidar cache relacionado
            invalidate_cache_by_prefix("participantes")

            return True

        except Exception as e:
            st.error(f"⚠️ Error al crear participante: {e}")
            return False

    def update_participante(self, participante_id: str, data: Dict[str, Any]) -> bool:
        """Actualiza un participante existente."""
        try:
            # Verificar permisos
            if self.rol == "gestor":
                # Verificar que el participante pertenece a un grupo de su empresa
                part_check = self.supabase.table("participantes").select("""
                    grupo_id, grupo:grupos(empresa_id)
                """).eq("id", participante_id).execute()
                
                if not part_check.data:
                    st.error("⚠️ Participante no encontrado.")
                    return False
                    
                grupo_data = part_check.data[0].get("grupo", {})
                if grupo_data.get("empresa_id") != self.empresa_id:
                    st.error("⚠️ No tienes permisos para editar este participante.")
                    return False

            # Validar email único (excluyendo el participante actual)
            if data.get("email"):
                existing = self.supabase.table("participantes").select("id").eq("email", data["email"]).neq("id", participante_id).execute()
                if existing.data:
                    st.error("⚠️ Ya existe otro participante con este email.")
                    return False

            # Validar DNI si se proporciona
            if data.get("dni"):
                from utils import validar_dni_cif
                if not validar_dni_cif(data["dni"]):
                    st.error("⚠️ El DNI/NIE proporcionado no es válido.")
                    return False

            # Verificar permisos de nuevo grupo si se cambia
            if data.get("grupo_id") and self.rol == "gestor":
                grupo_check = self.supabase.table("grupos").select("empresa_id").eq("id", data["grupo_id"]).execute()
                if not grupo_check.data or grupo_check.data[0]["empresa_id"] != self.empresa_id:
                    st.error("⚠️ No tienes permisos para asignar participantes a este grupo.")
                    return False

            # Actualizar participante
            data["updated_at"] = datetime.now().isoformat()
            result = self.supabase.table("participantes").update(data).eq("id", participante_id).execute()
            if not result.data:
                st.error("⚠️ Error al actualizar el participante.")
                return False

            # Invalidar cache relacionado
            invalidate_cache_by_prefix("participantes")

            return True

        except Exception as e:
            st.error(f"⚠️ Error al actualizar participante: {e}")
            return False

    def delete_participante(self, participante_id: str) -> bool:
        """Elimina un participante."""
        try:
            # Verificar permisos
            if self.rol == "gestor":
                # Verificar que el participante pertenece a un grupo de su empresa
                part_check = self.supabase.table("participantes").select("""
                    grupo_id, grupo:grupos(empresa_id)
                """).eq("id", participante_id).execute()
                
                if not part_check.data:
                    st.error("⚠️ Participante no encontrado.")
                    return False
                    
                grupo_data = part_check.data[0].get("grupo", {})
                if grupo_data.get("empresa_id") != self.empresa_id:
                    st.error("⚠️ No tienes permisos para eliminar este participante.")
                    return False

            # Eliminar participante
            result = self.supabase.table("participantes").delete().eq("id", participante_id).execute()
            
            # Invalidar cache relacionado
            invalidate_cache_by_prefix("participantes")

            return True

        except Exception as e:
            st.error(f"⚠️ Error al eliminar participante: {e}")
            return False

    def get_metricas_participantes(self) -> Dict[str, Any]:
        """Obtiene métricas específicas de participantes."""
        try:
            df = self.get_participantes_completos()
            if df.empty:
                return {
                    "total_participantes": 0,
                    "con_grupo": 0,
                    "nuevos_mes": 0,
                    "activos": 0,
                }

            total = len(df)
            con_grupo = len(df[df["grupo_id"].notna()])
            activos = len(df[df["estado"] == "activo"]) if "estado" in df.columns else total

            # Participantes registrados este mes
            hoy = pd.Timestamp.now()
            inicio_mes = pd.Timestamp(hoy.year, hoy.month, 1)
            if "created_at" in df.columns:
                df_fecha = pd.to_datetime(df["created_at"], errors="coerce")
                nuevos = len(df[df_fecha >= inicio_mes])
            else:
                nuevos = 0

            return {
                "total_participantes": total,
                "con_grupo": con_grupo,
                "nuevos_mes": nuevos,
                "activos": activos,
            }

        except Exception as e:
            st.error(f"⚠️ Error al calcular métricas de participantes: {e}")
            return {"total_participantes": 0, "con_grupo": 0, "nuevos_mes": 0, "activos": 0}

    def import_participantes_masivo(self, participantes_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Importa múltiples participantes de forma masiva."""
        try:
            exitosos = 0
            errores = []
            
            for i, participante in enumerate(participantes_data):
                try:
                    # Validaciones básicas
                    if not participante.get("email"):
                        errores.append(f"Fila {i+1}: Email obligatorio")
                        continue
                    
                    # Verificar duplicados
                    existing = self.supabase.table("participantes").select("id").eq("email", participante["email"]).execute()
                    if existing.data:
                        errores.append(f"Fila {i+1}: Email {participante['email']} ya existe")
                        continue
                    
                    # Añadir metadatos
                    participante["created_at"] = datetime.now().isoformat()
                    participante["fecha_alta"] = datetime.now().date().isoformat()
                    participante["estado"] = participante.get("estado", "activo")
                    
                    # Insertar
                    self.supabase.table("participantes").insert(participante).execute()
                    exitosos += 1
                    
                except Exception as e:
                    errores.append(f"Fila {i+1}: {str(e)}")
            
            # Invalidar cache si hubo cambios
            if exitosos > 0:
                invalidate_cache_by_prefix("participantes")
            
            return {
                "exitosos": exitosos,
                "errores": errores,
                "total_procesados": len(participantes_data)
            }
            
        except Exception as e:
            st.error(f"⚠️ Error en importación masiva: {e}")
            return {"exitosos": 0, "errores": [str(e)], "total_procesados": 0}

    def export_participantes(self, filtros: Dict[str, Any] = None) -> pd.DataFrame:
        """Exporta participantes según filtros especificados."""
        try:
            df = self.get_participantes_completos()
            
            if filtros:
                # Aplicar filtros de exportación
                if filtros.get("grupo_id"):
                    df = df[df["grupo_id"] == filtros["grupo_id"]]
                
                if filtros.get("empresa_id") and self.rol == "admin":
                    df = df[df["empresa_id_rel"] == filtros["empresa_id"]]
                
                if filtros.get("estado"):
                    df = df[df["estado"] == filtros["estado"]]
                
                if filtros.get("fecha_desde"):
                    fecha_desde = pd.to_datetime(filtros["fecha_desde"])
                    df_fecha = pd.to_datetime(df["created_at"], errors="coerce")
                    df = df[df_fecha >= fecha_desde]
                
                if filtros.get("fecha_hasta"):
                    fecha_hasta = pd.to_datetime(filtros["fecha_hasta"])
                    df_fecha = pd.to_datetime(df["created_at"], errors="coerce")
                    df = df[df_fecha <= fecha_hasta]
            
            # Limpiar columnas para exportación
            if not df.empty:
                # Remover columnas de relación anidadas
                export_columns = [
                    "id", "nombre", "apellidos", "email", "telefono", "dni",
                    "fecha_alta", "estado", "grupo_nombre", "empresa_nombre", "created_at"
                ]
                df_export = df[[col for col in export_columns if col in df.columns]].copy()
                
                # Renombrar columnas para mayor claridad
                column_names = {
                    "grupo_nombre": "Grupo",
                    "empresa_nombre": "Empresa",
                    "created_at": "Fecha Registro",
                    "fecha_alta": "Fecha Alta"
                }
                df_export = df_export.rename(columns=column_names)
                
                return df_export
            
            return df
            
        except Exception as e:
            st.error(f"⚠️ Error al exportar participantes: {e}")
            return pd.DataFrame()

    def get_participantes_por_grupo(self, grupo_id: str) -> pd.DataFrame:
        """Obtiene participantes específicos de un grupo."""
        try:
            # Verificar permisos para el grupo
            if self.rol == "gestor":
                grupo_check = self.supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                if not grupo_check.data or grupo_check.data[0]["empresa_id"] != self.empresa_id:
                    st.error("⚠️ No tienes permisos para ver participantes de este grupo.")
                    return pd.DataFrame()
            
            query = self.supabase.table("participantes").select("*").eq("grupo_id", grupo_id)
            res = query.order("apellidos", "nombre").execute()
            
            return pd.DataFrame(res.data or [])
            
        except Exception as e:
            return self._handle_query_error("cargar participantes por grupo", e)

    def cambiar_estado_masivo(self, participante_ids: List[str], nuevo_estado: str) -> bool:
        """Cambia el estado de múltiples participantes."""
        try:
            # Verificar que el estado es válido
            estados_validos = ["activo", "inactivo", "finalizado", "baja"]
            if nuevo_estado not in estados_validos:
                st.error(f"⚠️ Estado '{nuevo_estado}' no válido. Debe ser uno de: {', '.join(estados_validos)}")
                return False
            
            # Verificar permisos para cada participante (solo si es gestor)
            if self.rol == "gestor":
                for part_id in participante_ids:
                    part_check = self.supabase.table("participantes").select("""
                        grupo_id, grupo:grupos(empresa_id)
                    """).eq("id", part_id).execute()
                    
                    if part_check.data:
                        grupo_data = part_check.data[0].get("grupo", {})
                        if grupo_data.get("empresa_id") != self.empresa_id:
                            st.error("⚠️ No tienes permisos para modificar algunos participantes.")
                            return False
            
            # Actualizar estados
            update_data = {
                "estado": nuevo_estado,
                "updated_at": datetime.now().isoformat()
            }
            
            for part_id in participante_ids:
                self.supabase.table("participantes").update(update_data).eq("id", part_id).execute()
            
            # Invalidar cache
            invalidate_cache_by_prefix("participantes")
            
            st.success(f"✅ Estado actualizado a '{nuevo_estado}' para {len(participante_ids)} participantes.")
            return True
            
        except Exception as e:
            st.error(f"⚠️ Error al cambiar estado masivo: {e}")
            return False
