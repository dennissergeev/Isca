# -*- coding: utf-8 -*-
"""Exceptions specific to Isca package."""


class IscaWarning(UserWarning):
    """Base class for warnings in aeolus package."""

    pass


class DeprecatedWarning(IscaWarning):
    """Warning for a deprecated feature."""

    pass


class IscaError(Exception):
    """Base class for errors in aeolus package."""

    pass


class NotYetImplementedError(IscaError):
    """
    Raised by missing functionality.

    Different meaning to NotImplementedError, which is for abstract methods.
    """

    pass


class ArgumentError(IscaError):
    """Raised when argument type is not recognised or is not allowed."""

    pass


class EnvError(IscaError):
    """Raised when environment is not setup correctly."""

    pass


class InpOutError(IscaError):
    """IO error."""

    pass


class CompilationError(IscaError):
    """Raised when there is a problem with compiling Isca code."""

    pass


class FailedRunError(IscaError):
    """Raised when Isca experiment fails."""

    pass
