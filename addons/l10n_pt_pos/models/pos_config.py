# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import UserError, RedirectWarning


class PosConfig(models.Model):
    _inherit = 'pos.config'

    country_code = fields.Char(related='company_id.country_id.code', depends=['company_id.country_id'])
    l10n_pt_pos_official_series_id = fields.Many2one("l10n_pt_account.official.series", string="Official Series of the Tax Authority")

    def open_ui(self):
        if not self.company_id.country_id:
            raise UserError(_("You have to set a country in your company setting."))
        if self.company_id.country_id.code == 'PT':
            if not self.l10n_pt_pos_official_series_id:
                raise RedirectWarning(
                    _('You have to set an Official Series in the POS configuration settings'),
                    {
                        "view_mode": "form",
                        "res_model": "pos.config",
                        "type": "ir.actions.act_window",
                        "res_id": self.id,
                        "views": [[self.env.ref("l10n_pt_pos.pos_pt_config_view_form").id, "form"]],
                    },
                    _("Go to the POS configuration settings"),
                )
            products_incorrect_taxes = self.env['product.product'].filtered(lambda p: len(p.taxes_id) != 1 or not p.default_code)
            if products_incorrect_taxes:
                raise RedirectWarning(
                    _("All products should have one tax and an internal reference."),
                    {
                        'type': 'ir.actions.act_window',
                        'name': 'Incorrect products',
                        'res_model': 'product.product',
                        'view_mode': 'tree',
                        'views': [[False, 'list'], [False, 'form']],
                        'domain': [('id', 'in', products_incorrect_taxes.ids)],
                    },
                    _("Incorrect products"))
        return super().open_ui()

    def write(self, vals):
        res = super().write(vals)
        for config in self:
            if vals.get('l10n_pt_pos_official_series_id') and config.l10n_pt_pos_official_series_id:
                if self.env['pos.order'].search_count([('config_id', '=', config.id)]):
                    raise UserError(_("You cannot change the official series of a journal once it has been used."))
        return res
