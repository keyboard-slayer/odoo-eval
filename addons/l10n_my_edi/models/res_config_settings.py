# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ------------------
    # Fields declaration
    # ------------------

    l10n_my_edi_mode = fields.Selection(related="company_id.l10n_my_edi_mode", readonly=False)
    l10n_my_edi_default_import_journal_id = fields.Many2one(related="company_id.l10n_my_edi_default_import_journal_id", readonly=False)
    l10n_my_edi_proxy_user_id = fields.Many2one(related="company_id.l10n_my_edi_proxy_user_id")
    l10n_my_edi_company_vat = fields.Char(related="company_id.vat")

    # ----------------
    # Onchange methods
    # ----------------

    @api.onchange('l10n_my_edi_mode')
    def _onchange_l10n_my_edi_mode(self):
        """ This onchange is mostly here to improve usability by avoiding the need to save when changing the mode. """
        self.l10n_my_edi_proxy_user_id = self.company_id.account_edi_proxy_client_ids.filtered(
            lambda u: u.proxy_type == 'l10n_my_edi' and u.edi_mode == self.l10n_my_edi_mode
        )

    # --------------
    # Action methods
    # --------------

    def action_l10n_my_edi_allow_processing(self):
        """ We always expect the user to give his consent by pressing the button, in any mode, to enable the edi. """
        self.company_id._l10n_my_edi_create_proxy_user()

    def action_open_company_form(self):
        """ This will be used to ease the configuration by allowing to quickly access the company. """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_id': self.env.company.id,
            'res_model': 'res.company',
            'target': 'new',
            'view_mode': 'form',
        }
