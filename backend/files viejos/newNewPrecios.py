import csv
import time
import urllib.request
from pathlib import Path

# URL DIRECTA de descarga del CSV (link "DESCARGAR" del dataset oficial)
CSV_DOWNLOAD_URL = (
    "http://datos.energia.gob.ar/dataset/1c181390-5045-475e-94dc-410429be4b17/resource/80ac25de-a44a-4445-9215-090cf55cfda5/download/precios-en-surtidor-resolucin-3142016.csv"
)

# Ruta del archivo CSV local (el archivo crudo tal como viene del gobierno)
LOCAL_CSV = Path("precios-en-surtidor-resolucin-3142016.csv")

# Ruta del archivo de salida que va a consumir tu app en C
OUTPUT_TXT = Path("precios.txt")

# Tiempo máximo de vida del CSV local (en segundos)
REFRESH_SECONDS = 3600  # 1 hora

# Filtros de negocio
LOCALIDADES_PERMITIDAS = {"CORRIENTES", "PASO DE LOS LIBRES"}
EMPRESAS_PERMITIDAS = {"2", "4", "28"}  # 2=YPF, 4=Shell, 28=PUMA


# ------------ HELPERS PARA PRECIOS MÍNIMOS ------------

# Normaliza el nombre del producto para compararlo sin drama:
# - pasa a mayúsculas
# - saca tildes
# - compacta espacios
def _normalizar_producto(nombre: str) -> str:
    if not nombre:
        return ""
    nombre = nombre.upper()
    # reemplazo de vocales acentuadas
    nombre = nombre.translate(str.maketrans("ÁÉÍÓÚ", "AEIOU"))
    # compactar espacios múltiples
    nombre = " ".join(nombre.split())
    return nombre


def _pasa_filtro_precio(producto: str, precio_str: str) -> bool:
    """
    Devuelve True si el precio es válido para ese producto
    según los mínimos que definiste.

    Gas Oil Grado 2 / 3 -> mínimo 1600
    Nafta Super / Premium -> mínimo 1500
    Otros productos -> no se filtran por precio.
    """
    if not precio_str:
        return False

    # CSV a veces usa coma como separador decimal, lo normalizamos
    precio_str = precio_str.replace(",", ".")
    try:
        precio = float(precio_str)
    except ValueError:
        # Si no se puede parsear, lo tiramos a la basura
        return False

    prod_norm = _normalizar_producto(producto)

    minimo = None

    # GAS OIL GRADO 2
    if "GAS OIL" in prod_norm and "GRADO 2" in prod_norm:
        minimo = 1600.0
    # GAS OIL GRADO 3
    elif "GAS OIL" in prod_norm and "GRADO 3" in prod_norm:
        minimo = 1600.0
    # NAFTA SUPER
    elif "NAFTA" in prod_norm and "SUPER" in prod_norm:
        minimo = 1400.0
    # NAFTA PREMIUM
    elif "NAFTA" in prod_norm and "PREMIUM" in prod_norm:
        minimo = 1400.0

    # Si es un producto que no entra en estos cuatro casos, no lo filtramos por precio
    if minimo is None:
        return True

    return precio >= minimo


# ------------ DESCARGA DEL CSV ------------

def descargar_csv_si_necesario():
    """Si el CSV local no existe o tiene más de 1 hora, lo descarga de nuevo."""
    ahora = time.time()

    if LOCAL_CSV.exists():
        edad = ahora - LOCAL_CSV.stat().st_mtime
        minutos = edad / 60.0
        if edad < REFRESH_SECONDS:
            print(f"[INFO] CSV local vigente ({minutos:.1f} min). No se descarga de nuevo.")
            return
        else:
            print(f"[INFO] CSV local viejo ({minutos:.1f} min). Se refresca desde la web.")
            try:
                LOCAL_CSV.unlink()
            except OSError:
                pass

    print(f"[INFO] Descargando CSV desde {CSV_DOWNLOAD_URL}")
    req = urllib.request.Request(
        CSV_DOWNLOAD_URL,
        headers={"User-Agent": "Mozilla/5.0 WidgetViaje"}
    )

    with urllib.request.urlopen(req, timeout=120) as resp, LOCAL_CSV.open("wb") as f:
        data = resp.read()
        f.write(data)

    print(f"[INFO] CSV descargado en {LOCAL_CSV.resolve()}")


