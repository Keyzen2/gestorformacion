import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import uuid
from typing import Optional, Dict, List, Any

class ProyectosService:
    """Servicio para gestión de proyectos de formación"""
    
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
        self.user_role = session_state.role
        self.user_empresa_id = session_state.user.get("empresa_id")
    
    def can_modify_data(self) -> bool:
        """Verifica si el usuario puede modificar datos"""
        return self.user_role in ["admin", "gestor"]
    
    def can_view_all_projects(self) -> bool:
        """Verifica si puede ver proyectos de todas las empresas"""
        return self.user_role == "admin"
    
    # =========================
    # CRUD PROYECTOS
    # =========================
    
    @st.cache_data(ttl=300)
    def get_proyectos_completos(_self) -> pd.DataFrame:
        """Obtiene proyectos con información completa"""
        try:
            query = _self.supabase.table("proyectos").select("""
                *,
                empresas!inner(nombre, cif)
            """)
            
            # Filtrar por empresa si es gestor
            if _self.user_role == "gestor" and _self.user_empresa_id:
                query = query.eq("empresa_id", _self.user_empresa_id)
            
            result = query.execute()
            
            if not result.data:
                return pd.DataFrame()
            
            # Convertir a DataFrame y aplanar datos de empresa
            df = pd.DataFrame(result.data)
            
            # Aplanar información de empresa
            if 'empresas' in df.columns:
                df['empresa_nombre'] = df['empresas'].apply(lambda x: x.get('nombre', '') if x else '')
                df['empresa_cif'] = df['empresas'].apply(lambda x: x.get('cif', '') if x else '')
                df = df.drop('empresas', axis=1)
            
            # Convertir fechas
            fecha_cols = ['fecha_convocatoria', 'fecha_inicio', 'fecha_ejecucion', 
                         'fecha_fin', 'fecha_justificacion', 'fecha_presentacion_informes']
            for col in fecha_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
            
            # Convertir timestamps
            timestamp_cols = ['created_at', 'updated_at']
            for col in timestamp_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            # Rellenar valores nulos
            df = df.fillna('')
            
            return df
            
        except Exception as e:
            st.error(f"Error al cargar proyectos: {e}")
            return pd.DataFrame()
    
    def crear_proyecto(self, datos_proyecto: Dict[str, Any]) -> bool:
        """Crea un nuevo proyecto"""
        try:
            # Generar ID
            proyecto_id = str(uuid.uuid4())
            datos_proyecto["id"] = proyecto_id
            
            # Asignar empresa según rol
            if self.user_role == "gestor":
                datos_proyecto["empresa_id"] = self.user_empresa_id
            
            # Convertir fechas a strings para serialización JSON
            fecha_campos = ['fecha_convocatoria', 'fecha_inicio', 'fecha_ejecucion', 
                           'fecha_fin', 'fecha_justificacion', 'fecha_presentacion_informes']
            for campo in fecha_campos:
                if datos_proyecto.get(campo):
                    # Convertir date object a string ISO
                    fecha = datos_proyecto[campo]
                    if hasattr(fecha, 'isoformat'):
                        datos_proyecto[campo] = fecha.isoformat()
                    elif isinstance(fecha, str):
                        datos_proyecto[campo] = fecha
                    else:
                        datos_proyecto[campo] = str(fecha)
            
            # Añadir timestamps
            datos_proyecto["created_at"] = datetime.utcnow().isoformat()
            datos_proyecto["updated_at"] = datetime.utcnow().isoformat()
            
            # Validaciones básicas
            if not datos_proyecto.get("nombre"):
                st.error("El nombre del proyecto es obligatorio")
                return False
            
            if not datos_proyecto.get("empresa_id"):
                st.error("Debe asignar una empresa al proyecto")
                return False
            
            # Insertar en base de datos
            result = self.supabase.table("proyectos").insert(datos_proyecto).execute()
            
            if result.data:
                # Limpiar cache
                self.get_proyectos_completos.clear()
                st.success(f"Proyecto '{datos_proyecto['nombre']}' creado correctamente")
                return True
            else:
                st.error("Error al crear el proyecto")
                return False
                
        except Exception as e:
            st.error(f"Error al crear proyecto: {e}")
            return False
    
    def actualizar_proyecto(self, proyecto_id: str, datos_actualizados: Dict[str, Any]) -> bool:
        """Actualiza un proyecto existente"""
        try:
            # Validar permisos
            if not self.can_modify_data():
                st.error("No tienes permisos para modificar proyectos")
                return False
            
            # Convertir fechas a strings para serialización JSON
            fecha_campos = ['fecha_convocatoria', 'fecha_inicio', 'fecha_ejecucion', 
                           'fecha_fin', 'fecha_justificacion', 'fecha_presentacion_informes']
            for campo in fecha_campos:
                if datos_actualizados.get(campo):
                    # Convertir date object a string ISO
                    fecha = datos_actualizados[campo]
                    if hasattr(fecha, 'isoformat'):
                        datos_actualizados[campo] = fecha.isoformat()
                    elif isinstance(fecha, str):
                        datos_actualizados[campo] = fecha
                    else:
                        datos_actualizados[campo] = str(fecha)
            
            # Añadir timestamp de actualización
            datos_actualizados["updated_at"] = datetime.utcnow().isoformat()
            
            # Actualizar en base de datos
            result = self.supabase.table("proyectos").update(datos_actualizados).eq("id", proyecto_id).execute()
            
            if result.data:
                # Limpiar cache
                self.get_proyectos_completos.clear()
                st.success("Proyecto actualizado correctamente")
                return True
            else:
                st.error("Error al actualizar el proyecto")
                return False
                
        except Exception as e:
            st.error(f"Error al actualizar proyecto: {e}")
            return False
    
    def eliminar_proyecto(self, proyecto_id: str) -> bool:
        """Elimina un proyecto"""
        try:
            # Validar permisos
            if self.user_role != "admin":
                st.error("Solo los administradores pueden eliminar proyectos")
                return False
            
            # Eliminar proyecto (cascade eliminará hitos relacionados)
            result = self.supabase.table("proyectos").delete().eq("id", proyecto_id).execute()
            
            if result.data:
                # Limpiar cache
                self.get_proyectos_completos.clear()
                st.success("Proyecto eliminado correctamente")
                return True
            else:
                st.error("Error al eliminar el proyecto")
                return False
                
        except Exception as e:
            st.error(f"Error al eliminar proyecto: {e}")
            return False
    
    # =========================
    # CRUD HITOS
    # =========================
    
    @st.cache_data(ttl=300)
    def get_hitos_proyecto(_self, proyecto_id: str) -> pd.DataFrame:
        """Obtiene hitos de un proyecto específico"""
        try:
            result = _self.supabase.table("proyecto_hitos").select("*").eq("proyecto_id", proyecto_id).order("orden_display").execute()
            
            if not result.data:
                return pd.DataFrame()
            
            df = pd.DataFrame(result.data)
            
            # Convertir fechas
            fecha_cols = ['fecha_inicio', 'fecha_fin']
            for col in fecha_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
            
            return df
            
        except Exception as e:
            st.error(f"Error al cargar hitos: {e}")
            return pd.DataFrame()
    
    def crear_hito(self, datos_hito: Dict[str, Any]) -> bool:
        """Crea un nuevo hito para un proyecto"""
        try:
            if not self.can_modify_data():
                st.error("No tienes permisos para crear hitos")
                return False
            
            # Generar ID
            hito_id = str(uuid.uuid4())
            datos_hito["id"] = hito_id
            datos_hito["created_at"] = datetime.utcnow().isoformat()
            
            # Validaciones
            if not datos_hito.get("nombre_hito"):
                st.error("El nombre del hito es obligatorio")
                return False
            
            if not datos_hito.get("proyecto_id"):
                st.error("Debe especificar el proyecto")
                return False
            
            # Insertar en base de datos
            result = self.supabase.table("proyecto_hitos").insert(datos_hito).execute()
            
            if result.data:
                # Limpiar cache
                self.get_hitos_proyecto.clear()
                st.success(f"Hito '{datos_hito['nombre_hito']}' creado correctamente")
                return True
            else:
                st.error("Error al crear el hito")
                return False
                
        except Exception as e:
            st.error(f"Error al crear hito: {e}")
            return False
    
    # =========================
    # RELACIONES PROYECTO-GRUPOS
    # =========================
    
    @st.cache_data(ttl=300)
    def get_grupos_proyecto(_self, proyecto_id: str) -> pd.DataFrame:
        """Obtiene grupos asignados a un proyecto"""
        try:
            result = _self.supabase.table("proyecto_grupos").select("""
                *,
                grupos!inner(codigo_grupo, modalidad, fecha_inicio, fecha_fin_prevista, estado)
            """).eq("proyecto_id", proyecto_id).execute()
            
            if not result.data:
                return pd.DataFrame()
            
            df = pd.DataFrame(result.data)
            
            # Aplanar información de grupos
            if 'grupos' in df.columns:
                df['grupo_codigo'] = df['grupos'].apply(lambda x: x.get('codigo_grupo', '') if x else '')
                df['grupo_modalidad'] = df['grupos'].apply(lambda x: x.get('modalidad', '') if x else '')
                df['grupo_estado'] = df['grupos'].apply(lambda x: x.get('estado', '') if x else '')
                df['grupo_fecha_inicio'] = df['grupos'].apply(lambda x: x.get('fecha_inicio', '') if x else '')
                df = df.drop('grupos', axis=1)
            
            return df
            
        except Exception as e:
            st.error(f"Error al cargar grupos del proyecto: {e}")
            return pd.DataFrame()
    
    @st.cache_data(ttl=300)
    def get_grupos_disponibles(_self) -> pd.DataFrame:
        """Obtiene grupos disponibles para asignar a proyectos"""
        try:
            query = _self.supabase.table("grupos").select("id, codigo_grupo, modalidad, fecha_inicio, fecha_fin_prevista, estado")
            
            # Filtrar por empresa si es gestor
            if _self.user_role == "gestor" and _self.user_empresa_id:
                # Obtener grupos donde la empresa del usuario esté involucrada
                query = query.eq("empresa_id", _self.user_empresa_id)
            
            result = query.execute()
            
            if not result.data:
                return pd.DataFrame()
            
            df = pd.DataFrame(result.data)
            return df
            
        except Exception as e:
            st.error(f"Error al cargar grupos disponibles: {e}")
            return pd.DataFrame()
    
    def asignar_grupo_proyecto(self, proyecto_id: str, grupo_id: str) -> bool:
        """Asigna un grupo a un proyecto"""
        try:
            if not self.can_modify_data():
                st.error("No tienes permisos para asignar grupos")
                return False
            
            # Verificar si ya está asignado
            existing = self.supabase.table("proyecto_grupos").select("id").eq("proyecto_id", proyecto_id).eq("grupo_id", grupo_id).execute()
            
            if existing.data:
                st.warning("El grupo ya está asignado a este proyecto")
                return False
            
            # Insertar relación
            datos_relacion = {
                "id": str(uuid.uuid4()),
                "proyecto_id": proyecto_id,
                "grupo_id": grupo_id,
                "fecha_asignacion": datetime.utcnow().isoformat()
            }
            
            result = self.supabase.table("proyecto_grupos").insert(datos_relacion).execute()
            
            if result.data:
                # Limpiar cache
                self.get_grupos_proyecto.clear()
                st.success("Grupo asignado correctamente al proyecto")
                return True
            else:
                st.error("Error al asignar el grupo")
                return False
                
        except Exception as e:
            st.error(f"Error al asignar grupo: {e}")
            return False
    
    def desasignar_grupo_proyecto(self, proyecto_id: str, grupo_id: str) -> bool:
        """Desasigna un grupo de un proyecto"""
        try:
            if not self.can_modify_data():
                st.error("No tienes permisos para desasignar grupos")
                return False
            
            result = self.supabase.table("proyecto_grupos").delete().eq("proyecto_id", proyecto_id).eq("grupo_id", grupo_id).execute()
            
            if result.data:
                # Limpiar cache
                self.get_grupos_proyecto.clear()
                st.success("Grupo desasignado correctamente")
                return True
            else:
                st.error("Error al desasignar el grupo")
                return False
                
        except Exception as e:
            st.error(f"Error al desasignar grupo: {e}")
            return False
    
    # =========================
    # MÉTRICAS Y DASHBOARD
    # =========================
    
    def calcular_metricas_dashboard(self, df_proyectos: pd.DataFrame) -> Dict[str, Any]:
        """Calcula métricas para el dashboard"""
        try:
            if df_proyectos.empty:
                return {
                    "total_proyectos": 0,
                    "proyectos_activos": 0,
                    "presupuesto_total": 0,
                    "importe_concedido": 0,
                    "tasa_exito": 0,
                    "proximos_vencimientos": 0
                }
            
            total_proyectos = len(df_proyectos)
            proyectos_activos = len(df_proyectos[df_proyectos['estado_proyecto'] == 'EN_EJECUCION'])
            
            # Presupuestos
            presupuesto_total = df_proyectos['presupuesto_total'].fillna(0).sum()
            importe_concedido = df_proyectos['importe_concedido'].fillna(0).sum()
            
            # Tasa de éxito
            con_estado_subvencion = df_proyectos[df_proyectos['estado_subvencion'].notna() & (df_proyectos['estado_subvencion'] != '')]
            if len(con_estado_subvencion) > 0:
                concedidos = len(con_estado_subvencion[con_estado_subvencion['estado_subvencion'] == 'CONCEDIDA'])
                tasa_exito = (concedidos / len(con_estado_subvencion)) * 100
            else:
                tasa_exito = 0
            
            # Próximos vencimientos (próximos 30 días)
            hoy = datetime.now().date()
            fecha_limite = hoy + timedelta(days=30)
            
            proximos_vencimientos = 0
            for _, proyecto in df_proyectos.iterrows():
                for fecha_col in ['fecha_fin', 'fecha_justificacion', 'fecha_presentacion_informes']:
                    fecha = proyecto.get(fecha_col)
                    if fecha and isinstance(fecha, (datetime, pd.Timestamp)):
                        fecha = fecha.date() if hasattr(fecha, 'date') else fecha
                    if fecha and hoy <= fecha <= fecha_limite:
                        proximos_vencimientos += 1
                        break
            
            return {
                "total_proyectos": total_proyectos,
                "proyectos_activos": proyectos_activos,
                "presupuesto_total": presupuesto_total,
                "importe_concedido": importe_concedido,
                "tasa_exito": tasa_exito,
                "proximos_vencimientos": proximos_vencimientos
            }
            
        except Exception as e:
            st.error(f"Error al calcular métricas: {e}")
            return {}
    
    def filtrar_proyectos(self, df_proyectos: pd.DataFrame, filtros: Dict[str, Any]) -> pd.DataFrame:
        """Aplica filtros a los proyectos"""
        try:
            df_filtrado = df_proyectos.copy()
            
            # Filtro por año
            if filtros.get('año') and filtros['año'] != "Todos":
                df_filtrado = df_filtrado[df_filtrado['year_proyecto'] == filtros['año']]
            
            # Filtro por estado del proyecto
            if filtros.get('estado_proyecto') and filtros['estado_proyecto'] != "Todos":
                df_filtrado = df_filtrado[df_filtrado['estado_proyecto'] == filtros['estado_proyecto']]
            
            # Filtro por estado de subvención
            if filtros.get('estado_subvencion') and filtros['estado_subvencion'] != "Todos":
                df_filtrado = df_filtrado[df_filtrado['estado_subvencion'] == filtros['estado_subvencion']]
            
            # Filtro por tipo de proyecto
            if filtros.get('tipo_proyecto') and filtros['tipo_proyecto'] != "Todos":
                df_filtrado = df_filtrado[df_filtrado['tipo_proyecto'] == filtros['tipo_proyecto']]
            
            # Filtro por texto
            if filtros.get('buscar_texto'):
                texto = filtros['buscar_texto'].lower()
                mask = (
                    df_filtrado['nombre'].str.lower().str.contains(texto, na=False) |
                    df_filtrado['descripcion'].str.lower().str.contains(texto, na=False) |
                    df_filtrado['organismo_responsable'].str.lower().str.contains(texto, na=False)
                )
                df_filtrado = df_filtrado[mask]
            
            return df_filtrado
            
        except Exception as e:
            st.error(f"Error al filtrar proyectos: {e}")
            return df_proyectos


def get_proyectos_service(supabase, session_state) -> ProyectosService:
    """Factory function para obtener instancia del servicio"""
    return ProyectosService(supabase, session_state)
