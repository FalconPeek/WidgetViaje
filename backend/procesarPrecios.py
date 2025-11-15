import csv
import time
import urllib.request
from pathlib import Path
from collections import defaultdict

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

# Desviación máxima razonable entre precios de un mismo producto en una ciudad
MAX_DESVIACION = 150.0


# ------------ HELPERS PARA PRODUCTOS Y PRECIOS ------------

def _normalizar_texto(nombre: str) -> str:
    """Mayúsculas, sin tildes, espacios normalizados, y GASOIL unificado."""
    if not nombre:
        return ""
    nombre = nombre.upper()
    nombre = nombre.translate(str.maketrans("ÁÉÍÓÚ", "AEIOU"))
    # Unificar GASOIL / GAS OIL
    nombre = nombre.replace("GASOIL", "GAS OIL")
    # Compactar espacios múltiples
    nombre = " ".join(nombre.split())
    return nombre


def _clasificar_producto(producto: str) -> str | None:
    """
    Devuelve una categoría interna para los 4 productos que te interesan.
    Si no es uno de esos 4, devuelve None (lo descartamos).
    """
    p = _normalizar_texto(producto)

    if "GAS OIL" in p and "GRADO 2" in p:
        return "GAS OIL GRADO 2"
    if "GAS OIL" in p and "GRADO 3" in p:
        return "GAS OIL GRADO 3"
    if "NAFTA" in p and "SUPER" in p:
        return "NAFTA SUPER"
    if "NAFTA" in p and "PREMIUM" in p:
        return "NAFTA PREMIUM"

    return None


def _filtrar_y_parsear_precio(producto: str, precio_str: str) -> float | None:
    """
    Aplica los mínimos por producto y devuelve el precio como float.
    Si el precio es inválido o está por debajo del mínimo, devuelve None.

    Gas Oil Grado 2 / 3 -> mínimo 1600
    Nafta Super / Premium -> mínimo 1500
    Otros productos -> se descartan (no nos interesan).
    """
    if not precio_str:
        return None

    precio_str = precio_str.replace(",", ".")
    try:
        precio = float(precio_str)
    except ValueError:
        return None

    categoria = _clasificar_producto(producto)
    if categoria is None:
        # Producto que no es uno de los 4 que queremos.
        return None

    if categoria in ("GAS OIL GRADO 2", "GAS OIL GRADO 3"):
        minimo = 1600.0
    else:  # NAFTA SUPER / NAFTA PREMIUM
        minimo = 1500.0

    if precio < minimo:
        return None

    return precio


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

        producto = row.get("producto", "")
        precio_str = row.get("precio", "")

        # --- FILTRO POR PRODUCTO INTERESANTE + PRECIO MÍNIMO ---
        precio_num = _filtrar_y_parsear_precio(producto, precio_str)
        if precio_num is None:
            continue  # o no es uno de los 4 productos, o el precio es inválido/bajo

        categoria = _clasificar_producto(producto)
        if categoria is None:
            continue  # seguridad extra

        filas.append({
            "indice_tiempo": row.get("indice_tiempo", ""),
            "direccion": row.get("direccion", ""),
            "localidad": loc,
            "producto": producto,          # texto original del CSV
            "categoria": categoria,        # categoría normalizada (1 de los 4)
            "tipohorario": row.get("tipohorario", ""),
            "precio": f"{precio_num:.2f}", # texto para escribir
            "precio_num": precio_num,      # número para comparar
            "idempresabandera": row.get("idempresabandera", ""),
            "empresabandera": row.get("empresabandera", ""),
            "latitud": row.get("latitud", ""),
            "longitud": row.get("longitud", "")
        })

    # --- PRIMER CORTE: precio más nuevo POR ESTACIÓN (lat+long) Y PRODUCTO ---

    # clave1 = (latitud, longitud, categoria)
    # valor = fila con:
    #   - indice_tiempo más reciente
    #   - si empate de fecha, precio más alto
    por_estacion = {}

    for r in filas:
        lat = r["latitud"]
        lon = r["longitud"]
        cat = r["categoria"]
        indice = r["indice_tiempo"]
        precio_num = r["precio_num"]

        if not lat or not lon or not indice or not cat:
            continue

        clave1 = (lat, lon, cat)
        actual = por_estacion.get(clave1)

        if actual is None:
            por_estacion[clave1] = r
        else:
            # Comparamos primero por fecha (AAAA-MM)
            if indice > actual["indice_tiempo"]:
                por_estacion[clave1] = r
            elif indice == actual["indice_tiempo"] and precio_num > actual["precio_num"]:
                # misma fecha, preferimos el precio más alto
                por_estacion[clave1] = r

    filas_por_estacion = list(por_estacion.values())

    # --- SEGUNDO CORTE: MIN y MAX POR CIUDAD Y PRODUCTO, CONTROLANDO DESVIACIÓN ---

    # Agrupamos todas las estaciones por (localidad, categoria)
    grupos_ciudad_prod: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in filas_por_estacion:
        loc = r["localidad"]
        cat = r["categoria"]
        if not loc or not cat:
            continue
        grupos_ciudad_prod[(loc, cat)].append(r)

    filas_finales = []

    for (loc, cat), lista in grupos_ciudad_prod.items():
        if not lista:
            continue

        # Precio máximo real entre estaciones de esa ciudad/producto
        max_price = max(r["precio_num"] for r in lista)

        # Filtramos outliers demasiado bajos:
        # nos quedamos solo con precios >= max_price - MAX_DESVIACION
        candidatos = [
            r for r in lista
            if r["precio_num"] >= max_price - MAX_DESVIACION
        ]

        if not candidatos:
            # Por seguridad; en la práctica, el propio max siempre entra
            candidatos = lista

        # Elegimos MAX y MIN dentro de los candidatos
        max_row = max(candidatos, key=lambda r: r["precio_num"])
        min_row = min(candidatos, key=lambda r: r["precio_num"])

        # Clonamos y marcamos cada fila con indice_precio = MAX/MIN
        for row, label in ((max_row, "MAX"), (min_row, "MIN")):
            nuevo = row.copy()
            nuevo["indice_precio"] = label
            filas_finales.append(nuevo)

    # Máximo teórico: 2 (MAX/MIN) × 4 productos × 2 ciudades = 16 filas
    # Ordenamos por ciudad, producto y luego MAX/MIN para que quede prolijo
    filas_finales.sort(
        key=lambda r: (
            r["localidad"],
            r["categoria"],
            r["indice_precio"],  # MIN antes que MAX o al revés según te guste
        )
    )

    # Escritura de precios.txt
    with output_path.open("w", encoding="utf-8", newline="") as out:
        w = csv.writer(out, delimiter="|")
        w.writerow([
            "indice_precio",     # NUEVA COLUMNA: MIN o MAX
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
                r["indice_precio"],
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