# ------------ PROCESAMIENTO DEL CSV Y GENERACIÓN DE precios.txt ------------

def _procesar_stream_csv(f, output_path: Path):
    reader = csv.DictReader(f)

    # limpiar posible BOM en el primer encabezado
    if reader.fieldnames and reader.fieldnames[0].startswith("\ufeff"):
        reader.fieldnames[0] = reader.fieldnames[0].lstrip("\ufeff")

    filas = []

    for row in reader:
        # BOM en el dato
        if "indice_tiempo" not in row and "\ufeffindice_tiempo" in row:
            row["indice_tiempo"] = row.pop("\ufeffindice_tiempo")

        # --- FILTROS DE NEGOCIO BÁSICOS ---

        # Localidad
        loc = row.get("localidad")
        if not loc or loc not in LOCALIDADES_PERMITIDAS:
            continue

        # Horario
        if row.get("tipohorario") != "Diurno":
            continue

        # Empresa
        if row.get("idempresabandera") not in EMPRESAS_PERMITIDAS:
            continue

        # --- FILTRO POR PRECIO MÍNIMO SEGÚN PRODUCTO ---
        producto = row.get("producto", "")
        precio_str = row.get("precio", "")

        if not _pasa_filtro_precio(producto, precio_str):
            # Precio por debajo del mínimo -> ni siquiera lo consideramos
            continue

        # Si pasó todos los filtros, guardamos la fila relevante
        filas.append({
            "indice_tiempo": row.get("indice_tiempo", ""),
            "direccion": row.get("direccion", ""),
            "localidad": loc,
            "producto": producto,
            "tipohorario": row.get("tipohorario", ""),
            "precio": precio_str,
            "idempresabandera": row.get("idempresabandera", ""),
            "empresabandera": row.get("empresabandera", ""),
            "latitud": row.get("latitud", ""),
            "longitud": row.get("longitud", "")
        })

    # --- ELECCIÓN DEL PRECIO MÁS NUEVO POR ESTACIÓN + PRODUCTO ---

    # clave = (latitud, longitud, producto)
    # valor = fila con el indice_tiempo más nuevo PARA ESA CLAVE
    mejores_por_clave = {}

    for r in filas:
        lat = r["latitud"]
        lon = r["longitud"]
        prod = r["producto"]
        indice = r["indice_tiempo"]

        if not lat or not lon or not indice:
            continue

        clave = (lat, lon, prod)
        actual = mejores_por_clave.get(clave)

        if actual is None:
            # Primera vez que vemos esta estación+producto
            mejores_por_clave[clave] = r
        else:
            # Ya tenemos un registro para esa estación+producto
            # Nos quedamos con el de índice de tiempo más alto (AAAA-MM)
            if indice > actual["indice_tiempo"]:
                mejores_por_clave[clave] = r
            # OJO: acá ya no hace falta comparar precio, porque
            # a esta altura solo hay precios que pasaron el filtro mínimo.
            # El criterio para "más nuevo" sigue siendo la fecha.

    filas_finales = list(mejores_por_clave.values())

    # Ordenamos solo por prolijidad
    filas_finales.sort(
        key=lambda r: (
            r["indice_tiempo"],
            r["localidad"],
            r["empresabandera"],
            r["producto"],
        )
    )

    # Escritura de precios.txt
    with output_path.open("w", encoding="utf-8", newline="") as out:
        w = csv.writer(out, delimiter="|")
        w.writerow([
            "indice_tiempo",
            "direccion",
            "localidad",
            "producto",
            "precio",
            "idempresabandera",
            "empresabandera",
            "latitud",
            "longitud"
        ])

        for r in filas_finales:
            w.writerow([
                r["indice_tiempo"],
                r["direccion"],
                r["localidad"],
                r["producto"],
                r["precio"],
                r["idempresabandera"],
                r["empresabandera"],
                r["latitud"],
                r["longitud"]
            ])


def generar_precios_txt():
    """Pipeline completo: asegura CSV local actualizado y genera precios.txt."""
    descargar_csv_si_necesario()

    with LOCAL_CSV.open("r", encoding="utf-8", newline="") as f:
        _procesar_stream_csv(f, OUTPUT_TXT)

    print(f"[INFO] precios.txt generado en {OUTPUT_TXT.resolve()}")


if __name__ == "__main__":
    generar_precios_txt()
