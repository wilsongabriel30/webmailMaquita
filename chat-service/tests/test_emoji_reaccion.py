# -*- coding: utf-8 -*-
"""Refuerzo de A-1: el servidor solo acepta como reacción algo que parezca un emoji."""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RAIZ, "app"))
from interfaces.emoji_reaccion import normalizar_emoji  # noqa: E402


def test_emojis_normales():
    for e in ("👍", "❤️", "👨‍👩‍👧", "🏳️‍🌈", " 😀 ", "👍🏽"):
        assert normalizar_emoji(e) == e.strip()


def test_lo_que_no_es_emoji_se_rechaza():
    for e in ("<img src=x onerror=alert(1)>", "a&b", 'x"y', "x'y", "", "   ", None, 5, "x" * 17, "a\x00b"):
        assert normalizar_emoji(e) is None
