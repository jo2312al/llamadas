# Registro de cambios

## 0.2.0 - 2026-07-17

- VAD ligero por energía RMS para PCM de 16 bits.
- Conversión validada de PCM a WAV.
- Adaptadores de whisper.cpp y Piper con timeout y errores controlados.
- Caché de síntesis determinística y pruebas sin modelos reales.
- Diagnóstico de binarios y modelos configurados.
- Modo no interactivo supervisable por systemd y apagado mediante señales.
- El workflow ejecuta el script de despliegue perteneciente a la revisión validada.
- Instalación y despliegue habilitan el servicio para iniciar con EC2.

## 0.1.0 - 2026-07-17

- Núcleo Pydantic y máquina de estados explícita.
- Persistencia SQLite y migración inicial idempotente.
- Cliente Ollama con esquema JSON, extracción y reintento finito.
- CLI de migración, conversación y salud.
- Pruebas unitarias, CI, systemd y scripts de despliegue/operación.
- Documentación de arquitectura, seguridad y consumo estimado.
