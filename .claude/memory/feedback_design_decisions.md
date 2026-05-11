---
name: Decisiones de diseño — TFG Alumbrado
description: Decisiones tomadas, por qué, y cómo aplicarlas en el futuro
type: feedback
---

**No asumir nada del dominio sin confirmación explícita**
**Why:** Se asumió "alumbrado público municipal" cuando es nave industrial. Se asumió terminología ("tramos") cuando el término correcto es "cerchas". Cada asunción incorrecta contamina spec, plan y código.
**How to apply:** Marcar cualquier inferencia como `⚠️ ASUNCIÓN: [descripción]` y pedir confirmación antes de continuar.

---

**Leer el código existente antes de diseñar o proponer**
**Why:** Se redactó un plan completo de implementación que rehacía fins/ desde cero, sin saber que ya existía y tenía tests. El plan fue descartado íntegramente.
**How to apply:** Al inicio de cualquier tarea en este repo, leer los ficheros relevantes antes de proponer nada. Especialmente: fins/, config/, tests/.

---

**Área codes FINS: usar word access (0xB0–0xB3), no bit access (0x30–0x33)**
**Why:** Los códigos 0x30–0x33 son para acceso a bit individual. Para leer words completas (que es siempre el caso en este proyecto) hay que usar 0xB0–0xB3. DM usa 0x82 para ambos. WR=0xB1 y HR=0xB2 confirmados contra PLC real.
**How to apply:** La extracción de bits se hace en software sobre el word leído. Nunca usar área code de bit access para leer words.

---

**SQLite en Fase 1, SQL Server Express en Fase 2 — mismos modelos SQLAlchemy**
**Why:** SQL Server Express no corre en Linux (RPi es Ubuntu). SQLite es el motor provisional. SQLAlchemy abstrae el motor, Alembic gestiona la migración de esquema.
**How to apply:** No escribir queries, tipos o constraints específicos de un solo motor. Todo debe funcionar con SQLite y SQL Server sin cambios de código.

---

**Polling: log por cambio + heartbeat cada 5 min, no polling fijo**
**Why:** El CJ2M es antiguo y no puede recibir polling agresivo. El sistema de alumbrado es estable (99% del tiempo sin cambios). Log fijo llena el disco con filas idénticas.
**How to apply:** Solo escribir en BD cuando un valor cambia O cuando pasa el intervalo de heartbeat. Polling FINS cada 10s, heartbeat/snapshot cada 5min.

---

**Revisión multi-agente antes de push**
**Why:** Preferencia explícita del usuario para garantizar calidad antes de integrar.
**How to apply:** Tras implementación de Codex, desplegar en paralelo: security auditor + code corrector + senior programmer. Solo push tras aprobación del senior.
