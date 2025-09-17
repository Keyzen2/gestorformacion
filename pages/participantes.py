import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, export_csv, get_ajustes_app
from components.listado_con_ficha import listado_con_ficha
from services.data_service import get_data_service
from services.grupos_service import get_grupos_service
import re

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"

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
    st.markdown("## 👨‍🎓 Participantes")
    st.caption("Gestión de participantes y vinculación con empresas y grupos.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return
        
    # Inicializar servicios
    data_service = get_data_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar datos
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            df_participantes = data_service.get_participantes_completos()
            empresas_dict = data_service.get_empresas_dict()
            grupos_dict = grupos_service.get_grupos_dict()
            
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return

    # =========================
    # Métricas básicas
    # =========================
    if not df_participantes.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("👨‍🎓 Total Participantes", len(df_participantes))
        
        with col2:
            con_grupo = len(df_participantes[df_participantes["grupo_id"].notna()])
            st.metric("👥 Con Grupo", con_grupo)
        
        with col3:
            este_mes = len(df_participantes[
                pd.to_datetime(df_participantes["created_at"], errors="coerce").dt.month == datetime.now().month
            ])
            st.metric("🆕 Nuevos este mes", este_mes)
        
        with col4:
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
        query = st.text_input("🔍 Buscar por nombre, email o NIF")
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
    # Definir permisos de creación
    # =========================
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
    )

    # =========================
    # Funciones CRUD para participantes/usuarios
    # =========================
    def crear_participante(datos_nuevos):
        """Crea un participante como usuario con rol 'alumno'."""
        try:
            # Validaciones básicas
            if not datos_nuevos.get("email") or not datos_nuevos.get("nombre"):
                st.error("⚠️ Email y nombre son obligatorios.")
                return False
            
            if not re.match(EMAIL_REGEX, datos_nuevos["email"]):
                st.error("⚠️ Email no válido.")
                return False
            
            if datos_nuevos.get("nif") and not validar_dni_cif(datos_nuevos["nif"]):
                st.error("⚠️ NIF no válido.")
                return False
                
            # Validar NISS
            niss = datos_nuevos.get("niss")
            if niss and not re.match(r'^\d{12}$', niss):
                st.error("⚠️ NISS debe tener exactamente 12 dígitos.")
                return False
                
            # Validar empresa obligatoria para participantes
            empresa_id_part = datos_nuevos.get("empresa_id")
            if not empresa_id_part:
                st.error("⚠️ Los participantes deben tener una empresa asignada.")
                return False

            # Verificar email único
            email_existe_usuarios = supabase.table("usuarios").select("id").eq("email", datos_nuevos["email"]).execute()
            if email_existe_usuarios.data:
                st.error("⚠️ Ya existe un usuario con ese email.")
                return False
            
            email_existe_part = supabase.table("participantes").select("id").eq("email", datos_nuevos["email"]).execute()
            if email_existe_part.data:
                st.error("⚠️ Ya existe un participante con ese email.")
                return False

            # Generar contraseña temporal
            import random, string
            password = "".join(random.choices(string.ascii_letters + string.digits, k=8)) + "!"
            
            # 1. Crear usuario en Auth
            auth_res = supabase.auth.admin.create_user({
                "email": datos_nuevos["email"],
                "password": password,
                "email_confirm": True
            })
            
            if not getattr(auth_res, "user", None):
                st.error("❌ Error al crear usuario en Auth.")
                return False
                
            auth_id = auth_res.user.id

            try:
                # 2. Crear usuario en tabla usuarios
                usuario_datos = {
                    "auth_id": auth_id,
                    "email": datos_nuevos["email"],
                    "nombre_completo": f"{datos_nuevos.get('nombre', '')} {datos_nuevos.get('apellidos', '')}".strip(),
                    "nombre": datos_nuevos.get("nombre", ""),
                    "telefono": datos_nuevos.get("telefono"),
                    "nif": datos_nuevos.get("nif"),
                    "rol": "alumno",
                    "empresa_id": empresa_id_part,
                    "grupo_id": datos_nuevos.get("grupo_id"),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                usuario_res = supabase.table("usuarios").insert(usuario_datos).execute()
                if not usuario_res.data:
                    raise Exception("Error al crear usuario en BD")

                # 3. Crear participante en tabla participantes
                participante_datos = {
                    "email": datos_nuevos["email"],
                    "nombre": datos_nuevos.get("nombre", ""),
                    "apellidos": datos_nuevos.get("apellidos", ""),
                    "nif": datos_nuevos.get("nif"),
                    "telefono": datos_nuevos.get("telefono"),
                    "fecha_nacimiento": datos_nuevos.get("fecha_nacimiento"),
                    "sexo": datos_nuevos.get("sexo"),
                    "tipo_documento": datos_nuevos.get("tipo_documento"),
                    "niss": datos_nuevos.get("niss"), 
                    "empresa_id": empresa_id_part,
                    "grupo_id": datos_nuevos.get("grupo_id"),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                part_res = supabase.table("participantes").insert(participante_datos).execute()
                if not part_res.data:
                    raise Exception("Error al crear participante en BD")
                
                # Limpiar cache
                data_service.get_participantes_completos.clear()
                
                st.success(f"✅ Participante creado correctamente. Contraseña temporal: {password}")
                return True
                
            except Exception as e:
                # Rollback: eliminar usuario de Auth si falla la BD
                try:
                    supabase.auth.admin.delete_user(auth_id)
                except:
                    pass
                st.error(f"❌ Error al crear participante: {e}")
                return False
                
        except Exception as e:
            st.error(f"❌ Error al crear participante: {e}")
            return False

    def actualizar_participante(participante_id, datos_editados):
        """Actualiza un participante existente."""
        try:
            # Validaciones
            if not datos_editados.get("email") or not datos_editados.get("nombre"):
                st.error("⚠️ Email y nombre son obligatorios.")
                return False
            
            if not re.match(EMAIL_REGEX, datos_editados["email"]):
                st.error("⚠️ Email no válido.")
                return False
            
            if datos_editados.get("nif") and not validar_dni_cif(datos_editados["nif"]):
                st.error("⚠️ NIF no válido.")
                return False

            empresa_id_part = datos_editados.get("empresa_id")
            if not empresa_id_part:
                st.error("⚠️ Los participantes deben tener una empresa asignada.")
                return False

            # Preparar datos de actualización
            participante_update = {
                "nombre": datos_editados.get("nombre", ""),
                "apellidos": datos_editados.get("apellidos", ""),
                "email": datos_editados["email"],
                "nif": datos_editados.get("nif"),
                "telefono": datos_editados.get("telefono"),
                "fecha_nacimiento": datos_editados.get("fecha_nacimiento"),
                "sexo": datos_editados.get("sexo"),
                "empresa_id": empresa_id_part,
                "grupo_id": datos_editados.get("grupo_id"),
                "tipo_documento": datos_editados.get("tipo_documento"),
                "niss": datos_editados.get("niss"), 
                "updated_at": datetime.utcnow().isoformat()
            }

            # Actualizar participante
            supabase.table("participantes").update(participante_update).eq("id", participante_id).execute()
            
            # También actualizar en tabla usuarios si existe
            try:
                usuario_update = {
                    "email": datos_editados["email"],
                    "nombre_completo": f"{datos_editados.get('nombre', '')} {datos_editados.get('apellidos', '')}".strip(),
                    "nombre": datos_editados.get("nombre", ""),
                    "telefono": datos_editados.get("telefono"),
                    "nif": datos_editados.get("nif"),
                    "empresa_id": empresa_id_part,
                    "grupo_id": datos_editados.get("grupo_id")
                }
                supabase.table("usuarios").update(usuario_update).eq("email", datos_editados["email"]).execute()
            except:
                pass  # No todos los participantes tienen usuario asociado
            
            # Limpiar cache
            data_service.get_participantes_completos.clear()
            
            st.success("✅ Participante actualizado correctamente.")
            return True
            
        except Exception as e:
            st.error(f"❌ Error al actualizar participante: {e}")
            return False

    def get_campos_dinamicos(datos):
        """Define campos del formulario."""
        campos = ["email", "nombre", "apellidos", "nif", "telefono", "fecha_nacimiento", "sexo" , "tipo_documento", "niss"]
        
        if session_state.role == "admin":
            campos.extend(["empresa_sel", "grupo_sel"])
        else:
            # Gestor: solo puede asignar grupos de su empresa
            campos.append("grupo_sel")
            
        return campos

    # Configuración de campos para listado_con_ficha
    campos_select = {
        "sexo": ["", "M", "F"],
        "tipo_documento": ["", "NIF", "NIE", "Pasaporte"],
        "grupo_sel": [""] + sorted(grupos_dict.keys())
    }
    
    if session_state.role == "admin":
        campos_select["empresa_sel"] = [""] + sorted(empresas_dict.keys())

    campos_obligatorios = ["email", "nombre"]
    campos_readonly = ["created_at", "updated_at"]
    
    campos_help = {
        "email": "Email único del participante (obligatorio)",
        "nombre": "Nombre del participante (obligatorio)", 
        "apellidos": "Apellidos del participante",
        "nif": "NIF/DNI válido (opcional)",
        "telefono": "Teléfono de contacto",
        "fecha_nacimiento": "Fecha de nacimiento",
        "sexo": "Sexo del participante (M/F)",
        "tipo_documento": "Tipo de documento de identidad (obligatorio FUNDAE)",
        "niss": "Número de la Seguridad Social (12 dígitos, obligatorio FUNDAE)",
        "empresa_sel": "Empresa del participante (obligatorio)",
        "grupo_sel": "Grupo formativo asignado"
    }

    # =========================
    # Tabla principal con listado_con_ficha
    # =========================
    st.markdown("### 📊 Listado de Participantes")
    
    if df_filtered.empty:
        st.info("📋 No hay participantes registrados o que coincidan con los filtros.")
    else:
        # Preparar datos para display
        df_display = df_filtered.copy()
        
        # Convertir relaciones a campos de selección
        if "empresa_nombre" in df_display.columns:
            df_display["empresa_sel"] = df_display["empresa_nombre"]
        else:
            df_display["empresa_sel"] = ""
            
        if "grupo_codigo" in df_display.columns:
            df_display["grupo_sel"] = df_display["grupo_codigo"]
        else:
            df_display["grupo_sel"] = ""

        # Columnas visibles
        columnas_visibles = ["nombre", "apellidos", "email", "nif", "telefono"]
        if session_state.role == "admin" and "empresa_nombre" in df_display.columns:
            columnas_visibles.append("empresa_nombre")
        if "grupo_codigo" in df_display.columns:
            columnas_visibles.append("grupo_codigo")

        # Mensaje informativo
        if session_state.role == "gestor":
            st.info("💡 **Información:** Como gestor, solo puedes crear participantes para tu empresa.")
        else:
            st.info("💡 **Información:** Los participantes se crean como usuarios con rol 'alumno' y credenciales de acceso.")

        # Función para convertir selects a IDs
        def preparar_datos_para_guardar(datos):
            # Convertir empresa_sel a empresa_id
            if "empresa_sel" in datos:
                empresa_sel = datos.pop("empresa_sel", "")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos["empresa_id"] = empresas_dict[empresa_sel]
                elif session_state.role == "gestor":
                    datos["empresa_id"] = empresa_id
                else:
                    datos["empresa_id"] = None
            
            # Convertir grupo_sel a grupo_id
            if "grupo_sel" in datos:
                grupo_sel = datos.pop("grupo_sel", "")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos["grupo_id"] = grupos_dict[grupo_sel]
                else:
                    datos["grupo_id"] = None
                    
            return datos

        def guardar_wrapper(participante_id, datos):
            datos = preparar_datos_para_guardar(datos)
            return actualizar_participante(participante_id, datos)
            
        def crear_wrapper(datos):
            datos = preparar_datos_para_guardar(datos)
            return crear_participante(datos)

        # Usar listado_con_ficha
        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Participante",
            on_save=guardar_wrapper,
            on_create=crear_wrapper if puede_crear else None,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            campos_obligatorios=campos_obligatorios,
            allow_creation=puede_crear,
            campos_help=campos_help,
            search_columns=["nombre", "apellidos", "email", "nif"]
        )

    st.divider()

    # =========================
    # GESTIÓN DE DIPLOMAS COMPLETA
    # =========================
    if session_state.role in ["admin", "gestor"]:
        mostrar_seccion_diplomas_completa(supabase, session_state, empresa_id)

    # =========================
    # IMPORTACIÓN MASIVA COMPLETA
    # =========================
    if puede_crear:
        mostrar_importacion_masiva_completa(supabase, session_state, data_service, empresas_dict, grupos_dict, empresa_id)

    # =========================
    # Exportación
    # =========================
    if not df_filtered.empty:
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Exportar a CSV"):
                export_csv(df_filtered, filename="participantes.csv")
        
        with col2:
            st.metric("📋 Registros mostrados", len(df_filtered))

    st.divider()
    st.caption("💡 Los participantes son usuarios con rol 'alumno' que pueden acceder a sus cursos y obtener diplomas.")


def procesar_importacion_masiva(supabase, session_state, df_import, empresas_dict, grupos_dict, empresa_id):
    """Procesa la importación masiva de participantes."""
    import random, string
    
    resultados = {
        "exitosos": 0,
        "errores": 0, 
        "omitidos": 0,
        "detalles_errores": [],
        "contraseñas": []
    }
    
    for index, row in df_import.iterrows():
        try:
            # Validaciones básicas
            if pd.isna(row.get("email")) or pd.isna(row.get("nombre")):
                resultados["omitidos"] += 1
                resultados["detalles_errores"].append(f"Fila {index + 2}: Email o nombre faltante")
                continue
            
            email = str(row["email"]).strip().lower()
            nombre = str(row["nombre"]).strip()
            apellidos = str(row.get("apellidos", "")).strip()
            
            # Validar email
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                resultados["errores"] += 1
                resultados["detalles_errores"].append(f"Fila {index + 2}: Email inválido - {email}")
                continue
            
            # Verificar si ya existe
            existe_usuario = supabase.table("usuarios").select("id").eq("email", email).execute()
            existe_participante = supabase.table("participantes").select("id").eq("email", email).execute()
            
            if existe_usuario.data or existe_participante.data:
                resultados["omitidos"] += 1
                resultados["detalles_errores"].append(f"Fila {index + 2}: Email ya existe - {email}")
                continue
            
            # Determinar empresa
            if session_state.role == "gestor":
                participante_empresa_id = empresa_id
            else:
                # Admin: buscar empresa en archivo
                empresa_nombre = str(row.get("empresa", "")).strip()
                if empresa_nombre and empresa_nombre in empresas_dict:
                    participante_empresa_id = empresas_dict[empresa_nombre]
                else:
                    resultados["errores"] += 1
                    resultados["detalles_errores"].append(f"Fila {index + 2}: Empresa no encontrada - {empresa_nombre}")
                    continue
            
            # Determinar grupo (opcional)
            grupo_id = None
            grupo_nombre = str(row.get("grupo", "")).strip()
            if grupo_nombre and grupo_nombre in grupos_dict:
                grupo_id = grupos_dict[grupo_nombre]
            
            # Generar contraseña
            password = "".join(random.choices(string.ascii_letters + string.digits, k=8)) + "!"
            
            # Crear usuario en Auth
            auth_res = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True
            })
            
            if not getattr(auth_res, "user", None):
                resultados["errores"] += 1
                resultados["detalles_errores"].append(f"Fila {index + 2}: Error en Auth - {email}")
                continue
                
            auth_id = auth_res.user.id

            try:
                # Crear usuario en BD
                usuario_datos = {
                    "auth_id": auth_id,
                    "email": email,
                    "nombre_completo": f"{nombre} {apellidos}".strip(),
                    "nombre": nombre,
                    "telefono": str(row.get("telefono", "")).strip() or None,
                    "nif": str(row.get("nif", "")).strip() or None,
                    "rol": "alumno",
                    "empresa_id": participante_empresa_id,
                    "grupo_id": grupo_id,
                    "created_at": datetime.utcnow().isoformat()
                }
                
                supabase.table("usuarios").insert(usuario_datos).execute()
                
                # Crear participante en BD
                participante_datos = {
                    "email": email,
                    "nombre": nombre,
                    "apellidos": apellidos,
                    "nif": str(row.get("nif", "")).strip() or None,
                    "telefono": str(row.get("telefono", "")).strip() or None,
                    "empresa_id": participante_empresa_id,
                    "grupo_id": grupo_id,
                    "created_at": datetime.utcnow().isoformat()
                }
                
                supabase.table("participantes").insert(participante_datos).execute()
                
                # Registrar éxito
                resultados["exitosos"] += 1
                resultados["contraseñas"].append({
                    "email": email,
                    "nombre": f"{nombre} {apellidos}".strip(),
                    "contraseña": password
                })
                
            except Exception as e:
                # Rollback Auth si falla BD
                try:
                    supabase.auth.admin.delete_user(auth_id)
                except:
                    pass
                    
                resultados["errores"] += 1
                resultados["detalles_errores"].append(f"Fila {index + 2}: Error BD - {email}: {e}")
                
        except Exception as e:
            resultados["errores"] += 1
            resultados["detalles_errores"].append(f"Fila {index + 2}: Error general - {e}")
    
    return resultados


