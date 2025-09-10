import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from services.alumnos import alta_alumno
from utils import is_module_active, validar_dni_cif, export_csv, subir_archivo_supabase
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
        st.error(f"⚠️ Error al cargar datos: {e}")
        return

    # =========================
    # Métricas
    # =========================
    if not df_part.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🧑‍🎓 Total Participantes", len(df_part))
        
        with col2:
            # Participantes con grupo asignado
            con_grupo = len(df_part[df_part["grupo_id"].notna()])
            st.metric("👥 Con Grupo", con_grupo)
        
        with col3:
            # Participantes registrados este mes
            if "created_at" in df_part.columns:
                este_mes = df_part[
                    pd.to_datetime(df_part["created_at"], errors="coerce").dt.month == datetime.now().month
                ]
                st.metric("🆕 Nuevos este mes", len(este_mes))
            else:
                st.metric("🆕 Nuevos este mes", 0)
        
        with col4:
            # Diplomas disponibles
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

            # Procesar grupo si cambió
            if "grupo_sel" in datos_editados:
                grupo_sel = datos_editados.pop("grupo_sel")
                if grupo_sel:
                    datos_editados["grupo_id"] = grupos_dict.get(grupo_sel)
                else:
                    datos_editados["grupo_id"] = None

            # Procesar empresa si cambió (solo admin)
            if "empresa_sel" in datos_editados and session_state.role == "admin":
                empresa_sel = datos_editados.pop("empresa_sel")
                if empresa_sel:
                    datos_editados["empresa_id"] = empresas_dict.get(empresa_sel)

            # Sincronizar con usuarios si cambió el email
            participante_actual = df_part[df_part["id"] == participante_id].iloc[0]
            if datos_editados["email"] != participante_actual["email"]:
                usuario_res = supabase.table("usuarios").select("auth_id").eq("email", participante_actual["email"]).execute()
                if usuario_res.data:
                    auth_id = usuario_res.data[0]["auth_id"]
                    supabase.auth.admin.update_user_by_id(auth_id, {"email": datos_editados["email"]})
                    supabase.table("usuarios").update({"email": datos_editados["email"]}).eq("auth_id", auth_id).execute()

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

            # Procesar empresa y grupo
            empresa_id_new = None
            grupo_id_new = None
            
            if session_state.role == "admin":
                if datos_nuevos.get("empresa_sel"):
                    empresa_id_new = empresas_dict.get(datos_nuevos.pop("empresa_sel"))
                if datos_nuevos.get("grupo_sel"):
                    grupo_id_new = grupos_dict.get(datos_nuevos.pop("grupo_sel"))
            else:
                empresa_id_new = empresa_id
                if datos_nuevos.get("grupo_sel"):
                    grupo_id_new = grupos_dict.get(datos_nuevos.pop("grupo_sel"))

            if not empresa_id_new:
                st.error("⚠️ Debes seleccionar una empresa.")
                return
            if not grupo_id_new:
                st.error("⚠️ Debes seleccionar un grupo.")
                return

            # Usar la función alta_alumno existente
            creado = alta_alumno(
                supabase,
                email=datos_nuevos["email"],
                password=datos_nuevos.get("contraseña"),  # Si viene del formulario
                nombre=datos_nuevos["nombre"],
                dni=datos_nuevos.get("dni"),
                apellidos=datos_nuevos.get("apellidos"),
                telefono=datos_nuevos.get("telefono"),
                empresa_id=empresa_id_new,
                grupo_id=grupo_id_new
            )
            
            if creado:
                st.success("✅ Participante creado correctamente.")
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error al crear participante: {e}")

    # =========================
    # Campos dinámicos
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos_base = ["nombre", "apellidos", "email", "dni", "telefono", "grupo_sel"]
        
        # Solo admin puede seleccionar empresa
        if session_state.role == "admin":
            campos_base.insert(-1, "empresa_sel")
            
        # Para formulario de creación, añadir contraseña
        if not datos or not datos.get("id"):
            campos_base.append("contraseña")
            
        return campos_base

    # Configuración de campos
    campos_select = {
        "grupo_sel": grupos_opciones,
        "sexo": ["", "M", "F"]
    }
    
    if session_state.role == "admin":
        campos_select["empresa_sel"] = empresas_opciones

    campos_password = ["contraseña"]
    campos_readonly = ["created_at", "updated_at"]

    campos_help = {
        "email": "Email único del participante (obligatorio)",
        "dni": "DNI, NIE o CIF válido (opcional)",
        "grupo_sel": "Grupo al que pertenece el participante",
        "empresa_sel": "Empresa del participante (solo admin)",
        "contraseña": "Contraseña para acceso (se genera automáticamente si se deja vacío)"
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
    )

    if df_filtered.empty:
        if df_part.empty:
            st.info("ℹ️ No hay participantes registrados.")
        else:
            st.warning(f"🔍 No se encontraron participantes que coincidan con los filtros.")
    else:
        # Preparar datos para mostrar
        df_display = df_filtered.copy()
        
        # Añadir campos para selects
        df_display["grupo_sel"] = df_display["grupo_codigo"]
        if session_state.role == "admin":
            df_display["empresa_sel"] = df_display["empresa_nombre"]

        # Mostrar tabla interactiva
        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "id", "nombre", "apellidos", "email", "dni", 
                "telefono", "grupo_codigo", "empresa_nombre", "created_at"
            ],
            titulo="Participante",
            on_save=guardar_participante,
            on_create=crear_participante if puede_crear else None,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            campos_password=campos_password,
            allow_creation=puede_crear,
            campos_help=campos_help
        )

    st.divider()

    # =========================
    # FUNCIONALIDADES ADICIONALES PRESERVADAS
    # =========================
    
    # Gestión de diplomas (preservado del código original)
    if not df_part.empty and session_state.role in ["admin", "gestor"]:
        st.markdown("### 🏅 Gestión de Diplomas")
        
        # Selector de participante para gestión de diplomas
        participante_options = df_part.apply(
            lambda p: f"{p['nombre']} {p.get('apellidos', '')} ({p['email']})", axis=1
        ).tolist()
        
        if participante_options:
            participante_sel = st.selectbox(
                "Seleccionar participante para gestión de diplomas",
                participante_options
            )
            
            participante_idx = participante_options.index(participante_sel)
            participante_data = df_part.iloc[participante_idx]
            
            with st.expander(f"🏅 Diplomas de {participante_data['nombre']}"):
                # Mostrar diplomas existentes
                try:
                    diplomas_res = supabase.table("diplomas").select("*").eq("participante_id", participante_data["id"]).execute()
                    diplomas = diplomas_res.data or []
                    
                    if diplomas:
                        st.markdown("#### 📄 Diplomas existentes:")
                        for d in diplomas:
                            grupo_nombre = grupos_nombre_por_id.get(d["grupo_id"], "Grupo desconocido")
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"- 📄 [Diploma]({d['url']}) ({grupo_nombre}, {d.get('fecha_subida', '')})")
                            with col2:
                                if st.button("🗑️", key=f"delete_diploma_{d['id']}"):
                                    supabase.table("diplomas").delete().eq("id", d["id"]).execute()
                                    st.success("✅ Diploma eliminado.")
                                    st.rerun()
                    else:
                        st.info("Este participante no tiene diplomas registrados.")
                        
                except Exception as e:
                    st.error(f"❌ Error al cargar diplomas: {e}")

                # Subida de nuevo diploma
                st.markdown("#### 📤 Subir nuevo diploma")
                diploma_file = st.file_uploader(
                    "Seleccionar archivo de diploma (PDF)",
                    type=["pdf"],
                    key=f"diploma_uploader_{participante_data['id']}"
                )
                
                if diploma_file and st.button("📤 Subir diploma"):
                    try:
                        url = subir_archivo_supabase(
                            supabase,
                            diploma_file,
                            empresa_id=session_state.user.get("empresa_id"),
                            bucket="diplomas"
                        )
                        if url:
                            supabase.table("diplomas").insert({
                                "participante_id": participante_data["id"],
                                "grupo_id": participante_data["grupo_id"],
                                "url": url,
                                "fecha_subida": datetime.today().isoformat(),
                                "archivo_nombre": diploma_file.name
                            }).execute()
                            st.success("✅ Diploma subido correctamente.")
                            st.rerun()
                        else:
                            st.error("❌ No se pudo obtener la URL del diploma.")
                    except Exception as e:
                        st.error(f"❌ Error al subir diploma: {e}")

    # Importación masiva desde Excel (preservado)
    if puede_crear:
        st.divider()
        st.markdown("### 📤 Importación Masiva desde Excel")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("#### 📁 Subir archivo Excel")
            archivo_excel = st.file_uploader(
                "Archivo Excel con participantes (.xlsx)",
                type=["xlsx"],
                help="El archivo debe contener las columnas: nombre, email, apellidos, dni, telefono"
            )
            
        with col2:
            st.markdown("#### 📥 Descargar plantilla")
            plantilla = generar_plantilla_excel(session_state.role)
            st.download_button(
                "📥 Descargar plantilla Excel",
                data=plantilla.getvalue(),
                file_name="plantilla_participantes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        if archivo_excel:
            try:
                df_import = pd.read_excel(archivo_excel)
                st.markdown("#### 👀 Vista previa del archivo:")
                st.dataframe(df_import.head())
                
                if st.button("📥 Procesar importación masiva"):
                    errores = []
                    creados = 0
                    
                    for _, row in df_import.iterrows():
                        try:
                            # Validaciones básicas
                            if not row.get("nombre") or not row.get("email"):
                                errores.append(f"Fila {row.name + 2}: Nombre y email son obligatorios")
                                continue
                                
                            if row.get("dni") and not validar_dni_cif(str(row["dni"])):
                                errores.append(f"Fila {row.name + 2}: DNI inválido")
                                continue

                            # Determinar empresa y grupo
                            if session_state.role == "admin":
                                empresa_id_import = empresas_dict.get(row.get("empresa")) if row.get("empresa") else None
                                grupo_id_import = grupos_dict.get(row.get("grupo")) if row.get("grupo") else None
                            else:
                                empresa_id_import = empresa_id
                                grupo_id_import = grupos_dict.get(row.get("grupo")) if row.get("grupo") else None

                            if not empresa_id_import or not grupo_id_import:
                                errores.append(f"Fila {row.name + 2}: Empresa o grupo no válidos")
                                continue

                            # Crear participante
                            alta_alumno(
                                supabase,
                                email=row["email"],
                                password=None,
                                nombre=row["nombre"],
                                dni=str(row.get("dni", "")) if row.get("dni") else None,
                                apellidos=str(row.get("apellidos", "")) if row.get("apellidos") else None,
                                telefono=str(row.get("telefono", "")) if row.get("telefono") else None,
                                empresa_id=empresa_id_import,
                                grupo_id=grupo_id_import
                            )
                            creados += 1
                            
                        except Exception as e:
                            errores.append(f"Fila {row.name + 2}: {str(e)}")

                    # Mostrar resultados
                    if creados > 0:
                        st.success(f"✅ Se crearon {creados} participantes correctamente.")
                    
                    if errores:
                        st.warning("⚠️ Errores encontrados:")
                        for error in errores[:10]:  # Mostrar solo los primeros 10
                            st.caption(f"• {error}")
                        if len(errores) > 10:
                            st.caption(f"... y {len(errores) - 10} errores más")
                    
                    if creados > 0:
                        st.rerun()
                        
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo: {e}")

    st.divider()
    st.caption("💡 Los participantes son usuarios que pertenecen a grupos formativos y pueden obtener diplomas al completar los cursos.")
