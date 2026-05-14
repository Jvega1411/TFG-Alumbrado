# Plan F — Despliegue Lenovo: Subscriber, API, Startup y Acceso Remoto

> **For agentic workers:** Este plan crea scripts ejecutables. Los pasos marcados **[MANUAL]** los ejecuta el operador sobre el hardware real. Usar superpowers:executing-plans para iterar tarea a tarea.

**Goal:** Dejar el nodo IT (Lenovo) completamente operativo y accesible de forma remota: subscriber MQTT persistiendo en SQLite, FastAPI + dashboard activos, arranque automático al inicio de Windows y acceso remoto via AnyDesk.

**Topología confirmada (2026-05-13):**
```
[PLC 192.168.250.1]  OT
        │
  [RPi eth0: 192.168.250.220]  ← FINS read-only
  [RPi enx6083e7ac98fb: 10.0.0.1/30]  ← MQTT publisher
        │  enlace USB-Eth dedicado
        │
  [Lenovo "Ethernet 2": 10.0.0.2/30]  ← recibe MQTT
  [Lenovo "Ethernet": 192.168.2.177]  → red corporativa IT
```

**Estado heredado de Plan E (2026-05-13):**
- Mosquitto Lenovo: `Running`, `Automatic`, listener `10.0.0.2:1883`
- Windows Defender: allow MQTT desde `10.0.0.1`, block outbound a `192.168.250.0/24`
- `alumbrado-publisher-dev.service` en RPi: corregido, `disabled` hasta PLC real
- SSH Lenovo → RPi via `ssh master@10.0.0.1`: validado

**Prerrequisitos:**
- Plan B completado y pusheado a `origin/main`
- Plan C/D implementados (236 tests pasados)
- Mosquitto Lenovo activo (`Get-Service mosquitto` → `Running`)
- Git disponible en Lenovo (SSH key o HTTPS configurado)
- Python 3.11+ disponible en Lenovo

---

## File Map

| Fichero | Nodo | Descripción |
|---|---|---|
| `scripts/node-config/lenovo-deploy.ps1` | Lenovo | Clonar repo, venv, instalar dependencias |
| `scripts/node-config/lenovo-env-template.env` | Lenovo | Plantilla `.env` para nodo IT |
| `scripts/node-config/lenovo-start.ps1` | Lenovo | Arrancar subscriber + API (modo dev/manual) |
| `scripts/node-config/lenovo-task-runner.ps1` | Lenovo | Wrapper Task Scheduler con logs stdout/stderr |
| `scripts/node-config/lenovo-register-startup.ps1` | Lenovo | Registrar tareas de arranque automático (Task Scheduler) |
| `scripts/node-config/lenovo-firewall-api.ps1` | Lenovo | Regla Firewall para exponer API en red corporativa |
| `scripts/node-config/lenovo-anydesk.ps1` | Lenovo | Descargar e instalar AnyDesk |
| `scripts/node-config/alumbrado-publisher-dev.service` | RPi | Unidad systemd dev versionada para publisher |
| `scripts/node-config/rpi-enable-publisher.sh` | RPi | Habilitar y arrancar publisher contra PLC real |
| `scripts/node-config/verify-pipeline.ps1` | Lenovo | Verificación completa del pipeline end-to-end |

---

## Task 0: Pre-flight — Verificar estado Lenovo post-reboot

**Objetivo:** Confirmar que lo instalado en Plan E persiste antes de añadir más capas.

**[MANUAL] En Lenovo (PowerShell):**
```powershell
Get-NetIPAddress -InterfaceAlias "Ethernet 2" -AddressFamily IPv4
Get-Service mosquitto | Select-Object Name, Status, StartType
netstat -ano | Select-String "1883"
Get-NetFirewallRule -DisplayName "Mosquitto MQTT desde RPi" | Select-Object DisplayName, Enabled, Action
Get-NetFirewallRule -DisplayName "Bloquear salida red OT alumbrado" | Select-Object DisplayName, Enabled, Action
```

