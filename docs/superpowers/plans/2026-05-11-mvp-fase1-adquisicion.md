# MVP Fase 1 — Adquisición FINS + Persistencia SQLite

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Leer las áreas H11–H31 (estados de 112 secciones) y D116 (modo de funcionamiento) del PLC cada 30 segundos y persistirlos en dos bases de datos SQLite: `bd_estados.db` (estado actual, sobreescrito) y `bd_historizacion.db` (histórico append-only).

**Architecture:** Tres capas: `model/estados.py` define las tablas SQLAlchemy, `acquisition/poller.py` lee FINS y escribe en BD, `main.py` instancia todo y lanza el loop. Una sola lectura FINS (`read_h_range(11, 21)`) devuelve los 21 words que codifican 3 grupos × 112 bits (automaticos H11-H17, manuales H18-H24, horarios_activos H25-H31). La Config se extiende con dos URLs SQLite sobreescribibles por `.env`.

**Tech Stack:** Python **3.12** (target producción: Ubuntu 24.04 LTS en RPi), SQLAlchemy 2.0, SQLite (Fase 1), `fins.client.FINSClient`, `fins.frame.parse_words_to_int_list`

**Versiones:** desarrollo en Windows puede usar Python ≥ 3.12; el código debe ser compatible con 3.12.3 (RPi). No usar sintaxis ni stdlib exclusiva de 3.13+.

**Pruebas contra PLC real:** lectura mínima manual y autorizada. No escaneos ni lecturas agresivas.

---

## Mapeado PLC (fuente: Tabla_ES.html)

| Grupo PLC | Área | Words | Descripción |
|---|---|---|---|
| `automaticos[112]` | H11–H17 | offset 0–6 | funcionamiento automático por sección |
| `manuales[112]` | H18–H24 | offset 7–13 | marcha manual por sección |
| `horarios_activos[112]` | H25–H31 | offset 14–20 | memoria activación por sección |
| `modfunalu` | D116 | 1 word | modo global (0=horarios, 1=…) |

Extracción de bit para sección N (1-indexed): `(words[group_offset + (N-1)//16] >> ((N-1)%16)) & 1`

---

## File Map

| Fichero | Acción | Responsabilidad |
|---|---|---|
| `config/settings.py` | Modificar | Añadir `DB_ESTADOS_URL` y `DB_HIST_URL` |
| `model/estados.py` | **Reemplazar** placeholder | 4 tablas SQLAlchemy en 2 bases declarativas |
| `acquisition/poller.py` | **Reemplazar** placeholder | Extracción de bits + `run_once` + `run_loop` |
| `main.py` | **Reemplazar** placeholder | Arranque: validate → engines → client → loop |
| `tests/test_model.py` | Crear | Tests de tablas con SQLite en memoria |
| `tests/test_poller.py` | Crear | Tests de extracción de bits, run_once, run_loop |
| `data/.gitkeep` | Crear | Marca el directorio en git (ver nota .gitignore) |

> **Nota .gitignore:** usar el patrón siguiente para mantener el directorio versionado pero excluir las BDs:
> ```
> data/*
> !data/.gitkeep
> *.db
> *.sqlite
> ```

---

## Smoke test Windows-first (previo a Task 1, manual y autorizado)

Ejecutar **solo** desde el PC de desarrollo (192.168.250.x), con el PLC encendido y en RUN.  
Objetivo: confirmar conectividad FINS, longitud de respuesta y el código MRES/SRES real del CJ2M.  
No ejecutar contra RPi. No automatizar. No persistir nada todavía.

