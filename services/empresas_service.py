from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from datetime import datetime

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
        self.empresa_id = session_state.get("empresa_id")
        
    # =========================
    # MÉTODOS DE CONSULTA JERÁRQUICA
    # =========================
    
    def get_empresas_por_rol(self) -> pd.DataFrame:
        """
        Obtiene empresas según el rol del usuario.
        
        Admin: Ve todas las empresas con información jerárquica
        Gestor: Ve solo sus empresas clientes
        
        Returns:
            pd.DataFrame: Empresas filtradas por rol
        """
        try:
            if self.rol == "admin":
                return self._get_todas_empresas_con_jerarquia()
            elif self.rol == "gestor":
                return self._get_empresas_clientes_gestor()
            else:
                return pd.DataFrame()  # Otros roles no ven empresas
                
        except Exception as e:
            print(f"Error obteniendo empresas por rol: {e}")
            return pd.DataFrame()
    
    def _get_todas_empresas_con_jerarquia(self) -> pd.DataFrame:
        """Obtiene todas las empresas con información jerárquica (solo admin)."""
        try:
            response = self.supabase.table("v_empresas_jerarquia").select("*").execute()
            
            if response.data:
                df = pd.DataFrame(response.data)
                
                # Ordenar por jerarquía: primero empresas raíz, luego hijas
                df = df.sort_values(['nivel_jerarquico', 'nombre'])
                
                return df
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Error obteniendo empresas con jerarquía: {e}")
            return pd.DataFrame()
    
    def _get_empresas_clientes_gestor(self) -> pd.DataFrame:
        """Obtiene solo las empresas clientes del gestor."""
        if not self.empresa_id:
            return pd.DataFrame()
        
        try:
            response = self.supabase.table("empresas").select("""
                id, nombre, cif, direccion, telefono, email, 
                tipo_empresa, nivel_jerarquico, fecha_creacion,
                empresa_matriz_id
            """).eq("empresa_matriz_id", self.empresa_id).execute()
            
            if response.data:
                return pd.DataFrame(response.data)
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Error obteniendo empresas clientes: {e}")
            return pd.DataFrame()
    
    def get_empresas_gestoras(self) -> Dict[str, str]:
        """Obtiene empresas que pueden ser gestoras (tipo GESTORA)."""
        try:
            response = self.supabase.table("empresas").select(
                "id, nombre"
            ).eq("tipo_empresa", "GESTORA").execute()
            
            if response.data:
                return {empresa["nombre"]: empresa["id"] for empresa in response.data}
            return {}
            
        except Exception as e:
            print(f"Error obteniendo empresas gestoras: {e}")
            return {}
    
    def get_arbol_empresa(self, empresa_raiz_id: Optional[str] = None) -> List[Dict]:
        """
        Obtiene el árbol jerárquico de empresas.
        
        Args:
            empresa_raiz_id: ID de empresa raíz. Si es None, devuelve todo el árbol.
            
        Returns:
            List[Dict]: Árbol de empresas con nivel y ruta
        """
        try:
            # Usar función de PostgreSQL para obtener árbol
            if empresa_raiz_id:
                response = self.supabase.rpc('get_arbol_empresas', {
                    'empresa_raiz_id': empresa_raiz_id
                }).execute()
            else:
                response = self.supabase.rpc('get_arbol_empresas').execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Error obteniendo árbol de empresas: {e}")
            return []
    
    # =========================
    # MÉTODOS DE CREACIÓN
    # =========================
    
    def crear_empresa_con_jerarquia(self, datos_empresa: Dict) -> Tuple[bool, Optional[str]]:
        """
        Crea una empresa respetando la jerarquía según el rol del usuario.
        
        Args:
            datos_empresa: Datos de la empresa a crear
            
        Returns:
            Tuple[bool, Optional[str]]: (éxito, id_empresa_creada)
        """
        try:
            # Preparar datos según rol
            if self.rol == "admin":
                # Admin puede crear cualquier tipo
                tipo_empresa = datos_empresa.get("tipo_empresa", "CLIENTE_SAAS")
                
                if tipo_empresa == "CLIENTE_GESTOR":
                    # Requiere empresa_matriz_id
                    if not datos_empresa.get("empresa_matriz_id"):
                        return False, "Empresa matriz requerida para CLIENTE_GESTOR"
                        
                elif tipo_empresa == "GESTORA":
                    # Asegurar que sea nivel 1
                    datos_empresa["nivel_jerarquico"] = 1
                    
            elif self.rol == "gestor":
                # Gestor solo puede crear CLIENTE_GESTOR bajo su empresa
                datos_empresa.update({
                    "empresa_matriz_id": self.empresa_id,
                    "tipo_empresa": "CLIENTE_GESTOR",
                    "nivel_jerarquico": 2
                })
            else:
                return False, "Sin permisos para crear empresas"
            
            # Agregar metadatos
            datos_empresa.update({
                "creado_por_usuario_id": self.usuario_id,
                "fecha_creacion": datetime.now().isoformat()
            })
            
            # Crear empresa
            response = self.supabase.table("empresas").insert(datos_empresa).execute()
            
            if response.data:
                return True, response.data[0]["id"]
            return False, None
            
        except Exception as e:
            print(f"Error creando empresa: {e}")
            return False, None
    
    def crear_empresa_cliente(self, datos_empresa: Dict, empresa_gestora_id: str) -> Tuple[bool, Optional[str]]:
        """
        Crea una empresa cliente de una gestora específica.
        
        Args:
            datos_empresa: Datos de la empresa cliente
            empresa_gestora_id: ID de la empresa gestora
            
        Returns:
            Tuple[bool, Optional[str]]: (éxito, id_empresa_creada)
        """
        datos_empresa.update({
            "empresa_matriz_id": empresa_gestora_id,
            "tipo_empresa": "CLIENTE_GESTOR",
            "nivel_jerarquico": 2,
            "creado_por_usuario_id": self.usuario_id,
            "fecha_creacion": datetime.now().isoformat()
        })
        
        return self.crear_empresa_con_jerarquia(datos_empresa)
    
    # =========================
    # MÉTODOS DE ACTUALIZACIÓN
    # =========================
    
    def update_empresa(self, empresa_id: str, datos_actualizados: Dict) -> bool:
        """
        Actualiza una empresa respetando permisos jerárquicos.
        
        Args:
            empresa_id: ID de la empresa a actualizar
            datos_actualizados: Datos a actualizar
            
        Returns:
            bool: Éxito de la operación
        """
        try:
            # Verificar permisos
            if not self._puede_editar_empresa(empresa_id):
                return False
            
            # Filtrar campos que no se deben actualizar directamente
            campos_protegidos = ["id", "empresa_matriz_id", "tipo_empresa", 
                               "nivel_jerarquico", "creado_por_usuario_id", "fecha_creacion"]
            
            datos_filtrados = {
                k: v for k, v in datos_actualizados.items() 
                if k not in campos_protegidos
            }
            
            response = self.supabase.table("empresas").update(
                datos_filtrados
            ).eq("id", empresa_id).execute()
            
            return bool(response.data)
            
        except Exception as e:
            print(f"Error actualizando empresa: {e}")
            return False
    
    def cambiar_tipo_empresa(self, empresa_id: str, nuevo_tipo: str) -> bool:
        """
        Cambia el tipo de una empresa (solo admin).
        
        Args:
            empresa_id: ID de la empresa
            nuevo_tipo: Nuevo tipo de empresa
            
        Returns:
            bool: Éxito de la operación
        """
        if self.rol != "admin":
            return False
        
        try:
            # Validar transiciones permitidas
            empresa_actual = self.get_empresa_by_id(empresa_id)
            if not empresa_actual:
                return False
            
            datos_actualizacion = {"tipo_empresa": nuevo_tipo}
            
            # Ajustar jerarquía según el nuevo tipo
            if nuevo_tipo == "GESTORA":
                datos_actualizacion.update({
                    "nivel_jerarquico": 1,
                    "empresa_matriz_id": None  # Gestora no puede tener matriz
                })
            elif nuevo_tipo == "CLIENTE_GESTOR":
                if not empresa_actual.get("empresa_matriz_id"):
                    return False  # Requiere matriz
                datos_actualizacion["nivel_jerarquico"] = 2
            
            response = self.supabase.table("empresas").update(
                datos_actualizacion
            ).eq("id", empresa_id).execute()
            
            return bool(response.data)
            
        except Exception as e:
            print(f"Error cambiando tipo de empresa: {e}")
            return False
    
    # =========================
    # MÉTODOS DE ELIMINACIÓN
    # =========================
    
    def delete_empresa(self, empresa_id: str) -> bool:
        """
        Elimina una empresa respetando la jerarquía.
        
        Args:
            empresa_id: ID de la empresa a eliminar
            
        Returns:
            bool: Éxito de la operación
        """
        try:
            # Verificar permisos
            if not self._puede_editar_empresa(empresa_id):
                return False
            
            # Verificar si tiene empresas hijas
            hijas = self._get_empresas_hijas(empresa_id)
            if not hijas.empty:
                # No se puede eliminar si tiene empresas hijas
                return False
            
            response = self.supabase.table("empresas").delete().eq("id", empresa_id).execute()
            
            return bool(response.data)
            
        except Exception as e:
            print(f"Error eliminando empresa: {e}")
            return False
    
    def _get_empresas_hijas(self, empresa_id: str) -> pd.DataFrame:
        """Obtiene empresas hijas de una empresa."""
        try:
            response = self.supabase.table("empresas").select("id, nombre").eq(
                "empresa_matriz_id", empresa_id
            ).execute()
            
            if response.data:
                return pd.DataFrame(response.data)
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Error obteniendo empresas hijas: {e}")
            return pd.DataFrame()
    
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
            print(f"Error obteniendo empresa por ID: {e}")
            return None
            
    def get_empresas_dict(self) -> dict:
        """Devuelve dict {nombre: id} de todas las empresas visibles."""
        df = self.get_empresas()
        if df.empty:
            return {}
        return {row["nombre"]: row["id"] for _, row in df.iterrows() if row.get("id") and row.get("nombre")}
        
    def get_empresas_para_grupos(self) -> Dict[str, str]:
        """
        Obtiene empresas que pueden asignarse a grupos según rol.
        
        Returns:
            Dict[str, str]: {nombre_empresa: id_empresa}
        """
        try:
            if self.rol == "admin":
                # Admin ve todas las empresas
                response = self.supabase.table("empresas").select("id, nombre").execute()
            elif self.rol == "gestor":
                # Gestor solo ve sus empresas clientes
                response = self.supabase.table("empresas").select("id, nombre").eq(
                    "empresa_matriz_id", self.empresa_id
                ).execute()
            else:
                return {}
            
            if response.data:
                return {empresa["nombre"]: empresa["id"] for empresa in response.data}
            return {}
            
        except Exception as e:
            print(f"Error obteniendo empresas para grupos: {e}")
            return {}
    
    def validar_cif_unico(self, cif: str, empresa_id: Optional[str] = None) -> bool:
        """
        Valida que el CIF sea único en el ámbito correspondiente.
        
        Args:
            cif: CIF a validar
            empresa_id: ID de empresa actual (para edición)
            
        Returns:
            bool: True si el CIF es válido/único
        """
        try:
            query = self.supabase.table("empresas").select("id").eq("cif", cif)
            
            if empresa_id:
                query = query.neq("id", empresa_id)
            
            # Para gestores, verificar solo en su ámbito
            if self.rol == "gestor":
                query = query.eq("empresa_matriz_id", self.empresa_id)
            
            response = query.execute()
            
            return len(response.data) == 0
            
        except Exception as e:
            print(f"Error validando CIF: {e}")
            return False
    
    # =========================
    # MÉTODOS DE ESTADÍSTICAS
    # =========================
    
    def get_estadisticas_empresas(self) -> Dict[str, Any]:
        """Obtiene estadísticas de empresas según el rol."""
        try:
            if self.rol == "admin":
                # Admin ve estadísticas globales
                response = self.supabase.rpc('get_estadisticas_jerarquia').execute()
                return response.data if response.data else {}
            
            elif self.rol == "gestor":
                # Gestor ve estadísticas de sus clientes
                clientes = self._get_empresas_clientes_gestor()
                return {
                    "total_clientes": len(clientes),
                    "empresa_gestora": self.session_state.get("empresa_nombre", "")
                }
            
            return {}
            
        except Exception as e:
            print(f"Error obteniendo estadísticas: {e}")
            return {}
    
    # =========================
    # MÉTODOS AUXILIARES PRIVADOS
    # =========================
    
    def _puede_editar_empresa(self, empresa_id: str) -> bool:
        """Verifica si el usuario puede editar una empresa específica."""
        if self.rol == "admin":
            return True
        
        elif self.rol == "gestor":
            # Gestor solo puede editar sus empresas clientes
            empresa = self.get_empresa_by_id(empresa_id)
            return empresa and empresa.get("empresa_matriz_id") == self.empresa_id
        
        return False
    
    def get_contexto_jerarquico(self, empresa_id: str) -> str:
        """
        Obtiene información contextual de la posición jerárquica de una empresa.
        
        Args:
            empresa_id: ID de la empresa
            
        Returns:
            str: Descripción del contexto jerárquico
        """
        try:
            empresa = self.get_empresa_by_id(empresa_id)
            if not empresa:
                return "Empresa no encontrada"
            
            if empresa["tipo_empresa"] == "CLIENTE_SAAS":
                return "Cliente directo del SaaS"
            elif empresa["tipo_empresa"] == "GESTORA":
                clientes = self._get_empresas_hijas(empresa_id)
                return f"Gestora con {len(clientes)} clientes"
            elif empresa["tipo_empresa"] == "CLIENTE_GESTOR":
                if empresa.get("empresa_matriz_id"):
                    matriz = self.get_empresa_by_id(empresa["empresa_matriz_id"])
                    return f"Cliente de {matriz['nombre'] if matriz else 'Gestora desconocida'}"
            
            return "Sin contexto jerárquico"
            
        except Exception as e:
            print(f"Error obteniendo contexto jerárquico: {e}")
            return "Error obteniendo contexto"
