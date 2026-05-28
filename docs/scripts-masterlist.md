# Scripts Masterlist

Ratings: 5 = clean and long-lived, 3 = usable with known assumptions, 1 = fragile or temporary.

| Path | Role | Functionality | Clean | Longevity | Notes |
|---|---|---|---:|---:|---|
| `scripts/seed_dev_db.py` | Dev data | Creates and reseeds local SQLite sample data for UI/testing. | 3 | 3 | Local-only destructive seed. Keep away from real DB paths. |
| `scripts/node-config/pipeline_checks.py` | Lenovo helper | Python checks called by PowerShell diagnostics: config, MQTT host, DB liveness, recent cycles. | 4 | 4 | Keeps Python logic out of PowerShell strings. |
| `scripts/node-config/hmi_manual_diagnostic.py` | RPi/Lenovo diagnostics | Passive HMI manual troubleshooting: targeted HMI trace, wide declared-memory diff trace, and Lenovo DB inspection for recent cycles/section flags. | 4 | 4 | Read-only. Use during controlled HMI tests before changing PLC semantics. |
| `scripts/node-config/verify-pipeline.ps1` | Lenovo verification | End-to-end deployment check for venv, config, Mosquitto, subscriber/API processes, tasks, API HTTP, DB liveness, optional RPi ping, AnyDesk. | 4 | 4 | Important operator script. Python logic is delegated to `pipeline_checks.py`. |
| `scripts/node-config/inspect-api-db-state.ps1` | Lenovo diagnostics | Compares direct SQLite state against read-only API/dashboard responses. | 4 | 4 | Useful after deployment to explain what API is serving. |
| `scripts/node-config/lenovo-deploy.ps1` | Lenovo setup | Clones or pulls repo, creates venv, installs dependencies, creates data/log dirs. | 3 | 3 | Hard-coded repo/path; depends on Git/Python/network and operator credentials. |
| `scripts/node-config/lenovo-start.ps1` | Lenovo manual start | Starts subscriber and API as background Python processes with log redirection. | 3 | 3 | Simple fallback; Task Scheduler path is cleaner for normal runtime. |
| `scripts/node-config/lenovo-task-runner.ps1` | Lenovo runtime | Task Scheduler wrapper for subscriber/API with stdout/stderr log files. | 4 | 4 | Good operational boundary for Windows startup tasks. |
| `scripts/node-config/lenovo-register-startup.ps1` | Lenovo runtime setup | Registers subscriber and API Windows scheduled tasks. | 4 | 4 | Idempotently updates tasks; requires admin. |
| `scripts/node-config/lenovo-json-listener.ps1` | Lenovo diagnostics | Opens raw MQTT JSON listener in console without DB writes. | 4 | 3 | Useful manual diagnostic; not a service. |
| `scripts/node-config/lenovo-firewall-api.ps1` | Lenovo network | Opens inbound TCP 8000 from a fixed corporate CIDR. | 2 | 2 | Should become parameterized before broad reuse. Requires admin/network approval. |
| `scripts/node-config/lenovo-anydesk.ps1` | Lenovo remote access | Downloads and installs AnyDesk. | 2 | 2 | External download and manual security setup; keep optional. |
| `scripts/node-config/lenovo-cx-proxyarp-open.ps1` | Lenovo maintenance | Adds active-only OT maintenance IP `192.168.250.221/24` on `Ethernet 2` for the tested CX-One path. | 4 | 4 | Preferred CX path. Requires admin and matching RPi proxy-ARP window. Persistent cleanup requires `-RemovePersistent`. |
| `scripts/node-config/lenovo-cx-proxyarp-close.ps1` | Lenovo maintenance | Removes the temporary OT maintenance IP from ActiveStore by default. | 4 | 4 | Preferred cleanup pair for proxyarp-open. Persistent cleanup requires `-RemovePersistent`. |
| `scripts/node-config/lenovo-cx-route-open.ps1` | Lenovo maintenance | Adds temporary route to PLC network via RPi for the legacy NAT diagnostic path. | 3 | 2 | Legacy diagnostic only; not the preferred CX-One path. |
| `scripts/node-config/lenovo-cx-route-close.ps1` | Lenovo maintenance | Removes temporary PLC route via RPi for the legacy NAT diagnostic path. | 4 | 3 | Legacy cleanup pair for route-open. |
| `scripts/node-config/rpi-netplan-apply.sh` | RPi network setup | Writes static eth0 netplan for isolated OT/PLC network and applies it. | 3 | 3 | Privileged and system-changing; hard-coded eth0/PLC subnet. |
| `scripts/node-config/rpi-netplan-ot-static.yaml` | RPi network artifact | Versioned static netplan shape for eth0 OT/PLC network. | 4 | 3 | Config artifact, not executable. Interface assumptions must match hardware. |
| `scripts/node-config/rpi-ufw-cleanup.sh` | RPi firewall cleanup | Removes temporary SSH rule and prints expected UFW rules. | 3 | 3 | Good targeted cleanup, but expected rules are deployment-specific. |
| `scripts/node-config/rpi-enable-publisher.sh` | RPi publisher enablement | Removes temporary SSH rule, checks PLC ping, runs one publisher smoke cycle, installs/enables systemd unit after operator confirmation. | 3 | 3 | Privileged and PLC-facing; now uses publisher CLI instead of inline Python. |
| `scripts/node-config/rpi-cx-proxyarp-open.sh` | RPi maintenance | Opens tested no-NAT CX-One path using proxy ARP, host route, ICMP, TCP/UDP 9600, and TCP 44818. | 4 | 4 | Preferred CX path. Dedicated chain drops other Lenovo/OT traffic; requires explicit interfaces and stopped local FINS publisher. |
| `scripts/node-config/rpi-cx-proxyarp-close.sh` | RPi maintenance | Removes tagged proxy-ARP rules/chain, route, and restores saved sysctl state. | 4 | 4 | Deletes duplicate tagged direct rules if a command was repeated. |
| `scripts/node-config/rpi-cx-maintenance-open.sh` | RPi maintenance | Temporarily enables forwarding/NAT for Lenovo CX Programmer to PLC over FINS/UDP only. | 3 | 2 | Legacy diagnostic only; proxy-ARP path supersedes it for CX-One. |
| `scripts/node-config/rpi-cx-maintenance-close.sh` | RPi maintenance | Removes tagged legacy CX maintenance iptables/NAT rules and disables forwarding. | 4 | 3 | Legacy cleanup path; requires same interface values as open. |
| `scripts/node-config/alumbrado-publisher-dev.service` | RPi runtime artifact | Dev systemd unit for publisher under user `master` in dev path. | 4 | 3 | Dev-only by header; production unit should use production user/path. |
| `scripts/node-config/rpi-env-template.env` | RPi config template | Publisher-side `.env` template for PLC/FINS/MQTT/logs. | 4 | 4 | No secrets. Values are deployment defaults and must be verified. |
| `scripts/node-config/lenovo-env-template.env` | Lenovo config template | Subscriber/API `.env` template for MQTT/SQLite/FastAPI/logs. | 4 | 4 | No secrets. Broker and DB paths are defaults. |