```python
# scripts/smoke_fins.py  — ejecutar manualmente, no forma parte del paquete
from fins.client import FINSClient
from fins.frame import parse_words_to_int_list, FINSError

with FINSClient() as client:
    # 1. Leer D116 — modfunalu (1 word)
    result_dm = client.read_dm_range(116, 1)
    words_dm = parse_words_to_int_list(result_dm['data'])
    print(f"D116 modfunalu = {words_dm[0]}")

    # 2. Leer H11-H31 — estados secciones (21 words)
    result_h = client.read_h_range(11, 21)
    words_h = parse_words_to_int_list(result_h['data'])
    assert len(words_h) == 21, f"Esperados 21 words, recibidos {len(words_h)}"
    print(f"H11-H31 OK — {len(words_h)} words recibidos")
    print(f"H11={words_h[0]:#06x}  H18={words_h[7]:#06x}  H25={words_h[14]:#06x}")
```

Ejecutar con:
```
python -m scripts.smoke_fins
```

Si el PLC no está en RUN, `FINSClient` lanzará `PLCNotInRunError(MRES=0x21, SRES=?)` — anotar el SRES real para validar el PENDIENTE operacional.

---

## Task 1: Config — URLs de bases de datos

**Files:**
- Modify: `config/settings.py`
- Modify: `tests/test_settings.py`

- [ ] **Step 1: Añadir tests de los nuevos atributos**

En `tests/test_settings.py`, añadir al final de la clase `TestConfigValidation`:

```python
def test_db_estados_url_default_is_sqlite(self):
    assert Config.DB_ESTADOS_URL.startswith('sqlite:///')
    assert 'bd_estados.db' in Config.DB_ESTADOS_URL

def test_db_hist_url_default_is_sqlite(self):
    assert Config.DB_HIST_URL.startswith('sqlite:///')
    assert 'bd_historizacion.db' in Config.DB_HIST_URL
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_settings.py::TestConfigValidation::test_db_estados_url_default_is_sqlite -v
```

Expected: `FAILED` con `AttributeError: type object 'Config' has no attribute 'DB_ESTADOS_URL'`

- [ ] **Step 3: Añadir los atributos a Config**

En `config/settings.py`, añadir dentro de la clase `Config` tras la línea de `LOG_DIR`:

```python
DB_ESTADOS_URL: str = os.getenv(
    'DB_ESTADOS_URL',
    'sqlite:///' + str(_project_root / 'data' / 'bd_estados.db'),
)
DB_HIST_URL: str = os.getenv(
    'DB_HIST_URL',
    'sqlite:///' + str(_project_root / 'data' / 'bd_historizacion.db'),
)
```

- [ ] **Step 4: Verificar que todos los tests de settings pasan**

```
pytest tests/test_settings.py -v
```

Expected: todos PASSED

- [ ] **Step 5: Crear directorio data/ y actualizar .gitignore**

```bash
mkdir data
echo "" > data/.gitkeep
```

Añadir al fichero `.gitignore` (o crearlo si no existe):

```
data/*.db
```

> Commit a petición del usuario cuando los tests pasen.

---

## Task 2: model/estados.py — Tablas SQLAlchemy

**Files:**
- Create: `model/estados.py`
- Create: `tests/test_model.py`

- [ ] **Step 1: Escribir los tests del modelo**

Crear `tests/test_model.py`:

