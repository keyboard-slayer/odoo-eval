# -*- coding: utf-8 -*-
from odoo import fields, models


class IrActionsActWindowView(models.Model):
    _name = "ir.actions.act_window.view"

    _inherit = ['ir.actions.act_window.view']

    view_mode = fields.Selection(selection_add=[
        ('activity', 'Activity')
    ], ondelete={'activity': 'cascade'})