def mostrar_seccion_diplomas_completa(supabase, session_state, empresa_id):
    """Gestión completa de diplomas con filtros y subida de archivos."""
    st.markdown("### 🏅 Gestión de Diplomas")
    st.caption("Subir y gestionar diplomas para participantes de grupos finalizados.")
    
    try:
        # Obtener grupos finalizados con filtro de empresa
        hoy = datetime.now().date()
        
        query_grupos = supabase.table("grupos").select("""
            id, codigo_grupo, fecha_fin, fecha_fin_prevista, empresa_id,
            accion_formativa:acciones_formativas(nombre)
        """)
        
        if session_state.role == "gestor" and empresa_id:
            query_grupos = query_grupos.eq("empresa_id", empresa_id)
        
        grupos_res = query_grupos.execute()
        grupos_data = grupos_res.data or []
        
        # Filtrar grupos finalizados
        grupos_finalizados = []
        for grupo in grupos_data:
            fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
            if fecha_fin:
                try:
                    fecha_fin_dt = pd.to_datetime(fecha_fin, errors='coerce').date()
                    if fecha_fin_dt <= hoy:
                        grupos_finalizados.append(grupo)
                except:
                    continue
        
        if not grupos_finalizados:
            st.info("ℹ️ No hay grupos finalizados disponibles para gestionar diplomas.")
            return

        # Obtener participantes de grupos finalizados
        grupos_finalizados_ids = [g["id"] for g in grupos_finalizados]
        
        query_participantes = supabase.table("participantes").select("""
            id, nombre, apellidos, email, grupo_id, nif
        """).in_("grupo_id", grupos_finalizados_ids)
        
        if session_state.role == "gestor" and empresa_id:
            query_participantes = query_participantes.eq("empresa_id", empresa_id)
        
        participantes_res = query_participantes.execute()
        participantes_finalizados = participantes_res.data or []
        
        if not participantes_finalizados:
            st.info("ℹ️ No hay participantes en grupos finalizados.")
            return

        # Crear diccionario de grupos para mapeo
        grupos_dict_completo = {g["id"]: g for g in grupos_finalizados}
        
        # Obtener diplomas existentes
        participantes_ids = [p["id"] for p in participantes_finalizados]
        diplomas_res = supabase.table("diplomas").select("participante_id, id").in_(
            "participante_id", participantes_ids
        ).execute()
        participantes_con_diploma = {d["participante_id"] for d in diplomas_res.data or []}
        
        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Participantes", len(participantes_finalizados))
        with col2:
            st.metric("📚 Grupos Finalizados", len(grupos_finalizados))
        with col3:
            diplomas_count = len(participantes_con_diploma)
            st.metric("🏅 Diplomas Subidos", diplomas_count)
        with col4:
            pendientes = len(participantes_finalizados) - diplomas_count
            st.metric("⏳ Pendientes", pendientes)

        # FILTROS DE BÚSQUEDA
        st.markdown("#### 🔍 Filtros de Búsqueda")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            buscar_participante = st.text_input(
                "🔍 Buscar participante",
                placeholder="Nombre, email o NIF...",
                key="buscar_diploma_participante"
            )
        
        with col2:
            grupos_opciones = ["Todos"] + [g["codigo_grupo"] for g in grupos_finalizados]
            grupo_filtro = st.selectbox(
                "Filtrar por grupo",
                grupos_opciones,
                key="filtro_grupo_diplomas"
            )
        
        with col3:
            estado_diploma = st.selectbox(
                "Estado diploma",
                ["Todos", "Con diploma", "Sin diploma"],
                key="filtro_estado_diploma"
            )

        # Aplicar filtros
        participantes_filtrados = participantes_finalizados.copy()
        
        # Filtro de búsqueda
        if buscar_participante:
            buscar_lower = buscar_participante.lower()
            participantes_filtrados = [
                p for p in participantes_filtrados 
                if (buscar_lower in p.get("nombre", "").lower() or 
                    buscar_lower in p.get("apellidos", "").lower() or 
                    buscar_lower in p.get("email", "").lower() or
                    buscar_lower in p.get("nif", "").lower())
            ]
        
        # Filtro por grupo
        if grupo_filtro != "Todos":
            grupo_id_filtro = None
            for g in grupos_finalizados:
                if g["codigo_grupo"] == grupo_filtro:
                    grupo_id_filtro = g["id"]
                    break
            if grupo_id_filtro:
                participantes_filtrados = [
                    p for p in participantes_filtrados 
                    if p["grupo_id"] == grupo_id_filtro
                ]
        
        # Filtro por estado de diploma
        if estado_diploma == "Con diploma":
            participantes_filtrados = [
                p for p in participantes_filtrados 
                if p["id"] in participantes_con_diploma
            ]
        elif estado_diploma == "Sin diploma":
            participantes_filtrados = [
                p for p in participantes_filtrados 
                if p["id"] not in participantes_con_diploma
            ]

        st.markdown(f"#### 🎯 Participantes encontrados: {len(participantes_filtrados)}")

        if not participantes_filtrados:
            st.warning("🔍 No se encontraron participantes con los filtros aplicados.")
            return

        # Lista de participantes con paginación
        items_por_pagina = 10
        total_paginas = (len(participantes_filtrados) + items_por_pagina - 1) // items_por_pagina
        
        if total_paginas > 1:
            pagina_actual = st.selectbox(
                "Página",
                range(1, total_paginas + 1),
                key="pagina_diplomas"
            )
            inicio = (pagina_actual - 1) * items_por_pagina
            fin = inicio + items_por_pagina
            participantes_pagina = participantes_filtrados[inicio:fin]
        else:
            participantes_pagina = participantes_filtrados

        # Mostrar participantes
        for i, participante in enumerate(participantes_pagina):
            grupo_info = grupos_dict_completo.get(participante["grupo_id"], {})
            tiene_diploma = participante["id"] in participantes_con_diploma
            
            # Crear expander con información del participante
            accion_nombre = grupo_info.get("accion_formativa", {}).get("nombre", "Sin acción") if grupo_info.get("accion_formativa") else "Sin acción"
            nombre_completo = f"{participante['nombre']} {participante.get('apellidos', '')}".strip()
            
            status_emoji = "✅" if tiene_diploma else "⏳"
            status_text = "Con diploma" if tiene_diploma else "Pendiente"
            
            with st.expander(
                f"{status_emoji} {nombre_completo} - {grupo_info.get('codigo_grupo', 'Sin código')} ({status_text})",
                expanded=False
            ):
                col_info, col_actions = st.columns([2, 1])
                
                with col_info:
                    st.markdown(f"**📧 Email:** {participante['email']}")
                    st.markdown(f"**🆔 NIF:** {participante.get('nif', 'No disponible')}")
                    st.markdown(f"**📚 Grupo:** {grupo_info.get('codigo_grupo', 'Sin código')}")
                    st.markdown(f"**📖 Acción:** {accion_nombre}")
                    
                    fecha_fin = grupo_info.get("fecha_fin") or grupo_info.get("fecha_fin_prevista")
                    if fecha_fin:
                        fecha_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                        st.markdown(f"**📅 Finalizado:** {fecha_str}")
                
                with col_actions:
                    if tiene_diploma:
                        # Mostrar diploma existente
                        diplomas_part = supabase.table("diplomas").select("*").eq(
                            "participante_id", participante["id"]
                        ).execute()
                        
                        if diplomas_part.data:
                            diploma = diplomas_part.data[0]
                            st.markdown("**🏅 Diploma:**")
                            if st.button("👁️ Ver", key=f"ver_diploma_{participante['id']}"):
                                st.markdown(f"[🔗 Abrir diploma]({diploma['url']})")
                            
                            if st.button("🗑️ Eliminar", key=f"delete_diploma_{participante['id']}"):
                                confirmar_key = f"confirm_delete_{participante['id']}"
                                if st.session_state.get(confirmar_key, False):
                                    supabase.table("diplomas").delete().eq("id", diploma["id"]).execute()
                                    st.success("✅ Diploma eliminado.")
                                    st.rerun()
                                else:
                                    st.session_state[confirmar_key] = True
                                    st.warning("⚠️ Confirmar eliminación")
                    else:
                        # Subir diploma mejorado
                        st.markdown("**📤 Subir Diploma**")
                        
                        st.info("📱 **Para móviles:** Asegúrate de que el archivo PDF esté guardado en tu dispositivo")
                        
                        diploma_file = st.file_uploader(
                            "Seleccionar diploma (PDF)",
                            type=["pdf"],
                            key=f"upload_diploma_{participante['id']}",
                            help="Solo archivos PDF, máximo 10MB"
                        )
                        
                        if diploma_file is not None:
                            file_size_mb = diploma_file.size / (1024 * 1024)
                            
                            col_info_file, col_size_file = st.columns(2)
                            with col_info_file:
                                st.success(f"✅ **Archivo:** {diploma_file.name}")
                            with col_size_file:
                                color = "🔴" if file_size_mb > 10 else "🟢"
                                st.write(f"{color} **Tamaño:** {file_size_mb:.2f} MB")
                            
                            if file_size_mb > 10:
                                st.error("❌ Archivo muy grande. Máximo 10MB.")
                            else:
                                if st.button(
                                    f"📤 Subir diploma de {participante['nombre']}", 
                                    key=f"btn_upload_{participante['id']}", 
                                    type="primary",
                                    use_container_width=True
                                ):
                                    try:
                                        with st.spinner("📤 Subiendo diploma..."):
                                            # Validar que el archivo se puede leer
                                            try:
                                                file_bytes = diploma_file.getvalue()
                                                if len(file_bytes) == 0:
                                                    raise ValueError("El archivo está vacío")
                                            except Exception as e:
                                                st.error(f"❌ Error al leer el archivo: {e}")
                                                continue
                                            
                                            # Generar estructura de carpetas organizada
                                            timestamp = int(datetime.now().timestamp())
                                            
                                            # Obtener información del grupo y empresa para estructura de carpetas
                                            grupo_info = grupos_dict_completo.get(participante["grupo_id"], {})
                                            
                                            # Determinar empresa_id del participante
                                            if session_state.role == "gestor" and empresa_id:
                                                participante_empresa_id = empresa_id
                                            else:
                                                # Para admin, obtener empresa del participante
                                                part_empresa = supabase.table("participantes").select("empresa_id").eq("id", participante["id"]).execute()
                                                participante_empresa_id = part_empresa.data[0]["empresa_id"] if part_empresa.data else "sin_empresa"
                                            
                                            # Estructura de carpetas: empresa/grupo/accion/participante
                                            accion_id = grupo_info.get("accion_formativa", {}).get("id", "sin_accion") if grupo_info.get("accion_formativa") else "sin_accion"
                                            grupo_codigo = grupo_info.get("codigo_grupo", f"grupo_{participante['grupo_id']}")
                                            
                                            # Limpiar nombres para nombres de archivo seguros
                                            grupo_codigo_limpio = re.sub(r'[^\w\-_]', '_', grupo_codigo)
                                            participante_nif = participante.get('nif', participante['id'])
                                            participante_nif_limpio = re.sub(r'[^\w\-_]', '_', str(participante_nif))
                                            
                                            filename = f"empresa_{participante_empresa_id}/grupos/{grupo_codigo_limpio}/accion_{accion_id}/diploma_{participante_nif_limpio}_{timestamp}.pdf"
                                            
                                            # Subir a bucket de Supabase
                                            try:
                                                upload_res = supabase.storage.from_("diplomas").upload(
                                                    filename, 
                                                    file_bytes, 
                                                    file_options={
                                                        "content-type": "application/pdf",
                                                        "cache-control": "3600",
                                                        "upsert": "true"
                                                    }
                                                )
                                                
                                                # Verificar si la subida fue exitosa
                                                if hasattr(upload_res, 'error') and upload_res.error:
                                                    raise Exception(f"Error de subida: {upload_res.error}")
                                                elif not upload_res or (hasattr(upload_res, 'data') and not upload_res.data):
                                                    raise Exception("La subida no devolvió datos válidos")
                                                
                                                # Obtener URL pública
                                                try:
                                                    public_url = supabase.storage.from_("diplomas").get_public_url(filename)
                                                    if not public_url:
                                                        raise Exception("No se pudo generar URL pública")
                                                except Exception as url_error:
                                                    raise Exception(f"Error al obtener URL: {url_error}")
                                                
                                                # Guardar en tabla diplomas
                                                try:
                                                    diploma_insert = supabase.table("diplomas").insert({
                                                        "participante_id": participante["id"],
                                                        "grupo_id": participante["grupo_id"],
                                                        "url": public_url,
                                                        "archivo_nombre": diploma_file.name
                                                    }).execute()
                                                    
                                                    if hasattr(diploma_insert, 'error') and diploma_insert.error:
                                                        raise Exception(f"Error al guardar en BD: {diploma_insert.error}")
                                                    elif not diploma_insert.data:
                                                        raise Exception("No se pudieron guardar los datos del diploma")
                                                        
                                                except Exception as db_error:
                                                    # Si falla la BD, intentar eliminar el archivo subido
                                                    try:
                                                        supabase.storage.from_("diplomas").remove([filename])
                                                    except:
                                                        pass
                                                    raise Exception(f"Error de base de datos: {db_error}")
                                                
                                                st.success("✅ Diploma subido correctamente!")
                                                st.balloons()
                                                
                                                # Mostrar link directo
                                                st.markdown(f"🔗 [Ver diploma subido]({public_url})")
                                                
                                                # Recargar página después de 2 segundos
                                                import time
                                                time.sleep(2)
                                                st.rerun()
                                                
                                            except Exception as upload_error:
                                                st.error(f"❌ Error al subir archivo: {upload_error}")
                                                
                                                st.info("""
                                                🔧 **Soluciones:**
                                                - Verifica que el bucket 'diplomas' existe en Supabase
                                                - Asegúrate de que tienes permisos de subida
                                                - Intenta con un archivo más pequeño
                                                - Usa WiFi en lugar de datos móviles
                                                - Contacta al administrador si persiste el error
                                                """)
                                    
                                    except Exception as e:
                                        st.error(f"❌ Error general: {e}")
                        else:
                            st.info("📂 Selecciona un archivo PDF para continuar")
                            
                            # Instrucciones específicas para móviles
                            with st.expander("📱 Ayuda para dispositivos móviles"):
                                st.markdown("""
                                **Si tienes problemas desde móvil:**
                                1. **Asegúrate** de que el PDF está guardado en tu dispositivo
                                2. **Usa Chrome o Safari** (navegadores recomendados)
                                3. **Libera memoria** cerrando otras apps
                                4. **Conecta a WiFi** para mejor velocidad
                                5. **Tamaño máximo:** 10MB por archivo
                                
                                **Alternativa:** Usa un ordenador si continúan los problemas
                                """)
        
        # Estadísticas finales
        if participantes_filtrados:
            st.markdown("#### 📊 Estadísticas")
            total_mostrados = len(participantes_filtrados)
            con_diploma_filtrados = sum(1 for p in participantes_filtrados if p["id"] in participantes_con_diploma)
            sin_diploma_filtrados = total_mostrados - con_diploma_filtrados
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("👥 Mostrados", total_mostrados)
            with col2:
                st.metric("✅ Con diploma", con_diploma_filtrados)
            with col3:
                st.metric("⏳ Sin diploma", sin_diploma_filtrados)
            
            if total_mostrados > 0:
                progreso = (con_diploma_filtrados / total_mostrados) * 100
                st.progress(con_diploma_filtrados / total_mostrados, f"Progreso: {progreso:.1f}%")
        
    except Exception as e:
        st.error(f"❌ Error al cargar gestión de diplomas: {e}")