```python
from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.estados import (
    BaseEstados, BaseHist,
    EstadoActual, EstadoSistema,
    HistorialSecciones, HistorialSistema,
)


@pytest.fixture
def engine_estados():
    engine = create_engine('sqlite:///:memory:')
    BaseEstados.metadata.create_all(engine)
    return engine


@pytest.fixture
def engine_hist():
    engine = create_engine('sqlite:///:memory:')
    BaseHist.metadata.create_all(engine)
    return engine


class TestEstadoActual:

    def test_upsert_creates_row(self, engine_estados):
        with Session(engine_estados) as s:
            s.merge(EstadoActual(
                seccion_id=1, automatico=True, manual=False,
                horario_activo=False, timestamp=datetime(2026, 1, 1), fins_ok=True,
            ))
            s.commit()
            row = s.get(EstadoActual, 1)
        assert row.automatico is True
        assert row.fins_ok is True

    def test_upsert_overwrites_existing_row(self, engine_estados):
        with Session(engine_estados) as s:
            s.merge(EstadoActual(
                seccion_id=5, automatico=True, manual=False,
                horario_activo=True, timestamp=datetime(2026, 1, 1), fins_ok=True,
            ))
            s.commit()
            s.merge(EstadoActual(
                seccion_id=5, automatico=False, manual=True,
                horario_activo=False, timestamp=datetime(2026, 1, 2), fins_ok=True,
            ))
            s.commit()
            row = s.get(EstadoActual, 5)
        assert row.automatico is False
        assert row.manual is True

    def test_accepts_112_sections(self, engine_estados):
        now = datetime.utcnow()
        with Session(engine_estados) as s:
            for i in range(1, 113):
                s.merge(EstadoActual(
                    seccion_id=i, automatico=False, manual=False,
                    horario_activo=False, timestamp=now, fins_ok=True,
                ))
            s.commit()
            count = s.query(EstadoActual).count()
        assert count == 112


class TestEstadoSistema:

    def test_upsert_always_id_1(self, engine_estados):
        with Session(engine_estados) as s:
            s.merge(EstadoSistema(
                id=1, modfunalu=0, timestamp=datetime(2026, 1, 1),
                fins_ok=True, error_msg=None,
            ))
            s.commit()
            s.merge(EstadoSistema(
                id=1, modfunalu=1, timestamp=datetime(2026, 1, 2),
                fins_ok=True, error_msg=None,
            ))
            s.commit()
            count = s.query(EstadoSistema).count()
            row = s.get(EstadoSistema, 1)
        assert count == 1
        assert row.modfunalu == 1

    def test_stores_error_msg(self, engine_estados):
        with Session(engine_estados) as s:
            s.merge(EstadoSistema(
                id=1, modfunalu=None, timestamp=datetime(2026, 1, 1),
                fins_ok=False, error_msg='MRES=0x21 SRES=0x08: CPU Unit status/error',
            ))
            s.commit()
            row = s.get(EstadoSistema, 1)
        assert row.fins_ok is False
        assert 'MRES' in row.error_msg


class TestHistorialSecciones:

    def test_append_only_multiple_rows_same_section(self, engine_hist):
        now = datetime.utcnow()
        with Session(engine_hist) as s:
            s.add(HistorialSecciones(
                timestamp=now, seccion_id=1,
                automatico=True, manual=False, horario_activo=True,
            ))
            s.add(HistorialSecciones(
                timestamp=now, seccion_id=1,
                automatico=False, manual=False, horario_activo=False,
            ))
            s.commit()
            count = s.query(HistorialSecciones).filter_by(seccion_id=1).count()
        assert count == 2


class TestHistorialSistema:

    def test_append_stores_error(self, engine_hist):
        now = datetime.utcnow()
        with Session(engine_hist) as s:
            s.add(HistorialSistema(
                timestamp=now, modfunalu=None,
                fins_ok=False, error_msg='timeout',
            ))
            s.commit()
            row = s.query(HistorialSistema).first()
        assert row.fins_ok is False
        assert row.error_msg == 'timeout'
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_model.py -v
```

Expected: `ImportError: cannot import name 'BaseEstados' from 'model.estados'`

- [ ] **Step 3: Implementar model/estados.py**

Crear `model/estados.py`:

```python
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase


class BaseEstados(DeclarativeBase):
    pass


class BaseHist(DeclarativeBase):
    pass


class EstadoActual(BaseEstados):
    __tablename__ = 'estado_actual'
    seccion_id = Column(Integer, primary_key=True)
    automatico = Column(Boolean, nullable=False)
    manual = Column(Boolean, nullable=False)
    horario_activo = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    fins_ok = Column(Boolean, nullable=False)


class EstadoSistema(BaseEstados):
    __tablename__ = 'estado_sistema'
    id = Column(Integer, primary_key=True, default=1)
    modfunalu = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    fins_ok = Column(Boolean, nullable=False)
    error_msg = Column(String, nullable=True)


class HistorialSecciones(BaseHist):
    __tablename__ = 'historial_secciones'
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    seccion_id = Column(Integer, nullable=False)
    automatico = Column(Boolean, nullable=False)
    manual = Column(Boolean, nullable=False)
    horario_activo = Column(Boolean, nullable=False)


class HistorialSistema(BaseHist):
    __tablename__ = 'historial_sistema'
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    modfunalu = Column(Integer, nullable=True)
    fins_ok = Column(Boolean, nullable=False)
    error_msg = Column(String, nullable=True)
```

