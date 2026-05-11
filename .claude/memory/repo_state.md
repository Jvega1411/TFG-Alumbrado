---
name: Estado del repositorio — TFG Alumbrado
description: Qué está implementado y testeado, qué son stubs, qué falta por diseñar
type: project
---

**Repo:** C:\Users\sebas\TFG-Alumbrado\
**Tests:** 35 passed — ejecutar con C:\Users\sebas\AppData\Local\Python\pythoncore-3.14-64\Scripts\pytest.exe

**Why:** El plan de implementación previo fue descartado por desconocer el estado del repo. Esta memoria evita repetir ese error.

**Implementado y con tests:**
- fins/frame.py — build_memory_read_frame, parse_fins_response, parse_words_to_int_list, MEMORY_AREA_CODES
- fins/client.py — FINSClient (UDP, bind local port, context manager, read_memory_area, read_dm/w/h_range)
- fins/diagnostics.py — hexdump, decode_endcode, endcode_ok
- config/settings.py — Config class, carga desde .env, validate()
- tests/test_frame.py, test_client.py, test_settings.py — 35 tests pasando

**Stubs vacíos (TODO):**
- acquisition/poller.py — loop de adquisición (usa FINSClient + SQLAlchemy)
- model/estados.py — modelos SQLAlchemy para BD_Estados y BD_Historizacion
- schemas/lectura.py — Pydantic schemas para API REST
- api/routes.py — FastAPI endpoints (solo lectura/diagnóstico)
- main.py — arranque: Config.validate() → SQLAlchemy → poller → FastAPI

**Pendiente de diseño (no hay ficheros SQL ni migraciones):**
- Esquema de tablas BD_Estados y BD_Historizacion
- Alembic setup y primera migración

**How to apply:** Antes de implementar cualquier capa, verificar que fins/ y config/ ya existen y usarlos tal cual. No reimplementar lo que ya está.