def mostrar_importacion_masiva_completa(supabase, session_state, data_service, empresas_dict, grupos_dict, empresa_id):
    """Sección de importación masiva completa con todas las funcionalidades."""
    with st.expander("📂 Importación masiva de participantes"):
        st.markdown("Sube un archivo Excel con participantes para crear múltiples registros de una vez.")
        
        # Explicación del proceso
        st.info("""
        💡 **Proceso de importación:**
        1. Los participantes se crean como **usuarios con rol 'alumno'**
        2. Se generan **contraseñas temporales** automáticamente
        3. Se crean registros en **Auth de Supabase** y en las tablas usuarios y participantes
        4. Cada participante puede acceder al panel de alumno
        """)
        
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
        
        if archivo_subido:
            try:
                # Leer archivo
                df_import = pd.read_excel(archivo_subido)
                
                st.markdown("##### 📋 Preview de datos a importar:")
                st.dataframe(df_import.head(), use_container_width=True)
                
                # Validar columnas requeridas
                columnas_requeridas = ["nombre", "apellidos", "email"]
                columnas_faltantes = [col for col in columnas_requeridas if col not in df_import.columns]
                
                if columnas_faltantes:
                    st.error(f"❌ Columnas faltantes: {', '.join(columnas_faltantes)}")
                    return
                
                # Mostrar estadísticas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Total filas", len(df_import))
                with col2:
                    emails_validos = df_import["email"].str.match(r'^[^@]+@[^@]+\.[^@]+$', na=False).sum()
                    st.metric("📧 Emails válidos", emails_validos)
                with col3:
                    emails_duplicados = df_import["email"].duplicated().sum()
                    if emails_duplicados > 0:
                        st.metric("⚠️ Emails duplicados", emails_duplicados)
                    else:
                        st.metric("✅ Sin duplicados", 0)
                
                if st.button("🚀 Procesar importación", type="primary"):
                    with st.spinner("Procesando importación..."):
                        resultados = procesar_importacion_masiva(
                            supabase, session_state, df_import, 
                            empresas_dict, grupos_dict, empresa_id
                        )
                        
                        # Mostrar resultados
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if resultados["exitosos"] > 0:
                                st.success(f"✅ Creados: {resultados['exitosos']}")
                        with col2:
                            if resultados["errores"] > 0:
                                st.error(f"❌ Errores: {resultados['errores']}")
                        with col3:
                            if resultados["omitidos"] > 0:
                                st.warning(f"⚠️ Omitidos: {resultados['omitidos']}")
                        
                        # Mostrar detalles de errores
                        if resultados["detalles_errores"]:
                            with st.expander("Ver detalles de errores"):
                                for error in resultados["detalles_errores"]:
                                    st.error(f"• {error}")
                        
                        # Mostrar contraseñas generadas
                        if resultados["contraseñas"]:
                            with st.expander("📋 Contraseñas generadas", expanded=True):
                                st.warning("⚠️ **IMPORTANTE:** Guarda estas contraseñas y compártelas con los participantes")
                                
                                # Crear DataFrame con credenciales
                                df_credenciales = pd.DataFrame(resultados["contraseñas"])
                                st.dataframe(df_credenciales, use_container_width=True)
                                
                                # Botón para descargar credenciales
                                csv_credenciales = df_credenciales.to_csv(index=False)
                                st.download_button(
                                    "📥 Descargar credenciales CSV",
                                    data=csv_credenciales,
                                    file_name=f"credenciales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                        
                        # Limpiar cache
                        data_service.get_participantes_completos.clear()
                        
            except Exception as e:
                st.error(f"❌ Error al procesar archivo: {e}")
