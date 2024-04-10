# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models

AVAILABLE_PRIORITIES = [
    ('0', 'Low'),
    ('1', 'Medium'),
    ('2', 'High'),
    ('3', 'Very High'),
]


class Stage(models.Model):
    """ Model for case stages. This models the main stages of a document
        management flow. Main CRM objects (leads, opportunities, project
        issues, ...) will now use only stages, instead of state and stages.
        Stages are for example used to display the kanban view of records.
    """
    _name = "crm.stage"
    _description = "CRM Stages"
    _rec_name = 'name'
    _order = "sequence, name, id"

    @api.model
    def default_get(self, fields):
        """ As we have lots of default_team_id in context used to filter out
        leads and opportunities, we pop this key from default of stage creation.
        Otherwise stage will be created for a given team only which is not the
        standard behavior of stages. """
        if 'default_team_id' in self.env.context:
            ctx = dict(self.env.context)
            ctx.pop('default_team_id')
            self = self.with_context(ctx)
        return super(Stage, self).default_get(fields)

    name = fields.Char('Stage Name', required=True, translate=True)
    # Default needs to be high in order to have them set as end stage before computing frequencies when setting actual sequence.
    # Otherwise it starts low, frequencies are updated accordingly (almost max lost_count), then updated to max sequence -> all below stage
    sequence = fields.Integer('Sequence', default=1000, help="Used to order stages. Lower is better.")
    is_won = fields.Boolean('Is Won Stage?')
    requirements = fields.Text('Requirements', help="Enter here the internal requirements for this stage (ex: Offer sent to customer). It will appear as a tooltip over the stage's name.")
    team_id = fields.Many2one('crm.team', string='Sales Team', ondelete="set null",
        help='Specific team that uses this stage. Other teams will not be able to see or use this stage.')
    fold = fields.Boolean('Folded in Pipeline',
        help='This stage is folded in the kanban view when there are no records in that stage to display.')
    # This field for interface only
    team_count = fields.Integer('team_count', compute='_compute_team_count')

    @api.depends('team_id')
    def _compute_team_count(self):
        self.team_count = self.env['crm.team'].search_count([])

    def write(self, vals):
        """ Since leads that are in a won stage must have their
        probability = 100%, this override ensures that setting a stage as won
        will set all the leads in that stage to probability = 100%.
        Inversely, if a won stage is not marked as won anymore, the lead
        probability should be recomputed based on automated probability.
        Note: If a user sets a stage as won and changes his mind right after,
        the manual probability will be lost in the process."""
        res = super(Stage, self).write(vals)
        if 'is_won' in vals:
            won_leads = self.env['crm.lead'].search([('stage_id', 'in', self.ids)])
            if won_leads and vals.get('is_won'):
                won_leads.write({'probability': 100, 'automated_probability': 100})
            elif won_leads and not vals.get('is_won'):
                won_leads._compute_probabilities()
        return res

    def unlink(self):
        res = super().unlink()
        self.env['crm.lead.scoring.frequency'].sudo().search([
            ('variable', '=', 'stage_id'),
            ('value', 'in', [str(id_value) for id_value in self.ids])
        ]).unlink()
        return res