**Resultado esperado:**
- `Ethernet 2` → `10.0.0.2/30`
- `mosquitto` → `Running`, `StartType=Automatic`
- `netstat` → `TCP 10.0.0.2:1883 ... LISTENING`
- Ambas reglas Firewall → `Enabled=True`

**Si falta alguna regla:** re-ejecutar los comandos de Plan E Session 8 antes de continuar.

---

## Task 1: Clonar repo y configurar entorno Python

**[MANUAL] Ejecutar `scripts/node-config/lenovo-deploy.ps1` como administrador en Lenovo.**

El script clona el repo en `C:\alumbrado-gateway`, crea el venv y instala dependencias.

**[MANUAL] Crear `.env`:**
```powershell
Copy-Item "C:\alumbrado-gateway\scripts\node-config\lenovo-env-template.env" "C:\alumbrado-gateway\.env"
notepad "C:\alumbrado-gateway\.env"
```
Rellenar únicamente `MQTT_BROKER_HOST=10.0.0.2` (ya incluido en template). El resto tiene valores por defecto correctos para Lenovo.

**Verificación:**
```powershell
cd C:\alumbrado-gateway
.\.venv\Scripts\python.exe -m pytest tests\ -q --tb=no 2>&1 | Select-String "passed"
```
Esperado: `236 passed`.

---

## Task 2: Inicializar base de datos SQLite

**[MANUAL] En Lenovo (PowerShell), desde `C:\alumbrado-gateway`:**
```powershell
cd C:\alumbrado-gateway
.\.venv\Scripts\python.exe -m alembic upgrade head
```

**Verificación:**
```powershell
.\.venv\Scripts\python.exe -c "
import sqlite3, os
db = r'C:\alumbrado-gateway\data\bd_estados.db'
print('BD existe:', os.path.exists(db))
c = sqlite3.connect(db).cursor()
c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
print('Tablas:', [r[0] for r in c.fetchall()])
"
```
Esperado: `Tablas: ['ciclo', 'seccion_estado', 'horario_tramo', 'alembic_version']`

---

## Task 3: Arrancar subscriber MQTT (Plan C)

**[MANUAL] Arranque manual de prueba:**
```powershell
cd C:\alumbrado-gateway
.\.venv\Scripts\python.exe -m subscriber.listener
```
Esperar a ver el log `Subscriber MQTT iniciado`. Ctrl+C para detener.

Si el publisher RPi está activo, en pocos segundos aparecerán logs de payloads recibidos.

---

## Task 4: Arrancar FastAPI + dashboard (Plan D)

**[MANUAL] Arranque manual de prueba (ventana distinta):**
```powershell
cd C:\alumbrado-gateway
.\.venv\Scripts\python.exe main.py
```

**[MANUAL] Verificar en navegador:**
- `http://127.0.0.1:8000` → dashboard HTML
- `http://127.0.0.1:8000/api/estado` → JSON (404 si BD vacía, correcto)
- `http://127.0.0.1:8000/docs` → Swagger UI

Si `API_HOST=0.0.0.0` en `.env`, accesible también desde otra máquina en la red corporativa:
- `http://192.168.2.177:8000`

---

## Task 5: Arranque automático Windows (Task Scheduler)

**[MANUAL] Ejecutar `scripts/node-config/lenovo-register-startup.ps1` como administrador.**

Registra dos tareas en Task Scheduler:
- `AlumbradoSubscriber` — arranca subscriber al iniciar sesión
- `AlumbradoAPI` — arranca FastAPI al iniciar sesión

**Verificación:**
```powershell
Get-ScheduledTask -TaskName "AlumbradoSubscriber" | Select-Object TaskName, State
Get-ScheduledTask -TaskName "AlumbradoAPI" | Select-Object TaskName, State
```

