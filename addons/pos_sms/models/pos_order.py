from odoo import models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_sent_message_on_sms(self, phone, _):
        if not (self and self.config_id.module_pos_sms and self.config_id.sms_receipt_template_id and phone):
            return
        self.ensure_one()

        sms_logs = self.env['sms.composer'].search([
            ('res_id', '=', self.id),
            ('res_model', '=', 'pos.order'),
            ('numbers', '=', phone),
            ('template_id', '=', self.config_id.sms_receipt_template_id.id),
        ])

        if sms_logs:
            raise UserError(_('A receipt has already been sent to this number: %s', phone))

        sms_composer = self.env['sms.composer'].with_context(active_id=self.id).create(
            {
                'composition_mode': 'comment',
                'numbers': phone,
                'recipient_single_number_itf': phone,
                'template_id': self.config_id.sms_receipt_template_id.id,
                'res_model': 'pos.order'
            }
        )
        self.mobile = phone
        sms_composer.action_send_sms()
