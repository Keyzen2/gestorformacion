import os
import streamlit as st

def replace_use_container_width(base_path: str = "."):
    """
    Recorre todos los .py desde base_path y reemplaza:
      use_container_width=True  -> width='stretch'
      use_container_width=False -> width='content'
    Devuelve resumen de archivos modificados y total de reemplazos.
    """
    archivos_modificados = 0
    total_reemplazos = 0

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    nuevos = content
                    nuevos = nuevos.replace("use_container_width=True", "width='stretch'")
                    nuevos = nuevos.replace("use_container_width=False", "width='content'")

                    if nuevos != content:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(nuevos)

                        archivos_modificados += 1
                        # Contar cuántos reemplazos hicimos en este archivo
                        cambios = (content.count("use_container_width=True") +
                                   content.count("use_container_width=False"))
                        total_reemplazos += cambios

                        print(f"✅ {file_path} — {cambios} reemplazos")

                except Exception as e:
                    print(f"⚠️ Error procesando {file_path}: {e}")

    return archivos_modificados, total_reemplazos


def run_fix():
    """Ejecuta la corrección y muestra resumen en la app Streamlit."""
    archivos, reemplazos = replace_use_container_width(".")
    if archivos > 0:
        st.success(f"✅ Reemplazo completado: {reemplazos} cambios en {archivos} archivos.")
    else:
        st.info("ℹ️ No se encontraron `use_container_width` en el proyecto.")


if __name__ == "__main__":
    run_fix()
