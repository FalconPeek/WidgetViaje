#ifndef TDA_H
#define TDA_H

typedef enum {
    PRECIO_NAFTA_MAX = 0,
    PRECIO_NAFTA_MIN,
    PRECIO_DIESEL_MAX,
    PRECIO_DIESEL_MIN,
    PRECIO_COUNT
} PrecioTipo;

typedef struct {
    int    valido;
    char   producto[32];
    char   direccion[128];
    char   localidad[64];
    char   empresa[64];
    double precio;
    double lat;
    double lon;
} tPrecioInfo;

// Lee precios.txt (formato con |) y llena los 4 precios clave
int cargarEstacionesDesdeArchivo(const char *nombreArchivo);

// Arma TODO el texto del widget (rango de precios + presupuesto viaje + vehículo)
void formatearEstacionesEnTexto(char buffer[], int bufferSize);

// Devuelve lat/lon para abrir Maps cuando clickeás una de las 4 primeras líneas
int obtenerCoordenadas(PrecioTipo tipo, double *lat, double *lon);

#endif
