# CLAUDE.md — alumbrado-gateway

## Proyecto
Sistema read-only de supervisión y explotación de datos sobre alumbrado industrial en TVITEC.

Lee estados desde un PLC Omron Sysmac CJ2M CPU32 mediante FINS/UDP y persiste datos en SQL Server para consulta, historización y análisis.

No es sistema de mando. No debe modificar el PLC ni la instalación.

## Contexto técnico

## Knowledge Base - Vault Obsidian

El vault de conocimiento del proyecto vive en un repositorio separado: `TFG-Alumbrado-vault`.

Para agentes: leer `AGENTS.md` en la raiz del vault al inicio de sesiones que requieran contexto historico, decisiones previas o continuidad entre Claude Code y Codex.

El vault contiene:
- Nota diaria con decisiones y findings de cada sesion (`10_Daily/`)
- Variables PLC validadas y pendientes (`30_PLC/`)
- Arquitectura y contratos (`40_Architecture/`)
- Conceptos tecnicos explicados para Sebas (`60_Concepts/`)
- Mapa de codigo generado por Graphify (`graph/GRAPH_REPORT.md`)

Ruta del vault en esta maquina: ver `LOCAL_PATHS.md` en la raiz del vault.

Graphify no debe modificar este fichero ni `AGENTS.md` automaticamente.

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
