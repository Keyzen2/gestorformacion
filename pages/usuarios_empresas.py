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
        df = pd.DataFrame(usuarios_res.data or [])

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
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Usuarios", len(df))
        with col2:
            st.metric("🔧 Administradores", len(df[df['rol'] == 'admin']))
        with col3:
            st.metric("👨‍💼 Gestores", len(df[df['rol'] == 'gestor']))
        with col4:
            st.metric("🎓 Alumnos", len(df[df['rol'] == 'alumno']))

    if df.empty:
        st.info("ℹ️ No hay usuarios registrados.")
        return

    # Aplanar relaciones para mostrar correctamente
    if "empresa" in df.columns:
        df["empresa"] = df["empresa"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else (x or ""))
    if "grupo" in df.columns:
        df["grupo"] = df["grupo"].apply(lambda x: x.get("codigo_grupo") if isinstance(x, dict) else (x or ""))

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

    if df_fil.empty and query:
        st.warning(f"🔍 No se encontraron usuarios que coincidan con '{query}'.")
        return

    # Botón de exportación
    if not df_fil.empty:
        export_csv(df_fil, filename="usuarios.csv")
        st.divider()

    # =========================
    # Función de guardado
    # =========================
    def guardar_usuario(id_usuario, datos_editados):
        try:
            # Validaciones básicas
            if not datos_editados.get("nombre_completo") or not datos_editados.get("email"):
                st.error("⚠️ Nombre completo y email son obligatorios.")
                return
            
            if not re.match(EMAIL_REGEX, datos_editados["email"]):
                st.error("⚠️ El email no tiene un formato válido.")
                return
            
            if datos_editados.get("dni") and not validar_dni_cif(datos_editados["dni"]):
                st.error("⚠️ El DNI/NIE/CIF no es válido.")
                return

            # Obtener IDs de empresa y grupo según el rol
            empresa_id = None
            grupo_id = None
            
            if datos_editados["rol"] == "gestor" and datos_editados.get("empresa"):
                empresa_id = empresas_dict.get(datos_editados["empresa"])
                if not empresa_id:
                    st.error("⚠️ Empresa no encontrada.")
                    return
                    
            if datos_editados["rol"] == "alumno" and datos_editados.get("grupo"):
                grupo_id = grupos_dict.get(datos_editados["grupo"])
                if not grupo_id:
                    st.error("⚠️ Grupo no encontrado.")
                    return

            # Obtener auth_id para actualizar en Auth si es necesario
            usuario_actual = df.loc[df["id"] == id_usuario].iloc[0]
            auth_id = usuario_actual["auth_id"]
            
            # Actualizar email en Auth si cambió
            if auth_id and datos_editados["email"] != usuario_actual["email"]:
                supabase.auth.admin.update_user_by_id(auth_id, {"email": datos_editados["email"]})

            # Preparar datos para actualizar
            update_data = {
                "nombre_completo": datos_editados["nombre_completo"],
                "nombre": datos_editados["nombre_completo"],
                "email": datos_editados["email"],
                "rol": datos_editados["rol"],
                "empresa_id": empresa_id,
                "grupo_id": grupo_id,
                "dni": datos_editados.get("dni") or None,
                "telefono": datos_editados.get("telefono") or None,
            }

            # Limpiar campos según el rol
            if datos_editados["rol"] != "gestor":
                update_data["empresa_id"] = None
            if datos_editados["rol"] != "alumno":
                update_data["grupo_id"] = None

            supabase.table("usuarios").update(update_data).eq("id", id_usuario).execute()
            st.success("✅ Usuario actualizado correctamente.")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error al actualizar usuario: {e}")

    # =========================
    # Función de creación
    # =========================
    def crear_usuario(datos_nuevos):
        try:
            # Validaciones
            if not datos_nuevos.get("nombre_completo") or not datos_nuevos.get("email"):
                st.error("⚠️ Nombre completo y email son obligatorios.")
                return
                
            if not re.match(EMAIL_REGEX, datos_nuevos["email"]):
                st.error("⚠️ El email no tiene un formato válido.")
                return
                
            if datos_nuevos.get("dni") and not validar_dni_cif(datos_nuevos["dni"]):
                st.error("⚠️ El DNI/NIE/CIF no es válido.")
                return

            # Generar contraseña si no se proporcionó
            import random
            import string
            password = datos_nuevos.get("contraseña")
            if not password:
                password = "".join(random.choices(string.ascii_letters + string.digits, k=12))

            # Obtener IDs de empresa y grupo
            empresa_id = None
            grupo_id = None
            
            if datos_nuevos["rol"] == "gestor" and datos_nuevos.get("empresa"):
                empresa_id = empresas_dict.get(datos_nuevos["empresa"])
                
            if datos_nuevos["rol"] == "alumno" and datos_nuevos.get("grupo"):
                grupo_id = grupos_dict.get(datos_nuevos["grupo"])

            # Crear en Auth
            auth_res = supabase.auth.admin.create_user({
                "email": datos_nuevos["email"],
                "password": password,
                "email_confirm": True,
            })
            
            if not getattr(auth_res, "user", None):
                st.error("❌ Error al crear el usuario en Auth.")
                return
                
            auth_id = auth_res.user.id

            # Crear en base de datos
            supabase.table("usuarios").insert({
                "auth_id": auth_id,
                "email": datos_nuevos["email"],
                "nombre_completo": datos_nuevos["nombre_completo"],
                "nombre": datos_nuevos["nombre_completo"],
                "rol": datos_nuevos["rol"],
                "empresa_id": empresa_id,
                "grupo_id": grupo_id,
                "dni": datos_nuevos.get("dni") or None,
                "telefono": datos_nuevos.get("telefono") or None,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()

            success_msg = f"✅ Usuario '{datos_nuevos['nombre_completo']}' creado correctamente."
            if not datos_nuevos.get("contraseña"):
                success_msg += f"\n🔑 Contraseña generada: `{password}`"
                
            st.success(success_msg)
            st.rerun()

        except Exception as e:
            # Rollback si falla la inserción en BD
            if 'auth_id' in locals():
                try:
                    supabase.auth.admin.delete_user(auth_id)
                except Exception:
                    pass
            st.error(f"❌ Error al crear el usuario: {e}")

    # =========================
    # Función para campos dinámicos MEJORADA
    # =========================
    def campos_visibles_dinamicos(datos):
        """
        Determina qué campos mostrar según el rol seleccionado.
        Se ejecuta tanto para edición como para creación.
        """
        # Campos base que siempre aparecen
        campos_base = ["nombre_completo", "email", "rol", "dni", "telefono"]
        
        # Obtener el rol actual
        rol_actual = datos.get("rol", "")
        
        # Añadir campos específicos según el rol
        if rol_actual == "gestor":
            campos_base.append("empresa")
        elif rol_actual == "alumno":
            campos_base.append("grupo")
        
        # Para formulario de creación (datos vacíos), añadir campo contraseña
        if not datos or not datos.get("id"):
            campos_base.append("contraseña")
            
        return campos_base

    # =========================
    # Configuración de campos con mejoras visuales
    # =========================
    campos_select = {
        "rol": ["admin", "gestor", "alumno", "comercial"],
        "empresa": empresas_opciones,
        "grupo": grupos_opciones,
    }
    
    campos_password = ["contraseña"]
    campos_readonly = ["created_at"]

    # =========================
    # Campos con ayuda contextual
    # =========================
    campos_help = {
        "rol": "Selecciona el rol del usuario. Gestor requiere empresa, Alumno requiere grupo.",
        "empresa": "Solo para gestores. Empresa que administrará el usuario.",
        "grupo": "Solo para alumnos. Grupo al que pertenece el participante.",
        "dni": "DNI, NIE o CIF válido (opcional)",
        "contraseña": "Déjalo vacío para generar automáticamente"
    }

    # =========================
    # Callback para reaccionar a cambios de rol
    # =========================
    def on_rol_change():
        """Función que se ejecuta cuando cambia el rol (para futuras mejoras)."""
        pass

    # =========================
    # Llamada al componente mejorado
    # =========================
    listado_con_ficha(
        df_fil,
        columnas_visibles=[
            "id", "nombre_completo", "email", "rol", 
            "empresa", "grupo", "dni", "telefono"
        ],
        titulo="Usuario",
        on_save=guardar_usuario,
        on_create=crear_usuario,
        id_col="id",
        campos_select=campos_select,
        campos_readonly=campos_readonly,
        campos_dinamicos=campos_visibles_dinamicos,
        campos_password=campos_password,
        allow_creation=True
    )

    # =========================
    # JavaScript para campos dinámicos (mejorado)
    # =========================
    st.markdown("""
    <script>
    // Función para mostrar/ocultar campos según el rol seleccionado
    function toggleFieldsByRole() {
        const roleSelects = document.querySelectorAll('select[data-baseweb="select"]');
        
        roleSelects.forEach(select => {
            select.addEventListener('change', function() {
                const selectedRole = this.value;
                const form = this.closest('form');
                
                if (form) {
                    // Ocultar campos de empresa y grupo por defecto
                    const empresaField = form.querySelector('[data-testid*="empresa"]');
                    const grupoField = form.querySelector('[data-testid*="grupo"]');
                    
                    if (empresaField) {
                        empresaField.style.display = selectedRole === 'gestor' ? 'block' : 'none';
                    }
                    
                    if (grupoField) {
                        grupoField.style.display = selectedRole === 'alumno' ? 'block' : 'none';
                    }
                }
            });
        });
    }
    
    // Ejecutar cuando se carga la página
    setTimeout(toggleFieldsByRole, 1000);
    
    // Ejecutar periódicamente para capturar nuevos formularios
    setInterval(toggleFieldsByRole, 2000);
    </script>
    """, unsafe_allow_html=True)

    # =========================
    # CSS para mejorar la visualización
    # =========================
    st.markdown("""
    <style>
    /* Estilos para campos condicionales */
    .campo-condicional {
        transition: opacity 0.3s ease-in-out;
    }
    
    .campo-oculto {
        opacity: 0.5;
        pointer-events: none;
    }
    
    /* Mejorar visualización de formularios */
    .stForm {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        background-color: #fafafa;
    }
    
    /* Estilos para métricas */
    [data-testid="metric-container"] {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Botones de acción */
    .stButton > button {
        border-radius: 6px;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    /* Alertas mejoradas */
    .stAlert {
        border-radius: 8px;
        border-left: 4px solid;
    }
    
    /* Inputs mejorados */
    .stTextInput > div > div > input {
        border-radius: 6px;
    }
    
    .stSelectbox > div > div > div {
        border-radius: 6px;
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # Información adicional
    # =========================
    with st.expander("ℹ️ Información sobre roles"):
        st.markdown("""
        **Roles disponibles:**
        
        - **👑 Admin**: Acceso total al sistema, puede gestionar todas las empresas
        - **👨‍💼 Gestor**: Administra una empresa específica y sus datos
        - **🎓 Alumno**: Acceso limitado a sus grupos y diplomas
        - **💼 Comercial**: Gestión de CRM y clientes de la empresa
        
        **Campos dinámicos:**
        - Los **gestores** deben tener una **empresa** asignada
        - Los **alumnos** deben tener un **grupo** asignado
        - Los campos se muestran/ocultan automáticamente según el rol seleccionado
        """)

    st.divider()
    st.caption("💡 Los usuarios gestores administran empresas, los alumnos pertenecen a grupos específicos.")
