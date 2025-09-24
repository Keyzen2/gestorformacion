import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
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
        st.error(f"Error en {operation}: {error}")
        return pd.DataFrame()

    # =========================
    # PARTICIPANTES
    # =========================
    @st.cache_data(ttl=300)
    def get_participantes_completos(_self) -> pd.DataFrame:
        """Obtiene participantes con información de grupo y empresa."""
        try:
            query = _self.supabase.table("participantes").select("""
                id, nif, nombre, apellidos, email, telefono, 
                fecha_nacimiento, sexo, created_at, updated_at, 
                grupo_id, empresa_id,
                grupo:grupos!fk_participante_grupo(id, codigo_grupo),
                empresa:empresas!fk_empresa(id, nombre)
            """)
            query = _self._apply_empresa_filter(query, "participantes")
        
            res = query.order("created_at", desc=True).execute()
            df = pd.DataFrame(res.data or [])
        
            if not df.empty:
                if "grupo" in df.columns:
                    df["grupo_codigo"] = df["grupo"].apply(
                        lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                    )
            
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
        
            return df
        except Exception as e:
            return _self._handle_query_error("cargar participantes", e)

    @st.cache_data(ttl=300)
    def get_participantes_para_formulario(_self, rol: str, empresa_id_gestor: str = None) -> pd.DataFrame:
        """Obtiene participantes preparados para el formulario según el rol."""
        try:
            df = _self.get_participantes_completos()
            
            if df.empty:
                return df
                
            # Según el rol, crear los campos apropiados para el formulario
            if rol == "admin":
                df["empresa_sel"] = df.get("empresa_nombre", "")
            elif rol == "gestor":
                if "empresa_nombre" in df.columns and not df["empresa_nombre"].isna().all():
                    df["empresa_asignada"] = df["empresa_nombre"]
                else:
                    try:
                        empresas_dict = _self.get_empresas_dict()
                        empresa_gestor_nombre = "No asignada"
                        for nombre, id_emp in empresas_dict.items():
                            if id_emp == empresa_id_gestor:
                                empresa_gestor_nombre = nombre
                                break
                        df["empresa_asignada"] = empresa_gestor_nombre
                    except:
                        df["empresa_asignada"] = "No asignada"
                
            # Siempre crear grupo_sel basado en grupo_codigo
            if "grupo_codigo" in df.columns:
                df["grupo_sel"] = df["grupo_codigo"]
            else:
                df["grupo_sel"] = ""
            
            return df
            
        except Exception as e:
            st.error(f"Error en get_participantes_para_formulario: {e}")
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

    def get_empresa_nombre(self, empresa_id: str) -> str:
        """Obtiene el nombre de una empresa por su ID."""
        try:
            result = self.supabase.table("empresas").select("nombre").eq("id", empresa_id).execute()
            if result.data:
                return result.data[0]["nombre"]
            return "Empresa no encontrada"
        except Exception as e:
            st.error(f"Error al obtener nombre de empresa: {e}")
            return "Error al cargar empresa"
            
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
            df_empresas = _self.get_empresas_con_modulos()

            if df_empresas.empty:
                return {
                    "total_empresas": 0,
                    "nuevas_mes": 0,
                    "provincia_top": "N/D",
                    "modulos_activos": 0
                }

            total_empresas = len(df_empresas)

            # Nuevas este mes
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
            st.error(f"Error al cargar métricas de empresas: {e}")
            return {}

    def get_estadisticas_modulos(_self, df_empresas: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
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
            st.error(f"Error al calcular estadísticas de módulos: {e}")
            return {}

    def filter_empresas(_self, df_empresas: pd.DataFrame, query: str = "", modulo_filter: str = "Todos") -> pd.DataFrame:
        """Filtra empresas por búsqueda y módulo."""
        try:
            df_filtered = df_empresas.copy()

            if query:
                q_lower = query.lower()
                df_filtered = df_filtered[
                    df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["cif"].str.lower().str.contains(q_lower, na=False) |
                    df_filtered["email"].fillna("").str.lower().str.contains(q_lower, na=False) |
                    df_filtered["provincia"].fillna("").str.lower().str.contains(q_lower, na=False) |
                    df_filtered["ciudad"].fillna("").str.lower().str.contains(q_lower, na=False)
                ]

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
            st.error(f"Error al filtrar empresas: {e}")
            return df_empresas
    # =========================
    # MÉTODOS DE JERARQUÍA DE EMPRESAS
    # =========================
    
    @st.cache_data(ttl=300)
    def get_empresas_con_jerarquia(_self) -> pd.DataFrame:
        """Obtiene empresas usando la vista v_empresas_jerarquia."""
        try:
            if _self.rol == "admin":
                # Admin ve todas las empresas con jerarquía completa
                query = _self.supabase.table("v_empresas_jerarquia").select("*")
                
            elif _self.rol == "gestor" and _self.empresa_id:
                # Gestor ve su empresa y sus clientes
                query = _self.supabase.table("v_empresas_jerarquia").select("*").or_(
                    f"id.eq.{_self.empresa_id},empresa_matriz_id.eq.{_self.empresa_id}"
                )
            else:
                return pd.DataFrame()
            
            res = query.order("nivel_jerarquico", "nombre").execute()
            df = pd.DataFrame(res.data or [])
            
            if not df.empty:
                # Agregar indicadores visuales para la jerarquía
                df["nombre_display"] = df.apply(lambda row: 
                    f"{'  └─ ' if row.get('nivel_jerarquico') == 2 else ''}{row['nombre']}", 
                    axis=1
                )
                
                # Agregar contexto tipo empresa
                df["tipo_display"] = df["tipo_empresa"].map({
                    "CLIENTE_SAAS": "Cliente SaaS",
                    "GESTORA": "Gestora",
                    "CLIENTE_GESTOR": "Cliente de Gestora"
                })
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar empresas con jerarquía", e)
    
    def get_empresas_gestoras_disponibles(_self) -> Dict[str, str]:
        """Obtiene empresas que pueden ser gestoras (tipo GESTORA)."""
        try:
            if _self.rol != "admin":
                return {}
                
            res = _self.supabase.table("empresas").select("id, nombre").eq(
                "tipo_empresa", "GESTORA"
            ).order("nombre").execute()
            
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
            ).order("nombre").execute()
            
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar empresas clientes", e)
    
    def get_empresas_para_asignacion(_self) -> Dict[str, str]:
        """Obtiene empresas que pueden asignarse a grupos/participantes según rol."""
        try:
            if _self.rol == "admin":
                # Admin puede asignar cualquier empresa
                res = _self.supabase.table("empresas").select("id, nombre").order("nombre").execute()
                
            elif _self.rol == "gestor" and _self.empresa_id:
                # Gestor puede asignar su empresa y sus clientes
                res = _self.supabase.table("empresas").select("id, nombre").or_(
                    f"id.eq.{_self.empresa_id},empresa_matriz_id.eq.{_self.empresa_id}"
                ).order("nombre").execute()
            else:
                return {}
            
            if res.data:
                return {emp["nombre"]: emp["id"] for emp in res.data}
            return {}
            
        except Exception as e:
            st.error(f"Error al cargar empresas para asignación: {e}")
            return {}
    
    def create_empresa_con_jerarquia(_self, datos_empresa: Dict[str, Any]) -> bool:
        """Crea empresa respetando jerarquía y roles."""
        try:
            # Preparar datos según rol
            if _self.rol == "admin":
                # Admin puede especificar tipo y matriz
                tipo = datos_empresa.get("tipo_empresa", "CLIENTE_SAAS")
                
                # Validar coherencia según tipo
                if tipo == "CLIENTE_GESTOR":
                    if not datos_empresa.get("empresa_matriz_id"):
                        st.error("Empresa matriz requerida para CLIENTE_GESTOR")
                        return False
                    # El trigger se encarga de establecer nivel_jerarquico = 2
                        
                elif tipo == "GESTORA":
                    # Gestora debe ser nivel 1 sin matriz
                    datos_empresa["nivel_jerarquico"] = 1
                    datos_empresa["empresa_matriz_id"] = None
                    
                elif tipo == "CLIENTE_SAAS":
                    # Cliente SaaS es nivel 1 sin matriz
                    datos_empresa["nivel_jerarquico"] = 1
                    datos_empresa["empresa_matriz_id"] = None
                    
            elif _self.rol == "gestor" and _self.empresa_id:
                # Gestor solo puede crear CLIENTE_GESTOR bajo su empresa
                datos_empresa.update({
                    "empresa_matriz_id": _self.empresa_id,
                    "tipo_empresa": "CLIENTE_GESTOR"
                    # nivel_jerarquico lo establece el trigger automáticamente
                })
            else:
                st.error("Sin permisos para crear empresas")
                return False
            
            # Validaciones básicas
            if not datos_empresa.get("nombre") or not datos_empresa.get("cif"):
                st.error("Nombre y CIF son obligatorios")
                return False
            
            if not validar_dni_cif(datos_empresa["cif"]):
                st.error("CIF inválido")
                return False
            
            # Verificar CIF único
            if not _self._validar_cif_unico_jerarquico(datos_empresa["cif"]):
                st.error("Ya existe una empresa con ese CIF")
                return False
            
            # Agregar metadatos
            datos_empresa.update({
                "creado_por_usuario_id": _self.user_id,
                "fecha_creacion": datetime.utcnow().isoformat()
            })
            
            # Crear empresa (triggers automáticos manejan jerarquía)
            result = _self.supabase.table("empresas").insert(datos_empresa).execute()
            
            if result.data:
                # Limpiar caches
                _self.get_empresas_con_jerarquia.clear()
                _self.get_empresas_con_modulos.clear()
                _self.get_empresas_para_asignacion.clear()
                return True
            else:
                st.error("Error al crear la empresa")
                return False
                
        except Exception as e:
            st.error(f"Error al crear empresa: {e}")
            return False
    
    def _validar_cif_unico_jerarquico(_self, cif: str, empresa_id: str = None) -> bool:
        """Valida CIF único en el ámbito jerárquico apropiado."""
        try:
            query = _self.supabase.table("empresas").select("id").eq("cif", cif)
            
            if empresa_id:
                query = query.neq("id", empresa_id)
            
            # Para gestores, verificar solo en su ámbito
            if _self.rol == "gestor" and _self.empresa_id:
                query = query.or_(f"id.eq.{_self.empresa_id},empresa_matriz_id.eq.{_self.empresa_id}")
            
            res = query.execute()
            return len(res.data or []) == 0
            
        except Exception as e:
            st.error(f"Error validando CIF: {e}")
            return False
    
    def update_empresa_con_jerarquia(_self, empresa_id: str, datos_editados: Dict[str, Any]) -> bool:
        """Actualiza empresa respetando permisos jerárquicos."""
        try:
            # Verificar permisos
            if not _self._puede_editar_empresa_jerarquica(empresa_id):
                st.error("No tienes permisos para editar esta empresa")
                return False
            
            # Filtrar campos protegidos (los triggers manejan la jerarquía)
            campos_protegidos = [
                "id", "empresa_matriz_id", "tipo_empresa", "nivel_jerarquico",
                "creado_por_usuario_id", "fecha_creacion"
            ]
            
            datos_filtrados = {
                k: v for k, v in datos_editados.items() 
                if k not in campos_protegidos
            }
            
            # Solo admin puede cambiar tipo_empresa
            if _self.rol == "admin" and "tipo_empresa" in datos_editados:
                datos_filtrados["tipo_empresa"] = datos_editados["tipo_empresa"]
                
                # Si cambia a GESTORA, limpiar matriz
                if datos_editados["tipo_empresa"] == "GESTORA":
                    datos_filtrados["empresa_matriz_id"] = None
            
            # Validar CIF si se está cambiando
            if "cif" in datos_filtrados:
                if not _self._validar_cif_unico_jerarquico(datos_filtrados["cif"], empresa_id):
                    st.error("Ya existe otra empresa con ese CIF")
                    return False
            
            res = _self.supabase.table("empresas").update(datos_filtrados).eq("id", empresa_id).execute()
            
            if res.data:
                # Limpiar caches
                _self.get_empresas_con_jerarquia.clear()
                _self.get_empresas_con_modulos.clear()
                _self.get_empresas_para_asignacion.clear()
                return True
            return False
            
        except Exception as e:
            st.error(f"Error al actualizar empresa: {e}")
            return False
    
    def _puede_editar_empresa_jerarquica(_self, empresa_id: str) -> bool:
        """Verifica permisos para editar empresa según jerarquía."""
        if _self.rol == "admin":
            return True
        
        elif _self.rol == "gestor" and _self.empresa_id:
            # Gestor puede editar su empresa y sus clientes
            try:
                empresa = _self.supabase.table("empresas").select("id, empresa_matriz_id").eq("id", empresa_id).execute()
                if not empresa.data:
                    return False
                
                empresa_data = empresa.data[0]
                
                # Puede editar su propia empresa
                if empresa_data["id"] == _self.empresa_id:
                    return True
                
                # Puede editar sus empresas clientes
                if empresa_data.get("empresa_matriz_id") == _self.empresa_id:
                    return True
                
                return False
            except:
                return False
        
        return False
    
    def delete_empresa_con_jerarquia(_self, empresa_id: str) -> bool:
        """Elimina empresa respetando jerarquía."""
        try:
            # Verificar permisos
            if not _self._puede_editar_empresa_jerarquica(empresa_id):
                st.error("No tienes permisos para eliminar esta empresa")
                return False
            
            # Verificar dependencias - empresas hijas
            hijas = _self.supabase.table("empresas").select("id").eq("empresa_matriz_id", empresa_id).execute()
            if hijas.data:
                st.error("No se puede eliminar. La empresa tiene empresas clientes asociadas.")
                return False
            
            # Verificar dependencias - participantes
            participantes = _self.supabase.table("participantes").select("id").eq("empresa_id", empresa_id).execute()
            if participantes.data:
                st.error("No se puede eliminar. La empresa tiene participantes asociados.")
                return False
            
            # Verificar dependencias - grupos
            grupos = _self.supabase.table("grupos").select("id").eq("empresa_id", empresa_id).execute()
            if grupos.data:
                st.error("No se puede eliminar. La empresa tiene grupos asociados.")
                return False
            
            # Eliminar empresa (CASCADE eliminará relaciones automáticamente)
            res = _self.supabase.table("empresas").delete().eq("id", empresa_id).execute()
            
            if res.data:
                # Limpiar caches
                _self.get_empresas_con_jerarquia.clear()
                _self.get_empresas_con_modulos.clear()
                _self.get_empresas_para_asignacion.clear()
                return True
            return False
            
        except Exception as e:
            st.error(f"Error al eliminar empresa: {e}")
            return False
    
    def get_estadisticas_jerarquia(_self) -> Dict[str, Any]:
        """Obtiene estadísticas usando la función SQL."""
        try:
            if _self.rol == "admin":
                # Admin ve estadísticas globales
                res = _self.supabase.rpc('get_estadisticas_jerarquia').execute()
                if res.data:
                    return res.data
                return {}
            elif _self.rol == "gestor" and _self.empresa_id:
                # Gestor ve sus estadísticas
                clientes = _self.get_empresas_clientes_gestor()
                empresa_info = _self.supabase.table("empresas").select("nombre").eq("id", _self.empresa_id).execute()
                
                return {
                    "empresa_gestora": empresa_info.data[0]["nombre"] if empresa_info.data else "",
                    "total_clientes": len(clientes),
                    "tipo_empresa": "GESTORA"
                }
            return {}
        except Exception as e:
            st.error(f"Error al obtener estadísticas: {e}")
            return {}
    
    def get_arbol_empresas(_self, empresa_raiz_id: str = None) -> pd.DataFrame:
        """Obtiene árbol jerárquico usando función SQL."""
        try:
            if empresa_raiz_id:
                res = _self.supabase.rpc('get_arbol_empresas', {'empresa_raiz_id': empresa_raiz_id}).execute()
            else:
                res = _self.supabase.rpc('get_arbol_empresas').execute()
            
            return pd.DataFrame(res.data or [])
        except Exception as e:
            return _self._handle_query_error("cargar árbol de empresas", e)
    # =========================
    # OPERACIONES CRUD PARA EMPRESAS
    # =========================
    def update_empresa(_self, empresa_id: str, datos_editados: Dict[str, Any]) -> bool:
        """Actualiza una empresa con validaciones."""
        try:
            if not datos_editados.get("nombre") or not datos_editados.get("cif"):
                st.error("Nombre y CIF son obligatorios.")
                return False

            if not validar_dni_cif(datos_editados["cif"]):
                st.error("CIF inválido.")
                return False

            # Separar datos de CRM
            crm_data = {}
            empresa_data = {}

            for key, value in datos_editados.items():
                if key.startswith("crm_"):
                    crm_data[key] = value
                else:
                    empresa_data[key] = value

            _self.supabase.table("empresas").update(empresa_data).eq("id", empresa_id).execute()

            if crm_data:
                crm_data["empresa_id"] = empresa_id
                _self.supabase.table("crm_empresas").upsert(crm_data, on_conflict="empresa_id").execute()

            # Limpiar cache
            _self.get_empresas_con_modulos.clear()
            _self.get_metricas_empresas.clear()

            return True

        except Exception as e:
            st.error(f"Error al actualizar empresa: {e}")
            return False

    def create_empresa(_self, datos_nuevos: Dict[str, Any]) -> bool:
        """Crea una nueva empresa con validaciones básicas."""
        try:
            if not datos_nuevos.get("nombre") or not datos_nuevos.get("cif"):
                st.error("Nombre y CIF son obligatorios.")
                return False

            if not validar_dni_cif(datos_nuevos["cif"]):
                st.error("CIF inválido.")
                return False

            # Separar datos de CRM
            crm_data = {}
            empresa_data = {}

            for key, value in datos_nuevos.items():
                if key.startswith("crm_"):
                    crm_data[key] = value
                else:
                    empresa_data[key] = value

            empresa_data["fecha_alta"] = datetime.utcnow().isoformat()

            result = _self.supabase.table("empresas").insert(empresa_data).execute()

            if result.data:
                empresa_id = result.data[0]["id"]

                if crm_data and any(crm_data.values()):
                    crm_data["empresa_id"] = empresa_id
                    _self.supabase.table("crm_empresas").insert(crm_data).execute()

                _self.get_empresas_con_modulos.clear()
                _self.get_metricas_empresas.clear()

                return True
            else:
                st.error("Error al crear la empresa.")
                return False

        except Exception as e:
            st.error(f"Error al crear empresa: {e}")
            return False

    def delete_empresa(_self, empresa_id: str) -> bool:
        """Elimina una empresa con validaciones."""
        try:
            # Verificar dependencias
            participantes = _self.supabase.table("participantes").select("id").eq("empresa_id", empresa_id).execute()
            if participantes.data:
                st.error("No se puede eliminar. La empresa tiene participantes asociados.")
                return False

            grupos = _self.supabase.table("grupos").select("id").eq("empresa_id", empresa_id).execute()
            if grupos.data:
                st.error("No se puede eliminar. La empresa tiene grupos asociados.")
                return False

            _self.supabase.table("empresas").delete().eq("id", empresa_id).execute()
            _self.supabase.table("crm_empresas").delete().eq("empresa_id", empresa_id).execute()

            _self.get_empresas_con_modulos.clear()
            _self.get_metricas_empresas.clear()

            return True

        except Exception as e:
            st.error(f"Error al eliminar empresa: {e}")
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

    # Sobrescribir el método create_accion_formativa existente
    def create_accion_formativa(self, data: Dict[str, Any]) -> bool:
        """Redirige al método con validaciones FUNDAE."""
        return self.create_accion_formativa_con_validaciones_fundae(data)

    # Sobrescribir el método update_accion_formativa existente  
    def update_accion_formativa(self, accion_id: str, data: Dict[str, Any]) -> bool:
        """Redirige al método con validaciones FUNDAE."""
        return self.update_accion_formativa_con_validaciones_fundae(accion_id, data)

    def delete_accion_formativa(_self, accion_id: str) -> bool:
        """Elimina una acción formativa."""
        try:
            _self.supabase.table("acciones_formativas").delete().eq("id", accion_id).execute()
            _self.get_acciones_formativas.clear()
            return True
        except Exception as e:
            st.error(f"Error al eliminar acción formativa: {e}")
            return False

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
                especialidad, created_at, empresa_id,
                empresa:empresas!tutores_empresa_id_fkey(id, nombre)
            """)
            query = _self._apply_empresa_filter(query, "tutores")
            
            res = query.order("nombre").execute()
            df = pd.DataFrame(res.data or [])
            
            if not df.empty:
                # Añadir nombre_completo
                df["nombre_completo"] = df["nombre"].astype(str) + " " + df["apellidos"].fillna("").astype(str)
                df["nombre_completo"] = df["nombre_completo"].str.strip()
                
                # Aplanar empresa
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar tutores", e)

    def get_tutores_por_empresa(_self, empresa_id: str = None) -> pd.DataFrame:
        """Obtiene tutores filtrados por empresa."""
        try:
            query = _self.supabase.table("tutores").select("""
                id, nombre, apellidos, email, telefono, nif, tipo_tutor,
                direccion, ciudad, provincia, codigo_postal, cv_url, 
                especialidad, created_at, empresa_id,
                empresa:empresas!tutores_empresa_id_fkey(id, nombre)
            """)
    
            # Aplicar filtro de empresa
            if _self.rol == "gestor" and _self.empresa_id:
                query = query.eq("empresa_id", _self.empresa_id)
            elif empresa_id:
                query = query.eq("empresa_id", empresa_id)
    
            res = query.order("nombre").execute()
            df = pd.DataFrame(res.data or [])
    
            # Aplanar empresa
            if not df.empty and "empresa" in df.columns:
                df["empresa_nombre"] = df["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
    
            return df
        except Exception as e:
            return _self._handle_query_error("cargar tutores por empresa", e)

    def create_tutor(self, datos_tutor: Dict[str, Any]) -> bool:
        """Crea un nuevo tutor."""
        try:
            if self.rol == "gestor":
                datos_tutor["empresa_id"] = self.empresa_id
            
            self.supabase.table("tutores").insert(datos_tutor).execute()
            self.get_tutores_completos.clear()
            return True
        except Exception as e:
            st.error(f"Error al crear tutor: {e}")
            return False
    
    def update_tutor(self, tutor_id: str, datos_tutor: Dict[str, Any]) -> bool:
        """Actualiza un tutor existente."""
        try:
            self.supabase.table("tutores").update(datos_tutor).eq("id", tutor_id).execute()
            self.get_tutores_completos.clear()
            return True
        except Exception as e:
            st.error(f"Error al actualizar tutor: {e}")
            return False
    
    def delete_tutor(self, tutor_id: str) -> bool:
        """Elimina un tutor."""
        try:
            # Verificar si tiene grupos asignados
            grupos = self.supabase.table("tutores_grupos").select("id").eq("tutor_id", tutor_id).execute()
            if grupos.data:
                st.error("No se puede eliminar. El tutor tiene grupos asignados.")
                return False
            
            self.supabase.table("tutores").delete().eq("id", tutor_id).execute()
            self.get_tutores_completos.clear()
            return True
        except Exception as e:
            st.error(f"Error al eliminar tutor: {e}")
            return False
        
    # =========================
    # USUARIOS
    # =========================
    @st.cache_data(ttl=300)
    def get_usuarios(_self, include_empresa=False) -> pd.DataFrame:
        """Obtiene usuarios con información opcional de empresa."""
        try:
            if include_empresa:
                query = _self.supabase.table("usuarios").select("""
                    id, auth_id, email, rol, empresa_id, nif, nombre_completo, 
                    telefono, nombre, grupo_id, created_at,
                    empresa:empresas!fk_empresa(id, nombre, cif),
                    grupo:grupos(id, codigo_grupo)
                """)
            else:
                query = _self.supabase.table("usuarios").select("*")
            
            query = _self._apply_empresa_filter(query, "usuarios")
            
            res = query.order("created_at", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            if include_empresa and not df.empty:
                # Aplanar relación de empresa
                if "empresa" in df.columns:
                    df["empresa_nombre"] = df["empresa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                    df["empresa_cif"] = df["empresa"].apply(
                        lambda x: x.get("cif") if isinstance(x, dict) else ""
                    )
                
                # Aplanar relación de grupo
                if "grupo" in df.columns:
                    df["grupo_codigo"] = df["grupo"].apply(
                        lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar usuarios", e)

    # =========================
    # ÁREAS PROFESIONALES Y GRUPOS DE ACCIONES
    # =========================
    @st.cache_data(ttl=3600)
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

    @st.cache_data(ttl=300)
    def get_documentos_completos(_self) -> pd.DataFrame:
        """Obtiene documentos con información de grupo."""
        try:
            query = _self.supabase.table("documentos").select("""
                id, tipo, archivo_path, fecha_subida, created_at, empresa_id,
                grupo:grupos(id, codigo_grupo),
                accion_formativa:acciones_formativas(id, nombre)
            """)
            query = _self._apply_empresa_filter(query, "documentos")
            
            res = query.order("created_at", desc=True).execute()
            df = pd.DataFrame(res.data or [])
            
            # Aplanar relaciones
            if not df.empty:
                if "grupo" in df.columns:
                    df["grupo_codigo"] = df["grupo"].apply(
                        lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                    )
                
                if "accion_formativa" in df.columns:
                    df["accion_nombre"] = df["accion_formativa"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
            
            return df
        except Exception as e:
            return _self._handle_query_error("cargar documentos", e)
    # =========================
    # NUEVOS MÉTODOS PARA VALIDACIONES FUNDAE EN data_service.py
    # =========================
    
    def validar_codigo_accion_fundae(self, codigo_accion: str, empresa_id: str, ano: int, accion_id: str = None) -> Tuple[bool, str]:
        """
        Valida que el código de acción sea único para la empresa gestora en el año especificado.
        FUNDAE: Los códigos de acción deben ser únicos por empresa gestora y año.
        
        *** CORRECCIÓN: Para acciones formativas, la validación es más flexible ***
        Ya que las acciones formativas son catálogo general, no tienen fechas específicas.
        """
        if not codigo_accion or not empresa_id:
            return False, "Código de acción y empresa requeridos"
        
        try:
            # *** CORRECCIÓN: Buscar duplicados solo por empresa y código ***
            # No por año específico, ya que las acciones formativas no tienen fecha_inicio obligatoria
            query = self.supabase.table("acciones_formativas").select("id, codigo_accion").eq(
                "codigo_accion", codigo_accion
            ).eq("empresa_id", empresa_id)
            
            # Excluir la acción actual si estamos editando
            if accion_id:
                query = query.neq("id", accion_id)
            
            res = query.execute()
            
            if res.data:
                return False, f"Ya existe una acción con código '{codigo_accion}' para esta empresa gestora"
            
            return True, ""
            
        except Exception as e:
            return False, f"Error al validar código: {e}"
    
    def generar_codigo_accion_sugerido(self, empresa_id: str, ano: int = None) -> Tuple[str, str]:
        """
        Genera un código de acción sugerido para una empresa y año.
        Formato: [PREFIJO_EMPRESA][ANO][NUMERO_SECUENCIAL]
        """
        try:
            if not ano:
                ano = datetime.now().year
            
            # Obtener información de la empresa
            empresa_res = self.supabase.table("empresas").select("nombre, cif").eq("id", empresa_id).execute()
            if not empresa_res.data:
                return "", "Empresa no encontrada"
            
            empresa_data = empresa_res.data[0]
            empresa_nombre = empresa_data.get("nombre", "")
            
            # Generar prefijo basado en el nombre de la empresa (primeras 3 letras)
            prefijo = "".join([c.upper() for c in empresa_nombre if c.isalpha()])[:3]
            if len(prefijo) < 3:
                prefijo = prefijo.ljust(3, 'X')
            
            # Obtener acciones existentes para esta empresa en el año
            acciones_existentes = self.supabase.table("acciones_formativas").select(
                "codigo_accion"
            ).eq("empresa_id", empresa_id).gte(
                "fecha_inicio", f"{ano}-01-01"
            ).lt("fecha_inicio", f"{ano + 1}-01-01").execute()
            
            # Extraer números secuenciales usados
            patron_base = f"{prefijo}{str(ano)[-2:]}"  # Últimos 2 dígitos del año
            numeros_usados = []
            
            for accion in acciones_existentes.data or []:
                codigo = accion["codigo_accion"]
                if codigo.startswith(patron_base):
                    try:
                        numero_str = codigo[len(patron_base):]
                        numero = int(numero_str)
                        numeros_usados.append(numero)
                    except ValueError:
                        continue
            
            # Encontrar siguiente número
            siguiente_numero = 1
            while siguiente_numero in numeros_usados:
                siguiente_numero += 1
            
            codigo_sugerido = f"{patron_base}{siguiente_numero:03d}"  # 3 dígitos con padding
            return codigo_sugerido, ""
            
        except Exception as e:
            return "", f"Error al generar código sugerido: {e}"
    
    def create_accion_formativa_con_validaciones_fundae(self, data: Dict[str, Any]) -> bool:
        """
        Crea acción formativa con validaciones FUNDAE completas.
        """
        try:
            # Asignar empresa según rol
            if self.rol == "gestor":
                data["empresa_id"] = self.empresa_id
            elif self.rol == "admin":
                if not data.get("empresa_id"):
                    st.error("Debe especificar empresa para la acción formativa")
                    return False
            else:
                st.error("Sin permisos para crear acciones formativas")
                return False
            
            # *** CORRECIÓN: Campos obligatorios sin fecha_inicio ***
            # La fecha_inicio es obligatoria para GRUPOS, no para ACCIONES FORMATIVAS
            campos_obligatorios = ["nombre", "codigo_accion", "modalidad", "num_horas"]
            
            for campo in campos_obligatorios:
                if not data.get(campo):
                    st.error(f"Campo '{campo}' es obligatorio para FUNDAE")
                    return False
            
            # *** CORRECCIÓN: Validar código sin necesidad de año específico ***
            # Para acciones formativas, usamos año actual por defecto
            codigo_accion = data["codigo_accion"]
            empresa_id = data["empresa_id"]
            ano_actual = datetime.now().year
            
            es_valido, error_codigo = self.validar_codigo_accion_fundae(
                codigo_accion, empresa_id, ano_actual
            )
            
            if not es_valido:
                st.error(f"Código FUNDAE inválido: {error_codigo}")
                return False
            
            # Normalizar modalidad
            modalidad_normalizada = data["modalidad"].upper()
            if modalidad_normalizada == "ONLINE":
                modalidad_normalizada = "TELEFORMACION"
            elif modalidad_normalizada == "PRESENCIAL":
                modalidad_normalizada = "PRESENCIAL"  
            elif modalidad_normalizada == "MIXTA":
                modalidad_normalizada = "MIXTA"
            
            data["modalidad"] = modalidad_normalizada
            
            # Validar modalidad FUNDAE
            modalidades_validas = ["PRESENCIAL", "TELEFORMACION", "MIXTA"]
            if data["modalidad"] not in modalidades_validas:
                st.error(f"Modalidad debe ser una de: {', '.join(modalidades_validas)}")
                return False
            
            # Validar horas
            try:
                horas = int(data["num_horas"])
                if horas <= 0 or horas > 9999:
                    st.error("Las horas deben estar entre 1 y 9999")
                    return False
            except (ValueError, TypeError):
                st.error("Las horas deben ser un número entero")
                return False
            
            # Agregar metadatos (sin fecha_inicio obligatoria)
            data.update({
                "created_at": datetime.utcnow().isoformat(),
                "validada_fundae": True,
                "ano_fundae": ano_actual  # Año de creación, no de inicio
            })
            
            # Crear acción formativa
            res = self.supabase.table("acciones_formativas").insert(data).execute()
            
            if res.data:
                self.get_acciones_formativas.clear()
                return True
            else:
                st.error("Error al crear la acción formativa")
                return False
                
        except Exception as e:
            st.error(f"Error al crear acción formativa: {e}")
            return False
    
    def update_accion_formativa_con_validaciones_fundae(self, accion_id: str, data: Dict[str, Any]) -> bool:
        """
        Actualiza acción formativa con validaciones FUNDAE.
        """
        try:
            # Validar que podemos editar esta acción
            accion_actual = self.supabase.table("acciones_formativas").select("*").eq("id", accion_id).execute()
            if not accion_actual.data:
                st.error("Acción formativa no encontrada")
                return False
            
            accion_data = accion_actual.data[0]
            
            # Verificar permisos según rol
            if self.rol == "gestor" and accion_data.get("empresa_id") != self.empresa_id:
                st.error("No tienes permisos para editar esta acción formativa")
                return False
            
            # NORMALIZACIÓN DE MODALIDAD AL PRINCIPIO
            if "modalidad" in data:
                if data["modalidad"] == "Online":
                    data["modalidad"] = "TELEFORMACION"
                elif data["modalidad"] == "Presencial":
                    data["modalidad"] = "PRESENCIAL"
                elif data["modalidad"] == "Mixta":
                    data["modalidad"] = "MIXTA"
            
            # *** CORRECCIÓN: Validar código sin fecha_inicio ***
            if "codigo_accion" in data:
                codigo_nuevo = data["codigo_accion"]
                empresa_id = accion_data["empresa_id"]
                
                # Para acciones formativas, usar año actual o año de la acción original
                ano_validacion = datetime.now().year
                if accion_data.get("ano_fundae"):
                    ano_validacion = accion_data["ano_fundae"]
                
                es_valido, error_codigo = self.validar_codigo_accion_fundae(
                    codigo_nuevo, empresa_id, ano_validacion, accion_id
                )
                
                if not es_valido:
                    st.error(f"Código FUNDAE inválido: {error_codigo}")
                    return False
            
            # VALIDAR MODALIDAD CON VALORES NORMALIZADOS
            if "modalidad" in data:
                modalidades_validas = ["PRESENCIAL", "TELEFORMACION", "MIXTA"]
                if data["modalidad"] not in modalidades_validas:
                    st.error(f"Modalidad debe ser una de: {', '.join(modalidades_validas)}")
                    return False
            
            # Validar horas si se están cambiando
            if "num_horas" in data:
                try:
                    horas = int(data["num_horas"])
                    if horas <= 0 or horas > 9999:
                        st.error("Las horas deben estar entre 1 y 9999")
                        return False
                except (ValueError, TypeError):
                    st.error("Las horas deben ser un número entero")
                    return False
            
            # Agregar timestamp de actualización
            data["updated_at"] = datetime.utcnow().isoformat()
            
            # Actualizar
            res = self.supabase.table("acciones_formativas").update(data).eq("id", accion_id).execute()
            
            if res.data:
                self.get_acciones_formativas.clear()
                return True
            else:
                st.error("Error al actualizar la acción formativa")
                return False
                
        except Exception as e:
            st.error(f"Error al actualizar acción formativa: {e}")
            return False
    
    def get_estadisticas_codigos_fundae(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas sobre códigos FUNDAE para detectar problemas.
        """
        try:
            # Obtener todas las acciones formativas
            df_acciones = self.get_acciones_formativas()
            
            if df_acciones.empty:
                return {
                    "total_acciones": 0,
                    "codigos_duplicados": 0,
                    "empresas_con_conflictos": 0,
                    "anos_con_problemas": []
                }
            
            estadisticas = {
                "total_acciones": len(df_acciones),
                "codigos_duplicados": 0,
                "empresas_con_conflictos": 0,
                "anos_con_problemas": []
            }
            
            # Detectar códigos duplicados por empresa y año
            duplicados_detectados = set()
            empresas_con_problemas = set()
            
            # Agrupar por empresa_id
            for empresa_id in df_acciones['empresa_id'].unique():
                if pd.isna(empresa_id):
                    continue
                    
                acciones_empresa = df_acciones[df_acciones['empresa_id'] == empresa_id]
                
                # Agrupar por año
                acciones_empresa['ano'] = pd.to_datetime(acciones_empresa['fecha_inicio'], errors='coerce').dt.year
                
                for ano in acciones_empresa['ano'].unique():
                    if pd.isna(ano):
                        continue
                        
                    acciones_ano = acciones_empresa[acciones_empresa['ano'] == ano]
                    
                    # Detectar duplicados en código_accion
                    duplicados_ano = acciones_ano.groupby('codigo_accion').size()
                    duplicados_ano = duplicados_ano[duplicados_ano > 1]
                    
                    if not duplicados_ano.empty:
                        estadisticas["codigos_duplicados"] += len(duplicados_ano)
                        empresas_con_problemas.add(empresa_id)
                        if int(ano) not in estadisticas["anos_con_problemas"]:
                            estadisticas["anos_con_problemas"].append(int(ano))
            
            estadisticas["empresas_con_conflictos"] = len(empresas_con_problemas)
            
            return estadisticas
            
        except Exception as e:
            st.error(f"Error al calcular estadísticas FUNDAE: {e}")
            return {}
    
    def get_reporte_conflictos_fundae(self) -> List[Dict[str, Any]]:
        """
        Genera reporte detallado de conflictos en códigos FUNDAE.
        """
        try:
            df_acciones = self.get_acciones_formativas()
            
            if df_acciones.empty:
                return []
            
            conflictos = []
            
            # Obtener información de empresas para nombres legibles
            empresas_info = {}
            if not df_acciones.empty:
                empresas_ids = df_acciones['empresa_id'].dropna().unique()
                for empresa_id in empresas_ids:
                    empresa_res = self.supabase.table("empresas").select("id, nombre").eq("id", empresa_id).execute()
                    if empresa_res.data:
                        empresas_info[empresa_id] = empresa_res.data[0]["nombre"]
            
            # Agrupar por empresa
            for empresa_id in df_acciones['empresa_id'].unique():
                if pd.isna(empresa_id):
                    continue
                    
                empresa_nombre = empresas_info.get(empresa_id, f"Empresa {empresa_id}")
                acciones_empresa = df_acciones[df_acciones['empresa_id'] == empresa_id]
                
                # Añadir columna de año
                acciones_empresa = acciones_empresa.copy()
                acciones_empresa['ano'] = pd.to_datetime(acciones_empresa['fecha_inicio'], errors='coerce').dt.year
                
                # Agrupar por año
                for ano in acciones_empresa['ano'].unique():
                    if pd.isna(ano):
                        continue
                        
                    acciones_ano = acciones_empresa[acciones_empresa['ano'] == ano]
                    
                    # Detectar duplicados
                    for codigo in acciones_ano['codigo_accion'].unique():
                        acciones_codigo = acciones_ano[acciones_ano['codigo_accion'] == codigo]
                        
                        if len(acciones_codigo) > 1:
                            conflictos.append({
                                "tipo": "codigo_duplicado",
                                "empresa_id": empresa_id,
                                "empresa_nombre": empresa_nombre,
                                "ano": int(ano),
                                "codigo_accion": codigo,
                                "cantidad_duplicados": len(acciones_codigo),
                                "acciones_afectadas": [
                                    {
                                        "id": row["id"],
                                        "nombre": row["nombre"],
                                        "fecha_inicio": row["fecha_inicio"]
                                    }
                                    for _, row in acciones_codigo.iterrows()
                                ]
                            })
            
            return conflictos
            
        except Exception as e:
            st.error(f"Error al generar reporte de conflictos: {e}")
            return []
    
    def resolver_conflicto_codigo_fundae(self, conflicto: Dict[str, Any], accion_id: str, nuevo_codigo: str) -> bool:
        """
        Resuelve un conflicto de código FUNDAE asignando un nuevo código a una acción específica.
        """
        try:
            # Validar que el nuevo código no genere otro conflicto
            empresa_id = conflicto["empresa_id"]
            ano = conflicto["ano"]
            
            es_valido, error = self.validar_codigo_accion_fundae(
                nuevo_codigo, empresa_id, ano, accion_id
            )
            
            if not es_valido:
                st.error(f"El nuevo código también genera conflicto: {error}")
                return False
            
            # Actualizar la acción con el nuevo código
            datos_actualizacion = {
                "codigo_accion": nuevo_codigo,
                "updated_at": datetime.utcnow().isoformat(),
                "conflicto_resuelto": True
            }
            
            res = self.supabase.table("acciones_formativas").update(datos_actualizacion).eq("id", accion_id).execute()
            
            if res.data:
                # Limpiar cache
                self.get_acciones_formativas.clear()
                return True
            else:
                st.error("Error al actualizar la acción formativa")
                return False
                
        except Exception as e:
            st.error(f"Error al resolver conflicto: {e}")
            return False
    
    def auto_resolver_conflictos_fundae(self, empresa_id: str = None) -> Dict[str, int]:
        """
        Intenta resolver automáticamente conflictos de códigos FUNDAE generando códigos alternativos.
        """
        try:
            conflictos = self.get_reporte_conflictos_fundae()
            
            # Filtrar por empresa si se especifica
            if empresa_id:
                conflictos = [c for c in conflictos if c["empresa_id"] == empresa_id]
            
            resueltos = 0
            errores = 0
            
            for conflicto in conflictos:
                if conflicto["tipo"] != "codigo_duplicado":
                    continue
                
                # Para cada acción duplicada excepto la primera, generar nuevo código
                acciones_afectadas = conflicto["acciones_afectadas"]
                
                for i, accion in enumerate(acciones_afectadas[1:], 1):  # Empezar desde la segunda
                    accion_id = accion["id"]
                    empresa_id_conflicto = conflicto["empresa_id"]
                    ano_conflicto = conflicto["ano"]
                    
                    # Generar código alternativo
                    nuevo_codigo, error = self.generar_codigo_accion_sugerido(empresa_id_conflicto, ano_conflicto)
                    
                    if error:
                        errores += 1
                        continue
                    
                    # Intentar resolver
                    if self.resolver_conflicto_codigo_fundae(conflicto, accion_id, nuevo_codigo):
                        resueltos += 1
                    else:
                        errores += 1
            
            return {
                "conflictos_procesados": len(conflictos),
                "resueltos": resueltos,
                "errores": errores
            }
            
        except Exception as e:
            st.error(f"Error en resolución automática: {e}")
            return {"conflictos_procesados": 0, "resueltos": 0, "errores": 1}
    
    # =========================
    # MÉTODOS PARA MIGRACIÓN DE DATOS LEGACY
    # =========================
    
    def migrar_codigos_fundae_legacy(self) -> Dict[str, int]:
        """
        Migra acciones formativas existentes que no tienen códigos FUNDAE válidos.
        """
        try:
            # Obtener acciones sin código o con códigos problemáticos
            df_acciones = self.get_acciones_formativas()
            
            if df_acciones.empty:
                return {"procesadas": 0, "migradas": 0, "errores": 0}
            
            procesadas = 0
            migradas = 0
            errores = 0
            
            for _, accion in df_acciones.iterrows():
                procesadas += 1
                
                codigo_actual = accion.get("codigo_accion", "")
                empresa_id = accion.get("empresa_id")
                fecha_inicio = accion.get("fecha_inicio")
                
                # Determinar si necesita migración
                necesita_migracion = False
                
                # Sin código
                if not codigo_actual:
                    necesita_migracion = True
                
                # Código muy corto o muy largo
                elif len(codigo_actual) < 3 or len(codigo_actual) > 20:
                    necesita_migracion = True
                
                # Contiene caracteres no válidos para FUNDAE
                elif not re.match(r'^[A-Z0-9\-_]+$', codigo_actual.upper()):
                    necesita_migracion = True
                
                if necesita_migracion and empresa_id and fecha_inicio:
                    try:
                        ano = datetime.fromisoformat(str(fecha_inicio).replace('Z', '+00:00')).year
                        
                        # Generar nuevo código
                        nuevo_codigo, error = self.generar_codigo_accion_sugerido(empresa_id, ano)
                        
                        if error:
                            errores += 1
                            continue
                        
                        # Actualizar acción
                        datos_migracion = {
                            "codigo_accion": nuevo_codigo,
                            "updated_at": datetime.utcnow().isoformat(),
                            "migrado_fundae": True,
                            "codigo_anterior": codigo_actual
                        }
                        
                        res = self.supabase.table("acciones_formativas").update(datos_migracion).eq("id", accion["id"]).execute()
                        
                        if res.data:
                            migradas += 1
                        else:
                            errores += 1
                            
                    except Exception as e:
                        errores += 1
                        continue
            
            # Limpiar cache al final
            if migradas > 0:
                self.get_acciones_formativas.clear()
            
            return {
                "procesadas": procesadas,
                "migradas": migradas,
                "errores": errores
            }
            
        except Exception as e:
            st.error(f"Error en migración de códigos legacy: {e}")
            return {"procesadas": 0, "migradas": 0, "errores": 1}
        
    # =========================
    # MÉTRICAS Y ESTADÍSTICAS GLOBALES
    # =========================
    @st.cache_data(ttl=300)
    def get_metricas_empresa(_self, empresa_id: str) -> Dict[str, int]:
        """Obtiene métricas específicas de una empresa."""
        try:
            if _self.rol != "admin" and empresa_id != _self.empresa_id:
                return {}
            
            try:
                res = _self.supabase.rpc('get_gestor_metrics', {'empresa_uuid': empresa_id}).execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass
            
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
            st.error(f"Error al cargar métricas: {e}")
            return {}

    @st.cache_data(ttl=300)
    def get_metricas_admin(_self) -> Dict[str, int]:
        """Obtiene métricas globales para admin."""
        try:
            try:
                res = _self.supabase.rpc('get_admin_metrics').execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass
            
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
            st.error(f"Error al cargar métricas admin: {e}")
            return {}
    # =========================
    # MÉTODOS DE UTILIDAD ADICIONALES
    # =========================
    
    def get_dashboard_fundae(self) -> Dict[str, Any]:
        """
        Genera dashboard específico para estado FUNDAE del sistema.
        """
        try:
            estadisticas = self.get_estadisticas_codigos_fundae()
            conflictos = self.get_reporte_conflictos_fundae()
            
            # Análisis de estado
            estado_general = "EXCELENTE"
            alertas = []
            
            if estadisticas.get("codigos_duplicados", 0) > 0:
                estado_general = "CRITICO"
                alertas.append(f"{estadisticas['codigos_duplicados']} códigos duplicados detectados")
            
            if estadisticas.get("empresas_con_conflictos", 0) > 0:
                if estado_general != "CRITICO":
                    estado_general = "ADVERTENCIA"
                alertas.append(f"{estadisticas['empresas_con_conflictos']} empresas con conflictos")
            
            return {
                "estado_general": estado_general,
                "estadisticas": estadisticas,
                "conflictos": conflictos[:10],  # Primeros 10 conflictos
                "alertas": alertas,
                "total_conflictos": len(conflictos),
                "acciones_recomendadas": [
                    "Resolver códigos duplicados automáticamente" if estadisticas.get("codigos_duplicados", 0) > 0 else None,
                    "Migrar datos legacy sin códigos válidos" if estadisticas.get("total_acciones", 0) > 0 else None,
                    "Configurar alertas automáticas para prevenir duplicados" if estado_general != "EXCELENTE" else None
                ]
            }
            
        except Exception as e:
            return {
                "estado_general": "ERROR",
                "error": str(e),
                "estadisticas": {},
                "conflictos": [],
                "alertas": ["Error al generar dashboard FUNDAE"],
                "acciones_recomendadas": ["Revisar configuración del sistema"]
            }
    # =========================
    # BÚSQUEDAS OPTIMIZADAS
    # =========================
    def search_participantes(_self, search_term: str) -> pd.DataFrame:
        """Búsqueda optimizada de participantes."""
        if not search_term:
            return _self.get_participantes_completos()
        
        try:
            try:
                res = _self.supabase.rpc('search_usuarios', {'search_term': search_term}).execute()
                return pd.DataFrame(res.data or [])
            except Exception:
                pass
            
            df = _self.get_participantes_completos()
            if df.empty:
                return df
            
            search_lower = search_term.lower()
            mask = (
                df["nombre"].str.lower().str.contains(search_lower, na=False) |
                df["apellidos"].str.lower().str.contains(search_lower, na=False) |
                df["email"].str.lower().str.contains(search_lower, na=False) |
                df["nif"].str.lower().str.contains(search_lower, na=False)
            )
            return df[mask]
        except Exception as e:
            return _self._handle_query_error("buscar participantes", e)

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
