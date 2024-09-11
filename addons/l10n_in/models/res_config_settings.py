# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import str2bool
from odoo.addons.l10n_in.models.iap_account import IAP_SERVICE_NAME


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_l10n_in_reseller = fields.Boolean(implied_group='l10n_in.group_l10n_in_reseller', string="Manage Reseller(E-Commerce)")
    l10n_in_edi_production_env = fields.Boolean(
        string="Indian Production Environment",
        related="company_id.l10n_in_edi_production_env",
        readonly=False
    )
    module_l10n_in_edi = fields.Boolean('Indian Electronic Invoicing')
    module_l10n_in_edi_ewaybill = fields.Boolean('Indian Electronic Waybill')
    module_l10n_in_gstin_status = fields.Boolean('Check GST Number Status')
    module_l10n_in_withholding = fields.Boolean('Indian TDS and TCS')
    module_l10n_in_reports_gstr = fields.Boolean('GSTR India eFiling')
    l10n_in_hsn_code_digit = fields.Selection(related='company_id.l10n_in_hsn_code_digit', readonly=False)
    l10n_in_is_gst_registered = fields.Boolean('Register Under GST', config_parameter='l10n_in.l10n_in_is_gst_registered')
    l10n_in_gstin = fields.Char(related='company_id.vat', readonly=False)
    l10n_in_tax_payer_type = fields.Selection(
        selection=[
            ('normal_taxpayer', 'Normal Taxpayer'),
            ('composition_taxpayer', 'Composition Taxpayer'),
            ('casual_taxable_person', 'Casual Taxable Person'),
            ('input_service_distributor', 'Input Service Distributor (ISD)'),
            ('non_resident_taxable_person', 'Non-Resident Taxable Person'),
            ('online_service_distributor', 'Non-Resident Online Service Distributor'),
            ('embassy_un_body', 'Embassy / UN Body / Other Notified Persons'),
            ('sez_developer_unit', 'Special Economic Zone (SEZ) Developer / Unit'),
            ('tds_tcs', 'Tax Deductor at Source (TDS) / Tax Collector at Source (TCS)'),
        ],
        string='Payer Type',
        config_parameter='l10n_in.l10n_in_tax_payer_type'
    )
    l10n_in_gst_registered_on = fields.Date(related='company_id.l10n_in_gst_registered_on', readonly=False)
    l10n_in_tan = fields.Char(related='company_id.l10n_in_tan', readonly=False)

    def l10n_in_edi_buy_iap(self):
        if not self.l10n_in_edi_production_env or not (self.module_l10n_in_edi or self.module_l10n_in_gstin_status):
            raise ValidationError(_(
                "Please ensure that at least one Indian service and production environment is enabled,"
                " and save the configuration to proceed with purchasing credits."
            ))
        return {
            'type': 'ir.actions.act_url',
            'url': self.env["iap.account"].get_credits_url(service_name=IAP_SERVICE_NAME),
            'target': '_new'
        }

    def set_values(self):
        old_value = str2bool(self.env["ir.config_parameter"].get_param("l10n_in.l10n_in_is_gst_registered"))
        if self.country_code == 'IN' and old_value != self.l10n_in_is_gst_registered:
            self.archive_u_r_taxes()
            self._activate_gst_taxes()
        return super().set_values()

    def archive_u_r_taxes(self):
        tax_ref_ids = [
            'exempt_purchase_u_r', 'nil_rated_purchase_u_r', 'igst_purchase_u_r_0', 'igst_purchase_u_r_1', 'igst_purchase_u_r_2',
            'igst_purchase_u_r_28', 'igst_purchase_u_r_18', 'igst_purchase_u_r_12', 'igst_purchase_u_r_5', 'sgst_purchase_u_r_2_5',
            'cgst_purchase_u_r_2_5', 'sgst_purchase_u_r_5', 'sgst_purchase_u_r_0_5', 'cgst_purchase_u_r_0_5', 'sgst_purchase_u_r_1',
            'sgst_purchase_u_r_1_2', 'cgst_purchase_u_r_1_2', 'sgst_purchase_u_r_2', 'sgst_purchase_u_r_14', 'cgst_purchase_u_r_14',
            'sgst_purchase_u_r_28', 'sgst_purchase_u_r_9', 'cgst_purchase_u_r_9', 'sgst_purchase_u_r_18', 'sgst_purchase_u_r_6',
            'cgst_purchase_u_r_6', 'sgst_purchase_u_r_12', 'igst_purchase_u_r_1_rc', 'igst_purchase_u_r_2_rc', 'igst_purchase_u_r_28_rc',
            'igst_purchase_u_r_18_rc', 'igst_purchase_u_r_12_rc', 'igst_purchase_u_r_5_rc', 'sgst_purchase_u_r_2_5_rc', 'cgst_purchase_u_r_2_5_rc',
            'sgst_purchase_u_r_5_rc', 'sgst_purchase_u_r_0_5_rc', 'cgst_purchase_u_r_0_5_rc', 'sgst_purchase_u_r_1_rc', 'sgst_purchase_u_r_1_2_rc',
            'cgst_purchase_u_r_1_2_rc', 'sgst_purchase_u_r_2_rc', 'sgst_purchase_u_r_14_rc', 'cgst_purchase_u_r_14_rc', 'sgst_purchase_u_r_28_rc',
            'sgst_purchase_u_r_9_rc', 'cgst_purchase_u_r_9_rc', 'sgst_purchase_u_r_18_rc', 'sgst_purchase_u_r_6_rc', 'cgst_purchase_u_r_6_rc',
            'sgst_purchase_u_r_12_rc',
        ]
        tax_ids = [self.env['account.chart.template'].ref(tax_ref).id for tax_ref in tax_ref_ids]
        taxes = self.env['account.tax'].search([('id', 'in', tax_ids)])
        taxes.write({'active': False})

    def _activate_gst_taxes(self):
        tax_ref_ids = [
            'cess_sale_5', 'cess_sale_1591', 'cess_5_plus_1591_sale', 'cess_21_4170_higer_sale',
            'exempt_sale', 'nil_rated_sale', 'non_gst_supplies_sale', 'igst_sale_0', 'igst_sale_1',
            'igst_sale_2', 'igst_sale_28', 'igst_sale_18', 'igst_sale_12', 'igst_sale_5',
            'sgst_sale_0_5', 'cgst_sale_0_5', 'sgst_sale_1', 'sgst_sale_1_2', 'cgst_sale_1_2',
            'sgst_sale_2', 'sgst_sale_14', 'cgst_sale_14', 'sgst_sale_28', 'sgst_sale_9', 'cgst_sale_9',
            'sgst_sale_18', 'sgst_sale_6', 'cgst_sale_6', 'sgst_sale_12', 'sgst_sale_2_5', 'cgst_sale_2_5',
            'sgst_sale_5', 'cess_purchase_5', 'cess_purchase_1591', 'cess_5_plus_1591_purchase', 'cess_21_4170_higer_purchase',
            'exempt_purchase', 'nil_rated_purchase', 'igst_purchase_0', 'igst_purchase_1', 'igst_purchase_2', 'igst_purchase_28',
            'igst_purchase_18', 'igst_purchase_12', 'igst_purchase_5', 'sgst_purchase_0_5', 'cgst_purchase_0_5', 'sgst_purchase_1',
            'sgst_purchase_1_2', 'cgst_purchase_1_2', 'sgst_purchase_2', 'sgst_purchase_14', 'cgst_purchase_14',
            'sgst_purchase_28', 'sgst_purchase_9', 'cgst_purchase_9', 'sgst_purchase_18', 'sgst_purchase_6', 'cgst_purchase_6',
            'sgst_purchase_12', 'sgst_purchase_2_5', 'cgst_purchase_2_5', 'sgst_purchase_5', 'cess_purchase_5_rc', 'cess_purchase_1591_rc',
            'cess_5_plus_1591_purchase_rc', 'cess_21_4170_higer_purchase_rc', 'igst_purchase_1_rc', 'igst_purchase_2_rc', 'igst_purchase_28_rc', 'igst_purchase_18_rc',
            'igst_purchase_12_rc', 'igst_purchase_5_rc', 'sgst_purchase_0_5_rc', 'cgst_purchase_0_5_rc', 'sgst_purchase_1_rc', 'sgst_purchase_1_2_rc',
            'cgst_purchase_1_2_rc', 'sgst_purchase_2_rc', 'sgst_purchase_14_rc', 'cgst_purchase_14_rc', 'sgst_purchase_28_rc', 'sgst_purchase_9_rc',
            'cgst_purchase_9_rc', 'sgst_purchase_18_rc', 'sgst_purchase_6_rc', 'cgst_purchase_6_rc', 'sgst_purchase_12_rc', 'sgst_purchase_2_5_rc', 'cgst_purchase_2_5_rc',
            'sgst_purchase_5_rc', 'igst_sale_1_sez_exp', 'igst_sale_2_sez_exp', 'igst_sale_28_sez_exp', 'igst_sale_18_sez_exp', 'igst_sale_12_sez_exp',
            'igst_sale_5_sez_exp',
        ]
        tax_ids = [self.env['account.chart.template'].ref(tax_ref).id for tax_ref in tax_ref_ids]
        taxes = self.env['account.tax'].search([('id', 'in', tax_ids)])
        taxes.write({'active': True})
