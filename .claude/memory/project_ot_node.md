---
name: Proyecto OT Node — contexto técnico
description: Hardware, red, variables PLC, jerarquía física y stack tecnológico
type: project
---

Sistema read-only de supervisión de alumbrado industrial en nave TVITEC.

**Hardware:**
- PLC: Omron CJ2M CPU32, IP 192.168.250.1, FINS node 1
- RPi: Ubuntu 24.04 LTS aarch64, eth0 192.168.250.56 (FINS node 56)
- Red servicio RPi: wlan0 (hotspot móvil, primario) + eth1 USB adapter 10.10.10.1/30 (fallback laptop)
- DMZ (Fase 2): equipo Windows 10, eth1 del RPi pasará a conectar aquí
- Usuarios RPi: master (admin/sudo), gwsvc (servicio, sin sudo)

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
- Fase 1 (RPi, Linux): Python 3.x, SQLAlchemy 2.0 + SQLite, Alembic, FastAPI, uvicorn
- Fase 2 (DMZ, Windows 10): mismo stack, SQL Server Express (gratuito) en lugar de SQLite
- Migración: solo cambia connection string en .env + alembic upgrade head

**How to apply:** Antes de proponer cualquier decisión de modelo de datos o motor de BD, verificar que es compatible con SQLite Y SQL Server (sin queries específicas de un motor).