- [ ] **Step 4: Verificar que los tests pasan**

```
pytest tests/test_model.py -v
```

Expected: todos PASSED

> Commit a petición del usuario cuando los tests pasen.

---

## Task 3: Extracción de bits de sección

**Files:**
- Create: `acquisition/poller.py` (esqueleto + `extract_section_bits`)
- Create: `tests/test_poller.py`

- [ ] **Step 1: Escribir los tests de extracción de bits**

Crear `tests/test_poller.py`:

```python
import pytest
from unittest.mock import Mock, patch
from acquisition.poller import extract_section_bits


class TestExtractSectionBits:

    def test_all_zeros_returns_false_for_all(self):
        words = [0] * 21
        result = extract_section_bits(words, 0)
        assert len(result) == 112
        assert all(v is False for v in result)

    def test_all_ones_returns_true_for_all(self):
        words = [0xFFFF] * 21
        result = extract_section_bits(words, 0)
        assert all(v is True for v in result)

    def test_section1_is_bit0_of_first_word(self):
        words = [0] * 21
        words[0] = 0x0001  # bit 0 set
        result = extract_section_bits(words, 0)
        assert result[0] is True   # sección 1
        assert result[1] is False  # sección 2

    def test_section16_is_bit15_of_first_word(self):
        words = [0] * 21
        words[0] = 0x8000  # bit 15 set
        result = extract_section_bits(words, 0)
        assert result[14] is False  # sección 15
        assert result[15] is True   # sección 16

    def test_section17_is_bit0_of_second_word(self):
        words = [0] * 21
        words[1] = 0x0001
        result = extract_section_bits(words, 0)
        assert result[15] is False  # sección 16
        assert result[16] is True   # sección 17

    def test_section112_is_bit15_of_seventh_word(self):
        words = [0] * 21
        words[6] = 0x8000
        result = extract_section_bits(words, 0)
        assert result[110] is False  # sección 111
        assert result[111] is True   # sección 112

    def test_group_offset_selects_correct_group(self):
        words = [0] * 21
        words[7] = 0x0001  # primer word del grupo en offset 7
        result_group0 = extract_section_bits(words, 0)
        result_group7 = extract_section_bits(words, 7)
        assert result_group0[0] is False  # grupo 0 no afectado
        assert result_group7[0] is True   # grupo 7, sección 1

    def test_returns_exactly_112_values(self):
        assert len(extract_section_bits([0] * 21, 0)) == 112
        assert len(extract_section_bits([0] * 21, 7)) == 112
        assert len(extract_section_bits([0] * 21, 14)) == 112
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_poller.py -v
```

Expected: `ImportError: cannot import name 'extract_section_bits' from 'acquisition.poller'`

- [ ] **Step 3: Implementar el esqueleto de poller.py con extract_section_bits**

Crear `acquisition/poller.py`:

```python
import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from fins.client import FINSClient
from fins.frame import FINSError, parse_words_to_int_list
from model.estados import (
    EstadoActual, EstadoSistema,
    HistorialSecciones, HistorialSistema,
)

logger = logging.getLogger(__name__)


def extract_section_bits(words: list, group_offset: int) -> list:
    result = []
    for i in range(112):
        word_idx = group_offset + i // 16
        bit_idx = i % 16
        result.append(bool((words[word_idx] >> bit_idx) & 1))
    return result
```

- [ ] **Step 4: Verificar que los tests pasan**

