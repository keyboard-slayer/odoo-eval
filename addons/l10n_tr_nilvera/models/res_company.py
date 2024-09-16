from odoo import fields, models
from odoo.addons.l10n_tr_nilvera.lib.nilvera_client import NilveraClient


class ResCompany(models.Model):
    _inherit = 'res.company'

    nilvera_api_key = fields.Char(string='Nilvera API KEY', groups='base.group_system')
    nilvera_environment = fields.Selection(
        string="Nilvera Environment",
        selection=[
            ('sandbox', 'Sandbox'),
            ('production', 'Production'),
        ],
        required=True,
        default='sandbox',
    )
    setting_account_nilvera = fields.Boolean(string='Use Nilvera', store=True)

    def _get_nilvera_client(self):
        self.ensure_one()
        client = NilveraClient(
            environment=self.nilvera_environment,
            api_key=self.nilvera_api_key,
        )
        return client
