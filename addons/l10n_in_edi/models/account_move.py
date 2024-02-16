# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_in_edi_cancel_reason = fields.Selection(selection=[
        ("1", "Duplicate"),
        ("2", "Data Entry Mistake"),
        ("3", "Order Cancelled"),
        ("4", "Others"),
        ], string="Cancel reason", copy=False)
    l10n_in_edi_cancel_remarks = fields.Char("Cancel remarks", copy=False)
    l10n_in_edi_show_cancel = fields.Boolean(compute="_compute_l10n_in_edi_show_cancel", string="E-invoice(IN) is sent?")
    show_alert = fields.Boolean(string="Show Alert", compute="_compute_show_alert")

    @api.depends('edi_document_ids')
    def _compute_l10n_in_edi_show_cancel(self):
        for invoice in self:
            invoice.l10n_in_edi_show_cancel = bool(invoice.edi_document_ids.filtered(
                lambda i: i.edi_format_id.code == "in_einvoice_1_03"
                and i.state in ("sent", "to_cancel", "cancelled")
            ))

    def button_cancel_posted_moves(self):
        """Mark the edi.document related to this move to be canceled."""
        reason_and_remarks_not_set = self.env["account.move"]
        for move in self:
            send_l10n_in_edi = move.edi_document_ids.filtered(lambda doc: doc.edi_format_id.code == "in_einvoice_1_03")
            # check submitted E-invoice does not have reason and remarks
            # because it's needed to cancel E-invoice
            if send_l10n_in_edi and (not move.l10n_in_edi_cancel_reason or not move.l10n_in_edi_cancel_remarks):
                reason_and_remarks_not_set += move
        if reason_and_remarks_not_set:
            raise UserError(_(
                "To cancel E-invoice set cancel reason and remarks at Other info tab in invoices: \n%s",
                ("\n".join(reason_and_remarks_not_set.mapped("name"))),
            ))
        return super().button_cancel_posted_moves()

    def _get_l10n_in_edi_response_json(self):
        self.ensure_one()
        l10n_in_edi = self.edi_document_ids.filtered(lambda i: i.edi_format_id.code == "in_einvoice_1_03"
            and i.state in ("sent", "to_cancel"))
        if l10n_in_edi:
            return json.loads(l10n_in_edi.sudo().attachment_id.raw.decode("utf-8"))
        else:
            return {}

    @api.model
    def _l10n_in_edi_is_managing_invoice_negative_lines_allowed(self):
        """ Negative lines are not allowed by the Indian government making some features unavailable like sale_coupon
        or global discounts. This method allows odoo to distribute the negative discount lines to each others lines
        with same HSN code making such features available even for Indian people.
        :return: True if odoo needs to distribute the negative discount lines, False otherwise.
        """
        param_name = 'l10n_in_edi.manage_invoice_negative_lines'
        return bool(self.env['ir.config_parameter'].sudo().get_param(param_name))

    @api.depends('move_type')
    def _compute_show_alert(self):
        breakpoint()
        tax_tags = (
            self.env.ref("l10n_in.tax_tag_tds")+
            self.env.ref("l10n_in.tax_tag_tcs")
        )
        for record in self:
            record.show_alert = (
                record.partner_id.l10n_in_pan and record.move_type == 'in_invoice' and record.amount_residual > 0
                and any(line.tax_tag_ids in tax_tags.ids for line in record.line_ids)
            )
        # for record in self:line
        #     if record.move_type == 'in_invoice' and record.amount_residual > 0:
        #         for line in record.line_ids:
        #             breakpoint()
        #     # record.show_alert = (
        #     #     record.move_type == 'in_invoice' and record.amount_residual > 0
        #     #     and any(line.tax_tag_ids in tax_tags.ids for line in record.line_ids)
        #     # )
        #     record.show_alert = True

























    # def action_post(self):
    #     # super().action_post();
    #     if self.move_type == 'in_invoice' and self.state == 'draft':
    #         if self.line_ids.filtered(lambda line : line.tax_ids.tax_group_id.name in ['TCS','TDS']):
        
    # def high_rate_warning(self):
    #     return {'warning': {
    #         'title': _("warning"),
    #         'message': "warning message"
    #     }}
            
