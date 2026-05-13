# Plan E — Configuración Nodos OT/IT: Red, Firewall y Servicios

> **For agentic workers:** Este plan crea ficheros de configuración y scripts. NO ejecuta comandos sobre red, systemd, firewall ni PLC real. Los comandos marcados con **[MANUAL]** los ejecuta el operador, no el agente. Usar superpowers:executing-plans para iterar tarea a tarea.

**Goal:** Configurar RPi como nodo OT seguro (FINS reader + MQTT publisher) y Lenovo como nodo IT seguro (Mosquitto broker + FastAPI + SQLite), con aislamiento estricto entre redes OT e IT y sin canal permanente de gestión IT→OT.

**Principios de seguridad obligatorios:**
- Comunicación unidireccional: RPi publica MQTT → Lenovo. El Lenovo nunca conecta hacia red OT.
- Sin ip_forward en RPi: ningún paquete cruza de eth0 (OT) a eth1 (IT) ni al revés.
- Sin NAT/masquerade en RPi: no se permite SNAT, DNAT ni MASQUERADE entre OT e IT.
- Forwarding denegado por defecto y sin reglas `route allow` OT↔IT en ningún sentido.
- Mosquitto escucha solo en la IP del enlace RPi (10.0.0.2), no en la NIC corporativa del Lenovo.
- Lenovo bloquea cualquier salida hacia 192.168.250.0/24.
- En producción, el usuario MQTT de la RPi (`gwpub`) solo publica en `alumbrado/#`; no tiene permisos de lectura.
- Gestión SSH a RPi: exclusivamente via hotspot temporal (wlan0) — sin canal permanente.

**Topología confirmada:**
```
[PLC 192.168.250.1]
        │  OT (192.168.250.0/24)
        │
  [RPi eth0: 192.168.250.56]     ← FINS read-only (ya configurado desde Fase 1)
  [RPi <RPi_IT_IF>: 10.0.0.1/30] ← MQTT publish hacia Lenovo (USB-Eth)
        │  enlace dedicado USB-Eth↔USB-Eth
        │
  [Lenovo <LENOVO_NIC1>: 10.0.0.2/30]  ← recibe MQTT de RPi (USB-Eth)
  [Lenovo <LENOVO_NIC2>: red corporativa] → IT / internet
  
  [RPi wlan0]  ← gestión SSH temporal solo via hotspot de teléfono
```

**Placeholders — rellenar tras Task 0 antes de ejecutar el resto:**

| Placeholder | Descripción | Confirmar con |
|---|---|---|
| `<RPi_IT_IF>` | Interfaz USB-Eth de RPi hacia Lenovo | `ip link show` en RPi (ej. `eth1`, `enx3c18a0…`) |
| `<LENOVO_NIC1>` | Nombre adaptador USB-Eth Lenovo hacia RPi | `Get-NetAdapter` en Lenovo |
| `<LENOVO_NIC2>` | Nombre NIC corporativa Lenovo | `Get-NetAdapter` en Lenovo |

**Subnets fijas:**
- OT (existente): 192.168.250.0/24 — RPi eth0: 192.168.250.56, PLC: 192.168.250.1
- Enlace RPi↔Lenovo: 10.0.0.0/30 — RPi: 10.0.0.1, Lenovo: 10.0.0.2

**Tech Stack:**
- RPi: Ubuntu 24.04 LTS aarch64, netplan, UFW, systemd, usuario `gwsvc`
- Lenovo: Windows 10, Mosquitto 2.x, Windows Defender Firewall, PowerShell

