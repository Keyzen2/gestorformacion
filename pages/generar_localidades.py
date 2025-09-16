import csv
import requests

# URL del dataset oficial de municipios por provincias (INE / datos.gob.es)
# Este enlace devuelve un CSV con campos: CODAUTO;CPRO;CMUN;DC;NOMBRE
URL = "https://datos.gob.es/apidata/catalog/dataset/ea0010587-relacion-de-municipios-y-sus-codigos-por-provincias/resource/47b28b63-ec71-4fa7-9e1a-7bbaaa4e48b4/download/municipios.csv"

# Mapa de códigos de provincia a nombre oficial (52 provincias)
provincias_map = {
    "01": "Álava",
    "02": "Albacete",
    "03": "Alicante",
    "04": "Almería",
    "33": "Asturias",
    "05": "Ávila",
    "06": "Badajoz",
    "08": "Barcelona",
    "09": "Burgos",
    "10": "Cáceres",
    "11": "Cádiz",
    "39": "Cantabria",
    "12": "Castellón",
    "51": "Ceuta",
    "13": "Ciudad Real",
    "14": "Córdoba",
    "16": "Cuenca",
    "17": "Girona",
    "18": "Granada",
    "19": "Guadalajara",
    "20": "Guipúzcoa",
    "21": "Huelva",
    "22": "Huesca",
    "23": "Jaén",
    "15": "La Coruña",
    "26": "La Rioja",
    "35": "Las Palmas",
    "24": "León",
    "25": "Lleida",
    "27": "Lugo",
    "28": "Madrid",
    "29": "Málaga",
    "52": "Melilla",
    "30": "Murcia",
    "31": "Navarra",
    "32": "Ourense",
    "34": "Palencia",
    "36": "Pontevedra",
    "37": "Salamanca",
    "38": "Santa Cruz de Tenerife",
    "40": "Segovia",
    "41": "Sevilla",
    "42": "Soria",
    "43": "Tarragona",
    "44": "Teruel",
    "45": "Toledo",
    "46": "Valencia",
    "47": "Valladolid",
    "48": "Vizcaya",
    "49": "Zamora",
    "50": "Zaragoza"
}

# Descargar el CSV
resp = requests.get(URL)
resp.raise_for_status()
lines = resp.content.decode("latin-1").splitlines()

reader = csv.DictReader(lines, delimiter=";")

# Crear SQL
sql_lines = []

# Provincias
sql_lines.append("-- Insertar provincias")
for codigo, nombre in provincias_map.items():
    sql_lines.append(f"INSERT INTO provincias (nombre) VALUES ('{nombre}');")

# Localidades
sql_lines.append("\n-- Insertar localidades")
for row in reader:
    cod_prov = row["CPRO"].zfill(2)
    nombre_prov = provincias_map.get(cod_prov)
    nombre_muni = row["NOMBRE"].strip().replace("'", "''")  # escapar comillas
    if nombre_prov:
        sql_lines.append(
            f"INSERT INTO localidades (provincia_id, nombre) "
            f"VALUES ((SELECT id FROM provincias WHERE nombre = '{nombre_prov}'), '{nombre_muni}');"
        )

# Guardar en archivo
with open("provincias_localidades_completo.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(sql_lines))

print("✅ Script SQL generado: provincias_localidades_completo.sql")
