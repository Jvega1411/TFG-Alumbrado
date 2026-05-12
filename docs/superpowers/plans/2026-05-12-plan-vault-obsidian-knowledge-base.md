# Obsidian Vault — Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `TFG-Alumbrado-vault`, a separate git repo that serves as shared knowledge base for Sebas, Claude Code, and Codex — with daily notes, domain knowledge, concept explanations, and a Graphify-generated code map.

**Architecture:** The vault is a standalone Obsidian vault repo, independent of the code repo. `AGENTS.md` at the vault root is the mandatory agent entry point. Graphify indexes both repos and outputs `GRAPH_REPORT.md` into the vault after manual Sebas review. Machine-specific paths live in `LOCAL_PATHS.md` (gitignored). The code repo gets a `.graphifyignore` and a hand-written vault pointer in `CLAUDE.md`.

**Tech Stack:** Git, Obsidian (desktop app), Graphify (Python, pip), Python 3.12

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `TFG-Alumbrado-vault/AGENTS.md` | Create | Agent session protocol, writing contract, newer-prevails rule |
| `TFG-Alumbrado-vault/.gitignore` | Create | Ignore `LOCAL_PATHS.md`, `graph/graph.html` |
| `TFG-Alumbrado-vault/LOCAL_PATHS.md` | Create (not committed) | Machine-specific absolute path to code repo |
| `TFG-Alumbrado-vault/00_Index/Project Map.md` | Create | Static project overview |
| `TFG-Alumbrado-vault/00_Index/Pending Questions.md` | Create | Running PENDIENTE list seeded from smoke test |
| `TFG-Alumbrado-vault/10_Daily/2026-05-12.md` | Create | First daily note — today's session |
| `TFG-Alumbrado-vault/20_Decisions/` | Create (empty) | Placeholder for future decision records |
| `TFG-Alumbrado-vault/30_PLC/Variables Validated.md` | Create | Confirmed PLC addresses from smoke test |
| `TFG-Alumbrado-vault/30_PLC/Variables Pending.md` | Create | Addresses used but not formally validated |
| `TFG-Alumbrado-vault/30_PLC/Smoke Test Findings.md` | Create | Curated summary of all 7 smoke captures |
| `TFG-Alumbrado-vault/40_Architecture/Fase 2 Overview.md` | Create | Two-node architecture summary |
| `TFG-Alumbrado-vault/40_Architecture/MQTT Payload.md` | Create | Payload schema and topic |
| `TFG-Alumbrado-vault/40_Architecture/SQLite Schema.md` | Create | bd_alumbrado.db tables |
| `TFG-Alumbrado-vault/40_Architecture/API Contract.md` | Create | FastAPI endpoints |
| `TFG-Alumbrado-vault/50_AI_Context/Claude Context.md` | Create | Claude Code quirks and preferences |
| `TFG-Alumbrado-vault/50_AI_Context/Codex Context.md` | Create | Codex quirks and preferences |
| `TFG-Alumbrado-vault/50_AI_Context/Agent Rules.md` | Create | Shared conventions for both agents |
| `TFG-Alumbrado-vault/60_Concepts/FINS-Protocol.md` | Create | FINS explained for Sebas |
| `TFG-Alumbrado-vault/60_Concepts/BCD-Encoding.md` | Create | BCD encoding explained for Sebas |
| `TFG-Alumbrado-vault/graph/` | Create (empty) | Placeholder for Graphify output |
| `TFG-Alumbrado/.graphifyignore` | Create | Exclude .env, DBs, raw JSONs, venv |
| `TFG-Alumbrado/.gitignore` | Modify | Add `graph.json` |
| `TFG-Alumbrado/CLAUDE.md` | Modify | Add hand-written vault pointer section |

---

## Task 1: Create vault repo and gitignore

**Files:**
- Create: `TFG-Alumbrado-vault/` (new git repo)
- Create: `TFG-Alumbrado-vault/.gitignore`

- [ ] **Step 1: Create the vault directory and initialize git**

```powershell
cd C:\Users\sebas
mkdir TFG-Alumbrado-vault
cd TFG-Alumbrado-vault
git init
git config user.name "MSI"
```

- [ ] **Step 2: Create .gitignore**

Create `C:\Users\sebas\TFG-Alumbrado-vault\.gitignore` with this content:

```
# Machine-specific paths — each machine maintains its own copy
LOCAL_PATHS.md

# Graphify visual output — regenerated on demand
graph/graph.html

# Obsidian workspace state
.obsidian/workspace.json
.obsidian/workspace-mobile.json
```

- [ ] **Step 3: Create placeholder folder structure**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
mkdir 00_Index, 10_Daily, 20_Decisions, 30_PLC, 40_Architecture, 50_AI_Context, 60_Concepts, graph
```

- [ ] **Step 4: Add .gitignore and commit**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git add .gitignore
git commit -m "chore: init vault repo con gitignore"
```

---

## Task 2: Write AGENTS.md

**Files:**
- Create: `TFG-Alumbrado-vault/AGENTS.md`

- [ ] **Step 1: Create AGENTS.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\AGENTS.md` with this content:

```markdown
# AGENTS.md — TFG-Alumbrado-vault

> Este fichero es el contrato de sesión para todos los agentes (Claude Code y Codex).
> Leerlo siempre en primer lugar. No modificarlo sin revisión explícita de Sebas.

---

## Rutas de repositorio

Ver `LOCAL_PATHS.md` en la raíz de este vault (fichero local, no commiteado).
`LOCAL_PATHS.md` contiene la ruta absoluta al repo de código en esta máquina.
Sebas lo crea en el primer setup. Si no existe, pedirle a Sebas que lo cree.

---

## Protocolo de sesión — obligatorio en cada sesión

1. **Situarse:** Leer `10_Daily/YYYY-MM-DD.md` de hoy completamente.
   - Si existe: leer todas las sesiones anteriores del día para entender el estado actual.
   - Si no existe: crearlo desde la plantilla al final de este fichero.
2. **Leer:** `00_Index/Pending Questions.md` antes de empezar cualquier trabajo.
3. **Leer:** `graph/GRAPH_REPORT.md` si se necesita contexto sobre la estructura del código.
4. **Trabajar** en el repo de código.
5. **Añadir** el bloque de sesión a la nota diaria al terminar (aunque sea breve).
6. **Actualizar** `00_Index/Pending Questions.md` — añadir nuevos items, tachar los resueltos.
7. **Commitear el vault solo si hubo trabajo real.**
   - Sesión puramente de lectura sin razonamiento ni decisiones: no escribir, no commitear.
   - Si hubo razonamiento, decisiones, aprendizaje, revisión o conceptos trabajados (aunque no haya código producido): añadir bloque a la nota diaria y commitear. Esto incluye sesiones de revisión de planes o brainstorming.
   - Si hubo cambios en el vault: `git commit -m "session: YYYY-MM-DD <AgentName>"`

