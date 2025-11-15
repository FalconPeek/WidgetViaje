#ifndef UI_H
#define UI_H

#include <windows.h>
#include <windowsx.h>
#include <shellapi.h>
#include <stdio.h>
#include "tda.h"

static int gLineHeight = 16;
static const int gTopMargin = 5;

LRESULT CALLBACK WndProc(HWND hwnd, UINT Message, WPARAM wParam, LPARAM lParam) {
    switch (Message) {

    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);

        RECT client;
        GetClientRect(hwnd, &client);

        TEXTMETRIC tm;
        GetTextMetrics(hdc, &tm);
        gLineHeight = tm.tmHeight + 2;

        char buffer[1024];
        formatearEstacionesEnTexto(buffer, sizeof(buffer));

        char *line = strtok(buffer, "\n");
        int y = gTopMargin;

        while (line != NULL) {
            RECT r;
            r.left   = 5;
            r.top    = y;
            r.right  = client.right - 5;
            r.bottom = y + gLineHeight;

            DrawTextA(hdc, line, -1, &r, DT_LEFT | DT_VCENTER | DT_SINGLELINE);

            y += gLineHeight;
            line = strtok(NULL, "\n");
        }

        EndPaint(hwnd, &ps);
        break;
    }

    case WM_LBUTTONDOWN: {
        int y = GET_Y_LPARAM(lParam);
        int fila = (y - gTopMargin) / gLineHeight;

        // 0..3 -> abrir Maps
        if (fila >= 0 && fila <= 3) {
            PrecioTipo tipo;
            switch (fila) {
                case 0: tipo = PRECIO_NAFTA_MAX;   break;
                case 1: tipo = PRECIO_NAFTA_MIN;   break;
                case 2: tipo = PRECIO_DIESEL_MAX;  break;
                case 3: tipo = PRECIO_DIESEL_MIN;  break;
            }

            double lat, lon;
            if (obtenerCoordenadas(tipo, &lat, &lon)) {
                char url[256];
                snprintf(
                    url, sizeof(url),
                    "https://www.google.com/maps/search/?api=1&query=%f,%f",
                    lat, lon
                );
                ShellExecuteA(NULL, "open", url, NULL, NULL, SW_SHOWNORMAL);
            }
        } else {
            // Cualquier otro click cierra el widget
            PostQuitMessage(0);
        }

        break;
    }

    case WM_DESTROY:
        PostQuitMessage(0);
        break;

    default:
        return DefWindowProc(hwnd, Message, wParam, lParam);
    }
    return 0;
}

#endif
