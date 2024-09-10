# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class L10nLatamIdentificationType(models.Model):

    _name = "l10n_latam.identification.type"

    _inherit = ["l10n_latam.identification.type"]

    l10n_pe_vat_code = fields.Char()
