from odoo import models, fields


class check_layout_format(models.Model):
    _name = "account.check.layout.format"
    _description = "Check layout format"

    name = fields.Char(required=True)
    description = fields.Text()

    # Check dimensions
    account_check_width = fields.Float(required=True)
    account_check_height = fields.Float(required=True)

    # Check date
    account_check_date_dist_from_top = fields.Float(required=True)
    account_check_date_dist_from_left = fields.Float(required=True)
    account_check_date_format = fields.Char()
    account_check_date_dist_bet_char = fields.Float(required=True)

    # Payee/Party name
    account_payee_dist_from_top = fields.Float(required=True)
    account_payee_dist_from_left = fields.Float(required=True)
    account_payee_width_area = fields.Float(required=True)

    # amount in words
    account_aiw_line1_dist_from_top = fields.Float(required=True)
    account_aiw_line2_dist_from_top = fields.Float(required=True)
    account_aiw_line1_dist_from_left = fields.Float(required=True)
    account_aiw_line2_dist_from_left = fields.Float(required=True)
    account_aiw_line1_width_area = fields.Float(required=True)
    account_aiw_line2_width_area = fields.Float(required=True)
    account_aiw_currency_name = fields.Selection(selection=[('yes', 'Yes'), ('no', 'No')], required=True)

    # amount in figures
    account_aif_dist_from_top = fields.Float(required=True)
    account_aif_dist_from_left = fields.Float(required=True)
    account_aif_width_area = fields.Float(required=True)
    account_aif_currency_name = fields.Selection(selection=[('yes', 'Yes'), ('no', 'No')], required=True)
