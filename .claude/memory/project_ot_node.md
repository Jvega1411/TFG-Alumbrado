---
name: Proyecto OT Node — contexto técnico
description: Hardware, red, variables PLC, jerarquía física y stack tecnológico
type: project
---

Sistema read-only de supervisión de alumbrado industrial en nave TVITEC.

**Hardware:**
- PLC: Omron CJ2M CPU32, IP 192.168.250.1, FINS node 1
- Nodo OT: RPi, Ubuntu 24.04 LTS aarch64, eth0 192.168.250.56 (FINS node 56)
- Nodo IT (Fase 2): Lenovo S500, Intel i3, Windows 10 — asignado por informática 2026-05-11
- Usuarios RPi: master (admin/sudo), gwsvc (servicio, sin sudo)

**Infraestructura física (confirmada 2026-05-11):**
- Cable ethernet ~40m desde cuadro eléctrico (PLC) hasta puesto de producción
- Conectividad verificada: ping 192.168.250.1 OK desde laptop en 192.168.250.55
- Enlace RPi↔Lenovo: adaptador USB-Eth en RPi (eth1) → cable RJ45 → NIC1 del Lenovo

**Arquitectura de red (confirmada 2026-05-11):**
- RPi eth0: red OT (192.168.250.x) — habla FINS con el PLC
- RPi eth1 (USB-Eth): subred de enlace hacia el Lenovo (ej. 10.0.0.1/30, pendiente confirmar)
- Lenovo NIC1: subred de enlace con RPi (10.0.0.2/30)
- Lenovo NIC2: ethernet de fábrica / red corporativa

**Principio de seguridad IT/OT (normativa, confirmado 2026-05-11):**
- Comunicación estrictamente unidireccional OT→IT: RPi solo publica, nunca recibe del Lenovo
- El Lenovo nunca inicia conexión hacia la RPi ni hacia la red OT
- Sin dual-homed systems: el Lenovo no tiene visibilidad de 192.168.250.0/24
- Protocolo de publicación: MQTT — broker Mosquitto en Lenovo, RPi es publisher only

**Why:** Read-only. El PLC nunca debe cambiar de modo RUN. NOT_RUN es alarma operacional crítica.

**Jerarquía física:**
- 1104 luminarias → 172 cerchas → 112 secciones
- El PLC expone estado a nivel de sección (H11–H31, 112 bits por grupo)
- El equivalente eléctrico monitorizado es el encendido de cada cercha

**Variables PLC adquiridas (mapa verificado contra snapshots reales):**
- Reloj: D500=seg, D501=min, D502=hora, D503=dia, D504=mes, D505=anio, D506=diasem
  ⚠️ D500/D505 están INTERCAMBIADOS en el PDF de documentación — usar mapeo verificado
- Modo alumbrado: D116 (0=horarios, 1=fotocélula, 2=ambos)
- Fotocélula: W25.bit0 (entfot1), H100.bit0 (memfunfotalu), H100.bit1 (memactfotalu)
- Secciones 112: H11–H17 (automaticos), H18–H24 (manuales), H25–H31 (memactsec)
- Horarios tramos 1-2: D1000–D1007; D1008=indsec (no es hora)
- Horarios fin tramos 3-12: D3632–D3651
- Diagnóstico: A401.bit8 (cycle_time_error), A402.bit4 (low_battery), A402.bit9 (io_verify_error)
- Valores llegan como enteros planos (no BCD)

**Stack por fases:**
- Fase 1 (RPi, Linux): Python 3.x, SQLAlchemy 2.0 + SQLite, Alembic, FastAPI, uvicorn — todo en RPi
- Fase 2 (Lenovo, Windows 10): RPi solo corre FINS reader + paho-mqtt publisher (ligero, sin BD ni API); Lenovo corre subscriber MQTT + SQL Server Express + FastAPI
- Migración: solo cambia connection string en .env + alembic upgrade head

**How to apply:** Antes de proponer cualquier decisión de modelo de datos o motor de BD, verificar que es compatible con SQLite Y SQL Server (sin queries específicas de un motor).
