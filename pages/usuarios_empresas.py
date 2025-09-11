import streamlit as st
import pandas as pd
from datetime import datetime
from utils import validar_dni_cif, validar_email, export_csv, export_excel, generar_password_segura, get_ajustes_app
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios")
    st.caption("Consulta, creación y edición de usuarios.")

    # Permisos: solo admin
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    ds = get_data_service(supabase, session_state)

    # =========================
    # Carga de datos
    # =========================
    with st.spinner("Cargando usuarios..."):
        df_usuarios = ds.get_usuarios(include_empresa=True)
        # Normalizar nombre de columna rol por coherencia con UI
        if "rol" not in df_usuarios.columns and "role" in df_usuarios.columns:
            df_usuarios["rol"] = df_usuarios["role"]
        empresas_dict = ds.get_empresas_dict()

        try:
            df_grupos = ds.get_grupos_completos()
            grupos_dict = {row["codigo_grupo"]: row["id"] for _, row in df_grupos.iterrows()} if not df_grupos.empty else {}
        except Exception:
            grupos_dict = {}
            st.warning("⚠️ No se pudieron cargar los grupos.")

    # =========================
    # Métricas rápidas + export
    # =========================
    if not df_usuarios.empty:
        colm1, colm2, colm3, colm4 = st.columns(4)
        with colm1:
            st.metric("👥 Total", len(df_usuarios))
        with colm2:
            st.metric("👑 Admin", int((df_usuarios["rol"] == "admin").sum()) if "rol" in df_usuarios.columns else 0)
        with colm3:
            st.metric("🏢 Gestor", int((df_usuarios["rol"] == "gestor").sum()) if "rol" in df_usuarios.columns else 0)
        with colm4:
            st.metric("🎓 Alumno", int((df_usuarios["rol"] == "alumno").sum()) if "rol" in df_usuarios.columns else 0)

        colx1, colx2 = st.columns(2)
        with colx1:
            export_csv(df_usuarios, filename="usuarios.csv")
        with colx2:
            export_excel(df_usuarios, filename="usuarios.xlsx")

    st.divider()

    # =========================
    # Filtros
    # =========================
    st.markdown("### 🔍 Buscar y filtrar")
    colf1, colf2 = st.columns(2)
    with colf1:
        query = st.text_input("Buscar por nombre, email o teléfono")
    with colf2:
        rol_filter = st.selectbox("Rol", ["Todos", "Administrador", "Gestor", "Alumno", "Tutor", "Comercial"])

    df_filtered = df_usuarios.copy()

    if query:
        q = query.lower()
        mask = False
        for col in ["nombre_completo", "email", "telefono", "empresa_nombre"]:
            if col in df_filtered.columns:
                mask = mask | df_filtered[col].astype(str).str.lower().str.contains(q, na=False)
        df_filtered = df_filtered[mask]

    if rol_filter != "Todos" and "rol" in df_filtered.columns:
        map_rol = {
            "Administrador": "admin",
            "Gestor": "gestor",
            "Alumno": "alumno",
            "Tutor": "tutor",
            "Comercial": "comercial"
        }
        if rol_filter in map_rol:
            df_filtered = df_filtered[df_filtered["rol"] == map_rol[rol_filter]]

    # =========================
    # CRUD callbacks
    # =========================
    def guardar_usuario(usuario_id, datos_editados):
        try:
            # Validaciones
            if "email" in datos_editados and datos_editados["email"]:
                if not validar_email(datos_editados["email"]):
                    st.error("⚠️ Email inválido.")
                    return
            if "dni" in datos_editados and datos_editados["dni"]:
                if not validar_dni_cif(datos_editados["dni"]):
                    st.error("⚠️ DNI/NIE/CIF inválido.")
                    return

            # Convertir empresa_nombre -> empresa_id
            if "empresa_nombre" in datos_editados:
                nombre = datos_editados.pop("empresa_nombre")
                if nombre:
                    if nombre in empresas_dict:
                        datos_editados["empresa_id"] = empresas_dict[nombre]
                    else:
                        st.error(f"⚠️ Empresa '{nombre}' no encontrada.")
                        return
                else:
                    datos_editados["empresa_id"] = None

            # Convertir codigo_grupo -> grupo_id
            if "codigo_grupo" in datos_editados:
                codigo = datos_editados.pop("codigo_grupo")
                if codigo:
                    if codigo in grupos_dict:
                        datos_editados["grupo_id"] = grupos_dict[codigo]
                    else:
                        st.error(f"⚠️ Grupo '{codigo}' no encontrado.")
                        return
                else:
                    datos_editados["grupo_id"] = None

            # Normalizar campo rol (UI usa 'rol')
            if "rol" in datos_editados and datos_editados["rol"] == "":
                datos_editados.pop("rol")
            # Asegurar que no se intenta escribir un campo inexistente 'role'
            if "role" in datos_editados:
                # mapear a 'rol' por coherencia con el schema
                datos_editados["rol"] = datos_editados.pop("role")

            # Obtener auth_id para cambios en Auth si es necesario
            row = df_usuarios[df_usuarios["id"] == usuario_id].iloc[0]
            auth_id = row.get("auth_id")

            # Si cambia el email, actualizar también en Auth
            if "email" in datos_editados and auth_id and datos_editados["email"] != row.get("email"):
                try:
                    supabase.auth.admin.update_user_by_id(auth_id, {"email": datos_editados["email"]})
                except Exception as e:
                    st.error(f"⚠️ Error actualizando email en Auth: {e}")
                    return

            # Persistir en tabla usuarios (usar columnas del schema)
            allowed_cols = {"email", "nombre_completo", "telefono", "dni", "rol", "empresa_id", "grupo_id"}
            update_payload = {k: v for k, v in datos_editados.items() if k in allowed_cols}

            if not update_payload:
                st.info("ℹ️ No hay cambios válidos para guardar.")
                return

            supabase.table("usuarios").update(update_payload).eq("id", usuario_id).execute()
            st.success("✅ Usuario actualizado.")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")

    def crear_usuario(datos_nuevos):
        try:
            # Validaciones básicas
            required = ["email", "nombre_completo", "rol"]
            faltan = [c for c in required if not datos_nuevos.get(c)]
            if faltan:
                st.error(f"⚠️ Faltan campos obligatorios: {', '.join(faltan)}")
                return

            if not validar_email(datos_nuevos["email"]):
                st.error("⚠️ Email inválido.")
                return

            if datos_nuevos.get("dni") and not validar_dni_cif(datos_nuevos["dni"]):
                st.error("⚠️ DNI/NIE/CIF inválido.")
                return

            # Password
            password = datos_nuevos.get("password") or generar_password_segura()

            # Mapear empresa_nombre -> empresa_id
            empresa_id = None
            if datos_nuevos.get("empresa_nombre"):
                nombre = datos_nuevos["empresa_nombre"]
                if nombre in empresas_dict:
                    empresa_id = empresas_dict[nombre]
                else:
                    st.error(f"⚠️ Empresa '{nombre}' no encontrada.")
                    return

            # Mapear codigo_grupo -> grupo_id
            grupo_id = None
            if datos_nuevos.get("codigo_grupo"):
                codigo = datos_nuevos["codigo_grupo"]
                if codigo in grupos_dict:
                    grupo_id = grupos_dict[codigo]
                else:
                    st.error(f"⚠️ Grupo '{codigo}' no encontrado.")
                    return

            # Crear usuario en Auth
            try:
                auth_res = supabase.auth.admin.create_user({
                    "email": datos_nuevos["email"],
                    "password": password,
                    "email_confirm": True
                })
                if not getattr(auth_res, "user", None):
                    st.error("⚠️ No se pudo crear el usuario en Auth.")
                    return
                auth_id = auth_res.user.id
            except Exception as e:
                st.error(f"❌ Error creando en Auth: {e}")
                return

            # Insertar en tabla usuarios
            payload = {
                "auth_id": auth_id,
                "email": datos_nuevos["email"],
                "nombre_completo": datos_nuevos["nombre_completo"],
                "rol": datos_nuevos["rol"],  # usar 'rol' (schema)
                "created_at": datetime.now().isoformat()
            }
            if datos_nuevos.get("telefono"):
                payload["telefono"] = datos_nuevos["telefono"]
            if datos_nuevos.get("dni"):
                payload["dni"] = datos_nuevos["dni"]
            if empresa_id:
                payload["empresa_id"] = empresa_id
            if grupo_id:
                payload["grupo_id"] = grupo_id

            supabase.table("usuarios").insert(payload).execute()

            if "password" not in datos_nuevos or not datos_nuevos["password"]:
                st.success(f"✅ Usuario creado. Contraseña generada: {password}")
            else:
                st.success("✅ Usuario creado.")

            st.rerun()

        except Exception as e:
            st.error(f"❌ Error al crear: {e}")

    def eliminar_usuario(usuario_id):
        try:
            row = df_usuarios[df_usuarios["id"] == usuario_id].iloc[0]
            auth_id = row.get("auth_id")

            # Primero eliminar de la tabla
            supabase.table("usuarios").delete().eq("id", usuario_id).execute()

            # Luego eliminar en Auth
            if auth_id:
                try:
                    supabase.auth.admin.delete_user(auth_id)
                except Exception as e:
                    st.warning(f"⚠️ Usuario eliminado en BD, pero no en Auth: {e}")

            st.success("✅ Usuario eliminado.")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error al eliminar: {e}")

    # =========================
    # Configuración de formulario
    # =========================
    empresas_opciones = [""] + sorted(empresas_dict.keys())
    grupos_opciones = [""] + (sorted(grupos_dict.keys()) if grupos_dict else [])

    campos_select = {
        "rol": ["admin", "gestor", "alumno", "tutor", "comercial"],
        "empresa_nombre": empresas_opciones,
        "codigo_grupo": grupos_opciones
    }
    campos_readonly = ["id", "auth_id", "created_at"]
    campos_password = ["password"]
    campos_help = {
        "email": "Obligatorio. Se validará el formato.",
        "nombre_completo": "Obligatorio.",
        "rol": "Rol del usuario en el sistema.",
        "empresa_nombre": "Empresa a la que pertenece (opcional salvo gestores).",
        "codigo_grupo": "Grupo formativo (obligatorio para alumnos).",
        "dni": "DNI/NIE/CIF (opcional, se validará formato).",
        "telefono": "Teléfono de contacto (opcional).",
        "password": "Si se deja vacío, se generará automáticamente."
    }
    campos_obligatorios = ["email", "nombre_completo", "rol"]
    reactive_fields = {
        "rol": ["empresa_nombre", "codigo_grupo"]
    }

    # Columnas visibles coherentes con DF
    columnas_visibles = [c for c in [
        "nombre_completo", "email", "telefono", "rol", "empresa_nombre"
    ] if c in df_usuarios.columns]

    if df_usuarios.empty:
        st.info("ℹ️ No hay usuarios registrados.")
    elif df_filtered.empty:
        st.warning("🔍 No hay resultados con los filtros aplicados.")

    listado_con_ficha(
        df=df_filtered if not df_filtered.empty else df_usuarios,
        columnas_visibles=columnas_visibles,
        titulo="Usuario",
        on_save=guardar_usuario,
        on_create=crear_usuario,
        on_delete=eliminar_usuario,
        id_col="id",
        campos_select=campos_select,
        campos_readonly=campos_readonly,
        campos_password=campos_password,
        campos_help=campos_help,
        reactive_fields=reactive_fields,
        search_columns=["nombre_completo", "email", "telefono", "empresa_nombre"]
    )
