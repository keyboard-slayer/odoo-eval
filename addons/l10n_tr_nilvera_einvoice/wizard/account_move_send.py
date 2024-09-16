from io import BytesIO
import logging

from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMoveSend(models.TransientModel):
    _inherit = 'account.move.send'

    l10n_tr_nilvera_einvoice_enable_xml = fields.Boolean(compute='_compute_l10n_tr_nilvera_einvoice_enable_xml')
    l10n_tr_nilvera_einvoice_checkbox_xml = fields.Boolean(
        string="Send E-Invoice to Nilvera",
        default=True,
        company_dependent=True,
    )

    def _get_wizard_values(self):
        # EXTENDS 'account'
        values = super()._get_wizard_values()
        values['l10n_tr_nilvera_einvoice_xml'] = self.l10n_tr_nilvera_einvoice_checkbox_xml
        return values

    @api.model
    def _get_wizard_vals_restrict_to(self, only_options):
        # EXTENDS 'account'
        values = super()._get_wizard_vals_restrict_to(only_options)
        return {
            'l10n_tr_nilvera_einvoice_checkbox_xml': False,
            **values,
        }

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('move_ids')
    def _compute_l10n_tr_nilvera_einvoice_enable_xml(self):
        for wizard in self:
            wizard.l10n_tr_nilvera_einvoice_enable_xml = any(move._l10n_tr_nilvera_einvoice_get_default_enable() for move in wizard.move_ids)

    @api.depends('l10n_tr_nilvera_einvoice_enable_xml')
    def _compute_l10n_tr_nilvera_einvoice_checkbox_xml(self):
        for wizard in self:
            wizard.l10n_tr_nilvera_einvoice_checkbox_xml = wizard.l10n_tr_nilvera_einvoice_enable_xml

    @api.depends('l10n_tr_nilvera_einvoice_checkbox_xml')
    def _compute_mail_attachments_widget(self):
        # EXTENDS 'account' - add depends
        super()._compute_mail_attachments_widget()

    # -------------------------------------------------------------------------
    # ATTACHMENTS
    # -------------------------------------------------------------------------

    @api.model
    def _get_invoice_extra_attachments(self, move):
        # EXTENDS 'account'
        return super()._get_invoice_extra_attachments(move) + move.l10n_tr_nilvera_einvoice_xml_id

    # -------------------------------------------------------------------------
    # BUSINESS ACTIONS
    # -------------------------------------------------------------------------

    """
    Here the invoice is created.
    """
    @api.model
    def _hook_invoice_document_before_pdf_report_render(self, invoice, invoice_data):
        # EXTENDS 'account'
        super()._hook_invoice_document_before_pdf_report_render(invoice, invoice_data)

        if invoice_data.get('l10n_tr_nilvera_einvoice_xml') and invoice._l10n_tr_nilvera_einvoice_get_default_enable():
            try:
                builder = self.env['account.edi.xml.ubl.tr']
                xml_content, errors = builder._export_invoice(invoice)
                if errors:
                    invoice_data['error'] = {
                        'error_title': _("Errors occurred while creating the EDI document (format: %s):", "E-Invoice"),
                        'errors': errors,
                    }
                else:
                    invoice_data['l10n_tr_nilvera_einvoice_attachment_values'] = {
                        'name': invoice._l10n_tr_nilvera_einvoice_get_filename(),
                        'raw': xml_content,
                        'mimetype': 'application/xml',
                        'res_model': invoice._name,
                        'res_id': invoice.id,
                        'res_field': 'l10n_tr_nilvera_einvoice_xml_file',  # Binary field
                    }
            except UserError as e:
                if self.env.context.get('forced_invoice'):
                    _logger.warning(
                        'An error occured during generation of E-Invoice EDI of %s: %s',
                        invoice.name,
                        e.args[0]
                    )
                else:
                    raise

    """
    Here we try to send that invoice.
    """
    @api.model
    def _call_web_service_before_invoice_pdf_render(self, invoices_data):
        # EXTENDS 'account'
        super()._call_web_service_before_invoice_pdf_render(invoices_data)

        for invoice, invoice_data in invoices_data.items():
            # 0- make sure we actually created an xml for that invoice
            attachment_values = invoice_data.get('l10n_tr_nilvera_einvoice_attachment_values')
            if not attachment_values:
                # TODO handle this
                return
            xml_file = BytesIO(attachment_values.get('raw'))
            xml_file.name = attachment_values.get('name')

            if not invoice.partner_id.l10n_tr_nilvera_customer_alias:
                # If no alias is saved, the user is either an E-Archive user or we haven't checked before. Check again
                # just in case.
                invoice.partner_id.check_nilvera_customer()

            customer_alias = invoice.partner_id.l10n_tr_nilvera_customer_alias
            if customer_alias:  # E-Invoice
                invoice._l10n_tr_nilvera_submit_einvoice(xml_file, customer_alias)
            else:   # E-Archive
                invoice._l10n_tr_nilvera_submit_earchive(xml_file)

            # 4- we need to have a variable on the move with the state, and we need to update it here

            # bada-bing bada-boom

    """
    Here the invoice is linked to the move
    """
    @api.model
    def _link_invoice_documents(self, invoice, invoice_data):
        # EXTENDS 'account'
        super()._link_invoice_documents(invoice, invoice_data)

        attachment_vals = invoice_data.get('l10n_tr_nilvera_einvoice_attachment_values')
        if attachment_vals:
            self.env['ir.attachment'].with_user(SUPERUSER_ID).create(attachment_vals)
            invoice.invalidate_recordset(fnames=['l10n_tr_nilvera_einvoice_xml_id', 'l10n_tr_nilvera_einvoice_xml_file'])
