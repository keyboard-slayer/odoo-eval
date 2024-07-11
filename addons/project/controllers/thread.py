# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.addons.mail.controllers import thread
from odoo.addons.project.controllers.project_sharing_chatter import ProjectSharingChatter


class ThreadController(thread.ThreadController):

    @http.route()
    def mail_message_post(self, thread_model, thread_id, post_data, context=None, **kwargs):
        project_sharing_id = kwargs.get("project_sharing_id")
        if project_sharing_id:
            token = ProjectSharingChatter._check_project_access_and_get_token(
                self, project_sharing_id, thread_model, thread_id, kwargs.get("token")
            )
            if token:
                kwargs["token"] = token
        return super().mail_message_post(thread_model, thread_id, post_data, context, **kwargs)
