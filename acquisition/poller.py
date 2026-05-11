import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from fins.client import FINSClient
from fins.frame import FINSError, parse_words_to_int_list
from model.estados import (
    EstadoActual,
    EstadoSistema,
    HistorialSecciones,
    HistorialSistema,
)

logger = logging.getLogger(__name__)


def extract_section_bits(words: list, group_offset: int) -> list:
    result = []
    for i in range(112):
        word_idx = group_offset + i // 16
        bit_idx = i % 16
        result.append(bool((words[word_idx] >> bit_idx) & 1))
    return result
