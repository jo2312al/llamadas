# Agente telefónico de Hotel Villa Margaritas

Primera versión del núcleo determinístico para recopilar solicitudes de reservación en
español. Ollama solo interpreta lenguaje; Python controla estados, validaciones,
disponibilidad, tarifas, persistencia y transferencias. Esta fase no recibe tarjetas ni
confirma reservaciones de forma autónoma.

## Arquitectura y flujo

La interfaz de telefonía entregará audio a `whisper.cpp`; el texto pasa al adaptador de
Ollama con salida JSON validada por Pydantic. La máquina de estados decide una sola
acción, consulta servicios autorizados y guarda una **solicitud** en SQLite. Piper
produce la respuesta. Todos los adaptadores pueden reemplazarse por dobles de prueba.

Flujo: bienvenida → intención → recopilación → validación → disponibilidad → opciones
→ confirmación → guardado → notificación → finalización o transferencia.

## Requisitos e instalación local

- Python 3.11 o superior
- SQLite 3
- Opcionales por fase: Ollama, whisper.cpp, Piper y Asterisk

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp configuracion/configuracion_ejemplo.yaml configuracion/configuracion.yaml
python -m aplicacion.principal migrar --configuracion configuracion/configuracion.yaml
pytest
python -m aplicacion.principal salud --configuracion configuracion/configuracion.yaml
```

No se guardan secretos en YAML. Use `AGENTE_RUTA_BASE_DATOS`, `AGENTE_URL_OLLAMA` y
el archivo externo `/etc/agente-telefonico/agente-telefonico.env`.

## EC2, modelos y consumo esperado

La VM inspeccionada usa Amazon Linux 2023, 2 vCPU, 7.6 GiB RAM y 50 GiB de disco. Se
recomienda `qwen2.5:3b-instruct-q4_K_M`: aproximadamente 2.5–3.5 GiB residentes. Para
STT, `whisper.cpp` con `small` cuantizado Q5 (aprox. 0.6–1.2 GiB durante inferencia),
idioma español y segmentos por VAD. Piper suele requerir menos de 0.5 GiB. Asterisk y
Python/SQLite deberían permanecer bajo 0.4 GiB. El pico combinado esperado es 5–6 GiB;
se debe procesar una llamada a la vez inicialmente y agregar 2 GiB de swap cifrado o
supervisado solo tras medir.

## Despliegue y GitHub Actions

El workflow valida Ruff, Black, sintaxis, YAML y pytest antes de ejecutar el script
versionado. Configure en GitHub: **Settings → Secrets and variables → Actions → New
repository secret**:

- `EC2_HOST`: nombre DNS de EC2.
- `EC2_USER`: `ec2-user`.
- `EC2_SSH_PRIVATE_KEY`: clave de despliegue independiente (no una ruta Windows).
- `EC2_RUTA_PROYECTO`: `/opt/agente-telefonico-hotel`.

Instale primero los paquetes base con `scripts/instalar_servidor.sh`, clone el
repositorio en la ruta indicada, copie la configuración sin sobrescribir una existente,
instale la unidad systemd y habilítela. `scripts/desplegar.sh` usa bloqueo, revisión
exacta, migración, salud y rollback. No despliega si la validación falla.

## Audio local, Whisper y Piper

La Fase 2 incorpora un VAD por energía RMS para PCM S16LE, conversión WAV, ejecución
de `whisper.cpp` y Piper sin shell, timeouts estrictos y caché TTS por SHA-256. El VAD
no sustituye a un clasificador neuronal en ambientes muy ruidosos; ajuste
`umbral_voz_rms` con grabaciones controladas antes de recibir llamadas.

Las rutas y límites están en `configuracion/configuracion_ejemplo.yaml`. Para una prueba
local, coloque los binarios y modelos fuera de Git, ejecute `salud` y use WAV mono de
16 kHz. Los adaptadores rechazan archivos ausentes, salidas vacías y procesos que
excedan el tiempo. Los modelos nunca se descargan durante las pruebas automatizadas.

## Asterisk y Ollama

Mantenga ARI y Ollama en `127.0.0.1`; no publique sus puertos. Asterisk debe entregar
audio PCM mono de 8/16 kHz a una sesión aislada y conservar una extensión de
transferencia. Ollama debe usar el prompt de `prompts/`. La telefonía en tiempo real y
la conexión ARI permanecen para la Fase 3.

## Operación, seguridad y privacidad

`make validar`, `make probar`, `make migrar`, `make estado` y `make respaldar` son los
comandos habituales. Los respaldos usan la API `.backup` de SQLite. La restauración
requiere `--confirmar`, valida integridad y conserva copia previa. El servicio usa un
usuario sin login, filesystem protegido y rutas escribibles limitadas. No registre
tokens, audio binario, tarjetas ni teléfonos completos; defina retención y consentimiento
antes de producción.

Problemas comunes: revise `journalctl -u agente-telefonico`, espacio, permisos de
`datos/`, disponibilidad local de Ollama y que el modelo configurado aparezca en
`ollama list`. Esta versión ofrece flujo terminal y persistencia; audio, telefonía,
notificaciones reales, disponibilidad autorizada y llamadas externas siguen pendientes.
