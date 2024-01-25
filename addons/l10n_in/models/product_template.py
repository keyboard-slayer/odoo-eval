# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests
from werkzeug.urls import url_encode

from requests.exceptions import HTTPError
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

l10n_in_hsn_service_url = 'https://services.gst.gov.in/commonservices/hsn/search/qsearch'

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_in_hsn_code = fields.Char(string="HSN/SAC Code", help="Harmonized System Nomenclature/Services Accounting Code")

    @api.constrains('l10n_in_hsn_code')
    def _check_hsn_code_validation(self):
        for record in self:
            company = record.company_id or self.env.company
            minimum_hsn_len = company.l10n_in_hsn_code_digit
            check_hsn = record.l10n_in_hsn_code and minimum_hsn_len
            if check_hsn and len(record.l10n_in_hsn_code) < int(minimum_hsn_len):
                error_message = _("As per your HSN/SAC code validation, minimum %s digits HSN/SAC code is required.", minimum_hsn_len)
                raise ValidationError(error_message)

    @api.model
    def get_hsn_suggestions(self, value):
        response_json = {}
        all_url_and_params = [
            (l10n_in_hsn_service_url, {'inputText': value, 'selectedType': 'byCode', 'category': 'null'}),
            (l10n_in_hsn_service_url, {'inputText': value, 'selectedType': 'byDesc', 'category': 'P'}),
            (l10n_in_hsn_service_url, {'inputText': value, 'selectedType': 'byDesc', 'category': 'S'}),
        ]
        for url, params in all_url_and_params:
            try:
                response = requests.get(url, params=url_encode(params))
                response.raise_for_status()
                response_json = response.json()
                if response_json.get('data'):
                    hsn_code_digit = self.env.company.l10n_in_hsn_code_digit
                    if hsn_code_digit:
                        response_json['data'] = list(filter(lambda d: len(d.get('c')) >= int(hsn_code_digit), response_json.get('data')))
                    break
            except (ConnectionError, HTTPError, ValueError) as e:
                _logger.warning('HSN Autocomplete API error: %s', str(e))
        return response_json.get('data', [])
