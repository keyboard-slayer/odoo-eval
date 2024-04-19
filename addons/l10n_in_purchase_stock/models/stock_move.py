# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _l10n_in_compute_ewaybill_price_unit(self):
        self.ensure_one()
        if self.purchase_line_id:
            return self.purchase_line_id.price_unit
        return super()._l10n_in_compute_ewaybill_price_unit()

    def _l10n_in_compute_tax_ids(self):
        self.ensure_one()
        if self.purchase_line_id:
            return self.purchase_line_id.taxes_id
        return super()._l10n_in_compute_tax_ids()
