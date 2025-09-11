import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from services.alumnos import alta_alumno
from utils import validar_dni_cif, export_csv, subir_archivo_supabase
from components.listado_con_ficha import listado_con_ficha

def generar_plantilla_excel(rol):
    """Genera plantilla Excel para importación masiva de participantes."""
    columnas = ["nombre", "email"]
    if rol == "admin":
        columnas += ["grupo", "empresa"]
    columnas += ["apellidos", "dni", "telefono"]
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

    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar datos
    # =========================
    try:
        # Cargar empresas
        if session_state.role == "gestor":
            empresas_res = supabase.table("empresas").select("id,nombre").eq("id", empresa_id).execute()
        else:
            empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
        empresas_opciones = [""] + sorted(empresas_dict.keys())

        # Cargar grupos
        if session_state.role == "gestor":
            grupos_res = supabase.table("grupos").select("id,codigo_grupo").eq("empresa_id", empresa_id).execute()
        else:
            grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in (grupos_res.data or [])}
        grupos_nombre_por_id = {g["id"]: g["codigo_grupo"] for g in (grupos_res.data or [])}
        grupos_opciones = [""] + sorted(grupos_dict.keys())

        # Cargar participantes con información relacionada
        if session_state.role == "gestor":
            part_query = """
                id, nombre, apellidos, email, dni, nif, telefono, fecha_nacimiento, 
                sexo, created_at, updated_at, empresa_id,
                grupo:grupos(id, codigo_grupo),
                empresa:empresas(id, nombre)
            """
            part_res = supabase.table("participantes").select(part_query).eq("empresa_id", empresa_id).execute()
        else:
            part_query = """
                id, nombre, apellidos, email, dni, nif, telefono, fecha_nacimiento, 
                sexo, created_at, updated_at, empresa_id,
                grupo:grupos(id, codigo_grupo),
                empresa:empresas(id, nombre)
            """
            part_res = supabase.table("participantes").select(part_query).execute()

        df_part = pd.DataFrame(part_res.data or [])

        # Aplanar relaciones
        if not df_part.empty:
            if "grupo" in df_part.columns:
                df_part["grupo_codigo"] = df_part["grupo"].apply(
                    lambda x: x.get("codigo_grupo") if isinstance(x, dict) else ""
                )
                df_part["grupo_id"] = df_part["grupo"].apply(
                    lambda x: x.get("id") if isinstance(x, dict) else None
                )
            else:
                df_part["grupo_codigo"] = ""
                df_part["grupo_id"] = None

            if "empresa" in df_part.columns:
                df_part["empresa_nombre"] = df_part["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) else ""
                )
            else:
                df_part["empresa_nombre"] = ""

    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # Métricas rápidas
    # =========================
    if not df_part.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Participantes", len(df_part))
        with col2:
            con_grupo = len(df_part[df_part["grupo_id"].notna()])
            st.metric("🎯 Asignados a Grupo", con_grupo)
        with col3:
            sin_grupo = len(df_part[df_part["grupo_id"].isna()])
            st.metric("⚠️ Sin Grupo", sin_grupo)
        with col4:
            # Calcular participantes con diploma
            try:
                diplomas_res = supabase.table("diplomas").select("participante_id").execute()
                participantes_con_diploma = len(set(d["participante_id"] for d in (diplomas_res.data or [])))
                st.metric("🏅 Con Diplomas", participantes_con_diploma)
            except Exception:
                st.metric("🏅 Con Diplomas", 0)

    st.divider()

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o DNI")
    with col2:
        grupo_filter = st.selectbox(
            "Filtrar por grupo", 
            ["Todos", "Sin grupo"] + list(grupos_dict.keys())
        )

    # Aplicar filtros
    df_filtered = df_part.copy()
    
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["apellidos"].fillna("").str.lower().str.contains(q_lower, na=False) |
            df_filtered["email"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["dni"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if grupo_filter != "Todos":
        if grupo_filter == "Sin grupo":
            df_filtered = df_filtered[df_filtered["grupo_id"].isna()]
        else:
            grupo_id_filtro = grupos_dict.get(grupo_filter)
            df_filtered = df_filtered[df_filtered["grupo_id"] == grupo_id_filtro]

    # Exportar CSV
    if not df_filtered.empty:
        export_csv(df_filtered, filename="participantes.csv")
    
    st.divider()

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_participante(participante_id, datos_editados):
        """Función para guardar cambios en un participante."""
        try:
            # Validaciones
            if not datos_editados.get("nombre") or not datos_editados.get("email"):
                st.error("⚠️ Nombre y email son obligatorios.")
                return
                
            if datos_editados.get("dni") and not validar_dni_cif(datos_editados["dni"]):
                st.error("⚠️ El DNI/NIE/CIF no es válido.")
                return

            # Verificar email único
            existing_email = supabase.table("participantes").select("id").eq("email", datos_editados["email"]).neq("id", participante_id).execute()
            if existing_email.data:
                st.error("⚠️ Ya existe otro participante con ese email.")
                return

            # Convertir grupo_codigo a grupo_id si es necesario
            if "grupo_codigo" in datos_editados and datos_editados["grupo_codigo"]:
                grupo_id = grupos_dict.get(datos_editados["grupo_codigo"])
                datos_editados["grupo_id"] = grupo_id
                del datos_editados["grupo_codigo"]
            elif "grupo_codigo" in datos_editados:
                datos_editados["grupo_id"] = None
                del datos_editados["grupo_codigo"]

            # Convertir empresa_nombre a empresa_id si es necesario
            if "empresa_nombre" in datos_editados and datos_editados["empresa_nombre"]:
                empresa_id_new = empresas_dict.get(datos_editados["empresa_nombre"])
                datos_editados["empresa_id"] = empresa_id_new
                del datos_editados["empresa_nombre"]
            elif "empresa_nombre" in datos_editados:
                del datos_editados["empresa_nombre"]

            # Actualizar participante
            supabase.table("participantes").update(datos_editados).eq("id", participante_id).execute()
            
            st.success("✅ Participante actualizado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al actualizar participante: {e}")

    def crear_participante(datos_nuevos):
        """Función para crear un nuevo participante."""
        try:
            # Validaciones
            if not datos_nuevos.get("nombre") or not datos_nuevos.get("email"):
                st.error("⚠️ Nombre y email son obligatorios.")
                return
                
            if datos_nuevos.get("dni") and not validar_dni_cif(datos_nuevos["dni"]):
                st.error("⚠️ El DNI/NIE/CIF no es válido.")
                return

            # Verificar email único
            existing_email = supabase.table("participantes").select("id").eq("email", datos_nuevos["email"]).execute()
            if existing_email.data:
                st.error("⚠️ Ya existe un participante con ese email.")
                return

            # Asignar empresa según rol
            if session_state.role == "gestor":
                datos_nuevos["empresa_id"] = empresa_id
            elif "empresa_nombre" in datos_nuevos and datos_nuevos["empresa_nombre"]:
                empresa_id_new = empresas_dict.get(datos_nuevos["empresa_nombre"])
                datos_nuevos["empresa_id"] = empresa_id_new
                del datos_nuevos["empresa_nombre"]

            # Convertir grupo_codigo a grupo_id
            if "grupo_codigo" in datos_nuevos and datos_nuevos["grupo_codigo"]:
                grupo_id = grupos_dict.get(datos_nuevos["grupo_codigo"])
                datos_nuevos["grupo_id"] = grupo_id
                del datos_nuevos["grupo_codigo"]

            # Crear participante usando el servicio de alumnos
            alta_alumno(
                supabase,
                email=datos_nuevos["email"],
                password=None,  # Se generará automáticamente
                nombre=datos_nuevos["nombre"],
                dni=datos_nuevos.get("dni"),
                apellidos=datos_nuevos.get("apellidos"),
                telefono=datos_nuevos.get("telefono"),
                empresa_id=datos_nuevos.get("empresa_id"),
                grupo_id=datos_nuevos.get("grupo_id")
            )
            
            st.success("✅ Participante creado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al crear participante: {e}")

    def eliminar_participante(participante_id):
        """Función para eliminar un participante."""
        try:
            # Verificar dependencias
            diplomas_count = supabase.table("diplomas").select("id", count="exact").eq("participante_id", participante_id).execute()
            if diplomas_count.count and diplomas_count.count > 0:
                st.error("⚠️ No se puede eliminar. El participante tiene diplomas asociados.")
                return

            # Eliminar de auth si existe
            try:
                part_data = supabase.table("participantes").select("email").eq("id", participante_id).execute()
                if part_data.data:
                    email = part_data.data[0]["email"]
                    # Buscar usuario en auth
                    users_res = supabase.table("usuarios").select("auth_id").eq("email", email).execute()
                    if users_res.data:
                        auth_id = users_res.data[0]["auth_id"]
                        supabase.auth.admin.delete_user(auth_id)
                        supabase.table("usuarios").delete().eq("auth_id", auth_id).execute()
            except Exception:
                pass  # No importa si falla, puede que no tenga usuario

            # Eliminar participante
            supabase.table("participantes").delete().eq("id", participante_id).execute()
            
            st.success("✅ Participante eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar participante: {e}")

    # =========================
    # Definir campos para formularios
    # =========================
    def get_campos_dinamicos(datos):
        """Define campos visibles según el contexto y rol."""
        campos_base = ["id", "nombre", "apellidos", "email", "dni", "telefono"]
        
        if session_state.role == "admin":
            campos_base.extend(["empresa_nombre", "grupo_codigo"])
        elif session_state.role == "gestor":
            campos_base.append("grupo_codigo")
        
        return campos_base

    # Campos para select
    campos_select = {}
    if session_state.role == "admin":
        campos_select["empresa_nombre"] = empresas_opciones
        campos_select["grupo_codigo"] = grupos_opciones
    elif session_state.role == "gestor":
        campos_select["grupo_codigo"] = grupos_opciones

    # Campos de ayuda
    campos_help = {
        "nombre": "Nombre del participante (obligatorio)",
        "apellidos": "Apellidos del participante",
        "email": "Email único del participante (obligatorio)",
        "dni": "DNI, NIE o CIF del participante",
        "telefono": "Teléfono de contacto",
        "empresa_nombre": "Empresa a la que pertenece",
        "grupo_codigo": "Grupo de formación asignado"
    }

    # Campos obligatorios
    campos_obligatorios = ["nombre", "email"]

    # Columnas visibles en la tabla
    columnas_visibles = ["nombre", "apellidos", "email", "dni", "telefono"]
    if session_state.role == "admin":
        columnas_visibles.extend(["empresa_nombre", "grupo_codigo"])
    elif session_state.role == "gestor":
        columnas_visibles.append("grupo_codigo")

    # =========================
    # Renderizar componente principal
    # =========================
    if df_filtered.empty and query:
        st.warning(f"🔍 No se encontraron participantes que coincidan con '{query}'.")
    elif df_filtered.empty:
        st.info("ℹ️ No hay participantes registrados. Crea el primer participante usando el formulario de abajo.")
    else:
        listado_con_ficha(
            df=df_filtered,
            columnas_visibles=columnas_visibles,
            titulo="Participante",
            on_save=guardar_participante,
            on_create=crear_participante,
            on_delete=eliminar_participante if session_state.role == "admin" else None,
            id_col="id",
            campos_select=campos_select,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=True,
            campos_help=campos_help,
            campos_obligatorios=campos_obligatorios,
            search_columns=["nombre", "apellidos", "email", "dni"]
        )

    # =========================
    # Gestión de diplomas
    # =========================
    if not df_part.empty:
        st.divider()
        st.markdown("### 🏅 Gestión de Diplomas")
        
        # Seleccionar participante para generar diploma
        col1, col2 = st.columns([2, 1])
        
        with col1:
            participante_diploma_query = st.text_input("🔍 Buscar participante para diploma")
            
            df_part_diploma = df_part.copy()
            if participante_diploma_query:
                q_lower = participante_diploma_query.lower()
                df_part_diploma = df_part_diploma[
                    df_part_diploma["nombre"].str.lower().str.contains(q_lower, na=False) |
                    df_part_diploma["apellidos"].fillna("").str.lower().str.contains(q_lower, na=False) |
                    df_part_diploma["dni"].fillna("").str.lower().str.contains(q_lower, na=False)
                ]
            
            if not df_part_diploma.empty:
                participante_diploma_options = df_part_diploma.apply(
                    lambda p: f"{p.get('dni', 'Sin DNI')} - {p['nombre']} {p.get('apellidos', '')}", axis=1
                ).tolist()
                participante_diploma_sel = st.selectbox("Seleccionar participante", participante_diploma_options, key="diploma_part")
                
                participante_diploma_id = df_part_diploma[
                    df_part_diploma.apply(
                        lambda p: f"{p.get('dni', 'Sin DNI')} - {p['nombre']} {p.get('apellidos', '')}", axis=1
                    ) == participante_diploma_sel
                ]["id"].iloc[0]

        with col2:
            st.markdown("**Subir diploma:**")
            diploma_file = st.file_uploader("📄 Archivo del diploma", type=["pdf"], key="diploma_file")
            
            if st.button("📤 Subir Diploma") and diploma_file and participante_diploma_id:
                try:
                    # Subir archivo a Supabase Storage
                    diploma_url = subir_archivo_supabase(supabase, diploma_file.read(), diploma_file.name, "diplomas")
                    
                    if diploma_url:
                        # Crear registro de diploma
                        supabase.table("diplomas").insert({
                            "participante_id": participante_diploma_id,
                            "titulo": f"Diploma - {participante_diploma_sel}",
                            "fecha_expedicion": datetime.now().isoformat(),
                            "url": diploma_url,
                            "estado": "emitido"
                        }).execute()
                        
                        st.success("✅ Diploma subido correctamente.")
                        st.rerun()
                    else:
                        st.error("❌ No se pudo obtener la URL del diploma.")
                except Exception as e:
                    st.error(f"❌ Error al subir diploma: {e}")

        # Lista de diplomas existentes
        try:
            diplomas_res = supabase.table("diplomas").select("""
                id, titulo, fecha_expedicion, estado, url,
                participante:participantes(nombre, apellidos, dni)
            """).execute()
            
            df_diplomas = pd.DataFrame(diplomas_res.data or [])
            
            if not df_diplomas.empty:
                st.markdown("#### 📋 Diplomas Registrados")
                
                # Aplanar información del participante
                df_diplomas["participante_nombre"] = df_diplomas["participante"].apply(
                    lambda x: f"{x.get('nombre', '')} {x.get('apellidos', '')}" if isinstance(x, dict) else ""
                )
                df_diplomas["participante_dni"] = df_diplomas["participante"].apply(
                    lambda x: x.get('dni', '') if isinstance(x, dict) else ""
                )
                
                # Mostrar tabla de diplomas
                for _, diploma in df_diplomas.iterrows():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"📄 {diploma['titulo']} - {diploma['participante_nombre']} ({diploma['participante_dni']})")
                        st.caption(f"Expedido: {diploma['fecha_expedicion'][:10]} | Estado: {diploma['estado']}")
                    
                    with col2:
                        if diploma['url']:
                            st.link_button("🔗 Ver", diploma['url'])
                    
                    with col3:
                        if st.button("🗑️", key=f"delete_diploma_{diploma['id']}"):
                            try:
                                supabase.table("diplomas").delete().eq("id", diploma['id']).execute()
                                st.success("✅ Diploma eliminado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al eliminar diploma: {e}")
        except Exception as e:
          
