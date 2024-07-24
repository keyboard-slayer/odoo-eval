import requests
import logging

from odoo import _
REQUEST_TIMEOUT = 10

_logger = logging.getLogger(__name__)

class RazorpayPosRequest:
    def __init__(self, payment_method):
        self.razorpay_test_mode = payment_method.pos_payment_provider_id.mode
        self.razorpay_api_key = payment_method.pos_payment_provider_id.razorpay_api_key
        self.razorpay_username = payment_method.pos_payment_provider_id.razorpay_username
        self.terminal_identifier = payment_method.terminal_identifier
        self.razorpay_allowed_payment_modes = payment_method.pos_payment_provider_id.razorpay_allowed_payment_modes
        self.payment_provider = payment_method.pos_payment_provider_id
        self.session = requests.Session()

    def _razorpay_get_endpoint(self):
        if self.payment_provider.mode == 'test':
            return 'https://demo.ezetap.com/api/3.0/p2padapter/'
        return 'https://www.ezetap.com/api/3.0/p2padapter/'

    def _call_razorpay(self, endpoint, payload):
        """ Make a request to Razorpay POS API.

        :param str endpoint: The endpoint to be reached by the request.
        :param dict payload: The payload of the request.
        :return The JSON-formatted content of the response.
        :rtype: dict
        """
        endpoint = f'{self._razorpay_get_endpoint()}{endpoint}'
        request_timeout = self.payment_provider.env['ir.config_parameter'].sudo().get_param('pos_razorpay.timeout', REQUEST_TIMEOUT)
        try:
            response = self.session.post(endpoint, json=payload, timeout=request_timeout)
            response.raise_for_status()
            res_json = response.json()
        except requests.exceptions.RequestException as error:
            _logger.warning('Cannot connect with Razorpay POS. Error: %s', error)
            return {'errorMessage': str(error)}
        except ValueError as error:
            _logger.warning('Cannot decode response json. Error: %s', error)
            return {'errorMessage': _('Cannot decode Razorpay POS response')}
        return res_json

    def _razorpay_get_payment_request_body(self, payment_mode=True):
        request_parameters = {
            'pushTo': {
                'deviceId': f'{self.terminal_identifier}|ezetap_android',
            },
        }
        if payment_mode:
            request_parameters.update({'mode': self.razorpay_allowed_payment_modes.upper()})
        request_parameters.update(self._razorpay_get_payment_status_request_body())
        return request_parameters

    def _razorpay_get_payment_status_request_body(self):
        return {
            'username': self.razorpay_username,
            'appKey': self.razorpay_api_key,
        }
