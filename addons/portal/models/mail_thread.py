# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac

from werkzeug.exceptions import Forbidden, NotFound

from odoo import api, fields, models, _
from odoo.tools import consteq, frozendict


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    _mail_post_token_field = 'access_token' # token field for external posts, to be overridden

    website_message_ids = fields.One2many('mail.message', 'res_id', string='Website Messages',
        domain=lambda self: [('model', '=', self._name), ('message_type', 'in', ('comment', 'email', 'email_outgoing'))],
        auto_join=True,
        help="Website communication history")

    def _notify_get_recipients_groups(self, message, model_description, msg_vals=None):
        groups = super()._notify_get_recipients_groups(
            message, model_description, msg_vals=msg_vals
        )
        if not self:
            return groups

        portal_enabled = isinstance(self, self.env.registry['portal.mixin'])
        if not portal_enabled:
            return groups

        customer = self._mail_get_partners(introspect_fields=False)[self.id]
        if customer:
            access_token = self._portal_ensure_token()
            local_msg_vals = dict(msg_vals or {})
            local_msg_vals['access_token'] = access_token
            local_msg_vals['pid'] = customer.id
            local_msg_vals['hash'] = self._sign_token(customer.id)
            local_msg_vals.update(customer.signup_get_auth_param()[customer.id])
            access_link = self._notify_get_action_link('view', **local_msg_vals)

            new_group = [
                ('portal_customer', lambda pdata: pdata['id'] == customer.id, {
                    'active': True,
                    'button_access': {
                        'url': access_link,
                    },
                    'has_button_access': True,
                })
            ]
        else:
            new_group = []

        # enable portal users that should have access through portal (if not access rights
        # will do their duty)
        portal_group = next(group for group in groups if group[0] == 'portal')
        portal_group[2]['active'] = True
        portal_group[2]['has_button_access'] = True

        return new_group + groups

    def _sign_token(self, pid):
        """Generate a secure hash for this record with the email of the recipient with whom the record have been shared.

        This is used to determine who is opening the link
        to be able for the recipient to post messages on the document's portal view.

        :param str email:
            Email of the recipient that opened the link.
        """
        self.ensure_one()
        # check token field exists
        if self._mail_post_token_field not in self._fields:
            raise NotImplementedError(_(
                "Model %(model_name)s does not support token signature, as it does not have %(field_name)s field.",
                model_name=self._name,
                field_name=self._mail_post_token_field
            ))
        # sign token
        secret = self.env["ir.config_parameter"].sudo().get_param("database.secret")
        token = (self.env.cr.dbname, self[self._mail_post_token_field], pid)
        return hmac.new(secret.encode('utf-8'), repr(token).encode('utf-8'), hashlib.sha256).hexdigest()

    def _portal_get_parent_hash_token(self, pid):
        """ Overridden in models which have M2o 'parent' field and can be shared on
        either an individual basis or indirectly in a group via the M2o record.

        :return: False or logical parent's _sign_token() result
        """
        return False

    def _check_thread_portal_access(self, thread_id, token, _hash, pid):
        has_access = False
        if token or (_hash and pid):
            record = self.browse(thread_id).sudo()
            if _hash and pid:  # Signed Token Case: hash implies token is signed by partner pid
                pid = int(pid)
                has_access = consteq(_hash, record._sign_token(pid))
                if not has_access:
                    parent_sign_token = record._portal_get_parent_hash_token(pid)
                    has_access = parent_sign_token and consteq(_hash, parent_sign_token)
            elif token:  # Token Case: token is the global one of the document
                token_field = self._mail_post_token_field
                has_access = token and record and consteq(record[token_field], token)
            if not has_access:
                raise Forbidden()
            partner_id = self.env.user.partner_id
            if _hash and pid:
                partner_id = self.env["res.partner"].sudo().browse(pid)
            elif token:
                if self.env.user._is_public() and hasattr(record, "partner_id") and record.partner_id:
                    partner_id = record.partner_id
                elif not partner_id:
                    raise NotFound()
            self.env.context = frozendict({**self.env.context, "portal_partner": partner_id})
        return has_access

    @api.model
    def _get_thread_with_access(self, thread_id, **kwargs):
        if self._check_thread_portal_access(
            thread_id, kwargs.get("token"), kwargs.get("hash"), kwargs.get("pid")
        ):
            return (
                super(MailThread, self.sudo())
                ._get_thread_with_access(thread_id, **kwargs)
                .with_context(mail_create_nosubscribe=True)
            )
        return super()._get_thread_with_access(thread_id, **kwargs)
