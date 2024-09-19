# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from werkzeug import urls

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment_nuvei.controllers.main import NuveiController
from odoo.addons.payment_nuvei.tests.common import NuveiCommon


@tagged('post_install', '-at_install')
class TestPaymentTransaction(NuveiCommon):

    def _get_expected_values(self, tx):
        return_url = self._build_url(NuveiController._return_url)
        webhook_url = self._build_url(NuveiController._webhook_url)
        cancel_url = self._build_url(NuveiController._cancel_url)
        cancel_url_params = {
            'tx_ref': self.reference,
            'return_access_tkn': self._generate_test_access_token(self.reference),
        }

        return {
            'merchant_id': self.provider.nuvei_merchant_identifier,
            'merchant_site_id': self.provider.nuvei_site_identifier,
            'total_amount': tx.amount,
            'currency': tx.currency_id.name,
            'invoice_id': tx.reference,
            'merchantLocale': tx.partner_lang,
            'user_token_id': f'{tx.partner_id.id}|{tx.partner_name}',
            'email': tx.partner_id.email_normalized,
            'country': tx.partner_country_id.code,
            'item_name_1': tx.reference,
            'item_amount_1': tx.amount,
            'item_quantity_1': 1,
            'time_stamp': tx.create_date.strftime('%Y-%m-%d.%H:%M:%S'),
            'version': '4.0.0',
            'payment_method_mode': 'filter',
            'payment_method': 'unknown',
            'notify_url': webhook_url,
            'success_url': return_url,
            'error_url': return_url,
            'pending_url': return_url,
            'back_url': f'{cancel_url}?{urls.url_encode(cancel_url_params)}',
        }

    def test_no_item_missing_from_rendering_values(self):
        """ Test that the rendered values are conform to the transaction fields. """

        tx = self._create_transaction(flow='redirect')
        with patch(
            'odoo.addons.payment.utils.generate_access_token', new=self._generate_test_access_token
        ):
            processing_values = tx._get_specific_rendering_values(None)
        expected_values = self._get_expected_values(tx)
        self.assertDictEqual(processing_values['url_params'], expected_values)

    @mute_logger('odoo.addons.payment.models.payment_transaction')
    def test_no_input_missing_from_redirect_form(self):
        """ Test that the no key is not omitted from the rendering values. """
        tx = self._create_transaction(flow='redirect')
        expected_input_keys = [
            'checksum',
            'merchant_id',
            'merchant_site_id',
            'total_amount',
            'currency',
            'invoice_id',
            'merchantLocale',
            'user_token_id',
            'email',
            'country',
            'item_name_1',
            'item_amount_1',
            'item_quantity_1',
            'time_stamp',
            'version',
            'payment_method_mode',
            'payment_method',
            'notify_url',
            'success_url',
            'error_url',
            'pending_url',
            'back_url'
        ]
        with patch(
            'odoo.addons.payment.utils.generate_access_token', new=self._generate_test_access_token
        ):
            processing_values = tx._get_processing_values()

        form_info = self._extract_values_from_html_form(processing_values['redirect_form_html'])
        self.assertEqual(form_info['action'], 'https://ppp-test.safecharge.com/ppp/purchase.do')
        self.assertEqual(form_info['method'], 'post')
        self.assertListEqual(list(form_info['inputs'].keys()), expected_input_keys)

    def test_processing_notification_data_confirms_transaction(self):
        """ Test that the transaction state is set to 'done' when the notification data indicate a
        successful payment. """
        tx = self._create_transaction(flow='redirect')
        tx._process_notification_data(self.notification_data)
        self.assertEqual(tx.state, 'done')
