import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Optional, Tuple, Any
import uuid
import json

class ClasesService:
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
        self.role = session_state.role
        self.user_id = session_state.user.get("id") if hasattr(session_state, 'user') and session_state.user else None
        self.empresa_id = session_state.user.get("empresa_id") if hasattr(session_state, 'user') and session_state.user else None

    # =========================
    # GESTIÓN DE CACHE
    # =========================
    
    def limpiar_cache_clases(self):
        """Limpia el cache relacionado con clases"""
        try:
            if hasattr(self.get_clases_con_empresa, 'clear'):
                self.get_clases_con_empresa.clear()
            if hasattr(self.get_horarios_con_clase, 'clear'):
                self.get_horarios_con_clase.clear()
            if hasattr(self.get_estadisticas_clases, 'clear'):
                self.get_estadisticas_clases.clear()
            st.cache_data.clear()
        except:
            pass

    # =========================
    # GESTIÓN DE EMPRESAS
    # =========================
    
    def _get_empresas_gestionadas(self) -> List[str]:
        """Obtiene IDs de empresas que gestiona el usuario actual"""
        try:
            if self.role != "gestor" or not self.empresa_id:
                return []
            
            result = self.supabase.table("empresas").select("id").or_(
                f"id.eq.{self.empresa_id},empresa_matriz_id.eq.{self.empresa_id}"
            ).execute()
            
            return [emp["id"] for emp in result.data or []]
            
        except Exception as e:
            print(f"Error obteniendo empresas gestionadas: {e}")
            return [self.empresa_id] if self.empresa_id else []

    def _puede_modificar_clase(self, clase_id: str) -> bool:
        """Verifica si el usuario puede modificar una clase"""
        try:
            if self.role == "admin":
                return True
            
            if self.role == "gestor" and self.empresa_id:
                clase = self.supabase.table("clases").select("empresa_id").eq("id", clase_id).execute()
                if clase.data:
                    empresas_gestionadas = self._get_empresas_gestionadas()
                    return clase.data[0]["empresa_id"] in empresas_gestionadas
            
            return False
            
        except:
            return False

    # =========================
    # CRUD CLASES
    # =========================
    
    @st.cache_data(ttl=300)
    def get_clases_con_empresa(_self):
        """Obtiene clases con información de empresa según rol"""
        try:
            query = _self.supabase.table("clases").select("""
                id, nombre, descripcion, categoria, color_cronograma, activa,
                created_at, updated_at, empresa_id,
                empresas!inner(nombre, cif)
            """)
            
            # Filtrar según rol
            if _self.role == "gestor" and _self.empresa_id:
                empresas_gestionadas = _self._get_empresas_gestionadas()
                if empresas_gestionadas:
                    query = query.in_("empresa_id", empresas_gestionadas)
                else:
                    query = query.eq("empresa_id", _self.empresa_id)
            
            result = query.order("nombre").execute()
            
            if result.data:
                clases = []
                for clase in result.data:
                    clase_flat = {
                        **clase,
                        "empresa_nombre": clase["empresas"]["nombre"],
                        "empresa_cif": clase["empresas"]["cif"]
                    }
                    clase_flat.pop("empresas", None)
                    clases.append(clase_flat)
                
                return pd.DataFrame(clases)
            
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Error cargando clases: {e}")
            return pd.DataFrame()

    def crear_clase(self, datos_clase: Dict) -> Tuple[bool, Optional[str]]:
        """Crea una nueva clase"""
        try:
            if self.role == "gestor" and not datos_clase.get("empresa_id"):
                datos_clase["empresa_id"] = self.empresa_id
            
            clase_id = str(uuid.uuid4())
            datos_clase["id"] = clase_id
            
            # Validaciones
            if not datos_clase.get("nombre"):
                return False, "El nombre de la clase es obligatorio"
                
            if not datos_clase.get("empresa_id"):
                return False, "Empresa requerida"
            
            # Verificar nombre único en la empresa
            existing = self.supabase.table("clases").select("id").eq(
                "empresa_id", datos_clase["empresa_id"]
            ).eq("nombre", datos_clase["nombre"]).execute()
            
            if existing.data:
                return False, "Ya existe una clase con ese nombre en la empresa"
            
            result = self.supabase.table("clases").insert(datos_clase).execute()
            
            if result.data:
                self.limpiar_cache_clases()
                return True, clase_id
            
            return False, None
            
        except Exception as e:
            return False, f"Error creando clase: {e}"

    def actualizar_clase(self, clase_id: str, datos_clase: Dict) -> bool:
        """Actualiza una clase existente"""
        try:
            if not self._puede_modificar_clase(clase_id):
                return False
            
            # Verificar nombre único (excluyendo la clase actual)
            if "nombre" in datos_clase:
                existing = self.supabase.table("clases").select("id, empresa_id").eq(
                    "nombre", datos_clase["nombre"]
                ).neq("id", clase_id).execute()
                
                if existing.data:
                    clase_actual = self.supabase.table("clases").select("empresa_id").eq("id", clase_id).execute()
                    if (clase_actual.data and existing.data[0]["empresa_id"] == clase_actual.data[0]["empresa_id"]):
                        return False
            
            result = self.supabase.table("clases").update(datos_clase).eq("id", clase_id).execute()
            
            if result.data:
                self.limpiar_cache_clases()
                return True
                
            return False
            
        except Exception as e:
            return False

    def eliminar_clase(self, clase_id: str) -> bool:
        """Elimina una clase (solo si no tiene horarios activos)"""
        try:
            if not self._puede_modificar_clase(clase_id):
                return False
            
            # Verificar que no tenga horarios activos
            horarios_activos = self.supabase.table("clases_horarios").select("id").eq(
                "clase_id", clase_id
            ).eq("activo", True).execute()
            
            if horarios_activos.data:
                return False
            
            # Eliminar horarios inactivos primero
            self.supabase.table("clases_horarios").delete().eq("clase_id", clase_id).execute()
            
            # Eliminar clase
            result = self.supabase.table("clases").delete().eq("id", clase_id).execute()
            
            if result.data:
                self.limpiar_cache_clases()
                return True
                
            return False
            
        except Exception as e:
            return False
            
    def get_reservas_por_horario(self, horario_id: str, fecha: Optional[date] = None):
        """Obtiene reservas de un horario"""
        try:
            query = self.supabase.table("clases_reservas").select("""
                id, estado, fecha_clase,
                participantes(id, nombre, apellidos,
                    avatar:participantes_avatares(archivo_url)
                )
            """).eq("horario_id", horario_id).neq("estado", "CANCELADA")
            
            if fecha:
                query = query.eq("fecha_clase", fecha.isoformat())
            
            result = query.execute()
            return result.data or []
        except Exception as e:
            print("Error get_reservas_por_horario:", e)
            return []
            
    def get_reservas_periodo(self, fecha_inicio, fecha_fin, estado_filtro="Todas", empresa_id=None):
        """Obtiene reservas en un período con filtro opcional por empresa"""
        try:
            # ✅ CORREGIDO: participantes_avatars en lugar de avatares
            query = self.supabase.table("clases_reservas").select("""
                id, fecha_clase, estado,
                participante:participantes(id, nombre, apellidos, empresa_id, 
                    participantes_avatars(archivo_url)
                ),
                horario:clases_horarios(
                    hora_inicio, hora_fin,
                    clase:clases(id, nombre)
                )
            """)
            
            query = query.gte("fecha_clase", fecha_inicio.isoformat())
            query = query.lte("fecha_clase", fecha_fin.isoformat())
            
            if estado_filtro != "Todas":
                estado_map = {
                    "Reservadas": "RESERVADA",
                    "Asistió": "ASISTIÓ",
                    "No Asistió": "NO_ASISTIÓ",
                    "Canceladas": "CANCELADA"
                }
                query = query.eq("estado", estado_map.get(estado_filtro, estado_filtro.upper()))
            
            response = query.execute()
            
            if not response.data:
                return pd.DataFrame()
            
            reservas_procesadas = []
            
            for reserva in response.data:
                participante = reserva.get("participante")
                
                if not participante:
                    continue
                
                # Filtro por empresa
                if empresa_id:
                    if self.role == "gestor":
                        empresas_gestionadas = self._get_empresas_gestionadas()
                        if participante.get("empresa_id") not in empresas_gestionadas:
                            continue
                    else:
                        if participante.get("empresa_id") != empresa_id:
                            continue
                
                horario = reserva.get("horario", {})
                clase = horario.get("clase", {}) if horario else {}
                
                # Avatar - CORREGIDO
                avatar_url = None
                avatars = participante.get("participantes_avatars")
                if avatars and len(avatars) > 0:
                    avatar_url = avatars[0].get("archivo_url")
                
                reservas_procesadas.append({
                    "id": reserva["id"],
                    "fecha_clase": reserva["fecha_clase"],
                    "participante_nombre": f"{participante.get('nombre', '')} {participante.get('apellidos', '')}".strip(),
                    "clase_nombre": clase.get("nombre", "N/A"),
                    "horario": f"{horario.get('hora_inicio', '')} - {horario.get('hora_fin', '')}",
                    "estado": reserva["estado"],
                    "avatar_url": avatar_url or "https://via.placeholder.com/50"
                })
            
            return pd.DataFrame(reservas_procesadas)
        
        except Exception as e:
            print(f"Error en get_reservas_periodo: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_avatares_reserva(self, horario_id: str, fecha_clase: date) -> list:
        """Obtiene los avatares de los participantes con reserva en una clase/fecha."""
        try:
            result = (
                self.supabase.table("clases_reservas")
                .select("""
                    id,
                    participante:participantes!inner(
                        id,
                        participantes_avatars(archivo_url)
                    )
                """)
                .eq("horario_id", horario_id)
                .eq("fecha_clase", fecha_clase.isoformat())
                .neq("estado", "CANCELADA")
                .execute()
            )
    
            avatares = []
            if result.data:
                for r in result.data:
                    participante = r.get("participante", {})
                    avatars_data = participante.get("participantes_avatars", [])
                    
                    for avatar in avatars_data:
                        if avatar.get("archivo_url"):
                            avatares.append(avatar["archivo_url"])
            
            return avatares
        except Exception as e:
            print(f"Error get_avatares_reserva: {e}")
            return []
            
    # =========================
    # GESTIÓN DE HORARIOS
    # =========================
    @st.cache_data(ttl=300)
    def get_horarios_con_clase(_self, clase_id: Optional[str] = None):
        """Obtiene horarios con información de clase Y aula"""
        try:
            # LEFT JOIN con aulas para obtener nombre del aula
            query = _self.supabase.table("clases_horarios").select("""
                id, dia_semana, hora_inicio, hora_fin, capacidad_maxima, activo,
                created_at, clase_id, aula_id,
                clases!inner(nombre, categoria, empresa_id, activa),
                aulas(nombre, capacidad_maxima)
            """)
            
            if clase_id:
                query = query.eq("clase_id", clase_id)
            
            if _self.role == "gestor" and _self.empresa_id:
                empresas_gestionadas = _self._get_empresas_gestionadas()
                if empresas_gestionadas:
                    query = query.in_("clases.empresa_id", empresas_gestionadas)
                else:
                    return pd.DataFrame()
            
            result = query.order("dia_semana").order("hora_inicio").execute()
            
            if result.data:
                horarios = []
                dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                
                for horario in result.data:
                    # Extraer info del aula
                    aula_info = horario.get("aulas")
                    aula_nombre = aula_info.get("nombre") if aula_info else None
                    
                    horario_flat = {
                        "id": horario["id"],
                        "dia_semana": int(horario["dia_semana"]),  # Convertir a int nativo
                        "hora_inicio": horario["hora_inicio"],
                        "hora_fin": horario["hora_fin"],
                        "capacidad_maxima": horario["capacidad_maxima"],
                        "activo": horario["activo"],
                        "created_at": horario["created_at"],
                        "clase_id": horario["clase_id"],
                        "aula_id": horario.get("aula_id"),
                        "clase_nombre": horario["clases"]["nombre"],
                        "clase_categoria": horario["clases"]["categoria"],
                        "dia_nombre": dias_semana[horario["dia_semana"]],
                        "horario_display": f"{horario['hora_inicio']} - {horario['hora_fin']}",
                        "aula_nombre": aula_nombre
                    }
                    horarios.append(horario_flat)
                
                return pd.DataFrame(horarios)
            
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Error cargando horarios: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def crear_horario(self, datos_horario: Dict) -> Tuple[bool, Optional[str]]:
        """Crea un nuevo horario CON verificación de disponibilidad de aula"""
        try:
            # 1. Verificar que la clase existe y tenemos permisos
            clase_check = self.supabase.table("clases").select("empresa_id, nombre").eq(
                "id", datos_horario.get("clase_id")
            ).execute()
            
            if not clase_check.data:
                return False, "Clase no encontrada"
            
            clase_empresa_id = clase_check.data[0]["empresa_id"]
            clase_nombre = clase_check.data[0]["nombre"]
            
            # 2. Verificar permisos sobre la clase
            if self.role == "gestor" and self.empresa_id:
                empresas_permitidas = self._get_empresas_gestionadas()
                if clase_empresa_id not in empresas_permitidas:
                    return False, f"No tienes permisos para modificar la clase '{clase_nombre}'"
            
            # 3. Generar ID
            horario_id = str(uuid.uuid4())
            datos_horario["id"] = horario_id
            
            # 4. Validaciones de datos
            if not self._validar_datos_horario(datos_horario):
                return False, "Datos de horario inválidos - verifica día, horas y capacidad"
            
            # 5. Verificar conflictos con ESTA CLASE (mismo día)
            conflicto_clase = self.supabase.table("clases_horarios").select("id, hora_inicio, hora_fin").eq(
                "clase_id", datos_horario["clase_id"]
            ).eq("dia_semana", datos_horario["dia_semana"]).eq("activo", True).execute()
            
            if conflicto_clase.data:
                dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                dia_nombre = dias_semana[datos_horario["dia_semana"]]
                
                hora_inicio_nueva = datetime.strptime(datos_horario["hora_inicio"], "%H:%M:%S").time()
                hora_fin_nueva = datetime.strptime(datos_horario["hora_fin"], "%H:%M:%S").time()
                
                for horario_existente in conflicto_clase.data:
                    hora_inicio_exist = datetime.strptime(horario_existente["hora_inicio"], "%H:%M:%S").time()
                    hora_fin_exist = datetime.strptime(horario_existente["hora_fin"], "%H:%M:%S").time()
                    
                    # Verificar solapamiento
                    if not (hora_fin_nueva <= hora_inicio_exist or hora_inicio_nueva >= hora_fin_exist):
                        return False, f"Esta clase ya tiene un horario el {dia_nombre} de {hora_inicio_exist.strftime('%H:%M')} a {hora_fin_exist.strftime('%H:%M')}"
            
            # 6. SOLO SI HAY AULA: Verificar disponibilidad del aula
            if datos_horario.get("aula_id"):
                conflicto_aula = self.supabase.table("clases_horarios").select(
                    "id, hora_inicio, hora_fin, clases(nombre)"
                ).eq("aula_id", datos_horario["aula_id"]).eq(
                    "dia_semana", datos_horario["dia_semana"]
                ).eq("activo", True).execute()
                
                if conflicto_aula.data:
                    hora_inicio_nueva = datetime.strptime(datos_horario["hora_inicio"], "%H:%M:%S").time()
                    hora_fin_nueva = datetime.strptime(datos_horario["hora_fin"], "%H:%M:%S").time()
                    
                    for horario_aula in conflicto_aula.data:
                        hora_inicio_exist = datetime.strptime(horario_aula["hora_inicio"], "%H:%M:%S").time()
                        hora_fin_exist = datetime.strptime(horario_aula["hora_fin"], "%H:%M:%S").time()
                        
                        if not (hora_fin_nueva <= hora_inicio_exist or hora_inicio_nueva >= hora_fin_exist):
                            clase_conflicto = horario_aula.get("clases", {}).get("nombre", "otra clase")
                            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                            return False, f"El aula ya está ocupada por '{clase_conflicto}' el {dias_semana[datos_horario['dia_semana']]} de {hora_inicio_exist.strftime('%H:%M')} a {hora_fin_exist.strftime('%H:%M')}"
            
            # 7. Insertar
            result = self.supabase.table("clases_horarios").insert(datos_horario).execute()
            
            if result.data:
                self.limpiar_cache_clases()
                return True, horario_id
            
            return False, "Error al guardar en base de datos"
            
        except Exception as e:
            print(f"Error completo en crear_horario: {e}")
            return False, f"Error: {str(e)}"

    def actualizar_horario(self, horario_id: str, datos_horario: Dict) -> bool:
        """Actualiza un horario existente"""
        try:
            if not self._validar_datos_horario({**datos_horario, "clase_id": "dummy"}):
                return False
            
            result = self.supabase.table("clases_horarios").update(datos_horario).eq("id", horario_id).execute()
            
            if result.data:
                self.limpiar_cache_clases()
                return True
                
            return False
            
        except Exception as e:
            return False

    def eliminar_horario(self, horario_id: str) -> bool:
        """Elimina un horario (solo si no tiene reservas futuras)"""
        try:
            # Verificar reservas futuras
            hoy = datetime.now().date().isoformat()
            reservas_futuras = self.supabase.table("clases_reservas").select("id").eq(
                "horario_id", horario_id
            ).gte("fecha_clase", hoy).neq("estado", "CANCELADA").execute()
            
            if reservas_futuras.data:
                return False
            
            # Eliminar horario
            result = self.supabase.table("clases_horarios").delete().eq("id", horario_id).execute()
            
            if result.data:
                self.limpiar_cache_clases()
                return True
                
            return False
            
        except Exception as e:
            return False

    def _validar_datos_horario(self, datos: Dict) -> bool:
        """Valida datos de horario"""
        try:
            campos_obligatorios = ["clase_id", "dia_semana", "hora_inicio", "hora_fin", "capacidad_maxima"]
            
            # Verificar campos obligatorios
            for campo in campos_obligatorios:
                if campo not in datos or datos[campo] is None:
                    print(f"Campo faltante: {campo}")
                    return False
            
            # Validar día de semana (0-6)
            if not (0 <= datos["dia_semana"] <= 6):
                print(f"Día inválido: {datos['dia_semana']}")
                return False
            
            # Validar capacidad
            if datos["capacidad_maxima"] < 1:
                print(f"Capacidad inválida: {datos['capacidad_maxima']}")
                return False
            
            # Validar formato de horas (deben ser strings "HH:MM:SS")
            try:
                hora_inicio = datetime.strptime(datos["hora_inicio"], "%H:%M:%S").time()
                hora_fin = datetime.strptime(datos["hora_fin"], "%H:%M:%S").time()
                
                if hora_inicio >= hora_fin:
                    print(f"Hora fin debe ser posterior a hora inicio")
                    return False
                    
                print(f"Validación exitosa: {hora_inicio} - {hora_fin}")
                return True
                
            except ValueError as e:
                print(f"Error formato horas: {e}")
                return False
        
        except Exception as e:
            print(f"Error validación: {e}")
            return False

    def _verificar_conflicto_horario(self, datos: Dict, horario_excluir: Optional[str] = None) -> bool:
        """Verifica si hay conflicto de horarios"""
        try:
            query = self.supabase.table("clases_horarios").select("id").eq(
                "clase_id", datos["clase_id"]
            ).eq("dia_semana", datos["dia_semana"]).eq("activo", True)
            
            if horario_excluir:
                query = query.neq("id", horario_excluir)
            
            result = query.execute()
            
            # Por simplicidad, no verificamos solapamiento por ahora
            return False
            
        except Exception as e:
            return True  # Asumir conflicto en caso de error

    # =========================
    # GESTIÓN DE RESERVAS
    # =========================
    
    def crear_reserva(self, participante_id: str, horario_id: str, fecha_clase: date) -> Tuple[bool, Optional[str]]:
        """Crea una nueva reserva"""
        try:
            # Verificar límite mensual del participante
            if not self._verificar_limite_mensual(participante_id):
                return False, "Has alcanzado el límite de clases mensuales"
            
            # Verificar disponibilidad de la clase
            disponibilidad = self._verificar_disponibilidad_clase(horario_id, fecha_clase)
            if not disponibilidad.get("disponible", False):
                return False, "No hay cupos disponibles para esta clase"
            
            # Verificar que no tenga ya una reserva
            reserva_existente = self.supabase.table("clases_reservas").select("id").eq(
                "participante_id", participante_id
            ).eq("horario_id", horario_id).eq("fecha_clase", fecha_clase.isoformat()).execute()
            
            if reserva_existente.data:
                return False, "Ya tienes una reserva para esta clase en esta fecha"
            
            # Crear reserva
            reserva_id = str(uuid.uuid4())
            datos_reserva = {
                "id": reserva_id,
                "participante_id": participante_id,
                "horario_id": horario_id,
                "fecha_clase": fecha_clase.isoformat(),
                "estado": "RESERVADA",
                "fecha_reserva": datetime.utcnow().isoformat()
            }
            
            result = self.supabase.table("clases_reservas").insert(datos_reserva).execute()
            
            if result.data:
                # Incrementar contador mensual
                self._incrementar_contador_mensual(participante_id)
                return True, reserva_id
            
            return False, None
            
        except Exception as e:
            return False, f"Error creando reserva: {e}"

    def cancelar_reserva(self, reserva_id: str, participante_id: str) -> bool:
        """Cancela una reserva"""
        try:
            # Verificar que la reserva pertenece al participante
            reserva = self.supabase.table("clases_reservas").select("*").eq(
                "id", reserva_id
            ).eq("participante_id", participante_id).execute()
            
            if not reserva.data:
                return False
            
            # Cancelar reserva
            result = self.supabase.table("clases_reservas").update({
                "estado": "CANCELADA",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", reserva_id).execute()
            
            if result.data:
                # Decrementar contador mensual
                self._decrementar_contador_mensual(participante_id)
                return True
                
            return False
            
        except Exception as e:
            return False

    def marcar_asistencia(self, reserva_id: str, asistio: bool) -> bool:
        """Marca asistencia de un participante a una clase"""
        try:
            nuevo_estado = "ASISTIO" if asistio else "NO_ASISTIO"
            
            result = self.supabase.table("clases_reservas").update({
                "estado": nuevo_estado,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", reserva_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            return False

    # =========================
    # GESTIÓN DE SUSCRIPCIONES
    # =========================
    
    def get_suscripcion_participante(self, participante_id: str):
        """Devuelve la suscripción activa, reseteando el contador si cambió el mes."""
        try:
            res = (
                self.supabase.table("participantes_suscripciones")
                .select("*")
                .eq("participante_id", participante_id)
                .eq("activa", True)
                .maybe_single()
                .execute()
            )
            if not res.data:
                return None
    
            sus = res.data
    
            # Comprobar si estamos en un nuevo mes
            hoy = date.today()
            mes_actual = hoy.month
            año_actual = hoy.year
    
            if sus.get("mes_actual") != mes_actual or sus.get("año_actual") != año_actual:
                # Reiniciar contador
                update_data = {
                    "mes_actual": mes_actual,
                    "año_actual": año_actual,
                    "mes_referencia": f"{año_actual}-{mes_actual:02d}",
                    "clases_usadas_mes": 0
                }
                self.supabase.table("participantes_suscripciones").update(update_data).eq("id", sus["id"]).execute()
                sus.update(update_data)
    
            return sus
        except Exception as e:
            print("Error get_suscripcion_participante:", e)
            return None

    def activar_suscripcion(self, participante_id: str, empresa_id: str, clases_mensuales: int) -> bool:
        """Activa suscripción de un participante"""
        try:
            # Verificar si ya tiene suscripción
            existing = self.supabase.table("participantes_suscripciones").select("id").eq(
                "participante_id", participante_id
            ).eq("empresa_id", empresa_id).execute()
            
            mes_actual = datetime.now().month
            año_actual = datetime.now().year
            
            datos_suscripcion = {
                "participante_id": participante_id,
                "empresa_id": empresa_id,
                "activa": True,
                "clases_mensuales": clases_mensuales,
                "clases_usadas_mes": 0,
                "fecha_activacion": datetime.now().date().isoformat(),
                "mes_actual": mes_actual,
                "año_actual": año_actual
            }
            
            if existing.data:
                # Actualizar existente
                result = self.supabase.table("participantes_suscripciones").update(
                    datos_suscripcion
                ).eq("id", existing.data[0]["id"]).execute()
            else:
                # Crear nueva
                datos_suscripcion["id"] = str(uuid.uuid4())
                result = self.supabase.table("participantes_suscripciones").insert(
                    datos_suscripcion
                ).execute()
            
            return bool(result.data)
            
        except Exception as e:
            return False

    def desactivar_suscripcion(self, participante_id: str, empresa_id: str) -> bool:
        """Desactiva suscripción de un participante"""
        try:
            result = self.supabase.table("participantes_suscripciones").update({
                "activa": False,
                "fecha_vencimiento": datetime.now().date().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("participante_id", participante_id).eq("empresa_id", empresa_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            return False

    def _verificar_limite_mensual(self, participante_id: str) -> bool:
        """Verifica si el participante puede reservar más clases este mes"""
        try:
            suscripcion = self.supabase.table("participantes_suscripciones").select(
                "clases_mensuales, clases_usadas_mes"
            ).eq("participante_id", participante_id).eq("activa", True).execute()
            
            if not suscripcion.data:
                return False  # No tiene suscripción activa
            
            sub = suscripcion.data[0]
            return sub["clases_usadas_mes"] < sub["clases_mensuales"]
            
        except Exception as e:
            return False

    def _incrementar_contador_mensual(self, participante_id: str):
        """Incrementa el contador de clases usadas este mes con control de reinicio mensual"""
        try:
            hoy = datetime.utcnow().date()
            mes_actual = hoy.strftime("%Y-%m")  # Ej: 2025-09
    
            suscripcion = self.supabase.table("participantes_suscripciones").select(
                "clases_usadas_mes, mes_referencia"
            ).eq("participante_id", participante_id).eq("activa", True).execute()
            
            if suscripcion.data:
                registro = suscripcion.data[0]
                mes_guardado = registro.get("mes_referencia")
    
                # Reiniciar si es un mes nuevo
                if mes_guardado != mes_actual:
                    nuevo_contador = 1
                else:
                    nuevo_contador = registro["clases_usadas_mes"] + 1
    
                self.supabase.table("participantes_suscripciones").update({
                    "clases_usadas_mes": nuevo_contador,
                    "mes_referencia": mes_actual,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("participante_id", participante_id).eq("activa", True).execute()
                
        except Exception as e:
            print(f"Error incrementando contador: {e}")


    def _decrementar_contador_mensual(self, participante_id: str):
        """Decrementa el contador de clases usadas este mes con control de reinicio mensual"""
        try:
            hoy = datetime.utcnow().date()
            mes_actual = hoy.strftime("%Y-%m")
    
            suscripcion = self.supabase.table("participantes_suscripciones").select(
                "clases_usadas_mes, mes_referencia"
            ).eq("participante_id", participante_id).eq("activa", True).execute()
            
            if suscripcion.data:
                registro = suscripcion.data[0]
                mes_guardado = registro.get("mes_referencia")
    
                # Si cambió el mes, no restamos nada (contador ya debe reiniciarse)
                if mes_guardado != mes_actual:
                    nuevo_contador = 0
                else:
                    nuevo_contador = max(0, registro["clases_usadas_mes"] - 1)
    
                self.supabase.table("participantes_suscripciones").update({
                    "clases_usadas_mes": nuevo_contador,
                    "mes_referencia": mes_actual,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("participante_id", participante_id).eq("activa", True).execute()
                
        except Exception as e:
            print(f"Error decrementando contador: {e}")


    # =========================
    # CALENDARIO Y DISPONIBILIDAD
    # =========================
    
    def get_calendario_clases(self, fecha_inicio: date, fecha_fin: date, empresa_id: Optional[str] = None) -> List[Dict]:
        """Obtiene calendario de clases con disponibilidad"""
        try:
            # Obtener horarios
            query = self.supabase.table("clases_horarios").select("""
                id, dia_semana, hora_inicio, hora_fin, capacidad_maxima,
                clases!inner(id, nombre, categoria, color_cronograma, empresa_id, activa)
            """).eq("activo", True).eq("clases.activa", True)
            
            if empresa_id:
                query = query.eq("clases.empresa_id", empresa_id)
            elif self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                query = query.in_("clases.empresa_id", empresas_gestionadas)
            
            horarios_result = query.execute()
            
            eventos_calendario = []
            delta = timedelta(days=1)
            fecha_actual = fecha_inicio
            
            while fecha_actual <= fecha_fin:
                dia_semana = fecha_actual.weekday()  # 0=Lunes, 6=Domingo
                
                for horario in horarios_result.data or []:
                    if horario["dia_semana"] == dia_semana:
                        # Obtener disponibilidad para esta fecha
                        disponibilidad = self._verificar_disponibilidad_clase(horario["id"], fecha_actual)
                        
                        evento = {
                            "id": f"{horario['id']}_{fecha_actual.isoformat()}",
                            "horario_id": horario["id"],
                            "title": horario["clases"]["nombre"],
                            "start": f"{fecha_actual.isoformat()}T{horario['hora_inicio']}",
                            "end": f"{fecha_actual.isoformat()}T{horario['hora_fin']}",
                            "backgroundColor": horario["clases"]["color_cronograma"],
                            "borderColor": horario["clases"]["color_cronograma"],
                            "textColor": "#ffffff",
                            "extendedProps": {
                                "clase_id": horario["clases"]["id"],
                                "categoria": horario["clases"]["categoria"],
                                "capacidad_maxima": horario["capacidad_maxima"],
                                "disponible": disponibilidad.get("disponible", False),
                                "cupos_libres": disponibilidad.get("cupos_libres", 0),
                                "reservas_actuales": disponibilidad.get("reservas_actuales", 0),
                                "fecha_clase": fecha_actual.isoformat()
                            }
                        }
                        eventos_calendario.append(evento)
                
                fecha_actual += delta
            
            return eventos_calendario
            
        except Exception as e:
            print(f"Error generando calendario: {e}")
            return []

    def _verificar_disponibilidad_clase(self, horario_id: str, fecha_clase: date) -> Dict:
        """Verifica disponibilidad usando función SQL o lógica básica"""
        try:
            # Intentar usar función RPC si existe
            try:
                result = self.supabase.rpc("verificar_disponibilidad_clase", {
                    "p_horario_id": horario_id,
                    "p_fecha_clase": fecha_clase.isoformat()
                }).execute()
                
                if result.data:
                    return result.data
            except:
                # Si no existe la función, usar lógica básica
                pass
            
            # Lógica básica de disponibilidad
            horario = self.supabase.table("clases_horarios").select("capacidad_maxima").eq("id", horario_id).execute()
            
            if not horario.data:
                return {"disponible": False, "error": "Horario no encontrado"}
            
            capacidad_maxima = horario.data[0]["capacidad_maxima"]
            
            # Contar reservas activas para esa fecha y horario
            reservas = self.supabase.table("clases_reservas").select("id").eq(
                "horario_id", horario_id
            ).eq("fecha_clase", fecha_clase.isoformat()).neq("estado", "CANCELADA").execute()
            
            reservas_actuales = len(reservas.data or [])
            cupos_libres = capacidad_maxima - reservas_actuales
            
            return {
                "disponible": cupos_libres > 0,
                "cupos_libres": cupos_libres,
                "reservas_actuales": reservas_actuales,
                "capacidad_maxima": capacidad_maxima
            }
            
        except Exception as e:
            return {"disponible": False, "error": str(e)}
            
    def _verificar_disponibilidad_aula_recurrente(self, aula_id: str, dia_semana: int, 
                                              hora_inicio: str, hora_fin: str) -> bool:
        """Verifica si un aula está disponible para un horario recurrente"""
        try:
            # Verificar otros horarios de clases
            conflictos_clases = self.supabase.table("clases_horarios").select("id").eq(
                "aula_id", aula_id
            ).eq("dia_semana", dia_semana).eq("activo", True).execute()
            
            for horario in conflictos_clases.data or []:
                # Verificar solapamiento de horas (implementar lógica)
                pass
            
            # TODO: Verificar también reservas puntuales de aulas
            
            return True
            
        except Exception as e:
            print(f"Error verificando disponibilidad: {e}")
            return False
    # =========================
    # MÉTODOS PARA PARTICIPANTES/ALUMNOS
    # =========================
    
    def get_participante_id_from_auth(self, auth_id: str) -> Optional[str]:
        """Obtiene participante_id desde auth_id para compatibilidad"""
        try:
            # Buscar directamente por auth_id en participantes
            result = self.supabase.table("participantes").select("id").eq("auth_id", auth_id).execute()
            return result.data[0]["id"] if result.data else None
        except Exception as e:
            print(f"Error obteniendo participante desde auth_id: {e}")
            return None

    def get_reservas_participante(self, participante_id: str, fecha_inicio: Optional[date] = None, fecha_fin: Optional[date] = None) -> pd.DataFrame:
        """Obtiene reservas de un participante con filtros de fecha"""
        try:
            query = self.supabase.table("clases_reservas").select("""
                id, horario_id, fecha_clase, estado, fecha_reserva,
                clases_horarios!inner(dia_semana, hora_inicio, hora_fin, capacidad_maxima,
                    clases!inner(nombre, categoria, color_cronograma))
            """).eq("participante_id", participante_id)
        
            # Filtros de fecha
            if fecha_inicio:
                query = query.gte("fecha_clase", fecha_inicio.isoformat())
            else:
                query = query.gte("fecha_clase", date.today().isoformat())
        
            if fecha_fin:
                query = query.lte("fecha_clase", fecha_fin.isoformat())
        
            # Filtrar solo reservas activas (no canceladas)
            query = query.neq("estado", "CANCELADA")
        
            # Ordenar por fecha y hora de inicio
            query = query.order("fecha_clase", desc=False)
            query = query.order("hora_inicio", desc=False, foreign_table="clases_horarios")
        
            result = query.execute()
        
            if not result.data:
                return pd.DataFrame()
        
            reservas = []
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
            for reserva in result.data:
                horario = reserva.get("clases_horarios", {})
                clase = horario.get("clases", {})
            
                reserva_flat = {
                    "id": reserva["id"],
                    "horario_id": reserva["horario_id"],
                    "fecha_clase": pd.to_datetime(reserva["fecha_clase"]).date(),
                    "estado": reserva["estado"],
                    "clase_nombre": clase.get("nombre", "Sin nombre"),
                    "categoria": clase.get("categoria", ""),
                    "dia_semana": dias_semana[horario.get("dia_semana", 0)],
                    "hora_inicio": horario.get("hora_inicio", ""),
                    "hora_fin": horario.get("hora_fin", ""),
                    "horario_display": f"{horario.get('hora_inicio','')} - {horario.get('hora_fin','')}",
                    "color": clase.get("color_cronograma", "#3498db")
                }
                reservas.append(reserva_flat)
        
            return pd.DataFrame(reservas)
    
        except Exception as e:
            print(f"Error obteniendo reservas: {e}")
            return pd.DataFrame()

    def get_clases_disponibles_participante(self, participante_id: str, fecha_inicio: date, fecha_fin: date) -> List[Dict]:
        """Obtiene clases disponibles para un participante específico"""
        try:
            # Verificar suscripción activa
            suscripcion = self.get_suscripcion_participante(participante_id)
            if not suscripcion:
                return []
            
            empresa_id = suscripcion["empresa_id"]
            
            # Obtener calendario de clases de la empresa
            eventos = self.get_calendario_clases(fecha_inicio, fecha_fin, empresa_id)
            
            # Filtrar solo clases disponibles
            clases_disponibles = []
            for evento in eventos:
                if evento["extendedProps"]["disponible"]:
                    # Verificar que el participante no tenga ya una reserva
                    fecha_clase = evento["extendedProps"]["fecha_clase"]
                    horario_id = evento["horario_id"]
                    
                    reserva_existente = self.supabase.table("clases_reservas").select("id").eq(
                        "participante_id", participante_id
                    ).eq("horario_id", horario_id).eq("fecha_clase", fecha_clase).execute()
                    
                    if not reserva_existente.data:
                        clases_disponibles.append(evento)
            
            return clases_disponibles
            
        except Exception as e:
            print(f"Error obteniendo clases disponibles: {e}")
            return []

    def get_resumen_mensual_participante(self, participante_id: str) -> Dict[str, Any]:
        """Obtiene resumen mensual de un participante"""
        try:
            # Suscripción actual
            suscripcion = self.get_suscripcion_participante(participante_id)
            if not suscripcion:
                return {}
            
            # Reservas del mes actual
            mes_actual = datetime.now().month
            año_actual = datetime.now().year
            fecha_inicio_mes = date(año_actual, mes_actual, 1)
            
            if mes_actual == 12:
                fecha_fin_mes = date(año_actual + 1, 1, 1) - timedelta(days=1)
            else:
                fecha_fin_mes = date(año_actual, mes_actual + 1, 1) - timedelta(days=1)
            
            reservas_mes = self.get_reservas_participante(participante_id, fecha_inicio_mes, fecha_fin_mes)
            
            # Estadísticas
            total_reservadas = len(reservas_mes)
            asistencias = len(reservas_mes[reservas_mes["estado"] == "ASISTIO"]) if not reservas_mes.empty else 0
            no_asistencias = len(reservas_mes[reservas_mes["estado"] == "NO_ASISTIO"]) if not reservas_mes.empty else 0
            canceladas = len(reservas_mes[reservas_mes["estado"] == "CANCELADA"]) if not reservas_mes.empty else 0
            
            return {
                "clases_disponibles": suscripcion["clases_mensuales"],
                "clases_usadas": suscripcion["clases_usadas_mes"],
                "clases_restantes": suscripcion["clases_mensuales"] - suscripcion["clases_usadas_mes"],
                "total_reservadas": total_reservadas,
                "asistencias": asistencias,
                "no_asistencias": no_asistencias,
                "canceladas": canceladas,
                "porcentaje_asistencia": round((asistencias / max(1, total_reservadas - canceladas)) * 100, 1)
            }
            
        except Exception as e:
            return {}

    # =========================
    # MÉTRICAS Y ESTADÍSTICAS
    # =========================
    
    @st.cache_data(ttl=600)
    def get_estadisticas_clases(_self, empresa_id: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene estadísticas de clases"""
        try:
            stats = {}
            
            # Filtro de empresa
            if not empresa_id and _self.role == "gestor" and _self.empresa_id:
                empresas_gestionadas = _self._get_empresas_gestionadas()
                empresa_filter = empresas_gestionadas
            elif empresa_id:
                empresa_filter = [empresa_id]
            else:
                empresa_filter = None
            
            # Total de clases
            clases_query = _self.supabase.table("clases").select("id, activa")
            if empresa_filter:
                clases_query = clases_query.in_("empresa_id", empresa_filter)
            
            clases_result = clases_query.execute()
            clases_data = clases_result.data or []
            
            stats["total_clases"] = len(clases_data)
            stats["clases_activas"] = sum(1 for clase in clases_data if clase.get("activa", True))
            
            # ✅ CORREGIDO: Reservas HECHAS hoy (no clases que ocurren hoy)
            hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
            hoy_fin = datetime.now().replace(hour=23, minute=59, second=59).isoformat()
            
            reservas_hoy_query = _self.supabase.table("clases_reservas").select("id")
            reservas_hoy_query = reservas_hoy_query.gte("fecha_reserva", hoy_inicio)
            reservas_hoy_query = reservas_hoy_query.lte("fecha_reserva", hoy_fin)
            reservas_hoy_query = reservas_hoy_query.neq("estado", "CANCELADA")
            
            # Filtrar por empresa si aplica
            if empresa_filter:
                # Necesitamos hacer JOIN con participantes para filtrar por empresa
                reservas_hoy_query = _self.supabase.table("clases_reservas").select(
                    "id, participante:participantes!inner(empresa_id)"
                ).gte("fecha_reserva", hoy_inicio).lte("fecha_reserva", hoy_fin).neq("estado", "CANCELADA")
                
                reservas_hoy_result = reservas_hoy_query.execute()
                
                # Filtrar manualmente por empresa (ya que Supabase no permite filtrar en nested fields directamente)
                reservas_filtradas = [
                    r for r in (reservas_hoy_result.data or [])
                    if r.get("participante", {}).get("empresa_id") in empresa_filter
                ]
                stats["reservas_hoy"] = len(reservas_filtradas)
            else:
                reservas_hoy_result = reservas_hoy_query.execute()
                stats["reservas_hoy"] = len(reservas_hoy_result.data or [])
            
            # Participantes con suscripción activa
            suscripciones_query = _self.supabase.table("participantes_suscripciones").select("id")
            if empresa_filter:
                suscripciones_query = suscripciones_query.in_("empresa_id", empresa_filter)
            
            suscripciones_result = suscripciones_query.eq("activa", True).execute()
            stats["participantes_suscritos"] = len(suscripciones_result.data or [])
            
            # Tasa de ocupación promedio
            stats["ocupacion_promedio"] = _self._calcular_ocupacion_promedio(empresa_filter)
            
            return stats
            
        except Exception as e:
            print(f"Error obteniendo estadísticas: {e}")
            return {
                "total_clases": 0,
                "clases_activas": 0,
                "reservas_hoy": 0,
                "participantes_suscritos": 0,
                "ocupacion_promedio": 0
            }

    def _calcular_ocupacion_promedio(self, empresa_filter: Optional[List[str]] = None) -> float:
        """Calcula ocupación promedio de clases"""
        try:
            # Implementación simplificada
            fecha_inicio = (datetime.now() - timedelta(days=7)).date()
            fecha_fin = datetime.now().date()
            
            # Obtener horarios
            horarios_query = self.supabase.table("clases_horarios").select(
                "id, capacidad_maxima, clases!inner(empresa_id)"
            ).eq("activo", True)
            
            if empresa_filter:
                horarios_query = horarios_query.in_("clases.empresa_id", empresa_filter)
            
            horarios_result = horarios_query.execute()
            horarios = horarios_result.data or []
            
            if not horarios:
                return 0.0
            
            total_ocupacion = 0
            total_horarios = 0
            
            for horario in horarios:
                # Calcular ocupación de este horario en el período
                reservas = self.supabase.table("clases_reservas").select("id").eq(
                    "horario_id", horario["id"]
                ).gte("fecha_clase", fecha_inicio.isoformat()).lte(
                    "fecha_clase", fecha_fin.isoformat()
                ).neq("estado", "CANCELADA").execute()
                
                num_reservas = len(reservas.data or [])
                dias_periodo = (fecha_fin - fecha_inicio).days + 1
                capacidad_total = horario["capacidad_maxima"] * dias_periodo
                
                if capacidad_total > 0:
                    ocupacion = (num_reservas / capacidad_total) * 100
                    total_ocupacion += ocupacion
                    total_horarios += 1
            
            return round(total_ocupacion / total_horarios, 1) if total_horarios > 0 else 0.0
            
        except Exception as e:
            return 0.0

    def get_ocupacion_detallada(self, fecha_inicio: date, fecha_fin: date, empresa_id: Optional[str] = None) -> pd.DataFrame:
        """Obtiene ocupación detallada por clase y horario"""
        try:
            # Obtener horarios
            query = self.supabase.table("clases_horarios").select("""
                id, dia_semana, hora_inicio, hora_fin, capacidad_maxima,
                clases!inner(id, nombre, categoria, empresa_id)
            """).eq("activo", True).eq("clases.activa", True)
            
            if empresa_id:
                query = query.eq("clases.empresa_id", empresa_id)
            elif self.role == "gestor" and self.empresa_id:
                empresas_gestionadas = self._get_empresas_gestionadas()
                query = query.in_("clases.empresa_id", empresas_gestionadas)
            
            horarios_result = query.execute()
            
            ocupacion_data = []
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            
            for horario in horarios_result.data or []:
                # Contar reservas en el período
                reservas = self.supabase.table("clases_reservas").select("id, estado").eq(
                    "horario_id", horario["id"]
                ).gte("fecha_clase", fecha_inicio.isoformat()).lte(
                    "fecha_clase", fecha_fin.isoformat()
                ).execute()
                
                total_reservas = len(reservas.data or [])
                reservas_activas = len([r for r in (reservas.data or []) if r["estado"] != "CANCELADA"])
                
                # Calcular días del período que coinciden con el día de la semana
                dias_validos = 0
                fecha_actual = fecha_inicio
                while fecha_actual <= fecha_fin:
                    if fecha_actual.weekday() == horario["dia_semana"]:
                        dias_validos += 1
                    fecha_actual += timedelta(days=1)
                
                capacidad_total = horario["capacidad_maxima"] * dias_validos
                porcentaje_ocupacion = (reservas_activas / max(1, capacidad_total)) * 100
                
                ocupacion_info = {
                    "clase_nombre": horario["clases"]["nombre"],
                    "categoria": horario["clases"]["categoria"],
                    "dia_semana": dias_semana[horario["dia_semana"]],
                    "horario": f"{horario['hora_inicio']} - {horario['hora_fin']}",
                    "capacidad_maxima": horario["capacidad_maxima"],
                    "dias_periodo": dias_validos,
                    "capacidad_total": capacidad_total,
                    "reservas_totales": total_reservas,
                    "reservas_activas": reservas_activas,
                    "porcentaje_ocupacion": round(porcentaje_ocupacion, 1)
                }
                ocupacion_data.append(ocupacion_info)
            
            return pd.DataFrame(ocupacion_data)
            
        except Exception as e:
            print(f"Error obteniendo ocupación detallada: {e}")
            return pd.DataFrame()

    # =========================
    # FUNCIONES DE ADMINISTRACIÓN
    # =========================
    
    def get_participantes_por_clase(self, clase_id: str, fecha_inicio: date, fecha_fin: date) -> pd.DataFrame:
        """Obtiene participantes de una clase en un período"""
        try:
            query = self.supabase.table("clases_reservas").select("""
                id, fecha_clase, estado,
                participantes!inner(id, nombre, apellidos, email),
                clases_horarios!inner(dia_semana, hora_inicio, hora_fin)
            """).eq("clases_horarios.clase_id", clase_id).gte(
                "fecha_clase", fecha_inicio.isoformat()
            ).lte("fecha_clase", fecha_fin.isoformat())
            
            result = query.order("fecha_clase", "clases_horarios.hora_inicio").execute()
            
            if result.data:
                participantes = []
                dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                
                for reserva in result.data:
                    participante = reserva["participantes"]
                    horario = reserva["clases_horarios"]
                    
                    participante_info = {
                        "reserva_id": reserva["id"],
                        "fecha_clase": reserva["fecha_clase"],
                        "estado": reserva["estado"],
                        "participante_id": participante["id"],
                        "nombre_completo": f"{participante['nombre']} {participante['apellidos']}",
                        "email": participante["email"],
                        "dia_semana": dias_semana[horario["dia_semana"]],
                        "horario": f"{horario['hora_inicio']} - {horario['hora_fin']}"
                    }
                    participantes.append(participante_info)
                
                return pd.DataFrame(participantes)
            
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Error obteniendo participantes por clase: {e}")
            return pd.DataFrame()

    def exportar_datos_clases(self, fecha_inicio: date, fecha_fin: date, tipo_export: str = "reservas") -> pd.DataFrame:
        """Exporta datos de clases para análisis"""
        try:
            if tipo_export == "reservas":
                # Exportar todas las reservas del período
                query = self.supabase.table("clases_reservas").select("""
                    id, fecha_clase, estado, fecha_reserva,
                    participantes!inner(nombre, apellidos, email),
                    clases_horarios!inner(dia_semana, hora_inicio, hora_fin,
                        clases!inner(nombre, categoria))
                """).gte("fecha_clase", fecha_inicio.isoformat()).lte("fecha_clase", fecha_fin.isoformat())
                
                result = query.execute()
                
                if result.data:
                    export_data = []
                    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                    
                    for reserva in result.data:
                        participante = reserva["participantes"]
                        horario = reserva["clases_horarios"]
                        clase = horario["clases"]
                        
                        row = {
                            "Fecha Clase": reserva["fecha_clase"],
                            "Clase": clase["nombre"],
                            "Categoría": clase["categoria"],
                            "Día Semana": dias_semana[horario["dia_semana"]],
                            "Horario": f"{horario['hora_inicio']} - {horario['hora_fin']}",
                            "Participante": f"{participante['nombre']} {participante['apellidos']}",
                            "Email": participante["email"],
                            "Estado": reserva["estado"],
                            "Fecha Reserva": reserva["fecha_reserva"]
                        }
                        export_data.append(row)
                    
                    return pd.DataFrame(export_data)
            
            elif tipo_export == "ocupacion":
                return self.get_ocupacion_detallada(fecha_inicio, fecha_fin)
            
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Error exportando datos: {e}")
            return pd.DataFrame()

    def get_alertas_sistema(self) -> List[Dict[str, str]]:
        """Obtiene alertas del sistema de clases"""
        try:
            alertas = []
            
            # Clases sin horarios
            clases_sin_horarios = self.supabase.table("clases").select("id, nombre").eq("activa", True).execute()
            
            for clase in clases_sin_horarios.data or []:
                horarios = self.supabase.table("clases_horarios").select("id").eq(
                    "clase_id", clase["id"]
                ).eq("activo", True).execute()
                
                if not horarios.data:
                    alertas.append({
                        "tipo": "WARNING",
                        "mensaje": f"La clase '{clase['nombre']}' no tiene horarios activos"
                    })
            
            # Participantes con suscripción vencida
            fecha_actual = datetime.now().date()
            suscripciones_vencidas = self.supabase.table("participantes_suscripciones").select(
                "participantes!inner(nombre, apellidos)"
            ).eq("activa", True).lt("fecha_vencimiento", fecha_actual.isoformat()).execute()
            
            for sub in suscripciones_vencidas.data or []:
                participante = sub["participantes"]
                alertas.append({
                    "tipo": "INFO",
                    "mensaje": f"Suscripción vencida: {participante['nombre']} {participante['apellidos']}"
                })
            
            # Clases con baja ocupación
            fecha_inicio = datetime.now().date() - timedelta(days=7)
            fecha_fin = datetime.now().date()
            ocupacion = self.get_ocupacion_detallada(fecha_inicio, fecha_fin)
            
            if not ocupacion.empty:
                clases_baja_ocupacion = ocupacion[ocupacion["porcentaje_ocupacion"] < 30]
                for _, clase in clases_baja_ocupacion.iterrows():
                    alertas.append({
                        "tipo": "INFO",
                        "mensaje": f"Baja ocupación en {clase['clase_nombre']} - {clase['dia_semana']}: {clase['porcentaje_ocupacion']}%"
                    })
            
            return alertas[:10]  # Máximo 10 alertas
            
        except Exception as e:
            return [{"tipo": "ERROR", "mensaje": f"Error obteniendo alertas: {e}"}]


def get_clases_service(supabase, session_state) -> ClasesService:
    """Factory function para obtener instancia del servicio de clases"""
    return ClasesService(supabase, session_state)
