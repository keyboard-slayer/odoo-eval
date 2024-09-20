# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from random import randint

from odoo import fields, models


class MeetingType(models.Model):

    _name = 'calendar.event.type'
    _description = 'Event Meeting Type'

    def _default_color(self):
        return randint(1, 11)

    name = fields.Char('Name', required=True)
    color = fields.Integer('Color', default=_default_color)

    _name_uniq = models.Constraint(
        'unique (name)',
        lambda env: env._('Tag name already exists!'),
    )
