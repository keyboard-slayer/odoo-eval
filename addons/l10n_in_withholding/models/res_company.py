from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_in_withholding_account_id = fields.Many2one(
        comodel_name='account.account',
        string="TDS Account",
        check_company=True
    )
    l10n_in_withholding_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="TDS Journal",
        check_company=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Update Withholding Journal for new branch
        for company in res.filtered(lambda c: c.parent_id.l10n_in_withholding_journal_id):
            company.l10n_in_withholding_journal_id = company.parent_id.l10n_in_withholding_journal_id
        return res
