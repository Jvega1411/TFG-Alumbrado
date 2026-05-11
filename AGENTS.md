# CLAUDE.md - alumbrado-gateway

## Proyecto
Sistema read-only de supervision y explotacion de datos sobre alumbrado industrial en TVITEC.

Lee estados desde un PLC Omron Sysmac CJ2M CPU32 mediante FINS/UDP y persiste datos en SQL Server para consulta, historizacion y analisis.

No es sistema de mando. No debe modificar el PLC ni la instalacion.

## Contexto tecnico

### PLC
- Omron Sysmac CJ2M CPU32, IP 192.168.250.1, FINS node 1
- FINS/UDP puerto 9600
- Instalacion: 1104 luminarias, 172 cerchas, 112 secciones
- Jerarquia: Seccion (112) -> Cercha (172) -> Luminaria (1104)
- El PLC expone estado a nivel de seccion (H11-H31, 112 bits por grupo de estado)

### Nodo OT - Raspberry Pi (Ubuntu 24.04 LTS, aarch64)
- eth0: red OT 192.168.250.56, FINS node 56 - habla FINS con el PLC
- eth1 (adaptador USB-Eth): subred de enlace hacia el Lenovo (PENDIENTE confirmar nombre exacto de interfaz y subred)
- Usuarios: master (admin/sudo), gwsvc (servicio, sin sudo)
- Dev: /home/master/dev/alumbrado-gateway
- Prod: /opt/alumbrado-gateway
- Rol Fase 1: FINS reader + SQLite + FastAPI (todo en RPi)
- Rol Fase 2: FINS reader + paho-mqtt publisher unicamente (sin BD ni API)

### Nodo IT - Lenovo S500 (Windows 10, Intel i3)
- NIC1: subred de enlace con RPi (PENDIENTE confirmar IP, propuesta 10.0.0.2/30)
- NIC2: red corporativa de fabrica
- Rol Fase 2: broker Mosquitto + SQL Server Express + FastAPI
- Asignado por informatica: 2026-05-11

### Principio de aislamiento IT/OT (normativa)
- Comunicacion estrictamente unidireccional OT->IT: la RPi solo publica MQTT, nunca recibe del Lenovo
- El Lenovo nunca inicia conexion hacia la RPi ni tiene visibilidad de 192.168.250.0/24
- Ver docs/red_ot_aislamiento.md para comandos de firewall/sysctl de la RPi

### Stack
- BD: BD_Estados, BD_Historizacion
- Python 3.x (target produccion: 3.12.x en RPi), SQLAlchemy 2.0, Alembic

## Estrategia por fases

**Fase 1 - RPi standalone:** Python + SQLAlchemy + SQLite + FastAPI, todo en la RPi.
- SQL Server Express no corre en Linux; SQLite es el motor provisional.
- Los modelos SQLAlchemy se escriben una sola vez y son validos para ambas fases.
- BD_Estados y BD_Historizacion son dos ficheros .db.

**Fase 2 - arquitectura dos nodos (RPi + Lenovo):**
- RPi adelgaza: solo FINS reader + paho-mqtt publisher. Sin BD ni API.
- Lenovo: broker Mosquitto recibe los datos, SQL Server Express los persiste, FastAPI los expone.
- Transporte OT->IT: MQTT sobre subred de enlace RPi<->Lenovo (unidireccional).
- Migracion de esquema: alembic upgrade head en el Lenovo. Solo cambia la connection string en .env.

No usar engines ni queries especificas de un solo motor. Todo debe funcionar con SQLite y SQL Server sin cambios en el codigo de modelo.

## Limites absolutos
Claude Code solo puede trabajar en `/home/master/dev/alumbrado-gateway`.

Prohibido leer, modificar o ejecutar acciones sobre:
- `/opt/alumbrado-gateway`
- `/etc/netplan`, `/etc/ufw`, `/etc/systemd`
- servicios systemd
- red OT o PLC real
- `.env`
- bases SQL reales sin autorizacion explicita

Prohibido implementar, sugerir o ejecutar:
- escrituras FINS
- cambios de bits
- force/set/reset
- cambios de modo PLC
- modificacion de memoria PLC
- cambios de red, firewall, DNS o interfaces

Si una tarea requiere PLC, red OT, `/opt`, systemd, `.env` o BD real, detenerse y pedir confirmacion.

## Seguridad y secretos
El sistema es estrictamente de solo lectura. Toda funcion FINS debe limitarse a lectura de memoria o diagnostico pasivo.

