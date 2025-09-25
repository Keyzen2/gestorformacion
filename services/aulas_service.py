import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
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
            print(f"Error cargando aulas: {e}")  # Cambiar st.error por print
            return pd.DataFrame()

    def _get_empresas_gestionadas(self) -> List[str]:
        """Obtiene IDs de empresas que gestiona el usuario actual"""
        try:
            if self.role != "gestor" or not self.empresa_id:
                return []


def get_aulas_service(supabase, session_state) -> AulasService:
    """Factory function para obtener instancia del servicio de aulas"""
    return AulasService(supabase, session_state)
            
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
            st.error(f"Error cargando reservas: {e}")
            return pd.DataFrame()

    def get_reservas_proximas(self, dias: int = 30) -> pd.DataFrame:
        """Obtiene reservas próximas según rol"""
        try:
            fecha_inicio = datetime.utcnow().isoformat()
            fecha_fin = (datetime.utcnow() + timedelta(days=dias)).isoformat()
            
            query = self.supabase.table("aula_reservas").select("""
                id, titulo, fecha_inicio, fecha_fin, tipo_reserva, estado, responsable,
                aulas!inner(id, nombre, empresa_id),
                grupos(id, codigo_grupo)
            """).gte("fecha_inicio", fecha_inicio).lte("fecha_inicio", fecha_fin)
            
            # Filtrar según rol
            if self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                # Aplicar filtro a través de la relación con aulas
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
            st.error(f"Error cargando reservas: {e}")
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
                st.error("El aula no está disponible en esas fechas")
                return False, None
            
            # Generar ID
            reserva_id = str(uuid.uuid4())
            datos_reserva["id"] = reserva_id
            datos_reserva["created_at"] = datetime.utcnow().isoformat()
            
            result = self.supabase.table("aula_reservas").insert(datos_reserva).execute()
            
            if result.data:
                return True, reserva_id
            
            return False, None
            
        except Exception as e:
            st.error(f"Error creando reserva: {e}")
            return False, None

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
            st.error(f"Error verificando disponibilidad: {e}")
            return False

    def _validar_datos_reserva(self, datos: Dict) -> bool:
        """Valida datos de reserva"""
        campos_obligatorios = ["aula_id", "titulo", "fecha_inicio", "fecha_fin"]
        
        for campo in campos_obligatorios:
            if not datos.get(campo):
                st.error(f"Campo {campo} es obligatorio")
                return False
        
        # Validar fechas
        try:
            inicio = datetime.fromisoformat(datos["fecha_inicio"].replace('Z', '+00:00'))
            fin = datetime.fromisoformat(datos["fecha_fin"].replace('Z', '+00:00'))
            
            if inicio >= fin:
                st.error("La fecha de inicio debe ser anterior a la fecha de fin")
                return False
                
        except ValueError:
            st.error("Formato de fecha inválido")
            return False
        
        return True

    def asignar_grupo_a_aula(self, grupo_id: str, aula_id: str) -> bool:
        """Asigna un grupo formativo a un aula automáticamente"""
        try:
            # Obtener datos del grupo
            grupo = self.supabase.table("grupos").select(
                "id, codigo_grupo, fecha_inicio, fecha_fin_prevista, horario"
            ).eq("id", grupo_id).execute()
            
            if not grupo.data:
                st.error("Grupo no encontrado")
                return False
            
            grupo_data = grupo.data[0]
            
            # Crear reserva automática
            datos_reserva = {
                "aula_id": aula_id,
                "grupo_id": grupo_id,
                "titulo": f"Formación - {grupo_data['codigo_grupo']}",
                "fecha_inicio": grupo_data["fecha_inicio"] + "T08:00:00Z",  # Hora por defecto
                "fecha_fin": (grupo_data.get("fecha_fin_prevista") or grupo_data["fecha_inicio"]) + "T18:00:00Z",
                "tipo_reserva": "GRUPO",
                "estado": "CONFIRMADA",
                "responsable": "Sistema automático"
            }
            
            success, reserva_id = self.crear_reserva(datos_reserva)
            return success
            
        except Exception as e:
            st.error(f"Error asignando grupo a aula: {e}")
            return False

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
            st.error(f"Error calculando estadísticas: {e}")
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
            # En un caso real calcularías horas ocupadas vs horas disponibles
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
            st.error(f"Error calculando ocupación por aula: {e}")
            return pd.DataFrame()

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
            st.error(f"Error obteniendo eventos de cronograma: {e}")
            return []
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
                
                evento = {
                    "id": reserva["id"],
                    "title": f"{aula['nombre']}: {reserva['titulo']}",
                    "start": reserva["fecha_inicio"],
                    "end": reserva["fecha_fin"],
                    "color": color,
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
            st.error(f"Error obteniendo eventos de cronograma: {e}")
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
            st.error(f"Error obteniendo aulas disponibles: {e}")
            return []


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
