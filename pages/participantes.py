import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, export_csv, get_ajustes_app
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def generar_plantilla_excel(rol):
    """Genera plantilla Excel para importación masiva de participantes."""
    columnas = ["nombre", "apellidos", "email", "nif", "telefono"]
    if rol == "admin":
        columnas += ["grupo", "empresa"]
    
    df = pd.DataFrame(columns=columnas)
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

def main(supabase, session_state):
    st.markdown("## 🧑‍🎓 Participantes")
    st.caption("Gestión de participantes y vinculación con empresas y grupos.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)
    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar datos
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            # Usar el método corregido del DataService
            df_participantes = data_service.get_participantes_completos()
            
            # Obtener diccionarios de empresas y grupos
            empresas_dict = data_service.get_empresas_dict()
            grupos_dict = data_service.get_grupos_dict()
            
            # Opciones para selects
            empresas_opciones = [""] + sorted(empresas_dict.keys())
            grupos_opciones = [""] + sorted(grupos_dict.keys())
            
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return

    # =========================
    # Métricas básicas
    # =========================
    if not df_participantes.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🧑‍🎓 Total Participantes", len(df_participantes))
        
        with col2:
            con_grupo = len(df_participantes[df_participantes["grupo_id"].notna()])
            st.metric("👥 Con Grupo", con_grupo)
        
        with col3:
            # Nuevos este mes
            este_mes = len(df_participantes[
                pd.to_datetime(df_participantes["created_at"], errors="coerce").dt.month == datetime.now().month
            ])
            st.metric("🆕 Nuevos este mes", este_mes)
        
        with col4:
            # Con datos completos
            completos = len(df_participantes[
                (df_participantes["email"].notna()) & 
                (df_participantes["nombre"].notna()) & 
                (df_participantes["apellidos"].notna())
            ])
            st.metric("✅ Datos Completos", completos)

    st.divider()

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o DNI")
    with col2:
        grupo_filter = st.selectbox("Filtrar por grupo", ["Todos"] + sorted(grupos_dict.keys()))
    with col3:
        if session_state.role == "admin":
            empresa_filter = st.selectbox("Filtrar por empresa", ["Todas"] + sorted(empresas_dict.keys()))

    # Aplicar filtros
    df_filtered = df_participantes.copy()
    
    if query and not df_filtered.empty:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["apellidos"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["email"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["nif"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if grupo_filter != "Todos" and not df_filtered.empty:
        grupo_id = grupos_dict.get(grupo_filter)
        df_filtered = df_filtered[df_filtered["grupo_id"] == grupo_id]
    
    if session_state.role == "admin" and 'empresa_filter' in locals() and empresa_filter != "Todas" and not df_filtered.empty:
        empresa_id_filter = empresas_dict.get(empresa_filter)
        df_filtered = df_filtered[df_filtered["empresa_id"] == empresa_id_filter]

    # =========================
    # Funciones CRUD CORREGIDAS
    # =========================
    def guardar_participante(participante_id, datos_editados):
        """Guarda cambios en un participante - CORREGIDO."""
        try:
            # Validaciones básicas
            if not datos_editados.get("email"):
                st.error("⚠️ El email es obligatorio.")
                return
                
            if datos_editados.get("nif") and not validar_dni_cif(datos_editados["nif"]):
                st.error("⚠️ NIF no válido.")
                return
            
            # Convertir selects a IDs
            if "grupo_sel" in datos_editados:
                grupo_sel = datos_editados.pop("grupo_sel")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_editados["grupo_id"] = grupos_dict[grupo_sel]
                else:
                    datos_editados["grupo_id"] = None
                    
            # Solo para admin: convertir empresa_sel
            if "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if session_state.role == "admin" and empresa_sel and empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]
            
            # Para gestores, asegurar que mantienen su empresa
            if session_state.role == "gestor":
                datos_editados["empresa_id"] = empresa_id
            
            # CORRECCIÓN JSON: Convertir fecha a string ISO si es date object
            if "fecha_nacimiento" in datos_editados:
                fecha = datos_editados["fecha_nacimiento"]
                if hasattr(fecha, 'isoformat'):
                    datos_editados["fecha_nacimiento"] = fecha.isoformat()
                elif fecha:
                    datos_editados["fecha_nacimiento"] = str(fecha)
            
            # CORRECCIÓN JSON: Limpiar valores None y vacíos problemáticos
            datos_limpios = {}
            for key, value in datos_editados.items():
                if value is not None and value != "":
                    # Convertir datetime objects a string
                    if hasattr(value, 'isoformat'):
                        datos_limpios[key] = value.isoformat()
                    else:
                        datos_limpios[key] = value
            
            # Actualizar timestamp
            datos_limpios["updated_at"] = datetime.utcnow().isoformat()
            
            # Actualizar en base de datos
            supabase.table("participantes").update(datos_limpios).eq("id", participante_id).execute()
            
            st.success("✅ Participante actualizado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al guardar participante: {e}")
            # Debug info para desarrollo
            if st.session_state.get("debug_mode"):
                st.error(f"Datos enviados: {list(datos_editados.keys()) if 'datos_editados' in locals() else 'N/A'}")

    def crear_participante(datos_nuevos):
        """Crea un nuevo participante - CORREGIDO.""" 
        try:
            # Validaciones
            if not datos_nuevos.get("email") or not datos_nuevos.get("nombre") or not datos_nuevos.get("apellidos"):
                st.error("⚠️ Nombre, apellidos y email son obligatorios.")
                return
                
            if datos_nuevos.get("nif") and not validar_dni_cif(datos_nuevos["nif"]):
                st.error("⚠️ NIF no válido.")
                return

            # Verificar email único
            email_existe = supabase.table("participantes").select("id").eq("email", datos_nuevos["email"]).execute()
            if email_existe.data:
                st.error("⚠️ Ya existe un participante con ese email.")
                return

            # Convertir selects a IDs
            if "grupo_sel" in datos_nuevos:
                grupo_sel = datos_nuevos.pop("grupo_sel")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_nuevos["grupo_id"] = grupos_dict[grupo_sel]
                    
            # Solo para admin: convertir empresa_sel
            if "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel")
                if session_state.role == "admin" and empresa_sel and empresa_sel in empresas_dict:
                    datos_nuevos["empresa_id"] = empresas_dict[empresa_sel]
            
            # Para gestores, siempre asignar su empresa
            if session_state.role == "gestor":
                datos_nuevos["empresa_id"] = empresa_id

            # CORRECCIÓN JSON: Procesar fecha de nacimiento
            if "fecha_nacimiento" in datos_nuevos:
                fecha = datos_nuevos["fecha_nacimiento"]
                if hasattr(fecha, 'isoformat'):
                    datos_nuevos["fecha_nacimiento"] = fecha.isoformat()
                elif fecha:
                    datos_nuevos["fecha_nacimiento"] = str(fecha)

            # CORRECCIÓN JSON: Limpiar campos temporales y procesar valores
            datos_limpios = {}
            for key, value in datos_nuevos.items():
                # Saltar campos temporales
                if key.endswith("_sel") or key == "contraseña":
                    continue
                # Solo incluir valores no vacíos
                if value is not None and value != "":
                    # Convertir datetime objects a string
                    if hasattr(value, 'isoformat'):
                        datos_limpios[key] = value.isoformat()
                    else:
                        datos_limpios[key] = value
            
            # Añadir timestamps
            datos_limpios["created_at"] = datetime.utcnow().isoformat()
            datos_limpios["updated_at"] = datetime.utcnow().isoformat()

            # Crear participante
            result = supabase.table("participantes").insert(datos_limpios).execute()
            
            if result.data:
                st.success("✅ Participante creado correctamente.")
                st.rerun()
            else:
                st.error("❌ Error al crear el participante.")
                
        except Exception as e:
            st.error(f"❌ Error al crear participante: {e}")
            # Debug info para desarrollo
            if st.session_state.get("debug_mode"):
                st.error(f"Datos procesados: {list(datos_limpios.keys()) if 'datos_limpios' in locals() else 'N/A'}")

    def eliminar_participante(participante_id):
        """Elimina un participante.""" 
        try:
            # Eliminar participante
            supabase.table("participantes").delete().eq("id", participante_id).execute()
            st.success("✅ Participante eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar participante: {e}")

    # =========================
    # Configuración de campos para formulario
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente - ORDEN CORRECTO."""
        # Validar que datos es un diccionario
        if not isinstance(datos, dict):
            datos = {}
            
        # ORDEN SECUENCIAL CORRECTO: Nombre → Apellidos → Email → etc.
        campos_base = [
            "nombre", 
            "apellidos",  # Justo después de nombre para orden correcto
            "email", 
            "nif", 
            "telefono",
            "fecha_nacimiento",
            "sexo",
            "grupo_sel"
        ]
    
        # SOLUCIÓN SIMPLE: Solo admin ve empresa
        # Gestores NO ven campo empresa (se asigna automáticamente)
        if session_state.role == "admin":
            campos_base.append("empresa_sel")
            
        return campos_base

    # Configuración de selects
    campos_select = {
        "grupo_sel": grupos_opciones,
        "sexo": ["", "M", "F"]
    }

    # Solo admin puede seleccionar empresa
    if session_state.role == "admin":
        campos_select["empresa_sel"] = empresas_opciones

    # Campos textarea (vacío pero debe ser diccionario)
    campos_textarea = {}
    
    # Campos file (vacío pero debe ser diccionario)
    campos_file = {}

    # Campos readonly - SIN problemas de empresa
    campos_readonly = ["id", "created_at", "updated_at"]

    # Campos password (debe ser lista)
    campos_password = []

    # Campos de ayuda CORREGIDOS
    campos_help = {
        "nombre": "Nombre del participante (obligatorio)",
        "apellidos": "Apellidos del participante (obligatorio)",
        "email": "Email único del participante (obligatorio)",
        "nif": "NIF/DNI del participante (opcional)",
        "telefono": "Número de teléfono de contacto",
        "fecha_nacimiento": "Fecha de nacimiento (entre 1920 y 2010)",
        "sexo": "Sexo del participante (M/F)",
        "grupo_sel": "Grupo al que pertenece el participante"
    }

    # Solo añadir help de empresa para admin
    if session_state.role == "admin":
        campos_help["empresa_sel"] = "Empresa del participante"

    # Campos obligatorios
    campos_obligatorios = ["nombre", "apellidos", "email"]

    # Campos reactivos
    reactive_fields = {
        # Si cambias el grupo, podrías querer actualizar algo relacionado
        "grupo_sel": []
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
    )

    # Preparar df_display CORREGIDO
    if not df_filtered.empty:
        df_display = df_filtered.copy()
        
        # Convertir valores problemáticos
        for col in df_display.columns:
            if df_display[col].dtype == 'object':
                # Convertir None a string vacío para evitar problemas JSON
                df_display[col] = df_display[col].fillna("")
        
        # Campos de selección
        if "grupo_codigo" in df_display.columns:
            df_display["grupo_sel"] = df_display["grupo_codigo"].fillna("")
        else:
            df_display["grupo_sel"] = ""
            
        # Solo admin necesita empresa_sel
        if session_state.role == "admin":
            if "empresa_nombre" in df_display.columns:
                df_display["empresa_sel"] = df_display["empresa_nombre"].fillna("")
            else:
                df_display["empresa_sel"] = ""
    else:
        df_display = pd.DataFrame(columns=[
            "id", "nombre", "apellidos", "email", "nif", "telefono", "grupo_codigo",
            "empresa_nombre"
        ])

    # Columnas visibles según rol
    columnas_base = ["nombre", "apellidos", "email", "nif", "telefono"]
    
    # Añadir columnas adicionales si existen en el dataframe
    if not df_display.empty:
        if "grupo_codigo" in df_display.columns:
            columnas_base.append("grupo_codigo")
        if session_state.role == "admin" and "empresa_nombre" in df_display.columns:
            columnas_base.append("empresa_nombre")
    
    columnas_visibles = [col for col in columnas_base if col in df_display.columns]

    # Llamada con parámetros validados y manejo de errores
    try:
        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Participante",
            on_save=guardar_participante,
            on_create=crear_participante if puede_crear else None,
            on_delete=eliminar_participante if session_state.role == "admin" else None,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_file=campos_file,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            campos_password=campos_password,
            allow_creation=puede_crear,
            campos_help=campos_help,
            campos_obligatorios=campos_obligatorios,
            reactive_fields=reactive_fields,
            search_columns=["nombre", "apellidos", "email", "nif"]
        )
    except Exception as e:
        st.error(f"❌ Error al mostrar listado: {e}")
        st.error("Detalles técnicos para debugging:")
        st.code(f"""
        df_display shape: {df_display.shape if not df_display.empty else 'Empty'}
        columnas_visibles: {columnas_visibles}
        campos_select: {type(campos_select)} - {list(campos_select.keys())}
        campos_help: {type(campos_help)} - {len(campos_help)} items
        campos_obligatorios: {type(campos_obligatorios)} - {campos_obligatorios}
        """)

    # =========================
    # Exportación
    # =========================
    if not df_filtered.empty:
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Exportar a CSV"):
                export_csv(df_filtered[columnas_visibles], filename="participantes.csv")
        
        with col2:
            st.metric("📋 Registros mostrados", len(df_filtered))

    # =========================
    # Importación masiva
    # =========================
    if puede_crear:
        st.divider()
        with st.expander("📂 Importación masiva de participantes"):
            st.markdown("Sube un archivo Excel con participantes para crear múltiples registros de una vez.")
            
            col1, col2 = st.columns(2)
            with col1:
                plantilla = generar_plantilla_excel(session_state.role)
                st.download_button(
                    "📥 Descargar plantilla Excel",
                    data=plantilla.getvalue(),
                    file_name="plantilla_participantes.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col2:
                archivo_subido = st.file_uploader(
                    "Subir archivo Excel",
                    type=['xlsx', 'xls'],
                    help="El archivo debe seguir el formato de la plantilla"
                )
            
            if archivo_subido and st.button("🚀 Procesar importación"):
                try:
                    df_import = pd.read_excel(archivo_subido)
                    
                    if df_import.empty:
                        st.warning("⚠️ El archivo está vacío.")
                    else:
                        creados = 0
                        errores = []
                        
                        progress_bar = st.progress(0)
                        
                        for i, row in df_import.iterrows():
                            try:
                                progress_bar.progress((i + 1) / len(df_import))
                                
                                # Preparar datos con conversión de fecha
                                datos_participante = {
                                    "nombre": row.get("nombre"),
                                    "apellidos": row.get("apellidos"),
                                    "email": row.get("email"),
                                    "nif": row.get("nif"),
                                    "telefono": row.get("telefono"),
                                    "created_at": datetime.utcnow().isoformat(),
                                    "updated_at": datetime.utcnow().isoformat()
                                }
                                
                                # Procesar fecha de nacimiento si existe
                                if row.get("fecha_nacimiento"):
                                    try:
                                        if isinstance(row["fecha_nacimiento"], str):
                                            fecha_obj = pd.to_datetime(row["fecha_nacimiento"]).date()
                                        else:
                                            fecha_obj = row["fecha_nacimiento"]
                                        datos_participante["fecha_nacimiento"] = fecha_obj.isoformat() if hasattr(fecha_obj, 'isoformat') else str(fecha_obj)
                                    except:
                                        pass  # Ignorar fecha inválida
                                
                                # Asignar empresa y grupo
                                if session_state.role == "admin":
                                    if row.get("empresa"):
                                        datos_participante["empresa_id"] = empresas_dict.get(row["empresa"])
                                    if row.get("grupo"):
                                        datos_participante["grupo_id"] = grupos_dict.get(row["grupo"])
                                else:
                                    datos_participante["empresa_id"] = empresa_id
                                    if row.get("grupo"):
                                        datos_participante["grupo_id"] = grupos_dict.get(row["grupo"])
                                
                                # Validar datos básicos
                                if not datos_participante.get("nombre") or not datos_participante.get("email"):
                                    errores.append(f"Fila {i+1}: Faltan nombre o email")
                                    continue
                                
                                # Crear participante
                                result = supabase.table("participantes").insert(datos_participante).execute()
                                if result.data:
                                    creados += 1
                                else:
                                    errores.append(f"Fila {i+1}: Error al crear")
                                    
                            except Exception as e:
                                errores.append(f"Fila {i+1}: {str(e)}")
                        
                        progress_bar.empty()
                        
                        if creados > 0:
                            st.success(f"✅ Se crearon {creados} participantes correctamente.")
                            st.rerun()
                        
                        if errores:
                            st.error(f"❌ Errores en {len(errores)} registros:")
                            for error in errores[:5]:  # Mostrar solo los primeros 5
                                st.text(f"  • {error}")
                            if len(errores) > 5:
                                st.text(f"  • ... y {len(errores)-5} errores más")
                                
                except Exception as e:
                    st.error(f"❌ Error al procesar archivo: {e}")

    st.divider()
    st.caption("Los participantes son los alumnos que realizan la formacion en los grupos.")
