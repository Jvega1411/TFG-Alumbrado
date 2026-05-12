# CLAUDE.md — alumbrado-gateway

## Proyecto
Sistema read-only de supervisión y explotación de datos sobre alumbrado industrial en TVITEC.

Lee estados desde un PLC Omron Sysmac CJ2M CPU32 mediante FINS/UDP y persiste datos en SQL Server para consulta, historización y análisis.

No es sistema de mando. No debe modificar el PLC ni la instalación.

## Knowledge Base — Vault Obsidian

El vault de conocimiento del proyecto vive en un repositorio git separado: `TFG-Alumbrado-vault`.
Ruta en esta máquina: ver `LOCAL_PATHS.md` en la raíz del vault (fichero local, no commiteado).

### Protocolo de sesión — obligatorio en cada sesión

1. Leer `AGENTS.md` en la raíz del vault. **Siempre. Sin excepciones.**
2. Leer `10_Daily/YYYY-MM-DD.md` de hoy completo. Si no existe, crearlo desde la plantilla en `AGENTS.md`.
3. Leer `00_Index/Pending Questions.md` antes de empezar cualquier trabajo.
4. Leer `graph/GRAPH_REPORT.md` si se necesita contexto de estructura de código.
5. Trabajar en el repo de código.
6. Añadir bloque de sesión a la nota diaria al terminar.
7. Actualizar `00_Index/Pending Questions.md` — añadir items, tachar resueltos.
8. **Commitear el vault solo si hubo trabajo real** (decisiones, razonamiento, aprendizaje, revisión de planes — aunque no haya código). Sesiones de lectura trivial sin trabajo: no commitear. Mensaje: `git commit -m "session: YYYY-MM-DD Claude Code"`.

### Contrato de escritura

- **Formato decisiones: What / Why / Where.** Where = ruta exacta de fichero + línea en `TFG-Alumbrado`.
- **Tono educativo.** Sebas es estudiante. Explicar decisiones técnicas en lenguaje llano.
- **Enlazar conceptos.** Primera aparición de un término técnico → `[[60_Concepts/NombreConcepto]]`. Crear el fichero si no existe.
- **Snippets comentados para el "por qué"**, no para el "qué". Escritos para Sebas, no para el compilador.

### Regla newer-prevails

Si dos notas se contradicen, gana la de fecha más reciente.

**Excepción — estas fuentes siempre ganan sobre cualquier nota:**
- `Tabla_ES.html` — mapa de variables PLC (verdad de dirección y nombre)
- `LD_Ilum.pdf` — diagrama ladder (verdad de comportamiento)
- Capturas smoke en `data/smoke_fins/` — **solo para valores observados** (e.g. "W25=1 fue leído"). La interpretación semántica (e.g. "W25=1 significa que la fotocélula está activa") sigue requiriendo `LD_Ilum.pdf` o decisión explícita de Sebas.
- Decisión explícita de Sebas (marcada "Decisión Sebas" en la nota)

### Contenido del vault

| Carpeta | Propósito |
|---|---|
| `00_Index/` | Project Map (estático) + Pending Questions (actualizar cada sesión) |
| `10_Daily/` | Una nota por día · múltiples sesiones se añaden al mismo fichero |
| `20_Decisions/` | Decisiones largas que no caben en la nota diaria |
| `30_PLC/` | Variables validadas, pendientes y curated smoke findings |
| `40_Architecture/` | Fase 2 overview, MQTT payload, SQLite schema, API contract |
| `50_AI_Context/` | Reglas compartidas, contexto por agente (Claude y Codex) |
| `60_Concepts/` | Conceptos técnicos explicados para Sebas — crece orgánicamente |
| `graph/` | `GRAPH_REPORT.md` (agentes) y `graph.html` (gitignored, Sebas) |

### Qué NO escribir en el vault

- Contenido de `.env`, credenciales, contraseñas, connection strings
- Ficheros JSON raw de smoke (`data/smoke_fins/*.json` quedan en este repo)
- Ficheros generados (`__pycache__`, `.db`, `.venv`, `graph.json`)

### Graphify

Graphify indexa ambos repos y genera `graph/GRAPH_REPORT.md` en el vault.
**No modifica este fichero ni `AGENTS.md` automáticamente.** Cualquier sugerencia va a `graph/AGENT_SUGGESTIONS.md` para revisión manual de Sebas.

## Contexto técnico