No automatizar pruebas contra PLC real. Las pruebas FINS reales son manuales y controladas por el usuario.

No escribir, leer, imprimir ni loguear secretos: contrasenas, API keys, tokens, connection strings reales, credenciales SQL, claves privadas o contenido de `.env`.

Si se crea `.env.example`, usar solo nombres de variables sin valores reales. Si se detecta un secreto en el repo, detenerse y avisar.

## Fuentes de verdad PLC
Validar variables, direcciones, indices, tipos, BCD, mascaras y semantica contra:
- `Tabla_ES.pdf`
- `LD_Ilum.pdf`

Si falta informacion o hay contradiccion: no inventar, marcar como `PENDIENTE` y pedir confirmacion.

No asumir endianness, BCD, offsets, mascaras ni rango de indices sin validacion.

## Arquitectura
Mantener arquitectura modular por capas:
- `fins/` - comunicacion FINS
- `model/` - modelos SQLAlchemy
- `schemas/` - validacion/serializacion
- `api/` - endpoints REST
- `acquisition/` - adquisicion
- `config/` - configuracion
- `main.py` - entrada

No crear nuevas capas, frameworks o carpetas estructurales sin necesidad clara.

## Desarrollo
Principios obligatorios:
- cambios minimos y localizados
- YAGNI
- no refactors amplios sin orden explicita
- no documentacion no solicitada
- no frameworks nuevos sin justificar
- buscar causa raiz antes de parchear
- mantener compatibilidad con Raspberry Pi
- priorizar codigo simple, explicito y diagnosticable

## Adquisicion, BD y API
La adquisicion debe usar timeouts, tolerar fallos parciales y no detener permanentemente el servicio ante fallos FINS o SQL.

Registrar timestamp, estado de lectura, errores FINS, timeouts y errores SQL.

Diferenciar dato correcto, ausente, invalido y fallo de lectura. No presentar datos simulados como reales.

No ejecutar migraciones contra BD real sin autorizacion. No borrar tablas, columnas o datos sin orden explicita.

Los endpoints REST deben ser de consulta o diagnostico pasivo. Prohibido crear endpoints para escribir al PLC, cambiar alumbrado, ejecutar comandos, exponer secretos o modificar configuracion OT.

## Workflow
Para cualquier tarea no trivial (3+ pasos o decision arquitectonica), entrar en plan mode antes de actuar.

En plan mode - antes de construir:
1. redactar especificacion detallada: que, por que, limites, supuestos y casos borde
2. inspeccionar archivos relevantes
3. proponer cambio minimo con justificacion
4. esperar aprobacion antes de modificar

En plan mode - verificacion:
- usar plan mode tambien para verificar resultados, no solo para construir
- definir criterios de exito antes de ejecutar cualquier prueba

Fuera de plan mode, tras aprobacion:
5. modificar solo lo necesario
6. ejecutar pruebas locales si existen
7. resumir cambios, pruebas y riesgos

Si algo sale mal: PARAR inmediatamente, volver a plan mode y replanificar desde cero antes de continuar.

No continuar sobre una base rota. No parchear sin entender la causa raiz.

## Modo economico
Por defecto:
- no escanear todo el repo
- no leer archivos no relacionados
- no repetir contexto conocido
- no generar explicaciones largas
- no mostrar archivos completos si basta un diff
- no crear planes extensos para cambios simples
- limitar busquedas a carpetas relevantes
- preguntar antes de explorar masivamente

## Subagentes, lecciones y verificacion
No usar subagentes por defecto. Usarlos solo para analisis acotados: carpeta concreta, logs, tests fallidos o comparacion tecnica.

Un subagente = una tarea concreta. Nunca usar subagentes para tocar PLC, red, `/opt`, systemd, `.env` o BD real.

Usar `tasks/lessons.md` solo para reglas reutilizables, errores repetidos o correcciones importantes del usuario.

No declarar una tarea terminada sin verificacion proporcional.

Permitido: tests unitarios locales, importacion de modulos, lint/type-check si existe, revision de diff y simulacion local marcada como simulada.

No permitido sin autorizacion: pruebas contra PLC real, migraciones reales, reinicio de servicios o comandos de red.

Al finalizar, indicar: archivos modificados, comandos ejecutados, pruebas realizadas, no verificado y riesgos pendientes.

No ocultar incertidumbre. Lo no validado queda como `PENDIENTE`.
