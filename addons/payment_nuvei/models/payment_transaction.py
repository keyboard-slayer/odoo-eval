# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from werkzeug import urls

from odoo import _, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_nuvei import const
from odoo.addons.payment_nuvei.controllers.main import NuveiController


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        """ Override of `payment` to return Nuvei-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic processing values of the transaction.
        :return: The dict of provider-specific processing values.
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'nuvei':
            return res

        base_url = self.provider_id.get_base_url()
        return_url = urls.url_join(base_url, NuveiController._return_url)

        cancel_url = urls.url_join(base_url, NuveiController._cancel_url)
        cancel_url_params = {
            'tx_ref': self.reference,
            'return_access_tkn': payment_utils.generate_access_token(self.reference),
        }

        # Nuvei uses unique user references to keep track of saved payment methods.
        unique_user_ref = f'{self.partner_id.id}|{self.partner_name}'

        # Nuvei expects time sent in UTC/GMT
        timestamp = self.create_date.strftime('%Y-%m-%d.%H:%M:%S')

        url_params = {
            'merchant_id': self.provider_id.nuvei_merchant_identifier,
            'merchant_site_id': self.provider_id.nuvei_site_identifier,
            'total_amount': self.amount,
            'currency': self.currency_id.name,
            'invoice_id': self.reference,
            'merchantLocale': self.partner_lang,
            'user_token_id': unique_user_ref,
            'email': self.partner_id.email_normalized,
            'country': self.partner_country_id.code,
            'item_name_1': self.reference,
            'item_amount_1': self.amount,
            'item_quantity_1': 1,
            'time_stamp': timestamp,
            'version': '4.0.0',
            # 'payment_method_mode': 'filter',
            'payment_method': const.PAYMENT_METHODS_MAPPING.get(self.payment_method_code, self.payment_method_code),
            'notify_url': urls.url_join(base_url, NuveiController._webhook_url),
            'success_url': return_url,
            'error_url': return_url,
            'pending_url': return_url,
            'back_url': f'{cancel_url}?{urls.url_encode(cancel_url_params)}',
        }
        checksum = self.provider_id._nuvei_calculate_signature(url_params, incoming=False)
        rendering_values = {
            'api_url': self.provider_id._nuvei_get_api_url(),
            'checksum': checksum,
            'url_params': url_params,
        }
        return rendering_values

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of `payment` to find the transaction based on Nuvei data.

        :param str provider_code: The code of the provider that handled the transaction.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction if found.
        :rtype: recordset of `payment.transaction`
        :raise ValidationError: If inconsistent data are received.
        :raise ValidationError: If the data match no transaction.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'nuvei' or len(tx) == 1:
            return tx
        reference = notification_data.get('invoice_id')
        if not reference:
            raise ValidationError(
                "Nuvei: " + _("Received data with missing reference %(ref)s.", ref=reference)
            )

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'nuvei')])
        if not tx:
            raise ValidationError(
                "Nuvei: " + _("No transaction found matching reference %s.", reference)
            )

        return tx

    def _process_notification_data(self, notification_data):
        """ Override of `payment' to process the transaction based on Nuvei data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        :raise ValidationError: If inconsistent data are received.
        """
        super()._process_notification_data(notification_data)

        if self.provider_code != 'nuvei':
            return

        if not notification_data:
            self._set_canceled(state_message=_("The customer left the payment page."))
            return

        # Update the provider reference.
        self.provider_reference = notification_data.get('TransactionID')

        # Update the payment method.
        payment_option = notification_data.get('payment_method', '')
        payment_method = self.env['payment.method']._get_from_code(
            payment_option.lower(), mapping=const.PAYMENT_METHODS_MAPPING
        )
        self.payment_method_id = payment_method or self.payment_method_id

        # Update the payment state.
        status = notification_data.get('Status')
        if not status:
            raise ValidationError("Nuvei: " + _("Received data with missing payment state."))
        status = status.lower()
        if status in const.PAYMENT_STATUS_MAPPING['pending']:
            self._set_pending()
        elif status in const.PAYMENT_STATUS_MAPPING['done']:
            self._set_done()
        elif status in const.PAYMENT_STATUS_MAPPING['error']:
            failure_reason = notification_data.get('Reason')
            self._set_error(_(
                "An error occurred during the processing of your payment (%s). Please try again.",
                failure_reason,
            ))
        else:  # Classify unsupported payment state as `error` tx state.
            status_description = notification_data.get('Reason')
            _logger.info(
                "Received data with invalid payment status (%(status)s) and reason '%(reason)s' "
                "for transaction with reference %(ref)s",
                {'status': status, 'reason': status_description, 'ref': self.reference},
            )
            self._set_error("Nuvei: " + _(
                "Received invalid transaction status %(status)s and reason '%(reason)s'.",
                status=status, reason=status_description
            ))