### PLC
- Omron Sysmac CJ2M CPU32, IP 192.168.250.1, FINS node 1
- FINS/UDP puerto 9600
- Instalación: 1104 luminarias, 172 cerchas, 112 secciones
- Jerarquía: Sección (112) → Cercha (172) → Luminaria (1104)
- El PLC expone estado a nivel de sección (H11–H31, 112 bits por grupo de estado)

### Nodo OT — Raspberry Pi (Ubuntu 24.04 LTS, aarch64)
- eth0: red OT 192.168.250.56, FINS node 56 — habla FINS con el PLC
- eth1 (adaptador USB-Eth): subred de enlace hacia el Lenovo (⚠️ PENDIENTE confirmar nombre exacto de interfaz y subred)
- Usuarios: `master` (admin/sudo), `gwsvc` (servicio, sin sudo)
- Dev: `/home/master/dev/alumbrado-gateway`
- Prod: `/opt/alumbrado-gateway`
- Rol Fase 1: FINS reader + SQLite + FastAPI (todo en RPi)
- Rol Fase 2: FINS reader + paho-mqtt publisher únicamente (sin BD ni API)

### Nodo IT — Lenovo S500 (Windows 10, Intel i3)
- NIC1: subred de enlace con RPi (⚠️ PENDIENTE confirmar IP, propuesta 10.0.0.2/30)
- NIC2: red corporativa de fábrica
- Rol Fase 2: broker Mosquitto + SQL Server Express + FastAPI
- Asignado por informática: 2026-05-11

### Principio de aislamiento IT/OT (normativa)
- Comunicación estrictamente unidireccional OT→IT: la RPi solo publica MQTT, nunca recibe del Lenovo
- El Lenovo nunca inicia conexión hacia la RPi ni tiene visibilidad de 192.168.250.0/24
- Ver `docs/red_ot_aislamiento.md` para comandos de firewall/sysctl de la RPi

### Stack
- BD: `BD_Estados`, `BD_Historizacion`
- Python 3.x (target producción: 3.12.x en RPi), SQLAlchemy 2.0, Alembic

## Estrategia por fases

**Fase 1 — RPi standalone:** Python + SQLAlchemy + SQLite + FastAPI, todo en la RPi.
- SQL Server Express no corre en Linux; SQLite es el motor provisional.
- Los modelos SQLAlchemy se escriben una sola vez y son válidos para ambas fases.
- `BD_Estados` y `BD_Historizacion` son dos ficheros `.db`.

**Fase 2 — arquitectura dos nodos (RPi + Lenovo):**
- RPi adelgaza: solo FINS reader + paho-mqtt publisher. Sin BD ni API.
- Lenovo: broker Mosquitto recibe los datos, SQL Server Express los persiste, FastAPI los expone.
- Transporte OT→IT: MQTT sobre subred de enlace RPi↔Lenovo (unidireccional).
- Migración de esquema: `alembic upgrade head` en el Lenovo. Solo cambia la connection string en `.env`.

No usar engines ni queries específicas de un solo motor. Todo debe funcionar con SQLite y SQL Server sin cambios en el código de modelo.

## Límites absolutos
Claude Code solo puede trabajar en `/home/master/dev/alumbrado-gateway`.

Prohibido leer, modificar o ejecutar acciones sobre:
- `/opt/alumbrado-gateway`
- `/etc/netplan`, `/etc/ufw`, `/etc/systemd`
- servicios systemd
- red OT o PLC real
- `.env`
- bases SQL reales sin autorización explícita

Prohibido implementar, sugerir o ejecutar:
- escrituras FINS
- cambios de bits
- force/set/reset
- cambios de modo PLC
- modificación de memoria PLC
- cambios de red, firewall, DNS o interfaces

Si una tarea requiere PLC, red OT, `/opt`, systemd, `.env` o BD real, detenerse y pedir confirmación.

## Seguridad y secretos
El sistema es estrictamente de solo lectura. Toda función FINS debe limitarse a lectura de memoria o diagnóstico pasivo.

No automatizar pruebas contra PLC real. Las pruebas FINS reales son manuales y controladas por el usuario.

No escribir, leer, imprimir ni loguear secretos: contraseñas, API keys, tokens, connection strings reales, credenciales SQL, claves privadas o contenido de `.env`.

Si se crea `.env.example`, usar solo nombres de variables sin valores reales. Si se detecta un secreto en el repo, detenerse y avisar.

## Rigor técnico — sin asunciones

No asumir ningún contexto técnico no proporcionado explícitamente.

