# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class L10nArAfipResponsibilityType(models.Model):

    _name = 'l10n_ar.afip.responsibility.type'
    _description = 'AFIP Responsibility Type'
    _order = 'sequence'

    name = fields.Char(required=True, index='trigram')
    sequence = fields.Integer()
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        'unique(name)',
        lambda env: env._('Name must be unique!'),
    )
    _code_uniq = models.Constraint(
        'unique(code)',
        lambda env: env._('Code must be unique!'),
    )
