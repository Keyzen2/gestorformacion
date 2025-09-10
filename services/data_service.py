"""
Servicios centralizados para consultas de datos optimizadas.
Unifica las consultas y aplica filtros por rol de forma consistente.
"""

import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from utils import validar_dni_cif

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
                    left_on="id", right_on="empresa_id", how="left"
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
            df_empresas = _self.get_empresas_con_modulos()
            
            if df_empresas.empty:
                return {
                    "total_empresas": 0,
                    "nuevas_mes": 0,
                    "provincia_top": "N/D",
                    "modulos_activos": 0
                }

            # Total empresas
            total_empresas = len(df_empresas)

            # Empresas nuevas este mes
            nuevas_mes = 0
            if "fecha_alta" in df_empresas.columns:
                este_mes = df_empresas[
                    pd.to_datetime(df_empresas["fecha_alta"], errors="coerce").dt.month == datetime.now().month
                ]
                nuevas_mes = len(este_mes)

            # Provincia más frecuente
            provincia_top = "N/D"
            if "provincia" in df_empresas.columns and not df_empresas["provincia"].isna().all():
                provincia_top = df_empresas["provincia"].value_counts().idxmax()

            # Módulos activos
            modulos_activos = 0
            for col in ["formacion_activo", "iso_activo", "rgpd_activo", "crm_activo", "docu_avanzada_activo"]:
                if col in df_empresas.columns:
                    modulos_activos += df_empresas[col].fillna(False).sum()

            return {
                "total_empresas": total_empresas,
                "nuevas_mes": nuevas_mes,
                "provincia_top": provincia_top,
                "modulos_activos": int(modulos_activos)
            }

        except Exception as e:
            st.error(f"⚠️ Error al calcular métricas de empresas: {e}")
            return {}

    def filter_empresas(_self, df_empresas: pd.DataFrame, query: str, modulo_filter: str) -> pd.DataFrame:
        """Aplica filtros de búsqueda y módulo a empresas."""
        try:
            df_filtered = df_empresas.copy()
            
            # Filtro por texto
            if query:
                q_lower = query.lower()
                df_filtered = df_filtered[
                    df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["cif"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["email"].fillna("").str.lower().str.contains(q_lower, na=False) |
                    df_filtered["provincia"].fillna("").str.lower().str.contains(q_lower, na=False) |
                    df_filtered["ciudad"].fillna("").str.lower().str.contains(q_lower, na=False)
                ]
            
            # Filtro por módulo
            if modulo_filter != "Todos":
                modulo_map = {
                    "Formación": "formacion_activo",
                    "ISO 9001": "iso_activo", 
                    "RGPD": "rgpd_activo",
                    "CRM": "crm_activo",
                    "Doc. Avanzada": "docu_avanzada_activo"
                }
                col_filtro = modulo_map.get(modulo_filter)
                if col_filtro and col_filtro in df_filtered.columns:
                    df_filtered = df_filtered[df_filtered[col_filtro] == True]

            return df_filtered
            
        except Exception as e:
            st.error(f"⚠️ Error al filtrar empresas: {e}")
            return df_empresas

    def prepare_empresas_display(_self, df_empresas: pd.DataFrame) -> pd.DataFrame:
        """Prepara datos de empresas para mostrar en listado_con_ficha."""
        try:
            df_display = df_empresas.copy()
            
            # Asegurar que tenemos todas las columnas necesarias
            columnas_obligatorias = [
                "formacion_activo", "formacion_inicio", "formacion_fin",
                "iso_activo", "iso_inicio", "iso_fin",
                "rgpd_activo", "rgpd_inicio", "rgpd_fin",
                "docu_avanzada_activo", "docu_avanzada_inicio", "docu_avanzada_fin",
                "crm_activo", "crm_inicio", "crm_fin"
            ]
            
            for col in columnas_obligatorias:
                if col not in df_display.columns:
                    if col.endswith("_activo"):
                        df_display[col] = False
                    else:
                        df_display[col] = None

            # Convertir fechas a formato apropiado
            fecha_cols = [col for col in df_display.columns if col.endswith(("_inicio", "_fin"))]
            for col in fecha_cols:
                if col in df_display.columns:
                    df_display[col] = pd.to_datetime(df_display[col], errors="coerce").dt.date

            return df_display
            
        except Exception as e:
            st.error(f"⚠️ Error al preparar datos de empresas: {e}")
            return df_empresas

    def get_modulos_stats(_self, df_empresas: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Obtiene estadísticas de uso de módulos."""
        try:
            modulos = {
                "Formación": "formacion_activo",
                "ISO 9001": "iso_activo",
                "RGPD": "rgpd_activo", 
                "CRM": "crm_activo",
                "Doc. Avanzada": "docu_avanzada_activo"
            }
            
            stats = {}
            total_empresas = len(df_empresas)
            
            for nombre, columna in modulos.items():
                if columna in df_empresas.columns:
                    activos = df_empresas[columna].fillna(False).sum()
                    porcentaje = (activos / total_empresas * 100) if total_empresas > 0 else 0
                    stats[nombre] = {
                        "activos": int(activos),
                        "porcentaje": porcentaje
                    }
                else:
                    stats[nombre] = {"activos": 0, "porcentaje": 0}
            
            return stats
            
        except Exception as e:
            st.error(f"⚠️ Error al calcular estadísticas de módulos: {e}")
            return {}

    # =========================
    # OPERACIONES CRUD PARA EMPRESAS
    # =========================
    def update_empresa(_self, empresa_id: str, datos_editados: Dict[str, Any]) -> bool:
        """Actualiza una empresa con validaciones."""
        try:
            # Validaciones
            if not datos_editados.get("nombre") or not datos_editados.get("cif"):
                st.error("⚠️ Nombre y CIF son obligatorios.")
                return False
                
            if not validar_dni_cif(datos_editados["cif"]):
                st.error("⚠️ CIF inválido.")
                return False

            # Separar datos de CRM
            crm_data = {}
            empresa_data = {}
            
            for key, value in datos_editados.items():
                if key.startswith("crm_"):
                    crm_data[key] = value
                else:
                    empresa_data[key] = value

            # Actualizar empresa
            _self.supabase.table("empresas").update(empresa_data).eq("id", empresa_id).execute()

            # Actualizar/crear CRM si hay datos
            if crm_data:
                crm_data["empresa_id"] = empresa_id
                # Intentar actualizar, si no existe lo crea (upsert)
                _self.supabase.table("crm_empresas").upsert(crm_data, on_conflict="empresa_id").execute()

            # Limpiar cache
            _self.get_empresas_con_modulos.clear()
            _self.get_metricas_empresas.clear()
            
            return True
            
        except Exception as e:
            st.error(f"⚠️ Error al actualizar empresa: {e}")
            return False

    def create_empresa(_self, datos_nuevos: Dict[str, Any]) -> bool:
        """Crea una nueva empresa con validaciones básicas."""
        try:
            # Validaciones
            if not datos_nuevos.get("nombre") or not datos_nuevos.get("cif"):
                st.error("⚠️ Nombre y CIF son obligatorios.")
                return False
                
            if not validar_dni_cif(datos_nuevos["cif"]):
                st.error("⚠️ CIF inválido.")
                return False

            # Separar datos de CRM
            crm_data = {}
            empresa_data = {}
            
            for key, value in datos_nuevos.items():
                if key.startswith("crm_"):
                    crm_data[key] = value
                else:
                    empresa_data[key] = value

            # Añadir fecha de alta
            empresa_data["fecha_alta"] = datetime.utcnow().isoformat()

            # Crear empresa
            result = _self.supabase.table("empresas").insert(empresa_data).execute()
            
            if result.data:
                empresa_id = result.data[0]["id"]
                
                # Crear registro CRM si hay datos
                if crm_data and any(crm_data.values()):
                    crm_data["empresa_id"] = empresa_id
                    _self.supabase.table("crm_empresas").insert(crm_data).execute()

                # Limpiar cache
                _self.get_empresas_con_modulos.clear()
                _self.get_metricas_empresas.clear()
                
                return True
            else:
                st.error("⚠️ Error al crear la empresa.")
                return False
                
        except Exception as e:
            st.error(f"⚠️ Error al crear empresa: {e}")
            return False

    def create_empresa_completa(_self, datos_empresa: Dict[str, Any]) -> bool:
        """Crea una empresa completa con módulos y fechas."""
        try:
            # Validaciones básicas
            if not datos_empresa.get("nombre") or not datos_empresa.get("cif"):
                st.error("⚠️ Nombre y CIF son obligatorios.")
                return False
                
            if not validar_dni_cif(datos_empresa["cif"]):
                st.error("⚠️ CIF inválido.")
                return False

            # Preparar datos base de empresa
            empresa_base = {
                "nombre": datos_empresa["nombre"],
                "cif": datos_empresa["cif"],
                "direccion": datos_empresa.get("direccion", ""),
                "telefono": datos_empresa.get("telefono", ""),
                "email": datos_empresa.get("email", ""),
                "representante_nombre": datos_empresa.get("representante_nombre", ""),
                "representante_dni": datos_empresa.get("representante_dni", ""),
                "ciudad": datos_empresa.get("ciudad", ""),
                "provincia": datos_empresa.get("provincia", ""),
                "codigo_postal": datos_empresa.get("codigo_postal", ""),
                "fecha_alta": datetime.utcnow().isoformat(),
                "formacion_activo": datos_empresa.get("formacion_activo", False),
                "iso_activo": datos_empresa.get("iso_activo", False),
                "rgpd_activo": datos_empresa.get("rgpd_activo", False),
                "docu_avanzada_activo": datos_empresa.get("docu_avanzada_activo", False)
            }

            # Añadir fechas de inicio si están definidas
            if datos_empresa.get("formacion_inicio"):
                empresa_base["formacion_inicio"] = datos_empresa["formacion_inicio"]
            if datos_empresa.get("iso_inicio"):
                empresa_base["iso_inicio"] = datos_empresa["iso_inicio"]
            if datos_empresa.get("rgpd_inicio"):
                empresa_base["rgpd_inicio"] = datos_empresa["rgpd_inicio"]

            # Crear empresa
            result = _self.supabase.table("empresas").insert(empresa_base).execute()
            
            if not result.data:
                st.error("⚠️ Error al crear la empresa.")
                return False

            empresa_id = result.data[0]["id"]

            # Crear registro CRM si está activado
            if datos_empresa.get("crm_activo"):
                crm_data = {
                    "empresa_id": empresa_id,
                    "crm_activo": True
                }
                if datos_empresa.get("crm_inicio"):
                    crm_data["crm_inicio"] = datos_empresa["crm_inicio"]
                else:
                    crm_data["crm_inicio"] = date.today().isoformat()
                
                _self.supabase.table("crm_empresas").insert(crm_data).execute()

            # Limpiar cache
            _self.get_empresas_con_modulos.clear()
            _self.get_metricas_empresas.clear()
            
            return True
            
        except Exception as e:
            st.error(f"⚠️ Error al crear empresa completa: {e}")
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

    # =========================
    # GRUPOS
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
                accion_formativa:acciones_formativas(id, nombre, modalidad, num_horas)
            """)
            query = _self._apply_empresa_filter(query, "grupos")
            
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
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar grupos", e)

    def get_grupos_dict(_self) -> Dict[str, str]:
        """Obtiene diccionario codigo_grupo -> id de grupos."""
        df = _self.get_grupos_completos()
        return {row["codigo_grupo"]: row["id"] for _, row in df.iterrows()} if not df.empty else {}

    # =========================
    # PARTICIPANTES
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
            query = _self._apply_empresa_filter(query, "participantes")
            
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
    # TUTORES
    # =========================
    @st.cache_data(ttl=300)
    def get_tutores_completos(_self) -> pd.DataFrame:
        """Obtiene tutores con información de empresa."""
        try:
            query = _self.supabase.table("tutores").select("""
                id, nombre, apellidos, email, telefono, nif, tipo_tutor,
                direccion, ciudad, provincia, codigo_postal, cv_url, 
                especialidad, created_at,
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
    # MÉTRICAS Y ESTADÍSTICAS
    # =========================
    @st.cache_data(ttl=300)
    def get_metricas_empresa(_self, empresa_id: str) -> Dict[str, int]:
        """Obtiene métricas específicas de una empresa."""
        try:
            if _self.rol != "admin" and empresa_id != _self.empresa_id:
                return {}
            
            # Usar función SQL optimizada si existe
            try:
                res = _self.supabase.rpc('get_gestor_metrics', {'empresa_uuid': empresa_id}).execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass  # Fallback a consultas individuales
            
            # Fallback manual
            grupos = len(_self.supabase.table("grupos").select("id").eq("empresa_id", empresa_id).execute().data or [])
            participantes = len(_self.supabase.table("participantes").select("id").eq("empresa_id", empresa_id).execute().data or [])
            documentos = len(_self.supabase.table("documentos").select("id").eq("empresa_id", empresa_id).execute().data or [])
            acciones = len(_self.supabase.table("acciones_formativas").select("id").eq("empresa_id", empresa_id).execute().data or [])
            
            return {
                "total_grupos": grupos,
                "total_participantes": participantes,
                "total_documentos": documentos,
                "total_acciones": acciones
            }
        except Exception as e:
            st.error(f"⚠️ Error al cargar métricas: {e}")
            return {}

    @st.cache_data(ttl=300)
    def get_metricas_admin(_self) -> Dict[str, int]:
        """Obtiene métricas globales para admin."""
        try:
            # Usar función SQL optimizada si existe
            try:
                res = _self.supabase.rpc('get_admin_metrics').execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass  # Fallback a consultas individuales
            
            # Fallback manual con COUNT
            empresas = _self.supabase.table("empresas").select("*", count="exact").execute().count or 0
            usuarios = _self.supabase.table("usuarios").select("*", count="exact").execute().count or 0
            cursos = _self.supabase.table("acciones_formativas").select("*", count="exact").execute().count or 0
            grupos = _self.supabase.table("grupos").select("*", count="exact").execute().count or 0
            
            return {
                "total_empresas": empresas,
                "total_usuarios": usuarios,
                "total_cursos": cursos,
                "total_grupos": grupos
            }
        except Exception as e:
            st.error(f"⚠️ Error al cargar métricas admin: {e}")
            return {}

    # =========================
    # BÚSQUEDAS OPTIMIZADAS
    # =========================
    def search_participantes(_self, search_term: str) -> pd.DataFrame:
        """Búsqueda optimizada de participantes."""
        if not search_term:
            return _self.get_participantes_completos()
        
        try:
            # Usar función SQL si existe
            try:
                res = _self.supabase.rpc('search_usuarios', {'search_term': search_term}).execute()
                return pd.DataFrame(res.data or [])
            except Exception:
                pass  # Fallback a búsqueda manual
            
            # Fallback manual
            df = _self.get_participantes_completos()
            if df.empty:
                return df
            
            search_lower = search_term.lower()
            mask = (
                df["nombre"].str.lower().str.contains(search_lower, na=False) |
                df["apellidos"].str.lower().str.contains(search_lower, na=False) |
                df["email"].str.lower().str.contains(search_lower, na=False) |
                df["dni"].str.lower().str.contains(search_lower, na=False)
            )
            return df[mask]
        except Exception as e:
            return _self._handle_query_error("buscar participantes", e)

    # =========================
    # OPERACIONES DE ESCRITURA
    # =========================
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

# =========================
# FUNCIONES DE UTILIDAD
# =========================
def get_data_service(supabase, session_state) -> DataService:
    """Factory function para obtener instancia del servicio."""
    return DataService(supabase, session_state)

def clear_all_cache():
    """Limpia todo el cache de datos."""
    st.cache_data.clear()