**Prerrequisitos:**
- Plan B completado y `acquisition/publisher.py` testeado localmente.
- Mosquitto 2.x descargado e instalado en Lenovo (https://mosquitto.org/download/).
- Usuario `gwsvc` existe en RPi (sin sudo).

---

## File Map

| Fichero | Nodo | Acción | Responsabilidad |
|---|---|---|---|
| `scripts/node-config/rpi-netplan-it-link.yaml` | RPi | Crear | IP estática 10.0.0.1/30 para interfaz IT |
| `scripts/node-config/rpi-ufw.sh` | RPi | Crear | Script UFW completo (OT + IT + gestión) |
| `scripts/node-config/rpi-publisher.service` | RPi | Crear | Unidad systemd para publisher |
| `scripts/node-config/rpi-wpa.conf.template` | RPi | Crear | Plantilla wpa_supplicant para hotspot de mantenimiento |
| `scripts/node-config/lenovo-ip.ps1` | Lenovo | Crear | Asignar IP estática a NIC1 |
| `scripts/node-config/mosquitto.conf` | Lenovo | Crear | Configuración Mosquitto: bind, ACL, log |
| `scripts/node-config/mosquitto-acl.conf` | Lenovo | Crear | ACL topics MQTT |
| `scripts/node-config/lenovo-firewall.ps1` | Lenovo | Crear | Reglas Windows Defender Firewall |
| `scripts/node-config/verify-rpi.sh` | RPi | Crear | Checklist de verificación en RPi |
| `scripts/node-config/verify-lenovo.ps1` | Lenovo | Crear | Checklist de verificación en Lenovo |

---

## Task 0: Pre-flight — Reconocimiento de interfaces

**Objetivo:** Identificar nombres reales de interfaces antes de tocar cualquier configuración. Sin este paso no continuar.

**[MANUAL] En RPi (como `master`):**
```bash
ip link show
ip addr show
```
Buscar: `eth0` con 192.168.250.56, y el adaptador USB-Eth (sin IP o con IP DHCP aleatoria).

```bash
ping -c 3 192.168.250.1   # debe responder — si no, detener aquí
```

Anotar el nombre real del USB-Eth → sustituir `<RPi_IT_IF>` en todos los ficheros del File Map.

**[MANUAL] En Lenovo (PowerShell como administrador):**
```powershell
Get-NetAdapter | Select-Object Name, InterfaceDescription, Status
```
Identificar qué adaptador es el USB-Eth hacia RPi (NIC1) y cuál es el de red corporativa (NIC2).

Anotar → sustituir `<LENOVO_NIC1>` y `<LENOVO_NIC2>`.

- [ ] **Step 1:** Crear `scripts/node-config/` si no existe (solo el directorio, no ejecutar nada).

---

## Task 1: RPi — IP estática en interfaz IT (enlace hacia Lenovo)

**Files:**
- Crear: `scripts/node-config/rpi-netplan-it-link.yaml`

- [ ] **Step 1: Crear fichero netplan**

```yaml
# Copiar a /etc/netplan/51-it-link.yaml en la RPi
# Sustituir <RPi_IT_IF> por el nombre real antes de copiar
network:
  version: 2
  renderer: networkd
  ethernets:
    <RPi_IT_IF>:
      dhcp4: false
      addresses:
        - 10.0.0.1/30
      routes: []
      nameservers:
        addresses: []
```

**[MANUAL] Aplicar en RPi:**
```bash
sudo cp scripts/node-config/rpi-netplan-it-link.yaml /etc/netplan/51-it-link.yaml
sudo chmod 600 /etc/netplan/51-it-link.yaml
sudo netplan apply
ip addr show <RPi_IT_IF>   # debe mostrar inet 10.0.0.1/30
```

---

## Task 2: RPi — Aislamiento OT + IT (UFW completo)

**Referencia OT:** `docs/red_ot_aislamiento.md` cubre forwarding y UFW para el lado OT (FINS hacia PLC). Esta task crea el script completo que integra ambos lados.

**Files:**
- Crear: `scripts/node-config/rpi-ufw.sh`

- [ ] **Step 1: Crear script UFW unificado**

```bash
#!/usr/bin/env bash
# rpi-ufw.sh — Configuración UFW completa RPi nodo OT
# Ejecutar como root. Sustituir <RPi_IT_IF> por el nombre real del USB-Eth.
# Sustituir <RPi_OT_IF> por el nombre de la interfaz OT hacia PLC (normalmente eth0).
set -euo pipefail

RPi_OT_IF="${RPi_OT_IF:-eth0}"
RPi_IT_IF="${RPi_IT_IF:?Debes exportar RPi_IT_IF antes de ejecutar este script}"

echo "[1/5] Deshabilitando ip_forward..."
sysctl -w net.ipv4.ip_forward=0
echo "net.ipv4.ip_forward=0" | tee /etc/sysctl.d/99-no-ip-forward.conf
echo "net.ipv4.conf.all.send_redirects=0" | tee -a /etc/sysctl.d/99-no-ip-forward.conf
sysctl --system

echo "[2/5] Aplicando politica UFW FORWARD DROP..."
ufw default deny forward

echo "[3/5] Reglas interfaz OT (FINS/UDP hacia PLC)..."
# Orden critico: allow antes que deny
ufw allow in  on "$RPi_OT_IF" from 192.168.250.1 port 9600 proto udp
ufw allow out on "$RPi_OT_IF" to   192.168.250.1 port 9600 proto udp
ufw deny  in  on "$RPi_OT_IF"
ufw deny  out on "$RPi_OT_IF"

echo "[4/5] Reglas interfaz IT (MQTT hacia Lenovo)..."
ufw allow out on "$RPi_IT_IF" to 10.0.0.2 port 1883 proto tcp
ufw deny  in  on "$RPi_IT_IF"

echo "[5/5] Reglas wlan0 (SSH gestion via hotspot — solo cuando activa)..."
ufw allow in on wlan0 to any port 22 proto tcp
ufw deny  in on wlan0

ufw enable
ufw status numbered

echo "UFW configurado. Verificar salida arriba antes de continuar."
```

**[MANUAL] Aplicar en RPi:**
```bash
sudo RPi_IT_IF=<RPi_IT_IF> bash scripts/node-config/rpi-ufw.sh
```

---

## Task 3: RPi — Servicio systemd para publisher

**Files:**
- Crear: `scripts/node-config/rpi-publisher.service`

**Prerrequisito:** Plan B completo, `acquisition/publisher.py` existe y `run_publisher()` funciona.

- [ ] **Step 1: Crear unidad systemd**

```ini
# Copiar a /etc/systemd/system/alumbrado-publisher.service en la RPi
[Unit]
Description=Alumbrado FINS/MQTT Publisher
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=gwsvc
WorkingDirectory=/opt/alumbrado-gateway
ExecStart=/opt/alumbrado-gateway/.venv/bin/python -m acquisition.publisher
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=alumbrado-publisher
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Nota: durante desarrollo usar `WorkingDirectory=/home/master/dev/alumbrado-gateway` y el `.venv` correspondiente. Cambiar a `/opt/` solo al pasar a producción.

**[MANUAL] Instalar en RPi:**
```bash
sudo cp scripts/node-config/rpi-publisher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable alumbrado-publisher.service
# NO arrancar todavia — hacerlo solo tras Task 7 (verificacion completa)
```

---

## Task 4: RPi — Plantilla wpa_supplicant para mantenimiento via hotspot

**Files:**
- Crear: `scripts/node-config/rpi-wpa.conf.template`

- [ ] **Step 1: Crear plantilla**

```conf
# rpi-wpa.conf.template — Plantilla para conexion hotspot de mantenimiento
# Copiar a /tmp/hotspot.conf, rellenar SSID y PSK, usar y borrar al terminar.
# NUNCA committear con credenciales reales.

ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=ES

network={
    ssid="SSID_DEL_HOTSPOT"
    psk="CLAVE_DEL_HOTSPOT"
    key_mgmt=WPA-PSK
}
```

**Procedimiento completo de mantenimiento SSH (ver sección al final del documento).**

---

## Task 5: Lenovo — IP estática en NIC1 (enlace hacia RPi)

**Files:**
- Crear: `scripts/node-config/lenovo-ip.ps1`

- [ ] **Step 1: Crear script PowerShell**

```powershell
# lenovo-ip.ps1 — Asignar IP estatica 10.0.0.2/30 a NIC1 (USB-Eth hacia RPi)
# Ejecutar como administrador. Sustituir LENOVO_NIC1 por el nombre real del adaptador.
param(
    [Parameter(Mandatory=$true)]
    [string]$NIC1,

    [Parameter(Mandatory=$true)]
    [string]$NIC2
)

Write-Host "[1/3] Eliminando IPs existentes en $NIC1..."
$existing = Get-NetIPAddress -InterfaceAlias $NIC1 -ErrorAction SilentlyContinue
if ($existing) {
    Remove-NetIPAddress -InterfaceAlias $NIC1 -Confirm:$false -ErrorAction SilentlyContinue
}

Write-Host "[2/3] Asignando 10.0.0.2/30 a $NIC1..."
New-NetIPAddress -InterfaceAlias $NIC1 -IPAddress 10.0.0.2 -PrefixLength 30

Write-Host "[3/3] Verificando que $NIC2 (red corporativa) no fue afectada..."
Get-NetIPAddress -InterfaceAlias $NIC2 | Select-Object IPAddress, PrefixLength

Write-Host "Verificar que 192.168.250.0/24 NO es alcanzable desde este equipo:"
$result = Test-NetConnection -ComputerName 192.168.250.1 -WarningAction SilentlyContinue
Write-Host "Alcanzable OT: $($result.PingSucceeded)   <- debe ser False"
```

**[MANUAL] Ejecutar en Lenovo (PowerShell como administrador):**
```powershell
.\scripts\node-config\lenovo-ip.ps1 -NIC1 "<LENOVO_NIC1>" -NIC2 "<LENOVO_NIC2>"
```

---

## Task 6: Lenovo — Mosquitto: configuración

**Files:**
- Crear: `scripts/node-config/mosquitto.conf`
- Crear: `scripts/node-config/mosquitto-acl.conf`

- [ ] **Step 1: Crear mosquitto.conf**

```conf
# mosquitto.conf — Nodo IT Lenovo
# Copiar a C:\Program Files\mosquitto\mosquitto.conf
#
# MODO DEV: allow_anonymous true — la proteccion la da el firewall (Task 7)
# MODO PROD: cambiar a false y configurar password_file con credenciales

listener 1883 10.0.0.2
protocol mqtt

# Dev: anonimo permitido (firewall bloquea todo menos 10.0.0.1)
allow_anonymous true

# Prod: descomentar estas dos lineas y comentar allow_anonymous true
# allow_anonymous false
# password_file C:\Program Files\mosquitto\passwd
#
# En RPi, configurar en .env antes de activar prod:
# MQTT_USERNAME=gwpub
# MQTT_PASSWORD=<valor generado por el operador; no commitear>

# ACL por topic (aplica en prod con allow_anonymous false)
acl_file C:\Program Files\mosquitto\acl.conf

persistence true
persistence_location C:\ProgramData\mosquitto\

log_dest file C:\ProgramData\mosquitto\mosquitto.log
log_type error
log_type warning
log_type information
log_timestamp true
```

- [ ] **Step 2: Crear mosquitto-acl.conf**

```conf
# mosquitto-acl.conf — Control de acceso por topic
# En modo dev (allow_anonymous true) este fichero no se aplica.
# En modo prod: usuario gwpub (RPi) puede publicar; admin puede leer todo.

# RPi publisher
user gwpub
topic write alumbrado/#

# Administrador (solo lectura para diagnostico)
user admin
topic read alumbrado/#
topic read $SYS/#
```

**[MANUAL] Instalar en Lenovo (PowerShell como administrador):**
```powershell
Copy-Item "scripts\node-config\mosquitto.conf" "C:\Program Files\mosquitto\mosquitto.conf" -Force
Copy-Item "scripts\node-config\mosquitto-acl.conf" "C:\Program Files\mosquitto\acl.conf" -Force

# Crear directorio de persistencia si no existe
New-Item -ItemType Directory -Force -Path "C:\ProgramData\mosquitto"

# Reiniciar servicio Mosquitto
Restart-Service mosquitto
Get-Service mosquitto  # Status debe ser Running

# Verificar que escucha SOLO en 10.0.0.2, no en 0.0.0.0
netstat -ano | Select-String "1883"
# Resultado esperado: TCP  10.0.0.2:1883  — NO debe aparecer 0.0.0.0:1883
```

---

## Task 7: Lenovo — Windows Defender Firewall

> **NOTA DE DISEÑO — por qué NO hay regla Block para puerto 1883:**
> En Windows Defender Firewall las reglas Block tienen precedencia absoluta sobre las Allow,
> independientemente del orden de creación. Una regla `Block TCP 1883 from Any` bloquearía
> también a 10.0.0.1, anulando la Allow. El aislamiento se garantiza por capas inferiores:
> (1) `listener 1883 10.0.0.2` en mosquitto.conf — Mosquitto no escucha en la NIC corporativa;
> (2) topología de red — solo la RPi tiene ruta a 10.0.0.2.
> La regla Allow para 10.0.0.1 añade intención explícita sin necesitar Block complementario.

**Files:**
- Crear: `scripts/node-config/lenovo-firewall.ps1`

- [ ] **Step 1: Crear script de firewall**

```powershell
# lenovo-firewall.ps1 — Reglas Windows Defender Firewall para nodo IT
# Ejecutar como administrador.
#
# Solo 2 reglas: Allow MQTT desde RPi + Block salida a red OT.
# NO se crea Block general para 1883: en Windows Firewall Block > Allow,
# lo que anularia la Allow. El aislamiento de 1883 lo da mosquitto.conf (bind 10.0.0.2).

Write-Host "[1/3] Eliminando reglas previas de Mosquitto/OT si existen..."
Get-NetFirewallRule | Where-Object {
    $_.DisplayName -like "*Mosquitto*" -or $_.DisplayName -like "*OT*alumbrado*"
} | Remove-NetFirewallRule

Write-Host "[2/3] Permitir MQTT entrante desde RPi (10.0.0.1) en puerto 1883..."
New-NetFirewallRule `
    -DisplayName "Mosquitto MQTT desde RPi" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 1883 `
    -RemoteAddress 10.0.0.1 `
    -Action Allow `
    -Profile Any `
    -Enabled True

Write-Host "[3/3] Bloquear salida hacia red OT 192.168.250.0/24..."
New-NetFirewallRule `
    -DisplayName "Bloquear salida red OT alumbrado" `
    -Direction Outbound `
    -RemoteAddress 192.168.250.0/24 `
    -Action Block `
    -Profile Any `
    -Enabled True

Write-Host "Reglas aplicadas:"
Get-NetFirewallRule | Where-Object {
    $_.DisplayName -like "*Mosquitto*" -or $_.DisplayName -like "*OT*alumbrado*"
} | Select-Object DisplayName, Direction, Action, Enabled

Write-Host ""
Write-Host "Verificar que Mosquitto escucha solo en 10.0.0.2 (no en 0.0.0.0):"
netstat -ano | Select-String "1883"
```

**[MANUAL] Ejecutar en Lenovo (PowerShell como administrador):**
```powershell
.\scripts\node-config\lenovo-firewall.ps1
```

---

## Task 8: Scripts de verificación

**Files:**
- Crear: `scripts/node-config/verify-rpi.sh`
- Crear: `scripts/node-config/verify-lenovo.ps1`

- [ ] **Step 1: Crear verify-rpi.sh**

```bash
#!/usr/bin/env bash
# verify-rpi.sh — Checklist post-configuracion RPi nodo OT
set -uo pipefail

RPi_OT_IF="${RPi_OT_IF:-eth0}"
RPi_IT_IF="${RPi_IT_IF:?Debes exportar RPi_IT_IF}"
PASS=0; FAIL=0

check() {
    local desc="$1"; shift
    if eval "$@" &>/dev/null; then
        echo "  PASS  $desc"; ((PASS++))
    else
        echo "  FAIL  $desc"; ((FAIL++))
    fi
}

echo "=== Verificacion RPi nodo OT ==="

check "ip_forward = 0" "[ \$(cat /proc/sys/net/ipv4/ip_forward) = '0' ]"
check "eth0 tiene 192.168.250.56" "ip addr show $RPi_OT_IF | grep -q '192.168.250.56'"
check "<RPi_IT_IF> tiene 10.0.0.1" "ip addr show $RPi_IT_IF | grep -q '10.0.0.1'"
check "ping PLC responde" "ping -c 1 -W 2 192.168.250.1"
check "ping Lenovo responde" "ping -c 1 -W 2 10.0.0.2"
check "UFW activo" "ufw status | grep -q 'Status: active'"
check "No bridge activo" "[ -z \"\$(ip link show type bridge 2>/dev/null)\" ]"
check "Sin NAT/masquerade IPv4" "! iptables -t nat -S 2>/dev/null | grep -Eq 'MASQUERADE|DNAT|SNAT'"
check "Sin reglas UFW route allow" "! ufw status numbered | grep -Ei 'ALLOW.*FWD|route allow'"
check "99-no-ip-forward.conf existe" "[ -f /etc/sysctl.d/99-no-ip-forward.conf ]"
check "publisher.service habilitado" "systemctl is-enabled alumbrado-publisher.service"

echo ""
echo "Resultado: $PASS pass, $FAIL fail"
[ "$FAIL" -eq 0 ] && echo "OK — listo para arrancar servicio" || echo "REVISAR fallos antes de arrancar"
```

- [ ] **Step 2: Crear verify-lenovo.ps1**

```powershell
# verify-lenovo.ps1 — Checklist post-configuracion Lenovo nodo IT
param(
    [Parameter(Mandatory=$true)] [string]$NIC1,
    [Parameter(Mandatory=$true)] [string]$NIC2
)

$pass = 0; $fail = 0

function Check($desc, $expr) {
    if (& $expr) { Write-Host "  PASS  $desc"; $script:pass++ }
    else         { Write-Host "  FAIL  $desc"; $script:fail++ }
}

Write-Host "=== Verificacion Lenovo nodo IT ==="

Check "NIC1 tiene 10.0.0.2" {
    (Get-NetIPAddress -InterfaceAlias $NIC1 -ErrorAction SilentlyContinue).IPAddress -contains "10.0.0.2"
}
Check "NIC2 tiene IP corporativa (no 10.0.0.x)" {
    $ip = (Get-NetIPAddress -InterfaceAlias $NIC2 -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
    $ip -and -not ($ip -like "10.0.0.*")
}
Check "Mosquitto servicio Running" {
    (Get-Service mosquitto -ErrorAction SilentlyContinue).Status -eq "Running"
}
Check "Mosquitto escucha en 10.0.0.2:1883" {
    netstat -ano | Select-String "10\.0\.0\.2:1883" | Select-String "LISTEN"
}
Check "Mosquitto NO escucha en 0.0.0.0:1883" {
    -not (netstat -ano | Select-String "0\.0\.0\.0:1883")
}
Check "Red OT no alcanzable desde Lenovo" {
    -not (Test-NetConnection -ComputerName 192.168.250.1 -WarningAction SilentlyContinue).PingSucceeded
}
Check "Regla firewall MQTT desde RPi existe" {
    Get-NetFirewallRule -DisplayName "Mosquitto MQTT desde RPi" -ErrorAction SilentlyContinue
}
Check "Regla bloqueo red OT existe" {
    Get-NetFirewallRule -DisplayName "Bloquear salida red OT alumbrado" -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Resultado: $pass pass, $fail fail"
if ($fail -eq 0) { Write-Host "OK — listo para test end-to-end" }
else             { Write-Host "REVISAR fallos antes de continuar" }
```

**[MANUAL] Ejecutar verificaciones:**
```bash
# En RPi:
sudo RPi_IT_IF=<RPi_IT_IF> bash scripts/node-config/verify-rpi.sh

# En Lenovo (PowerShell admin):
.\scripts\node-config\verify-lenovo.ps1 -NIC1 "<LENOVO_NIC1>" -NIC2 "<LENOVO_NIC2>"
```

---

## Test Plan (end-to-end tras pasar ambas verificaciones)

**Criterio de éxito:** todos los checks en verde antes de arrancar el servicio.

- [ ] Desde RPi: `ping -c 3 10.0.0.2` — 3/3 recibidos
- [ ] Desde RPi (mosquitto-clients): `mosquitto_pub -h 10.0.0.2 -p 1883 -t "alumbrado/test" -m "ping"` — sin error
- [ ] Desde Lenovo: `mosquitto_sub -h 10.0.0.2 -p 1883 -t "alumbrado/#" -v` — recibe el mensaje "ping"
- [ ] Desde Lenovo: `Test-NetConnection -ComputerName 192.168.250.1` — False (aislamiento OT)
- [ ] Arrancar publisher: `sudo systemctl start alumbrado-publisher.service` + `journalctl -u alumbrado-publisher -n 50`
- [ ] Confirmar que llegan mensajes reales en Lenovo suscriptor tras arranque del publisher

---

## Procedimiento de mantenimiento: SSH via hotspot de teléfono

**Cuándo:** Solo cuando se necesita acceso SSH a la RPi. No dejar activo.
**El enlace USB-Eth MQTT permanece activo durante el mantenimiento** — la adquisición no se interrumpe.

```
1. Encender hotspot en el teléfono (anotar SSID y clave)

2. En RPi (acceso físico o sesión activa):
   cp scripts/node-config/rpi-wpa.conf.template /tmp/hotspot.conf
   # Editar /tmp/hotspot.conf con SSID y PSK reales
   sudo wpa_supplicant -B -i wlan0 -c /tmp/hotspot.conf
   sudo dhclient wlan0
   ip addr show wlan0   # anotar IP asignada (ej. 192.168.43.x)

3. Conectar Lenovo al mismo hotspot (WiFi del Lenovo)

4. SSH desde Lenovo:
   ssh master@<RPi_HOTSPOT_IP>

5. Al terminar:
   sudo ip link set wlan0 down
   sudo kill $(pgrep wpa_supplicant) 2>/dev/null; sudo kill $(pgrep dhclient) 2>/dev/null
   rm /tmp/hotspot.conf

6. Apagar hotspot del teléfono
```

**Invariantes durante mantenimiento:**
- UFW permite SSH solo en wlan0 — sin acceso SSH por eth1 ni eth0.
- wlan0 no tiene ruta hacia red OT ni hacia eth1 (ip_forward=0 + reglas UFW).
- /tmp/hotspot.conf con credenciales: crear en el momento, borrar al terminar, nunca committear.

---

## Assumptions

- Mosquitto 2.x instalado en `C:\Program Files\mosquitto\` antes de Task 6.
- Usuario `gwsvc` ya existe en RPi sin sudo (creado en setup Fase 1).
- `paho-mqtt` está en `requirements.txt` del proyecto y disponible en `.venv`.
- La subnet 10.0.0.0/30 no colisiona con ninguna red existente en el Lenovo (verificar con `Get-NetIPAddress` antes de Task 5).
- La configuración `allow_anonymous true` en Mosquitto es aceptable para dev; cambiar a `false` con `password_file` antes de producción.
- En producción con `allow_anonymous false`, el publisher usa `MQTT_USERNAME`/`MQTT_PASSWORD` desde `.env`; nunca commitear valores reales.
- Plan B implementado y todos sus tests pasan antes de ejecutar Task 3 (systemd service).
- Plan C (subscriber SQLite en Lenovo) queda fuera del scope de este plan — se ejecuta después.
