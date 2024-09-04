# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import uuid
from hashlib import sha1
from datetime import timedelta

from werkzeug.urls import url_join, url_encode

from odoo import _, api, fields, models
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import AccessError, UserError

from odoo.addons.payment_razorpay_oauth import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    razorpay_key_id = fields.Char(
        required_if_provider=False,
        copy=False
    )
    razorpay_key_secret = fields.Char(
        required_if_provider=False,
        copy=False
    )
    razorpay_webhook_secret = fields.Char(
        required_if_provider=False,
        copy=False
    )
    # Use for Oauth
    razorpay_access_token = fields.Char(
        string='Access Token',
        groups='base.group_system',
        copy=False
    )
    razorpay_access_token_expiration = fields.Datetime(
        string='Access Token Expiration',
        groups='base.group_system',
        copy=False
    )
    razorpay_account_id = fields.Char(
        string="Account ID",
        copy=False
    )
    razorpay_refresh_token = fields.Char(
        string='Refresh Token',
        groups='base.group_system',
        copy=False
    )
    razorpay_public_token = fields.Char(
        string='Public Token',
        groups='base.group_system',
        copy=False
    )

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    @api.onchange('state')
    def _onchange_state(self):
        if self.razorpay_public_token and self._origin.state != self.state:
            self.write({
                'razorpay_access_token': False,
                'razorpay_refresh_token': False,
                'razorpay_access_token_expiration': False,
                'razorpay_public_token': False,
                'razorpay_key_id': False,
                'razorpay_key_secret': False,
                'razorpay_webhook_secret': False,
            })

    def _get_razorpay_access_token(self):
        super()._get_razorpay_access_token()
        return self.razorpay_access_token

# -------------------------------------------------------------------------
    # OAUTH ACTIONS
    # -------------------------------------------------------------------------

    def action_razorpay_redirect_to_oauth_url(self):
        """
        Redirect to the Razorpay Oauth url.
        :return: A url action with Razorpay Oauth url.
        :rtype: dict
        """
        self.ensure_one()
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        oauth_url = self._razorpay_get_oauth_url()
        params = {
            'dbuuid': dbuuid,
            'state': self._razorpay_generate_authorization_state(),
            'id': self.id,
            'redirect_url': self.get_base_url() + '/payment/razorpay/oauth/callback',
        }
        authorization_url = url_join(
            oauth_url, 'api/razorpay/1/authorize?%s'
            % url_encode(params)
        )
        return {
            'type': 'ir.actions.act_url',
            'url': authorization_url,
            'target': 'self',
        }

    def _razorpay_generate_authorization_state(self):
        """
        Generate a random 80-character string for use as a secure state parameter.
        :return: Random string.
        :rtype: str
        """
        database_uuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        current_date = fields.Datetime.now()
        return sha1(f'{database_uuid}{self.id}{current_date}'.encode()).hexdigest()

    def _razorpay_get_oauth_url(self):
        """
        Return the Oauth url for Razorpay.
        :return: The Razorpay Oauth url.
        :rtype: str
        """
        self.ensure_one()
        return self.env['ir.config_parameter'].sudo().get_param('payment_razorpay.oauth_url', const.OAUTH_URL)

    def action_razorpay_create_or_update_webhook(self):
        """
        Create or update the Razorpay webhook.
        This method sets up or updates the webhook in Razorpay to keep payment states synced with
        Odoo. It sends a request to the Razorpay API with the necessary parameters.
        """
        self.ensure_one()
        response = self._razorpay_generate_webhook()
        error = response.get('error', {})
        if error.get('code') == 'http_error':
            _logger.exception("Error on connect with Razorpay %s",
                error.get('message', str(error))
            )
            raise UserError(_('Unable/Unauthorized to connect Razorpay.'))
        elif error:
            raise UserError(error.get('description', str(error)))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'message': _("Webhook successfully updated"),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _razorpay_generate_webhook(self):
        webhook_url = url_join(self._razorpay_get_oauth_url(), '/api/razorpay/1/create_webhook')
        self.razorpay_webhook_secret = uuid.uuid4().hex
        params = {
            'account_id': self.razorpay_account_id,
            'access_token': self.razorpay_access_token,
            'webhook_url': self.get_base_url() + '/payment/razorpay/webhook',
            'webhook_secret': self.razorpay_webhook_secret,
        }

        try:
            response = iap_tools.iap_jsonrpc(webhook_url, params=params, timeout=60)
        except AccessError as e:
            raise UserError(
                _("Unable to create and update webhook."
                "Razorpay gave us the following information: %s",
                str(e))
            )

        return response

    def action_razorpay_revoked_token(self):
        """
        Revoke the Razorpay access token.
        This method generates a URL to revoke the Razorpay access token.
        After revocation the token will no longer be valid.
        :return: URL for revoking the access token.
        :rtype: str
        """
        self.write({
            'razorpay_account_id': False,
            'razorpay_access_token': False,
            'razorpay_refresh_token': False,
            'razorpay_access_token_expiration': False,
            'razorpay_public_token': False,
            'razorpay_webhook_secret': False,
            'state': 'disabled',
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'sticky': False,
                'message': _("Successfully Disconnected"),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _razorpay_refresh_token(self):
        """
        Refresh the Razorpay access token.
        This method retrieves a new access token using the refresh token and updates the record with
        the new token details. It handles errors if the token cannot be refreshed.
        :return: dict
        """
        self.ensure_one()
        request_url = url_join(self._razorpay_get_oauth_url(), '/api/razorpay/1/get_refresh_token')
        params = {
            'refresh_token': self.razorpay_refresh_token,
        }
        try:
            response = iap_tools.iap_jsonrpc(request_url, params=params, timeout=60)
        except AccessError:
            raise UserError(
                _('Something went wrong during refreshing the token.')
            )
        if response.get('error'):
            _logger.warning("Error :during refreshing token. %s", str(response['error']))

        if not response.get('access_token'):
            _logger.warning("New Token not exist in response. %s", response)

        expires_in = fields.Datetime.now() + timedelta(seconds=int(response['expires_in']))
        self.write({
            'razorpay_access_token': response.get('access_token'),
            'razorpay_public_token': response.get('public_token'),
            'razorpay_access_token_expiration': expires_in,
            'razorpay_refresh_token': response.get('refresh_token'),
        })
