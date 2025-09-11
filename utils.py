import streamlit as st
import pandas as pd
import re
import base64
from datetime import datetime, date
from io import BytesIO
from typing import Optional, List, Dict, Any
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from lxml import etree
import xml.etree.ElementTree as ET
import uuid
import requests

# =========================
# VALIDACIONES
# =========================

def validar_dni_cif(documento: str) -> bool:
    if not documento:
        return False
    documento = documento.upper().replace('-', '').replace(' ', '')
    if re.match(r'^[0-9]{8}[A-Z]$', documento):
        letras = 'TRWAGMYFPDXBNJZSQVHLCKE'
        return letras[int(documento[:8]) % 23] == documento[8]
    elif re.match(r'^[XYZ][0-9]{7}[A-Z]$', documento):
        tabla = {'X': 0, 'Y': 1, 'Z': 2}
        letras = 'TRWAGMYFPDXBNJZSQVHLCKE'
        numero = int(str(tabla[documento[0]]) + documento[1:8])
        return letras[numero % 23] == documento[8]
    elif re.match(r'^[ABCDEFGHJKLMNPQRSUVW][0-9]{7}[0-9A-J]$', documento):
        letra_ini = documento[0]
        numeros = documento[1:8]
        control = documento[8]
        suma_a = sum(int(numeros[i]) for i in range(0, 7, 2))
        suma_b = sum((2*int(numeros[i])-9 if 2*int(numeros[i])>9 else 2*int(numeros[i])) for i in range(1, 7, 2))
        unidad = (10 - (suma_a + suma_b) % 10) % 10
        letras_control = 'JABCDEFGHI'
        if letra_ini in 'KPQRSNW':
            return letras_control[unidad] == control
        return str(unidad) == control or letras_control[unidad] == control
    return False

def validar_email(email: str) -> bool:
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validar_telefono(telefono: str) -> bool:
    if not telefono:
        return False
    telefono = telefono.replace(' ', '').replace('-', '')
    return bool(re.match(r'^[6789]\d{8}$', telefono))

def es_fecha_valida(fecha_str: str) -> bool:
    if not fecha_str:
        return False
    try:
        if isinstance(fecha_str, (date, datetime)):
            return True
        pd.to_datetime(fecha_str)
        return True
    except Exception:
        return False

# =========================
# EXPORTACIÓN DE DATOS
# =========================

def export_csv(df: pd.DataFrame, filename: str = "export.csv"):
    if df is None or df.empty:
        return
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 Descargar CSV</a>'
    st.markdown(href, unsafe_allow_html=True)

def export_excel(df: pd.DataFrame, filename: str = "export.xlsx"):
    if df is None or df.empty:
        return
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).str.len().max(), len(str(col))) + 2
            worksheet.set_column(i, i, max_len)
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode('utf-8')
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 Descargar Excel</a>'
    st.markdown(href, unsafe_allow_html=True)

# =========================
# FORMATEO DE DATOS
# =========================

def formato_fecha(fecha, formato: str = "%d/%m/%Y"):
    if not fecha:
        return ""
    try:
        if isinstance(fecha, str):
            fecha = pd.to_datetime(fecha)
        return fecha.strftime(formato)
    except Exception:
        return str(fecha)

def formato_moneda(valor, simbolo: str = "€"):
    try:
        valor_num = float(valor)
        return f"{valor_num:,.2f} {simbolo}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(valor)

def formato_porcentaje(valor, decimales=1):
    try:
        if valor is None or valor == "":
            return "0%"
        if isinstance(valor, str):
            valor = float(valor.replace('%', '').replace(',', '.'))
        return f"{valor*100:.{decimales}f}%" if valor <= 1 else f"{valor:.{decimales}f}%"
    except Exception:
        return "0%"

# =========================
# UTILIDADES DE CACHE
# =========================

def clear_cache_by_prefix(prefix: str):
    count = 0
    for key in list(st.session_state.keys()):
        if key.startswith(f"_cache_data_{prefix}"):
            del st.session_state[key]
            count += 1
    return count

def optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df_optimized = df.copy()
    for col in df_optimized.columns:
        if df_optimized[col].dtype == 'object':
            if df_optimized[col].nunique()/len(df_optimized) < 0.5:
                df_optimized[col] = df_optimized[col].astype('category')
        elif df_optimized[col].dtype == 'int64':
            if df_optimized[col].min() >= 0:
                if df_optimized[col].max() < 255:
                    df_optimized[col] = df_optimized[col].astype('uint8')
                elif df_optimized[col].max() < 65535:
                    df_optimized[col] = df_optimized[col].astype('uint16')
                else:
                    df_optimized[col] = df_optimized[col].astype('uint32')
        elif df_optimized[col].dtype == 'float64':
            df_optimized[col] = df_optimized[col].astype('float32')
    return df_optimized

