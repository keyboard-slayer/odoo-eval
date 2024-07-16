# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools import _


class KarmaTracking(models.Model):
    _inherit = 'gamification.karma.tracking'

    def _get_origin_selection_values(self):
        return (
            super(KarmaTracking, self)._get_origin_selection_values()
            + [('slide.slide', _('Course Quiz')), ('slide.channel', self.env['ir.model']._get('slide.channel').display_name)]
        )
