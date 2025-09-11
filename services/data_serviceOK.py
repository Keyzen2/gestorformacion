"""
Servicios centralizados para consultas de datos optimizadas.
Unifica las consultas y aplica filtros por rol de forma consistente.
Versión mejorada para resolver problemas de interacción con listado_con_ficha
y evitar errores de caché en ajustes.
"""

import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import date, datetime

# -------------------------------------------------------------------
# Caché segura para ajustes (no pasa objetos no-hasheables a cache_data)
# -------------------------------------------------------------------
@st.cache_data(ttl=300, hash_funcs={object: lambda _: "X"})
def cached_get_ajustes_app(campos: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Obtiene ajustes de la app con caché segura.
    - No recibe el cliente de Supabase (lo toma de session_state).
    - Usa lista de strings (hasheable) para seleccionar campos.
    """
    sb = (
        st.session_state.get("supabase_public")
        or st.session_state.get("supabase_admin")
        or st.session_state.get("supabase")
    )
    if not sb:
        return {}

    try:
        if campos:
            sel = ",".join(campos)
            res = sb.table("ajustes_app").select(sel).single().execute()
        else:
            res = sb.table("ajustes_app").select("*").single().execute()
        return res.data or {}
    except Exception as e:
        st.error(f"⚠️ Error al cargar ajustes: {e}")
        return {}


class DataService:
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
        self.rol = session_state.role
        self.empresa_id = session_state.user.get("empresa_id")
        self.user_id = session_state.user.get("id")

    # =========================
    # MÉTODOS HELPER PARA FILTROS
    # =========================
    def _apply_empresa_filter(self, query, table_name: str, empresa_field: str = "empresa_id"):
        """Aplica filtro de empresa según el rol."""
        if self.rol == "gestor" and self.empresa_id:
            return query.eq(empresa_field, self.empresa_id)
        return query

    def _handle_query_error(self, operation: str, error: Exception) -> pd.DataFrame:
        """Manejo centralizado de errores en consultas."""
        st.error(f"⚠️ Error en {operation}: {error}")
        return pd.DataFrame()

    # =========================
    # EMPRESAS - MÉTODOS EXPANDIDOS
    # =========================
    @st.cache_data(ttl=300)
    def get_empresas_con_modulos(_self) -> pd.DataFrame:
        """Obtiene empresas con información completa de módulos."""
        try:
            if _self.rol == "gestor":
                query = _self.supabase.table("empresas").select("*").eq("id", _self.empresa_id)
            else:
                query = _self.supabase.table("empresas").select("*")

            empresas_res = query.execute()
            df_emp = pd.DataFrame(empresas_res.data or [])

            if df_emp.empty:
                return df_emp

            # Cargar datos CRM
            crm_res = _self.supabase.table("crm_empresas").select("*").execute()
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
            return _self._handle_query_error("cargar empresas con módulos", e)

    @st.cache_data(ttl=300)
    def get_metricas_empresas(_self) -> Dict[str, Any]:
        """Obtiene métricas específicas de empresas."""
        try:
            df = _self.get_empresas_con_modulos()
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

    def filter_empresas(_self, df: pd.DataFrame, query: str = "", modulo_filter: str = "Todos") -> pd.DataFrame:
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

    def create_empresa(_self, datos_empresa: Dict[str, Any]) -> bool:
        """Crea una nueva empresa con validaciones."""
        try:
            # Verificar permisos
            if _self.rol != "admin":
                st.error("⚠️ Solo los administradores pueden crear empresas.")
                return False

            # Validar datos obligatorios
            if not datos_empresa.get("nombre"):
                st.error("⚠️ El nombre de la empresa es obligatorio.")
                return False

            if not datos_empresa.get("cif"):
                st.error("⚠️ El CIF de la empresa es obligatorio.")
                return False

            # Validar CIF (import diferido)
            from utils import validar_dni_cif
            cif = datos_empresa.get("cif", "")
            if not validar_dni_cif(cif):
                st.error(f"⚠️ El CIF {cif} no es válido.")
                return False

            # Verificar duplicados
            check = _self.supabase.table("empresas").select("id").eq("cif", cif).execute()
            if check.data:
                st.error(f"⚠️ Ya existe una empresa con el CIF {cif}.")
                return False

            # Añadir fecha de alta
            datos_empresa["fecha_alta"] = date.today().isoformat()

            # Insertar empresa
            result = _self.supabase.table("empresas").insert(datos_empresa).execute()
            if not result.data:
                st.error("⚠️ Error al crear la empresa.")
                return False

            empresa_id = result.data[0]["id"]

            # Crear registro CRM si está activado
            if datos_empresa.get("crm_activo"):
                crm_data = {"empresa_id": empresa_id, "crm_activo": True}
                crm_data["crm_inicio"] = datos_empresa.get("crm_inicio") or date.today().isoformat()
                _self.supabase.table("crm_empresas").insert(crm_data).execute()

            # Limpiar cache de empresas
            _self.get_empresas_con_modulos.clear()
            _self.get_metricas_empresas.clear()

            return True

        except Exception as e:
            st.error(f"⚠️ Error al crear empresa: {e}")
            return False

    def update_empresa(_self, empresa_id: str, datos_empresa: Dict[str, Any]) -> bool:
        """Actualiza datos de una empresa con validaciones."""
        try:
            if _self.rol != "admin":
                st.error("⚠️ Solo los administradores pueden modificar empresas.")
                return False

            # Validar CIF si se actualiza
            if "cif" in datos_empresa and datos_empresa["cif"]:
                # Import diferido para evitar bucle
                from utils import validar_dni_cif
                cif = datos_empresa["cif"]
                if not validar_dni_cif(cif):
                    st.error(f"⚠️ El CIF {cif} no es válido.")
                    return False

                # Verificar que no existe otro con mismo CIF
                check = _self.supabase.table("empresas").select("id").eq("cif", cif).neq("id", empresa_id).execute()
                if check.data:
                    st.error(f"⚠️ Ya existe otra empresa con el CIF {cif}.")
                    return False

            # Actualizar empresa
            result = _self.supabase.table("empresas").update(datos_empresa).eq("id", empresa_id).execute()
            if not result.data:
                st.error("⚠️ Error al actualizar la empresa.")
                return False

            # Manejar CRM
            if "crm_activo" in datos_empresa:
                crm_check = _self.supabase.table("crm_empresas").select("*").eq("empresa_id", empresa_id).execute()
                
                if datos_empresa["crm_activo"]:
                    # Activar CRM
                    crm_data = {
                        "empresa_id": empresa_id,
                        "crm_activo": True,
                        "crm_inicio": datos_empresa.get("crm_inicio") or date.today().isoformat()
                    }
                    
                    if crm_check.data:
                        _self.supabase.table("crm_empresas").update(crm_data).eq("empresa_id", empresa_id).execute()
                    else:
                        _self.supabase.table("crm_empresas").insert(crm_data).execute()
                else:
                    # Desactivar CRM
                    if crm_check.data:
                        _self.supabase.table("crm_empresas").update({
                            "crm_activo": False,
                            "crm_fin": date.today().isoformat()
                        }).eq("empresa_id", empresa_id).execute()

            # Limpiar cache
            _self.get_empresas_con_modulos.clear()
            _self.get_metricas_empresas.clear()

            return True

        except Exception as e:
            st.error(f"⚠️ Error al actualizar empresa: {e}")
            return False

    def delete_empresa(_self, empresa_id: str) -> bool:
        """Elimina una empresa (solo admin)."""
        try:
            if _self.rol != "admin":
                st.error("⚠️ Solo los administradores pueden eliminar empresas.")
                return False
            
            # Verificar si tiene datos relacionados
            usuarios_res = _self.supabase.table("usuarios").select("id").eq("empresa_id", empresa_id).execute()
            if usuarios_res.data:
                st.error("⚠️ No se puede eliminar: la empresa tiene usuarios asociados.")
                return False

            grupos_res = _self.supabase.table("grupos").select("id").eq("empresa_id", empresa_id).execute()
            if grupos_res.data:
                st.error("⚠️ No se puede eliminar: la empresa tiene grupos asociados.")
                return False

            # Eliminar registros relacionados primero
            _self.supabase.table("crm_empresas").delete().eq("empresa_id", empresa_id).execute()
            
            # Eliminar empresa
            _self.supabase.table("empresas").delete().eq("id", empresa_id).execute()
            
            # Limpiar cache
            _self.get_empresas_con_modulos.clear()
            _self.get_metricas_empresas.clear()
            
            return True
            
        except Exception as e:
            st.error(f"⚠️ Error al eliminar empresa: {e}")
            return False

    # =========================
    # EMPRESAS ORIGINALES (mantenidos para compatibilidad)
    # =========================
    @st.cache_data(ttl=300)
    def get_empresas(_self) -> pd.DataFrame:
        """Obtiene lista de empresas según el rol."""
        try:
            if _self.rol == "gestor":
                query = _self.supabase.table("empresas").select("*").eq("id", _self.empresa_id)
            else:
                query = _self.supabase.table("empresas").select("*")
            
            res = query.execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar empresas", e)

    def get_empresas_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de empresas."""
        df = _self.get_empresas()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

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

    def get_acciones_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de acciones."""
        df = _self.get_acciones_formativas()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    def create_accion_formativa(_self, data: Dict[str, Any]) -> bool:
        """Crea una nueva acción formativa."""
        try:
            if _self.rol == "gestor":
                data["empresa_id"] = _self.empresa_id
            
            _self.supabase.table("acciones_formativas").insert(data).execute()
            # Limpiar cache
            _self.get_acciones_formativas.clear()
            return True
        except Exception as e:
            st.error(f"⚠️ Error al crear acción formativa: {e}")
            return False

    def update_accion_formativa(_self, accion_id: str, data: Dict[str, Any]) -> bool:
        """Actualiza una acción formativa."""
        try:
            _self.supabase.table("acciones_formativas").update(data).eq("id", accion_id).execute()
            # Limpiar cache
            _self.get_acciones_formativas.clear()
            return True
        except Exception as e:
            st.error(f"⚠️ Error al actualizar acción formativa: {e}")
            return False

    def delete_accion_formativa(_self, accion_id: str) -> bool:
        """Elimina una acción formativa."""
        try:
            _self.supabase.table("acciones_formativas").delete().eq("id", accion_id).execute()
            # Limpiar cache
            _self.get_acciones_formativas.clear()
            return True
        except Exception as e:
            st.error(f"⚠️ Error al eliminar acción formativa: {e}")
            return False

    # =========================
    # GRUPOS
    # =========================
    @st.cache_data(ttl=300)
    def get_grupos_completos(_self) -> pd.DataFrame:
        """Obtiene grupos con información de empresa y acción formativa."""
        try:
            query = _self.supabase.table("grupos").select("""
                id, nombre, fecha_inicio, fecha_fin, estado, modalidad,
                empresa_id, accion_formativa_id,
                empresa:empresas(id, nombre),
                accion_formativa:acciones_formativas(id, nombre)
            """)
            query = _self._apply_empresa_filter(query, "grupos")
            
            res = query.order("fecha_inicio", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar datos relacionados
            if not df.empty:
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                if "accion_formativa" in df.columns:
                    df["accion_nombre"] = df["accion_formativa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar grupos", e)

    @st.cache_data(ttl=300)
    def get_grupos(_self) -> pd.DataFrame:
        """Obtiene grupos básicos según el rol."""
        try:
            query = _self.supabase.table("grupos").select("*")
            query = _self._apply_empresa_filter(query, "grupos")
            
            res = query.order("nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar grupos", e)

    def get_grupos_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario nombre -> id de grupos."""
        df = _self.get_grupos()
        return {row["nombre"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    # =========================
    # PARTICIPANTES
    # =========================
    @st.cache_data(ttl=300)
    def get_participantes_completos(_self) -> pd.DataFrame:
        """Obtiene participantes con información de grupo y empresa."""
        try:
            query = _self.supabase.table("participantes").select("""
                id, nombre, apellidos, email, telefono, dni, 
                fecha_alta, estado, grupo_id,
                grupo:grupos(id, nombre, empresa_id,
                    empresa:empresas(id, nombre)
                )
            """)
            
            # Aplicar filtro según rol
            if _self.rol == "gestor" and _self.empresa_id:
                # Para gestores, filtrar por empresa a través del grupo
                grupos_empresa = _self.supabase.table("grupos").select("id").eq("empresa_id", _self.empresa_id).execute()
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
                df["empresa_nombre"] = df["grupo"].apply(
                    lambda x: x.get("empresa", {}).get("nombre") if isinstance(x, dict) else ""
                )
                df["empresa_id"] = df["grupo"].apply(
                    lambda x: x.get("empresa_id") if isinstance(x, dict) else ""
                )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes", e)

    @st.cache_data(ttl=300)
    def get_participantes(_self) -> pd.DataFrame:
        """Obtiene participantes básicos según el rol."""
        try:
            query = _self.supabase.table("participantes").select("*")
            
            # Aplicar filtro según rol
            if _self.rol == "gestor" and _self.empresa_id:
                # Para gestores, filtrar por empresa a través del grupo
                grupos_empresa = _self.supabase.table("grupos").select("id").eq("empresa_id", _self.empresa_id).execute()
                if grupos_empresa.data:
                    grupo_ids = [g["id"] for g in grupos_empresa.data]
                    query = query.in_("grupo_id", grupo_ids)
                else:
                    return pd.DataFrame()
            
            res = query.order("apellidos", "nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar participantes", e)

    # =========================
    # MÉTODOS PARA TUTORES
    # =========================
    
    @st.cache_data(ttl=300)
    def get_tutores_completos(_self) -> pd.DataFrame:
        """Obtiene tutores con información de empresa."""
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
            
            # Aplanar empresa
            if not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
            else:
                df["empresa_nombre"] = ""
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar tutores", e)

    def create_tutor(_self, data: Dict[str, Any]) -> bool:
        """Crea un nuevo tutor."""
        try:
            # Validaciones básicas
            if not data.get("nombre") or not data.get("apellidos"):
                st.error("⚠️ Nombre y apellidos son obligatorios.")
                return False
            
            if not data.get("tipo_tutor"):
                st.error("⚠️ Tipo de tutor es obligatorio.")
                return False
            
            # Verificar permisos
            if _self.rol == "gestor" and not _self.empresa_id:
                st.error("⚠️ Error: Gestor sin empresa asignada.")
                return False
            
            # Asegurar empresa_id para gestores
            if _self.rol == "gestor":
                data["empresa_id"] = _self.empresa_id
            
            # Verificar si ya existe tutor con mismo email
            if data.get("email"):
                existing = _self.supabase.table("tutores").select("id").eq("email", data["email"]).execute()
                if existing.data:
                    st.error("⚠️ Ya existe un tutor con este email.")
                    return False
            
            # Crear tutor
            data["created_at"] = datetime.now().isoformat()
            res = _self.supabase.table("tutores").insert(data).execute()
            
            if res.data:
                # Invalidar cache
                st.cache_data.clear()
                return True
            else:
                st.error("⌛ Error al crear tutor.")
                return False
                
        except Exception as e:
            st.error(f"⌛ Error al crear tutor: {e}")
            return False

    def update_tutor(_self, tutor_id: str, data: Dict[str, Any]) -> bool:
        """Actualiza un tutor existente."""
        try:
            # Verificar permisos
            if _self.rol == "gestor":
                # Verificar que el tutor pertenece a su empresa
                tutor_check = _self.supabase.table("tutores").select("empresa_id").eq("id", tutor_id).execute()
                if not tutor_check.data or tutor_check.data[0]["empresa_id"] != _self.empresa_id:
                    st.error("⚠️ No tienes permisos para editar este tutor.")
                    return False
            
            # Verificar email único (excluyendo el tutor actual)
            if data.get("email"):
                existing = _self.supabase.table("tutores").select("id").eq("email", data["email"]).neq("id", tutor_id).execute()
                if existing.data:
                    st.error("⚠️ Ya existe otro tutor con este email.")
                    return False
            
            # Actualizar
            data["updated_at"] = datetime.now().isoformat()
            res = _self.supabase.table("tutores").update(data).eq("id", tutor_id).execute()
            
            if res.data:
                # Invalidar cache
                st.cache_data.clear()
                return True
            else:
                st.error("⌛ Error al actualizar tutor.")
                return False
                
        except Exception as e:
            st.error(f"⌛ Error al actualizar tutor: {e}")
            return False

    def delete_tutor(_self, tutor_id: str) -> bool:
        """Elimina un tutor."""
        try:
            # Verificar permisos
            if _self.rol == "gestor":
                # Verificar que el tutor pertenece a su empresa
                tutor_check = _self.supabase.table("tutores").select("empresa_id").eq("id", tutor_id).execute()
                if not tutor_check.data or tutor_check.data[0]["empresa_id"] != _self.empresa_id:
                    st.error("⚠️ No tienes permisos para eliminar este tutor.")
                    return False
            
            # Verificar si el tutor está asignado a algún grupo
            tutores_grupos = _self.supabase.table("tutores_grupos").select("id").eq("tutor_id", tutor_id).execute()
            if tutores_grupos.data:
                st.error("⚠️ No se puede eliminar: el tutor está asignado a uno o más grupos.")
                return False
            
            # Eliminar tutor
            res = _self.supabase.table("tutores").delete().eq("id", tutor_id).execute()
            
            if res.data:
                # Invalidar cache
                st.cache_data.clear()
                return True
            else:
                st.error("⌛ Error al eliminar tutor.")
                return False
                
        except Exception as e:
            st.error(f"⌛ Error al eliminar tutor: {e}")
            return False

    # =========================
    # DOCUMENTOS
    # =========================
    @st.cache_data(ttl=300)
    def get_documentos(_self, tipo: Optional[str] = None) -> pd.DataFrame:
        """Obtiene documentos según el rol y tipo opcional."""
        try:
            query = _self.supabase.table("documentos").select("*")
            query = _self._apply_empresa_filter(query, "documentos")
            
            if tipo:
                query = query.eq("tipo", tipo)
            
            res = query.order("created_at", desc=True).execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar documentos", e)

    # =========================
    # ÁREAS PROFESIONALES Y GRUPOS DE ACCIONES
    # =========================
    @st.cache_data(ttl=3600)  # Cache más largo para datos estáticos
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
            res = _self.supabase.table("grupos_acciones").select("*").order("codigo").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar grupos de acciones", e)

    def get_grupos_acciones_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario de grupos de acciones."""
        df = _self.get_grupos_acciones()
        return {
            f"{row['codigo']} - {row['nombre']}": row['codigo'] 
            for _, row in df.iterrows()
        } if not df.empty else {}

    # =========================
    # USUARIOS
    # =========================
    @st.cache_data(ttl=300)
    def get_usuarios_completos(_self) -> pd.DataFrame:
        """Obtiene usuarios con información de empresa y grupo."""
        try:
            query = _self.supabase.table("usuarios").select("""
                id, auth_id, email, rol, dni, nombre_completo, telefono, 
                nombre, created_at, empresa_id, grupo_id,
                empresa:empresas(id, nombre),
                grupo:grupos(id, nombre)
            """)
            
            # Aplicar filtro según rol
            if _self.rol == "gestor" and _self.empresa_id:
                query = query.eq("empresa_id", _self.empresa_id)
            
            res = query.order("nombre_completo").execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar datos relacionados
            if not df.empty:
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                if "grupo" in df.columns:
                    df["grupo_nombre"] = df["grupo"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar usuarios", e)

    @st.cache_data(ttl=300)
    def get_usuarios(_self) -> pd.DataFrame:
        """Obtiene usuarios básicos según el rol."""
        try:
            query = _self.supabase.table("usuarios").select("*")
            
            # Aplicar filtro según rol
            if _self.rol == "gestor" and _self.empresa_id:
                query = query.eq("empresa_id", _self.empresa_id)
            
            res = query.order("nombre_completo").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar usuarios", e)

    # =========================
    # MÉTRICAS Y ESTADÍSTICAS
    # =========================
    @st.cache_data(ttl=600)  # Cache más largo para métricas
    def get_metricas_admin(_self) -> Dict[str, int]:
        """Obtiene métricas principales para admin."""
        try:
            # Contar empresas
            empresas_res = _self.supabase.table("empresas").select("id", count="exact").execute()
            total_empresas = empresas_res.count or 0
            
            # Contar usuarios
            usuarios_res = _self.supabase.table("usuarios").select("id", count="exact").execute()
            total_usuarios = usuarios_res.count or 0
            
            # Contar grupos
            grupos_res = _self.supabase.table("grupos").select("id", count="exact").execute()
            total_grupos = grupos_res.count or 0
            
            # Contar participantes
            participantes_res = _self.supabase.table("participantes").select("id", count="exact").execute()
            total_participantes = participantes_res.count or 0
            
            return {
                "empresas": total_empresas,
                "usuarios": total_usuarios,
                "grupos": total_grupos,
                "participantes": total_participantes
            }
        except Exception as e:
            st.error(f"⚠️ Error al calcular métricas: {e}")
            return {"empresas": 0, "usuarios": 0, "grupos": 0, "participantes": 0}

    @st.cache_data(ttl=600)
    def get_metricas_gestor(_self) -> Dict[str, int]:
        """Obtiene métricas para gestores (filtradas por empresa)."""
        try:
            if not _self.empresa_id:
                return {"grupos": 0, "participantes": 0, "tutores": 0}
            
            # Contar grupos de la empresa
            grupos_res = _self.supabase.table("grupos").select("id", count="exact").eq("empresa_id", _self.empresa_id).execute()
            total_grupos = grupos_res.count or 0
            
            # Contar tutores de la empresa
            tutores_res = _self.supabase.table("tutores").select("id", count="exact").eq("empresa_id", _self.empresa_id).execute()
            total_tutores = tutores_res.count or 0
            
            # Contar participantes (a través de grupos)
            grupos_ids_res = _self.supabase.table("grupos").select("id").eq("empresa_id", _self.empresa_id).execute()
            if grupos_ids_res.data:
                grupo_ids = [g["id"] for g in grupos_ids_res.data]
                participantes_res = _self.supabase.table("participantes").select("id", count="exact").in_("grupo_id", grupo_ids).execute()
                total_participantes = participantes_res.count or 0
            else:
                total_participantes = 0
            
            return {
                "grupos": total_grupos,
                "participantes": total_participantes,
                "tutores": total_tutores
            }
        except Exception as e:
            st.error(f"⚠️ Error al calcular métricas: {e}")
            return {"grupos": 0, "participantes": 0, "tutores": 0}

    # =========================
    # VALIDACIÓN DE PERMISOS
    # =========================
    def can_access_empresa_data(_self, empresa_id: str) -> bool:
        """Verifica si el usuario puede acceder a datos de una empresa."""
        if _self.rol == "admin":
            return True
        if _self.rol == "gestor":
            return empresa_id == _self.empresa_id
        return False

    def can_modify_data(_self) -> bool:
        """Verifica si el usuario puede modificar datos."""
        return _self.rol in ["admin", "gestor"]

    def can_create_users(_self) -> bool:
        """Verifica si el usuario puede crear usuarios."""
        return _self.rol == "admin"

    def can_access_admin_features(_self) -> bool:
        """Verifica si el usuario puede acceder a funciones de admin."""
        return _self.rol == "admin"

    def can_delete_data(_self) -> bool:
        """Verifica si el usuario puede eliminar datos."""
        return _self.rol in ["admin", "gestor"]

    # =========================
    # MÉTODOS DE UTILIDAD
    # =========================
    def get_empresa_actual(_self) -> Optional[Dict[str, Any]]:
        """Obtiene información de la empresa actual del gestor."""
        if _self.rol == "gestor" and _self.empresa_id:
            try:
                res = _self.supabase.table("empresas").select("*").eq("id", _self.empresa_id).single().execute()
                return res.data
            except Exception:
                return None
        return None

    def invalidate_cache(_self, cache_keys: Optional[List[str]] = None):
        """Invalida caché específico o todo el caché."""
        if cache_keys:
            # Invalidar cachés específicos
            for key in cache_keys:
                if hasattr(_self, key):
                    getattr(_self, key).clear()
        else:
            # Invalidar todo el caché
            st.cache_data.clear()

    def refresh_user_session(_self):
        """Refresca la sesión del usuario actual."""
        try:
            # Recargar información del usuario desde la base de datos
            if _self.user_id:
                user_res = _self.supabase.table("usuarios").select("*").eq("id", _self.user_id).single().execute()
                if user_res.data:
                    # Actualizar session_state con nueva información
                    _self.session_state.user.update(user_res.data)
                    _self.empresa_id = user_res.data.get("empresa_id")
                    _self.rol = user_res.data.get("rol")
        except Exception as e:
            st.error(f"⚠️ Error al refrescar sesión: {e}")

    # =========================
    # MÉTODOS PARA BUSQUEDAS Y FILTROS AVANZADOS
    # =========================
    def search_data(_self, table: str, search_query: str, columns: List[str]) -> pd.DataFrame:
        """Búsqueda avanzada en una tabla específica."""
        try:
            query = _self.supabase.table(table).select("*")
            query = _self._apply_empresa_filter(query, table)
            
            # Aplicar filtros de búsqueda
            if search_query:
                # Para PostgreSQL, usar ilike para búsqueda insensible a mayúsculas
                conditions = []
                for col in columns:
                    conditions.append(f"{col}.ilike.%{search_query}%")
                
                # Combinar condiciones con OR
                if conditions:
                    query = query.or_(",".join(conditions))
            
            res = query.execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error(f"buscar en {table}", e)

    def get_filtered_data(_self, table: str, filters: Dict[str, Any]) -> pd.DataFrame:
        """Obtiene datos con filtros específicos."""
        try:
            query = _self.supabase.table(table).select("*")
            query = _self._apply_empresa_filter(query, table)
            
            # Aplicar filtros
            for column, value in filters.items():
                if value is not None:
                    if isinstance(value, list):
                        query = query.in_(column, value)
                    else:
                        query = query.eq(column, value)
            
            res = query.execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error(f"filtrar {table}", e)

    # =========================
    # MÉTODOS PARA EXPORTACIÓN
    # =========================
    def export_to_excel(_self, dataframes: Dict[str, pd.DataFrame], filename: str = "export.xlsx") -> bytes:
        """Exporta múltiples DataFrames a un archivo Excel."""
        try:
            from io import BytesIO
            import pandas as pd
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for sheet_name, df in dataframes.items():
                    # Limpiar nombres de hoja (máximo 31 caracteres, sin caracteres especiales)
                    clean_name = sheet_name.replace("/", "_").replace("\\", "_")[:31]
                    df.to_excel(writer, sheet_name=clean_name, index=False)
            
            return output.getvalue()
        except Exception as e:
            st.error(f"⚠️ Error al exportar a Excel: {e}")
            return b""

    def export_empresa_data(_self, empresa_id: str) -> Dict[str, pd.DataFrame]:
        """Exporta todos los datos de una empresa específica."""
        try:
            if not _self.can_access_empresa_data(empresa_id):
                st.error("⚠️ No tienes permisos para exportar datos de esta empresa.")
                return {}
            
            # Recopilar datos de la empresa
            data = {}
            
            # Información de la empresa
            empresa_res = _self.supabase.table("empresas").select("*").eq("id", empresa_id).execute()
            if empresa_res.data:
                data["Empresa"] = pd.DataFrame(empresa_res.data)
            
            # Grupos
            grupos_res = _self.supabase.table("grupos").select("*").eq("empresa_id", empresa_id).execute()
            if grupos_res.data:
                data["Grupos"] = pd.DataFrame(grupos_res.data)
                
                # Participantes de los grupos
                grupo_ids = [g["id"] for g in grupos_res.data]
                participantes_res = _self.supabase.table("participantes").select("*").in_("grupo_id", grupo_ids).execute()
                if participantes_res.data:
                    data["Participantes"] = pd.DataFrame(participantes_res.data)
            
            # Tutores
            tutores_res = _self.supabase.table("tutores").select("*").eq("empresa_id", empresa_id).execute()
            if tutores_res.data:
                data["Tutores"] = pd.DataFrame(tutores_res.data)
            
            # Usuarios
            usuarios_res = _self.supabase.table("usuarios").select("*").eq("empresa_id", empresa_id).execute()
            if usuarios_res.data:
                data["Usuarios"] = pd.DataFrame(usuarios_res.data)
            
            return data
        except Exception as e:
            st.error(f"⚠️ Error al exportar datos de empresa: {e}")
            return {}


# =========================
# FUNCIONES DE UTILIDAD GLOBALES
# =========================
def get_data_service(supabase, session_state) -> DataService:
    """Factory function para obtener instancia del servicio."""
    return DataService(supabase, session_state)

def clear_all_cache():
    """Limpia todo el cache de datos."""
    st.cache_data.clear()

def refresh_cache_for_table(table_name: str):
    """Refresca el cache para una tabla específica."""
    # Esta función se puede expandir para invalidar cachés específicos
    st.cache_data.clear()
