# CX Programmer - ventana temporal Lenovo a PLC

Objetivo: permitir que CX Programmer/CX-One en la Lenovo conecte temporalmente
con el PLC real `192.168.250.1` sin mover fisicamente la Lenovo al switch OT.
El camino probado usa IP temporal en Lenovo + proxy ARP/routing en RPi, sin NAT.

Este procedimiento es una excepcion OT manual. El estado normal sigue siendo
aislamiento entre Lenovo/IT y PLC/OT.

## Camino probado

- Lenovo `Ethernet 2`: enlace normal `10.0.0.2/30` + IP temporal
  `192.168.250.221/24`, sin gateway.
- RPi `eth0`: OT/PLC `192.168.250.220/24`.
- RPi `enx6083e7ac98fb`: enlace Lenovo `10.0.0.1/30`.
- RPi: `ip_forward=1`, proxy ARP en interfaces implicadas y ruta host
  `192.168.250.221/32 dev enx6083e7ac98fb`.
- Puertos permitidos solo entre `192.168.250.221` y `192.168.250.1`:
  ICMP, TCP/UDP `9600`, TCP `44818`.
- El script RPi envia todo trafico `192.168.250.221` <-> `192.168.250.0/24`
  a una cadena dedicada, acepta solo el par/puertos del PLC y termina en DROP.
  Asi el limite se mantiene aunque la politica FORWARD sea permisiva.
- La cadena y los saltos restrictivos se preparan antes de activar
  `ip_forward`/proxy ARP/ruta. Si falla la apertura, el script ejecuta rollback
  de saltos, cadena, ruta y sysctl guardados.
- El rollback de apertura solo elimina recursos creados por esa ejecucion. Si
  detecta una ventana ya abierta, aborta antes de armar rollback para no cerrar
  una maniobra existente.
- No usar MASQUERADE/NAT para este camino.
- La IP Lenovo se configura como `/24` porque fue el camino validado con
  CX-One. Esto hace que Windows vea la subred OT como on-link durante la
  ventana; por eso el cierre de trafico lo hace la RPi, no una ruta Windows.

## Precheck

- Confirmar IPs:
  - PLC: `192.168.250.1`
  - Lenovo enlace RPi: `10.0.0.2`
  - Lenovo mantenimiento OT: `192.168.250.221`
  - RPi lado Lenovo: `10.0.0.1`
  - RPi lado OT: `192.168.250.220`
- En la RPi, identificar interfaces reales:
  - `ip -br addr`
  - `ip route get 192.168.250.1`
  - `ip route get 10.0.0.2`
- Pausar la adquisicion FINS si hay un proceso usando UDP `9600` en la RPi.
  El script de apertura aborta si detecta un listener local.
- Confirmar que no hay bridge activo:
  - `ip link show type bridge`
- Validar que `192.168.250.221` esta libre en OT antes de usarla:
  - `ip neigh flush 192.168.250.221 2>/dev/null || true`
  - `ping -c 2 -W 1 192.168.250.221`
  - `ip neigh show 192.168.250.221`

## Abrir ventana

En la Lenovo, PowerShell como administrador:

```powershell
.\scripts\node-config\lenovo-cx-proxyarp-open.ps1
```

Si existe una IP persistente vieja `192.168.250.221`, el script aborta por
defecto. Limpiarla solo si se sabe que viene de una prueba anterior:

```powershell
.\scripts\node-config\lenovo-cx-proxyarp-open.ps1 -RemovePersistent
```

Si la IP ya existe en ActiveStore, el script solo la acepta si coincide con el
estado probado: `/24`, `SkipAsSource=False` y estado `Preferred` o `Tentative`.

En la RPi, sustituir interfaces por las reales:

```bash
sudo OT_IF=<interfaz_ot> LENOVO_IF=<interfaz_lenovo> \
  bash scripts/node-config/rpi-cx-proxyarp-open.sh
```

Ejemplo validado:

```bash
sudo OT_IF=eth0 LENOVO_IF=enx6083e7ac98fb \
  bash scripts/node-config/rpi-cx-proxyarp-open.sh
```

Validacion rapida:

```powershell
ping -S 192.168.250.221 192.168.250.1
```

```bash
sudo tcpdump -ni eth0 'host 192.168.250.221 and host 192.168.250.1 and (tcp port 9600 or udp port 9600 or tcp port 44818)'
```

Abrir CX Programmer/CX-One y conectar directo al PLC `192.168.250.1`.
No automatizar pruebas contra el PLC.

Parametros que funcionaron en campo:

- Conexion directa al PLC `192.168.250.1`.
- FINS/TCP en `9600` aparece durante la conexion.
- EtherNet/IP TCP `44818` tambien es necesario para CX-One.
- No depender de Browse/broadcast para la primera conexion.

## Cerrar ventana

Cerrar CX Programmer/CX-One.

En la RPi, con las mismas interfaces usadas en la apertura:

```bash
sudo OT_IF=<interfaz_ot> LENOVO_IF=<interfaz_lenovo> \
  bash scripts/node-config/rpi-cx-proxyarp-close.sh
```

En la Lenovo, PowerShell como administrador:

```powershell
.\scripts\node-config\lenovo-cx-proxyarp-close.ps1
```

Si una prueba manual anterior dejo la IP en PersistentStore:

```powershell
.\scripts\node-config\lenovo-cx-proxyarp-close.ps1 -RemovePersistent
```

Reanudar la adquisicion FINS si se habia pausado.

## Criterios de cierre

- `cat /proc/sys/net/ipv4/ip_forward` queda restaurado al valor previo
  guardado por el script; normalmente `0`.
- `iptables -S FORWARD | grep alumbrado-cx-proxyarp` no devuelve reglas.
- `iptables -S ALUMBRADO_CX_PROXYARP` falla o no muestra cadena.
- Si una referencia inesperada impide borrar la cadena, el cierre deja la
  cadena con DROP de seguridad y termina con error para revision manual.
- `ip route show 192.168.250.221/32` no muestra ruta via `enx6083e7ac98fb`.
- `Get-NetIPAddress -InterfaceAlias "Ethernet 2" -IPAddress 192.168.250.221`
  no muestra la IP temporal en la Lenovo.
- `Test-NetConnection 10.0.0.1 -Port 22` sigue usando `10.0.0.2` y da OK.

## Camino NAT legado

Los scripts siguientes quedan solo como diagnostico historico, no como canal
principal de CX Programmer:

- `scripts/node-config/rpi-cx-maintenance-open.sh`
- `scripts/node-config/rpi-cx-maintenance-close.sh`
- `scripts/node-config/lenovo-cx-route-open.ps1`
- `scripts/node-config/lenovo-cx-route-close.ps1`

Ese camino probaba forwarding/NAT para UDP `9600`, pero no hacia que el PLC
viera a la Lenovo como host real `192.168.250.x` y no cubria TCP `44818`.
