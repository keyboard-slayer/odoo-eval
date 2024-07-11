# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.addons.project.controllers.project_sharing_chatter import ProjectSharingChatter


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.model
    def _get_thread_with_access(self, thread_id, mode="read", **kwargs):
        if project_sharing_id := kwargs.get("project_sharing_id"):
            if token := ProjectSharingChatter._check_project_access_and_get_token(
                self, project_sharing_id, self._name, thread_id, kwargs.get("token")
            ):
                kwargs["token"] = token
        return super()._get_thread_with_access(thread_id, mode, **kwargs)
