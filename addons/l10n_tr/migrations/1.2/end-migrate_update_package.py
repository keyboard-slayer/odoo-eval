# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api
from odoo.api import SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env['res.company'].search([('chart_template', '=', 'tr')]):
        env['account.chart.template'].try_loading('tr', company)
