# Registro de cambios

## 0.4.0 - 2026-07-17

- Instaladores fijados para whisper.cpp 1.8.6 y Piper 1.4.2.
- Modelo Whisper small Q5_1 con SHA-256 verificada.
- Voz Piper mexicana de alta calidad administrada fuera de Git.
- Adaptador Piper actualizado a la CLI vigente.
- Medición real Piper→Whisper en EC2 y transcripción española verificada.
- Bienvenida Piper convertida a WAV mono telefónico de 8 kHz y reproducción desde ARI.
- Receptor WebSocket ARI estable durante periodos sin llamadas.
- Grabación ARI acotada, transcripción local con Whisper y eliminación inmediata
  del audio procesado sin registrar en disco el contenido hablado.

## 0.3.0 - 2026-07-17

- Cliente REST de Asterisk ARI con operaciones explícitamente permitidas.
- Interpretación validada de eventos de llamada relevantes.
- Sesiones independientes y seguras para concurrencia.
- Transferencia PJSIP controlada y límite máximo de duración.
- Pruebas ARI simuladas sin llamadas ni puertos públicos.
- Instalador reproducible de Asterisk 22.10.1 con SHA-256 fijada.
- Plantillas ARI limitadas a localhost y dialplan de laboratorio.
- Espera acotada de disponibilidad ARI después de reiniciar Asterisk.
- Cliente WebSocket autenticado para eventos ARI con reintentos finitos.
- Credencial ARI transferida al entorno protegido del servicio y diagnóstico autenticado.
- Orquestador idempotente de StasisStart/StasisEnd y cierre de llamadas vencidas.
- Logging ARI visible en journald y permisos corregidos para CDR de Asterisk.

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