---

## Contrato de escritura

- **Las decisiones usan el formato What / Why / Where.**
  - **What:** qué cambió o se decidió
  - **Why:** explicación en lenguaje llano, escrita para Sebas (estudiante, no experto en programación)
  - **Where:** ruta exacta de fichero + línea en el repo de código (`TFG-Alumbrado`)
- **Tono educativo.** Sebas está aprendiendo. Explicar las decisiones técnicas en lenguaje claro.
- **Enlazar conceptos.** Cuando aparece un término técnico por primera vez en una sesión, enlazar a `[[60_Concepts/NombreConcepto]]`. Crear el fichero si no existe.
- **Los snippets de código se comentan para Sebas**, no para el compilador. Los comentarios explican el *por qué*, no el *qué*.
- **Nunca resumir sin explicar.** "Fixed bind" no es suficiente. Explicar qué es bind y por qué importa.

---

## Regla newer-prevails

Si dos notas se contradicen, gana la de fecha más reciente.

**Excepción — estas fuentes siempre ganan sobre cualquier nota:**
- `Tabla_ES.html` en el repo de código — mapa de variables PLC (verdad de dirección)
- `LD_Ilum.pdf` en el repo de código — diagrama ladder (verdad de comportamiento)
- Capturas smoke en `data/smoke_fins/` — **solo para valores observados** (e.g. "W25=1 fue leído"). La interpretación semántica (e.g. "W25=1 significa que la fotocélula está activa") sigue requiriendo confirmación en LD_Ilum.pdf o decisión explícita de Sebas.
- Una decisión explícita de Sebas (marcada "Decisión Sebas" en la nota)

---

## Qué NO escribir en el vault

- Contenido de `.env`, credenciales, contraseñas, connection strings
- Ficheros JSON raw de smoke (`data/smoke_fins/*.json` quedan en el repo de código)
- Ficheros generados (`__pycache__`, `.db`, `.venv`, `graph.json`)

---

## Plantilla de nota diaria

Usar esta plantilla cuando la nota del día no existe aún:

```
# YYYY-MM-DD

---
## ── Sesión 1 · [Claude Code / Codex] · HH:MM UTC
**Contexto al llegar:** <una línea — estado del proyecto al iniciar esta sesión>

### Decisiones

#### <Título de decisión>
- **What:** <qué cambió o se eligió>
- **Why:** <explicación en lenguaje llano>
- **Where:** `<fichero> · línea <N>` en TFG-Alumbrado
- → Ver [[60_Concepts/<FicheroConcepto>]] _(si se introduce un concepto nuevo)_

### Findings
- <descubrimiento empírico — lecturas PLC, resultados de tests, inspección de código>

### Explained
<Breve explicación en lenguaje llano de un concepto que apareció esta sesión.>

\`\`\`python
# <fichero> · <función o contexto>
# El comentario explica el POR QUÉ, no el qué — escrito para Sebas
<snippet de código>
\`\`\`
→ [[60_Concepts/<FicheroConcepto>]]

### Pending
- <pregunta abierta o item sin resolver — añadir también a 00_Index/Pending Questions.md>

### Supersedes
- <qué nota o asunción anterior corrige esta sesión>
```
```

- [ ] **Step 2: Create LOCAL_PATHS.md (local only, never committed)**

Create `C:\Users\sebas\TFG-Alumbrado-vault\LOCAL_PATHS.md` with this content:

```markdown
# LOCAL_PATHS.md — rutas locales de esta máquina

> Este fichero está en .gitignore. Cada máquina mantiene su propia copia.

## Repo de código
C:\Users\sebas\TFG-Alumbrado
```

- [ ] **Step 3: Verify LOCAL_PATHS.md is gitignored**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git status
```

Expected: `LOCAL_PATHS.md` does NOT appear in untracked files. Only `AGENTS.md` appears.

- [ ] **Step 4: Commit AGENTS.md**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git add AGENTS.md
git commit -m "docs: añadir AGENTS.md — contrato de sesión para agentes"
```

---

## Task 3: Seed 00_Index

**Files:**
- Create: `TFG-Alumbrado-vault/00_Index/Project Map.md`
- Create: `TFG-Alumbrado-vault/00_Index/Pending Questions.md`

- [ ] **Step 1: Create Project Map.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\00_Index\Project Map.md`:

