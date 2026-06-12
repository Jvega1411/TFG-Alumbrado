# Spec historica: capa semantica FINS V2

**Fecha original:** 2026-05-23
**Estado:** superada por V3 desde 2026-05-28.

Esta especificacion queda solo como marcador historico. El contrato V2 partia
de una interpretacion que ya no se considera valida: tratar `W4..W13` como un
espejo indexado de secciones.

No usar este documento para implementar ni validar el pipeline actual. La
fuente vigente es:

- `docs/specs/2026-05-28-fins-v3-vector-salidas-logicas.md`

Resumen de la correccion V3:

- `schema_version=3`.
- `READ_BLOCKS_V3`.
- `secciones[]` no contiene campo de salida WR.
- `W4..W13` se publica como `vector_salidas_logicas`.
- El vector de salidas logicas no confirma salida fisica ni relacion 1:1 con
  secciones.
