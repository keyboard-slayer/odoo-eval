# Part of Odoo. See LICENSE file for full copyright and licensing details.

from random import randint
from odoo import models
from odoo.tools.duplicate import get_random_sql_string
from odoo.tools.sql import SQL

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _duplicate_field_need_variation(self, field, **kwargs):
        if field.name == 'name':
            return True
        return super()._duplicate_field_need_variation(field)

    def _duplicate_variate_field(self, field, **kwargs):
        if field.name == 'name':
            first_name = get_random_sql_string(randint(4, 10))
            last_name = get_random_sql_string(randint(5, 11))
            return SQL('''%s || ' ' ||  %s''', first_name, last_name)
        return super()._duplicate_variate_field(field)
