# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, Command
from odoo.tests import Form, HttpCase, new_test_user
from odoo.tools.float_utils import float_round

from odoo.addons.product.tests.common import ProductCommon

import json
import base64
from contextlib import contextmanager
from functools import wraps
from lxml import etree
from unittest import SkipTest
from unittest.mock import patch


class AccountTestInvoicingCommon(ProductCommon):
    # to override by the helper methods setup_country and setup_chart_template to adapt to a localization
    chart_template = False
    country_code = False

    @classmethod
    def safe_copy(cls, record):
        return record and record.copy()

    @staticmethod
    def setup_country(country_code):

        def _decorator(function):
            @wraps(function)
            def wrapper(self):
                self.country_code = country_code.upper()
                function(self)
            return wrapper

        return _decorator

    @staticmethod
    def setup_chart_template(chart_template):
        def _decorator(function):
            @wraps(function)
            def wrapper(self):
                self.chart_template = chart_template
                function(self)
            return wrapper

        return _decorator

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data = cls.collect_company_accounting_data(cls.env.company)

        # ==== Taxes ====
        cls.tax_sale_a = cls.company_data['default_tax_sale']
        cls.tax_sale_b = cls.company_data['default_tax_sale'] and cls.company_data['default_tax_sale'].copy()
        cls.tax_purchase_a = cls.company_data['default_tax_purchase']
        cls.tax_purchase_b = cls.company_data['default_tax_purchase'] and cls.company_data['default_tax_purchase'].copy()
        cls.tax_armageddon = cls.setup_armageddon_tax('complex_tax', cls.company_data)

        # ==== Products ====
        cls.product_a = cls._create_product(
            name='product_a',
            lst_price=1000.0,
            standard_price=800.0
        )
        cls.product_b = cls._create_product(
            name='product_b',
            uom_id=cls.uom_dozen.id,
            lst_price=200.0,
            standard_price=160.0,
            property_account_income_id=cls.copy_account(cls.company_data['default_account_revenue']).id,
            property_account_expense_id=cls.copy_account(cls.company_data['default_account_expense']).id,
            taxes_id=[Command.set((cls.tax_sale_a + cls.tax_sale_b).ids)],
            supplier_taxes_id=[Command.set((cls.tax_purchase_a + cls.tax_purchase_b).ids)],
        )

        # ==== Fiscal positions ====
        cls.fiscal_pos_a = cls.env['account.fiscal.position'].create({
            'name': 'fiscal_pos_a',
            'tax_ids': ([(0, None, {
                    'tax_src_id': cls.tax_sale_a.id,
                    'tax_dest_id': cls.tax_sale_b.id,
            })] if cls.tax_sale_b else []) + ([(0, None, {
                    'tax_src_id': cls.tax_purchase_a.id,
                    'tax_dest_id': cls.tax_purchase_b.id,
            })] if cls.tax_purchase_b else []),
            'account_ids': [
                (0, None, {
                    'account_src_id': cls.product_a.property_account_income_id.id,
                    'account_dest_id': cls.product_b.property_account_income_id.id,
                }),
                (0, None, {
                    'account_src_id': cls.product_a.property_account_expense_id.id,
                    'account_dest_id': cls.product_b.property_account_expense_id.id,
                }),
            ],
        })

        # ==== Payment terms ====
        cls.pay_terms_a = cls.env.ref('account.account_payment_term_immediate')
        cls.pay_terms_b = cls.env['account.payment.term'].create({
            'name': '30% Advance End of Following Month',
            'note': 'Payment terms: 30% Advance End of Following Month',
            'line_ids': [
                (0, 0, {
                    'value': 'percent',
                    'value_amount': 30.0,
                    'nb_days': 0,
                }),
                (0, 0, {
                    'value': 'percent',
                    'value_amount': 70.0,
                    'delay_type': 'days_after_end_of_next_month',
                    'nb_days': 0,
                }),
            ],
        })

        # ==== Partners ====
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'partner_a',
            'property_payment_term_id': cls.pay_terms_a.id,
            'property_supplier_payment_term_id': cls.pay_terms_a.id,
            'property_account_receivable_id': cls.company_data['default_account_receivable'].id,
            'property_account_payable_id': cls.company_data['default_account_payable'].id,
            'company_id': False,
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'partner_b',
            'property_payment_term_id': cls.pay_terms_b.id,
            'property_supplier_payment_term_id': cls.pay_terms_b.id,
            'property_account_position_id': cls.fiscal_pos_a.id,
            'property_account_receivable_id': cls.company_data['default_account_receivable'].copy().id,
            'property_account_payable_id': cls.company_data['default_account_payable'].copy().id,
            'company_id': False,
        })

        # ==== Cash rounding ====
        cls.cash_rounding_a = cls.env['account.cash.rounding'].create({
            'name': 'add_invoice_line',
            'rounding': 0.05,
            'strategy': 'add_invoice_line',
            'profit_account_id': cls.company_data['default_account_revenue'].copy().id,
            'loss_account_id': cls.company_data['default_account_expense'].copy().id,
            'rounding_method': 'UP',
        })
        cls.cash_rounding_b = cls.env['account.cash.rounding'].create({
            'name': 'biggest_tax',
            'rounding': 0.05,
            'strategy': 'biggest_tax',
            'rounding_method': 'DOWN',
        })

        # ==== Payment methods ====
        bank_journal = cls.company_data['default_journal_bank']
        cls.inbound_payment_method_line = bank_journal.inbound_payment_method_line_ids[0]
        cls.outbound_payment_method_line = bank_journal.outbound_payment_method_line_ids[0]

    @classmethod
    def change_company_country(cls, company, country):
        company.country_id = country
        company.account_fiscal_country_id = country
        for model in ('account.tax', 'account.tax.group'):
            cls.env.add_to_compute(
                cls.env[model]._fields['country_id'],
                cls.env[model].search([('company_id', '=', company.id)]),
            )

    @classmethod
    def setup_other_company(cls, **kwargs):
        # OVERRIDE
        company = cls._create_company(**{'name': 'company_2'} | kwargs)
        return cls.collect_company_accounting_data(company)

    @classmethod
    def setup_independent_company(cls, **kwargs):
        return cls._create_company(name='company_1_data', **kwargs)

    @classmethod
    def setup_independent_user(cls):
        return new_test_user(
            cls.env,
            name='Because I am accountman!',
            login='accountman',
            password='accountman',
            email='accountman@test.com',
            groups_id=cls.get_default_groups().ids,
            company_id=cls.env.company.id,
        )

    @classmethod
    def _create_company(cls, **create_values):
        if cls.country_code:
            country = cls.env['res.country'].search([('code', '=', cls.country_code.upper())])
            if not country:
                raise ValueError('Invalid country code')
            if 'country_id' not in create_values:
                create_values['country_id'] = country.id
            if 'currency_id' not in create_values:
                create_values['currency_id'] = country.currency_id.id
        company = super()._create_company(**create_values)
        cls._use_chart_template(company, cls.chart_template)
        # if the currency_id was defined explicitly (or via the country), it should override the one from the coa
        if create_values.get('currency_id'):
            company.currency_id = create_values['currency_id']
        return company

    @classmethod
    def _create_product(cls, **create_values):
        # OVERRIDE
        create_values.setdefault('property_account_income_id', cls.company_data['default_account_revenue'].id)
        create_values.setdefault('property_account_expense_id', cls.company_data['default_account_expense'].id)
        create_values.setdefault('taxes_id', [Command.set(cls.tax_sale_a.ids)])
        return super()._create_product(**create_values)

    @classmethod
    def get_default_groups(cls):
        groups = super().get_default_groups()
        return groups | cls.env.ref('account.group_account_manager') | cls.env.ref('account.group_account_user')

    @classmethod
    def setup_other_currency(cls, code, **kwargs):
        if 'rates' not in kwargs:
            return super().setup_other_currency(code, rates=[('2016-01-01', 3.0), ('2017-01-01', 2.0)], **kwargs)
        return super().setup_other_currency(code, **kwargs)

    @classmethod
    def _use_chart_template(cls, company, chart_template_ref=None):
        chart_template_ref = chart_template_ref or cls.env['account.chart.template']._guess_chart_template(company.country_id)
        template_vals = cls.env['account.chart.template']._get_chart_template_mapping()[chart_template_ref]
        template_module = cls.env['ir.module.module']._get(template_vals['module'])
        if template_module.state != 'installed':
            raise SkipTest(f"Module required for the test is not installed ({template_module.name})")

        # Install the chart template
        cls.env['account.chart.template'].try_loading(chart_template_ref, company=company, install_demo=False)
        if not company.account_fiscal_country_id:
            company.account_fiscal_country_id = cls.env.ref('base.us')

    @classmethod
    def collect_company_accounting_data(cls, company):
        return {
            'company': company,
            'currency': company.currency_id,
            'default_account_revenue': cls.env['account.account'].search([
                    ('company_id', '=', company.id),
                    ('account_type', '=', 'income'),
                    ('id', '!=', company.account_journal_early_pay_discount_gain_account_id.id)
                ], limit=1),
            'default_account_expense': cls.env['account.account'].search([
                    ('company_id', '=', company.id),
                    ('account_type', '=', 'expense'),
                    ('id', '!=', company.account_journal_early_pay_discount_loss_account_id.id)
                ], limit=1),
            'default_account_receivable': cls.env['ir.property'].with_company(company)._get(
                'property_account_receivable_id', 'res.partner'
            ),
            'default_account_payable': cls.env['account.account'].search([
                    ('company_id', '=', company.id),
                    ('account_type', '=', 'liability_payable')
                ], limit=1),
            'default_account_assets': cls.env['account.account'].search([
                    ('company_id', '=', company.id),
                    ('account_type', '=', 'asset_fixed')
                ], limit=1),
            'default_account_deferred_expense': cls.env['account.account'].search([
                    ('company_id', '=', company.id),
                    ('account_type', '=', 'asset_current')
                ], limit=1),
            'default_account_deferred_revenue': cls.env['account.account'].search([
                    ('company_id', '=', company.id),
                    ('account_type', '=', 'liability_current')
                ], limit=1),
            'default_account_tax_sale': company.account_sale_tax_id.mapped('invoice_repartition_line_ids.account_id'),
            'default_account_tax_purchase': company.account_purchase_tax_id.mapped('invoice_repartition_line_ids.account_id'),
            'default_journal_misc': cls.env['account.journal'].search([
                    ('company_id', '=', company.id),
                    ('type', '=', 'general')
                ], limit=1),
            'default_journal_sale': cls.env['account.journal'].search([
                    ('company_id', '=', company.id),
                    ('type', '=', 'sale')
                ], limit=1),
            'default_journal_purchase': cls.env['account.journal'].search([
                    ('company_id', '=', company.id),
                    ('type', '=', 'purchase')
                ], limit=1),
            'default_journal_bank': cls.env['account.journal'].search([
                    ('company_id', '=', company.id),
                    ('type', '=', 'bank')
                ], limit=1),
            'default_journal_cash': cls.env['account.journal'].search([
                    ('company_id', '=', company.id),
                    ('type', '=', 'cash')
                ], limit=1),
            'default_tax_sale': company.account_sale_tax_id,
            'default_tax_purchase': company.account_purchase_tax_id,
        }

    @classmethod
    def copy_account(cls, account, default=None):
        suffix_nb = 1
        while True:
            new_code = '%s.%s' % (account.code, suffix_nb)
            if account.search_count([('company_id', '=', account.company_id.id), ('code', '=', new_code)]):
                suffix_nb += 1
            else:
                return account.copy(default={'code': new_code, 'name': account.name, **(default or {})})

    @classmethod
    def setup_armageddon_tax(cls, tax_name, company_data, **kwargs):
        type_tax_use = kwargs.get('type_tax_use', 'sale')
        cash_basis_transition_account = company_data['default_account_tax_sale'] and company_data['default_account_tax_sale'].copy()
        return cls.env['account.tax'].create({
            'name': '%s (group)' % tax_name,
            'amount_type': 'group',
            'amount': 0.0,
            'country_id': company_data['company'].account_fiscal_country_id.id,
            'children_tax_ids': [
                (0, 0, {
                    'name': '%s (child 1)' % tax_name,
                    'amount_type': 'percent',
                    'amount': 20.0,
                    'type_tax_use': type_tax_use,
                    'country_id': company_data['company'].account_fiscal_country_id.id,
                    'price_include': True,
                    'include_base_amount': True,
                    'tax_exigibility': 'on_invoice',
                    'invoice_repartition_line_ids': [
                        (0, 0, {
                            'repartition_type': 'base',
                        }),
                        (0, 0, {
                            'factor_percent': 40,
                            'repartition_type': 'tax',
                            'account_id': company_data['default_account_tax_sale'].id,
                        }),
                        (0, 0, {
                            'factor_percent': 60,
                            'repartition_type': 'tax',
                            # /!\ No account set.
                        }),
                    ],
                    'refund_repartition_line_ids': [
                        (0, 0, {
                            'repartition_type': 'base',
                        }),
                        (0, 0, {
                            'factor_percent': 40,
                            'repartition_type': 'tax',
                            'account_id': company_data['default_account_tax_sale'].id,
                        }),
                        (0, 0, {
                            'factor_percent': 60,
                            'repartition_type': 'tax',
                            # /!\ No account set.
                        }),
                    ],
                }),
                (0, 0, {
                    'name': '%s (child 2)' % tax_name,
                    'amount_type': 'percent',
                    'amount': 10.0,
                    'type_tax_use': type_tax_use,
                    'country_id': company_data['company'].account_fiscal_country_id.id,
                    'tax_exigibility': 'on_payment',
                    'cash_basis_transition_account_id': cash_basis_transition_account.id,
                    'invoice_repartition_line_ids': [
                        (0, 0, {
                            'repartition_type': 'base',
                        }),
                        (0, 0, {
                            'repartition_type': 'tax',
                            'account_id': company_data['default_account_tax_sale'].id,
                        }),
                    ],
                    'refund_repartition_line_ids': [
                        (0, 0, {
                            'repartition_type': 'base',
                        }),

                        (0, 0, {
                            'repartition_type': 'tax',
                            'account_id': company_data['default_account_tax_sale'].id,
                        }),
                    ],
                }),
            ],
            **kwargs,
        })

    @classmethod
    def init_invoice(cls, move_type, partner=None, invoice_date=None, post=False, products=None, amounts=None, taxes=None, company=False, currency=None):
        products = [] if products is None else products
        amounts = [] if amounts is None else amounts
        move_form = Form(cls.env['account.move'] \
                    .with_company(company or cls.env.company) \
                    .with_context(default_move_type=move_type))
        move_form.invoice_date = invoice_date or fields.Date.from_string('2019-01-01')
        # According to the state or type of the invoice, the date field is sometimes visible or not
        # Besides, the date field can be put multiple times in the view
        # "invisible": "['|', ('state', '!=', 'draft'), ('auto_post', '!=', 'at_date')]"
        # "invisible": ['|', '|', ('state', '!=', 'draft'), ('auto_post', '=', 'no'), ('auto_post', '=', 'at_date')]
        # "invisible": "['&', ('move_type', 'in', ['out_invoice', 'out_refund', 'out_receipt']), ('quick_edit_mode', '=', False)]"
        # :TestAccountMoveOutInvoiceOnchanges, :TestAccountMoveOutRefundOnchanges, .test_00_debit_note_out_invoice, :TestAccountEdi
        if not move_form._get_modifier('date', 'invisible'):
            move_form.date = move_form.invoice_date
        move_form.partner_id = partner or cls.partner_a
        if currency:
            move_form.currency_id = currency

        for product in (products or []):
            with move_form.invoice_line_ids.new() as line_form:
                line_form.product_id = product
                if taxes is not None:
                    line_form.tax_ids.clear()
                    for tax in taxes:
                        line_form.tax_ids.add(tax)

        for amount in (amounts or []):
            with move_form.invoice_line_ids.new() as line_form:
                line_form.name = "test line"
                line_form.price_unit = amount
                if taxes is not None:
                    line_form.tax_ids.clear()
                    for tax in taxes:
                        line_form.tax_ids.add(tax)

        rslt = move_form.save()

        if post:
            rslt.action_post()

        return rslt

    def create_line_for_reconciliation(self, balance, amount_currency, currency, move_date, account_1=None, partner=None):
        write_off_account_to_be_reconciled = account_1 if account_1 else self.receivable_account
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': move_date,
            'line_ids': [
                Command.create({
                    'debit': balance if balance > 0.0 else 0.0,
                    'credit': -balance if balance < 0.0 else 0.0,
                    'amount_currency': amount_currency,
                    'account_id': write_off_account_to_be_reconciled.id,
                    'currency_id': currency.id,
                    'partner_id': partner.id if partner else None,
                }),
                Command.create({
                    'debit': -balance if balance < 0.0 else 0.0,
                    'credit': balance if balance > 0.0 else 0.0,
                    'amount_currency': -amount_currency,
                    'account_id': self.company_data['default_account_revenue'].id,
                    'currency_id': currency.id,
                    'partner_id': partner.id if partner else None,
                }),
            ],
        })
        move.action_post()
        line = move.line_ids.filtered(lambda x: x.account_id == write_off_account_to_be_reconciled)

        self.assertRecordValues(line, [{
            'amount_residual': balance,
            'amount_residual_currency': amount_currency,
            'reconciled': False,
        }])

        return line

    def assertInvoiceValues(self, move, expected_lines_values, expected_move_values):
        def sort_lines(lines):
            return lines.sorted(lambda line: (line.sequence, not bool(line.tax_line_id), line.name or line.product_id.display_name or '', line.balance))
        self.assertRecordValues(sort_lines(move.line_ids.sorted()), expected_lines_values)
        self.assertRecordValues(move, [expected_move_values])

    def assert_invoice_outstanding_to_reconcile_widget(self, invoice, expected_amounts):
        """ Check the outstanding widget before the reconciliation.
        :param invoice:             An invoice.
        :param expected_amounts:    A map <move_id> -> <amount>
        """
        invoice.invalidate_recordset(['invoice_outstanding_credits_debits_widget'])
        widget_vals = invoice.invoice_outstanding_credits_debits_widget

        if widget_vals:
            current_amounts = {vals['move_id']: vals['amount'] for vals in widget_vals['content']}
        else:
            current_amounts = {}
        self.assertDictEqual(current_amounts, expected_amounts)

    def assert_invoice_outstanding_reconciled_widget(self, invoice, expected_amounts):
        """ Check the outstanding widget after the reconciliation.
        :param invoice:             An invoice.
        :param expected_amounts:    A map <move_id> -> <amount>
        """
        invoice.invalidate_recordset(['invoice_payments_widget'])
        widget_vals = invoice.invoice_payments_widget

        if widget_vals:
            current_amounts = {vals['move_id']: vals['amount'] for vals in widget_vals['content']}
        else:
            current_amounts = {}
        self.assertDictEqual(current_amounts, expected_amounts)

    ####################################################
    # Xml Comparison
    ####################################################

    def _turn_node_as_dict_hierarchy(self, node, path=''):
        ''' Turn the node as a python dictionary to be compared later with another one.
        Allow to ignore the management of namespaces.
        :param node:    A node inside an xml tree.
        :param path:    The optional path of tags for recursive call.
        :return:        A python dictionary.
        '''
        tag_split = node.tag.split('}')
        tag_wo_ns = tag_split[-1]
        attrib_wo_ns = {k: v for k, v in node.attrib.items() if '}' not in k}
        full_path = f'{path}/{tag_wo_ns}'
        return {
            'tag': tag_wo_ns,
            'full_path': full_path,
            'namespace': None if len(tag_split) < 2 else tag_split[0],
            'text': (node.text or '').strip(),
            'attrib': attrib_wo_ns,
            'children': [
                self._turn_node_as_dict_hierarchy(child_node, path=path)
                for child_node in node.getchildren()
            ],
        }

    def assertXmlTreeEqual(self, xml_tree, expected_xml_tree):
        ''' Compare two lxml.etree.
        :param xml_tree:            The current tree.
        :param expected_xml_tree:   The expected tree.
        '''

        def assertNodeDictEqual(node_dict, expected_node_dict):
            ''' Compare nodes created by the `_turn_node_as_dict_hierarchy` method.
            :param node_dict:           The node to compare with.
            :param expected_node_dict:  The expected node.
            '''
            if expected_node_dict['text'] == '___ignore___':
                return
            # Check tag.
            self.assertEqual(node_dict['tag'], expected_node_dict['tag'])

            # Check attributes.
            for k, v in expected_node_dict['attrib'].items():
                if v == '___ignore___':
                    node_dict['attrib'][k] = '___ignore___'

            self.assertDictEqual(
                node_dict['attrib'],
                expected_node_dict['attrib'],
                f"Element attributes are different for node {node_dict['full_path']}",
            )

            # Check text.
            if expected_node_dict['text'] != '___ignore___':
                self.assertEqual(
                    node_dict['text'],
                    expected_node_dict['text'],
                    f"Element text are different for node {node_dict['full_path']}",
                )

            # Check children.
            self.assertEqual(
                [child['tag'] for child in node_dict['children']],
                [child['tag'] for child in expected_node_dict['children']],
                f"Number of children elements for node {node_dict['full_path']} is different.",
            )

            for child_node_dict, expected_child_node_dict in zip(node_dict['children'], expected_node_dict['children']):
                assertNodeDictEqual(child_node_dict, expected_child_node_dict)

        assertNodeDictEqual(
            self._turn_node_as_dict_hierarchy(xml_tree),
            self._turn_node_as_dict_hierarchy(expected_xml_tree),
        )

    def with_applied_xpath(self, xml_tree, xpath):
        ''' Applies the xpath to the xml_tree passed as parameter.
        :param xml_tree:    An instance of etree.
        :param xpath:       The xpath to apply as a string.
        :return:            The resulting etree after applying the xpaths.
        '''
        diff_xml_tree = etree.fromstring('<data>%s</data>' % xpath)
        return self.env['ir.ui.view'].apply_inheritance_specs(xml_tree, diff_xml_tree)

    def get_xml_tree_from_attachment(self, attachment):
        ''' Extract an instance of etree from an ir.attachment.
        :param attachment:  An ir.attachment.
        :return:            An instance of etree.
        '''
        return etree.fromstring(base64.b64decode(attachment.with_context(bin_size=False).datas))

    def get_xml_tree_from_string(self, xml_tree_str):
        ''' Convert the string passed as parameter to an instance of etree.
        :param xml_tree_str:    A string representing an xml.
        :return:                An instance of etree.
        '''
        return etree.fromstring(xml_tree_str)

    @contextmanager
    def enter_test_mode(self):
        """
        Make so that all new cursors opened on this database registry
        reuse the one currently used by the test.

        Useful for printing PDFs inside a TransactionCase test when
        using a HttpCase is not possible/desirable.
        """
        self.env.registry.enter_test_mode(self.env.cr)
        try:
            yield
        finally:
            self.env.registry.leave_test_mode()


