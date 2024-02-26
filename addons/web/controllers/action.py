# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import _
from odoo.exceptions import MissingError
from odoo.http import Controller, request, route
from .utils import clean_action
from werkzeug.exceptions import BadRequest


_logger = logging.getLogger(__name__)


class Action(Controller):

    @route('/web/action/load', type='json', auth='user', readonly=True)
    def load(self, action_id, additional_context=None):
        Actions = request.env['ir.actions.actions']
        value = False
        try:
            action_id = int(action_id)
        except ValueError:
            try:
                if '.' in action_id:
                    action = request.env.ref(action_id)
                else:
                    action = Actions.search([('path', '=', action_id)], limit=1)
                assert action._name.startswith('ir.actions.')
                action_id = action.id
            except Exception as exc:
                raise MissingError(_("The action %r does not exist.", action_id)) from exc

        base_action = Actions.browse([action_id]).sudo().read(['type'])
        if base_action:
            action_type = base_action[0]['type']
            if action_type == 'ir.actions.report':
                request.update_context(bin_size=True)
            if additional_context:
                request.update_context(**additional_context)
            action = request.env[action_type].sudo().browse([action_id]).read()
            if action:
                value = clean_action(action[0], env=request.env)
        return value

    @route('/web/action/run', type='json', auth="user")
    def run(self, action_id, context=None):
        if context:
            request.update_context(**context)
        action = request.env['ir.actions.server'].browse([action_id])
        result = action.run()
        return clean_action(result, env=action.env) if result else False

    @route('/web/action/load_breadcrumbs', type='json', auth='user', readonly=True)
    def load_breadcrumbs(self, actions):
        display_names = []
        for action in actions:
            record_id = action.get('resId')
            try:
                if action.get('action'):
                    act = self.load(action.get('action'))
                    if record_id:
                        display_names.append(request.env[act['res_model']].browse(record_id).display_name)
                    else:
                        display_names.append(act['display_name'])
                elif action.get('model'):
                    Model = request.env[action.get('model')]
                    if record_id:
                        display_names.append(Model.browse(record_id).display_name)
                    else:
                        # This case cannot be produced by the web client
                        # display_names.append(Model._description)
                        raise BadRequest('Actions with a model should also have a resId')
                else:
                    raise BadRequest('Actions should have either an action (id or path) or a model')
            except Exception: # FIXME don't catch blind exceptions
                display_names.append(None) # TODO: add something that could allow the webclient to show a warning for some things?
        return display_names