```
pytest tests/test_poller.py -v
```

Expected: todos PASSED

> Commit a petición del usuario cuando los tests pasen.

---

## Task 4: run_once — lectura FINS y persistencia

**Files:**
- Modify: `acquisition/poller.py`
- Modify: `tests/test_poller.py`

**Nota FINS endurecido:** `FINSClient.read_*_range()` lanza excepciones en errores FINS o respuestas malformadas (`FINSError`, `FINSProtocolError`, `FINSResponseError`, `PLCNotInRunError`) porque internamente usa `raise_on_error=True`. No escribir tests ni lógica que esperen `{'success': False, ...}` como camino normal de error.

**Separación FINS vs SQL:** `run_once` captura únicamente `(FINSError, OSError, ValueError)` — errores de capa FINS/red. Los errores SQLAlchemy (`sqlalchemy.exc.*`) **no** se capturan aquí; suben a `run_loop` y se registran como errores de ciclo. Esto distingue "el PLC no respondió" de "la BD local falló".

- [ ] **Step 1: Añadir tests de run_once**

Añadir al final de `tests/test_poller.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from acquisition.poller import run_once
from fins.frame import FINSResponseError
from model.estados import BaseEstados, BaseHist


def _h_bytes_word0_bit0() -> bytes:
    """21 words con bit0 del word0 de cada grupo a 1. Sección 1 activa en los 3 grupos."""
    return b'\x00\x01' * 21


def _dm_bytes(value: int) -> bytes:
    return bytes([(value >> 8) & 0xFF, value & 0xFF])


@pytest.fixture
def dbs():
    engine_e = create_engine('sqlite:///:memory:')
    engine_h = create_engine('sqlite:///:memory:')
    BaseEstados.metadata.create_all(engine_e)
    BaseHist.metadata.create_all(engine_h)
    return engine_e, engine_h


class TestRunOnce:

    def test_fins_ok_writes_112_estado_actual_rows(self, dbs):
        engine_e, engine_h = dbs
        client = Mock()
        client.read_h_range.return_value = {
            'success': True, 'mres': 0, 'sres': 0,
            'data': _h_bytes_word0_bit0(), 'word_count': 21,
        }
        client.read_dm_range.return_value = {
            'success': True, 'mres': 0, 'sres': 0,
            'data': _dm_bytes(0), 'word_count': 1,
        }
        with Session(engine_e) as sess_e, Session(engine_h) as sess_h:
            run_once(client, sess_e, sess_h)
        with Session(engine_e) as s:
            assert s.query(EstadoActual).count() == 112

    def test_fins_ok_section1_automatico_true(self, dbs):
        engine_e, engine_h = dbs
        client = Mock()
        # word 0 (H11) = 0x0001 → sección 1 automatico=True
        client.read_h_range.return_value = {
            'success': True, 'mres': 0, 'sres': 0,
            'data': _h_bytes_word0_bit0(), 'word_count': 21,
        }
        client.read_dm_range.return_value = {
            'success': True, 'mres': 0, 'sres': 0,
            'data': _dm_bytes(0), 'word_count': 1,
        }
        with Session(engine_e) as sess_e, Session(engine_h) as sess_h:
            run_once(client, sess_e, sess_h)
        with Session(engine_e) as s:
            row = s.get(EstadoActual, 1)
        assert row.automatico is True

    def test_fins_ok_stores_modfunalu(self, dbs):
        engine_e, engine_h = dbs
        client = Mock()
        client.read_h_range.return_value = {
            'success': True, 'mres': 0, 'sres': 0,
            'data': _h_bytes_word0_bit0(), 'word_count': 21,
        }
        client.read_dm_range.return_value = {
            'success': True, 'mres': 0, 'sres': 0,
            'data': _dm_bytes(1), 'word_count': 1,
        }
        with Session(engine_e) as sess_e, Session(engine_h) as sess_h:
            run_once(client, sess_e, sess_h)
        with Session(engine_e) as s:
            sys_row = s.get(EstadoSistema, 1)
        assert sys_row.modfunalu == 1
        assert sys_row.fins_ok is True

    def test_fins_error_writes_estado_sistema_fins_ok_false(self, dbs):
        engine_e, engine_h = dbs
        client = Mock()
        client.read_h_range.side_effect = FINSResponseError(0x21, 0x08)
        client.read_dm_range.side_effect = FINSResponseError(0x21, 0x08)
        with Session(engine_e) as sess_e, Session(engine_h) as sess_h:
            run_once(client, sess_e, sess_h)
        with Session(engine_e) as s:
            sys_row = s.get(EstadoSistema, 1)
        assert sys_row.fins_ok is False
        assert sys_row.error_msg is not None

    def test_fins_error_does_not_write_estado_actual(self, dbs):
        engine_e, engine_h = dbs
        client = Mock()
        client.read_h_range.side_effect = FINSResponseError(0x21, 0x08)
        client.read_dm_range.side_effect = FINSResponseError(0x21, 0x08)
        with Session(engine_e) as sess_e, Session(engine_h) as sess_h:
            run_once(client, sess_e, sess_h)
        with Session(engine_e) as s:
            assert s.query(EstadoActual).count() == 0

    def test_dm_error_preserves_sections_but_fins_ok_false(self, dbs):
        """H OK pero D116 falla: las secciones se persisten, fins_ok=False en EstadoSistema."""
        engine_e, engine_h = dbs
        client = Mock()
        client.read_h_range.return_value = {
            'success': True, 'mres': 0, 'sres': 0,
            'data': _h_bytes_word0_bit0(), 'word_count': 21,
        }
        client.read_dm_range.side_effect = FINSResponseError(0x04, 0x00)
        with Session(engine_e) as sess_e, Session(engine_h) as sess_h:
            run_once(client, sess_e, sess_h)
        with Session(engine_e) as s:
            assert s.query(EstadoActual).count() == 112
            sys_row = s.get(EstadoSistema, 1)
        assert sys_row.fins_ok is False
        assert sys_row.modfunalu is None

    def test_fins_ok_appends_historial_secciones_across_cycles(self, dbs):
        engine_e, engine_h = dbs
        client = Mock()
        client.read_h_range.return_value = {
            'success': True, 'mres': 0, 'sres': 0,
            'data': _h_bytes_word0_bit0(), 'word_count': 21,
        }
        client.read_dm_range.return_value = {
            'success': True, 'mres': 0, 'sres': 0,
            'data': _dm_bytes(0), 'word_count': 1,
        }
        with Session(engine_e) as sess_e, Session(engine_h) as sess_h:
            run_once(client, sess_e, sess_h)
            run_once(client, sess_e, sess_h)
        with Session(engine_h) as s:
            assert s.query(HistorialSecciones).count() == 224  # 2 ciclos × 112

    def test_fins_error_appends_historial_sistema(self, dbs):
        engine_e, engine_h = dbs
        client = Mock()
        client.read_h_range.side_effect = FINSResponseError(0x21, 0x08)
        client.read_dm_range.side_effect = FINSResponseError(0x21, 0x08)
        with Session(engine_e) as sess_e, Session(engine_h) as sess_h:
            run_once(client, sess_e, sess_h)
            run_once(client, sess_e, sess_h)
        with Session(engine_h) as s:
            assert s.query(HistorialSistema).count() == 2
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_poller.py::TestRunOnce -v
```

