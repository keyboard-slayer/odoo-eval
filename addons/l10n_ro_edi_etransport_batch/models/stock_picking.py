from odoo import api, models


class Picking(models.Model):
    _inherit = 'stock.picking'

    @api.depends('batch_id', 'l10n_ro_edi_etransport_message')
    def _compute_l10n_ro_edi_etransport_should_show_send_info(self):
        # Extends l10n_ro_edi_etransport
        for picking in self:
            picking.l10n_ro_edi_etransport_should_show_send_info = not picking.batch_id and picking.l10n_ro_edi_etransport_message

    @api.depends('batch_id', 'company_id')
    def _compute_l10n_ro_edi_etransport_should_show(self):
        # Extends l10n_ro_edi_etransport
        for picking in self:
            picking.l10n_ro_edi_etransport_should_show = not picking.batch_id and picking.company_id.country_id.code == 'RO'
