import uuid

from odoo import models, fields


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move']

    def _default_l10n_tr_nilvera_uuid(self):
        return str(uuid.uuid4())

    l10n_tr_nilvera_einvoice_xml_id = fields.Many2one(
        comodel_name='ir.attachment',
        string="Facturae Attachment",
        compute=lambda self: self._compute_linked_attachment_id('l10n_tr_nilvera_einvoice_xml_id',
                                                                'l10n_tr_nilvera_einvoice_xml_file'),
        depends=['l10n_tr_nilvera_einvoice_xml_file']
    )
    l10n_tr_nilvera_einvoice_xml_file = fields.Binary(
        attachment=True,
        string="Facturae File",
        copy=False,
    )
    l10n_tr_nilvera_uuid = fields.Char(
        string='Document UUID (TR)',
        copy=False,
        readonly=True,
        default=_default_l10n_tr_nilvera_uuid,
        help="Universally unique identifier of the Invoice",
    )

    def _l10n_tr_nilvera_submit_einvoice(self, xml_file, customer_alias):
        client = self.env.company._get_nilvera_client()
        query_result = client.request(
            "POST",
            "/einvoice/Send/Xml",
            params={'Alias': customer_alias},
            files={'file': (xml_file.name, xml_file, 'application/xml')},
            handle_response=False,
        )

        print(query_result)

    def _l10n_tr_nilvera_submit_earchive(self, xml_file):
        client = self.env.company._get_nilvera_client()
        query_result = client.request(
            "POST",
            "/earchive/Send/Xml",
            files={'file': (xml_file.name, xml_file, 'application/xml')},
            handle_response=False,
        )

        print(query_result)

    def _l10n_tr_nilvera_einvoice_get_default_enable(self):
        self.ensure_one()
        return not self.invoice_pdf_report_id \
            and not self.l10n_tr_nilvera_einvoice_xml_id \
            and self.is_invoice(include_receipts=True) \
            and self.company_id.country_code == 'TR' \
            # and self.company_id.currency_id.name == 'EUR'

    def _l10n_tr_nilvera_einvoice_get_filename(self):
        self.ensure_one()
        return '%s_einvoice.xml' % self.name.replace("/", "_")
