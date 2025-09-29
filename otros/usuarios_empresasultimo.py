import streamlit as st
import pandas as pd
import re
from datetime import datetime
from utils import validar_dni_cif, validar_email, export_csv, export_excel, generar_password_segura, get_ajustes_app
from components.listado_con_ficha import listado_con_ficha, validar_campos_obligatorios
from services.data_service import get_data_service

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"

def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios")
    st.caption("Consulta, creación y edición de usuarios registrados en la plataforma.")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    # =========================
    # Cargar datos con DataService
    # =========================
    data_service = get_data_service(supabase, session_state)
    
    try:
        # Usar el método get_usuarios del DataService
        df_usuarios = data_service.get_usuarios(include_empresa=True)

        # Obtener empresas y grupos para los selects
        empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data or []}
        empresas_opciones = [""] + sorted(empresas_dict.keys())

        grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data or []}
        grupos_opciones = [""] + sorted(grupos_dict.keys())

    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # Métricas rápidas
    # =========================
    if not df_usuarios.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Usuarios", len(df_usuarios))
        with col2:
            admin_count = len(df_usuarios[df_usuarios['rol'] == 'admin']) if 'rol' in df_usuarios.columns else 0
            st.metric("🔧 Administradores", admin_count)
        with col3:
            gestor_count = len(df_usuarios[df_usuarios['rol'] == 'gestor']) if 'rol' in df_usuarios.columns else 0
            st.metric("👨‍💼 Gestores", gestor_count)
        with col4:
            alumno_count = len(df_usuarios[df_usuarios['rol'] == 'alumno']) if 'rol' in df_usuarios.columns else 0
            st.metric("🎓 Alumnos", alumno_count)

    if df_usuarios.empty:
        st.info("ℹ️ No hay usuarios registrados.")
        return

    # =========================
    # Filtros de búsqueda
    # =========================
    st.divider()
    st.markdown("### 🔍 Buscar y filtrar")
    
    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o teléfono")
    with col2:
        rol_filter = st.selectbox("Filtrar por rol", ["Todos", "admin", "gestor", "alumno"])

    # Aplicar filtros
    df_filtered = df_usuarios.copy()
    
    if query:
        q_lower = query.lower()
        search_cols = []
        
        # Verificar qué columnas existen para búsqueda (usando columnas reales)
        for col in ["nombre", "nombre_completo", "email", "telefono"]:
            if col in df_filtered.columns:
                search_cols.append(df_filtered[col].fillna("").str.lower().str.contains(q_lower, na=False))
        
        if search_cols:
            # Combinar todas las búsquedas con OR
            search_mask = search_cols[0]
            for mask in search_cols[1:]:
                search_mask = search_mask | mask
            df_filtered = df_filtered[search_mask]
    
    if rol_filter != "Todos" and "rol" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["rol"] == rol_filter]

    # Exportación
    if not df_filtered.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Descargar CSV"):
                csv_data = df_filtered.to_csv(index=False)
                st.download_button(
                    "💾 Descargar CSV",
                    data=csv_data,
                    file_name=f"usuarios_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("📥 Descargar Excel"):
                try:
                    from io import BytesIO
                    buffer = BytesIO()
                    df_filtered.to_excel(buffer, index=False)
                    buffer.seek(0)
                    st.download_button(
                        "💾 Descargar Excel",
                        data=buffer.getvalue(),
                        file_name=f"usuarios_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except ImportError:
                    st.error("📦 Para exportar a Excel, instala openpyxl: pip install openpyxl")

    st.divider()

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_usuario(usuario_id, datos_editados):
        """Función para guardar cambios en un usuario."""
        try:
            # Validaciones
            if not datos_editados.get("email"):
                st.error("⚠️ El email es obligatorio.")
                return
            
            if not re.match(EMAIL_REGEX, datos_editados["email"]):
                st.error("⚠️ Email no válido.")
                return
            
            # Usar 'nif' en lugar de 'dni'
            if datos_editados.get("nif") and not validar_dni_cif(datos_editados["nif"]):
                st.error("⚠️ NIF/CIF no válido.")
                return
                
            # VALIDACIÓN: Verificar empresa obligatoria para gestor y alumno
            if datos_editados.get("rol") in ["gestor", "alumno"]:
                empresa_sel = datos_editados.get("empresa_sel", "")
                if not empresa_sel or empresa_sel not in empresas_dict:
                    st.error(f"⚠️ Los usuarios con rol '{datos_editados.get('rol')}' deben tener una empresa asignada.")
                    return

            # Convertir selects a IDs
            if "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]
                else:
                    datos_editados["empresa_id"] = None

            if "grupo_sel" in datos_editados:
                grupo_sel = datos_editados.pop("grupo_sel")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_editados["grupo_id"] = grupos_dict[grupo_sel]
                else:
                    datos_editados["grupo_id"] = None

            # Actualizar usuario
            supabase.table("usuarios").update(datos_editados).eq("id", usuario_id).execute()
            
            # Limpiar cache del DataService
            data_service.get_usuarios.clear()
            
            st.success("✅ Usuario actualizado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar usuario: {e}")

    def crear_usuario(datos_nuevos):
        """Función para crear un nuevo usuario."""
        try:
            # Validaciones
            if not datos_nuevos.get("email"):
                st.error("⚠️ El email es obligatorio.")
                return
            
            if not datos_nuevos.get("nombre_completo"):
                st.error("⚠️ El nombre completo es obligatorio.")
                return
            
            if not re.match(EMAIL_REGEX, datos_nuevos["email"]):
                st.error("⚠️ Email no válido.")
                return
            
            # Usar 'nif' en lugar de 'dni'
            if datos_nuevos.get("nif") and not validar_dni_cif(datos_nuevos["nif"]):
                st.error("⚠️ NIF/CIF no válido.")
                return

            # VALIDACIÓN: Verificar empresa obligatoria para gestor y alumno
            if datos_nuevos.get("rol") in ["gestor", "alumno"]:
                empresa_sel = datos_nuevos.get("empresa_sel", "")
                if not empresa_sel or empresa_sel not in empresas_dict:
                    st.error(f"⚠️ Los usuarios con rol '{datos_nuevos.get('rol')}' deben tener una empresa asignada.")
                    return

            # Verificar email único
            email_existe = supabase.table("usuarios").select("id").eq("email", datos_nuevos["email"]).execute()
            if email_existe.data:
                st.error("⚠️ Ya existe un usuario con ese email.")
                return

            # Convertir selects a IDs
            empresa_id = None
            if "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel")
                if empresa_sel and empresa_sel in empresas_dict:
                    empresa_id = empresas_dict[empresa_sel]

            grupo_id = None
            if "grupo_sel" in datos_nuevos:
                grupo_sel = datos_nuevos.pop("grupo_sel")
                if grupo_sel and grupo_sel in grupos_dict:
                    grupo_id = grupos_dict[grupo_sel]

            # Generar contraseña temporal si no se proporciona
            password = datos_nuevos.get("password", "TempPass123!")
            
            # Crear usuario en Auth primero
            auth_res = supabase.auth.admin.create_user({
                "email": datos_nuevos["email"],
                "password": password,
                "email_confirm": True
            })
            
            if not getattr(auth_res, "user", None):
                st.error("❌ Error al crear usuario en Auth.")
                return
                
            auth_id = auth_res.user.id

            # Preparar datos usando campos exactos del schema (nif en lugar de dni)
            db_datos = {
                "auth_id": auth_id,
                "email": datos_nuevos["email"],
                "nombre_completo": datos_nuevos.get("nombre_completo", ""),
                "nombre": datos_nuevos.get("nombre", datos_nuevos.get("nombre_completo", "")[:50]),
                "telefono": datos_nuevos.get("telefono"),
                "nif": datos_nuevos.get("nif"),  # CAMBIADO: de 'dni' a 'nif'
                "rol": datos_nuevos.get("rol", "alumno"),
                "empresa_id": empresa_id,
                "grupo_id": grupo_id,
                "created_at": datetime.utcnow().isoformat()
            }

            # Crear usuario en la base de datos
            result = supabase.table("usuarios").insert(db_datos).execute()
            
            if not result.data:
                try:
                    supabase.auth.admin.delete_user(auth_id)
                except:
                    pass
                st.error("❌ Error al crear usuario en la base de datos.")
                return
            
            data_service.get_usuarios.clear()
            st.success(f"✅ Usuario creado correctamente. Contraseña temporal: {password}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al crear usuario: {e}")

    # =========================
    # SOLUCIÓN SIMPLE: Campos estáticos sin reactividad
    # =========================
    def get_campos_dinamicos(datos):
        """Campos siempre visibles - sin complejidad reactiva."""
        # Todos los campos siempre visibles
        campos = ["email", "nombre_completo", "nombre", "telefono", "nif", "rol", "empresa_sel", "grupo_sel"]
        
        # Si es creación (no tiene ID), añadir password
        if not datos or not datos.get("id"):
            campos.append("password")
                
        return campos

    # Configuración simple de campos
    campos_select = {
        "rol": ["", "admin", "gestor", "alumno"],
        "empresa_sel": empresas_opciones,
        "grupo_sel": grupos_opciones
    }

    campos_readonly = ["created_at", "auth_id"]
    campos_password = ["password"]

    # Ayuda clara sobre reglas de negocio
    campos_help = {
        "email": "Email único del usuario (obligatorio)",
        "nif": "NIF, NIE o CIF válido (opcional)",
        "rol": "Rol del usuario en la plataforma",
        "empresa_sel": "Empresa del usuario (OBLIGATORIO para gestores y alumnos)",
        "grupo_sel": "Grupo asignado al usuario (opcional)",
        "nombre": "Nombre corto del usuario",
        "nombre_completo": "Nombre completo del usuario (obligatorio)",
        "telefono": "Número de teléfono de contacto",
        "password": "Contraseña temporal para el usuario (solo al crear)"
    }

    campos_obligatorios = ["email", "nombre_completo", "rol"]

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        st.warning("🔍 No se encontraron usuarios que coincidan con los filtros.")
    else:
        df_display = df_filtered.copy()
        
        # Preparar datos para display con campos correctos
        if "empresa_nombre" in df_display.columns:
            df_display["empresa_sel"] = df_display["empresa_nombre"]
        else:
            df_display["empresa_sel"] = ""
            
        if "grupo_codigo" in df_display.columns:
            df_display["grupo_sel"] = df_display["grupo_codigo"]
        else:
            df_display["grupo_sel"] = ""

        # Columnas visibles actualizadas
        columnas_visibles = ["nombre_completo", "email", "telefono", "rol", "nif"]
        if "empresa_nombre" in df_display.columns:
            columnas_visibles.append("empresa_nombre")
        if "created_at" in df_display.columns:
            columnas_visibles.append("created_at")

        # MENSAJE INFORMATIVO claro sobre reglas
        st.info("💡 **Reglas importantes:** Los gestores y alumnos deben tener una empresa asignada. Los gestores gestionan su empresa, los alumnos pueden pertenecer a grupos de su empresa.")

        # Usar listado_con_ficha estándar - sin reactive_fields
        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Usuario",
            on_save=guardar_usuario,
            on_create=crear_usuario,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            campos_password=campos_password,
            campos_obligatorios=campos_obligatorios,
            allow_creation=True,
            campos_help=campos_help,
            search_columns=["nombre_completo", "email", "telefono", "nif"]
        )

    st.divider()
    st.caption("💡 Gestiona usuarios del sistema desde esta interfaz centralizada.")
