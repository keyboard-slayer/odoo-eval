# -*- coding: utf-8 -*-
from unittest.mock import patch
from odoo import fields, Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.models import Model
from odoo.tests import tagged
import datetime


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nPtAccount(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref='pt_account'):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.company_data['company'].write({
            'street': '250 Executive Park Blvd, Suite 3400',
            'city': 'Lisboa',
            'zip': '9415-343',
            'company_registry': '123456',
            'phone': '+351 11 11 11 11',
            'country_id': cls.env.ref('base.pt').id,
            'vat': 'PT123456789',
        })
        cls.company_pt = cls.company_data['company']
        cls.company_data['default_journal_sale'].restrict_mode_hash_table = True
        cls.company_data['default_journal_sale'].l10n_pt_account_invoice_official_series_id = cls.env['l10n_pt_account.official.series'].create({'code': 'INV_SERIES'})
        cls.company_data['default_journal_sale'].l10n_pt_account_refund_official_series_id = cls.env['l10n_pt_account.official.series'].create({'code': 'REF_SERIES'})

    @staticmethod
    def post_moves(moves, l10n_pt_force_compute_signature=False):
        def _l10n_pt_check_taxes_patched(self):
            pass
        with patch('odoo.addons.l10n_pt_account.models.account_move.AccountMove._l10n_pt_check_taxes', _l10n_pt_check_taxes_patched):
            moves.with_context(l10n_pt_force_compute_signature=l10n_pt_force_compute_signature).action_post()
        return moves

    @classmethod
    def create_invoice(cls, move_type, invoice_date="2022-01-01", create_date=None, amount=1000.0, post=False):
        move = cls.env['account.move'].create({
            'move_type': move_type,
            'partner_id': cls.partner_a.id,
            'invoice_date': fields.Date.from_string(invoice_date),
            'line_ids': [
                Command.create({
                    'name': 'Product A',
                    'quantity': 1,
                    'price_unit': amount,
                    'tax_ids': [],
                }),
            ],
        })
        # Bypass ORM to update the create_date
        move._cr.execute('''
            UPDATE account_move
               SET create_date = %s
             WHERE id = %s
        ''', (datetime.datetime.strptime(create_date, '%Y-%m-%dT%H:%M:%S') if create_date else invoice_date, move.id))
        move.invalidate_model(['create_date'])
        if post:
            cls.post_moves(move, l10n_pt_force_compute_signature=True)
        return move

    def test_l10n_pt_account_hash_sequence(self):
        """
        Test that the hash sequence is correct.
        For this, we use the following resource provided by the Portuguese tax authority:
        https://info.portaldasfinancas.gov.pt/apps/saft-pt01/local/saft_idemo599999999.xml
        We create invoices with the same info as in the link, and we check that the hash that we obtain in Odoo
        is the same as the one given in the link (using the same sample keys).
        """

        L10N_PT_ACCOUNT_INVOICE_TYPE_MAP = {
            'out_invoice': '1T',
            'out_refund': '2T',
            'out_receipt': '11T',
            '1T': 'out_invoice',
            '2T': 'out_refund',
            '11T': 'out_receipt',
        }

        with patch('odoo.addons.l10n_pt_account.models.account_move.L10N_PT_ACCOUNT_INVOICE_TYPE_MAP', L10N_PT_ACCOUNT_INVOICE_TYPE_MAP):
            move_vals = {
                ('1T 1/1', '2017-03-10', '2017-03-10T15:58:01', 28.07): "vfinNfF+rToGp3dWF1LV6mEctQ76hAeZm+PlhBnV4wokN//N79L7fTNvi71ONnMHzfIzVR/Iz2zOOo9MUrYfYYZhqtpcEgFNHMdET6ZqbVVke7HbfqSACzaKXNdgWZt7lm7AFOfhcizQgC4a66SNvJvPJUqF7bCTUMIJFR9Zfro=",
                ('1T 1/2', '2017-09-16', '2017-09-16T15:58:10', 235.15): "jABYv0ThJHWoocmbzuLPOJXknl2WHBpLRBPqhIBSYP6GRzo3WiMxh6ryFiaa8rQD2BM9tdLxjhPHOZo1XPeGR5hFGK5BI/NzTXBu9+ponV4wvASOhjy2iomBlOxISN3MYGBcG1XWLfi+aDBw0TLrVwpbsENk0MtypYGU78OPPjg=",
                ('1T 1/3', '2017-09-16', '2017-09-16T15:58:45', 679.61): "MqvfiYZOh1L1fgfrAXBemPED1xy27MUs79vWxk/0P99Bq+jxvxwjJa3HQdElGfogj5bslcxX3ia9Tps2Oxfw1kH3GnsmfzqHbVagqnNxiI/KMZGfR4XXXNSOf7l7K7iMELz29b/c8u8eRmUwm13sgk9E9yAyk9zLuQ/s5TByG9k=",

                # We now have a new document type, so we have a new hash chain. The previous_hash of 2T A/1 is '', and not the hash of 1T 1/3
                ('2T A/1', '2017-09-16', '2017-09-16T16:02:16', 235.15): "CM1pPaqk/pTE5DajJZ3H9VejD00FL455GvHx0FjuNj3UKj1V9EkP5dPsOpB6/KXlttY1WsHGG4dcunSOKULW0FMEWAMQYxBo/HqLcIojedKxrzh6m9+P61VM4BnYxbtEBQRFdVs0MGP8X85uSc4ikPrY4OeO1UOixGR9xLIAtr4=",
                ('2T A/2', '2017-09-16', '2017-09-16T16:03:11', 2261.34): "Y7kXSvGiS1eCSU9DY1GlWHw+HMmpI/gdZKEv17EXFC7OFdOdSCwcRNPzBUB6QjB1aQ60T8+4jvQb+tSWAQJdsCoiNUMcZl+oQJKJjJTfPJTmDBlrnh0JGXaOrg4sPe1eVvjjtCKxyJ3xoQnwU/bVBjMde2Kx0zXBsBwIWoT0ukg=",
                ('2T A/3', '2017-09-16', '2017-09-16T16:04:45', 47.03): "W3Z1jj4rNG5CREwXq0ZCjaRHDqrB1U9U6NmyKZZ7VpruDsw+NxcbwUubuMgejYBCVr6OIRrUNlm1UvNuYx/EXFZpzhdoWRc7O1HPBSQFhAfhByE6QxvumsVtxSome95/cG2VmAU1MJUJTVQN4Y//snz8YaCy1/81bB7aGfUs0C0=",

                # We now have a new document type, so we have a new hash chain. The previous_hash of 11T P/1 is '', and not the hash of 2T A/3
                ('11T P/1', '2017-10-23', '2017-10-25T18:32:01', 28.07): "Niozekjl2e9pmgUC0cuDoII43yVpfHHFldwd3G45y9rpdODZmPd/uHr3YDP3UxDedPEGCqJR182qUFD8nYhRL4yn6ys9pKYKAtR2GVL2lTHoGqyvT8OB04X+w2SRD5fVuL/A1EqrSbSFj/FpEAJYrSDVJaZLVLwz9jK7KeuK/DM=",
                ('11T P/2', '2017-11-23', '2017-11-25T18:33:11', 28.07): "uXVDR4LxAvibqH+YTiLuNiM1rGBATTwtdx296NLmJcTroj9o0ydn8hjnKtbSOLfZsI2kXWXIHr1hCPNyfSjpePykbUsYLw0L3jBoxJfHGw3aMGH56L6muocxbfvO6a7V94uhog3ZwRG/obULIPT4HVqzMhQ9ShLzhf0zWt0cH+g=",

                # We now have a new series inside the same document type, so we have a new hash chain. The previous_hash of 11T Q/1 is '', and not the hash of 11T P/2
                ('11T Q/1', '2017-10-21', '2017-10-22T15:56:11', 28.07): "UkkKZXGlJpBzLw1KlQjnR5WnONyaNj58DlFfDQySOB6csg9KaPQpxmk5lbmokTZuNIQXYHlJYzh7hH+Pen3IaEN4pLh6a6mXD/59vez79DnVD7MiOuGPn3ad4CdtgQnXxtYrackQW+h4FiEoh+HO6KNwSw2R3FxGAilUvxJqCbI=",
            }
            moves = self.env['account.move']
            for (l10n_pt_account_document_number, invoice_date, create_date, amount) in move_vals:
                move_type = L10N_PT_ACCOUNT_INVOICE_TYPE_MAP[l10n_pt_account_document_number.split()[0]]
                move = self.create_invoice(move_type, invoice_date, create_date, amount, post=False)
                move.name = l10n_pt_account_document_number.split()[1]
                moves += move
            self.post_moves(moves, l10n_pt_force_compute_signature=True)
            for move, expected_hash in zip(moves, move_vals.values()):
                self.assertEqual(move.inalterable_hash.split("$")[2], expected_hash)

        integrity_check = self.company_pt._check_accounting_hash_integrity()['results'][0]  # [0] = 'out_invoice'
        self.assertEqual(integrity_check['status'], 'verified')

    def test_l10n_pt_account_hash_inalterability(self):
        expected_error_msg = "You cannot edit the following fields:.*"

        out_invoice = self.create_invoice('out_invoice', '2022-01-01', post=True)
        out_invoice.with_context(l10n_pt_force_compute_signature=True).flush_recordset()
        with self.assertRaisesRegex(UserError, f"{expected_error_msg}Inalterability Hash"):
            out_invoice.inalterable_hash = '$1$$1$fake_hash'
        with self.assertRaisesRegex(UserError, f"{expected_error_msg}Invoice/Bill Date"):
            out_invoice.invoice_date = fields.Date.from_string('2000-01-01')
        with self.assertRaisesRegex(UserError, expected_error_msg):
            out_invoice.create_date = fields.Datetime.now()
        with self.assertRaisesRegex(UserError, f"{expected_error_msg}Total"):
            out_invoice.amount_total = 666
        with self.assertRaisesRegex(UserError, expected_error_msg):
            out_invoice.sequence_number = 666  # Sequence number is used by l10n_pt_account_document_number so it cannot be modified either
        with self.assertRaisesRegex(UserError, expected_error_msg):
            out_invoice.sequence_prefix = "FAKE"  # Sequence prefix is used by l10n_pt_account_document_number so it cannot be modified either

        # The following fields are not part of the hash so they can be modified
        out_invoice.ref = 'new ref'
        out_invoice.line_ids[0].expected_pay_date = fields.Date.from_string('2023-01-01')

    def test_l10n_pt_account_document_no(self):
        """
        Test that the document number for Portugal follows this format: [^ ]+ [^/^ ]+/[0-9]+
        """
        for (move_type, date, expected) in [
            ('out_invoice', '2022-01-01', 'FT INV2022/1'),
            ('out_invoice', '2022-01-02', 'FT INV2022/2'),
            ('out_invoice', '2022-01-03', 'FT INV2022/3'),
            ('out_refund', '2022-01-01', 'NC RINV2022/1'),
            ('out_invoice', '2022-01-04', 'FT INV2022/4'),
        ]:
            move = self.create_invoice(move_type, date, post=True)
            self.assertEqual(move.l10n_pt_account_document_number, expected)

    def test_l10n_pt_account_move_hash_integrity_report(self):
        """Test the hash integrity report"""
        # Everything should be correctly hashed and verified
        # Reminder: we have one chain per move_type in Portugal
        out_invoice1 = self.create_invoice('out_invoice', '2022-01-01', post=True)
        self.create_invoice('out_invoice', '2022-01-02', post=True)
        out_invoice3 = self.create_invoice('out_invoice', '2022-01-03', post=True)
        out_invoice4 = self.create_invoice('out_invoice', '2022-01-04', post=True)

        integrity_check = self.company_pt._check_accounting_hash_integrity()['results'][0]  # [0] = 'out_invoice'
        self.assertEqual(integrity_check['status'], 'verified')
        self.assertRegex(integrity_check['msg'], 'Entries are correctly hashed')
        self.assertEqual(integrity_check['from_date'], fields.Date.to_string(out_invoice1.date))
        self.assertEqual(integrity_check['to_date'], fields.Date.to_string(out_invoice4.date))

        # Let's change one of the fields used by the hash. It should be detected by the integrity report.
        # We need to bypass the write method of account.move to do so.
        Model.write(out_invoice3, {'invoice_date': fields.Date.from_string('2022-01-07')})
        integrity_check = self.company_pt._check_accounting_hash_integrity()['results'][0]
        self.assertEqual(integrity_check['status'], 'corrupted')
        self.assertEqual(integrity_check['msg'], f'Corrupted data on journal entry with id {out_invoice3.id}.')

        # Let's try with the inalterable_hash field itself
        Model.write(out_invoice3, {'invoice_date': fields.Date.from_string("2022-01-03")})  # Revert the previous change
        Model.write(out_invoice4, {'inalterable_hash': '$1$fake_hash'})
        integrity_check = self.company_pt._check_accounting_hash_integrity()['results'][0]
        self.assertEqual(integrity_check['status'], 'corrupted')
        self.assertEqual(integrity_check['msg'], f'Corrupted data on journal entry with id {out_invoice4.id}.')

    def test_l10n_pt_account_inalterable_hash_computation_optimization(self):
        """
        Test that the hash is computed only when needed (when printing, previewing or
        when generating the hash integrity report), and not when posting an invoice.
        One must make sure that all invoices before the one being printed have a hash too.
        """
        out_invoices = self.env['account.move']
        for _ in range(3):
            out_invoices |= self.create_invoice('out_invoice', '2022-01-01')
            self.post_moves(out_invoices[-1])
            self.assertEqual(out_invoices[-1].inalterable_hash, False)

        for method in ['preview_invoice', 'action_send_and_print']:
            out_invoices |= self.create_invoice('out_invoice', '2022-01-01')
            self.post_moves(out_invoices[-1])
            self.assertEqual(out_invoices[-1].inalterable_hash, False)
            getattr(out_invoices[-1], method)()  # Should trigger the compute of the hash
            self.assertNotEqual(out_invoices[-1].inalterable_hash, False)

        integrity_check = self.company_pt._check_accounting_hash_integrity()['results'][0]  # [0] = 'out_invoice'
        self.assertEqual(integrity_check['status'], 'verified')
        self.assertRegex(integrity_check['msg'], 'Entries are correctly hashed')
        self.assertEqual(integrity_check['from_date'], fields.Date.to_string(out_invoices[0].date))
        self.assertEqual(integrity_check['to_date'], fields.Date.to_string(out_invoices[-1].date))
