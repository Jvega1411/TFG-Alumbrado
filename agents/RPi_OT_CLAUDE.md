# CLAUDE.md — alumbrado-gateway

## Proyecto
Sistema read-only de supervisión y explotación de datos sobre alumbrado industrial en TVITEC.

Lee estados desde un PLC Omron Sysmac CJ2M CPU32 mediante FINS/UDP y persiste datos en SQL Server para consulta, historización y análisis.

No es sistema de mando. No debe modificar el PLC ni la instalación.

## Contexto técnico
- PLC: Omron Sysmac CJ2M CPU32
- FINS/UDP: puerto 9600
- PLC IP: 192.168.250.1
- Instalación: 1104 luminarias
- Lógica: 172 tramos, 112 secciones
- Stack: Python 3.x, SQLAlchemy 2.0, Alembic, SQL Server
- BD: `BD_Estados`, `BD_Historizacion`
- Dev: `/home/master/dev/alumbrado-gateway`
- Prod: `/opt/alumbrado-gateway`
- Servicio: usuario `gwsvc`

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
