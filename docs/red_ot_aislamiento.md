# Aislamiento red OT — RPi gateway

Objetivo: impedir puenteo entre la interfaz OT/PLC de la RPi y el enlace
Lenovo/IT. En el despliegue validado, `eth0` es OT/PLC
`192.168.250.220/24` y `enx6083e7ac98fb` es el enlace Lenovo
`10.0.0.1/30`.

El switch del PLC solo debe ver tráfico FINS/UDP puerto 9600 desde la RPi
durante operacion normal.

Sustituir `<OT_IF>` por la interfaz real que mire al PLC. No asumir que el
adaptador USB es OT: en campo, el USB validado es el enlace Lenovo.

---

## Reconocimiento

| # | Comando | Qué hace y por qué |
|---|---------|-------------------|
| 1 | `ip link show` | Lista todas las interfaces de red del sistema con su estado (UP/DOWN). Identifica el nombre exacto del adaptador USB ethernet antes de tocar nada. |
| 2 | `ip addr show` | Muestra la IP asignada a cada interfaz. Confirma qué dirección tiene cada interfaz y si el adaptador USB ya tiene IP en el rango 192.168.250.x. |
| 3 | `ip route show` | Muestra la tabla de rutas activa. Detecta si ya existe alguna ruta que cruce tráfico entre eth0 y el adaptador OT. |
| 4 | `cat /proc/sys/net/ipv4/ip_forward` | Lee si el kernel está actuando como router entre interfaces (1=sí, 0=no). Si devuelve 1, el riesgo de puenteo está activo ahora mismo. |

## Deshabilitar forwarding

| # | Comando | Qué hace y por qué |
|---|---------|-------------------|
| 5 | `sudo sysctl -w net.ipv4.ip_forward=0` | Desactiva el forwarding de paquetes entre interfaces de forma inmediata. No persiste tras reinicio — es el paso de emergencia. |
| 6 | `echo "net.ipv4.ip_forward=0" \| sudo tee /etc/sysctl.d/99-no-ip-forward.conf` | Escribe la regla en sysctl.d para que sobreviva reinicios. Es el fichero de mayor prioridad y sobreescribe defaults del sistema. |
| 7 | `sudo sysctl --system` | Recarga todos los ficheros sysctl.d y confirma que el valor queda aplicado. Verifica que no hay otro fichero que lo reactive. |
| 8 | `sudo sysctl net.ipv4.conf.all.send_redirects=0 && echo "net.ipv4.conf.all.send_redirects=0" \| sudo tee -a /etc/sysctl.d/99-no-ip-forward.conf` | Impide que la RPi envíe ICMP redirects que podrían usarse para redirigir tráfico OT. Evita que actúe como router aunque alguien lo intente via ICMP. |

## Firewall UFW

Orden crítico: las reglas allow deben añadirse antes que los deny. UFW procesa por primera coincidencia.

| # | Comando | Qué hace y por qué |
|---|---------|-------------------|
| 9 | `sudo ufw status verbose` | Muestra si UFW está activo y qué políticas por defecto tiene. Si está inactivo, los pasos siguientes no tienen efecto hasta activarlo. |
| 10 | `sudo ufw default deny forward` | Establece DROP como política por defecto para paquetes en tránsito entre interfaces. Segunda línea de defensa si sysctl fallara por cualquier razón. |
| 11 | `sudo ufw allow in on <OT_IF> from 192.168.250.1 port 9600 proto udp` | Permite únicamente tráfico FINS/UDP entrante desde el PLC en la interfaz OT. Todo lo demás en esa interfaz queda bloqueado por las reglas siguientes. |
| 12 | `sudo ufw allow out on <OT_IF> to 192.168.250.1 port 9600 proto udp` | Permite únicamente tráfico FINS/UDP saliente hacia el PLC en la interfaz OT. El gateway solo puede hablar FINS con esa IP exacta. |
| 13 | `sudo ufw deny in on <OT_IF>` | Bloquea cualquier tráfico entrante por la interfaz OT que no haya sido permitido explícitamente arriba. Cierra el vector de entrada desde el switch del PLC. |
| 14 | `sudo ufw deny out on <OT_IF>` | Bloquea cualquier tráfico saliente por la interfaz OT que no sea FINS al PLC. Impide que la RPi origine tráfico inesperado hacia el switch. |
| 15 | `sudo ufw enable` | Activa el firewall si no lo estaba. Sin este paso todas las reglas anteriores están definidas pero no aplicadas. |

## Verificación

| # | Comando | Qué hace y por qué |
|---|---------|-------------------|
| 16 | `sudo ufw status numbered` | Lista todas las reglas en orden de prioridad con numeración. Confirma que las reglas FINS van antes que los deny generales. |
| 17 | `ip route show dev <OT_IF>` | Muestra solo las rutas de la interfaz OT. Debe aparecer únicamente 192.168.250.0/24 — ninguna ruta por defecto ni hacia red IT. |
| 18 | `ip link show type bridge` | Lista interfaces de tipo bridge. Debe devolver vacío — cualquier resultado aquí significa que existe un puente de red activo. |
| 19 | `ip route get 8.8.8.8 dev <OT_IF>` | Consulta la tabla de rutas en memoria sin enviar ningún paquete. Si devuelve `RTNETLINK: Network unreachable`, el aislamiento es correcto. |
| 20 | `sudo iptables -nvL FORWARD \| grep <OT_IF>` | Muestra los contadores de paquetes rechazados en FORWARD para la interfaz OT. El contador debe crecer en cualquier prueba de conectividad. |
