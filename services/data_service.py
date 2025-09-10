"""
Servicios centralizados para consultas de datos optimizadas.
Unifica las consultas y aplica filtros por rol de forma consistente.
Versión mejorada para resolver problemas de interacción con listado_con_ficha
y evitar errores de caché en ajustes.
"""

import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import date
from utils import validar_dni_cif


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
                # Limpiar columna duplicada
                if "empresa_id" in df_emp.columns:
                    df_emp = df_emp.drop("empresa_id", axis=1)
            else:
                # Añadir columnas CRM vacías si no hay datos
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

            # Calcular métricas
            total = len(df)

            # Nuevas este mes
            hoy = pd.Timestamp.now()
            inicio_mes = pd.Timestamp(hoy.year, hoy.month, 1)
            df_fecha = pd.to_datetime(df["created_at"], errors="coerce")
            nuevas = len(df[df_fecha >= inicio_mes])

            # Provincia más común
            if "provincia" in df.columns and not df["provincia"].isna().all():
                provincia_counts = df["provincia"].value_counts()
                provincia_top = provincia_counts.index[0] if not provincia_counts.empty else "N/D"
            else:
                provincia_top = "N/D"

            # Contar módulos activos
            modulos_cols = ["formacion_activo", "iso_activo", "rgpd_activo", "docu_avanzada_activo", "crm_activo"]

            modulos_totales = 0
            for col in modulos_cols:
                if col in df.columns:
                    modulos_totales += df[col].fillna(False).sum()

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

            # Columnas para buscar
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

            # Validar CIF
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
                if datos_empresa.get("crm_inicio"):
                    crm_data["crm_inicio"] = datos_empresa["crm_inicio"]
                else:
                    crm_data["crm_inicio"] = date.today().isoformat()

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
            # Verificar permisos
            if _self.rol != "admin":
                st.error("⚠️ Solo los administradores pueden modificar empresas.")
                return False

            # Validar CIF si se actualiza
            if "cif" in datos_empresa and datos_empresa["cif"]:
                cif = datos_empresa["cif"]
                if not validar_dni_cif(cif):
                    st.error(f"⚠️ El CIF {cif} no es válido.")
                    return False

                # Verificar duplicados (excluyendo esta empresa)
                check = (
                    _self.supabase.table("empresas")
                    .select("id")
                    .eq("cif", cif)
                    .neq("id", empresa_id)
                    .execute()
                )
                if check.data:
                    st.error(f"⚠️ Ya existe otra empresa con el CIF {cif}.")
                    return False

            # Obtener datos actuales para verificar cambios en CRM
            empresa_actual = _self.supabase.table("empresas").select("*").eq("id", empresa_id).execute()

            if not empresa_actual.data:
                st.error("⚠️ No se encontró la empresa para actualizar.")
                return False

            # Actualizar empresa base
            update_data = {k: v for k, v in datos_empresa.items() if k not in {"crm_activo", "crm_inicio", "crm_fin"}}
            if update_data:
                _self.supabase.table("empresas").update(update_data).eq("id", empresa_id).execute()

            # Actualizar datos CRM si existen
            crm_fields = ["crm_activo", "crm_inicio", "crm_fin"]
            if any(field in datos_empresa for field in crm_fields):
                crm_data = {k: v for k, v in datos_empresa.items() if k in crm_fields}

                # Comprobar si ya existe un registro CRM
                crm_check = _self.supabase.table("crm_empresas").select("id").eq("empresa_id", empresa_id).execute()

                if crm_check.data:
                    # Actualizar registro existente
                    _self.supabase.table("crm_empresas").update(crm_data).eq("empresa_id", empresa_id).execute()
                elif datos_empresa.get("crm_activo"):
                    # Crear nuevo registro
                    crm_data["empresa_id"] = empresa_id
                    _self.supabase.table("crm_empresas").insert(crm_data).execute()

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
    # EMPRESAS ORIGINALES (compatibilidad)
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
    # USUARIOS
    # =========================
    @st.cache_data(ttl=300)
    def get_usuarios(_self, include_empresa: bool = True) -> pd.DataFrame:
        """Obtiene usuarios según el rol."""
        try:
            if include_empresa:
                query = _self.supabase.table("usuarios").select(
                    """
                    id, email, nombre_completo, role, telefono, created_at, 
                    ultimo_acceso, empresa_id, empresa:empresas(nombre)
                """
                )
            else:
                query = _self.supabase.table("usuarios").select("*")

            # Aplicar filtro por empresa para gestores
            query = _self._apply_empresa_filter(query, "usuarios")

            res = query.execute()
            df = pd.DataFrame(res.data or [])

            # Aplanar columna empresa
            if include_empresa and not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else "")
                df = df.drop("empresa", axis=1)

            return df

        except Exception as e:
            return _self._handle_query_error("cargar usuarios", e)

    # =========================
    # GRUPOS 
    # =========================
    @st.cache_data(ttl=300)
    def get_grupos_completos(_self) -> pd.DataFrame:
        """Obtiene grupos con información completa."""
        try:
            # Query optimizada con información esencial
            query = _self.supabase.table("grupos").select(
                """
                id, codigo_grupo, n_participantes_previstos, fecha_inicio_prevista, 
                fecha_fin_prevista, accion_id, empresa_id, tutor_id, estado,
                accion:acciones_formativas(id, nombre, area_profesional),
                empresa:empresas(id, nombre),
                tutor:tutores(id, nombre, apellidos)
            """
            )

            # Aplicar filtro por empresa para gestores
            query = _self._apply_empresa_filter(query, "grupos")

            res = query.execute()
            df = pd.DataFrame(res.data or [])

            if df.empty:
                return df

            # Procesar columnas anidadas (mantener ambos, planos y originales)
            if "accion" in df.columns:
                df["accion_nombre"] = df["accion"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else "")
                df["area_profesional"] = df["accion"].apply(
                    lambda x: x.get("area_profesional") if isinstance(x, dict) else ""
                )

            if "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else "")

            if "tutor" in df.columns:
                df["tutor_nombre"] = df["tutor"].apply(
                    lambda x: f"{x.get('nombre', '')} {x.get('apellidos', '')}" if isinstance(x, dict) else ""
                )

            return df

        except Exception as e:
            return _self._handle_query_error("cargar grupos completos", e)

    # =========================
    # PARTICIPANTES
    # =========================
    @st.cache_data(ttl=300)
    def get_participantes_completos(_self) -> pd.DataFrame:
        """Obtiene lista completa de participantes."""
        try:
            # Query optimizada
            query = _self.supabase.table("participantes").select(
                """
                id, nombre, apellidos, dni, email, telefono, sexo, fecha_nacimiento,
                nivel_estudios, situacion_laboral, grupo_id, asistencia, evaluacion,
                created_at, updated_at, empresa_id,
                grupo:grupos(id, codigo_grupo, accion_id, accion:acciones_formativas(nombre))
            """
            )

            # Aplicar filtro por empresa para gestores
            query = _self._apply_empresa_filter(query, "participantes")

            res = query.execute()
            df = pd.DataFrame(res.data or [])

            if df.empty:
                return df

            # Procesar columnas anidadas
            if "grupo" in df.columns:
                df["codigo_grupo"] = df["grupo"].apply(lambda x: x.get("codigo_grupo") if isinstance(x, dict) else "")
                df["accion_nombre"] = df["grupo"].apply(
                    lambda x: x.get("accion", {}).get("nombre") if isinstance(x, dict) and "accion" in x else ""
                )

            return df

        except Exception as e:
            return _self._handle_query_error("cargar participantes completos", e)

    # =========================
    # TUTORES
    # =========================
    @st.cache_data(ttl=300)
    def get_tutores(_self) -> pd.DataFrame:
        """Obtiene lista completa de tutores."""
        try:
            query = _self.supabase.table("tutores").select(
                """
                id, nombre, apellidos, email, telefono, nif, tipo_tutor,
                direccion, ciudad, provincia, codigo_postal, cv_url, 
                especialidad, created_at,
                empresa:empresas(id, nombre)
            """
            )
            query = _self._apply_empresa_filter(query, "tutores")

            res = query.order("nombre").execute()
            df = pd.DataFrame(res.data or [])

            # Aplanar empresa
            if not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else "")

            return df
        except Exception as e:
            return _self._handle_query_error("cargar tutores", e)

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
        return {f"{row['codigo']} - {row['nombre']}": row["codigo"] for _, row in df.iterrows()} if not df.empty else {}

    @st.cache_data(ttl=3600)
    def get_grupos_acciones(_self) -> pd.DataFrame:
        """Obtiene grupos de acciones."""
        try:
            res = _self.supabase.table("grupos_acciones").select("*").order("nombre").execute()
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar grupos de acciones", e)

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

    # =========================
    # AJUSTES
    # =========================
    # Importante: SIN decorador @st.cache_data para evitar hashing de self
    def get_ajustes_app(_self, campos: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene ajustes de la aplicación (sin cache de Streamlit para evitar Unhashable)."""
        try:
            query = _self.supabase.table("ajustes_app").select("*")

            # Filtrar campos si se especifica (string de campos separado por comas)
            if campos:
                campos_lista = [c.strip() for c in campos.split(",")]
                query = query.select(",".join(campos_lista))

            res = query.single().execute()

            if not res.data:
                return {}

            return res.data

        except Exception as e:
            st.error(f"⚠️ Error al cargar ajustes: {e}")
            return {}


# Factory function para obtener instancia de DataService
def get_data_service(supabase, session_state) -> DataService:
    """Crea y devuelve una instancia de DataService."""
    return DataService(supabase, session_state)