# =========================
# DEBUGGING Y DESARROLLO
# =========================

def debug_dataframe(df: pd.DataFrame, nombre: str = "DataFrame"):
    if df is None:
        st.warning(f"⚠️ {nombre} es None")
        return
    if df.empty:
        st.warning(f"⚠️ {nombre} está vacío")
        return
    with st.expander(f"🔍 Debug: {nombre}"):
        st.write(f"Filas: {len(df)}, Columnas: {len(df.columns)}")
        st.write("Tipos de datos:")
        st.write(df.dtypes)
        nulos = df.isna().sum()
        if nulos.sum() > 0:
            st.write("Valores nulos:")
            st.write(nulos[nulos > 0])
        st.write("Primeras filas:")
        st.dataframe(df.head(3))
        if not df.select_dtypes(include=['number']).empty:
            st.write("Estadísticas numéricas:")
            st.write(df.describe())

def log_accion(accion: str, usuario_id: str, detalles: dict = None):
    if not hasattr(st.session_state, "log_acciones"):
        st.session_state.log_acciones = []
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "accion": accion,
        "usuario_id": usuario_id,
        "detalles": detalles or {}
    }
    st.session_state.log_acciones.append(log_entry)
    if len(st.session_state.log_acciones) > 1000:
        st.session_state.log_acciones = st.session_state.log_acciones[-1000:]

# =========================
# SEGURIDAD Y PERMISOS
# =========================

def verificar_permiso(rol: str, modulos_requeridos: list = None) -> bool:
    if not rol:
        return False
    if rol == "admin":
        return True
    if not modulos_requeridos:
        return rol in ["admin", "gestor"]
    permisos_por_rol = {
        "gestor": ["formacion", "iso", "rgpd", "documentos"],
        "alumno": ["cursos", "diplomas"],
        "tutor": ["grupos", "evaluaciones"],
        "comercial": ["clientes", "oportunidades"]
    }
    if rol not in permisos_por_rol:
        return False
    return all(modulo in permisos_por_rol[rol] for modulo in modulos_requeridos)

def generar_password_segura(longitud: int = 10) -> str:
    import random, string
    minusculas = string.ascii_lowercase
    mayusculas = string.ascii_uppercase
    numeros = string.digits
    especiales = "!@#$%&*-_+=?"
    pwd = [random.choice(minusculas), random.choice(mayusculas), random.choice(numeros), random.choice(especiales)]
    caracteres = minusculas + mayusculas + numeros + especiales
    pwd.extend(random.choice(caracteres) for _ in range(longitud - 4))
    random.shuffle(pwd)
    return ''.join(pwd)

# =========================
# NOTIFICACIONES Y MENSAJES
# =========================

def mostrar_notificacion(tipo: str, mensaje: str, duracion: int = 3):
    estilos = {
        "success": {"icono": "✅", "color": "#28a745"},
        "info": {"icono": "ℹ️", "color": "#17a2b8"},
        "warning": {"icono": "⚠️", "color": "#ffc107"},
        "error": {"icono": "❌", "color": "#dc3545"}
    }
    estilo = estilos.get(tipo, estilos["info"])
    html = f"""
    <div style="
        padding: 10px 15px;
        border-radius: 5px;
        background-color: {estilo['color']}22;
        border-left: 5px solid {estilo['color']};
        margin-bottom: 10px;
        animation: fadeOut {duracion}s forwards {duracion-0.5}s;
    ">
        <div style="display: flex; align-items: center;">
            <div style="font-size: 1.2rem; margin-right: 10px;">{estilo['icono']}</div>
            <div>{mensaje}</div>
        </div>
    </div>
    <style>
    @keyframes fadeOut {{
        from {{ opacity: 1; }}
        to {{ opacity: 0; display: none; }}
    }}
    </style>
    """
    st.markdown(html, unsafe_allow_html=True)

def confirmar_accion(mensaje: str, btn_confirmar: str = "Confirmar", btn_cancelar: str = "Cancelar"):
    st.warning(mensaje)
    col1, col2 = st.columns(2)
    with col1:
        confirmar = st.button(btn_confirmar)
    with col2:
        cancelar = st.button(btn_cancelar)
    if confirmar:
        return True
    if cancelar:
        return False
    return None

# =========================
# Ajustes globales de la app
# =========================

def get_ajustes_app(supabase, campos=None):
    try:
        query = supabase.table("ajustes_app")
        query = query.select(",".join(campos)) if campos else query.select("*")
        res = query.eq("id", 1).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        st.error(f"❌ Error al cargar ajustes de la app: {e}")
        return {}

def update_ajustes_app(supabase, data_dict):
    try:
        data_dict["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("ajustes_app").update(data_dict).eq("id", 1).execute()
    except Exception as e:
        st.error(f"❌ Error al guardar ajustes de la app: {e}")