class AccountTestMockOnlineSyncCommon(HttpCase):
    def start_tour(self, url_path, tour_name, step_delay=None, **kwargs):
        with self.mock_online_sync_favorite_institutions():
            super().start_tour(url_path, tour_name, step_delay, **kwargs)

    @classmethod
    @contextmanager
    def mock_online_sync_favorite_institutions(cls):
        def get_institutions(*args, **kwargs):
            return [
                {
                    'country': 'US',
                    'id': 3245,
                    'name': 'BMO Business Banking',
                    'picture': '/base/static/img/logo_white.png',
                },
                {
                    'country': 'US',
                    'id': 8192,
                    'name': 'Banc of California',
                    'picture': '/base/static/img/logo_white.png'
                },
            ]
        with patch.object(
             target=cls.registry['account.journal'],
             attribute='fetch_online_sync_favorite_institutions',
             new=get_institutions,
             create=True):
            yield


class AccountTestInvoicingHttpCommon(AccountTestInvoicingCommon, AccountTestMockOnlineSyncCommon):
    pass


class TestTaxCommon(AccountTestInvoicingHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.number = 0
        cls.maxDiff = None

    def setUp(self):
        super().setUp()
        self.js_tests = []

    def new_currency(self, rounding):
        self.number += 1
        return self.env.company.currency_id.copy({
            'name': f"{self.number}",
            'rounding': rounding,
        })

    def group_of_taxes(self, taxes, **kwargs):
        self.number += 1
        return self.env['account.tax'].create({
            **kwargs,
            'name': f"group_({self.number})",
            'amount_type': 'group',
            'children_tax_ids': [Command.set(taxes.ids)],
        })

    def percent_tax(self, amount, **kwargs):
        self.number += 1
        return self.env['account.tax'].create({
            **kwargs,
            'name': f"percent_{amount}_({self.number})",
            'amount_type': 'percent',
            'amount': amount,
        })

    def division_tax(self, amount, **kwargs):
        self.number += 1
        return self.env['account.tax'].create({
            **kwargs,
            'name': f"division_{amount}_({self.number})",
            'amount_type': 'division',
            'amount': amount,
        })

    def fixed_tax(self, amount, **kwargs):
        self.number += 1
        return self.env['account.tax'].create({
            **kwargs,
            'name': f"fixed_{amount}_({self.number})",
            'amount_type': 'fixed',
            'amount': amount,
        })

    def init_document(self, lines, currency=None, rate=None):
        return {
            'currency_id': currency or self.env.company.currency_id,
            'rate': rate if rate is not None else 1.0,
            'line_ids': lines,
        }

    def populate_document(self, document):
        AccountTax = self.env['account.tax']
        base_lines = []
        for i, line in enumerate(document['line_ids']):
            base_line = AccountTax._prepare_base_line_for_taxes_computation(
                None,
                id=i,
                currency_id=line['currency_id'] if 'currency_id' in line else document['currency_id'],
                quantity=1.0,
                rate=line['rate'] if 'rate' in line else document['rate'],
                **line,
            )
            AccountTax._add_base_line_tax_details(base_line, self.env.company)
            base_lines.append(base_line)
        return {
            **document,
            'line_ids': base_lines,
        }

    def _jsonify_currency(self, currency):
        if not currency:
            return None
        return {
            'id': currency.id,
            'rounding': currency.rounding,
        }

    def _jsonify_product(self, product, taxes):
        return taxes._eval_taxes_computation_turn_to_product_values(product=product)

    def _jsonify_tax(self, tax):
        return {
            'id': tax.id,
            'name': tax.name,
            'amount_type': tax.amount_type,
            'sequence': tax.sequence,
            'amount': tax.amount,
            'price_include': tax.price_include,
            'include_base_amount': tax.include_base_amount,
            'is_base_affected': tax.is_base_affected,
            'total_tax_factor': tax.total_tax_factor,
            'children_tax_ids': [self._jsonify_tax(child) for child in tax.children_tax_ids],
        }

    def _jsonify_partner(self, partner):
        if not partner:
            return None
        return {
            'id': partner.id,
        }

    def _jsonify_base_line(self, base_line):
        return {
            **base_line,
            'product_id': self._jsonify_product(base_line['product_id'], base_line['tax_ids']),
            'tax_ids': [self._jsonify_tax(tax) for tax in base_line['tax_ids']],
            'currency_id': self._jsonify_currency(base_line['currency_id']),
            'partner_id': self._jsonify_partner(base_line['partner_id']),
        }

    def _jsonify_document(self, document):
        return {
            **document,
            'currency_id': self._jsonify_currency(document['currency_id']),
            'line_ids': [self._jsonify_base_line(base_line) for base_line in document['line_ids']],
        }

    def convert_document_to_invoice(self, document, cash_rounding=None):
        invoice_date = '2020-01-01'
        usd = self.setup_other_currency('EUR', rates=[(invoice_date, document['rate'])])
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': invoice_date,
            'currency_id': document['currency_id'].id,
            'invoice_cash_rounding_id': cash_rounding and cash_rounding.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': base_line['product_id'].id,
                    'price_unit': base_line['price_unit'],
                    'discount': base_line['discount'],
                    'quantity': base_line['quantity'],
                    'tax_ids': [Command.set(base_line['tax_ids'].ids)],
                })
                for base_line in document['line_ids']
            ],
        })
        usd.rate_ids.unlink()
        return invoice

    @contextmanager
    def with_tax_calculation_rounding_method(self, rounding_method):
        self.env.company.tax_calculation_rounding_method = rounding_method
        yield

    def _create_assert_test(
        self,
        expected_values,
        py_function,
        js_function,
        assert_function,
        *args,
        extra_function=None,
    ):
        if py_function:
            py_results = py_function(*args)
            if extra_function:
                extra_function(py_results)
            assert_function(py_results, expected_values)
        if js_function:
            js_test = js_function(*args)
            if extra_function:
                extra_function(js_test)
            self.js_tests.append((js_test, expected_values, assert_function))

    def _run_js_tests(self):
        if not self.js_tests:
            return

        self.env['ir.config_parameter'].set_param(
            'account.tests_shared_js_python',
            json.dumps([test for test, _expected_values, _assert_function in self.js_tests]),
        )

        self.start_tour('/account/init_tests_shared_js_python', 'tests_shared_js_python', login=self.env.user.login)
        results = json.loads(self.env['ir.config_parameter'].get_param('account.tests_shared_js_python', '[]'))

        self.assertEqual(len(results), len(self.js_tests))
        index = 1
        for (js_test, expected_values, assert_function), results in zip(self.js_tests, results):
            js_test.update(results)
            with self.subTest(test=js_test['test'], index=index):
                assert_function(js_test, expected_values)
            index += 1

    # -------------------------------------------------------------------------
    # taxes_computation
    # -------------------------------------------------------------------------

    def _assert_sub_test_taxes_computation(self, results, expected_values):

        def compare_taxes_computation_values(sub_results, rounding):
            self.assertEqual(
                float_round(sub_results['total_included'], precision_rounding=rounding),
                float_round(expected_values['total_included'], precision_rounding=rounding),
            )
            self.assertEqual(
                float_round(sub_results['total_excluded'], precision_rounding=rounding),
                float_round(expected_values['total_excluded'], precision_rounding=rounding),
            )
            self.assertEqual(len(sub_results['taxes_data']), len(expected_values['taxes_data']))
            for tax_data, (expected_base, expected_tax) in zip(sub_results['taxes_data'], expected_values['taxes_data']):
                self.assertEqual(
                    float_round(tax_data['base_amount'], precision_rounding=rounding),
                    float_round(expected_base, precision_rounding=rounding),
                )
                self.assertEqual(
                    float_round(tax_data['tax_amount'], precision_rounding=rounding),
                    float_round(expected_tax, precision_rounding=rounding),
                )

        is_round_globally = results['rounding_method'] == 'round_globally'
        excluded_special_modes = results['excluded_special_modes'] or []
        rounding = 0.000001 if is_round_globally else 0.01
        compare_taxes_computation_values(results['results'], rounding)

        # Check the special modes in case of round_globally.
        if is_round_globally:
            # special_mode == 'total_excluded'.
            if 'total_excluded' not in excluded_special_modes:
                compare_taxes_computation_values(results['total_excluded_results'], rounding)
                delta = sum(
                    x['tax_amount']
                    for x in results['total_excluded_results']['taxes_data']
                    if x['tax']['price_include']
                )

                self.assertEqual(
                    float_round(
                        (results['total_excluded_results']['total_excluded'] + delta) / results['quantity'],
                        precision_rounding=rounding,
                    ),
                    float_round(results['price_unit'], precision_rounding=rounding),
                )

            # special_mode == 'total_included'.
            if 'total_included' not in excluded_special_modes:
                compare_taxes_computation_values(results['total_included_results'], rounding)
                delta = sum(
                    x['tax_amount']
                    for x in results['total_included_results']['taxes_data']
                    if not x['tax']['price_include']
                )

                self.assertEqual(
                    float_round(
                        (results['total_included_results']['total_included'] - delta) / results['quantity'],
                        precision_rounding=rounding,
                    ),
                    float_round(results['price_unit'], precision_rounding=rounding),
                )

    def _create_py_sub_test_taxes_computation(self, taxes, price_unit, quantity, product, precision_rounding, rounding_method):
        kwargs = {
            'product': product,
            'precision_rounding': precision_rounding,
            'rounding_method': rounding_method,
        }
        results = {'results': taxes._evaluate_taxes_computation(price_unit, quantity, **kwargs)}
        if rounding_method == 'round_globally':
            results['total_excluded_results'] = taxes._evaluate_taxes_computation(
                price_unit=results['results']['total_excluded'] / quantity,
                quantity=quantity,
                special_mode='total_excluded',
                **kwargs,
            )
            results['total_included_results'] = taxes._evaluate_taxes_computation(
                price_unit=results['results']['total_included'] / quantity,
                quantity=quantity,
                special_mode='total_included',
                **kwargs,
            )
        return results

    def _create_js_sub_test_taxes_computation(self, taxes, price_unit, quantity, product, precision_rounding, rounding_method):
        return {
            'test': 'taxes_computation',
            'taxes': [self._jsonify_tax(tax) for tax in taxes],
            'price_unit': price_unit,
            'quantity': quantity,
            'product': self._jsonify_product(product, taxes),
            'precision_rounding': precision_rounding,
            'rounding_method': rounding_method,
        }

    def assert_taxes_computation(
        self,
        taxes,
        price_unit,
        expected_values,
        quantity=1,
        product=None,
        precision_rounding=0.01,
        rounding_method='round_per_line',
        excluded_special_modes=None,
    ):
        def extra_function(results):
            results['excluded_special_modes'] = excluded_special_modes
            results['rounding_method'] = rounding_method
            results['price_unit'] = price_unit
            results['quantity'] = quantity

        self._create_assert_test(
            expected_values,
            self._create_py_sub_test_taxes_computation,
            None,
            # self._create_js_sub_test_taxes_computation,
            self._assert_sub_test_taxes_computation,
            taxes,
            price_unit,
            quantity,
            product,
            precision_rounding,
            rounding_method,
            extra_function=extra_function,
        )

    # -------------------------------------------------------------------------
    # adapt_price_unit_to_another_taxes
    # -------------------------------------------------------------------------

    def _assert_sub_test_adapt_price_unit_to_another_taxes(self, results, expected_price_unit):
        self.assertEqual(results['price_unit'], expected_price_unit)

    def _create_py_sub_test_adapt_price_unit_to_another_taxes(self, price_unit, original_taxes, new_taxes, product):
        return {'price_unit': self.env['account.tax']._adapt_price_unit_to_another_taxes(price_unit, product, original_taxes, new_taxes)}

    def _create_js_sub_test_adapt_price_unit_to_another_taxes(self, price_unit, original_taxes, new_taxes, product):
        return {
            'test': 'adapt_price_unit_to_another_taxes',
            'price_unit': price_unit,
            'product': self._jsonify_product(product, original_taxes + new_taxes),
            'original_taxes': [self._jsonify_tax(tax) for tax in original_taxes],
            'new_taxes': [self._jsonify_tax(tax) for tax in new_taxes],
        }

    def assert_adapt_price_unit_to_another_taxes(self, price_unit, original_taxes, new_taxes, expected_price_unit, product=None):
        self._create_assert_test(
            expected_price_unit,
            self._create_py_sub_test_adapt_price_unit_to_another_taxes,
            self._create_js_sub_test_adapt_price_unit_to_another_taxes,
            self._assert_sub_test_adapt_price_unit_to_another_taxes,
            price_unit,
            original_taxes,
            new_taxes,
            product,
        )

    # -------------------------------------------------------------------------
    # tax_totals_summary
    # -------------------------------------------------------------------------

    def _assert_sub_test_tax_totals_summary(self, results, expected_values):
        multi_currency = results['currency_id'] != results['company_currency_id']
        excluded_fields = set() if multi_currency else {
            'tax_amount',
            'base_amount',
            'display_base_amount',
            'company_currency_id',
            'untaxed_amount',
            'total_amount',
       }
        excluded_fields.add('group_name')
        excluded_fields.add('involved_tax_ids')

        self.assertEqual(
            {k: len(v) if k == 'subtotals' else v for k, v in results.items() if k not in excluded_fields},
            {k: len(v) if k == 'subtotals' else v for k, v in expected_values.items()},
        )
        for subtotal, expected_subtotal in zip(results['subtotals'], expected_values['subtotals']):
            self.assertEqual(
                {k: len(v) if k == 'tax_groups' else v for k, v in subtotal.items() if k not in excluded_fields},
                {k: len(v) if k == 'tax_groups' else v for k, v in expected_subtotal.items()},
            )
            for tax_group, expected_tax_group in zip(subtotal['tax_groups'], expected_subtotal['tax_groups']):
                self.assertDictEqual(
                    {k: v for k, v in tax_group.items() if k not in excluded_fields},
                    expected_tax_group,
                )

    def _create_py_sub_test_tax_totals_summary(self, document):
        return self.env['account.tax']._get_tax_totals_summary(document['line_ids'], document['currency_id'], self.env.company)

    def _create_js_sub_test_tax_totals_summary(self, document):
        return {
            'test': 'tax_totals_summary',
            'document': self._jsonify_document(document),
            'rounding_method': self.env.company.tax_calculation_rounding_method,
        }

    def assert_tax_totals_summary(self, document, expected_values):
        self._create_assert_test(
            expected_values,
            self._create_py_sub_test_tax_totals_summary,
            None,
            # self._create_js_sub_test_tax_totals_summary,
            self._assert_sub_test_tax_totals_summary,
            document,
        )

    # -------------------------------------------------------------------------
    # tax_totals_summary, tax_amount_currency only
    # -------------------------------------------------------------------------

    def _assert_sub_test_tax_total(self, tax_amount, expected_tax_amount):
        self.assertAlmostEqual(tax_amount, expected_tax_amount)

    def _create_py_sub_test_tax_total(self, document):
        tax_totals = self.env['account.tax']._get_tax_totals_summary(document['line_ids'], document['currency_id'], self.env.company)
        return tax_totals['tax_amount_currency']

    def _create_js_sub_test_tax_total(self, document):
        return {
            'test': 'tax_total',
            'document': self._jsonify_document(document),
            'rounding_method': self.env.company.tax_calculation_rounding_method,
        }

    def assert_tax_total(self, document, expected_tax_amount):
        self._create_assert_test(
            expected_tax_amount,
            self._create_py_sub_test_tax_total,
            None,
            # self._create_js_sub_test_tax_total,
            self._assert_sub_test_tax_total,
            document,
        )

    # -------------------------------------------------------------------------
    # invoice tax_totals_summary
    # -------------------------------------------------------------------------

    def assert_invoice_tax_totals_summary(self, invoice, expected_values):
        self._assert_sub_test_tax_totals_summary(invoice.tax_totals, expected_values)
        self.assertRecordValues(invoice, [{
            'amount_untaxed': expected_values['base_amount_currency'],
            'amount_tax': expected_values['tax_amount_currency'],
            'amount_total': expected_values['total_amount_currency'],
        }])
