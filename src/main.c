#include <windows.h>
#include <string.h>
#include "tda.h"
#include "net.h"
#include "ui.h"

#define PRECIOS_PATH "backend/precios.txt"


int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    WNDCLASSEX wc;
    HWND hwnd;
    MSG Msg;

    const char *URL_PRECIOS = "https://miMiniWeb/precios.txt"; // Cambiá por tu URL real

    // Best-effort: intentamos descargar; si falla, usamos el precios.txt local
    descargarArchivoPrecios(URL_PRECIOS);

    if (!cargarEstacionesDesdeArchivo(PRECIOS_PATH)) {
        MessageBox(NULL,
                   "No se pudieron cargar los precios desde precios.txt.\n"
                   "Revisá que el archivo exista y tenga datos válidos.",
                   "Widget Viaje",
                   MB_ICONWARNING | MB_OK);
    }

    memset(&wc, 0, sizeof(wc));
    wc.cbSize        = sizeof(WNDCLASSEX);
    wc.lpfnWndProc   = WndProc;
    wc.hInstance     = hInstance;
    wc.hCursor       = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW+1);
    wc.lpszClassName = "FuelWidgetClass";
    wc.hIcon         = LoadIcon(NULL, IDI_APPLICATION);
    wc.hIconSm       = LoadIcon(NULL, IDI_APPLICATION);

    if (!RegisterClassEx(&wc)) {
        MessageBox(NULL, "Window Registration Failed!", "Error!", MB_ICONEXCLAMATION | MB_OK);
        return 0;
    }

    int width  = 350;
    int height = 230;

    int screenW = GetSystemMetrics(SM_CXSCREEN);
    int screenH = GetSystemMetrics(SM_CYSCREEN);
    int x = screenW - width - 20;
    int y = 20;

    hwnd = CreateWindowEx(
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
        "FuelWidgetClass",
        NULL,
        WS_POPUP,
        x, y, width, height,
        NULL, NULL, hInstance, NULL
    );

    if (hwnd == NULL) {
        MessageBox(NULL, "Window Creation Failed!", "Error!", MB_ICONEXCLAMATION | MB_OK);
        return 0;
    }

    ShowWindow(hwnd, nCmdShow);
    UpdateWindow(hwnd);

    while (GetMessage(&Msg, NULL, 0, 0) > 0) {
        TranslateMessage(&Msg);
        DispatchMessage(&Msg);
    }

    return (int)Msg.wParam;
}
