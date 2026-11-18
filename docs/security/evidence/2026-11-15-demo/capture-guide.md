# Guía de capturas DLP/DRP

- Ejecución: 2026-11-16T04:05:52+00:00
- Commit: 77d7bc8
- Suite exit code: 1 (1 = hay FAIL, esperado)
- results.json SHA-256: 4DCD13E505726982AF07CFBD050670DBC94D64BFBD63075DDD372D104544E68F
- Carpeta: C:\Users\dell\Documents\GitHub\frostbase-v2\docs\security\evidence\2026-11-15-demo
## Capturas principales

| Prueba | Bloque listo | Captura PNG | Qué debe verse |
| --- | --- | --- | --- |
| DLP-01 | `captures\DLP-01.txt` | `captures\DLP-01.png` | 401 anónimo, 403 RBAC, 401 token, PII redactada |
| DLP-02 | `captures\DLP-02.txt` | `captures\DLP-02.png` | estado CO, active=false, FK, recovered=true |
| DR-01 | `captures\DR-01.txt` | `captures\DR-01.png` | expected_digest == actual_digest, differences=[] |
| DR-02 | `captures\DR-02.txt` | `captures\DR-02.png` | exists_after_drop=false, checksums_match=true, rto_seconds |

## Cómo capturar manualmente

1. Abra `captures\<PRUEBA>.txt` en un editor o terminal.
2. Maximice la ventana y use una fuente legible (14-16 pt).
3. Verifique que se vean la cabecera, el comando y todas las líneas de resultado.
4. Capture con `Win + Shift + S` y guarde como `captures\<PRUEBA>.png`.
5. Ejecute de nuevo este script con `-SkipRun` para incluir los PNG en `manifest.json`.

## Reglas de evidencia

- No oculte los `[FALLO]`: son hallazgos de seguridad, no errores del procedimiento.
- No muestre PII real. La suite ya entrega una muestra redactada.
- No recorte el comando ni la cabecera: son parte de la evidencia.
- Use el mismo `results.json` para las cuatro capturas y muestre su SHA-256.
