#!/bin/bash
# Launcher para el Laboratorio de Experimentos en Linux
cd "$(dirname "$0")"
export PYTHONPATH=$PYTHONPATH:$(pwd)/..
../venv/bin/python3 lab_main.py
