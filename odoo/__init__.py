# -*- coding: utf-8 -*-
# ruff: noqa: E402, F401
# Part of Odoo. See LICENSE file for full copyright and licensing details.

""" OpenERP core library."""

# ----------------------------------------------------------
# odoo must be a namespace package for odoo.addons to become one too
# https://packaging.python.org/guides/packaging-namespace-packages/
# ----------------------------------------------------------
import pkgutil
import os.path
__path__ = [
    os.path.abspath(path)
    for path in pkgutil.extend_path(__path__, __name__)
]

import sys
from odoo.release import MIN_PY_VERSION
# XXX here for the runbot:
# MIN_PY_VERSION = (3, 10)
assert sys.version_info > MIN_PY_VERSION, f"Outdated python version detected, Odoo requires Python >= {'.'.join(map(str, MIN_PY_VERSION))} to run."

# ----------------------------------------------------------
# Shortcuts
# ----------------------------------------------------------
_GLOBAL_VARIABLES_LOCATION = {
    # XXX future locations of variables
    "SUPERUSER_ID": "odoo.api",
    "Command": "odoo.fields",
    "_": "odoo.tools",
    "_lt": "odoo.tools.translate",
    "MIN_PY_VERSION": "odoo.release",
    "MAX_PY_VERSION": "odoo.release",
}
# store file names from which the warning was raised
# used to stop raising warnings after X times
_GLOBAL_VARIABLE_WARNING = set()


def __getattr__(name: str):
    """Get variables from the odoo module and show warnings"""
    module_name = _GLOBAL_VARIABLES_LOCATION.get(name)
    if not module_name:
        raise AttributeError(f"Module {__name__!r} has not attribute {name!r}.")

    module = __import__(module_name)

    import inspect  # noqa: PLC0415
    import warnings  # noqa: PLC0415

    frame = inspect.currentframe().f_back
    _GLOBAL_VARIABLE_WARNING.add(frame.f_code.co_filename)

    if len(_GLOBAL_VARIABLE_WARNING) < 10:
        # cannot import odoo.tools.lazy here (results in circular dependency)
        warnings.warn(f"You'll find {name!r} at {module.__name__!r}", DeprecationWarning)
    return getattr(module, name)


def registry(database_name=None):
    """
    Return the model registry for the given database, or the database mentioned
    on the current thread. If the registry does not exist yet, it is created on
    the fly.
    """
    import warnings  # noqa: PLC0415
    warnings.warn("Use directly odoo.modules.registry.Registry", DeprecationWarning, 2)
    if database_name is None:
        import threading
        database_name = threading.current_thread().dbname
    return modules.registry.Registry(database_name)


# ----------------------------------------------------------
# Import tools to patch code and libraries
# required to do as early as possible for evented and timezone
# ----------------------------------------------------------
from . import _monkeypatches
_monkeypatches.patch_all()


# ----------------------------------------------------------
# Imports
# ----------------------------------------------------------
from . import upgrade  # this namespace must be imported first
from . import addons
from . import conf
from . import loglevels
from . import modules
from . import netsvc
from . import osv
from . import release
from . import service
from . import sql_db
from . import tools

# ----------------------------------------------------------
# Model classes, fields, api decorators, and translations
# ----------------------------------------------------------
from . import models
from . import fields
from . import api

# ----------------------------------------------------------
# Other imports, which may require stuff from above
# ----------------------------------------------------------
from . import cli
from . import http
