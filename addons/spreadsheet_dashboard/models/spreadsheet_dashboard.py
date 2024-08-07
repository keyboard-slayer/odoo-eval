import json

from odoo import _, fields, models
from odoo.tools import file_open


class SpreadsheetDashboard(models.Model):
    _name = 'spreadsheet.dashboard'
    _description = 'Spreadsheet Dashboard'
    _inherit = "spreadsheet.mixin"
    _order = 'sequence'

    name = fields.Char(required=True, translate=True)
    dashboard_group_id = fields.Many2one('spreadsheet.dashboard.group', required=True)
    sequence = fields.Integer()
    sample_dashboard_file_path = fields.Char(export_string_translation=False)
    is_published = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company')
    group_ids = fields.Many2many('res.groups', default=lambda self: self.env.ref('base.group_user'))
    main_data_model_ids = fields.Many2many('ir.model')

    def get_readonly_dashboard(self):
        self.ensure_one()
        snapshot = json.loads(self.spreadsheet_data)
        if self.dashboard_is_empty() and self.sample_dashboard_file_path:
            with file_open(self.sample_dashboard_file_path) as f:
                sample_data = json.load(f)
            return {
                "snapshot": sample_data,
                "isSample": True,
            }
        user_locale = self.env['res.lang']._get_user_spreadsheet_locale()
        snapshot.setdefault('settings', {})['locale'] = user_locale
        default_currency = self.env['res.currency'].get_company_currency_for_spreadsheet()
        return {
            'snapshot': snapshot,
            'revisions': [],
            'default_currency': default_currency,
        }

    def dashboard_is_empty(self, revisions=[]):
        if len(revisions) > 0:
            return False
        return (
            any(self.env[model.model].search_count([], limit=1) == 0 for model in self.main_data_model_ids)
            and self.env["spreadsheet.revision"].with_context(active_test=False).search_count([("res_id", "=", self.id), ("res_model", "=", self._name)], limit=1) == 0
        )

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        if 'name' not in default:
            for dashboard, vals in zip(self, vals_list):
                vals['name'] = _("%s (copy)", dashboard.name)
        return vals_list
