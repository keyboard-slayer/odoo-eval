# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pl')
    def _get_pl_template_data(self):
        return {
            'property_account_receivable_id': 'chart20000100',
            'property_account_payable_id': 'chart21000100',
            'property_account_expense_categ_id': 'chart70010100',
            'property_account_income_categ_id': 'chart73000100',
            'code_digits': '10',
            'use_storno_accounting': True,
        }

    @template('pl', 'res.company')
    def _get_pl_res_company(self):
        return {
            self.env.company.id: {
                'account_fiscal_country_id': 'base.pl',
                'bank_account_code_prefix': '11.000.',
                'transfer_account_code_prefix': '11.090.',
                'cash_account_code_prefix': '12.000.',
                'account_default_pos_receivable_account_id': 'chart20000200',
                'income_currency_exchange_account_id': 'chart75000600',
                'expense_currency_exchange_account_id': 'chart75010400',
                'account_journal_early_pay_discount_loss_account_id': 'chart75010900',
                'account_journal_early_pay_discount_gain_account_id': 'chart75000900',
                'default_cash_difference_income_account_id': 'chart75000700',
                'default_cash_difference_expense_account_id': 'chart75010500',
            },
        }

    def _post_load_data(self, template_code, company, template_data):
        super()._post_load_data(template_code, company, template_data)
        tags = self.env["account.account.tag"].search([("country_id.code", "=", "PL"), ("name", "in", ["bs_assets_b_3_1_c_1", "small_bs_assets_b_3_a_1", "micro_bs_assets_b_1"])])
        # Can't include the compnay.country.code in the search because country is a computed field and can't be searched
        pl_bank_and_cash_accounts = self.env["account.account"].search([("code", "in", ["11.000.001", "11.000.002", "11.000.003", "11.000.004", "11.090.001", "12.000.001"])]).filtered(lambda a: a.company_id.country_id.code == "PL")
        pl_bank_and_cash_accounts.tag_ids = tags
