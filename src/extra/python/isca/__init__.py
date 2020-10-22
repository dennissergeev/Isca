# -*- coding: utf-8 -*-
"""Python interface to Isca."""
import os
from collections import defaultdict

from .codebase import DryCodeBase, GreyCodeBase, IscaCodeBase, SocratesCodeBase
from .diagtable import DiagTable
from .exceptions import InpOutError
from .experiment import Experiment
from .loghandler import log
from .paths import GFDL_BASE, GFDL_DATA, GFDL_SOC, GFDL_WORK

__all__ = (
    "DryCodeBase",
    "GreyCodeBase",
    "IscaCodeBase",
    "SocratesCodeBase",
    "DiagTable",
    "Experiment",
    "GFDL_BASE",
    "GFDL_DATA",
    "GFDL_SOC",
    "GFDL_WORK",
)


# GFDL_ENV: The environment on which the model is being run.
# Primarily, this determines which compilers and libraries are to be used
# to compile the code.
# A file with matching name in GFDL_BASE/src/extra/env is sourced before
# compilation or the model is run.  For example, if the user has `export GFDL_ENV=emps-gv`
# then before compilation or running the code, GFDL_BASE/src/extra/env/emps-gv
# is sourced to ensure that the same libraries will be used to run the code
# as those against which it was compiled.  To get the python scripts working
# on a new computer with different compilers, a new environment script will
# need to be developed and placed in this directory.
try:
    GFDL_ENV = os.environ["GFDL_ENV"]
except KeyError:
    # if the user doesn't have the environment variable set, use the computer's
    # fully qualified domain name as GFDL_ENV
    import socket  # noqa

    GFDL_ENV = socket.getfqdn()
    log.warning(f"Environment variable GFDL_ENV not set, using {GFDL_ENV}")


def get_env_file(env=GFDL_ENV):
    filepath = GFDL_BASE / "src" / "extra" / "env" / env
    if filepath.isfile():
        return filepath
    else:
        msg = f"Environment file {filepath} not found"
        log.error(msg)
        raise InpOutError(msg)


class EventEmitter(object):
    """
    A very simple event driven object to make it easier
    to tie custom functionality into the model.
    """

    def __init__(self):
        self._events = defaultdict(list)

    def on(self, event, fn=None):
        """
        Assign function `fn` to be called when `event` is triggered.

        Can be used in two ways:
        1. As a normal function:
        >>> exp.on('start', fn)

        2. As a decorator:
        >>> @exp.on('start')
            def fn(*args):
                pass

        """

        def _on(fn):
            self._events[event].append(fn)
            return fn

        if fn is None:
            return _on  # used as a decorator
        else:
            return _on(fn)  # used as a normal function

    def emit(self, event, *args, **kwargs):
        """Trigger an event."""
        handled = False
        for callback in self._events[event]:
            callback(*args, **kwargs)
            handled = True
        return handled
