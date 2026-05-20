# CX Programmer - ventana temporal Lenovo a PLC

Objetivo: permitir que CX Programmer en la Lenovo conecte temporalmente con el
PLC real `192.168.250.1` por FINS/UDP `9600`, usando la RPi como router/NAT
solo durante mantenimiento.

Este procedimiento es una excepcion OT manual. El estado normal sigue siendo
aislamiento entre Lenovo/IT y PLC/OT.

## Precheck

- Confirmar IPs:
  - PLC: `192.168.250.1`
  - Lenovo: `10.0.0.2`
  - RPi lado Lenovo: `10.0.0.1`
- En la RPi, identificar interfaces reales:
  - `ip -br addr`
  - `ip route get 192.168.250.1`
  - `ip route get 10.0.0.2`
- Pausar la adquisicion FINS si hay un proceso usando UDP `9600` en la RPi.
  El script de apertura avisa si detecta un listener local.
- Confirmar que no hay bridge activo:
  - `ip link show type bridge`

## Abrir ventana

En la RPi, sustituir interfaces por las reales:

```bash
sudo OT_IF=<interfaz_ot> LENOVO_IF=<interfaz_lenovo> \
  bash scripts/node-config/rpi-cx-maintenance-open.sh
```

En la Lenovo, PowerShell como administrador:

```powershell
.\scripts\node-config\lenovo-cx-route-open.ps1
```

Si Windows no resuelve la interfaz correcta hacia la RPi, indicar el adaptador:

```powershell
.\scripts\node-config\lenovo-cx-route-open.ps1 -InterfaceAlias "<adaptador_lenovo>"
```

Abrir CX Programmer y conectar al PLC `192.168.250.1` usando FINS/UDP `9600`.
No automatizar pruebas contra el PLC.

## Cerrar ventana

Cerrar CX Programmer.

En la Lenovo, PowerShell como administrador:

```powershell
.\scripts\node-config\lenovo-cx-route-close.ps1
```

En la RPi, con las mismas interfaces usadas en la apertura:

```bash
sudo OT_IF=<interfaz_ot> LENOVO_IF=<interfaz_lenovo> \
  bash scripts/node-config/rpi-cx-maintenance-close.sh
```

Reanudar la adquisicion FINS si se habia pausado.

## Criterios de cierre

- `cat /proc/sys/net/ipv4/ip_forward` devuelve `0` en la RPi.
- `iptables -S FORWARD | grep alumbrado-cx-maintenance` no devuelve reglas.
- `iptables -t nat -S POSTROUTING | grep alumbrado-cx-maintenance` no devuelve reglas.
- `Get-NetRoute -DestinationPrefix 192.168.250.0/24` no muestra la ruta via
  `10.0.0.1` en la Lenovo.

## Pendiente antes de uso real

- Confirmar nombres reales de interfaces RPi.
- Confirmar si CX Programmer necesita algun puerto adicional aparte de
  FINS/UDP `9600`. Por defecto no se abre nada mas.
