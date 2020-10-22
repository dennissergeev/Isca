# -*- coding: utf-8 -*-
"""Decorators for Isca python interface."""
from functools import wraps


__all__ = ("destructive", "useworkdir")


def destructive(fn):
    """
    Functions decorated with `@destructive` are prevented from running in safe mode."""

    @wraps(fn)
    def _destructive(*args, **kwargs):
        self = args[0]
        if self.safe_mode:
            raise AttributeError(
                "Cannot run destructive function {fn.__name__} in safe mode."
            )
        else:
            return fn(*args, **kwargs)

    return _destructive


def useworkdir(fn):
    """
    Decorator for functions that need to write to a working directory.
    Ensures before the function is run that the workdir exists.
    """

    @wraps(fn)
    def _useworkdir(*args, **kwargs):
        self = args[0]
        self.log.debug("Using directory {self.workdir}")
        # TODO: check object has workdir and log attributes.
        self.workdir.mkdir(parents=True, exist_ok=True)
        return fn(*args, **kwargs)

    return _useworkdir
