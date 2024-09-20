# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductCustomsCode(models.Model):
    _name = "product.customs_code"
    _description = "Codes used by customs authorities."

    _order = 'code, id'

    active = fields.Boolean(default=True)
    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    code_type = fields.Selection([])
    description = fields.Char(string='Description')
    product_ids = fields.Many2many('product.product', 'product_customs_code_rel', 'customs_code_id', 'product_id')


    start_date = fields.Date(
        string='Usage start date',
        help='Date from which a code may be used.',
    )
    expiry_date = fields.Date(
        string='Expiry Date',
        help='Date at which a code must not be used anymore.',
    )
