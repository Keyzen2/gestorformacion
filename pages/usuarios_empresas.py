"""
Módulo para la gestión de usuarios empresariales.
Versión mejorada con integración completa de DataService y listado_con_ficha.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from utils import validar_dni_cif, validar_email, export_csv, export_excel, generar_password_segura
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios")
    st.caption("Consulta, creación y edición de usuarios registrados en la plataforma.")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)

    # =========================
    # Cargar datos y opciones
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            # Obtener usuarios con información de empresa
            df_usuarios = data_service.get_usuarios(include_empresa=True)
            
            # Obtener diccionarios para selects
            empresas_dict = data_service.get_empresas_dict()
            empresas_opciones = [""] + sorted(empresas_dict.keys())
            
            # Obtener grupos para la selección
            try:
                df_grupos = data_service.get_grupos_completos()
                grupos_dict = {row["codigo_grupo"]: row["id"] for _, row in df_grupos.iterrows()} if not df_grupos.empty else {}
                grupos_opciones = [""] + sorted(grupos_dict.keys())
            except Exception:
                grupos_dict = {}
                grupos_opciones = [""]
                st.warning("⚠️ No se pudieron cargar los grupos. Algunos usuarios no podrán ser asignados a grupos.")

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
            st.metric("🔧 Administradores", len(df_usuarios[df_usuarios['rol'] == 'admin']))
        with col3:
            st.metric("👨‍💼 Gestores", len(df_usuarios[df_usuarios['rol'] == 'gestor']))
        with col4:
            st.metric("🎓 Alumnos", len(df_usuarios[df_usuarios['rol'] == 'alumno']))

    # Exportar datos
    if not df_usuarios.empty:
        col1, col2 = st.columns(2)
        with col1:
            export_csv(df_usuarios, filename="usuarios.csv")
        with col2:
            export_excel(df_usuarios, filename="usuarios.xlsx")

    st.divider()

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o teléfono")
    with col2:
        rol_filter = st.selectbox(
            "Filtrar por rol", 
            ["Todos", "Administrador", "Gestor", "Alumno", "Tutor"]
        )

    # Aplicar filtros
    df_filtered = df_usuarios.copy()
    if query:
        query_lower = query.lower()
        mask = False
        for col in ["nombre_completo", "email", "telefono", "empresa_nombre"]:
            if col in df_filtered.columns:
                mask = mask | df_filtered[col].astype(str).str.lower().str.contains(query_lower, na=False)
        df_filtered = df_filtered[mask]
    
    if rol_filter != "Todos":
        # Mapear la selección a los valores de la columna
        rol_map = {
            "Administrador": "admin",
            "Gestor": "gestor", 
            "Alumno": "alumno",
            "Tutor": "tutor"
        }
        if rol_filter in rol_map:
            df_filtered = df_filtered[df_filtered["rol"] == rol_map[rol_filter]]

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_usuario(usuario_id, datos_editados):
        """Función para guardar cambios en un usuario."""
        try:
            # Validar email si se ha modificado
            if "email" in datos_editados and not validar_email(datos_editados["email"]):
                st.error("⚠️ El email no es válido.")
                return
                
            # Validar DNI/NIE si se ha modificado
            if "dni" in datos_editados and datos_editados["dni"] and not validar_dni_cif(datos_editados["dni"]):
                st.error("⚠️ El DNI/NIE no es válido.")
                return
                
            # Convertir nombres de empresa y grupo a sus IDs
            if "empresa_nombre" in datos_editados and datos_editados["empresa_nombre"]:
                if datos_editados["empresa_nombre"] in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[datos_editados["empresa_nombre"]]
                    del datos_editados["empresa_nombre"]
                else:
                    st.error(f"⚠️ No se encontró la empresa {datos_editados['empresa_nombre']}")
                    return
                    
            if "codigo_grupo" in datos_editados and datos_editados["codigo_grupo"]:
                if datos_editados["codigo_grupo"] in grupos_dict:
                    datos_editados["grupo_id"] = grupos_dict[datos_editados["codigo_grupo"]]
                    del datos_editados["codigo_grupo"]
                else:
                    st.error(f"⚠️ No se encontró el grupo {datos_editados['codigo_grupo']}")
                    return
                    
            # Obtener el auth_id del usuario
            usuario = df_usuarios[df_usuarios["id"] == usuario_id].iloc[0]
            auth_id = usuario["auth_id"]
            
            # Actualizar usuario
            try:
                # Si hay cambio de email, actualizar en Auth
                if "email" in datos_editados and datos_editados["email"] != usuario["email"]:
                    supabase.auth.admin.update_user_by_id(
                        auth_id, 
                        {"email": datos_editados["email"]}
                    )
                
                # Actualizar en tabla usuarios
                supabase.table("usuarios").update(datos_editados).eq("id", usuario_id).execute()
                
                st.success("✅ Usuario actualizado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error al actualizar usuario: {e}")
                
        except Exception as e:
            st.error(f"⚠️ Error al procesar datos: {e}")

    def crear_usuario(datos_nuevos):
        """Función para crear un nuevo usuario."""
        try:
            # Validaciones
            if not datos_nuevos.get("email") or not datos_nuevos.get("nombre_completo") or not datos_nuevos.get("rol"):
                st.error("⚠️ Email, nombre y rol son obligatorios.")
                return
                
            if not validar_email(datos_nuevos["email"]):
                st.error("⚠️ El email no es válido.")
                return
                
            if datos_nuevos.get("dni") and not validar_dni_cif(datos_nuevos["dni"]):
                st.error("⚠️ El DNI/NIE no es válido.")
                return
                
            # Generar contraseña si no se proporciona
            password = datos_nuevos.get("password")
            if not password:
                password = generar_password_segura()
                
            # Convertir nombres de empresa y grupo a sus IDs
            empresa_id = None
            if datos_nuevos.get("empresa_nombre"):
                if datos_nuevos["empresa_nombre"] in empresas_dict:
                    empresa_id = empresas_dict[datos_nuevos["empresa_nombre"]]
                else:
                    st.error(f"⚠️ No se encontró la empresa {datos_nuevos['empresa_nombre']}")
                    return
                    
            grupo_id = None
            if datos_nuevos.get("codigo_grupo"):
                if datos_nuevos["codigo_grupo"] in grupos_dict:
                    grupo_id = grupos_dict[datos_nuevos["codigo_grupo"]]
                else:
                    st.error(f"⚠️ No se encontró el grupo {datos_nuevos['codigo_grupo']}")
                    return
            
            # Validaciones adicionales por rol
            if datos_nuevos["rol"] == "gestor" and not empresa_id:
                st.error("⚠️ Los gestores deben tener una empresa asignada.")
                return
                
            if datos_nuevos["rol"] == "alumno" and not grupo_id:
                st.error("⚠️ Los alumnos deben tener un grupo asignado.")
                return
            
            # Crear usuario en Auth
            try:
                auth_res = supabase.auth.admin.create_user({
                    "email": datos_nuevos["email"],
                    "password": password,
                    "email_confirm": True
                })
                
                if not getattr(auth_res, "user", None):
                    st.error("⚠️ Error al crear usuario en Auth.")
                    return
                    
                auth_id = auth_res.user.id
                
                # Insertar en tabla usuarios
                usuario_data = {
                    "auth_id": auth_id,
                    "email": datos_nuevos["email"],
                    "nombre_completo": datos_nuevos["nombre_completo"],
                    "rol": datos_nuevos["rol"],
                    "created_at": datetime.now().isoformat()
                }
                
                if datos_nuevos.get("telefono"):
                    usuario_data["telefono"] = datos_nuevos["telefono"]
                    
                if datos_nuevos.get("dni"):
                    usuario_data["dni"] = datos_nuevos["dni"]
                    
                if empresa_id:
                    usuario_data["empresa_id"] = empresa_id
                    
                if grupo_id:
                    usuario_data["grupo_id"] = grupo_id
                
                supabase.table("usuarios").insert(usuario_data).execute()
                
                # Mostrar mensaje con la contraseña generada
                if not datos_nuevos.get("password"):
                    st.success(f"✅ Usuario creado con éxito. Contraseña generada: **{password}**")
                else:
                    st.success("✅ Usuario creado correctamente.")
                    
                st.rerun()
                
            except Exception as e:
                st.error(f"⚠️ Error al crear usuario: {e}")
                
        except Exception as e:
            st.error(f"⚠️ Error al procesar datos: {e}")

    def eliminar_usuario(usuario_id):
        """Función para eliminar un usuario."""
        try:
            # Obtener el auth_id del usuario
            usuario = df_usuarios[df_usuarios["id"] == usuario_id].iloc[0]
            auth_id = usuario["auth_id"]
            
            # Eliminar usuario
            try:
                # Primero de la tabla usuarios
                supabase.table("usuarios").delete().eq("id", usuario_id).execute()
                
                # Luego de Auth
                supabase.auth.admin.delete_user(auth_id)
                
                st.success("✅ Usuario eliminado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error al eliminar usuario: {e}")
                
        except Exception as e:
            st.error(f"⚠️ Error al obtener datos del usuario: {e}")

    # =========================
    # Configuración de campos para listado_con_ficha
    # =========================
    campos_select = {
        "rol": ["admin", "gestor", "alumno", "tutor", "comercial"],
        "empresa_nombre": empresas_opciones,
        "codigo_grupo": grupos_opciones
    }

    campos_readonly = ["id", "auth_id", "created_at"]

    campos_password = ["password"]

    campos_help = {
        "email": "Email del usuario (obligatorio)",
        "nombre_completo": "Nombre completo del usuario (obligatorio)",
        "rol": "Rol del usuario en el sistema (obligatorio)",
        "empresa_nombre": "Empresa a la que pertenece el usuario",
        "codigo_grupo": "Grupo formativo al que pertenece el usuario",
        "dni": "DNI/NIE del usuario",
        "telefono": "Teléfono de contacto",
        "password": "Contraseña (se generará automáticamente si se deja vacío)"
    }

    campos_obligatorios = ["email", "nombre_completo", "rol"]

    # Campos reactivos según el rol
    reactive_fields = {
        "rol": ["empresa_nombre", "codigo_grupo"]
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        if df_usuarios.empty:
            st.info("ℹ️ No hay usuarios registrados en el sistema.")
        else:
            st.warning("🔍 No se encontraron usuarios que coincidan con los filtros aplicados.")
    
    # Mostrar el listado con ficha
    listado_con_ficha(
        df=df_filtered,
        columnas_visibles=["nombre_completo", "email", "telefono", "rol", "empresa_nombre", "dni"],
        titulo="Usuario",
        on_save=guardar_usuario,
        on_create=crear_usuario,
        on_delete=eliminar_usuario,
        id_col="id",
        campos_select=campos_select,
        campos_readonly=campos_readonly,
        campos_password=campos_password,
        campos_help=campos_help,
        campos_obligatorios=campos_obligatorios,
        reactive_fields=reactive_fields,
        search_columns=["nombre_completo", "email", "dni"]
    )