Si algo requiere inferencia o hipótesis, marcarlo como:
`⚠️ ASUNCIÓN: [descripción]` y pedir confirmación antes de continuar.

Ejemplos de lo que NO se asume sin confirmación:
- terminología del dominio (tramo, cercha, sección, zona…)
- tipo de instalación o entorno
- codificación de datos (BCD, entero, endianness, máscaras)
- mapeado de registros PLC
- arquitectura del sistema o stack tecnológico
- rutas de ficheros, usuarios, servicios
- código existente en el repo

Si se detecta una asunción incorrecta ya escrita, corregirla en todos los ficheros afectados antes de continuar.

## Fuentes de verdad PLC
Validar variables, direcciones, índices, tipos, BCD, máscaras y semántica contra:
- `Tabla_ES.pdf`
- `LD_Ilum.pdf`

Si falta información o hay contradicción: no inventar, marcar como `PENDIENTE` y pedir confirmación.

No asumir endianness, BCD, offsets, máscaras ni rango de índices sin validación.

## Arquitectura
Mantener arquitectura modular por capas:
- `fins/` — comunicación FINS
- `model/` — modelos SQLAlchemy
- `schemas/` — validación/serialización
- `api/` — endpoints REST
- `acquisition/` — adquisición
- `config/` — configuración
- `main.py` — entrada

No crear nuevas capas, frameworks o carpetas estructurales sin necesidad clara.

## Desarrollo
Principios obligatorios:
- cambios mínimos y localizados
- YAGNI
- no refactors amplios sin orden explícita
- no documentación no solicitada
- no frameworks nuevos sin justificar
- buscar causa raíz antes de parchear
- mantener compatibilidad con Raspberry Pi
- priorizar código simple, explícito y diagnosticable

## Adquisición, BD y API
La adquisición debe usar timeouts, tolerar fallos parciales y no detener permanentemente el servicio ante fallos FINS o SQL.

Registrar timestamp, estado de lectura, errores FINS, timeouts y errores SQL.

Diferenciar dato correcto, ausente, inválido y fallo de lectura. No presentar datos simulados como reales.

No ejecutar migraciones contra BD real sin autorización. No borrar tablas, columnas o datos sin orden explícita.

Los endpoints REST deben ser de consulta o diagnóstico pasivo. Prohibido crear endpoints para escribir al PLC, cambiar alumbrado, ejecutar comandos, exponer secretos o modificar configuración OT.

## Workflow
Para cualquier tarea no trivial (3+ pasos o decisión arquitectónica), entrar en plan mode antes de actuar.

En plan mode — antes de construir:
1. redactar especificación detallada: qué, por qué, límites, supuestos y casos borde
2. inspeccionar archivos relevantes
3. proponer cambio mínimo con justificación
4. esperar aprobación antes de modificar

En plan mode — verificación:
- usar plan mode también para verificar resultados, no solo para construir
- definir criterios de éxito antes de ejecutar cualquier prueba

Fuera de plan mode, tras aprobación:
5. modificar solo lo necesario
6. ejecutar pruebas locales si existen
7. resumir cambios, pruebas y riesgos

Si algo sale mal: PARAR inmediatamente, volver a plan mode y replanificar desde cero antes de continuar.

No continuar sobre una base rota. No parchear sin entender la causa raíz.

## Modo económico
Por defecto:
- no escanear todo el repo
- no leer archivos no relacionados
- no repetir contexto conocido
- no generar explicaciones largas
- no mostrar archivos completos si basta un diff
- no crear planes extensos para cambios simples
- limitar búsquedas a carpetas relevantes
- preguntar antes de explorar masivamente

## Subagentes, lecciones y verificación
No usar subagentes por defecto. Usarlos solo para análisis acotados: carpeta concreta, logs, tests fallidos o comparación técnica.

Un subagente = una tarea concreta. Nunca usar subagentes para tocar PLC, red, `/opt`, systemd, `.env` o BD real.

Usar `tasks/lessons.md` solo para reglas reutilizables, errores repetidos o correcciones importantes del usuario.

No declarar una tarea terminada sin verificación proporcional.

Permitido: tests unitarios locales, importación de módulos, lint/type-check si existe, revisión de diff y simulación local marcada como simulada.

No permitido sin autorización: pruebas contra PLC real, migraciones reales, reinicio de servicios o comandos de red.

Al finalizar, indicar: archivos modificados, comandos ejecutados, pruebas realizadas, no verificado y riesgos pendientes.

No ocultar incertidumbre. Lo no validado queda como `PENDIENTE`.
