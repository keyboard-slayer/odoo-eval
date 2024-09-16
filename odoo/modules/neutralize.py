# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from contextlib import suppress

from odoo.tools import file_open

_logger = logging.getLogger(__name__)

def get_installed_modules(cursor):
    cursor.execute('''
        SELECT name
          FROM ir_module_module
         WHERE state IN ('installed', 'to upgrade', 'to remove');
    ''')
    return [result[0] for result in cursor.fetchall()]

def get_neutralization_queries(modules):
    # neutralization for each module
    for module in modules:
        filename = f'{module}/data/neutralize.sql'
        with suppress(FileNotFoundError):
            with file_open(filename) as file:
                yield file.read().strip()

def neutralize_database(cursor):
    installed_modules = get_installed_modules(cursor)
    queries = get_neutralization_queries(installed_modules)
    for query in queries:
        cursor.execute(query)
    _logger.info("Neutralization finished")
