import streamlit as st
import pandas as pd
import re
from datetime import datetime
from utils import validar_dni_cif
from services.alumnos import alta_alumno
from components.listado_crud import listado_crud

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"

def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios")
    st.caption("Consulta, creación, edición y eliminación de usuarios registrados en la plataforma.")

    # =========================
    # Cargar datos y opciones
    # =========================
    usuarios_res = supabase.table("usuarios").select(
        "id, auth_id, nombre, email, rol, empresa:empresa_id!fk_empresa(nombre), grupo:grupo_id(codigo_grupo), created_at, dni"
    ).execute()
    df = pd.DataFrame(usuarios_res.data or [])

    empresas_res = supabase.table("empresas").select("id,nombre").execute()
    empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data or []}
    empresas_opciones = sorted(empresas_dict.keys())

    grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
    grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data or []}
    grupos_opciones = sorted(grupos_dict.keys())

    if df.empty:
        st.info("ℹ️ No hay usuarios registrados.")
        return

    # Renombrar columnas para vista amigable
    df = df.rename(columns={
        "id": "ID",
        "nombre": "Nombre",
        "email": "Email",
        "rol": "Rol",
        "empresa": "Empresa",
        "grupo": "Grupo",
        "created_at": "Fecha de alta",
        "dni": "DNI"
    })
    df["Fecha de alta"] = pd.to_datetime(df["Fecha de alta"], errors="coerce").dt.strftime("%d/%m/%Y")

    # =========================
    # Función de guardado
    # =========================
    def guardar_usuario(id_usuario, datos_editados):
        if not datos_editados["Nombre"] or not datos_editados["Email"]:
            st.error("⚠️ Nombre y email son obligatorios.")
            return
        if not re.match(EMAIL_REGEX, datos_editados["Email"]):
            st.error("⚠️ El email no tiene un formato válido.")
            return
        if datos_editados.get("DNI") and not validar_dni_cif(datos_editados["DNI"]):
            st.error("⚠️ El DNI/NIE/CIF no es válido.")
            return

        try:
            empresa_id = None
            grupo_id = None
            if datos_editados["Rol"] == "gestor" and datos_editados.get("Empresa"):
                empresa_id = empresas_dict.get(datos_editados["Empresa"])
            if datos_editados["Rol"] == "alumno" and datos_editados.get("Grupo"):
                grupo_id = grupos_dict.get(datos_editados["Grupo"])

            # Actualizar en Auth si hay auth_id
            auth_id = df.loc[df["ID"] == id_usuario, "auth_id"].values[0]
            if auth_id:
                supabase.auth.admin.update_user_by_id(auth_id, {"email": datos_editados["Email"]})

            supabase.table("usuarios").update({
                "nombre": datos_editados["Nombre"],
                "email": datos_editados["Email"],
                "rol": datos_editados["Rol"],
                "empresa_id": empresa_id,
                "grupo_id": grupo_id,
                "dni": datos_editados.get("DNI")
            }).eq("id", id_usuario).execute()

            st.success("✅ Usuario actualizado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar: {e}")

    # =========================
    # Función de creación
    # =========================
    def crear_usuario(datos_nuevos):
        if not datos_nuevos["Nombre"] or not datos_nuevos["Email"] or not datos_nuevos.get("Contraseña"):
            st.error("⚠️ Todos los campos obligatorios deben completarse.")
            return
        if not re.match(EMAIL_REGEX, datos_nuevos["Email"]):
            st.error("⚠️ El email no tiene un formato válido.")
            return
        if datos_nuevos.get("DNI") and not validar_dni_cif(datos_nuevos["DNI"]):
            st.error("⚠️ El DNI/NIE/CIF no es válido.")
            return

        try:
            empresa_id = None
            grupo_id = None
            if datos_nuevos["Rol"] == "gestor" and datos_nuevos.get("Empresa"):
                empresa_id = empresas_dict.get(datos_nuevos["Empresa"])
            if datos_nuevos["Rol"] == "alumno" and datos_nuevos.get("Grupo"):
                grupo_id = grupos_dict.get(datos_nuevos["Grupo"])

            # Crear en Auth
            auth_res = supabase.auth.admin.create_user({
                "email": datos_nuevos["Email"],
                "password": datos_nuevos["Contraseña"],
                "email_confirm": True
            })
            if not getattr(auth_res, "user", None):
                st.error("❌ Error al crear el usuario en Auth.")
                return
            auth_id = auth_res.user.id

            # Insertar en tabla usuarios
            insert_data = {
                "auth_id": auth_id,
                "email": datos_nuevos["Email"],
                "nombre": datos_nuevos["Nombre"],
                "rol": datos_nuevos["Rol"],
                "empresa_id": empresa_id,
                "grupo_id": grupo_id,
                "dni": datos_nuevos.get("DNI"),
                "created_at": datetime.utcnow().isoformat()
            }
            supabase.table("usuarios").insert(insert_data).execute()

            st.success(f"✅ Usuario '{datos_nuevos['Nombre']}' creado correctamente.")
            st.rerun()
        except Exception as e:
            # Rollback en Auth si falla la inserción
            if 'auth_id' in locals():
                supabase.auth.admin.delete_user(auth_id)
            st.error(f"❌ Error al crear el usuario: {e}")

    # =========================
    # Mostrar CRUD
    # =========================
    listado_crud(
        df,
        columnas_visibles=["ID", "Nombre", "Email", "Rol", "Empresa", "Grupo", "DNI", "Fecha de alta"],
        titulo="Usuario",
        on_save=guardar_usuario,
        on_create=crear_usuario,
        id_col="ID",
        campos_select={
            "Rol": ["admin", "gestor", "alumno"],
            "Empresa": empresas_opciones,
            "Grupo": grupos_opciones
        }
    )
