# Part of Odoo. See LICENSE file for full copyright and licensing details.
import html
from base64 import b64encode
from datetime import date

from odoo.api import Environment
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tools import file_open

from .test_common import TestHttpBase

CT_HTML = 'text/html; charset=utf-8'


@tagged('-at_install', 'post_install')
class TestHttpWebJson1(TestHttpBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.milky_way = cls.env.ref('test_http.milky_way')
        cls.earth = cls.env.ref('test_http.earth')
        with file_open('test_http/static/src/img/gizeh.png', 'rb') as file:
            cls.gizeh_data = file.read()
            cls.gizeh_b64 = b64encode(cls.gizeh_data).decode()

    def url_open_json(self, url, *, expected_code=0):
        url = f"/json/1/{url.lstrip('/')}"
        res = self.url_open(url)
        if expected_code is None:
            pass
        elif expected_code:
            self.assertEqual(res.status_code, expected_code)
        else:
            # expected=0, raise for status
            res.raise_for_status()
        return res

    def action_crm(self):
        action_crm = self.env['ir.actions.server'].search([('path', '=', 'crm')])
        if not action_crm:
            self.skipTest("crm is not installed")
        return action_crm

    def authenticate_demo(self):
        self.authenticate('demo', 'demo')
        user = self.user_demo
        return Environment(self.env.cr, user.id, {'lang': user.lang, 'tz': user.tz})

    @staticmethod
    def _read_group_list(model, domain=None, groupby=(), fields=('__count',)):
        result = model.web_read_group(domain or [], groupby=groupby, fields=fields, lazy=False)
        # transform tuples into list and pop '__domain'
        for group in result['groups']:
            del group['__domain']
            for k, v in group.items():
                if isinstance(v, tuple):
                    group[k] = list(v)
        return result

    def test_webjson_access_error(self):
        self.authenticate_demo()
        with self.assertLogs('odoo.http', 'WARNING') as capture:
            res = self.url_open_json('/settings', expected_code=403)
            self.assertEqual(res.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertIn("You are not allowed to access", res.text)
        self.assertEqual(len(capture.output), 1)
        self.assertIn("You are not allowed to access", capture.output[0])

    def test_webjson_access_error_crm(self):
        action_crm = self.action_crm()
        self.authenticate_demo()
        self.url_open_json('/crm')

        self.env['ir.model.access'].search([
            ('model_id', '=', action_crm.model_id.id)
        ]).perm_read = False

        with self.assertLogs('odoo.http', 'WARNING') as capture:
            res = self.url_open_json('/crm', expected_code=403)
            self.assertEqual(res.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertIn("You are not allowed to access", res.text)
        self.assertEqual(len(capture.output), 1)
        self.assertIn("You are not allowed to access", capture.output[0])

    def test_webjson_access_export(self):
        # a simple call
        url = f'/test_http.stargate/{self.earth.id}'
        self.authenticate_demo()
        res = self.url_open_json(url)

        # remove export permssion
        group_export = self.env.ref('base.group_allow_export')
        self.user_demo.write({'groups_id': [Command.unlink(group_export.id)]})

        # check that demo has no access to /json
        with self.assertLogs('odoo.http', 'WARNING') as capture:
            res = self.url_open_json(url, expected_code=403)
            self.assertIn("need export permissions", res.text)
            self.assertIn("need export permissions", capture.output[0])

    def test_webjson_bad_stuff(self):
        self.authenticate_demo()

        with self.subTest(bad='action'):
            res = self.url_open_json('/idontexist', expected_code=400)
            self.assertEqual(res.headers['Content-Type'], CT_HTML)
            self.assertIn(
                "expected action at word 1 but found “idontexist”", res.text)

        with self.subTest(bad='active_id'):
            res = self.url_open_json('/5/test_http.stargate', expected_code=400)
            self.assertEqual(res.headers['Content-Type'], CT_HTML)
            self.assertIn("expected action at word 1 but found “5”", res.text)

        with self.subTest(bad='record_id'):
            res = self.url_open_json('/test_http.stargate/1/2', expected_code=400)
            self.assertEqual(res.headers['Content-Type'], CT_HTML)
            self.assertIn("expected action at word 3 but found “2”", res.text)

        with self.subTest(bad='view_type'):
            error = "Invalid view type"
            res = self.url_open_json('/res.users?view_type=idontexist', expected_code=400)
            self.assertEqual(res.headers['Content-Type'], CT_HTML)
            self.assertIn(error, html.unescape(res.text))

    def test_webjson_form(self):
        self.authenticate_demo()
        res = self.url_open_json(f'/test_http.stargate/{self.earth.id}')
        self.assertEqual(res.json(), {
            'id': self.earth.id,
            'name': self.earth.name,
            'sgc_designation': self.earth.sgc_designation,
            'galaxy_id': {'id': self.earth.galaxy_id.id,
                          'display_name': self.earth.galaxy_id.name},
            'glyph_attach': self.gizeh_b64,
            'glyph_inline': self.gizeh_b64,
        })

    def test_webjson_form_subtree(self):
        env = self.authenticate_demo()
        res = self.url_open_json(f'/test_http.galaxy/{self.milky_way.id}')
        self.assertEqual(
            res.json(),
            self.milky_way.with_env(env).web_read({
                'name': {},
                'stargate_ids': {'fields': {
                    'name': {},
                    'sgc_designation': {}
                }},
            })[0],
        )

    def test_webjson_form_viewtype_list(self):
        self.authenticate_demo()
        url = f'/test_http.stargate/{self.earth.id}'
        res = self.url_open_json(f'{url}?view_type=list')
        self.assertEqual(res.json(), {
            'id': self.earth.id,
            'name': self.earth.name,
            'sgc_designation': self.earth.sgc_designation,
        })

    def test_webjson_list(self):
        env = self.authenticate_demo()
        res = self.url_open_json('/test_http.stargate')
        self.assertEqual(
            res.json(),
            env['test_http.stargate']
                .web_search_read([], {'name': {}, 'sgc_designation': {}})
        )

    def test_webjson_list_limit_offset(self):
        env = self.authenticate_demo()
        url = '/test_http.stargate'
        stargates = (
            env['test_http.stargate']
                .web_search_read([], {'name': {}, 'sgc_designation': {}})
        )['records']

        res_limit = self.url_open_json(f'{url}?limit=1')
        self.assertEqual(res_limit.json(), {
            'length': len(stargates),
            'records': stargates[:1]
        })

        res_offset = self.url_open_json(f'{url}?offset=1')
        self.assertEqual(res_offset.json(), {
            'length': len(stargates),
            'records': stargates[1:]
        })

        res_limit_offset = self.url_open_json(f'{url}?limit=1&offset=1')
        self.assertEqual(res_limit_offset.json(), {
            'length': len(stargates),
            'records': stargates[1:2]
        })

    def test_webjson_list_domain(self):
        env = self.authenticate_demo()
        domain = [("address", "like", "gs38")]
        res = self.url_open_json(f'/test_http.stargate?domain={domain}')
        self.assertEqual(
            res.json(),
            env['test_http.stargate']
                .web_search_read(domain, {'name': {}, 'sgc_designation': {}})
        )

    def test_webjson_list_args(self):
        env = self.authenticate_demo()
        # create a default filter
        domain = [("name", "ilike", "earth")]
        self.env['ir.filters'].create({
            'name': 'my filter',
            'is_default': True,
            'domain': domain,
            'model_id': 'test_http.stargate',
        })
        res = self.url_open_json('/test_http.stargate')
        self.assertEqual(
            res.json(),
            env['test_http.stargate']
                .web_search_read(domain, {'name': {}, 'sgc_designation': {}})
        )
        # we should find one redirect with the domain in the URL
        [hist] = res.history
        self.assertEqual(hist.status_code, 307)
        str_domain = str(domain).replace(' ', '+')
        self.assertIn("limit=80", res.url)
        self.assertIn(f"domain={str_domain}", res.url)

    def test_webjson_pivot(self):
        env = self.authenticate_demo()
        res = self.url_open_json('/test_http.stargate?view_type=pivot')
        self.assertEqual(
            res.json(),
            self._read_group_list(
                env['test_http.stargate'], [], ['galaxy_id', 'has_galaxy_crystal'], ['availability']),
        )

        res = self.url_open_json('/test_http.stargate?view_type=pivot&groupby=has_galaxy_crystal&fields=availability:min')
        self.assertEqual(
            res.json(),
            self._read_group_list(env['test_http.stargate'], [], ['has_galaxy_crystal'], ['availability:min']),
        )

    def test_webjson_graph(self):
        env = self.authenticate_demo()
        res = self.url_open_json('/test_http.stargate?view_type=graph')
        self.assertEqual(
            res.json(),
            self._read_group_list(env['test_http.stargate'], [], ['galaxy_id']),
        )

    def test_webjson_crm_default_filter(self):
        self.action_crm()
        env = self.authenticate_demo()
        res = self.url_open_json('/crm')
        self.assertEqual(
            res.json()["length"],
            env['crm.lead'].search_count([('type', '=', 'opportunity'), ('user_id', '=', env.uid)]),
        )
        self.assertIn(f"+{env.uid})", res.url, "URL should contain a domain with user id")
        self.assertNotIn("opportunity", res.url, "URL should not contain a domain with action domain")

    def test_webjson_crm_activity(self):
        self.action_crm()
        self.authenticate_demo()
        res = self.url_open_json('/crm?view_type=activity')
        # check that we have at least the following fields
        expected_fields = ["activity_ids", "activity_summary", "activity_user_id", "name"]
        self.assertEqual(
            sorted(field_name for field_name in res.json()["records"][0] if field_name in expected_fields),
            expected_fields,
        )

    def test_webjson_crm_calendar(self):
        self.action_crm()
        env = self.authenticate_demo()
        today = date.today()
        start_date_iso = today.replace(day=1).isoformat()
        # check that we have the date in the URL
        res = self.url_open_json('/crm?view_type=calendar')
        self.assertIn(f"start_date={start_date_iso}", res.url)
        # check that we can filter using the date
        last_deadline = max(
            env['crm.lead'].search([('type', '=', 'opportunity'), ('activity_date_deadline', '!=', False)])
            .mapped('activity_date_deadline')
        )
        res = self.url_open_json(f'/crm?view_type=calendar&domain=[]&start_date={last_deadline.isoformat()}&end_date=2099-01-01')
        self.assertEqual(
            res.json()["length"],
            env['crm.lead'].search_count([('type', '=', 'opportunity'), ('activity_date_deadline', '>=', last_deadline)]),
        )

    def test_webjson_crm_pivot(self):
        self.action_crm()
        env = self.authenticate_demo()
        res = self.url_open_json('/crm?view_type=pivot&domain=[]')
        self.assertIn('groupby=', res.url)
        self.assertIn('fields=expected_revenue', res.url)
        self.assertEqual(
            res.json(),
            self._read_group_list(env['crm.lead'], [('type', '=', 'opportunity')], ['create_date', 'stage_id'], ['expected_revenue']),
        )
