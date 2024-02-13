from odoo import api, fields, models


class AccountReportClosing(models.Model):
    _name = "account.report.closing"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Account Report Closing"
    _check_company_auto = True

    name = fields.Char(string="Name", required=True)
    closing_type_id = fields.Many2one(string="Type", comodel_name='account.report.closing.type', required=True)
    date = fields.Date(string="Date", required=True)
    locked_journal_ids = fields.Many2many(string="Locked Journals", comodel_name='account.journal')
    closing_move_ids = fields.One2many(string="Closing Moves", comodel_name='account.move', inverse_name='report_closing_id') #TODO OCO du coup, empêcher l'édition de ces moves semble indiqué
    state = fields.Selection(string="State", selection=[('in_progress', "In Progress"), ('closed', "Closed")], required=True, default='in_progress')
    notes = fields.Html(string="Notes") #TODO OCO on pourrait lui mettre une valeur par défaut set sur le closing type; peut-être too much, mais pas sûr; ce sont des flux cycliques
    #TODO OCO statuer sur le fait de mettre la fpos dessus (si on garde le cas de multivat indien)
    company_id = fields.Many2one(string="Company", comodel_name='res.company', required=True)
    report_id = fields.Many2one(string="Report", comodel_name='account.report') # Only set when generating closings with split_per_report


class AccountReportClosingType(models.Model):
    _name = "account.report.closing.type"
    _description = "Account Report Closing Type"

    name = fields.Char(string="Name", required=True)
    tax_ids = fields.One2many(string="Taxes", comodel_name='account.tax', inverse_name='closing_type_id')
    on_interval = fields.Boolean(string="On Interval")
    report_ids = fields.One2many(string="Reports", comodel_name='account.report', inverse_name='closing_type_id')
    move_generator_code = fields.Char(string="Entry Generator")
    lock_journals = fields.Boolean(string="Lock Journals")
    split_per_report = fields.Boolean(string="Split per Report")

    #TODO OCO je le mets ici pour une raison simple: si deux rapports partagent la même closing et peuvent avoir des périodicités différentes, c'est tout foireux => overengineering pour éventuellement les gérer, clairement
    #TODO OCO pour le cas de l'EC Sales List à rendre avec le tax report belge ; on pourrait peut-être plutôt s'en sortir avec une section optionnelle sur le rapport de taxes, et une closing liée juste à ce rapport
    periodicity = fields.Selection(
        string="Periodicity",
        selection=[
            ('year', 'Annually'),
            ('semester', 'Semi-annually'),
            ('4_months', 'Every 4 months'),
            ('trimester', 'Quarterly'),
            ('2_months', 'Every 2 months'),
            ('monthly', 'Monthly'),
        ], #TODO OCO renommer les labels techniques, ce serait pas mal, je pense... c'est super incohérent
        company_dependent=True,
        required=True,
    ) # TODO OCO mais du coup, si on le met ici, c'est cross company :/ => un peu nul, quand même. => un par société ? Ou champ company_dependent, simpplement ?
    #TODO OCO on devrait sans doute en faire un par compagnie, justement pour que le mec puisse en créer lui-même, en fait
    # ====> non parce que sinon, comment on lie les rapports à une closing ? Ca marcherait pas :/

    tax_closing_payable_account_id = fields.Many2one(string="Tax Payable Account", comodel_name='account.account', company_dependent=True, required=True)
    tax_closing_receivable_account_id = fields.Many2one(string="Tax Receivable Account", comodel_name='account.account', company_dependent=True, required=True)
    tax_closing_journal_id = fields.Many2one(string="Tax Closing Journal", comodel_name='account.journal', company_dependent=True, required=True)



    #TODO OCO pour les trucs comme l'EDI FR, on pourrait avoir un champ property sur les closings

    #TODO OCO une tax closing doit générer un object closing par rapport (et peut-être * fpos), pas une clôture qui veut juste vérifier des rapports ensemble => un booléen pour "spread" la closing par rapport et un m2o optionel sur les closings pour ce cas ?

    # TODO OCO si on mettait un champ active company_dependent à True par défaut ? (ça marche ?) comme ça, pas obligé d'utiliser chaque closing type partout

    @api.model_create_multi
    def create(self, vals_list):
        rslt = super().create(vals_list)
        for closing_type in rslt:
            self.env['ir.property']._set_default('periodicity', 'account.report.closing.type', closing_type.periodicity, res_id=closing_type.id) #TODO OCO à tester, mais ça devrait le faire
        return rslt
