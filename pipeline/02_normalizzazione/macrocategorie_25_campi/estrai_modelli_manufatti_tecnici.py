#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estrai Modelli e manufatti tecnici dal CSV del Rijksmuseum in JSON con 25 campi.

Input predefinito: ~/Desktop/rijksmuseum_completo.csv
Output predefinito: ~/Desktop/macrocategorie json/
Questo script richiede macrocategorie_core_14.py e
mappatura_macrocategorie_14.json nella stessa cartella.
"""
from macrocategorie_core_14 import run

if __name__ == "__main__":
    raise SystemExit(run(("modelli_manufatti_tecnici",)))
