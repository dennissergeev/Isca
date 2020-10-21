# -*- coding: utf-8 -*-
"""Paths to package files and directories."""
import os
from pathlib import Path

from .loghandler import log
from .exceptions import EnvError


# Isca python module directory
MODULE_DIR = Path(__file__).absolute().parent
# Directory with templates and defaults
AUX_DIR = MODULE_DIR / "aux"
# Template for DiagTable
TEMPLATE_DIAGTABLE = AUX_DIR / "aux" / "template_diagtable.rc"

try:
    GFDL_BASE = Path(os.environ["GFDL_BASE"])
    GFDL_WORK = Path(os.environ["GFDL_WORK"])
    GFDL_DATA = Path(os.environ["GFDL_DATA"])
except KeyError:
    msg = "Environment variables GFDL_BASE, GFDL_WORK, GFDL_DATA must be set"
    log.error(msg)
    raise EnvError(msg)

try:
    GFDL_SOC = os.environ["GFDL_SOC"]
except KeyError:
    # if the user doesn't have the SOC variable set, then use None
    GFDL_SOC = None
    msg = (
        "Environment variable GFDL_SOC not set, but this is only required"
        " if using `SocratesCodebase`. Setting to {}".format(GFDL_SOC)
    )
    log.warning(msg)
