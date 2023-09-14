# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.http import request

from odoo.addons.mail.controllers.attachment import AttachmentController
from odoo.addons.portal.utils import get_portal_partner


class PortalAttachmentController(AttachmentController):
    def _is_allowed_to_delete(self, message, **kwargs):
        thread = request.env[message.model].browse(message.res_id)
        if (
            thread
            and request.env.user._is_public()
            and get_portal_partner(
                thread, kwargs.get("hash"), kwargs.get("pid"), kwargs.get("token")
            )
        ):
            return True
        return super()._is_allowed_to_delete(message, **kwargs)
