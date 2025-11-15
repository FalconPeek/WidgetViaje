#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "tda.h"

static tPrecioInfo gPrecios[PRECIO_COUNT];

static void trim(char *s) {
    int len = (int)strlen(s);
    while (len > 0 && (s[len-1] == '\n' || s[len-1] == '\r' || s[len-1] == ' ')) {
        s[len-1] = '\0';
        len--;
    }
}

int cargarEstacionesDesdeArchivo(const char *nombreArchivo) {
    // Abrimos log
    FILE *log = fopen("widget_log.txt", "w");
    if (log) {
        fprintf(log, "Abriendo archivo: %s\n", nombreArchivo);
    }
	int i;
    for (i = 0; i < PRECIO_COUNT; i++) {
        gPrecios[i].valido = 0;
    }

    FILE *f = fopen(nombreArchivo, "r");
    if (!f) {
        if (log) {
            fprintf(log, "ERROR: fopen() fallo, no se pudo abrir el archivo.\n");
            fclose(log);
        }
        return 0;
    }

    char linea[512];
    int numLinea = 0;

    while (fgets(linea, sizeof(linea), f)) {
        numLinea++;
        if (log) {
            fprintf(log, "Linea %d cruda: %s", numLinea, linea);
        }

        char *indice_precio   = strtok(linea, "|");
        char *indice_tiempo   = strtok(NULL, "|");
        char *direccion       = strtok(NULL, "|");
        char *localidad       = strtok(NULL, "|");
        char *producto        = strtok(NULL, "|");
        char *precioStr       = strtok(NULL, "|");
        char *inEmpBandera    = strtok(NULL, "|");
        char *empresa         = strtok(NULL, "|");
        char *latStr          = strtok(NULL, "|");
        char *lonStr          = strtok(NULL, "|");

        if (!indice_precio || !producto || !precioStr || !latStr || !lonStr) {
            if (log) fprintf(log, "  -> linea ignorada (faltan campos clave)\n");
            continue;
        }

        trim(indice_precio);
        trim(producto);
        if (localidad) trim(localidad);
        if (empresa)   trim(empresa);
        trim(precioStr);
        trim(latStr);
        trim(lonStr);

        int esNafta  = (strcmp(producto, "Nafta (súper) entre 92 y 95 Ron") == 0 ||
                        strcmp(producto, "Nafta (súper) entre 92 y 95 Ron") == 0);
        int esDiesel = (strcmp(producto, "Gas Oil Grado 3") == 0);

        if (log) {
            fprintf(log,
                    "  -> producto='%s', indice='%s', precio='%s', lat='%s', lon='%s'\n",
                    producto, indice_precio, precioStr, latStr, lonStr);
        }

        PrecioTipo tipo;
        if (esNafta) {
            if (strcmp(indice_precio, "MAX") == 0)
                tipo = PRECIO_NAFTA_MAX;
            else if (strcmp(indice_precio, "MIN") == 0)
                tipo = PRECIO_NAFTA_MIN;
            else {
                if (log) fprintf(log, "  -> Nafta pero indice_precio NO es MAX/MIN, se ignora.\n");
                continue;
            }
        } else if (esDiesel) {
            if (strcmp(indice_precio, "MAX") == 0)
                tipo = PRECIO_DIESEL_MAX;
            else if (strcmp(indice_precio, "MIN") == 0)
                tipo = PRECIO_DIESEL_MIN;
            else {
                if (log) fprintf(log, "  -> Diesel pero indice_precio NO es MAX/MIN, se ignora.\n");
                continue;
            }
        } else {
            if (log) fprintf(log, "  -> producto no relevante (no es Nafta Super ni Gas Oil Grado 3).\n");
            continue;
        }

        double precio = atof(precioStr);
        double lat    = atof(latStr);
        double lon    = atof(lonStr);

        tPrecioInfo *info = &gPrecios[tipo];

        if (!info->valido) {
            info->valido = 1;
            strncpy(info->producto, producto, sizeof(info->producto)-1);
            info->producto[sizeof(info->producto)-1] = '\0';

            if (direccion) {
                strncpy(info->direccion, direccion, sizeof(info->direccion)-1);
                info->direccion[sizeof(info->direccion)-1] = '\0';
            } else {
                info->direccion[0] = '\0';
            }

            if (localidad) {
                strncpy(info->localidad, localidad, sizeof(info->localidad)-1);
                info->localidad[sizeof(info->localidad)-1] = '\0';
            } else {
                info->localidad[0] = '\0';
            }

            if (empresa) {
                strncpy(info->empresa, empresa, sizeof(info->empresa)-1);
                info->empresa[sizeof(info->empresa)-1] = '\0';
            } else {
                info->empresa[0] = '\0';
            }

            info->precio = precio;
            info->lat    = lat;
            info->lon    = lon;

            if (log) fprintf(log, "  -> NUEVO valor para tipo %d: precio=%.2f\n", tipo, precio);
        } else {
            if ((tipo == PRECIO_NAFTA_MAX || tipo == PRECIO_DIESEL_MAX) && precio > info->precio) {
                info->precio = precio;
                info->lat    = lat;
                info->lon    = lon;
                if (log) fprintf(log, "  -> ACTUALIZA MAX tipo %d: precio=%.2f\n", tipo, precio);
            } else if ((tipo == PRECIO_NAFTA_MIN || tipo == PRECIO_DIESEL_MIN) && precio < info->precio) {
                info->precio = precio;
                info->lat    = lat;
                info->lon    = lon;
                if (log) fprintf(log, "  -> ACTUALIZA MIN tipo %d: precio=%.2f\n", tipo, precio);
            } else {
                if (log) fprintf(log, "  -> valor no mas extremo, se mantiene el existente.\n");
            }
        }
    }

    fclose(f);

    int encontrados = 0;
	int j;
    for (j = 0; j < PRECIO_COUNT; j++) {
        if (gPrecios[j].valido) encontrados++;
    }

    if (log) {
        fprintf(log, "Resumen: encontrados=%d (NaftaMax=%d, NaftaMin=%d, DieselMax=%d, DieselMin=%d)\n",
                encontrados,
                gPrecios[PRECIO_NAFTA_MAX].valido,
                gPrecios[PRECIO_NAFTA_MIN].valido,
                gPrecios[PRECIO_DIESEL_MAX].valido,
                gPrecios[PRECIO_DIESEL_MIN].valido);
        fclose(log);
    }

    // Consideramos éxito si encontramos AL MENOS un precio relevante
    return (gPrecios[PRECIO_NAFTA_MAX].valido ||
        gPrecios[PRECIO_NAFTA_MIN].valido ||
        gPrecios[PRECIO_DIESEL_MAX].valido ||
        gPrecios[PRECIO_DIESEL_MIN].valido);

}
