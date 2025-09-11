import streamlit as st
import pandas as pd
import re
from datetime import datetime
from utils import validar_dni_cif, validar_email, export_csv, export_excel, generar_password_segura, get_ajustes_app
from components.listado_con_ficha import listado_con_ficha
from services.data_service import get_data_service

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"

def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios")
    st.caption("Consulta, creación y edición de usuarios registrados en la plataforma.")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    # =========================
    # Cargar datos y opciones
    # =========================
    try:
        usuarios_res = supabase.table("usuarios").select(
            "id, auth_id, nombre, nombre_completo, telefono, email, rol, empresa:empresas(nombre), grupo:grupos(codigo_grupo), created_at, dni"
        ).execute()
        df_usuarios = pd.DataFrame(usuarios_res.data or [])

        # Procesar relaciones anidadas
        if not df_usuarios.empty:
            # Aplanar empresa
            if "empresa" in df_usuarios.columns:
                df_usuarios["empresa_nombre"] = df_usuarios["empresa"].apply(
                    lambda x: x.get("nombre") if isinstance(x, dict) and x else ""
                )
            else:
                df_usuarios["empresa_nombre"] = ""
            
            # Aplanar grupo
            if "grupo" in df_usuarios.columns:
                df_usuarios["grupo_codigo"] = df_usuarios["grupo"].apply(
                    lambda x: x.get("codigo_grupo") if isinstance(x, dict) and x else ""
                )
            else:
                df_usuarios["grupo_codigo"] = ""

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
            st.metric("🔧 Administradores", len(df_usuarios[df_usuarios['rol'] == 'admin']))
        with col3:
            st.metric("👨‍💼 Gestores", len(df_usuarios[df_usuarios['rol'] == 'gestor']))
        with col4:
            st.metric("🎓 Alumnos", len(df_usuarios[df_usuarios['rol'] == 'alumno']))

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
        df_filtered = df_filtered[
            df_filtered["nombre"].fillna("").str.lower().str.contains(q_lower, na=False) |
            df_filtered["nombre_completo"].fillna("").str.lower().str.contains(q_lower, na=False) |
            df_filtered["email"].fillna("").str.lower().str.contains(q_lower, na=False) |
            df_filtered["telefono"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if rol_filter != "Todos":
        df_filtered = df_filtered[df_filtered["rol"] == rol_filter]

    # Exportación
    if not df_filtered.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Descargar CSV"):
                csv_data = export_csv(df_filtered)
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
            
            if datos_editados.get("dni") and not validar_dni_cif(datos_editados["dni"]):
                st.error("⚠️ DNI/CIF no válido.")
                return

            # Convertir selects a IDs
            if "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]

            if "grupo_sel" in datos_editados:
                grupo_sel = datos_editados.pop("grupo_sel")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_editados["grupo_id"] = grupos_dict[grupo_sel]

            # Actualizar usuario
            supabase.table("usuarios").update(datos_editados).eq("id", usuario_id).execute()
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
            
            if not datos_nuevos.get("nombre"):
                st.error("⚠️ El nombre es obligatorio.")
                return
            
            if not re.match(EMAIL_REGEX, datos_nuevos["email"]):
                st.error("⚠️ Email no válido.")
                return
            
            if datos_nuevos.get("dni") and not validar_dni_cif(datos_nuevos["dni"]):
                st.error("⚠️ DNI/CIF no válido.")
                return

            # Verificar email único
            email_existe = supabase.table("usuarios").select("id").eq("email", datos_nuevos["email"]).execute()
            if email_existe.data:
                st.error("⚠️ Ya existe un usuario con ese email.")
                return

            # Convertir selects a IDs
            if "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_nuevos["empresa_id"] = empresas_dict[empresa_sel]

            if "grupo_sel" in datos_nuevos:
                grupo_sel = datos_nuevos.pop("grupo_sel")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_nuevos["grupo_id"] = grupos_dict[grupo_sel]

            # Crear usuario
            supabase.table("usuarios").insert(datos_nuevos).execute()
            st.success("✅ Usuario creado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al crear usuario: {e}")

    # =========================
    # Campos dinámicos con lógica reactiva
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente según el rol."""
        campos_base = ["nombre", "nombre_completo", "email", "telefono", "dni", "rol"]
        
        # Obtener rol actual
        rol_actual = datos.get("rol", "")
        
        # Si es gestor, mostrar selector de empresa
        if rol_actual == "gestor":
            campos_base.append("empresa_sel")
        
        # Si es alumno, mostrar selector de grupo
        if rol_actual == "alumno":
            campos_base.append("grupo_sel")
        
        return campos_base

    # Configuración de campos
    campos_select = {
        "rol": ["", "admin", "gestor", "alumno"],
        "empresa_sel": empresas_opciones,
        "grupo_sel": grupos_opciones
    }

    campos_readonly = ["created_at", "auth_id"]

    campos_help = {
        "email": "Email único del usuario (obligatorio)",
        "dni": "DNI, NIE o CIF válido (opcional)",
        "rol": "Rol del usuario en la plataforma",
        "empresa_sel": "Empresa a la que pertenece el usuario (solo para gestores)",
        "grupo_sel": "Grupo asignado al usuario (solo para alumnos)",
        "nombre": "Nombre del usuario (obligatorio)",
        "nombre_completo": "Nombre completo del usuario",
        "telefono": "Número de teléfono de contacto"
    }

    # Campos reactivos - empresa aparece cuando rol es "gestor"
    reactive_fields = {
        "rol": ["empresa_sel", "grupo_sel"]
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        st.warning("🔍 No se encontraron usuarios que coincidan con los filtros.")
    else:
        # Preparar datos para mostrar
        df_display = df_filtered.copy()
        
        # Añadir campos para selects usando datos ya existentes
        df_display["empresa_sel"] = df_display["empresa_nombre"]
        df_display["grupo_sel"] = df_display["grupo_codigo"]

        # Interfaz principal con campos reactivos
        listado_con_ficha(
            df=df_display,
            columnas_visibles=["nombre_completo", "email", "telefono", "rol", "empresa_nombre", "created_at"],
            titulo="Usuario",
            on_save=guardar_usuario,
            on_create=crear_usuario,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=True,
            campos_help=campos_help,
            reactive_fields=reactive_fields
        )

    st.divider()
    st.caption("💡 Gestiona usuarios del sistema desde esta interfaz centralizada.")
