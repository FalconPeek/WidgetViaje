#include <windows.h>
#include <wininet.h>
#include <stdio.h>
#include "net.h"

int descargarArchivoPrecios(const char *url) {
    HINTERNET hInternet = InternetOpen(
        "WidgetCombustible",
        INTERNET_OPEN_TYPE_PRECONFIG,
        NULL,
        NULL,
        0
    );
    if (!hInternet) {
        return 0;
    }

    HINTERNET hFile = InternetOpenUrl(
        hInternet,
        url,
        NULL,
        0,
        INTERNET_FLAG_RELOAD,
        0
    );
    if (!hFile) {
        InternetCloseHandle(hInternet);
        return 0;
    }

    FILE *f = fopen("precios.txt", "wb");
    if (!f) {
        InternetCloseHandle(hFile);
        InternetCloseHandle(hInternet);
        return 0;
    }

    char buffer[4096];
    DWORD bytesRead = 0;
    BOOL ok;

    do {
        ok = InternetReadFile(hFile, buffer, sizeof(buffer), &bytesRead);
        if (!ok) {
            fclose(f);
            InternetCloseHandle(hFile);
            InternetCloseHandle(hInternet);
            return 0;
        }
        if (bytesRead > 0) {
            fwrite(buffer, 1, bytesRead, f);
        }
    } while (bytesRead > 0);

    fclose(f);
    InternetCloseHandle(hFile);
    InternetCloseHandle(hInternet);
    return 1;
}
