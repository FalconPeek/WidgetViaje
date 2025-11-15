import csv
import time
import urllib.request
from pathlib import Path

# URL DIRECTA de descarga del CSV (link "DESCARGAR" del dataset oficial)
CSV_DOWNLOAD_URL = (
    "http://datos.energia.gob.ar/dataset/1c181390-5045-475e-94dc-410429be4b17/resource/80ac25de-a44a-4445-9215-090cf55cfda5/download/precios-en-surtidor-resolucin-3142016.csv"
)

# Nombre del CSV local (el archivo que guardamos en disco)
LOCAL_CSV = Path("precios-en-surtidor-resolucin-3142016.csv")

# Salida que va a leer tu app en C
OUTPUT_TXT = Path("precios.txt")

# Tiempo máximo de vida del CSV local (1 hora)
REFRESH_SECONDS = 3600

# Filtros de negocio
LOCALIDADES_PERMITIDAS = {"CORRIENTES", "PASO DE LOS LIBRES"}
EMPRESAS_PERMITIDAS = {"2", "4", "28"}  # 2=YPF, 4=Shell, 28=PUMA


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
            # Lo borramos como pediste (no es obligatorio, pero tampoco molesta)
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

        # --- FILTROS ---

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

        filas.append({
            "indice_tiempo": row.get("indice_tiempo", ""),
            "direccion": row.get("direccion", ""),
            "localidad": loc,
            "producto": row.get("producto", ""),
            "tipohorario": row.get("tipohorario", ""),
            "precio": row.get("precio", ""),
            "idempresabandera": row.get("idempresabandera", ""),
            "empresabandera": row.get("empresabandera", ""),
            "latitud": row.get("latitud", ""),
            "longitud": row.get("longitud", "")
            #"geojson": row.get("geojson", ""),
        })

    # Orden
    filas.sort(
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
            #"tipohorario",
            "precio",
            "idempresabandera",
            "empresabandera",
            "latitud",
            "longitud"
            #"geojson",
        ])

        for r in filas:
            w.writerow([
                r["indice_tiempo"],
                r["direccion"],
                r["localidad"],
                r["producto"],
                #r["tipohorario"],
                r["precio"],
                r["idempresabandera"],
                r["empresabandera"],
                r["latitud"],
                r["longitud"]
                #r["geojson"],
            ])


def generar_precios_txt():
    """Pipeline completo: asegura CSV local actualizado y genera precios.txt."""
    descargar_csv_si_necesario()

    with LOCAL_CSV.open("r", encoding="utf-8", newline="") as f:
        _procesar_stream_csv(f, OUTPUT_TXT)

    print(f"[INFO] precios.txt generado en {OUTPUT_TXT.resolve()}")


if __name__ == "__main__":
    generar_precios_txt()