```markdown
# Project Map — TFG-Alumbrado

**Proyecto:** Sistema read-only de supervisión de alumbrado industrial en TVITEC.
**Estado actual:** Fase 1 completada (FINS/UDP smoke test). Fase 2 en implementación.

## Instalación
- 1104 luminarias · 172 cerchas · 112 secciones
- Jerarquía: Sección → Cercha → Luminaria
- PLC: Omron CJ2M CPU32 · IP 192.168.250.1 · FINS node 1

## Arquitectura Fase 2
- **Nodo OT (RPi):** Lee PLC via FINS/UDP → publica MQTT
- **Nodo IT (Lenovo):** Broker Mosquitto → SQLite → FastAPI
- **Transporte:** MQTT unidireccional OT→IT sobre subred de enlace

## Repos
- Código: `TFG-Alumbrado` (ver `LOCAL_PATHS.md` para ruta absoluta)
- Vault: este repo (`TFG-Alumbrado-vault`)

## Planes de implementación
Ver `TFG-Alumbrado/docs/superpowers/plans/` para los planes detallados:
- Plan B: FINS reader + MQTT publisher (nodo OT)
- Plan C: MQTT subscriber + SQLite (nodo IT)
- Plan D: FastAPI + web dashboard

## Fuentes de verdad PLC
- `Tabla_ES.html` — mapa de variables (1215 entradas)
- `LD_Ilum.pdf` — diagrama ladder
- `data/smoke_fins/*.json` — capturas reales del PLC (valores observados)
```

- [ ] **Step 2: Create Pending Questions.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\00_Index\Pending Questions.md`:

```markdown
# Pending Questions

> Agentes: actualizar este fichero cada sesión. Añadir nuevos items. Tachar con ~~texto~~ los resueltos.

## PLC / Hardware

- [ ] **H10.13 (0x2000 = marmansec):** Observado constante en smoke. selcer termina en H10.11=selcer172. H10.12=funautsec, H10.13=marmansec, H10.14=ordtraseccom (posible duplicado documental), H10.15=indactalusec. Confirmar semántica con LD_Ilum.pdf y el programador.
- [ ] **W25.00 = entfot1:** Confirmado empíricamente (smoke: W25=1) y visible en ladder como I:6.00, pero no aparece en Tabla_ES.html. Confirmar formalmente contra LD_Ilum.pdf.
- [ ] **horini3–12:** D3632 empieza en horfin3. Los horarios de inicio de tramos 3-12 deben estar entre D1008 y D3631. No leídos aún.
- [ ] **D116 (modfunalu):** Validado en Tabla_ES.html. No leído en smoke test. Leer en la próxima sesión con acceso al PLC.
- [ ] **W4-W14 (salidas cerchas):** Tabla_ES valida W4.00–W11.13 = saldigcer1..126. Smoke ha leído W4–W14. W11.14–W14.15 presentes en lecturas pero sin confirmación en tabla. Confirmar cobertura completa con programador.

## Arquitectura / Infraestructura

- [ ] **P4:** Nombre exacto de interfaz USB-Eth en la RPi (eth1 u otro).
- [ ] **P5:** IP de la subred de enlace RPi↔Lenovo (propuesta 10.0.0.x/30).
- [ ] **P3:** Colores corporativos de TVITEC para el CSS del dashboard.

## Plan B (bugs detectados en revisión)

- [ ] `_validate_db()` en `config/settings.py` referencia `cls.DB_URL` que no existe — usar `cls.DB_ESTADOS_URL`.
- [ ] Tests de `TestRunPublisher` no mockean `Config.validate_publisher()` — fallan por `MQTT_BROKER_HOST` vacío.
- [ ] `test_does_not_publish_when_unchanged`: mock de publish devuelve `Mock()` con `rc != 0`, `last_payload` nunca se actualiza → `call_count == 2` en vez de 1.
```

- [ ] **Step 3: Commit 00_Index**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git add "00_Index/"
git commit -m "docs: seed 00_Index — Project Map y Pending Questions"
```

---

## Task 4: Create today's daily note

**Files:**
- Create: `TFG-Alumbrado-vault/10_Daily/2026-05-12.md`

- [ ] **Step 1: Create 2026-05-12.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\10_Daily\2026-05-12.md`:

```markdown
# 2026-05-12

---
## ── Sesión 1 · Claude Code · 07:30 UTC
**Contexto al llegar:** Smoke test FINS completado (7 capturas). Planes B/C/D revisados. Inicio de sesión de brainstorming del vault.

### Decisions

#### Bind socket a IP específica, no a ""
- **What:** `sock.bind("", 9600)` → `sock.bind("192.168.250.55", 9600)`
- **Why:** El portátil tiene varios adaptadores de red (WiFi, Ethernet, cable OT). Binding a `""` escucha en todos — si el PLC responde y lo recoge el adaptador equivocado, el paquete se pierde. Binding a `192.168.250.55` fuerza el tráfico por el cable OT únicamente.
- **Where:** `smoke_fins.py · línea 23` / `fins/client.py · línea 41`
- → Ver [[60_Concepts/Sockets-y-NICs]]

#### Vault en repo separado (TFG-Alumbrado-vault)
- **What:** El vault vive en su propio repositorio git, no como subcarpeta del repo de código.
- **Why:** Los commits de código permanecen limpios y enfocados. El historial del vault muestra la evolución del conocimiento de forma independiente. Graphify indexa ambos repos.
- **Where:** No hay fichero de código afectado. `TFG-Alumbrado/CLAUDE.md` recibirá un puntero manual al vault.

#### AGENTS.md como punto de entrada fijo
- **What:** `AGENTS.md` en la raíz del vault es el primer fichero que lee cualquier agente en cualquier sesión.
- **Why:** Centraliza el protocolo (qué leer, cómo escribir, regla newer-prevails) en un único lugar. Sin él, cada agente tendría que inferir las convenciones del historial de notas.
- **Where:** `TFG-Alumbrado-vault/AGENTS.md`

#### Graphify no modifica CLAUDE.md ni AGENTS.md
- **What:** Desactivar cualquier feature de Graphify que auto-genere o sobreescriba ficheros de instrucciones de agentes.
- **Why:** `CLAUDE.md` y `AGENTS.md` son contratos escritos a mano con reglas de seguridad estrictas para este proyecto. Una sobreescritura automática podría relajar restricciones sin revisión.
- **Where:** Configuración de Graphify (`.graphifyignore` + config manual).

### Findings
- PLC clock ~5 min detrás de UTC+2, no 1 hora. Confirmado en 4 capturas. Deriva fija, sin NTP.
- H10 = 0x2000 (bit 13 = H10.13 = marmansec). selcer termina en H10.11=selcer172. H10.12=funautsec, H10.13=marmansec, H10.14=ordtraseccom, H10.15=indactalusec. ⚠️ Semántica pendiente de confirmar contra LD_Ilum.pdf.
- DM clock = enteros planos. AR clock = pares BCD (e.g. 0x3109 = min 31, seg 09). Ambos confirmados empíricamente.
- Tiempo de ciclo ~15-16ms (A264=15, A265=0). Intervalo de adquisición de 10s es muy seguro.
- W25=1, H100=0x0002 (memactfotalu=1): fotocélula activa durante el smoke test.

### Explained

**Codificación BCD** — El reloj AR no guarda los minutos como un número normal. Empaqueta dos dígitos decimales en un byte hex: `0x31` significa "3 decenas, 1 unidad = 31 minutos". Esto se llama BCD (Binary Coded Decimal). Era útil en hardware industrial antiguo para mostrarlo en displays de 7 segmentos.

```python
# fins/frame.py — decodificación BCD del reloj AR
# Byte 0x48: nibble alto = 4, nibble bajo = 8 → 48 minutos
# Byte 0x27: nibble alto = 2, nibble bajo = 7 → 27 segundos
tens  = (byte >> 4) & 0xF   # desplaza 4 bits a la derecha para obtener las decenas
units = byte & 0xF           # máscara para quedarse solo con las unidades
value = tens * 10 + units    # reconstruir el número decimal
```
→ [[60_Concepts/BCD-Encoding]]

### Pending
- Confirmar H10 bit 13 con el programador
- Leer D116 (modfunalu) en el próximo smoke test
- Encontrar horini3–12 (gap DM entre D1008 y D3631)
- Confirmar W25.00 contra LD_Ilum.pdf

### Supersedes
- Asunción anterior: SQL Server para Fase 2 → corregido: SQLite (`bd_alumbrado.db`)
- Asunción anterior: bind socket a `""` → corregido: bind a `192.168.250.55`
```

- [ ] **Step 2: Commit daily note**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git add "10_Daily/"
git commit -m "session: 2026-05-12 Claude Code — smoke test findings + vault design"
```

---

## Task 5: Seed 30_PLC

**Files:**
- Create: `TFG-Alumbrado-vault/30_PLC/Variables Validated.md`
- Create: `TFG-Alumbrado-vault/30_PLC/Variables Pending.md`
- Create: `TFG-Alumbrado-vault/30_PLC/Smoke Test Findings.md`

- [ ] **Step 1: Create Variables Validated.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\30_PLC\Variables Validated.md`:

```markdown
# Variables PLC — Validadas

> Validadas = confirmadas contra Tabla_ES.html o LD_Ilum.pdf.
> Última actualización: 2026-05-12

## Área HR (Holding Relay)

| Dirección | Variable | Descripción | Fuente |
|---|---|---|---|
| H0–H10 | selcer1..172 | Selección de cerchas (172 bits en H0.00–H10.11) | Tabla_ES.html |
| H11–H17 | funautsec1..112 | Funcionamiento automático por sección (112 bits) | Tabla_ES.html |
| H18–H24 | marmansec1..112 | Marcha manual por sección (112 bits) | Tabla_ES.html |
| H25–H31 | memactsec1..112 | Memoria de activación por sección (112 bits) | Tabla_ES.html |
| H100.00 | memfunfotalu | Memoria función fotocélula | Tabla_ES.html |
| H100.01 | memactfotalu | Memoria activación fotocélula | Tabla_ES.html |

**Nota H10:** selcer termina en H10.11 (selcer172). H10.12=funautsec, H10.13=marmansec, H10.14=ordtraseccom (posible duplicado documental), H10.15=indactalusec. H10.13 (0x2000) aparece activo en smoke → marmansec=True observado. Confirmar semántica contra LD_Ilum.pdf.

## Área DM (Data Memory)

| Dirección | Variable | Descripción | Fuente |
|---|---|---|---|
| D500 | segplc | Segundos del reloj PLC | Tabla_ES.html |
| D501 | minplc | Minutos del reloj PLC | Tabla_ES.html |
| D502 | horplc | Hora del reloj PLC | Tabla_ES.html |
| D503 | diaplc | Día del reloj PLC | Tabla_ES.html |
| D504 | mesplc | Mes del reloj PLC | Tabla_ES.html |
| D505 | añoplc | Año del reloj PLC | Tabla_ES.html |
| D506 | diasemplc | Día de la semana del reloj PLC | Tabla_ES.html |
| D1000 | horini1 | Hora inicio tramo 1 | Tabla_ES.html |
| D1001 | minini1 | Minuto inicio tramo 1 | Tabla_ES.html |
| D1002 | horfin1 | Hora fin tramo 1 | Tabla_ES.html |
| D1003 | minfin1 | Minuto fin tramo 1 | Tabla_ES.html |
| D1004 | horini2 | Hora inicio tramo 2 | Tabla_ES.html |
| D1005 | minini2 | Minuto inicio tramo 2 | Tabla_ES.html |
| D1006 | horfin2 | Hora fin tramo 2 | Tabla_ES.html |
| D1007 | minfin2 | Minuto fin tramo 2 | Tabla_ES.html |
| D3632–D3651 | horfin3/minfin3..horfin12/minfin12 | Horas fin tramos 3–12 (20 words) | Tabla_ES.html |

**Nota D clock:** Los valores son enteros planos (no BCD). Confirmado en smoke test.

## Área AR (Auxiliary Relay)

| Dirección | Variable | Descripción | Fuente |
|---|---|---|---|
| A351 | minsegplc | Minutos y segundos PLC (BCD packed) | Tabla_ES.html |
| A352 | diahorplc | Día y hora PLC (BCD packed) | Tabla_ES.html |
| A353 | anomesplc | Año y mes PLC (BCD packed) | Tabla_ES.html |
| A401.08 | P_Cycle_Time_err | Error de tiempo de ciclo | Tabla_ES.html |
| A402.04 | P_Low_Battery | Batería baja | Tabla_ES.html |
| A402.09 | P_IO_Verify_Error | Error de verificación I/O | Tabla_ES.html |

**Nota AR clock:** Los valores son BCD packed (pares de dígitos decimales por nibble). Ver [[60_Concepts/BCD-Encoding]].
```

- [ ] **Step 2: Create Variables Pending.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\30_PLC\Variables Pending.md`:

```markdown
# Variables PLC — Pendientes de validación formal

> Pendiente = en uso o detectadas, pero sin confirmación en Tabla_ES.html o LD_Ilum.pdf.
> Última actualización: 2026-05-12

## WR W25.00 — entfot1 (fotocélula entrada)

- **Estado:** Confirmada empíricamente. W25=1 en todos los smoke tests. Visible en diagrama LD como entrada I:6.00.
- **No aparece en:** Tabla_ES.html (tabla truncada en W11.13)
- **Pendiente:** Confirmar contra LD_Ilum.pdf sección entradas digitales
- **Referencia smoke:** `fins_smoke_20260512_075408Z.json` · SID 4

## DM D116 — modfunalu

- **Estado:** Referenciada en Plan B de implementación. No leída en smoke test.
- **Pendiente:** Leer en próxima sesión con acceso al PLC
- **Área:** DM

## DM D1008–D3631 — horini3..horini12

- **Estado:** D3632 arranca con horfin3. Las horas de inicio de tramos 3-12 deben estar en este rango pero no han sido leídas.
- **Pendiente:** Localizar y leer en próximo smoke test

## AR A264–A265 — P_Cycle_Time_Value

- **Estado:** Leídas en smoke (A264=15, A265=0). Tipo UDINT raw, word-order pendiente de verificar.
- **Pendiente:** Decodificación DINT/word-order
```

- [ ] **Step 3: Create Smoke Test Findings.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\30_PLC\Smoke Test Findings.md`:

```markdown
# Smoke Test Findings

> Fuente canónica indexada por Graphify. Los JSON raw están en `TFG-Alumbrado/data/smoke_fins/` y no se copian aquí.
> Última actualización: 2026-05-12

## Capturas disponibles

| Fichero | Timestamp UTC | Reads | Errores |
|---|---|---|---|
| `fins_smoke_20260512_073512Z.json` | 07:35:12 | 8 | 0 |
| `fins_smoke_20260512_075315Z.json` | 07:53:15 | 11 | 0 |
| `fins_smoke_20260512_075332Z.json` | 07:53:32 | 11 | 0 |
| `fins_smoke_20260512_075351Z.json` | 07:53:51 | 11 | 0 |
| `fins_smoke_20260512_075408Z.json` | 07:54:08 | 11 | 0 |

Total: 5 capturas · 0 errores FINS · Comunicación 100% estable.

## Confirmaciones empíricas

### Reloj PLC
- **DM clock (D500–D506):** Enteros planos. Ejemplo: D500=3 (seg), D501=49 (min), D502=9 (hora), D503=12 (día), D504=5 (mes), D505=26 (año), D506=2 (día semana).
- **AR clock (A351–A353):** BCD packed. Ejemplo: A351=0x4903 → nibbles: 0x49=49 min, 0x03=03 seg.
- **Desfase:** ~5 minutos detrás de UTC+2. Deriva fija, sin NTP. No es error de decodificación.

### Fotocélula
- W25=1 en todas las capturas → `entfot1` activo (fotocélula encendida)
- H100=0x0002 → bit1=1 → `memactfotalu` activo

### Tiempo de ciclo
- A264=15 ms, A265=0 → tiempo de ciclo ~15-16ms. El intervalo de adquisición de 10s es 625× el tiempo de ciclo.

### Selección cerchas y H10
- H0–H9: todos 0x0000 (ninguna cercha seleccionada, selcer1..160)
- H10=0x2000 (bit 13 = H10.13) constante en todas las capturas. selcer termina en H10.11=selcer172. H10.13 = marmansec → marmansec=True observado. ⚠️ Semántica pendiente de confirmar contra LD_Ilum.pdf.

### Salidas cerchas (WR)
- Leído por smoke: W4–W14
- Validado por Tabla_ES: W4.00–W11.13 = saldigcer1..126
- No validado: W11.14–W14.15 (presentes en lecturas, sin confirmación en tabla)

### Horarios tramos
- Tramo 1: ini=00:00, fin=09:00
- Tramo 2: ini=00:00, fin=09:00
- Tramos 3–5 fin: 07:45
- Tramo 6 fin: 08:00
- Tramo 7 fin: 08:15
- Tramo 8 fin: 09:50
- Tramos 9–10 fin: 10:00
- horini3–12: no leídos (gap D1008–D3631 pendiente)

### Diagnóstico
- A401=0x0000, A402=0x0000 → Sin errores de ciclo, batería ok, I/O ok.
```

- [ ] **Step 4: Commit 30_PLC**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git add "30_PLC/"
git commit -m "docs: seed 30_PLC — variables validadas, pendientes y findings smoke test"
```

---

## Task 6: Seed 40_Architecture

**Files:**
- Create: `TFG-Alumbrado-vault/40_Architecture/Fase 2 Overview.md`
- Create: `TFG-Alumbrado-vault/40_Architecture/MQTT Payload.md`
- Create: `TFG-Alumbrado-vault/40_Architecture/SQLite Schema.md`
- Create: `TFG-Alumbrado-vault/40_Architecture/API Contract.md`

- [ ] **Step 1: Create Fase 2 Overview.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\40_Architecture\Fase 2 Overview.md`:

```markdown
# Fase 2 — Arquitectura dos nodos

## Diagrama

```
RPi (nodo OT)                    Lenovo (nodo IT)
192.168.250.56                   red corporativa
─────────────────                ────────────────────────────
fins/ → adquisición              Mosquitto broker
acquisition/poller.py            subscriber/listener.py
acquisition/publisher.py  →MQTT→ model/ + SQLite
                                 api/routes.py → FastAPI
                                 web/ → dashboard
```

## Principio de aislamiento OT/IT

Comunicación estrictamente unidireccional OT→IT. La RPi solo publica MQTT, nunca recibe del Lenovo. El Lenovo nunca inicia conexión hacia la RPi.

## Subsistemas (planes de implementación)

| Plan | Nodo | Módulo | Estado |
|---|---|---|---|
| Plan B | RPi (OT) | `acquisition/poller.py` + `acquisition/publisher.py` | En revisión |
| Plan C | Lenovo (IT) | `subscriber/listener.py` + `subscriber/payload_schema.py` | Pendiente |
| Plan D | Lenovo (IT) | `api/routes.py` + `web/` + `main.py` | Pendiente |

## Pendientes de infraestructura

- P4: Nombre interfaz USB-Eth en RPi (propuesta eth1)
- P5: IP subred enlace RPi↔Lenovo (propuesta 10.0.0.x/30)
```

- [ ] **Step 2: Create MQTT Payload.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\40_Architecture\MQTT Payload.md`:

```markdown
# MQTT Payload

**Topic:** `alumbrado/estado`
**QoS:** 1
**Formato:** JSON

## Estructura payload normal (fins_ok=true)

```json
{
  "ts": "2026-05-12T07:54:08.310232+00:00",
  "fins_ok": true,
  "fins_error": null,
  "plc_reloj": {
    "seg": 3, "min": 49, "hora": 9,
    "dia": 12, "mes": 5, "anio": 26, "diasem": 2
  },
  "modo": {
    "modfunalu": 0,
    "fotocelula_entrada": true,
    "fotocelula_mem_fun": false,
    "fotocelula_mem_act": true
  },
  // NOTA: modfunalu=0 es valor spec/ejemplo — D116 no fue leído en smoke test.
  "secciones": [
    { "id": 1, "automatico": false, "manual": false, "horario_activo": false },
    ...
  ],
  "horarios": { "raw_words": [0, 0, 9, 0, 0, 0, 9, 0, ...] },
  "diagnostico": {
    "cycle_time_error": false,
    "low_battery": false,
    "io_verify_error": false
  }
}
```

## Estructura payload error (fins_ok=false)

```json
{
  "ts": "2026-05-12T07:54:08+00:00",
  "fins_ok": false,
  "fins_error": "MRES=0x21 SRES=0x08"
}
```

## Lógica de publicación

Publicar cuando:
1. Primera lectura de la sesión (`last_payload is None`)
2. Algún valor cambió respecto al último payload publicado (`not _payloads_equal()`)
3. Han pasado ≥300s desde la última publicación (heartbeat)

`_payloads_equal()` ignora el campo `ts` para comparar.
```

- [ ] **Step 3: Create SQLite Schema.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\40_Architecture\SQLite Schema.md`:

```markdown
# SQLite Schema — bd_alumbrado.db

Base de datos única para Fase 2. Fichero: `bd_alumbrado.db`.

## Tabla: ciclo

Registro de cada ciclo de adquisición. Una fila por publicación MQTT procesada.

| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| timestamp | DATETIME NOT NULL | Timestamp del ciclo (UTC) |
| fins_ok | BOOLEAN NOT NULL | True si la lectura FINS fue exitosa |
| fins_error | TEXT | Mensaje de error si fins_ok=False |
| plc_seg | INTEGER | Segundos del reloj PLC |
| plc_min | INTEGER | Minutos del reloj PLC |
| plc_hora | INTEGER | Hora del reloj PLC |
| plc_dia | INTEGER | Día del reloj PLC |
| plc_mes | INTEGER | Mes del reloj PLC |
| plc_anio | INTEGER | Año del reloj PLC |
| modfunalu | INTEGER | Modo de funcionamiento alumbrado |
| fotocelula_entrada | BOOLEAN | Señal entrada fotocélula (W25.00) |
| fotocelula_mem_fun | BOOLEAN | Memoria función fotocélula (H100.00) |
| fotocelula_mem_act | BOOLEAN | Memoria activación fotocélula (H100.01) |
| cycle_time_error | BOOLEAN | A401.08 |
| low_battery | BOOLEAN | A402.04 |
| io_verify_error | BOOLEAN | A402.09 |

Constraint: `uq_ciclo_timestamp` UNIQUE (timestamp)

## Tabla: seccion_estado

Estado de cada sección por ciclo. 112 filas por ciclo con fins_ok=True.
`timestamp` se desnormaliza desde `ciclo` para evitar joins en consultas frecuentes.

| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| ciclo_id | INTEGER FK → ciclo.id | |
| timestamp | DATETIME NOT NULL | Copia desnormalizada de ciclo.timestamp |
| seccion_id | INTEGER NOT NULL | 1–112 |
| automatico | BOOLEAN NOT NULL | H11–H17 |
| manual | BOOLEAN NOT NULL | H18–H24 |
| horario_activo | BOOLEAN NOT NULL | H25–H31 |

## Tabla: horario_tramo

Raw words de horarios. Una fila por ciclo con fins_ok=True.
> ⚠️ Forma definitiva pendiente de spec completa. Por ahora: almacenamiento raw como placeholder.

| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| ciclo_id | INTEGER FK → ciclo.id | |
| raw_words | TEXT NOT NULL | JSON array de integers (D1000–D1007 + D3632–D3651) — forma definitiva TBD |
```

- [ ] **Step 4: Create API Contract.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\40_Architecture\API Contract.md`:

```markdown
# API Contract — FastAPI

**Base URL:** `http://localhost:8000` (dev) / `http://<lenovo-ip>:8000` (prod)
**Todos los endpoints son GET — read-only.**

## Endpoints

### GET /
Bienvenida / health básico.

### GET /api/estado
Estado más reciente del sistema. Response: último ciclo + sus 112 secciones.

### GET /api/secciones/actual
Estado actual de todas las secciones.

### GET /api/horarios
Último raw_words de horarios disponible.

### GET /api/historial/ciclos
Historial de ciclos. Query params: `desde`, `hasta` (ISO datetime), `limit` (default 100).

### GET /api/historial/secciones
Historial de estados de secciones. Query params: `desde`, `hasta`, `seccion_id`.
```

- [ ] **Step 5: Commit 40_Architecture**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git add "40_Architecture/"
git commit -m "docs: seed 40_Architecture — overview, MQTT payload, SQLite schema, API contract"
```

---

## Task 7: Seed 50_AI_Context

**Files:**
- Create: `TFG-Alumbrado-vault/50_AI_Context/Claude Context.md`
- Create: `TFG-Alumbrado-vault/50_AI_Context/Codex Context.md`
- Create: `TFG-Alumbrado-vault/50_AI_Context/Agent Rules.md`

- [ ] **Step 1: Create Agent Rules.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\50_AI_Context\Agent Rules.md`:

```markdown
# Agent Rules — convenciones compartidas

> Aplica a Claude Code y Codex por igual.

## Formato commit (vault)
`session: YYYY-MM-DD <AgentName>`
Ejemplo: `session: 2026-05-12 Claude Code`

## Formato commit (código)
Seguir el estilo del repo: `feat(módulo): descripción` / `fix(módulo): descripción`
Co-authored-by siempre al final.

## Escritura de notas
- What / Why / Where en cada decisión
- Tono educativo — Sebas es estudiante, no experto
- Enlazar [[60_Concepts/X]] cuando aparece un término técnico por primera vez
- Snippets de código comentados para el "por qué", no el "qué"

## Lo que NO hacer
- No escribir a `.env` ni leer su contenido
- No copiar JSON raw de `data/smoke_fins/` al vault
- No modificar `AGENTS.md` sin revisión de Sebas
- No ejecutar migraciones de BD sin autorización explícita
- No tocar red OT, PLC, ni `/opt/alumbrado-gateway`
```

- [ ] **Step 2: Create Claude Context.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\50_AI_Context\Claude Context.md`:

```markdown
# Claude Context

**Modelo:** claude-sonnet-4-6
**Herramienta:** Claude Code (CLI)

## Qué funciona bien
- Plan mode antes de cambios no triviales — Claude lo sigue si se lo pides
- Revisión de planes antes de implementar — detecta bugs en tests y specs
- Explicaciones técnicas detalladas para Sebas — responde bien a "explícame esto"
- Lee ficheros existentes antes de editar — no inventa código

## Quirks conocidos
- Tiende a implementar si no se le frena — usar "quiero entendimiento, no implementación"
- Puede olvidar el contexto del PLC si la sesión es muy larga — recordarle con el smoke test
- Usa CLAUDE.md del repo de código como instrucciones primarias

## Cómo darle contexto al inicio de sesión
1. Abrir Claude Code en `TFG-Alumbrado`
2. Decirle que lea `TFG-Alumbrado-vault/AGENTS.md` y la nota diaria de hoy
3. Confirmar que entendió el estado antes de pedir trabajo
```

- [ ] **Step 3: Create Codex Context.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\50_AI_Context\Codex Context.md`:

```markdown
# Codex Context

**Herramienta:** OpenAI Codex CLI

## Qué funciona bien
- Revisión técnica precisa — detectó 8 bugs/mejoras en la spec del vault
- Estructura de código limpia y bien descompuesta
- Lee AGENTS.md automáticamente si está en la raíz del vault

## Quirks conocidos
- (completar con la experiencia acumulada en sesiones futuras)

## Cómo darle contexto al inicio de sesión
1. Abrir Codex en `TFG-Alumbrado-vault` o `TFG-Alumbrado`
2. Codex lee `AGENTS.md` automáticamente
3. Confirmar estado antes de pedir trabajo
```

- [ ] **Step 4: Commit 50_AI_Context**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git add "50_AI_Context/"
git commit -m "docs: seed 50_AI_Context — reglas compartidas y contexto por agente"
```

---

## Task 8: Seed 60_Concepts initial files

**Files:**
- Create: `TFG-Alumbrado-vault/60_Concepts/FINS-Protocol.md`
- Create: `TFG-Alumbrado-vault/60_Concepts/BCD-Encoding.md`

- [ ] **Step 1: Create FINS-Protocol.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\60_Concepts\FINS-Protocol.md`:

```markdown
# FINS Protocol

_First encountered: 2026-05-12_

## What it is

FINS (Factory Interface Network Service) es el protocolo propietario de Omron para comunicarse con sus PLCs. Funciona sobre UDP — como enviar una carta con un sobre de formato específico: la cabecera dice quién envía, quién debe recibir y qué comando ejecutar. El PLC lee el sobre, ejecuta el comando y responde con otro sobre del mismo formato.

En este proyecto usamos FINS para **leer memoria del PLC** — nunca para escribir.

## Why it matters for this project

El PLC expone su estado interno (qué secciones están encendidas, qué hora tiene, si hay errores) a través de áreas de memoria (HR, WR, DM, AR). La única forma de leer esas áreas desde Python es construir tramas FINS bien formadas y enviarlas por UDP al puerto 9600 del PLC.

## Structure de una trama FINS

```
Byte 0:    ICF  (Information Control Field) = 0x80 (comando) / 0xC0 (respuesta)
Byte 1:    RSV  (reservado) = 0x00
Byte 2:    GCT  (Gateway Count) = 0x02
Byte 3:    DNA  (Destination Network Address) = 0x00
Byte 4:    DA1  (Destination Node Address) = 0x01  ← nodo PLC
Byte 5:    DA2  (Destination Unit Address) = 0x00
Byte 6:    SNA  (Source Network Address) = 0x00
Byte 7:    SA1  (Source Node Address) = 0x37  ← nodo laptop (55 = 0x37)
Byte 8:    SA2  (Source Unit Address) = 0x00
Byte 9:    SID  (Service ID) = número de secuencia 0x01, 0x02...
Bytes 10-11: MRC/SRC (comando) = 0x01 0x01 para "leer memoria"
Bytes 12+: Parámetros del comando (área, dirección, número de words)
```

## Code example

```python
# fins/frame.py — construcción de trama de lectura de memoria
# Ejemplo: leer 11 words desde HR (área 0xB2) dirección 0x0000

def build_memory_read_frame(src_node, dst_node, sid, area_code, start_addr, count):
    # El área code indica qué tipo de memoria se lee:
    # 0xB2 = HR (Holding Relay) — bits que persisten aunque se apague el PLC
    # 0xB1 = WR (Work Relay) — bits de trabajo temporales
    # 0x82 = DM (Data Memory) — words de datos generales
    # 0xB3 = AR (Auxiliary Relay) — registros de sistema del PLC
    return bytes([
        0x80, 0x00, 0x02,        # ICF RSV GCT
        0x00, dst_node, 0x00,    # DNA DA1 DA2
        0x00, src_node, 0x00,    # SNA SA1 SA2
        sid,                     # SID (número de secuencia para emparejar respuesta)
        0x01, 0x01,              # MRC SRC = "Memory Area Read"
        area_code,               # qué área de memoria
        (start_addr >> 8) & 0xFF, start_addr & 0xFF,  # dirección inicio (big-endian)
        0x00,                    # bit offset (siempre 0 para lectura de words)
        (count >> 8) & 0xFF, count & 0xFF,  # número de words a leer
    ])
```

## Further reading

- Omron FINS Command Reference Manual (no disponible públicamente, preguntar al programador)
- `fins/frame.py` en TFG-Alumbrado — implementación real
- `fins/client.py` en TFG-Alumbrado — cliente que usa las tramas
```

- [ ] **Step 2: Create BCD-Encoding.md**

Create `C:\Users\sebas\TFG-Alumbrado-vault\60_Concepts\BCD-Encoding.md`:

```markdown
# BCD Encoding

_First encountered: 2026-05-12_

## What it is

BCD (Binary Coded Decimal) es una forma de guardar números decimales en binario. En vez de convertir el número completo a binario, guarda cada dígito decimal por separado usando 4 bits (un nibble).

**Ejemplo:** El número 48 en BCD se guarda como `0x48`:
- Nibble alto (4 bits de la izquierda): `0100` = 4 → las decenas
- Nibble bajo (4 bits de la derecha): `1000` = 8 → las unidades
- Resultado: 4×10 + 8 = 48

## Why it matters for this project

El reloj auxiliar del PLC (registros AR A351–A353) guarda la hora en BCD. Esto era común en hardware industrial antiguo porque los displays de 7 segmentos mostraban directamente un nibble por dígito.

El reloj DM (D500–D506) **no usa BCD** — usa enteros planos. Hay que saber cuál es cuál para decodificar correctamente.

## Code example

```python
# fins/frame.py — decodificación BCD del reloj AR
# A351 = 0x4827 → byte alto 0x48 = 48 minutos, byte bajo 0x27 = 27 segundos

def bcd_byte_to_int(byte: int) -> int:
    # Separa las decenas (nibble alto) y las unidades (nibble bajo)
    tens  = (byte >> 4) & 0xF   # desplaza 4 bits → solo quedan las decenas
    units = byte & 0xF           # máscara 0xF → solo quedan las unidades
    return tens * 10 + units    # reconstruye el número decimal

# Para decodificar un word BCD de 2 bytes (e.g. 0x4827):
word = 0x4827
high_byte = (word >> 8) & 0xFF  # → 0x48 → bcd_byte_to_int → 48 (minutos)
low_byte  = word & 0xFF          # → 0x27 → bcd_byte_to_int → 27 (segundos)
```

## Trampa frecuente

Si lees `0x48` y lo conviertes directamente a decimal obtienes 72 — incorrecto.
Si lo decodificas como BCD obtienes 48 — correcto.

El reloj DM usa enteros planos: D501=48 significa 48 minutos directamente, sin decodificación BCD.
```

- [ ] **Step 3: Commit 60_Concepts**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git add "60_Concepts/"
git commit -m "docs: seed 60_Concepts — FINS Protocol y BCD Encoding para Sebas"
```

---

## Task 9: Update code repo (.graphifyignore, .gitignore, CLAUDE.md)

**Files:**
- Create: `TFG-Alumbrado/.graphifyignore`
- Modify: `TFG-Alumbrado/.gitignore`
- Modify: `TFG-Alumbrado/CLAUDE.md`

- [ ] **Step 1: Create .graphifyignore**

Create `C:\Users\sebas\TFG-Alumbrado\.graphifyignore`:

```
# Secretos y configuración local
.env
.env.*

# Entornos virtuales y caché Python
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/

# Datos de brainstorming y superpowers
.superpowers/

# Capturas raw del PLC — usar 30_PLC/Smoke Test Findings.md en el vault
data/smoke_fins/*.json

# Bases de datos — datos en tiempo real, no código
*.db
*.sqlite

# Artefactos de Graphify — no indexarse a sí mismo
graph.json
graphify-out/
.graphify_cache/

# Rutas locales de máquina
LOCAL_PATHS.md

# Git y editor
.git/
.gitignore
*.pyc
```

- [ ] **Step 2: Add graph.json to .gitignore**

Check the current `.gitignore`:

```powershell
Get-Content "C:\Users\sebas\TFG-Alumbrado\.gitignore"
```

Add `graph.json` if not already present. Edit `C:\Users\sebas\TFG-Alumbrado\.gitignore` and add at the end:

```
# Graphify raw graph — regenerado localmente, no commitear
graph.json
graphify-out/
.graphify_cache/
```

- [ ] **Step 3: Add vault pointer to CLAUDE.md**

Open `C:\Users\sebas\TFG-Alumbrado\CLAUDE.md` and add this section after the `## Proyecto` header section (before `## Contexto técnico`):

```markdown
## Knowledge Base — Vault Obsidian

El vault de conocimiento del proyecto vive en un repositorio separado: `TFG-Alumbrado-vault`.

**Para agentes:** Leer `AGENTS.md` en la raíz del vault al inicio de cada sesión.
El vault contiene:
- Nota diaria con decisiones y findings de cada sesión (`10_Daily/`)
- Variables PLC validadas y pendientes (`30_PLC/`)
- Arquitectura y contratos (`40_Architecture/`)
- Conceptos técnicos explicados para Sebas (`60_Concepts/`)
- Mapa de código generado por Graphify (`graph/GRAPH_REPORT.md`)

**Ruta del vault en esta máquina:** Ver `LOCAL_PATHS.md` en la raíz del vault.
**Graphify no modifica este fichero ni `AGENTS.md` automáticamente.**
```

- [ ] **Step 4: Commit code repo changes**

```powershell
cd C:\Users\sebas\TFG-Alumbrado
git add .graphifyignore .gitignore CLAUDE.md
git commit -m "chore: añadir .graphifyignore, actualizar .gitignore y CLAUDE.md con puntero al vault"
```

---

## Task 10: Install Graphify and first run

**Files:**
- Read: Graphify installation docs at `https://graphify.net` (Sebas reviews manually)
- Create: `TFG-Alumbrado-vault/graph/GRAPH_REPORT.md` (after manual review)

- [ ] **Step 1: Consultar docs e instalar Graphify**

Antes de instalar, verificar el nombre exacto del paquete y el comando de instalación recomendado:

1. Consultar la guía oficial en `https://graphify.net` (sección instalación / README).
2. Ejecutar `graphify --help` si ya hay una versión disponible, para verificar la CLI correcta.
3. Una vez confirmado el nombre del paquete, instalar en el entorno virtual del repo de código:

```powershell
cd C:\Users\sebas\TFG-Alumbrado
.venv\Scripts\Activate.ps1
# Sustituir 'graphify' por el nombre correcto del paquete si difiere
pip install graphify
```

> ⚠️ No asumir que `pip install graphify` es correcto hasta verificarlo. El nombre del paquete PyPI puede diferir del nombre de la herramienta o la CLI. No instalar en el Python del sistema.

- [ ] **Step 2: Verify Graphify CLI is available**

```powershell
graphify --version
```

Expected: version string (e.g. `graphify 0.x.x`). If not found, check pip install output for the correct command name.

- [ ] **Step 3: Run Graphify against both repos**

```powershell
graphify \
  --source C:\Users\sebas\TFG-Alumbrado \
  --source C:\Users\sebas\TFG-Alumbrado-vault \
  --ignore C:\Users\sebas\TFG-Alumbrado\.graphifyignore \
  --output C:\Users\sebas\TFG-Alumbrado-vault\graph\
```

> ⚠️ The exact flags depend on Graphify's CLI. Check `graphify --help` and adjust. The goal is: index both repos, apply the ignore rules, output to `vault/graph/`.

- [ ] **Step 4: Review GRAPH_REPORT.md before committing**

Open `C:\Users\sebas\TFG-Alumbrado-vault\graph\GRAPH_REPORT.md` in a text editor or Obsidian.

Check:
- Does it describe the actual code structure? (`fins/`, `acquisition/`, `config/`)
- Does it reference any content it shouldn't? (secrets, raw JSON data, internal paths)
- Is the content accurate and useful for an agent starting a session?

**Only commit if the content passes review.**

- [ ] **Step 5: Commit GRAPH_REPORT.md to vault (if approved)**

```powershell
cd C:\Users\sebas\TFG-Alumbrado-vault
git add graph/GRAPH_REPORT.md
git commit -m "docs: añadir GRAPH_REPORT.md generado por Graphify — revisado manualmente"
```

`graph.html` is NOT committed — regenerate with `graphify` when needed.

- [ ] **Step 6: Open vault in Obsidian**

1. Open Obsidian
2. "Open folder as vault" → select `C:\Users\sebas\TFG-Alumbrado-vault`
3. Verify graph view shows connections between `10_Daily/`, `30_PLC/`, `60_Concepts/`
4. Verify `AGENTS.md` appears at the root

---

## Self-Review

**Spec coverage:**
- ✅ Vault repo creation + .gitignore
- ✅ AGENTS.md (full contract with session protocol, writing contract, newer-prevails rule, LOCAL_PATHS.md reference)
- ✅ LOCAL_PATHS.md (gitignored, machine-specific)
- ✅ 00_Index (Project Map + Pending Questions seeded with known PENDIENTEs including Plan B bugs)
- ✅ 10_Daily (today's note seeded with actual session findings)
- ✅ 20_Decisions (placeholder directory)
- ✅ 30_PLC (Variables Validated, Pending, Smoke Test Findings — curated, references filenames not raw JSON)
  - ✅ H10.13 = marmansec corregido (no selcer174); selcer termina en H10.11
  - ✅ W4-W14: solo W4.00–W11.13 declarados validados; W11.14–W14.15 marcados sin confirmar
  - ✅ D116/modfunalu: validado en Tabla_ES, no leído en smoke — marcado explícitamente
- ✅ 40_Architecture (Fase 2 Overview, MQTT Payload, SQLite Schema, API Contract)
  - ✅ API endpoints alineados con spec Fase 2: /, /api/estado, /api/secciones/actual, /api/horarios, /api/historial/ciclos, /api/historial/secciones
  - ✅ SQLite Schema: columna `timestamp` (no `ts`); `uq_ciclo_timestamp`; `timestamp` desnormalizado en `seccion_estado`; `horario_tramo` marcado como placeholder/raw
  - ✅ MQTT Payload: modfunalu marcado como spec/example, no como dato confirmado por smoke
- ✅ 50_AI_Context (Agent Rules, Claude Context, Codex Context)
- ✅ 60_Concepts (FINS-Protocol, BCD-Encoding — both with code examples for Sebas)
- ✅ .graphifyignore (all required excludes from Codex review: .env, .venv, .pytest_cache, .superpowers, data/smoke_fins/*.json, *.db, *.sqlite, graph.json, graphify-out)
- ✅ graph.json gitignored in code repo
- ✅ CLAUDE.md hand-written pointer (Graphify does not touch it)
- ✅ Graphify install: verificar nombre de paquete contra docs oficiales antes de instalar
- ✅ First run with manual review gate before commit
- ✅ graph.html not committed (gitignored, regenerated on demand)
- ✅ Commit solo si hubo trabajo real (no solo lectura trivial)
- ✅ Smoke capture wins for observed values only (semantic interpretation requires LD/Sebas)
- ✅ AGENTS.md session protocol: commit si hubo razonamiento/decisiones/aprendizaje, aunque no haya código

**Placeholder scan:** `horario_tramo.raw_words` marcado explícitamente como placeholder/TBD — esto es intencional por spec.

**Type consistency:** No shared types or method signatures across tasks — this is a configuration plan, not a code plan. N/A.
