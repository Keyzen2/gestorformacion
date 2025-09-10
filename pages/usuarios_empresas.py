import streamlit as st
import pandas as pd
import re
from datetime import datetime
from utils import validar_dni_cif, export_csv
from components.listado_con_ficha import listado_con_ficha

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"


def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios")
    st.caption("Consulta, creación y edición de usuarios registrados en la plataforma.")

    # =========================
    # Cargar datos y opciones
    # =========================
    usuarios_res = supabase.table("usuarios").select(
        "id, auth_id, nombre, nombre_completo, telefono, email, rol, empresa:empresas(nombre), grupo:grupos(codigo_grupo), created_at, dni"
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

    # Aplanar relaciones
    if "empresa" in df.columns:
        df["empresa"] = df["empresa"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else x)
    if "grupo" in df.columns:
        df["grupo"] = df["grupo"].apply(lambda x: x.get("codigo_grupo") if isinstance(x, dict) else x)

    # =========================
    # Filtro de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar usuarios")
    query = st.text_input("Buscar por nombre, email, DNI, empresa o grupo")
    df_fil = df.copy()
    if query:
        q = query.lower()
        df_fil = df_fil[
            df_fil["nombre_completo"].fillna("").str.lower().str.contains(q, na=False)
            | df_fil["email"].fillna("").str.lower().str.contains(q, na=False)
            | df_fil["dni"].fillna("").str.lower().str.contains(q, na=False)
            | df_fil["empresa"].fillna("").str.lower().str.contains(q, na=False)
            | df_fil["grupo"].fillna("").str.lower().str.contains(q, na=False)
        ]

    if df_fil.empty:
        st.info("ℹ️ No hay usuarios que coincidan con la búsqueda.")
        return

    export_csv(df_fil, filename="usuarios.csv")
    st.divider()

    # =========================
    # Función de guardado
    # =========================
    def guardar_usuario(id_usuario, datos_editados):
        if not datos_editados["nombre_completo"] or not datos_editados["email"]:
            st.error("⚠️ Nombre completo y email son obligatorios.")
            return
        if not re.match(EMAIL_REGEX, datos_editados["email"]):
            st.error("⚠️ El email no tiene un formato válido.")
            return
        if datos_editados.get("dni") and not validar_dni_cif(datos_editados["dni"]):
            st.error("⚠️ El DNI/NIE/CIF no es válido.")
            return

        try:
            empresa_id = None
            grupo_id = None
            if datos_editados["rol"] == "gestor" and datos_editados.get("empresa"):
                empresa_id = empresas_dict.get(datos_editados["empresa"])
            if datos_editados["rol"] == "alumno" and datos_editados.get("grupo"):
                grupo_id = grupos_dict.get(datos_editados["grupo"])

            # Actualizar en Auth si hay auth_id
            auth_id = df.loc[df["id"] == id_usuario, "auth_id"].values[0]
            if auth_id:
                supabase.auth.admin.update_user_by_id(auth_id, {"email": datos_editados["email"]})

            supabase.table("usuarios").update(
                {
                    "nombre_completo": datos_editados["nombre_completo"],
                    "nombre": datos_editados["nombre_completo"],  # sincronizar opcionalmente
                    "email": datos_editados["email"],
                    "rol": datos_editados["rol"],
                    "empresa_id": empresa_id,
                    "grupo_id": grupo_id,
                    "dni": datos_editados.get("dni"),
                    "telefono": datos_editados.get("telefono"),
                }
            ).eq("id", id_usuario).execute()

            st.success("✅ Usuario actualizado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar: {e}")

    # =========================
    # Función de creación
    # =========================
    def crear_usuario(datos_nuevos):
        if (
            not datos_nuevos["nombre_completo"]
            or not datos_nuevos["email"]
            or not datos_nuevos.get("contraseña")
        ):
            st.error("⚠️ Todos los campos obligatorios deben completarse.")
            return
        if not re.match(EMAIL_REGEX, datos_nuevos["email"]):
            st.error("⚠️ El email no tiene un formato válido.")
            return
        if datos_nuevos.get("dni") and not validar_dni_cif(datos_nuevos["dni"]):
            st.error("⚠️ El DNI/NIE/CIF no es válido.")
            return

        try:
            empresa_id = None
            grupo_id = None
            if datos_nuevos["rol"] == "gestor" and datos_nuevos.get("empresa"):
                empresa_id = empresas_dict.get(datos_nuevos["empresa"])
            if datos_nuevos["rol"] == "alumno" and datos_nuevos.get("grupo"):
                grupo_id = grupos_dict.get(datos_nuevos["grupo"])

            # Crear en Auth
            auth_res = supabase.auth.admin.create_user(
                {
                    "email": datos_nuevos["email"],
                    "password": datos_nuevos["contraseña"],
                    "email_confirm": True,
                }
            )
            if not getattr(auth_res, "user", None):
                st.error("❌ Error al crear el usuario en Auth.")
                return
            auth_id = auth_res.user.id

            supabase.table("usuarios").insert(
                {
                    "auth_id": auth_id,
                    "email": datos_nuevos["email"],
                    "nombre_completo": datos_nuevos["nombre_completo"],
                    "nombre": datos_nuevos["nombre_completo"],  # sincronizar opcionalmente
                    "rol": datos_nuevos["rol"],
                    "empresa_id": empresa_id,
                    "grupo_id": grupo_id,
                    "dni": datos_nuevos.get("dni"),
                    "telefono": datos_nuevos.get("telefono"),
                    "created_at": datetime.utcnow().isoformat(),
                }
            ).execute()

            st.success(f"✅ Usuario '{datos_nuevos['nombre_completo']}' creado correctamente.")
            st.rerun()
        except Exception as e:
            if "auth_id" in locals():
                supabase.auth.admin.delete_user(auth_id)
            st.error(f"❌ Error al crear el usuario: {e}")

    # =========================
    # Campos para ficha con lógica condicional y limpieza
    # =========================
    campos_select = {
        "rol": ["admin", "gestor", "alumno"],
        "empresa": empresas_opciones,
        "grupo": grupos_opciones,
    }
    campos_readonly = []

    def campos_visibles(datos):
        """Determina qué campos mostrar y limpia los que no aplican."""
        visibles = ["nombre_completo", "email", "rol", "dni", "telefono"]

        if datos.get("rol") != "gestor" and datos.get("empresa"):
            datos["empresa"] = None
        if datos.get("rol") != "alumno" and datos.get("grupo"):
            datos["grupo"] = None

        if datos.get("rol") == "gestor":
            visibles.append("empresa")
        if datos.get("rol") == "alumno":
            visibles.append("grupo")
        return visibles

    # =========================
    # Llamada a listado_con_ficha
    # =========================
    listado_con_ficha(
        df_fil,
        columnas_visibles=[
            "id",
            "nombre_completo",
            "email",
            "rol",
            "empresa",
            "grupo",
            "dni",
            "telefono",
        ],
        titulo="Usuario",
        on_save=guardar_usuario,
        on_create=crear_usuario,
        id_col="id",
        campos_select=campos_select,
        campos_readonly=campos_readonly,
        campos_dinamicos=campos_visibles,
    )