Las tareas ejecutan PowerShell y redirigen stdout/stderr a ficheros reales en `C:\alumbrado-gateway\logs\`:
- `subscriber.log`
- `subscriber-err.log`
- `api.log`
- `api-err.log`

**Logs de las tareas** (en `C:\alumbrado-gateway\logs\`):
```powershell
Get-Content "C:\alumbrado-gateway\logs\subscriber.log" -Tail 20
Get-Content "C:\alumbrado-gateway\logs\api.log" -Tail 20
```

---

## Task 6: Regla Firewall para API en red corporativa

Solo necesaria si quieres acceder al dashboard desde otra máquina del edificio.

**[MANUAL] Ejecutar `scripts/node-config/lenovo-firewall-api.ps1` como administrador.**

Abre el puerto `8000 TCP` inbound solo desde la subred corporativa `192.168.2.0/21`.

---

## Task 7: Habilitar publisher en RPi (con PLC real conectado)

**Prerrequisito:** `eth0` de la RPi conectado físicamente a la red OT / switch PLC.

**[MANUAL] Desde Lenovo, entrar a la RPi:**
```powershell
ssh master@10.0.0.1
```

**[MANUAL] Ejecutar `scripts/node-config/rpi-enable-publisher.sh` en la RPi:**
```bash
bash ~/dev/alumbrado-gateway/scripts/node-config/rpi-enable-publisher.sh
```

El script:
1. Elimina la regla UFW temporal de SSH desde `192.168.250.200` solo si encuentra una unica regla candidata `22/tcp ALLOW IN`; si hay cero hace skip y si hay varias aborta
2. Valida conectividad al PLC (`ping -c 3 192.168.250.1`)
3. Ejecuta `run_publisher(max_cycles=1)` manual y muestra el payload
4. Pide confirmacion manual si el payload tiene al menos un bloque `status=ok`
5. Instala la unidad versionada y arranca `alumbrado-publisher-dev.service`

---

## Task 8: Instalar AnyDesk (acceso remoto al Lenovo)

**Por qué AnyDesk:**
- Recomendado por el departamento → IT lo conoce y no lo bloquea
- Gratuito para uso personal / no comercial (TFG incluido)
- Sin port forwarding, funciona en Windows 11 Home
- ID permanente + contraseña de acceso desatendido, igual de simple que Supremo

**[MANUAL] Ejecutar `scripts/node-config/lenovo-anydesk.ps1` como administrador.**

El script descarga el instalador desde `download.anydesk.com` (URL estable, siempre última versión) y lo instala en silencio. Al finalizar imprime el ID asignado.

**[MANUAL] Post-instalación:**
1. Abrir AnyDesk desde el escritorio
2. Ir a `Ajustes` → `Seguridad` → `Habilitar acceso no supervisado`
3. Establecer una **contraseña de acceso desatendido**
4. Anotar el **ID** (visible en la pantalla principal, ej. `123 456 789`) y la contraseña
5. Descargar el cliente AnyDesk en el equipo remoto (gratuito) y conectar con ese ID

**Verificación:**
- Desde otro equipo: abrir AnyDesk, introducir el ID del Lenovo, conectar
- Verificar que el dashboard en `http://127.0.0.1:8000` es visible desde esa sesión remota

---

## Task 9: Verificación end-to-end del pipeline completo

**[MANUAL] Ejecutar `scripts/node-config/verify-pipeline.ps1` en Lenovo.**

Comprueba en orden:
1. Mosquitto escuchando en `10.0.0.2:1883`
2. Subscriber activo (proceso Python corriendo)
3. API activa (responde HTTP)
4. BD con datos (al menos 1 ciclo en `ciclo`)
5. Conectividad AnyDesk activa

**Estado final esperado:**
```
[RPi] publisher → MQTT → [Lenovo] subscriber → SQLite → FastAPI → dashboard
                                  ↑ AnyDesk (acceso remoto)
```
