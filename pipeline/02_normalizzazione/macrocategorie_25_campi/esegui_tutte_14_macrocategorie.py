#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Opzionale: esporta tutte le QUATTORDICI categorie in una scansione.
ATTENZIONE: i nuovi output a 25 campi sono distinti dai precedenti a 26 campi;
non si sovrascrivono file esistenti senza --overwrite.
"""
from macrocategorie_core_14 import PRIORITY, run

if __name__ == "__main__":
    raise SystemExit(run(PRIORITY))
