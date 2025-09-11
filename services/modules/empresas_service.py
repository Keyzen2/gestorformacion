"""
Servicio especializado para gestión de empresas.
Maneja CRUD, métricas y filtros específicos de empresas.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any
from datetime import date
from ..base.base_service import BaseService
from ..cache.cache_decorators import dynamic_cache, metrics_cache, invalidate_cache_by_prefix


class EmpresasService(BaseService):
    """Servicio especializado para gestión de empresas"""
    
    @dynamic_cache(ttl=300)
    def get_empresas_con_modulos(self) -> pd.DataFrame:
        """Obtiene empresas con información completa de módulos."""
        try:
            if self.rol == "gestor":
                query = self.supabase.table("empresas").select("*").eq("id", self.empresa_id)
            else:
                query = self.supabase.table("empresas").select("*")

            empresas_res = query.execute()
            df_emp = pd.DataFrame(empresas_res.data or [])

            if df_emp.empty:
                return df_emp

            # Cargar datos CRM
            crm_res = self.supabase.table("crm_empresas").select("*").execute()
            df_crm = pd.DataFrame(crm_res.data or [])

            # Unir CRM a empresas
            if not df_crm.empty:
                df_emp = df_emp.merge(
                    df_crm[["empresa_id", "crm_activo", "crm_inicio", "crm_fin"]],
                    left_on="id",
                    right_on="empresa_id",
                    how="left",
                )
                if "empresa_id" in df_emp.columns:
                    df_emp = df_emp.drop("empresa_id", axis=1)
            else:
                df_emp["crm_activo"] = False
                df_emp["crm_inicio"] = None
                df_emp["crm_fin"] = None

            return df_emp

        except Exception as e:
            return self._handle_query_error("cargar empresas con módulos", e)

    @dynamic_cache(ttl=300)
    def get_empresas(self) -> pd.DataFrame:
        """Obtiene lista básica de empresas según el rol."""
        try:
            if self.rol == "gestor":
                query = self.supabase.table("empresas").select("*").eq("id", self.empresa_id)
            else:
                query = self.supabase.table("empresas").select("*")
            
            res = query.execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return self._handle_query_error("cargar empresas", e)

    def get_empresas_dict(self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de empresas."""
        df = self.get_empresas()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    @metrics_cache(ttl=600)
    def get_metricas_empresas(self) -> Dict[str, Any]:
        """Obtiene métricas específicas de empresas."""
        try:
            df = self.get_empresas_con_modulos()
            if df.empty:
                return {
                    "total_empresas": 0,
                    "nuevas_mes": 0,
                    "provincia_top": "N/D",
                    "modulos_activos": 0,
                }

            total = len(df)
            hoy = pd.Timestamp.now()
            inicio_mes = pd.Timestamp(hoy.year, hoy.month, 1)
            df_fecha = pd.to_datetime(df["created_at"], errors="coerce")
            nuevas = len(df[df_fecha >= inicio_mes])

            if "provincia" in df.columns and not df["provincia"].isna().all():
                provincia_counts = df["provincia"].value_counts()
                provincia_top = provincia_counts.index[0] if not provincia_counts.empty else "N/D"
            else:
                provincia_top = "N/D"

            modulos_cols = ["formacion_activo", "iso_activo", "rgpd_activo", "docu_avanzada_activo", "crm_activo"]
            modulos_totales = sum(df[col].fillna(False).sum() for col in modulos_cols if col in df.columns)

            return {
                "total_empresas": total,
                "nuevas_mes": nuevas,
                "provincia_top": provincia_top,
                "modulos_activos": int(modulos_totales),
            }

        except Exception as e:
            st.error(f"⚠️ Error al calcular métricas: {e}")
            return {"total_empresas": 0, "nuevas_mes": 0, "provincia_top": "Error", "modulos_activos": 0}

    def filter_empresas(self, df: pd.DataFrame, query: str = "", modulo_filter: str = "Todos") -> pd.DataFrame:
        """Filtra empresas por búsqueda y módulo activo."""
        if df.empty:
            return df

        df_filtered = df.copy()

        # Filtrar por búsqueda
        if query:
            query_lower = query.lower()
            mask = False
            for col in ["nombre", "cif", "email", "ciudad", "provincia"]:
                if col in df_filtered.columns:
                    mask = mask | df_filtered[col].astype(str).str.lower().str.contains(query_lower, na=False)
            df_filtered = df_filtered[mask]

        # Filtrar por módulo
        if modulo_filter != "Todos":
            modulo_map = {
                "Formación": "formacion_activo",
                "ISO 9001": "iso_activo",
                "RGPD": "rgpd_activo",
                "CRM": "crm_activo",
                "Doc. Avanzada": "docu_avanzada_activo",
            }
            if modulo_filter in modulo_map and modulo_map[modulo_filter] in df_filtered.columns:
                df_filtered = df_filtered[df_filtered[modulo_map[modulo_filter]] == True]

        return df_filtered

    def create_empresa(self, datos_empresa: Dict[str, Any]) -> bool:
        """Crea una nueva empresa con validaciones."""
        try:
            # Verificar permisos
            if self.rol != "admin":
                st.error("⚠️ Solo los administradores pueden crear empresas.")
                return False

            # Validar datos obligatorios
            if not datos_empresa.get("nombre"):
                st.error("⚠️ El nombre de la empresa es obligatorio.")
                return False

            if not datos_empresa.get("cif"):
                st.error("⚠️ El CIF de la empresa es obligatorio.")
                return False

            # Validar CIF
            from utils import validar_dni_cif
            cif = datos_empresa.get("cif", "")
            if not validar_dni_cif(cif):
                st.error(f"⚠️ El CIF {cif} no es válido.")
                return False

            # Verificar duplicados
            check = self.supabase.table("empresas").select("id").eq("cif", cif).execute()
            if check.data:
                st.error(f"⚠️ Ya existe una empresa con el CIF {cif}.")
                return False

            # Añadir fecha de alta
            datos_empresa["fecha_alta"] = date.today().isoformat()

            # Insertar empresa
            result = self.supabase.table("empresas").insert(datos_empresa).execute()
            if not result.data:
                st.error("⚠️ Error al crear la empresa.")
                return False

            empresa_id = result.data[0]["id"]

            # Crear registro CRM si está activado
            if datos_empresa.get("crm_activo"):
                crm_data = {"empresa_id": empresa_id, "crm_activo": True}
                crm_data["crm_inicio"] = datos_empresa.get("crm_inicio") or date.today().isoformat()
                self.supabase.table("crm_empresas").insert(crm_data).execute()

            # Invalidar cache relacionado
            invalidate_cache_by_prefix("empresas")

            return True

        except Exception as e:
            st.error(f"⚠️ Error al crear empresa: {e}")
            return False

    def update_empresa(self, empresa_id: str, datos_empresa: Dict[str, Any]) -> bool:
        """Actualiza datos de una empresa con validaciones."""
        try:
            if self.rol != "admin":
                st.error("⚠️ Solo los administradores pueden modificar empresas.")
                return False

            # Validar CIF si se actualiza
            if "cif" in datos_empresa and datos_empresa["cif"]:
                from utils import validar_dni_cif
                cif = datos_empresa["cif"]
                if not validar_dni_cif(cif):
                    st.error(f"⚠️ El CIF {cif} no es válido.")
                    return False

                # Verificar que no existe otro con mismo CIF
                check = self.supabase.table("empresas").select("id").eq("cif", cif).neq("id", empresa_id).execute()
                if check.data:
                    st.error(f"⚠️ Ya existe otra empresa con el CIF {cif}.")
                    return False

            # Actualizar empresa
            result = self.supabase.table("empresas").update(datos_empresa).eq("id", empresa_id).execute()
            if not result.data:
                st.error("⚠️ Error al actualizar la empresa.")
                return False

            # Manejar CRM
            if "crm_activo" in datos_empresa:
                crm_check = self.supabase.table("crm_empresas").select("*").eq("empresa_id", empresa_id).execute()
                
                if datos_empresa["crm_activo"]:
                    # Activar CRM
                    crm_data = {
                        "empresa_id": empresa_id,
                        "crm_activo": True,
                        "crm_inicio": datos_empresa.get("crm_inicio") or date.today().isoformat()
                    }
                    
                    if crm_check.data:
                        self.supabase.table("crm_empresas").update(crm_data).eq("empresa_id", empresa_id).execute()
                    else:
                        self.supabase.table("crm_empresas").insert(crm_data).execute()
                else:
                    # Desactivar CRM
                    if crm_check.data:
                        self.supabase.table("crm_empresas").update({
                            "crm_activo": False,
                            "crm_fin": date.today().isoformat()
                        }).eq("empresa_id", empresa_id).execute()

            # Invalidar cache relacionado
            invalidate_cache_by_prefix("empresas")

            return True

        except Exception as e:
            st.error(f"⚠️ Error al actualizar empresa: {e}")
            return False

    def delete_empresa(self, empresa_id: str) -> bool:
        """Elimina una empresa (solo admin)."""
        try:
            if self.rol != "admin":
                st.error("⚠️ Solo los administradores pueden eliminar empresas.")
                return False
            
            # Verificar si tiene datos relacionados
            usuarios_res = self.supabase.table("usuarios").select("id").eq("empresa_id", empresa_id).execute()
            if usuarios_res.data:
                st.error("⚠️ No se puede eliminar: la empresa tiene usuarios asociados.")
                return False

            grupos_res = self.supabase.table("grupos").select("id").eq("empresa_id", empresa_id).execute()
            if grupos_res.data:
                st.error("⚠️ No se puede eliminar: la empresa tiene grupos asociados.")
                return False

            # Eliminar registros relacionados primero
            self.supabase.table("crm_empresas").delete().eq("empresa_id", empresa_id).execute()
            
            # Eliminar empresa
            self.supabase.table("empresas").delete().eq("id", empresa_id).execute()
            
            # Invalidar cache relacionado
            invalidate_cache_by_prefix("empresas")
            
            return True
            
        except Exception as e:
            st.error(f"⚠️ Error al eliminar empresa: {e}")
            return False
