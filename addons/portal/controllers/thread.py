# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.tools import html2plaintext
from odoo.http import request
from odoo.addons.mail.controllers import thread


class ThreadController(thread.ThreadController):

    @http.route()
    def mail_message_post(self, thread_model, thread_id, post_data, context=None, **kwargs):
        message = super().mail_message_post(thread_model, thread_id, post_data, context, **kwargs)
        message_data = message.get("Message")
        if (message_data := message_data and message_data[0]) and request.env[
            "res.partner"
        ]._get_portal_partner_from_context():
            message = {
                "default_message": html2plaintext(message_data.get("body")),
                "default_message_id": message_data.get("id"),
                "default_attachment_ids": message_data.get("attachments"),
            }
        return message

    def _get_allowed_message_post_params(self):
        post_params = super()._get_allowed_message_post_params()
        if request.env["res.partner"]._get_portal_partner_from_context():
            post_params.update(["author_id", "send_after_commit"])
        return post_params

    def _prepare_post_data(self, post_data, thread, special_mentions, **kwargs):
        post_data = super()._prepare_post_data(post_data, thread, special_mentions, **kwargs)
        if portal_partner := request.env["res.partner"]._get_portal_partner_from_context():
            post_data["author_id"] = portal_partner.id
            post_data["send_after_commit"] = False
            post_data.pop("parent_id", None)
            post_data["message_type"] = post_data.pop("message_type", "comment")
            post_data["subtype_xmlid"] = post_data.pop("subtype_xmlid", "mail.mt_comment")
        return post_data