Expected: `ImportError: cannot import name 'run_once' from 'acquisition.poller'`

- [ ] **Step 3: Implementar run_once en acquisition/poller.py**

Añadir a continuación de `extract_section_bits` en `acquisition/poller.py`:

```python
def run_once(client: FINSClient, sess_estados: Session, sess_hist: Session) -> None:
    now = datetime.utcnow()
    error_msg = None
    modfunalu = None
    secciones_ok = False

    try:
        result_h = client.read_h_range(11, 21)
        words = parse_words_to_int_list(result_h['data'])
        automaticos = extract_section_bits(words, 0)
        manuales = extract_section_bits(words, 7)
        horarios = extract_section_bits(words, 14)
        secciones_ok = True
    except (FINSError, OSError, ValueError) as exc:
        error_msg = str(exc)

    try:
        result_dm = client.read_dm_range(116, 1)
        dm_words = parse_words_to_int_list(result_dm['data'])
        modfunalu = dm_words[0]
    except (FINSError, OSError, ValueError) as exc:
        if error_msg is None:
            error_msg = str(exc)

    fins_ok = secciones_ok and error_msg is None

    if secciones_ok:
        for i in range(112):
            sess_estados.merge(EstadoActual(
                seccion_id=i + 1,
                automatico=automaticos[i],
                manual=manuales[i],
                horario_activo=horarios[i],
                timestamp=now,
                fins_ok=True,
            ))
        for i in range(112):
            sess_hist.add(HistorialSecciones(
                timestamp=now,
                seccion_id=i + 1,
                automatico=automaticos[i],
                manual=manuales[i],
                horario_activo=horarios[i],
            ))

    sess_estados.merge(EstadoSistema(
        id=1,
        modfunalu=modfunalu,
        timestamp=now,
        fins_ok=fins_ok,
        error_msg=error_msg,
    ))
    sess_estados.commit()

    sess_hist.add(HistorialSistema(
        timestamp=now,
        modfunalu=modfunalu,
        fins_ok=fins_ok,
        error_msg=error_msg,
    ))
    sess_hist.commit()

    if fins_ok:
        logger.info("Ciclo OK — secciones actualizadas, modfunalu=%s", modfunalu)
    else:
        logger.warning("Ciclo con error FINS — %s", error_msg)
```

