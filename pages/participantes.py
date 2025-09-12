import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from utils import validar_dni_cif, export_csv, get_ajustes_app
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def generar_plantilla_excel(rol):
    """Genera plantilla Excel para importación masiva de participantes."""
    columnas = ["nombre", "apellidos", "email", "dni", "telefono"]
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
            # Obtener participantes con consulta directa (ya que el servicio especializado falla)
            query = supabase.table("participantes").select("""
                id, nif, nombre, apellidos, dni, email, telefono, 
                fecha_nacimiento, sexo, created_at, updated_at,
                grupo_id, empresa_id
            """)
            
            if session_state.role == "gestor" and empresa_id:
                query = query.eq("empresa_id", empresa_id)
            
            res = query.order("created_at", desc=True).execute()
            df_participantes = pd.DataFrame(res.data or [])
            
            # Obtener diccionarios de empresas y grupos
            empresas_dict = data_service.get_empresas_dict()
            grupos_dict = data_service.get_grupos_dict()
            
            # Mapear nombres
            if not df_participantes.empty:
                # Mapear empresa_id a nombre
                df_participantes["empresa_nombre"] = df_participantes["empresa_id"].map(
                    {v: k for k, v in empresas_dict.items()}
                ).fillna("Sin empresa")
                
                # Mapear grupo_id a código
                df_participantes["grupo_codigo"] = df_participantes["grupo_id"].map(
                    {v: k for k, v in grupos_dict.items()}
                ).fillna("Sin grupo")
            
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
            df_filtered["dni"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if grupo_filter != "Todos" and not df_filtered.empty:
        grupo_id = grupos_dict.get(grupo_filter)
        df_filtered = df_filtered[df_filtered["grupo_id"] == grupo_id]
    
    if session_state.role == "admin" and 'empresa_filter' in locals() and empresa_filter != "Todas" and not df_filtered.empty:
        empresa_id_filter = empresas_dict.get(empresa_filter)
        df_filtered = df_filtered[df_filtered["empresa_id"] == empresa_id_filter]

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_participante(participante_id, datos_editados):
        """Guarda cambios en un participante."""
        try:
            # Validaciones básicas
            if not datos_editados.get("email"):
                st.error("⚠️ El email es obligatorio.")
                return
                
            if datos_editados.get("dni") and not validar_dni_cif(datos_editados["dni"]):
                st.error("⚠️ DNI/CIF no válido.")
                return
            
            # Convertir selects a IDs
            if "grupo_sel" in datos_editados:
                grupo_sel = datos_editados.pop("grupo_sel")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_editados["grupo_id"] = grupos_dict[grupo_sel]
                else:
                    datos_editados["grupo_id"] = None
                    
            if "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if session_state.role == "admin" and empresa_sel and empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]
                elif session_state.role == "gestor":
                    datos_editados["empresa_id"] = empresa_id
            
            # Actualizar en base de datos
            datos_editados["updated_at"] = datetime.utcnow().isoformat()
            supabase.table("participantes").update(datos_editados).eq("id", participante_id).execute()
            
            st.success("✅ Participante actualizado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al guardar participante: {e}")

    def crear_participante(datos_nuevos):
        """Crea un nuevo participante."""
        try:
            # Validaciones
            if not datos_nuevos.get("email") or not datos_nuevos.get("nombre") or not datos_nuevos.get("apellidos"):
                st.error("⚠️ Nombre, apellidos y email son obligatorios.")
                return
                
            if datos_nuevos.get("dni") and not validar_dni_cif(datos_nuevos["dni"]):
                st.error("⚠️ DNI/CIF no válido.")
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
                    
            if "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel")
                if session_state.role == "admin" and empresa_sel and empresa_sel in empresas_dict:
                    datos_nuevos["empresa_id"] = empresas_dict[empresa_sel]
                elif session_state.role == "gestor":
                    datos_nuevos["empresa_id"] = empresa_id

            # Limpiar campos temporales
            datos_limpios = {k: v for k, v in datos_nuevos.items() 
                           if not k.endswith("_sel") and k != "contraseña" and v}
            
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
    # Campos dinámicos
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos_base = ["nombre", "apellidos", "email", "dni", "telefono", "grupo_sel"]
        
        # Solo admin puede seleccionar empresa
        if session_state.role == "admin":
            campos_base.insert(-1, "empresa_sel")
            
        return campos_base

    # Configuración de campos
    campos_select = {
        "grupo_sel": grupos_opciones,
        "sexo": ["", "M", "F"]
    }
    
    if session_state.role == "admin":
        campos_select["empresa_sel"] = empresas_opciones

    campos_readonly = ["created_at", "updated_at"]

    campos_help = {
        "email": "Email único del participante (obligatorio)",
        "dni": "DNI, NIE o CIF válido (opcional)",
        "grupo_sel": "Grupo al que pertenece el participante",
        "empresa_sel": "Empresa del participante (solo admin)"
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
    )

    if df_filtered.empty:
        if df_participantes.empty:
            st.info("ℹ️ No hay participantes registrados.")
        else:
            st.warning("🔍 No se encontraron participantes que coincidan con los filtros.")
    else:
        # Preparar datos para mostrar
        df_display = df_filtered.copy()
        
        # Añadir campos para selects
        df_display["grupo_sel"] = df_display["grupo_codigo"]
        if session_state.role == "admin":
            df_display["empresa_sel"] = df_display["empresa_nombre"]

        # Columnas a mostrar (verificar que existen)
        columnas_base = ["nombre", "apellidos", "email", "dni", "telefono", "grupo_codigo"]
        if session_state.role == "admin":
            columnas_base.append("empresa_nombre")
        
        columnas_visibles = [col for col in columnas_base if col in df_display.columns]

        # Mostrar tabla
        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Participante",
            on_save=guardar_participante,
            on_create=crear_participante if puede_crear else None,
            on_delete=eliminar_participante if session_state.role == "admin" else None,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=puede_crear,
            campos_help=campos_help,
            campos_obligatorios=["nombre", "apellidos", "email"]
        )

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
                                
                                # Preparar datos
                                datos_participante = {
                                    "nombre": row.get("nombre"),
                                    "apellidos": row.get("apellidos"),
                                    "email": row.get("email"),
                                    "dni": row.get("dni"),
                                    "telefono": row.get("telefono"),
                                    "created_at": datetime.utcnow().isoformat(),
                                    "updated_at": datetime.utcnow().isoformat()
                                }
                                
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
