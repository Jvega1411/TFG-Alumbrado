# Alumbrado Gateway V3

Gateway read-only para supervision del alumbrado industrial TVITEC. La RPi lee
memoria PLC Omron CJ2M por FINS/UDP y publica el estado por MQTT; el Lenovo
ingiere, persiste en SQLite, sirve API FastAPI y dashboard web.

## Alcance V3

- V3 no manda ordenes al PLC, no cambia bits, no fuerza salidas y no modifica
  memoria PLC.
- El PLC calcula la logica de alumbrado. V3 observa, valida, persiste y expone
  datos para supervision.
- `schema_version=3` es un clean break desde V2. Los payloads V2 no son
  compatibles.
- `W4-W13` se publica como `vector_salidas_logicas`: vector logico observado.
  No confirma estado fisico de luminarias y no es un mapa directo
  `seccion -> salida`.
- La relacion exacta entre secciones/maquinas y bits de `W4-W13` queda
  pendiente hasta validar la matriz `maquinas_planta[m].word_0..word_9`.

## Clean Break SQLite V2 -> V3

V3 no migra automaticamente una SQLite V2 existente. Antes de arrancar V3 en
Lenovo:

```powershell
cd C:\alumbrado-gateway
Stop-ScheduledTask -TaskName "AlumbradoSubscriber" -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName "AlumbradoAPI" -ErrorAction SilentlyContinue

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
Rename-Item data\bd_estados.db "bd_estados.v2-backup-$ts.db" -ErrorAction SilentlyContinue
```

Crear o revisar `.env` desde el template sin anadir secretos al repo:

```powershell
Copy-Item scripts\node-config\lenovo-env-template.env .env
notepad .env
```

Para primer arranque con BD limpia, `DB_AUTO_CREATE=true`. Tras verificar que
`schema-v3` pasa y la API arranca, se puede fijar `DB_AUTO_CREATE=false`.

## Lenovo Deploy, Start y Verify

Si V3 ya esta mergeado en `main`, usar el despliegue normal:

```powershell
.\scripts\node-config\lenovo-deploy.ps1
```

Si se despliega el branch WIP antes del merge, pedirlo explicitamente:

```powershell
.\scripts\node-config\lenovo-deploy.ps1 -Branch wip/v3-incomplete
```

El branch debe ser `wip/v3-incomplete` para pruebas pre-merge, o `main` una vez
mergeado V3. El deploy muestra branch y commit desplegados.

Arrancar Lenovo:

```powershell
.\scripts\node-config\lenovo-start.ps1
```

Verificar pipeline:

```powershell
.\scripts\node-config\verify-pipeline.ps1 `
  -ExpectedBranch wip/v3-incomplete `
  -MaxDataAgeSeconds 420 `
  -MaxIngestAgeSeconds 90
```

Tras mergear V3 a `main`, omitir `-ExpectedBranch` o usar `-ExpectedBranch main`.

Criterio de exito: `schema-v3` pasa, subscriber y API quedan activos, la API
responde y `verify-pipeline.ps1` termina con `PIPELINE OK`.

## RPi Publisher

En la RPi, usar solo el publisher read-only. No ejecutar pruebas contra PLC real
sin autorizacion operativa.

```bash
cd ~/dev/alumbrado-gateway
git fetch origin
git switch wip/v3-incomplete
git pull --ff-only origin wip/v3-incomplete
cp scripts/node-config/rpi-env-template.env .env
```

Revisar `.env` localmente. El template V3 usa intervalo conservador de 10 s y
heartbeat de 30 s. No guardar credenciales reales en git.

Prueba manual autorizada de un ciclo:

```bash
python -m acquisition.publisher --max-cycles 1
```

El payload esperado usa `schema_version=3` e incluye
`vector_salidas_logicas` y `contexto_plc_raw`.

## Rollback

Rollback a V2 o commit anterior:

```powershell
cd C:\alumbrado-gateway
Stop-ScheduledTask -TaskName "AlumbradoSubscriber" -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName "AlumbradoAPI" -ErrorAction SilentlyContinue
git fetch origin
git switch main
git pull --ff-only origin main
```

Restaurar la BD respaldada solo con autorizacion:

```powershell
Rename-Item data\bd_estados.db "bd_estados.v3-rollback-backup.db" -ErrorAction SilentlyContinue
Rename-Item data\bd_estados.v2-backup-YYYYMMDD-HHMMSS.db bd_estados.db
```

Despues, arrancar de nuevo con el script correspondiente al commit restaurado y
verificar el pipeline.

## Retencion SQLite

V3 persiste por ciclo el vector observado y contexto raw limitado. Para el
prototipo se acepta crecimiento controlado de SQLite durante ventanas cortas de
demo o validacion.

No hay script destructivo de purga en esta version. Cualquier backup, borrado,
compactacion o purga de ciclos antiguos debe ser manual, autorizado y con el
servicio parado. Para uso continuo, definir retencion de N dias antes de dejarlo
ejecutando de forma indefinida.