- [ ] **Step 4: Verificar que todos los tests del poller pasan**

```
pytest tests/test_poller.py -v
```

Expected: todos PASSED

> Commit a petición del usuario cuando los tests pasen.

---

## Task 5: run_loop — loop periódico tolerante a fallos

**Files:**
- Modify: `acquisition/poller.py`
- Modify: `tests/test_poller.py`

- [ ] **Step 1: Añadir tests de run_loop**

Añadir al final de `tests/test_poller.py`:

```python
from acquisition.poller import run_loop


class TestRunLoop:

    def test_run_loop_calls_run_once_each_cycle(self):
        call_count = [0]

        def fake_run_once(client, sess_e, sess_h):
            call_count[0] += 1

        sleep_count = [0]

        def fake_sleep(interval):
            sleep_count[0] += 1
            if sleep_count[0] >= 3:
                raise KeyboardInterrupt

        with patch('acquisition.poller.run_once', fake_run_once), \
             patch('acquisition.poller.time.sleep', fake_sleep):
            with pytest.raises(KeyboardInterrupt):
                run_loop(Mock(), Mock(), Mock(), 30)

        assert call_count[0] == 3

    def test_run_loop_does_not_propagate_run_once_exception(self):
        call_count = [0]

        def fake_run_once(client, sess_e, sess_h):
            call_count[0] += 1
            raise RuntimeError("FINS timeout simulado")

        sleep_count = [0]

        def fake_sleep(interval):
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                raise KeyboardInterrupt

        with patch('acquisition.poller.run_once', fake_run_once), \
             patch('acquisition.poller.time.sleep', fake_sleep):
            with pytest.raises(KeyboardInterrupt):
                run_loop(Mock(), Mock(), Mock(), 30)

        assert call_count[0] == 2

    def test_run_loop_sleeps_with_configured_interval(self):
        intervals = []

        def fake_sleep(interval):
            intervals.append(interval)
            raise KeyboardInterrupt

        with patch('acquisition.poller.run_once'), \
             patch('acquisition.poller.time.sleep', fake_sleep):
            with pytest.raises(KeyboardInterrupt):
                run_loop(Mock(), Mock(), Mock(), 45.0)

        assert intervals[0] == 45.0
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_poller.py::TestRunLoop -v
```

