# Spec: contrato FINS V3 - lectura minima observable

**Fecha:** 2026-05-28
**Estrategia:** clean break desde V2. No hay compatibilidad con mensajes
`schema_version=2`.

## Decision

El contrato V3 expone memoria PLC observada localmente. El rango `W4..W13` ya
no se interpreta como espejo indexado de `secciones[1..112]`; se publica como
bloque independiente
`vector_salidas_logicas`.

La causa es la logica del bloque funcional de alumbrado: las secciones o
maquinas activas aportan patrones de 10 words que se acumulan por OR. Por
tanto, `W4..W13` es un resultado muchos-a-muchos y no permite validar una
relacion directa `seccion -> bit WR` sin la matriz
`maquinas_planta[m].word_0..word_9`.

## Contrato

`READ_BLOCKS_V3` contiene:

```python
(
    "secciones",
    "modo",
    "fotocelula",
    "reloj",
    "horarios",
    "diagnostico",
    "reset_temporizado",
    "hmi_original",
    "reloj_ar",
    "vector_salidas_logicas",
    "contexto_plc_raw",
)
```

Payload:

```json
{
  "schema_version": 3,
  "secciones": [
    {
      "id": 1,
      "automatico_calculado": false,
      "manual_activo": false,
      "salida_interna": false
    }
  ],
  "vector_salidas_logicas": {
    "source_range": "W4-W13",
    "raw_words": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "bits": [
      {
        "id": 1,
        "word": "W4",
        "bit": 0,
        "source": "W4.00",
        "activa": false
      }
    ]
  },
  "contexto_plc_raw": {
    "ranges": [
      {"area": "H", "source_range": "H0-H42", "raw_words": [0]},
      {"area": "H", "source_range": "H100", "raw_words": [0]},
      {"area": "W", "source_range": "W1", "raw_words": [0]},
      {"area": "W", "source_range": "W4-W13", "raw_words": [0]},
      {"area": "W", "source_range": "W25", "raw_words": [0]},
      {"area": "D", "source_range": "D100-D116", "raw_words": [0]},
      {"area": "D", "source_range": "D500-D506", "raw_words": [0]},
      {"area": "D", "source_range": "D1000-D1007", "raw_words": [0]},
      {"area": "D", "source_range": "D1008-D1009", "raw_words": [0]},
      {"area": "D", "source_range": "D3630-D3651", "raw_words": [0]},
      {"area": "A", "source_range": "A351-A353", "raw_words": [0]},
      {"area": "A", "source_range": "A401-A402", "raw_words": [0]}
    ]
  }
}
```

Nota: el ejemplo de `contexto_plc_raw` es abreviado; en payload real
`raw_words` tiene longitud fija segun el rango. `contexto_plc_raw` transporta
solo comunicacion raw del PLC: `area`, `source_range` y `raw_words`.

## Persistencia y API

- `seccion_estado.salida_wr` desaparece.
- `salidas_wr_state` se reemplaza por `vector_salidas_logicas_state`.
- La API expone `GET /api/ciclos/{id}/vector_salidas_logicas`.
- La API expone `GET /api/ciclos/{id}/contexto_plc_raw` para auditoria raw
  selectiva.
- Los contadores de secciones no incluyen WR; `senales_observadas_activas` se
  calcula con `automatico_calculado`, `manual_activo` o `salida_interna`.

## Pendiente explicito

- No se reinterpreta el rango de secciones `101..112`.
- No se reinterpreta la formula automatico/horario.
- `W4..W13` queda como vector logico observado.
- El reloj AR/A354 queda fuera de este cambio.
