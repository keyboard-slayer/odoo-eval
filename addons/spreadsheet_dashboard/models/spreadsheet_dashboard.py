import json

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError


class SpreadsheetDashboard(models.Model):
    _name = 'spreadsheet.dashboard'
    _description = 'Spreadsheet Dashboard'
    _inherit = "spreadsheet.mixin"
    _order = 'sequence'

    name = fields.Char(required=True, translate=True)
    dashboard_group_id = fields.Many2one('spreadsheet.dashboard.group', required=True)
    sequence = fields.Integer()
    is_published = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company')
    group_ids = fields.Many2many('res.groups', default=lambda self: self.env.ref('base.group_user'))
    favorite_user_ids = fields.Many2many(
        'res.users', string='Favorite Users', help='Users who have favorited this dashboard'
    )
    is_favorite = fields.Boolean(
        compute='_compute_is_favorite', string='Is Favorite',
        help='Indicates whether the dashboard is favorited by the current user'
    )
    main_data_model_ids = fields.Many2many('ir.model')

    @api.depends('favorite_user_ids')
    def _compute_is_favorite(self):
        current_user_id = self.env.uid
        for dashboard in self:
            dashboard.is_favorite = current_user_id in dashboard.favorite_user_ids.ids

    def action_toggle_favorite(self):
        self.ensure_one()
        try:
            self.check_access('read')
        except AccessError:
            raise AccessError(_("You don't have the required access rights to favorite this dashboard."))

        current_user_id = self.env.uid
        if current_user_id in self.sudo().favorite_user_ids.ids:
            self.sudo().favorite_user_ids = [Command.unlink(current_user_id)]
        else:
            self.sudo().favorite_user_ids = [Command.link(current_user_id)]

    def get_readonly_dashboard(self):
        self.ensure_one()
        snapshot = json.loads(self.spreadsheet_data)
        user_locale = self.env['res.lang']._get_user_spreadsheet_locale()
        snapshot.setdefault('settings', {})['locale'] = user_locale
        default_currency = self.env['res.currency'].get_company_currency_for_spreadsheet()
        return {
            'snapshot': snapshot,
            'revisions': [],
            'default_currency': default_currency,
        }

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        if 'name' not in default:
            for dashboard, vals in zip(self, vals_list):
                vals['name'] = _("%s (copy)", dashboard.name)
        return vals_list