Expected: `ImportError: cannot import name 'run_loop' from 'acquisition.poller'`

- [ ] **Step 3: Implementar run_loop en acquisition/poller.py**

Añadir al final de `acquisition/poller.py`:

```python
def run_loop(client: FINSClient, sess_estados: Session, sess_hist: Session, interval_s: float) -> None:
    logger.info("Loop de adquisición iniciado. Intervalo: %ss", interval_s)
    while True:
        try:
            run_once(client, sess_estados, sess_hist)
        except Exception as exc:
            logger.error("Error en ciclo de adquisición: %s", exc)
        time.sleep(interval_s)
```

- [ ] **Step 4: Verificar que todos los tests del poller pasan**

```
pytest tests/test_poller.py -v
```

Expected: todos PASSED

> Commit a petición del usuario cuando los tests pasen.

---

## Task 6: main.py — entry point

**Files:**
- Create: `main.py`

No se escribe test unitario para `main` (es solo cableado). Se verifica con importación y suite completa.

- [ ] **Step 1: Implementar main.py**

Crear `main.py`:

```python
import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from acquisition.poller import run_loop
from config.settings import Config
from fins.client import FINSClient
from model.estados import BaseEstados, BaseHist

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    Config.validate()

    for url in (Config.DB_ESTADOS_URL, Config.DB_HIST_URL):
        if url.startswith('sqlite:///'):
            db_path = Path(url.replace('sqlite:///', '', 1))
            db_path.parent.mkdir(parents=True, exist_ok=True)

    engine_estados = create_engine(Config.DB_ESTADOS_URL)
    engine_hist = create_engine(Config.DB_HIST_URL)

    BaseEstados.metadata.create_all(engine_estados)
    BaseHist.metadata.create_all(engine_hist)

    logger.info("BDs inicializadas: %s | %s", Config.DB_ESTADOS_URL, Config.DB_HIST_URL)

    with FINSClient() as client, \
         Session(engine_estados) as sess_estados, \
         Session(engine_hist) as sess_hist:
        run_loop(client, sess_estados, sess_hist, Config.ACQUISITION_INTERVAL_S)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verificar que importa sin errores**

```
python -c "import main; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verificar que la suite completa pasa**

```
pytest tests/ -v
```

Expected: todos PASSED

> Commit a petición del usuario cuando los tests pasen.

---

## Self-Review

**Cobertura de spec:**
- H11-H31 (21 words, 3 grupos × 112 bits): Task 3 extrae los 3 grupos con `group_offset` 0/7/14, Task 4 los persiste ✅
- D116 (modfunalu): Task 4 llama `read_dm_range(116, 1)` y persiste en `estado_sistema` ✅
- BD_Estados (estado actual sobreescrito): Task 2 define `EstadoActual` + `EstadoSistema`, Task 4 hace merge ✅
- BD_Historizacion (append-only): Task 2 define `HistorialSecciones` + `HistorialSistema`, Task 4 usa `add` ✅
- SQLite fase 1, compatible SQLAlchemy para SQL Server fase 2: no hay SQL específico de motor ✅
- Config con URLs sobreescribibles: Task 1 ✅
- Tolerancia a fallos FINS: Task 4 testa path de error; Task 5 testa que `run_loop` no propaga excepciones ✅
- Sin API: no implementada ✅
- `main.py` crea directorio `data/` si no existe: Task 6 ✅

**Consistencia de tipos:**
- `extract_section_bits(words: list, group_offset: int) -> list` — Tasks 3 y 4 ✅
- `run_once(client, sess_estados, sess_hist)` — Tasks 4 y 5 ✅
- `run_loop(client, sess_estados, sess_hist, interval_s)` — Tasks 5 y 6 ✅
- `BaseEstados`, `BaseHist` — Task 2, importados en Tasks 4 y 6 ✅
