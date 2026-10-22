"""Piezas para correr el backend en varias réplicas (gran escala).

Todo lo de este paquete es neutro en una instalación de una sola máquina: con la
configuración de serie (sin PgBouncer, sin Sentinel, sin réplica de lectura) el
comportamiento es el de siempre. Ver docs/GRAN-ESCALA.md.
"""
