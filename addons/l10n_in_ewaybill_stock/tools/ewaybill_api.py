# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, _
from datetime import timedelta
from odoo.addons.iap import jsonrpc
from odoo.exceptions import AccessError
from odoo.addons.l10n_in_edi.models.account_edi_format import DEFAULT_IAP_ENDPOINT, DEFAULT_IAP_TEST_ENDPOINT


_logger = logging.getLogger(__name__)


class EWayBillApi:

    def __init__(self, company):
        company.ensure_one()
        self.company = company
        self.env = self.company.env

    def _ewaybill_connect_to_server(self, url_path, params):
        user_token = self.env["iap.account"].get("l10n_in_edi")
        params.update({
            "account_token": user_token.account_token,
            "dbuuid": self.env["ir.config_parameter"].sudo().get_param("database.uuid"),
            "username": self.company.sudo().l10n_in_edi_ewaybill_username,
            "gstin": self.company.vat,
        })
        if self.company.sudo().l10n_in_edi_production_env:
            default_endpoint = DEFAULT_IAP_ENDPOINT
        else:
            default_endpoint = DEFAULT_IAP_TEST_ENDPOINT
        endpoint = self.env["ir.config_parameter"].sudo().get_param("l10n_in_edi_ewaybill.endpoint", default_endpoint)
        url = "%s%s" % (endpoint, url_path)
        try:
            return jsonrpc(url, params=params, timeout=70)
        except AccessError as e:
            _logger.warning("Connection error: %s", e.args[0])
            return {
                "error": [{
                    "code": "access_error",
                    "message": _("Unable to connect to the E-WayBill service."
                                 "The web service may be temporary down. Please try again in a moment.")
                }]
            }

    def _ewaybill_check_authentication(self):
        sudo_company = self.company.sudo()
        if sudo_company.l10n_in_edi_ewaybill_username and sudo_company._l10n_in_edi_ewaybill_token_is_valid():
            return True
        elif sudo_company.l10n_in_edi_ewaybill_username and sudo_company.l10n_in_edi_ewaybill_password:
            authenticate_response = self._ewaybill_authenticate()
            if not authenticate_response.get("error"):
                return True
        return False

    def _ewaybill_authenticate(self):
        params = {"password": self.company.sudo().l10n_in_edi_ewaybill_password}
        response = self._ewaybill_connect_to_server(url_path="/iap/l10n_in_edi_ewaybill/1/authenticate", params=params)
        if response and response.get("status_cd") == "1":
            self.company.sudo().l10n_in_edi_ewaybill_auth_validity = fields.Datetime.now() + timedelta(
                hours=6, minutes=00, seconds=00)
        return response

    def _ewaybill_generate(self, json_payload):
        is_authenticated = self._ewaybill_check_authentication()
        if not is_authenticated:
            return self._ewaybill_no_config_response()
        params = {"json_payload": json_payload}
        return self._ewaybill_connect_to_server(url_path="/iap/l10n_in_edi_ewaybill/1/generate", params=params)

    def _ewaybill_cancel(self, json_payload):
        is_authenticated = self._ewaybill_check_authentication()
        if not is_authenticated:
            return self._ewaybill_no_config_response()
        params = {"json_payload": json_payload}
        return self._ewaybill_connect_to_server(url_path="/iap/l10n_in_edi_ewaybill/1/cancel", params=params)

    def _ewaybill_get_by_consigner(self, document_type, document_number):
        is_authenticated = self._ewaybill_check_authentication()
        if not is_authenticated:
            return self._ewaybill_no_config_response()
        params = {"document_type": document_type, "document_number": document_number}
        return self._ewaybill_connect_to_server(url_path="/iap/l10n_in_edi_ewaybill/1/getewaybillgeneratedbyconsigner", params=params)

    def _ewaybill_no_config_response(self):
        return {"error": [{
            "code": "0",
            "message": _(
                "Unable to send E-waybill."
                "Create an API user in NIC portal, and set it using the top menu: Configuration > Settings."
            )}
        ]}
