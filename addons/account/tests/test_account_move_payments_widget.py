# -*- coding: utf-8 -*-
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged
from odoo.tests.common import users

import json


@tagged('post_install', '-at_install')
class TestAccountMovePaymentsWidget(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.receivable_account = cls.company_data['default_account_receivable']
        cls.payable_account = cls.company_data['default_account_payable']

        cls.currency_data_2 = cls.setup_multi_currency_data(default_values={
            'name': 'Stars',
            'symbol': '☆',
            'currency_unit_label': 'Stars',
            'currency_subunit_label': 'Little Stars',
        }, rate2016=6.0, rate2017=4.0)

        cls.curr_1 = cls.company_data['currency']
        cls.curr_2 = cls.currency_data['currency']
        cls.curr_3 = cls.currency_data_2['currency']

        cls.payment_2016_curr_1 = cls.env['account.move'].create({
            'date': '2016-01-01',
            'line_ids': [
                (0, 0, {'debit': 0.0,       'credit': 500.0,    'amount_currency': -500.0,  'currency_id': cls.curr_1.id,   'account_id': cls.receivable_account.id,    'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 500.0,     'credit': 0.0,      'amount_currency': 500.0,   'currency_id': cls.curr_1.id,   'account_id': cls.payable_account.id,       'partner_id': cls.partner_a.id}),
            ],
        })
        cls.payment_2016_curr_1.action_post()

        cls.payment_2016_curr_2 = cls.env['account.move'].create({
            'date': '2016-01-01',
            'line_ids': [
                (0, 0, {'debit': 0.0,       'credit': 500.0,    'amount_currency': -1550.0, 'currency_id': cls.curr_2.id,   'account_id': cls.receivable_account.id,    'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 500.0,     'credit': 0.0,      'amount_currency': 1550.0,  'currency_id': cls.curr_2.id,   'account_id': cls.payable_account.id,       'partner_id': cls.partner_a.id}),
            ],
        })
        cls.payment_2016_curr_2.action_post()

        cls.payment_2017_curr_2 = cls.env['account.move'].create({
            'date': '2017-01-01',
            'line_ids': [
                (0, 0, {'debit': 0.0,       'credit': 500.0,    'amount_currency': -950.0, 'currency_id': cls.curr_2.id,   'account_id': cls.receivable_account.id,    'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 500.0,     'credit': 0.0,      'amount_currency': 950.0,  'currency_id': cls.curr_2.id,   'account_id': cls.payable_account.id,       'partner_id': cls.partner_a.id}),
            ],
        })
        cls.payment_2017_curr_2.action_post()

        cls.payment_2016_curr_3 = cls.env['account.move'].create({
            'date': '2016-01-01',
            'line_ids': [
                (0, 0, {'debit': 0.0,       'credit': 500.0,    'amount_currency': -3050.0, 'currency_id': cls.curr_3.id,   'account_id': cls.receivable_account.id,    'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 500.0,     'credit': 0.0,      'amount_currency': 3050.0,  'currency_id': cls.curr_3.id,   'account_id': cls.payable_account.id,       'partner_id': cls.partner_a.id}),
            ],
        })
        cls.payment_2016_curr_3.action_post()

        cls.payment_2017_curr_3 = cls.env['account.move'].create({
            'date': '2017-01-01',
            'line_ids': [
                (0, 0, {'debit': 0.0,       'credit': 500.0,    'amount_currency': -1950.0, 'currency_id': cls.curr_3.id,   'account_id': cls.receivable_account.id,    'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 500.0,     'credit': 0.0,      'amount_currency': 1950.0,  'currency_id': cls.curr_3.id,   'account_id': cls.payable_account.id,       'partner_id': cls.partner_a.id}),
            ],
        })
        cls.payment_2017_curr_3.action_post()

        cls.payment_2017_curr_2_partner_b = cls.env['account.move'].create({
            'date': '2017-01-01',
            'line_ids': [
                (0, 0, {'debit': 0.0, 'credit': 500.0, 'amount_currency': -950.0, 'currency_id': cls.curr_2.id, 'account_id': cls.receivable_account.id, 'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 500.0, 'credit': 0.0, 'amount_currency': 950.0, 'currency_id': cls.curr_2.id, 'account_id': cls.payable_account.id, 'partner_id': cls.partner_b.id}),
            ],
        })
        cls.payment_2017_curr_2_partner_b.action_post()

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _test_all_outstanding_payments(self, invoice, expected_amounts):
        ''' Check the outstanding payments widget before/after the reconciliation.
        :param invoice:             An account.move record.
        :param expected_amounts:    A map <move_id> -> <amount>
        '''

        # Check suggested outstanding payments.
        to_reconcile_payments_widget_vals = json.loads(invoice.invoice_outstanding_credits_debits_widget)

        self.assertTrue(to_reconcile_payments_widget_vals)

        current_amounts = {vals['move_id']: vals['amount'] for vals in to_reconcile_payments_widget_vals['content']}
        self.assertDictEqual(current_amounts, expected_amounts)

        # Reconcile
        pay_term_lines = invoice.line_ids\
                .filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        to_reconcile = self.env['account.move'].browse(list(current_amounts.keys()))\
            .line_ids\
            .filtered(lambda line: line.account_id == pay_term_lines.account_id)
        (pay_term_lines + to_reconcile).reconcile()

        # Check payments after reconciliation.
        reconciled_payments_widget_vals = json.loads(invoice.invoice_payments_widget)

        self.assertTrue(reconciled_payments_widget_vals)

        current_amounts = {vals['move_id']: vals['amount'] for vals in reconciled_payments_widget_vals['content']}
        self.assertDictEqual(current_amounts, expected_amounts)

    # -------------------------------------------------------------------------
    # TESTS
    # -------------------------------------------------------------------------

    def test_outstanding_payments_single_currency(self):
        ''' Test the outstanding payments widget on invoices having the same currency
        as the company one.
        '''

        # Customer invoice of 2500.0 in curr_1.
        out_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'date': '2017-01-01',
            'invoice_date': '2017-01-01',
            'partner_id': self.partner_a.id,
            'currency_id': self.curr_1.id,
            'invoice_line_ids': [(0, 0, {'name': '/', 'price_unit': 2500.0})],
        })
        out_invoice.action_post()

        # Vendor bill of 2500.0 in curr_1.
        in_invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'date': '2017-01-01',
            'invoice_date': '2017-01-01',
            'partner_id': self.partner_a.id,
            'currency_id': self.curr_1.id,
            'invoice_line_ids': [(0, 0, {'name': '/', 'price_unit': 2500.0})],
        })
        in_invoice.action_post()

        expected_amounts = {
            self.payment_2016_curr_1.id: 500.0,
            self.payment_2016_curr_2.id: 500.0,
            self.payment_2017_curr_2.id: 500.0,
            self.payment_2016_curr_3.id: 500.0,
            self.payment_2017_curr_3.id: 500.0,
        }

        self._test_all_outstanding_payments(out_invoice, expected_amounts)
        self._test_all_outstanding_payments(in_invoice, expected_amounts)

    def test_outstanding_payments_foreign_currency(self):
        ''' Test the outstanding payments widget on invoices having a foreign currency. '''

        # Customer invoice of 2500.0 in curr_1.
        out_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'date': '2017-01-01',
            'invoice_date': '2017-01-01',
            'partner_id': self.partner_a.id,
            'currency_id': self.curr_2.id,
            'invoice_line_ids': [(0, 0, {'name': '/', 'price_unit': 7500.0})],
        })
        out_invoice.action_post()

        # Vendor bill of 2500.0 in curr_1.
        in_invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'date': '2017-01-01',
            'invoice_date': '2017-01-01',
            'partner_id': self.partner_a.id,
            'currency_id': self.curr_2.id,
            'invoice_line_ids': [(0, 0, {'name': '/', 'price_unit': 7500.0})],
        })
        in_invoice.action_post()

        expected_amounts = {
            self.payment_2016_curr_1.id: 1500.0,
            self.payment_2016_curr_2.id: 1550.0,
            self.payment_2017_curr_2.id: 950.0,
            self.payment_2016_curr_3.id: 1500.0,
            self.payment_2017_curr_3.id: 1000.0,
        }

        self._test_all_outstanding_payments(out_invoice, expected_amounts)
        self._test_all_outstanding_payments(in_invoice, expected_amounts)

    @users('admin')
    def test_registered_payments_foreign_currency(self):
        """
        Test the outstanding payments widget on an invoice in a foreign currency with a registered payment in the same foreign currency.
        """

        self.partner_b.property_account_receivable_id = self.receivable_account
        out_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'date': '2016-01-01',
            'invoice_date': '2016-01-06',
            'partner_id': self.partner_b.id,
            'currency_id': self.curr_2.id,
            'invoice_line_ids': [(0, 0, {'name': '/', 'price_unit': 950.0})],
        })
        out_invoice.action_post()

        payment = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=out_invoice.ids).create({
            'amount': 950.0,
            'group_payment': True,
            'currency_id': self.curr_2.id,
            'payment_method_line_id': self.inbound_payment_method_line.id,
        })._create_payments()

        exchange_move = out_invoice.line_ids.full_reconcile_id.exchange_move_id
        expected_amounts = {
            payment.move_id.id: 950.0,
            exchange_move.id: exchange_move.amount_total_signed,
        }

        reconciled_payments_widget_vals = json.loads(out_invoice.invoice_payments_widget)
        current_amounts = {vals['move_id']: vals['amount'] for vals in reconciled_payments_widget_vals['content']}

        self.assertDictEqual(current_amounts, expected_amounts)
