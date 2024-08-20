import uuid

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_sg_get_uuid(self):
        """ The rule is only to provide a uuid. To keep it as simple as possible, we won't store it but instead generate it """
        self.ensure_one()
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        guid = uuid.uuid5(namespace=uuid.UUID(dbuuid), name=str(self.id))
        return str(guid)
