# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import functools
import logging
from collections import defaultdict
from datetime import date
from http import HTTPStatus
from urllib.parse import urlencode

import psycopg2.errors
from dateutil.relativedelta import relativedelta
from lxml import etree
from werkzeug.exceptions import BadRequest

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.models import regex_object_name
from odoo.osv import expression
from odoo.tools import lazy
from odoo.tools.safe_eval import safe_eval

from .utils import get_action_triples

_logger = logging.getLogger(__name__)


class WebJsonController(http.Controller):

    @http.route('/json/<path:subpath>', auth='public', type='http', readonly=True)
    def web_json(self, subpath, **kwargs):
        return self.web_json_version_1(subpath, **kwargs, redirect=True)

    @http.route('/json/1/<path:subpath>', auth='user', type='http', readonly=True)
    def web_json_version_1(self, subpath, **kwargs):
        env = request.env
        if not request.env.user.has_group('base.group_allow_export'):
            raise AccessError(env._("You need export permissions to use the /json route"))

        # redirect when the kwargs have changed
        param_list = set(kwargs)
        kwargs.pop("redirect", None)  # pop redirect, so it is forced in check_redirect

        def check_redirect():
            if set(param_list) == set(kwargs):
                return None
            # for domains, make chars as safe
            encoded_kwargs = urlencode(kwargs, safe="()[], '\"")
            return request.redirect(
                f'/json/1/{subpath}?{encoded_kwargs}',
                HTTPStatus.TEMPORARY_REDIRECT
            )

        def get_action_triples_():
            try:
                yield from get_action_triples(env, subpath, start_pos=1)
            except ValueError as exc:
                raise BadRequest(exc.args[0])

        # Hack for OXP. We are not sure yet if we wanna run all server
        # actions, but we are sure we want to run those ones. TODO: find
        # a better way to do it.
        allowed_server_action_paths = {'crm'}

        context = dict(env.context)
        context_eval = safe_eval
        for active_id, action, record_id in get_action_triples_():
            if action.sudo().path in allowed_server_action_paths:
                try:
                    action_data = action.sudo(False).run()
                except psycopg2.errors.ReadOnlySqlTransaction as e:
                    # never retry on RO connection, just leave
                    raise AccessError() from e
                action = env[action_data['type']]
                action = action.new(action_data, origin=action.browse(action_data.pop('id')))
            if action._name != 'ir.actions.act_window':
                e = f"{action._name} are not supported server-side"
                raise BadRequest(e)
            context_eval = functools.partial(safe_eval, globals_dict=dict(
                action._get_eval_context(action),
                active_id=active_id,
                context=context,
            ))
            context.update(context_eval(action.context))
        action_domain = context_eval(action.domain or '[]')
        model = env[action.res_model].with_context(context)

        # Get the view type
        assert action._name == 'ir.actions.act_window'
        view_modes = action.view_mode.split(',')
        view_type = kwargs.get('view_type')
        if not view_type:
            view_type = 'form' if record_id else view_modes[0]
        for view_id, action_view_type in action.views:
            if view_type == action_view_type:
                break
        else:
            if view_type not in view_modes:
                raise BadRequest(env._(
                    "Invalid view type %(view_type)s for action %(action)s",
                    view_type=view_type,
                    action=action,
                ))
            view_id = False

        # Get the view
        view = model.get_view(view_id, view_type)
        spec = model._get_fields_spec(view)
        view_tree = lazy(lambda: etree.fromstring(view['arch']))

        # Simple case: form view with record
        if record_id or view_type == 'form':
            if redirect := check_redirect():
                return redirect
            if not record_id:
                raise BadRequest(env._("Missing record id"))
            res = model.browse(int(record_id)).web_read(spec)[0]
            return request.make_json_response(res)

        # Find domain and limits
        if "domain" in kwargs:
            # for the user-given domain, use only literal-eval instead of safe_eval
            user_domain = ast.literal_eval(kwargs.get("domain") or "[]")
        else:
            default_domain = self.__filter_user_default(action, model)
            if default_domain:
                default_domain = context_eval(default_domain)
            else:
                default_domain = expression.AND(map(
                    context_eval,
                    self.__filter_from_context(context, action, model),
                ))
            if default_domain and default_domain != expression.TRUE_DOMAIN:
                kwargs["domain"] = repr(default_domain)
            user_domain = default_domain
        try:
            limit = int(kwargs.get("limit", 0)) or action.limit
            offset = int(kwargs.get("offset", 0))
        except ValueError as exc:
            raise BadRequest(exc.args[0])
        if "offset" not in kwargs:
            kwargs["offset"] = offset
        if "limit" not in kwargs:
            kwargs["limit"] = limit

        # Add date domain for some view types
        date_domain = []
        if view_type in ('calendar', 'gantt', 'cohort'):
            try:
                start_date, end_date = self.__get_start_date_end_date(kwargs)
            except ValueError as exc:
                raise BadRequest(exc)
            if start_date and end_date:
                date_field = view_tree.attrib.get("date_start")
                assert date_field, "Could not find the date field in the view"
                date_domain = [(date_field, '>=', start_date), (date_field, '<', end_date)]
            else:
                # by default, select the current month
                month = date.today() + relativedelta(day=1)
                kwargs.update({
                    'start_date': month.isoformat(),
                    'end_date': (month + relativedelta(months=1)).isoformat(),
                })

        # Add explicitly activity fields for an activity view
        activity_domain = []
        if view_type == 'activity':
            activity_domain = [('activity_ids', '!=', False)]
            # add activity fields
            for field_name, field in model._fields.items():
                if field_name.startswith("activity_") and field_name not in spec and field.is_accessible(env):
                    spec[field_name] = {}

        # Group by
        groupby = kwargs.get('groupby')
        fields = kwargs.get('fields')
        if groupby:
            groupby = groupby.split(",")
        if fields:
            fields = fields.split(',')
        if groupby is None and view_tree.attrib.get('default_group_by'):
            # in case the kanban view (or other) defines a default grouping
            # add that field to the spec
            default_group_by_field = view_tree.attrib.get('default_group_by')
            spec.setdefault(default_group_by_field, {})
        if not groupby and view_type in ('pivot', 'graph'):
            # extract groupby from the view if we don't have any
            field_by_type = defaultdict(list)
            for element in view_tree.findall(r"./field"):
                field_name = element.attrib.get("name")
                if element.attrib.get("invisible", "") in ("1", "true"):
                    field_by_type["invisible"].append(field_name)
                else:
                    field_by_type[element.attrib.get("type", "normal")].append(field_name)
                # not reading interval from the attribute
            groupby = [
                *field_by_type.get("row", ()),
                *field_by_type.get("col", ()),
                *field_by_type.get("normal", ()),
            ]
            assert groupby, f"No groupby columns found in view {view['id']}"
            kwargs['groupby'] = ','.join(groupby)
            if "measure" in field_by_type and "fields" not in kwargs:
                kwargs['fields'] = field_by_type['measure'][0]

        # Last checks before the query
        if redirect := check_redirect():
            return redirect
        domain = expression.AND([action_domain, date_domain, user_domain, activity_domain])
        # Reading a group or a list
        if groupby:
            res = model.web_read_group(
                domain,
                fields=fields or ['__count'],
                groupby=groupby,
                limit=limit,
                lazy=False,
            )
            # pop '__domain' key
            for value in res["groups"]:
                del value["__domain"]
        else:
            res = model.web_search_read(
                domain,
                spec,
                limit=limit,
                offset=offset,
            )
        return request.make_json_response(res)

    def __filter_user_default(self, action, model):
        for ir_filter in model.env['ir.filters'].get_filters(model._name, action._origin.id):
            if ir_filter['is_default']:
                return ir_filter['domain']
        return None

    def __filter_from_context(self, context, action, model):
        view = None
        for key, value in context.items():
            if key.startswith("search_default_") and value:
                filter_name = key[15:]
                if not regex_object_name.match(filter_name):
                    raise ValueError(model.env._("Invalid default search filter name for %s", key))
                if view is None:
                    view = model.get_view(action.search_view_id.id, 'search')
                    view_tree = etree.fromstring(view['arch'])
                if (element := view_tree.find(rf".//filter[@name='{filter_name}']")) is not None:
                    # parse the domain
                    if domain := element.attrib.get("domain"):
                        yield domain
                    # not parsing context['group_by']

    def __get_start_date_end_date(self, kwargs):
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        if not (start_date and end_date):
            return None, None
        return date.fromisoformat(start_date), date.fromisoformat(end_date)
