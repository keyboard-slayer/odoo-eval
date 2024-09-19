from odoo import models


class AccountEdiXmlUblTr(models.AbstractModel):
    _name = "account.edi.xml.ubl.tr"
    _inherit = 'account.edi.xml.ubl_21'
    _description = "UBL-TR 1.2"

    def _export_invoice_filename(self, invoice):
        # EXTENDS account_edi_ubl_cii
        return '%s_einvoice.xml' % invoice.name.replace("/", "_")

    def _export_invoice_vals(self, invoice):
        # EXTENDS account.edi.xml.ubl_21
        vals = super()._export_invoice_vals(invoice)
        vals['vals'].update({
            'customization_id': 'TR1.2',
            'profile_id': 'TEMELFATURA' if invoice.partner_id.l10n_tr_nilvera_customer_status == 'einvoice' else 'EARSIVBELGE',
            'copy_indicator': 'false',
            'uuid': invoice.l10n_tr_nilvera_uuid,
            'document_type_code': 'SATIS',  # TODO need to figure out the type as it's not always sale
            'due_date': False,
            'line_count_numeric': len(invoice.line_ids),
            'order_issue_date': invoice.invoice_date,
        })

        return vals

    def _get_partner_party_identification_vals_list(self, partner):
        # EXTENDS account.edi.xml.ubl_21
        vals = super()._get_partner_party_identification_vals_list(partner)
        vals.append({
            'id_attrs': {
                'schemeID': 'VKN' if partner.is_company else 'TCKN',
            },
            'id': partner.vat,
        })
        return vals

    def _get_partner_address_vals(self, partner):
        # EXTENDS account.edi.xml.ubl_21
        vals = super()._get_partner_address_vals(partner)
        vals.update({
            'city_subdivision_name': partner.state_id.name or 'Ankara', # TODO change ankara.
            'country_subentity': False,
            'country_subentity_code': False,
        })
        return vals

    def _get_partner_party_tax_scheme_vals_list(self, partner, role):
        # EXTENDS account.edi.xml.ubl_21
        vals_list = super()._get_partner_party_tax_scheme_vals_list(partner, role)

        for vals in vals_list:
            vals.pop('registration_address_vals', None)

    def _get_partner_party_legal_entity_vals_list(self, partner):
        # EXTENDS account.edi.xml.ubl_21
        vals_list = super()._get_partner_party_legal_entity_vals_list(partner)

        for vals in vals_list:
            vals.pop('registration_address_vals', None)

    def _get_delivery_vals_list(self, invoice):
        # EXTENDS account.edi.xml.ubl_21
        delivery_vals = super()._get_delivery_vals_list(invoice)
        if 'picking_ids' in invoice._fields:
            delivery_vals[0]['delivery_id'] = invoice.picking_ids[0].name
            return delivery_vals

        return []

    def _get_invoice_payment_means_vals_list(self, invoice):
        # EXTENDS account.edi.xml.ubl_21
        vals_list = super()._get_invoice_payment_means_vals_list(invoice)

        for vals in vals_list:
            vals.pop('instruction_id', None)
            vals.pop('payment_id_vals', None)

        return vals_list

    def _get_tax_category_list(self, invoice, taxes):
        # EXTENDS account.edi.common
        vals_list = super()._get_tax_category_list(invoice, taxes)
        for vals in vals_list:
            vals['tax_scheme_vals']['name'] = 'Çankaya'
            vals['tax_scheme_vals']['id'] = False

        return vals_list

    def _get_invoice_tax_totals_vals_list(self, invoice, taxes_vals):
        # EXTENDS account.edi.xml.ubl_21
        tax_totals_vals = super()._get_invoice_tax_totals_vals_list(invoice, taxes_vals)

        for vals in tax_totals_vals:
            for subtotal_vals in vals.get('tax_subtotal_vals', []):
                subtotal_vals.get('tax_category_vals', {})['name'] = "Çankayas"
                subtotal_vals.get('tax_category_vals', {})['id'] = False
                subtotal_vals.get('tax_category_vals', {})['percent'] = False

        return tax_totals_vals

    def _get_invoice_monetary_total_vals(self, invoice, taxes_vals, line_extension_amount, allowance_total_amount, charge_total_amount):
        # EXTENDS account.edi.xml.ubl_20
        vals = super()._get_invoice_monetary_total_vals(invoice, taxes_vals, line_extension_amount, allowance_total_amount, charge_total_amount)
        if invoice.currency_id.is_zero(vals['prepaid_amount']):
            del vals['prepaid_amount']
        return vals

    def _get_invoice_line_item_vals(self, line, taxes_vals):
        # EXTENDS account.edi.xml.ubl_21
        line_item_vals = super()._get_invoice_line_item_vals(line, taxes_vals)

        line_item_vals['classified_tax_category_vals'] = False

        return line_item_vals
