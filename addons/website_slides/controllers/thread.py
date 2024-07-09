# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.mail.controllers import thread
from odoo import _, http
from odoo.http import request
from odoo.exceptions import ValidationError


class ThreadController(thread.ThreadController):

    @http.route()
    def mail_message_post(self, thread_model, thread_id, post_data, context=None, **kwargs):
        previous_post = request.env["mail.message"].search(
            [
                ("res_id", "=", thread_id),
                ("author_id", "=", request.env.user.partner_id.id),
                ("model", "=", "slide.channel"),
                ("subtype_id", "=", request.env.ref("mail.mt_comment").id),
            ]
        )
        if thread_model == "slide.channel" and previous_post:
            raise ValidationError(_("Only a single review can be posted per course."))
        message = super().mail_message_post(thread_model, thread_id, post_data, context, **kwargs)
        if message and thread_model == "slide.channel":
            rating_value = post_data.get("rating_value", False)
            slide_channel = request.env[thread_model].sudo().browse(int(thread_id))
            if (
                rating_value
                and slide_channel
                and request.env.user.partner_id.id == int(kwargs.get("pid"))
            ):
                request.env.user._add_karma(
                    slide_channel.karma_gen_channel_rank,
                    slide_channel,
                    _("Course Ranked"),
                )
            message.update(
                {
                    "default_rating_value": rating_value,
                    "rating_avg": slide_channel.rating_avg,
                    "rating_count": slide_channel.rating_count,
                    "force_submit_url": message.get("default_message_id")
                    and "/slides/mail/update_comment",
                }
            )
        return message
