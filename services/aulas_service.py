import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
import uuid

class AulasService:
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
        self.role = session_state.role
        self.empresa_id = session_state.user.get("empresa_id") if hasattr(session_state, 'user') else None

    # =========================
    # CACHE MANAGEMENT
    # =========================
    
    def limpiar_cache_aulas(self):
        """Limpia el cache relacionado con aulas"""
        try:
            self.get_aulas_con_empresa.clear()
            self.get_estadisticas_aulas.clear()
            self.get_ocupacion_por_aula.clear()
            st.cache_data.clear()
        except:
            pass

    # =========================
    # CRUD AULAS
    # =========================
    
    @st.cache_data(ttl=300)
    def get_aulas_con_empresa(_self):
        """Obtiene aulas con información de empresa según rol"""
        try:
            # Query base
            query = _self.supabase.table("aulas").select("""
                id, nombre, descripcion, capacidad_maxima, equipamiento,
                ubicacion, activa, color_cronograma, observaciones,
                created_at, updated_at, empresa_id,
                empresas!inner(nombre, cif)
            """)
            
            # Filtrar según rol
            if _self.role == "gestor" and _self.empresa_id:
                # Gestores ven sus aulas y las de sus empresas cliente
                empresas_gestionadas = _self._get_empresas_gestionadas()
                if empresas_gestionadas:
                    query = query.in_("empresa_id", empresas_gestionadas)
                else:
                    query = query.eq("empresa_id", _self.empresa_id)
            
            result = query.order("nombre").execute()
            
            if result.data:
                # Aplanar datos de empresa
                aulas = []
                for aula in result.data:
                    aula_flat = {
                        **aula,
                        "empresa_nombre": aula["empresas"]["nombre"],
                        "empresa_cif": aula["empresas"]["cif"]
                    }
                    # Remover objeto anidado
                    aula_flat.pop("empresas", None)
                    aulas.append(aula_flat)
                
                return pd.DataFrame(aulas)
            
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Error cargando aulas: {e}")
            return pd.DataFrame()

    def _get_empresas_gestionadas(self) -> List[str]:
        """Obtiene IDs de empresas que gestiona el usuario actual"""
        try:
            if self.role != "gestor" or not self.empresa_id:
                return []
            
            # Obtener empresa propia + empresas cliente
            result = self.supabase.table("empresas").select("id").or_(
                f"id.eq.{self.empresa_id},empresa_matriz_id.eq.{self.empresa_id}"
            ).execute()
            
            return [emp["id"] for emp in result.data or []]
            
        except Exception as e:
            print(f"Error obteniendo empresas gestionadas: {e}")
            return [self.empresa_id] if self.empresa_id else []

    def crear_aula(self, datos_aula: Dict) -> Tuple[bool, Optional[str]]:
        """Crea una nueva aula"""
        try:
            # Validar empresa_id según rol
            if self.role == "gestor" and not datos_aula.get("empresa_id"):
                datos_aula["empresa_id"] = self.empresa_id
            
            # Generar ID
            aula_id = str(uuid.uuid4())
            datos_aula["id"] = aula_id
            
            # Validaciones
            if not datos_aula.get("nombre"):
                return False, "El nombre del aula es obligatorio"
                
            if not datos_aula.get("empresa_id"):
                return False, "Empresa requerida"
            
            # Verificar nombre único en la empresa
            existing = self.supabase.table("aulas").select("id").eq(
                "empresa_id", datos_aula["empresa_id"]
            ).eq("nombre", datos_aula["nombre"]).execute()
            
            if existing.data:
                return False, "Ya existe un aula con ese nombre en la empresa"
            
            # Crear aula
            result = self.supabase.table("aulas").insert(datos_aula).execute()
            
            if result.data:
                self.limpiar_cache_aulas()
                return True, aula_id
            
            return False, None
            
        except Exception as e:
            return False, f"Error creando aula: {e}"

    def actualizar_aula(self, aula_id: str, datos_aula: Dict) -> bool:
        """Actualiza un aula existente"""
        try:
            # Verificar permisos
            if not self._puede_modificar_aula(aula_id):
                return False
            
            # Verificar nombre único (excluyendo el aula actual)
            if "nombre" in datos_aula:
                existing = self.supabase.table("aulas").select("id, empresa_id").eq(
                    "nombre", datos_aula["nombre"]
                ).neq("id", aula_id).execute()
                
                if existing.data:
                    # Verificar si es de la misma empresa
                    aula_actual = self.supabase.table("aulas").select("empresa_id").eq("id", aula_id).execute()
                    if (aula_actual.data and existing.data[0]["empresa_id"] == aula_actual.data[0]["empresa_id"]):
                        return False
            
            # Actualizar
            result = self.supabase.table("aulas").update(datos_aula).eq("id", aula_id).execute()
            
            if result.data:
                self.limpiar_cache_aulas()
                return True
                
            return False
            
        except Exception as e:
            return False

    def eliminar_aula(self, aula_id: str) -> bool:
        """Elimina un aula (solo si no tiene reservas futuras)"""
        try:
            # Verificar permisos
            if not self._puede_modificar_aula(aula_id):
                return False
            
            # Verificar que no tenga reservas futuras
            ahora = datetime.utcnow().isoformat()
            reservas_futuras = self.supabase.table("aula_reservas").select("id").eq(
                "aula_id", aula_id
            ).gte("fecha_fin", ahora).execute()
            
            if reservas_futuras.data:
                return False
            
            # Eliminar reservas pasadas primero
            self.supabase.table("aula_reservas").delete().eq("aula_id", aula_id).execute()
            
            # Eliminar aula
            result = self.supabase.table("aulas").delete().eq("id", aula_id).execute()
            
            if result.data:
                self.limpiar_cache_aulas()
                return True
                
            return False
            
        except Exception as e:
            return False

    def _puede_modificar_aula(self, aula_id: str) -> bool:
        """Verifica si el usuario puede modificar un aula"""
        try:
            if self.role == "admin":
                return True
            
            if self.role == "gestor" and self.empresa_id:
                # Verificar que el aula pertenezca a empresa gestionada
                aula = self.supabase.table("aulas").select("empresa_id").eq("id", aula_id).execute()
                if aula.data:
                    empresas_gestionadas = self._get_empresas_gestionadas()
                    return aula.data[0]["empresa_id"] in empresas_gestionadas
            
            return False
            
        except:
            return False

    # =========================
    # GESTIÓN DE RESERVAS
    # =========================
    
    def get_reservas_periodo(self, fecha_inicio: str, fecha_fin: str) -> pd.DataFrame:
        """Obtiene reservas en un período específico"""
        try:
            query = self.supabase.table("aula_reservas").select("""
                id, titulo, fecha_inicio, fecha_fin, tipo_reserva, estado, responsable,
                aulas!inner(id, nombre, empresa_id),
                grupos(id, codigo_grupo)
            """).gte("fecha_inicio", fecha_inicio).lte("fecha_fin", fecha_fin)
            
            # Filtrar según rol
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                query = query.in_("aulas.empresa_id", empresas_gestionadas)
            
            result = query.order("fecha_inicio").execute()
            
            if result.data:
                reservas = []
                for reserva in result.data:
                    reserva_flat = {
                        **reserva,
                        "aula_nombre": reserva["aulas"]["nombre"],
                        "aula_id": reserva["aulas"]["id"],
                        "grupo_codigo": reserva.get("grupos", {}).get("codigo_grupo") if reserva.get("grupos") else None
                    }
                    # Remover objetos anidados
                    reserva_flat.pop("aulas", None)
                    reserva_flat.pop("grupos", None)
                    reservas.append(reserva_flat)
                
                return pd.DataFrame(reservas)
            
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Error cargando reservas: {e}")
            return pd.DataFrame()

    def get_reservas_proximas(self, dias: int = 30) -> pd.DataFrame:
        """Obtiene reservas próximas según rol"""
        try:
            fecha_inicio = datetime.utcnow().isoformat()
            fecha_fin = (datetime.utcnow() + timedelta(days=dias)).isoformat()
            
            return self.get_reservas_periodo(fecha_inicio, fecha_fin)
            
        except Exception as e:
            print(f"Error cargando reservas próximas: {e}")
            return pd.DataFrame()

    def crear_reserva(self, datos_reserva: Dict) -> Tuple[bool, Optional[str]]:
        """Crea una nueva reserva de aula"""
        try:
            # Validaciones
            if not self._validar_datos_reserva(datos_reserva):
                return False, None
            
            # Verificar disponibilidad
            if not self.verificar_disponibilidad_aula(
                datos_reserva["aula_id"], 
                datos_reserva["fecha_inicio"], 
                datos_reserva["fecha_fin"]
            ):
                return False, "El aula no está disponible en esas fechas"
            
            # Generar ID
            reserva_id = str(uuid.uuid4())
            datos_reserva["id"] = reserva_id
            datos_reserva["created_at"] = datetime.utcnow().isoformat()
            
            result = self.supabase.table("aula_reservas").insert(datos_reserva).execute()
            
            if result.data:
                return True, reserva_id
            
            return False, None
            
        except Exception as e:
            return False, f"Error creando reserva: {e}"
            
    def verificar_disponibilidad_aula(self, aula_id: str, fecha_inicio: str, fecha_fin: str, 
                                    reserva_excluir: Optional[str] = None) -> bool:
        """Verifica si un aula está disponible en un periodo"""
        try:
            query = self.supabase.table("aula_reservas").select("id").eq("aula_id", aula_id).neq(
                "estado", "CANCELADA"
            ).or_(
                f"and(fecha_inicio.lte.{fecha_fin},fecha_fin.gte.{fecha_inicio})"
            )
            
            if reserva_excluir:
                query = query.neq("id", reserva_excluir)
            
            result = query.execute()
            
            return len(result.data) == 0
            
        except Exception as e:
            return False

    def obtener_conflictos_detallados(self, aula_id: str, fecha_inicio: str, fecha_fin: str, 
                                    reserva_excluir: Optional[str] = None) -> List[Dict]:
        """Obtiene detalles de los conflictos de disponibilidad"""
        try:
            query = self.supabase.table("aula_reservas").select("""
                id, titulo, fecha_inicio, fecha_fin, tipo_reserva, estado,
                grupos(codigo_grupo)
            """).eq("aula_id", aula_id).neq("estado", "CANCELADA").or_(
                f"and(fecha_inicio.lte.{fecha_fin},fecha_fin.gte.{fecha_inicio})"
            )
            
            if reserva_excluir:
                query = query.neq("id", reserva_excluir)
            
            result = query.execute()
            
            conflictos = []
            for reserva in result.data or []:
                inicio_dt = pd.to_datetime(reserva["fecha_inicio"])
                fin_dt = pd.to_datetime(reserva["fecha_fin"])
                
                conflicto = {
                    "id": reserva["id"],
                    "titulo": reserva["titulo"],
                    "tipo_reserva": reserva["tipo_reserva"],
                    "fecha_inicio": inicio_dt.strftime('%d/%m/%Y %H:%M'),
                    "fecha_fin": fin_dt.strftime('%d/%m/%Y %H:%M'),
                    "grupo_codigo": reserva.get("grupos", {}).get("codigo_grupo") if reserva.get("grupos") else None
                }
                conflictos.append(conflicto)
            
            return conflictos
            
        except Exception as e:
            return []

    def _validar_datos_reserva(self, datos: Dict) -> bool:
        """Valida datos de reserva"""
        campos_obligatorios = ["aula_id", "titulo", "fecha_inicio", "fecha_fin"]
        
        for campo in campos_obligatorios:
            if not datos.get(campo):
                return False
        
        # Validar fechas
        try:
            inicio = datetime.fromisoformat(datos["fecha_inicio"].replace('Z', '+00:00'))
            fin = datetime.fromisoformat(datos["fecha_fin"].replace('Z', '+00:00'))
            
            if inicio >= fin:
                return False
                
        except ValueError:
            return False
        
        return True

    def actualizar_reserva(self, reserva_id: str, datos_actualizacion: Dict) -> bool:
        """Actualiza una reserva existente"""
        try:
            datos_actualizacion["updated_at"] = datetime.utcnow().isoformat()
            
            result = self.supabase.table("aula_reservas").update(
                datos_actualizacion
            ).eq("id", reserva_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            return False

    def eliminar_reserva(self, reserva_id: str) -> bool:
        """Elimina una reserva"""
        try:
            result = self.supabase.table("aula_reservas").delete().eq("id", reserva_id).execute()
            return bool(result.data)
            
        except Exception as e:
            return False

    def get_grupos_basicos(self):
        """Método temporal para obtener grupos - debería usar grupos_service"""
        try:
            query = self.supabase.table("grupos").select("""
                id, codigo_grupo, fecha_inicio, fecha_fin_prevista, estado,
                acciones_formativas(nombre)
            """)
            
            # Filtrar según rol
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                query = query.in_("empresa_id", empresas_gestionadas)
            
            result = query.execute()
            
            if result.data:
                grupos = []
                for grupo in result.data:
                    grupo_flat = {
                        **grupo,
                        "accion_nombre": grupo.get("acciones_formativas", {}).get("nombre", "Sin acción") if grupo.get("acciones_formativas") else "Sin acción"
                    }
                    grupo_flat.pop("acciones_formativas", None)
                    grupos.append(grupo_flat)
                
                return pd.DataFrame(grupos)
            
            return pd.DataFrame()
            
        except Exception as e:
            return pd.DataFrame()

    def get_reserva_by_id(self, reserva_id: str) -> Optional[Dict]:
        """Obtiene una reserva específica por ID"""
        try:
            result = self.supabase.table("aula_reservas").select("""
                id, titulo, descripcion, fecha_inicio, fecha_fin, tipo_reserva, estado,
                responsable, aula_id, grupo_id, created_at, updated_at
            """).eq("id", reserva_id).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            print(f"Error obteniendo reserva {reserva_id}: {e}")
            return None
    
    def verificar_conflictos_reserva(self, aula_id: str, fecha_inicio: str, fecha_fin: str, 
                                   excluir_reserva_id: Optional[str] = None) -> bool:
        """Verifica si hay conflictos con otras reservas (True = hay conflictos)"""
        try:
            query = self.supabase.table("aula_reservas").select("id").eq("aula_id", aula_id).neq(
                "estado", "CANCELADA"
            ).or_(
                f"and(fecha_inicio.lte.{fecha_fin},fecha_fin.gte.{fecha_inicio})"
            )
            
            if excluir_reserva_id:
                query = query.neq("id", excluir_reserva_id)
            
            result = query.execute()
            
            # True = hay conflictos, False = no hay conflictos
            return len(result.data or []) > 0
            
        except Exception as e:
            print(f"Error verificando conflictos: {e}")
            return True  # Asumir conflicto en caso de error
    
    def actualizar_estado_reserva(self, reserva_id: str, nuevo_estado: str) -> bool:
        """Actualiza solo el estado de una reserva"""
        try:
            datos_actualizacion = {
                "estado": nuevo_estado,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            result = self.supabase.table("aula_reservas").update(
                datos_actualizacion
            ).eq("id", reserva_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            print(f"Error actualizando estado de reserva: {e}")
            return False
    
    def get_estadisticas_rapidas(self) -> Dict[str, Any]:
        """Estadísticas rápidas para el widget lateral"""
        try:
            stats = {}
            
            # Total aulas
            aulas_query = self.supabase.table("aulas").select("id, activa, empresa_id")
            
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                aulas_query = aulas_query.in_("empresa_id", empresas_gestionadas)
            
            aulas_result = aulas_query.execute()
            aulas_data = aulas_result.data or []
            
            stats["total_aulas"] = len(aulas_data)
            stats["aulas_activas"] = sum(1 for aula in aulas_data if aula.get("activa", True))
            
            # Reservas de hoy
            hoy_inicio = datetime.now().strftime("%Y-%m-%d") + "T00:00:00Z"
            hoy_fin = datetime.now().strftime("%Y-%m-%d") + "T23:59:59Z"
            
            reservas_query = self.supabase.table("aula_reservas").select(
                "id, aulas!inner(empresa_id)"
            ).gte("fecha_inicio", hoy_inicio).lte("fecha_inicio", hoy_fin)
            
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                reservas_query = reservas_query.in_("aulas.empresa_id", empresas_gestionadas)
            
            reservas_result = reservas_query.execute()
            stats["reservas_hoy"] = len(reservas_result.data or [])
            
            # Ocupación actual (simplificada)
            if stats["total_aulas"] > 0:
                stats["ocupacion_actual"] = min((stats["reservas_hoy"] / stats["total_aulas"]) * 100, 100)
            else:
                stats["ocupacion_actual"] = 0
            
            return stats
            
        except Exception as e:
            print(f"Error obteniendo estadísticas rápidas: {e}")
            return {
                "total_aulas": 0,
                "aulas_activas": 0,
                "reservas_hoy": 0,
                "ocupacion_actual": 0
            }
    
    def get_proximas_reservas(self, limite: int = 5) -> List[Dict]:
        """Obtiene las próximas reservas"""
        try:
            ahora = datetime.utcnow().isoformat()
            
            query = self.supabase.table("aula_reservas").select("""
                id, titulo, fecha_inicio, fecha_fin,
                aulas!inner(nombre, empresa_id)
            """).gte("fecha_inicio", ahora).order("fecha_inicio").limit(limite)
            
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                query = query.in_("aulas.empresa_id", empresas_gestionadas)
            
            result = query.execute()
            
            proximas = []
            for reserva in result.data or []:
                proximas.append({
                    "id": reserva["id"],
                    "titulo": reserva["titulo"],
                    "fecha_inicio": reserva["fecha_inicio"],
                    "fecha_fin": reserva["fecha_fin"],
                    "aula_nombre": reserva["aulas"]["nombre"]
                })
            
            return proximas
            
        except Exception as e:
            print(f"Error obteniendo próximas reservas: {e}")
            return []
    
    def get_aulas_disponibles_ahora(self) -> List[Dict]:
        """Obtiene aulas disponibles en este momento"""
        try:
            ahora = datetime.utcnow().isoformat()
            
            # Obtener todas las aulas activas
            aulas_query = self.supabase.table("aulas").select(
                "id, nombre, capacidad_maxima"
            ).eq("activa", True)
            
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                aulas_query = aulas_query.in_("empresa_id", empresas_gestionadas)
            
            aulas_result = aulas_query.execute()
            aulas = aulas_result.data or []
            
            # Obtener aulas ocupadas ahora
            reservas_actuales = self.supabase.table("aula_reservas").select(
                "aula_id"
            ).lte("fecha_inicio", ahora).gte("fecha_fin", ahora).neq("estado", "CANCELADA").execute()
            
            aulas_ocupadas = [r["aula_id"] for r in reservas_actuales.data or []]
            
            # Filtrar aulas disponibles
            aulas_disponibles = [aula for aula in aulas if aula["id"] not in aulas_ocupadas]
            
            return aulas_disponibles
            
        except Exception as e:
            print(f"Error obteniendo aulas disponibles: {e}")
            return []
    
    def get_notificaciones_pendientes(self) -> List[Dict]:
        """Obtiene notificaciones pendientes para el usuario"""
        try:
            notificaciones = []
            
            # Verificar conflictos próximos
            fecha_limite = (datetime.now() + timedelta(days=7)).isoformat()
            
            # Buscar reservas próximas que puedan tener conflictos
            reservas_proximas = self.supabase.table("aula_reservas").select("""
                id, titulo, fecha_inicio, aula_id,
                aulas!inner(nombre, empresa_id)
            """).gte("fecha_inicio", datetime.now().isoformat()).lte("fecha_inicio", fecha_limite)
            
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                reservas_proximas = reservas_proximas.in_("aulas.empresa_id", empresas_gestionadas)
            
            result = reservas_proximas.execute()
            
            # Verificar mantenimientos próximos
            for reserva in result.data or []:
                if reserva.get("tipo_reserva") == "MANTENIMIENTO":
                    fecha_reserva = pd.to_datetime(reserva["fecha_inicio"]).strftime('%d/%m/%Y')
                    notificaciones.append({
                        "tipo": "MANTENIMIENTO",
                        "mensaje": f"Mantenimiento programado en {reserva['aulas']['nombre']} para el {fecha_reserva}"
                    })
            
            # Añadir más tipos de notificaciones según necesidades
            if len(notificaciones) == 0:
                # Recordatorio general si no hay notificaciones específicas
                disponibles = self.get_aulas_disponibles_ahora()
                if len(disponibles) == 0:
                    notificaciones.append({
                        "tipo": "RECORDATORIO",
                        "mensaje": "Todas las aulas están ocupadas en este momento"
                    })
            
            return notificaciones[:5]  # Máximo 5 notificaciones
            
        except Exception as e:
            print(f"Error obteniendo notificaciones: {e}")
            return []
    
    def marcar_notificaciones_leidas(self) -> bool:
        """Marca las notificaciones como leídas (placeholder)"""
        try:
            # Implementación placeholder - podrías almacenar estado en BD si es necesario
            return True
            
        except Exception as e:
            print(f"Error marcando notificaciones como leídas: {e}")
            return False
    
    def get_alertas_aulas(self) -> List[Dict]:
        """Obtiene alertas importantes sobre aulas"""
        try:
            alertas = []
            
            # Verificar aulas sin reservas en mucho tiempo
            fecha_limite = (datetime.now() - timedelta(days=30)).isoformat()
            
            aulas_query = self.supabase.table("aulas").select("id, nombre, empresa_id").eq("activa", True)
            
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                aulas_query = aulas_query.in_("empresa_id", empresas_gestionadas)
            
            aulas_result = aulas_query.execute()
            
            for aula in aulas_result.data or []:
                # Verificar si tiene reservas recientes
                reservas_recientes = self.supabase.table("aula_reservas").select("id").eq(
                    "aula_id", aula["id"]
                ).gte("fecha_inicio", fecha_limite).execute()
                
                if not reservas_recientes.data:
                    alertas.append({
                        "tipo": "WARNING",
                        "mensaje": f"El aula '{aula['nombre']}' no tiene reservas en los últimos 30 días"
                    })
            
            # Verificar conflictos próximos
            ahora = datetime.now().isoformat()
            una_semana = (datetime.now() + timedelta(days=7)).isoformat()
            
            # Esta es una verificación simplificada - podrías hacer más detallada
            reservas_proximas = self.supabase.table("aula_reservas").select(
                "aula_id"
            ).gte("fecha_inicio", ahora).lte("fecha_inicio", una_semana).execute()
            
            aulas_con_reservas = {}
            for reserva in reservas_proximas.data or []:
                aula_id = reserva["aula_id"]
                aulas_con_reservas[aula_id] = aulas_con_reservas.get(aula_id, 0) + 1
            
            # Alertar si alguna aula tiene muchas reservas próximas
            for aula_id, num_reservas in aulas_con_reservas.items():
                if num_reservas > 10:  # Más de 10 reservas en una semana
                    aula_info = next((a for a in aulas_result.data if a["id"] == aula_id), None)
                    if aula_info:
                        alertas.append({
                            "tipo": "INFO",
                            "mensaje": f"El aula '{aula_info['nombre']}' tiene alta demanda esta semana ({num_reservas} reservas)"
                        })
            
            return alertas[:3]  # Máximo 3 alertas
            
        except Exception as e:
            print(f"Error obteniendo alertas: {e}")
            return []
    
    def get_metricas_aulas(self) -> Dict[str, Any]:
        """Obtiene métricas completas para el dashboard de admin"""
        try:
            metricas = {}
            
            # Obtener estadísticas básicas
            stats_basicas = self.get_estadisticas_aulas()
            metricas.update(stats_basicas)
            
            # Métricas adicionales
            fecha_inicio_mes = datetime.now().replace(day=1).isoformat()
            fecha_fin_mes = datetime.now().isoformat()
            
            # Reservas por tipo este mes
            reservas_mes = self.supabase.table("aula_reservas").select(
                "tipo_reserva"
            ).gte("fecha_inicio", fecha_inicio_mes).lte("fecha_fin", fecha_fin_mes)
            
            if self.role == "gestor" and self.empresa_id:
                # Agregar filtro para gestores
                reservas_mes = reservas_mes.select("tipo_reserva, aulas!inner(empresa_id)")
                empresas_gestionadas = self._get_empresas_gestionadas()
                reservas_mes = reservas_mes.in_("aulas.empresa_id", empresas_gestionadas)
            
            result_reservas = reservas_mes.execute()
            
            tipos_count = {}
            for reserva in result_reservas.data or []:
                tipo = reserva["tipo_reserva"]
                tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
            
            metricas["reservas_por_tipo"] = tipos_count
            
            # Capacidad total
            aulas_query = self.supabase.table("aulas").select("capacidad_maxima, empresa_id").eq("activa", True)
            
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                aulas_query = aulas_query.in_("empresa_id", empresas_gestionadas)
            
            aulas_result = aulas_query.execute()
            capacidad_total = sum(aula.get("capacidad_maxima", 0) for aula in aulas_result.data or [])
            metricas["capacidad_total"] = capacidad_total
            
            # Aulas más utilizadas (simplificado)
            aulas_utilizadas = {}
            for reserva in result_reservas.data or []:
                # Esta es una aproximación - necesitarías hacer un JOIN más completo
                pass
            
            metricas["aulas_mas_utilizadas"] = {}  # Placeholder
            
            # Porcentaje de ocupación
            if metricas["total_aulas"] > 0:
                metricas["porcentaje_ocupacion"] = (metricas["reservas_hoy"] / metricas["total_aulas"]) * 100
            else:
                metricas["porcentaje_ocupacion"] = 0
            
            return metricas
            
        except Exception as e:
            print(f"Error obteniendo métricas completas: {e}")
            return {
                "total_aulas": 0,
                "aulas_activas": 0,
                "reservas_hoy": 0,
                "capacidad_total": 0,
                "porcentaje_ocupacion": 0,
                "reservas_por_tipo": {},
                "aulas_mas_utilizadas": {}
            }
    
    def get_detalle_ocupacion_aulas(self) -> pd.DataFrame:
        """Obtiene detalle de ocupación por aula para el dashboard"""
        try:
            # Obtener aulas
            aulas_query = self.supabase.table("aulas").select("id, nombre, capacidad_maxima, empresa_id")
            
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                aulas_query = aulas_query.in_("empresa_id", empresas_gestionadas)
            
            aulas_result = aulas_query.execute()
            aulas = aulas_result.data or []
            
            if not aulas:
                return pd.DataFrame()
            
            # Calcular ocupación por aula
            fecha_inicio_mes = datetime.now().replace(day=1).isoformat()
            fecha_fin_mes = datetime.now().isoformat()
            
            detalle_data = []
            
            for aula in aulas:
                # Reservas este mes
                reservas_mes = self.supabase.table("aula_reservas").select("id, fecha_inicio, fecha_fin").eq(
                    "aula_id", aula["id"]
                ).gte("fecha_inicio", fecha_inicio_mes).lte("fecha_fin", fecha_fin_mes).execute()
                
                num_reservas = len(reservas_mes.data or [])
                
                # Calcular horas ocupadas (simplificado)
                horas_ocupadas = 0
                for reserva in reservas_mes.data or []:
                    try:
                        inicio = pd.to_datetime(reserva["fecha_inicio"])
                        fin = pd.to_datetime(reserva["fecha_fin"])
                        horas = (fin - inicio).total_seconds() / 3600
                        horas_ocupadas += horas
                    except:
                        pass
                
                # Porcentaje de ocupación (basado en horas disponibles en un mes)
                horas_disponibles_mes = 30 * 12  # 12 horas/día, 30 días
                porcentaje_ocupacion = min((horas_ocupadas / horas_disponibles_mes) * 100, 100) if horas_disponibles_mes > 0 else 0
                
                detalle_data.append({
                    "nombre": aula["nombre"],
                    "capacidad_maxima": aula["capacidad_maxima"],
                    "reservas_mes": num_reservas,
                    "horas_ocupadas": round(horas_ocupadas, 1),
                    "porcentaje_ocupacion": round(porcentaje_ocupacion, 1)
                })
            
            return pd.DataFrame(detalle_data)
            
        except Exception as e:
            print(f"Error obteniendo detalle de ocupación: {e}")
            return pd.DataFrame()
            
    # =========================
    # MÉTRICAS Y ESTADÍSTICAS
    # =========================
    
    @st.cache_data(ttl=600)
    def get_estadisticas_aulas(_self) -> Dict[str, Any]:
        """Obtiene estadísticas generales de aulas"""
        try:
            stats = {}
            
            # Query base para aulas
            aulas_query = _self.supabase.table("aulas").select("id, activa, empresa_id")
            
            # Filtrar según rol
            if _self.role == "gestor" and _self.empresa_id:
                empresas_gestionadas = _self._get_empresas_gestionadas()
                aulas_query = aulas_query.in_("empresa_id", empresas_gestionadas)
            
            aulas_result = aulas_query.execute()
            aulas_data = aulas_result.data or []
            
            stats["total_aulas"] = len(aulas_data)
            stats["aulas_activas"] = sum(1 for aula in aulas_data if aula.get("activa", True))
            stats["aulas_inactivas"] = stats["total_aulas"] - stats["aulas_activas"]
            
            # Reservas de hoy
            hoy_inicio = datetime.now().strftime("%Y-%m-%d") + "T00:00:00Z"
            hoy_fin = datetime.now().strftime("%Y-%m-%d") + "T23:59:59Z"
            
            reservas_query = _self.supabase.table("aula_reservas").select(
                "id, aulas!inner(empresa_id)"
            ).gte("fecha_inicio", hoy_inicio).lte("fecha_inicio", hoy_fin)
            
            if _self.role == "gestor" and _self.empresa_id:
                empresas_gestionadas = _self._get_empresas_gestionadas()
                reservas_query = reservas_query.in_("aulas.empresa_id", empresas_gestionadas)
            
            reservas_result = reservas_query.execute()
            stats["reservas_hoy"] = len(reservas_result.data or [])
            
            # Ocupación promedio (último mes)
            stats["ocupacion_promedio"] = _self._calcular_ocupacion_promedio()
            
            return stats
            
        except Exception as e:
            return {
                "total_aulas": 0,
                "aulas_activas": 0,
                "aulas_inactivas": 0,
                "reservas_hoy": 0,
                "ocupacion_promedio": 0
            }
    
    def _calcular_ocupacion_promedio(self) -> float:
        """Calcula la ocupación promedio de las aulas"""
        try:
            # Esto es una implementación simplificada
            fecha_inicio = (datetime.now() - timedelta(days=30)).isoformat()
            fecha_fin = datetime.now().isoformat()
            
            # Obtener aulas
            aulas = self.supabase.table("aulas").select("id").execute()
            total_aulas = len(aulas.data or [])
            
            if total_aulas == 0:
                return 0.0
            
            # Obtener reservas del último mes
            reservas = self.supabase.table("aula_reservas").select("id").gte(
                "fecha_inicio", fecha_inicio
            ).lte("fecha_fin", fecha_fin).execute()
            
            total_reservas = len(reservas.data or [])
            
            # Cálculo simplificado: reservas por aula
            ocupacion = min((total_reservas / total_aulas) * 10, 100) if total_aulas > 0 else 0
            
            return round(ocupacion, 1)
            
        except:
            return 0.0
    
    @st.cache_data(ttl=600)
    def get_ocupacion_por_aula(_self) -> pd.DataFrame:
        """Obtiene ocupación por aula individual"""
        try:
            # Obtener aulas
            aulas_query = _self.supabase.table("aulas").select("id, nombre, empresa_id")
            
            if _self.role == "gestor" and _self.empresa_id:
                empresas_gestionadas = _self._get_empresas_gestionadas()
                aulas_query = aulas_query.in_("empresa_id", empresas_gestionadas)
            
            aulas_result = aulas_query.execute()
            aulas = aulas_result.data or []
            
            if not aulas:
                return pd.DataFrame()
            
            # Calcular ocupación por aula
            fecha_inicio = (datetime.now() - timedelta(days=30)).isoformat()
            fecha_fin = datetime.now().isoformat()
            
            ocupacion_data = []
            
            for aula in aulas:
                reservas = _self.supabase.table("aula_reservas").select("id").eq(
                    "aula_id", aula["id"]
                ).gte("fecha_inicio", fecha_inicio).lte("fecha_fin", fecha_fin).execute()
                
                num_reservas = len(reservas.data or [])
                # Ocupación simplificada (máximo 100%)
                ocupacion_porcentaje = min(num_reservas * 5, 100)
                
                ocupacion_data.append({
                    "nombre": aula["nombre"],
                    "reservas": num_reservas,
                    "ocupacion_porcentaje": ocupacion_porcentaje
                })
            
            return pd.DataFrame(ocupacion_data)
            
        except Exception as e:
            return pd.DataFrame()
    
    # =========================
    # FUNCIONES DE CRONOGRAMA
    # =========================
    
    def get_eventos_cronograma(self, fecha_inicio: str, fecha_fin: str, 
                             aulas_ids: Optional[List[str]] = None) -> List[Dict]:
        """Obtiene eventos para el componente de cronograma"""
        try:
            query = self.supabase.table("aula_reservas").select("""
                id, titulo, fecha_inicio, fecha_fin, tipo_reserva, estado,
                aulas!inner(id, nombre, color_cronograma, empresa_id),
                grupos(codigo_grupo)
            """).gte("fecha_inicio", fecha_inicio).lte("fecha_fin", fecha_fin)
            
            # Filtrar por aulas específicas
            if aulas_ids:
                query = query.in_("aula_id", aulas_ids)
            
            # Filtrar según rol
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                query = query.in_("aulas.empresa_id", empresas_gestionadas)
            
            result = query.execute()
            
            eventos = []
            for reserva in result.data or []:
                aula = reserva["aulas"]
                grupo = reserva.get("grupos")
                
                # Determinar color según tipo
                color = self._get_color_evento(reserva["tipo_reserva"], aula.get("color_cronograma"))
                
                # Determinar clases CSS
                css_class = f"fc-event-{reserva['tipo_reserva'].lower()}"
                
                evento = {
                    "id": reserva["id"],
                    "title": f"{aula['nombre']}: {reserva['titulo']}",
                    "start": reserva["fecha_inicio"],
                    "end": reserva["fecha_fin"],
                    "backgroundColor": color,
                    "borderColor": color,
                    "textColor": "#ffffff" if reserva["tipo_reserva"] != "MANTENIMIENTO" else "#000000",
                    "className": css_class,
                    "extendedProps": {
                        "aula_id": aula["id"],
                        "aula_nombre": aula["nombre"],
                        "tipo_reserva": reserva["tipo_reserva"],
                        "estado": reserva["estado"],
                        "grupo_codigo": grupo.get("codigo_grupo") if grupo else None
                    }
                }
                eventos.append(evento)
            
            return eventos
            
        except Exception as e:
            print(f"Error obteniendo eventos de cronograma: {e}")
            return []
    
    def _get_color_evento(self, tipo_reserva: str, color_aula: Optional[str] = None) -> str:
        """Determina el color del evento según el tipo"""
        colores_tipo = {
            'GRUPO': '#28a745',          # Verde - Formación
            'MANTENIMIENTO': '#ffc107',  # Amarillo - Mantenimiento  
            'EVENTO': '#17a2b8',         # Azul - Eventos especiales
            'BLOQUEADA': '#dc3545'       # Rojo - No disponible
        }
        
        return colores_tipo.get(tipo_reserva, color_aula or '#6c757d')
    
    def get_aulas_disponibles_periodo(self, fecha_inicio: str, fecha_fin: str) -> List[Dict]:
        """Obtiene aulas disponibles en un periodo específico"""
        try:
            # Obtener todas las aulas activas
            aulas_query = self.supabase.table("aulas").select(
                "id, nombre, capacidad_maxima, ubicacion"
            ).eq("activa", True)
            
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                aulas_query = aulas_query.in_("empresa_id", empresas_gestionadas)
            
            aulas_result = aulas_query.execute()
            aulas = aulas_result.data or []
            
            # Filtrar aulas disponibles
            aulas_disponibles = []
            for aula in aulas:
                if self.verificar_disponibilidad_aula(aula["id"], fecha_inicio, fecha_fin):
                    aulas_disponibles.append(aula)
            
            return aulas_disponibles
            
        except Exception as e:
            return []
    
    
def get_aulas_service(supabase, session_state) -> AulasService:
    """Factory function para obtener instancia del servicio de aulas"""
    return AulasService(supabase, session_state)
