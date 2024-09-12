from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env['res.company'].search([('chart_template', 'in', ('es_assec', 'es_common', 'es_coop_full', 'es_coop_pymes', 'es_full', 'es_pymes'))]):
        env['account.chart.template'].try_loading(company.chart_template, company)
