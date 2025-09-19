import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

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
        st.error(f"❌ Error en {operation}: {error}")
        return pd.DataFrame()

    # =========================
    # EMPRESAS
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
    # MÉTODOS DE JERARQUÍA DE EMPRESAS
    # =========================
    
    @st.cache_data(ttl=300)
    def get_empresas_con_jerarquia(_self) -> pd.DataFrame:
        """Obtiene empresas con información jerárquica completa."""
        try:
            query = _self.supabase.table("empresas").select("""
                id, nombre, cif, direccion, telefono, email, ciudad, provincia,
                tipo_empresa, empresa_matriz_id, nivel_jerarquico,
                fecha_alta, created_at,
                empresa_matriz:empresas!empresa_matriz_id(id, nombre, cif),
                empresas_hijas:empresas!empresa_matriz_id(id, nombre, cif)
            """)
            
            # Aplicar filtro según rol
            if _self.rol == "gestor":
                # Gestor ve su empresa y sus clientes
                query = query.or_(f"id.eq.{_self.empresa_id},empresa_matriz_id.eq.{_self.empresa_id}")
            
            res = query.order("nivel_jerarquico", "nombre").execute()
            df = pd.DataFrame(res.data or [])
            
            if not df.empty:
                # Aplanar datos de empresa matriz
                if "empresa_matriz" in df.columns:
                    df["matriz_nombre"] = df["empresa_matriz"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                
                # Contar empresas hijas
                if "empresas_hijas" in df.columns:
                    df["num_clientes"] = df["empresas_hijas"].apply(
                        lambda x: len(x) if isinstance(x, list) else 0
                    )
                else:
                    df["num_clientes"] = 0
                    
                # Agregar indicador visual para jerarquía
                df["nombre_jerarquico"] = df.apply(lambda row: 
                    f"{'  └─ ' if row.get('nivel_jerarquico') == 2 else ''}{row['nombre']}", 
                    axis=1
                )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar empresas con jerarquía", e)
    
    def get_empresas_gestoras(_self) -> Dict[str, str]:
        """Obtiene empresas que pueden ser gestoras."""
        try:
            # Solo admin puede ver todas las gestoras
            if _self.rol != "admin":
                return {}
                
            res = _self.supabase.table("empresas").select("id, nombre").eq(
                "tipo_empresa", "GESTORA"
            ).execute()
            
            return {emp["nombre"]: emp["id"] for emp in (res.data or [])}
        except Exception as e:
            st.error(f"Error al cargar empresas gestoras: {e}")
            return {}
    
    def get_empresas_clientes_gestor(_self, gestor_id: str = None) -> pd.DataFrame:
        """Obtiene empresas clientes de un gestor específico."""
        try:
            if not gestor_id:
                gestor_id = _self.empresa_id
                
            if not gestor_id:
                return pd.DataFrame()
            
            res = _self.supabase.table("empresas").select("*").eq(
                "empresa_matriz_id", gestor_id
            ).execute()
            
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar empresas clientes", e)
    
    def create_empresa_con_jerarquia(_self, datos_empresa: Dict[str, Any]) -> bool:
        """Crea empresa respetando jerarquía según rol."""
        try:
            # Preparar datos según rol
            if _self.rol == "admin":
                # Admin puede especificar tipo y matriz
                tipo = datos_empresa.get("tipo_empresa", "CLIENTE_SAAS")
                
                if tipo == "CLIENTE_GESTOR":
                    if not datos_empresa.get("empresa_matriz_id"):
                        st.error("Empresa matriz requerida para CLIENTE_GESTOR")
                        return False
                    datos_empresa["nivel_jerarquico"] = 2
                elif tipo == "GESTORA":
                    datos_empresa["nivel_jerarquico"] = 1
                    datos_empresa["empresa_matriz_id"] = None
                else:  # CLIENTE_SAAS
                    datos_empresa["nivel_jerarquico"] = 1
                    datos_empresa["empresa_matriz_id"] = None
                    
            elif _self.rol == "gestor":
                # Gestor solo puede crear CLIENTE_GESTOR bajo su empresa
                datos_empresa.update({
                    "empresa_matriz_id": _self.empresa_id,
                    "tipo_empresa": "CLIENTE_GESTOR", 
                    "nivel_jerarquico": 2
                })
            else:
                st.error("Sin permisos para crear empresas")
                return False
            
            # Validaciones
            if not datos_empresa.get("nombre") or not datos_empresa.get("cif"):
                st.error("Nombre y CIF son obligatorios")
                return False
            
            if not validar_dni_cif(datos_empresa["cif"]):
                st.error("CIF inválido")
                return False
            
            # Verificar CIF único en el ámbito correspondiente
            if not _self._validar_cif_unico_jerarquico(datos_empresa["cif"]):
                st.error("Ya existe una empresa con ese CIF")
                return False
            
            # Crear empresa
            datos_empresa["fecha_alta"] = datetime.utcnow().isoformat()
            result = _self.supabase.table("empresas").insert(datos_empresa).execute()
            
            if result.data:
                _self.get_empresas_con_jerarquia.clear()
                _self.get_empresas_con_modulos.clear()
                return True
            else:
                st.error("Error al crear la empresa")
                return False
                
        except Exception as e:
            st.error(f"Error al crear empresa: {e}")
            return False
    
    def _validar_cif_unico_jerarquico(_self, cif: str, empresa_id: str = None) -> bool:
        """Valida CIF único respetando jerarquía."""
        try:
            query = _self.supabase.table("empresas").select("id").eq("cif", cif)
            
            if empresa_id:
                query = query.neq("id", empresa_id)
            
            # Para gestores, verificar solo en su ámbito jerárquico
            if _self.rol == "gestor":
                query = query.or_(f"id.eq.{_self.empresa_id},empresa_matriz_id.eq.{_self.empresa_id}")
            
            res = query.execute()
            return len(res.data or []) == 0
            
        except Exception as e:
            st.error(f"Error validando CIF: {e}")
            return False
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
            st.error(f"❌ Error al cargar métricas: {e}")
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
            st.error(f"❌ Error al cargar métricas admin: {e}")
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
            st.error(f"❌ Error al crear acción formativa: {e}")
            return False

    def update_accion_formativa(_self, accion_id: str, data: Dict[str, Any]) -> bool:
        """Actualiza una acción formativa."""
        try:
            _self.supabase.table("acciones_formativas").update(data).eq("id", accion_id).execute()
            # Limpiar cache
            _self.get_acciones_formativas.clear()
            return True
        except Exception as e:
            st.error(f"❌ Error al actualizar acción formativa: {e}")
            return False

    def delete_accion_formativa(_self, accion_id: str) -> bool:
        """Elimina una acción formativa."""
        try:
            _self.supabase.table("acciones_formativas").delete().eq("id", accion_id).execute()
            # Limpiar cache
            _self.get_acciones_formativas.clear()
            return True
        except Exception as e:
            st.error(f"❌ Error al eliminar acción formativa: {e}")
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

# =========================
# FUNCIONES DE UTILIDAD
# =========================
def get_data_service(supabase, session_state) -> DataService:
    """Factory function para obtener instancia del servicio."""
    return DataService(supabase, session_state)

def clear_all_cache():
    """Limpia todo el cache de datos."""
    st.cache_data.clear()
