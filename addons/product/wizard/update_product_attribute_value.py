# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, Command


class UpdateProductAttributeValue(models.TransientModel):
    _name = 'update.product.attribute.value'
    _description = "Update product attribute value"

    attribute_value_id = fields.Many2one('product.attribute.value', required=True)
    is_new_attribute_value = fields.Boolean()
    message = fields.Char(compute='_compute_message')
    product_count = fields.Integer(compute='_compute_product_count')

    @api.depends('product_count', 'is_new_attribute_value', 'attribute_value_id')
    def _compute_message(self):
        for wizard in self:
            if wizard.is_new_attribute_value:
                wizard.message = _(
                    'You are about to add "%(attribute_value)s" to %(product_count)s products.',
                    attribute_value=wizard.attribute_value_id.name,
                    product_count=wizard.product_count,
                )
            else:
                wizard.message = _(
                    "You are about to update the extra price of %s products.",
                    wizard.product_count,
                )

    @api.depends('is_new_attribute_value')
    def _compute_product_count(self):
        ProductTemplate = self.env['product.template']
        for wizard in self:
            if wizard.is_new_attribute_value:
                wizard.product_count = ProductTemplate.search_count([
                    ('attribute_line_ids.attribute_id', '=', wizard.attribute_value_id.attribute_id.id),
                ])
            else:
                wizard.product_count = ProductTemplate.search_count([
                    ('attribute_line_ids.value_ids', '=', wizard.attribute_value_id.id),
                ])

    def action_confirm(self):
        self.ensure_one()
        if self.is_new_attribute_value:
            ptals = self.attribute_value_id.attribute_id.attribute_line_ids
            ptals.write({'value_ids': [Command.link(self.attribute_value_id.id)]})
        else:
            ptavs = self.env['product.template.attribute.value'].search([
                ('product_attribute_value_id', '=', self.attribute_value_id.id),
            ])
            ptavs.write({'price_extra': self.attribute_value_id.default_extra_price})
