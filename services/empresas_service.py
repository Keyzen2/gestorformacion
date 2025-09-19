import streamlit as st
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from utils import validar_dni_cif

class EmpresasService:
    """
    Servicio para gestión de empresas con soporte para jerarquía multi-tenant.
    
    Tipos de empresa:
    - CLIENTE_SAAS: Cliente directo del SaaS (nivel 1)
    - GESTORA: Cliente SaaS que gestiona otros (nivel 1)  
    - CLIENTE_GESTOR: Cliente de una empresa gestora (nivel 2)
    """
    
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
        self.rol = session_state.get("role")
        self.usuario_id = session_state.get("user_id")
        self.empresa_id = session_state.user.get("empresa_id")
        
    # =========================
    # MÉTODOS DE CONSULTA JERÁRQUICA
    # =========================
    
    @st.cache_data(ttl=300)
    def get_empresas_con_jerarquia(_self) -> pd.DataFrame:
        """Obtiene empresas con información jerárquica completa."""
        try:
            if _self.rol == "admin":
                # Admin ve todas las empresas con jerarquía completa
                query = _self.supabase.table("empresas").select("""
                    id, nombre, cif, direccion, telefono, email, ciudad, provincia,
                    codigo_postal, tipo_empresa, nivel_jerarquico, empresa_matriz_id,
                    fecha_creacion, formacion_activo, formacion_inicio, formacion_fin,
                    iso_activo, iso_inicio, iso_fin,
                    rgpd_activo, rgpd_inicio, rgpd_fin,
                    docu_avanzada_activo, docu_avanzada_inicio, docu_avanzada_fin,
                    empresa_matriz:empresas!empresa_matriz_id(nombre)
                """)
                
            elif _self.rol == "gestor" and _self.empresa_id:
                # Gestor ve su empresa y sus clientes
                query = _self.supabase.table("empresas").select("""
                    id, nombre, cif, direccion, telefono, email, ciudad, provincia,
                    codigo_postal, tipo_empresa, nivel_jerarquico, empresa_matriz_id,
                    fecha_creacion, formacion_activo, formacion_inicio, formacion_fin,
                    iso_activo, iso_inicio, iso_fin,
                    rgpd_activo, rgpd_inicio, rgpd_fin,
                    docu_avanzada_activo, docu_avanzada_inicio, docu_avanzada_fin,
                    empresa_matriz:empresas!empresa_matriz_id(nombre)
                """).or_(f"id.eq.{_self.empresa_id},empresa_matriz_id.eq.{_self.empresa_id}"
                )
            else:
                return pd.DataFrame()
            
            res = query.order("nivel_jerarquico").order("nombre").execute()
            df = pd.DataFrame(res.data or [])
            
            if not df.empty:
                # Agregar indicadores visuales para la jerarquía
                df["nombre_display"] = df.apply(lambda row: 
                    f"{'  └── ' if row.get('nivel_jerarquico') == 2 else ''}{row['nombre']}", 
                    axis=1
                )
                
                # Agregar contexto tipo empresa
                df["tipo_display"] = df["tipo_empresa"].map({
                    "CLIENTE_SAAS": "Cliente SaaS",
                    "GESTORA": "Gestora",
                    "CLIENTE_GESTOR": "Cliente de Gestora"
                })
                
                # Procesar empresa matriz
                if "empresa_matriz" in df.columns:
                    df["matriz_nombre"] = df["empresa_matriz"].apply(
                        lambda x: x.get("nombre") if isinstance(x, dict) else ""
                    )
                else:
                    df["matriz_nombre"] = ""
            
            return df
        except Exception as e:
            st.error(f"Error al cargar empresas con jerarquía: {e}")
            return pd.DataFrame()
    
    def get_empresas_gestoras_disponibles(self) -> Dict[str, str]:
        """Obtiene empresas que pueden ser gestoras (tipo GESTORA)."""
        try:
            if self.rol != "admin":
                return {}
                
            res = self.supabase.table("empresas").select("id, nombre").eq(
                "tipo_empresa", "GESTORA"
            ).order("nombre").execute()
            
            return {emp["nombre"]: emp["id"] for emp in (res.data or [])}
        except Exception as e:
            st.error(f"Error al cargar empresas gestoras: {e}")
            return {}
    
    def get_empresas_clientes_gestor(self, gestor_id: str = None) -> pd.DataFrame:
        """Obtiene empresas clientes de un gestor específico."""
        try:
            if not gestor_id:
                gestor_id = self.empresa_id
                
            if not gestor_id:
                return pd.DataFrame()
            
            res = self.supabase.table("empresas").select("*").eq(
                "empresa_matriz_id", gestor_id
            ).order("nombre").execute()
            
            return pd.DataFrame(res.data or [])
        except Exception as e:
            st.error(f"Error al cargar empresas clientes: {e}")
            return pd.DataFrame()
    
    def get_empresas_para_asignacion(self) -> Dict[str, str]:
        """Obtiene empresas que pueden asignarse a grupos/participantes según rol."""
        try:
            if self.rol == "admin":
                # Admin puede asignar cualquier empresa
                res = self.supabase.table("empresas").select("id, nombre, tipo_empresa").order("nombre").execute()
                
            elif self.rol == "gestor" and self.empresa_id:
                # Gestor puede asignar su empresa y sus clientes
                res = self.supabase.table("empresas").select("id, nombre, tipo_empresa").or_(
                    f"id.eq.{self.empresa_id},empresa_matriz_id.eq.{self.empresa_id}"
                ).order("nombre").execute()
            else:
                return {}
            
            if res.data:
                # Agregar indicador de tipo para claridad
                result = {}
                for emp in res.data:
                    tipo_display = {
                        "CLIENTE_SAAS": "",
                        "GESTORA": " (Gestora)",
                        "CLIENTE_GESTOR": " (Cliente)"
                    }.get(emp.get("tipo_empresa", ""), "")
                    
                    result[f"{emp['nombre']}{tipo_display}"] = emp["id"]
                return result
            return {}
            
        except Exception as e:
            st.error(f"Error al cargar empresas para asignación: {e}")
            return {}
    
    # =========================
    # MÉTODOS DE CREACIÓN CON JERARQUÍA
    # =========================
    
    def crear_empresa_con_jerarquia(self, datos_empresa: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Crea empresa respetando jerarquía según el rol del usuario."""
        try:
            # Preparar datos según rol
            if self.rol == "admin":
                # Admin puede especificar tipo y matriz
                tipo = datos_empresa.get("tipo_empresa", "CLIENTE_SAAS")
                
                # Validar coherencia según tipo
                if tipo == "CLIENTE_GESTOR":
                    if not datos_empresa.get("empresa_matriz_id"):
                        st.error("Empresa matriz requerida para CLIENTE_GESTOR")
                        return False, None
                    # El trigger se encarga de establecer nivel_jerarquico = 2
                        
                elif tipo == "GESTORA":
                    # Gestora debe ser nivel 1 sin matriz
                    datos_empresa["nivel_jerarquico"] = 1
                    datos_empresa["empresa_matriz_id"] = None
                    
                elif tipo == "CLIENTE_SAAS":
                    # Cliente SaaS es nivel 1 sin matriz
                    datos_empresa["nivel_jerarquico"] = 1
                    datos_empresa["empresa_matriz_id"] = None
                    
            elif self.rol == "gestor" and self.empresa_id:
                # Gestor solo puede crear CLIENTE_GESTOR bajo su empresa
                datos_empresa.update({
                    "empresa_matriz_id": self.empresa_id,
                    "tipo_empresa": "CLIENTE_GESTOR"
                    # nivel_jerarquico lo establece el trigger automáticamente
                })
            else:
                st.error("Sin permisos para crear empresas")
                return False, None
            
            # Validaciones básicas
            if not datos_empresa.get("nombre") or not datos_empresa.get("cif"):
                st.error("Nombre y CIF son obligatorios")
                return False, None
            
            if not validar_dni_cif(datos_empresa["cif"]):
                st.error("CIF inválido")
                return False, None
            
            # Verificar CIF único
            if not self._validar_cif_unico_jerarquico(datos_empresa["cif"]):
                st.error("Ya existe una empresa con ese CIF")
                return False, None
            
            # Agregar metadatos
            datos_empresa.update({
                "creado_por_usuario_id": self.usuario_id,
                "fecha_creacion": datetime.utcnow().isoformat()
            })
            
            # Crear empresa (triggers automáticos manejan jerarquía)
            result = self.supabase.table("empresas").insert(datos_empresa).execute()
            
            if result.data:
                # Limpiar caches
                self.get_empresas_con_jerarquia.clear()
                return True, result.data[0]["id"]
            else:
                st.error("Error al crear la empresa")
                return False, None
                
        except Exception as e:
            st.error(f"Error al crear empresa: {e}")
            return False, None
    
    def crear_empresa_cliente(self, datos_empresa: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Crea una empresa cliente para el gestor actual."""
        if self.rol != "gestor" or not self.empresa_id:
            st.error("Solo gestores pueden crear empresas clientes")
            return False, None
        
        datos_empresa.update({
            "empresa_matriz_id": self.empresa_id,
            "tipo_empresa": "CLIENTE_GESTOR",
            "nivel_jerarquico": 2,
            "creado_por_usuario_id": self.usuario_id,
            "fecha_creacion": datetime.utcnow().isoformat()
        })
        
        return self.crear_empresa_con_jerarquia(datos_empresa)
    
    # =========================
    # MÉTODOS DE ACTUALIZACIÓN
    # =========================
    
    def update_empresa_con_jerarquia(self, empresa_id: str, datos_editados: Dict[str, Any]) -> bool:
        """Actualiza empresa respetando permisos jerárquicos."""
        try:
            # Verificar permisos
            if not self._puede_editar_empresa_jerarquica(empresa_id):
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
            if self.rol == "admin" and "tipo_empresa" in datos_editados:
                datos_filtrados["tipo_empresa"] = datos_editados["tipo_empresa"]
                
                # Si cambia a GESTORA, limpiar matriz
                if datos_editados["tipo_empresa"] == "GESTORA":
                    datos_filtrados["empresa_matriz_id"] = None
            
            # Validar CIF si se está cambiando
            if "cif" in datos_filtrados:
                if not self._validar_cif_unico_jerarquico(datos_filtrados["cif"], empresa_id):
                    st.error("Ya existe otra empresa con ese CIF")
                    return False
            
            res = self.supabase.table("empresas").update(datos_filtrados).eq("id", empresa_id).execute()
            
            if res.data:
                # Limpiar caches
                self.get_empresas_con_jerarquia.clear()
                return True
            return False
            
        except Exception as e:
            st.error(f"Error al actualizar empresa: {e}")
            return False
    
    # =========================
    # MÉTODOS DE ELIMINACIÓN
    # =========================
    
    def delete_empresa_con_jerarquia(self, empresa_id: str) -> bool:
        """Elimina empresa respetando jerarquía."""
        try:
            # Verificar permisos
            if not self._puede_editar_empresa_jerarquica(empresa_id):
                st.error("No tienes permisos para eliminar esta empresa")
                return False
            
            # Verificar dependencias - empresas hijas
            hijas = self.supabase.table("empresas").select("id").eq("empresa_matriz_id", empresa_id).execute()
            if hijas.data:
                st.error("No se puede eliminar. La empresa tiene empresas clientes asociadas.")
                return False
            
            # Verificar dependencias - participantes
            participantes = self.supabase.table("participantes").select("id").eq("empresa_id", empresa_id).execute()
            if participantes.data:
                st.error("No se puede eliminar. La empresa tiene participantes asociados.")
                return False
            
            # Verificar dependencias - grupos
            grupos = self.supabase.table("grupos").select("id").eq("empresa_id", empresa_id).execute()
            if grupos.data:
                st.error("No se puede eliminar. La empresa tiene grupos asociados.")
                return False
            
            # Eliminar empresa (CASCADE eliminará relaciones automáticamente)
            res = self.supabase.table("empresas").delete().eq("id", empresa_id).execute()
            
            if res.data:
                # Limpiar caches
                self.get_empresas_con_jerarquia.clear()
                return True
            return False
            
        except Exception as e:
            st.error(f"Error al eliminar empresa: {e}")
            return False
    
    # =========================
    # MÉTODOS DE CONSULTA ESPECÍFICA
    # =========================
    
    def get_empresa_by_id(self, empresa_id: str) -> Optional[Dict]:
        """Obtiene una empresa por ID."""
        try:
            response = self.supabase.table("empresas").select("*").eq("id", empresa_id).execute()
            
            if response.data:
                return response.data[0]
            return None
            
        except Exception as e:
            st.error(f"Error obteniendo empresa por ID: {e}")
            return None
    
    def get_empresas_dict(self) -> Dict[str, str]:
        """Devuelve dict {nombre: id} de todas las empresas visibles."""
        try:
            df = self.get_empresas_con_jerarquia()
            if df.empty:
                return {}
            return {row["nombre"]: row["id"] for _, row in df.iterrows() if row.get("id") and row.get("nombre")}
        except Exception as e:
            st.error(f"Error al obtener diccionario de empresas: {e}")
            return {}
    
    def validar_cif_unico(self, cif: str, empresa_id: Optional[str] = None) -> bool:
        """Valida que el CIF sea único en el ámbito correspondiente."""
        return self._validar_cif_unico_jerarquico(cif, empresa_id)
    
    # =========================
    # MÉTODOS DE ESTADÍSTICAS
    # =========================
    
    def get_estadisticas_empresas(self) -> Dict[str, Any]:
        """Obtiene estadísticas de empresas según el rol."""
        try:
            if self.rol == "admin":
                # Admin ve estadísticas globales
                try:
                    response = self.supabase.rpc('get_estadisticas_jerarquia').execute()
                    if response.data:
                        # La función ahora devuelve JSON, no una tabla
                        return response.data if isinstance(response.data, dict) else {}
                except Exception as sql_error:
                    # Fallback si la función SQL no funciona
                    st.warning(f"Función SQL no disponible: {sql_error}")
                
                # Estadísticas básicas como fallback
                try:
                    empresas = self.supabase.table("empresas").select("tipo_empresa", count="exact").execute()
                    return {
                        "total_empresas": empresas.count or 0,
                        "nuevas_mes": 0,
                        "con_formacion": 0,
                        "porcentaje_activas": 0
                    }
                except Exception as basic_error:
                    st.error(f"Error cargando estadísticas básicas: {basic_error}")
                    return {}
            
            elif self.rol == "gestor":
                # Gestor ve estadísticas de sus clientes
                clientes = self.get_empresas_clientes_gestor()
                empresa_info = self.get_empresa_by_id(self.empresa_id)
                
                return {
                    "empresa_gestora": empresa_info.get("nombre", "") if empresa_info else "",
                    "total_clientes": len(clientes),
                    "tipo_empresa": "GESTORA"
                }
            
            return {}
            
        except Exception as e:
            st.error(f"Error obteniendo estadísticas: {e}")
            return {}
    
    def get_arbol_empresas(self, empresa_raiz_id: str = None) -> pd.DataFrame:
        """Obtiene árbol jerárquico usando función SQL o simulación."""
        try:
            try:
                # Intentar usar función SQL si existe
                if empresa_raiz_id:
                    res = self.supabase.rpc('get_arbol_empresas', {'empresa_raiz_id': empresa_raiz_id}).execute()
                else:
                    res = self.supabase.rpc('get_arbol_empresas').execute()
                
                return pd.DataFrame(res.data or [])
            except:
                # Fallback: simular árbol con datos existentes
                df = self.get_empresas_con_jerarquia()
                if not df.empty:
                    # Agregar información de ruta para simular árbol
                    df["ruta"] = df.apply(lambda row: 
                        f"{row['matriz_nombre']} > {row['nombre']}" if row['matriz_nombre'] else row['nombre'], 
                        axis=1
                    )
                return df
        except Exception as e:
            st.error(f"Error al cargar árbol de empresas: {e}")
            return pd.DataFrame()
    
    # =========================
    # MÉTODOS AUXILIARES PRIVADOS
    # =========================
    
    def _puede_editar_empresa_jerarquica(self, empresa_id: str) -> bool:
        """Verifica permisos para editar empresa según jerarquía."""
        if self.rol == "admin":
            return True
        
        elif self.rol == "gestor" and self.empresa_id:
            # Gestor puede editar su empresa y sus clientes
            try:
                empresa = self.get_empresa_by_id(empresa_id)
                if not empresa:
                    return False
                
                # Puede editar su propia empresa
                if empresa["id"] == self.empresa_id:
                    return True
                
                # Puede editar sus empresas clientes
                if empresa.get("empresa_matriz_id") == self.empresa_id:
                    return True
                
                return False
            except:
                return False
        
        return False
    
    def _validar_cif_unico_jerarquico(self, cif: str, empresa_id: str = None) -> bool:
        """Valida CIF único en el ámbito jerárquico apropiado."""
        try:
            query = self.supabase.table("empresas").select("id").eq("cif", cif)
            
            if empresa_id:
                query = query.neq("id", empresa_id)
            
            # Para gestores, verificar solo en su ámbito
            if self.rol == "gestor" and self.empresa_id:
                query = query.or_(f"id.eq.{self.empresa_id},empresa_matriz_id.eq.{self.empresa_id}")
            
            res = query.execute()
            return len(res.data or []) == 0
            
        except Exception as e:
            st.error(f"Error validando CIF: {e}")
            return False
    
    def get_contexto_jerarquico(self, empresa_id: str) -> str:
        """Obtiene información contextual de la posición jerárquica de una empresa."""
        try:
            empresa = self.get_empresa_by_id(empresa_id)
            if not empresa:
                return "Empresa no encontrada"
            
            if empresa["tipo_empresa"] == "CLIENTE_SAAS":
                return "Cliente directo del SaaS"
            elif empresa["tipo_empresa"] == "GESTORA":
                clientes = self.get_empresas_clientes_gestor(empresa_id)
                return f"Gestora con {len(clientes)} clientes"
            elif empresa["tipo_empresa"] == "CLIENTE_GESTOR":
                if empresa.get("empresa_matriz_id"):
                    matriz = self.get_empresa_by_id(empresa["empresa_matriz_id"])
                    return f"Cliente de {matriz['nombre'] if matriz else 'Gestora desconocida'}"
            
            return "Sin contexto jerárquico"
            
        except Exception as e:
            st.error(f"Error obteniendo contexto jerárquico: {e}")
            return "Error obteniendo contexto"
    
    # =========================
    # MÉTODOS DE COMPATIBILIDAD
    # =========================
    
    def can_modify_data(self) -> bool:
        """Verifica si el usuario puede modificar datos."""
        return self.rol in ["admin", "gestor"]
    
    def can_access_empresa_data(self, empresa_id: str) -> bool:
        """Verifica si el usuario puede acceder a datos de una empresa."""
        if self.rol == "admin":
            return True
        if self.rol == "gestor":
            return self._puede_editar_empresa_jerarquica(empresa_id)
        return False


# =========================
# FUNCIÓN FACTORY
# =========================

def get_empresas_service(supabase, session_state) -> EmpresasService:
    """Factory function para obtener instancia del servicio de empresas."""
    return EmpresasService(supabase, session_state)
