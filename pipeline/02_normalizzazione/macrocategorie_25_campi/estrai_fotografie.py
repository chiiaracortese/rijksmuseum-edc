#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estrae la macrocategoria Fotografie e materiali fotografici in JSON con 25 campi.
Legge ~/Desktop/rijksmuseum_completo.csv e scrive in
~/Desktop/macrocategorie json/. Non sovrascrive il file originale.
Richiede macrocategorie_core_14.py e mappatura_macrocategorie_14.json nella stessa cartella.
"""
from macrocategorie_core_14 import run

if __name__ == "__main__":
    raise SystemExit(run(("fotografie",)))
