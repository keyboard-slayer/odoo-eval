# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    def _l10n_ec_setup_location_accounts(self, companies):
        for company in companies:
            parent_location = self.env.ref('stock.stock_location_locations_virtual', raise_if_not_found=False)
            loss_loc = parent_location.child_ids.filtered(lambda l: l.usage == 'inventory' and l.company_id == company and l.scrap_location is False)
            loss_loc_account = self._get_account_from_template(company, self.env.ref('l10n_ec.ec510112', raise_if_not_found=False))
            if loss_loc and loss_loc_account:
                loss_loc.write({
                    'valuation_in_account_id': loss_loc_account.id,
                    'valuation_out_account_id': loss_loc_account.id,
                })
            prod_loc = parent_location.child_ids.filtered(lambda l: l.usage == 'production' and l.company_id == company and l.scrap_location is False)
            prod_loc_account = self._get_account_from_template(company, self.env.ref('l10n_ec.ec110302', raise_if_not_found=False))
            if prod_loc and prod_loc_account:
                prod_loc.write({
                    'valuation_in_account_id': prod_loc_account.id,
                    'valuation_out_account_id': prod_loc_account.id,
                })
