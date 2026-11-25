#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Esegue le NOVE nuove categorie con una sola lettura del CSV.
Le 5 categorie precedenti restano al primo posto nella precedenza, ma
non vengono riesportate; i loro file gia' esistenti non sono modificati.
"""
from macrocategorie_core_14 import NEW_PRIORITY, run

if __name__ == "__main__":
    raise SystemExit(run(NEW_PRIORITY))
