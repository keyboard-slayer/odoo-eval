# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, tools
from odoo.tests import tagged
from odoo.fields import Command
from odoo.tools import float_compare, mute_logger, test_reports
from odoo.tests.common import Form
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon
from odoo.addons.l10n_sa_edi.tests.common import TestSaEdiCommon


@tagged('post_install', '-at_install')
class TestEdiPos(TestPointOfSaleCommon, TestSaEdiCommon):

    def test_order_combo_invoice(self):
        invoice_partner_address = self.env["res.partner"].create({
            'name': "Test invoice partner",
        })

        # Creating combo product
        product = self.env['product.product'].create({
            'name': 'Test Product 1',
            'list_price': 100,
            'taxes_id': [(6, 0, self.tax_15.ids)],
            'available_in_pos': True,
        })

        product_1_combo_line = self.env["pos.combo.line"].create({
            "product_id": product.id,
        })

        pos_combo = self.env["pos.combo"].create(
            {
                "name": "Pos combo",
                "combo_line_ids": [
                    (6, 0, [product_1_combo_line.id])
                ],
            }
        )

        product_combo = self.env["product.product"].create({
            "available_in_pos": True,
            "list_price": 100,
            "name": "Office Combo",
            "type": "combo",
            "combo_ids": [
                (6, 0, [pos_combo.id])
            ],
        })

        #self.journal['edi_format_ids'] = self.edi_format.ids
        self.pos_config.open_ui()
        current_session = self.pos_config.current_session_id

        order_data = {'data': {
            'amount_paid': 115,
            'amount_return': 0,
            'amount_tax': 15,
            'amount_total': 115,
            'date_order': fields.Datetime.to_string(fields.Datetime.now()),
            'fiscal_position_id': False,
            'lines': [[0, 0, {
                'discount': 0,
                'pack_lot_ids': [],
                'price_unit': 0,
                'product_id': product_combo.id,
                'price_subtotal': 0,
                'price_subtotal_incl': 0.0,
                'tax_ids': False,
                'qty': 1,
            }], [0, 0, {
                'discount': 0,
                'pack_lot_ids': [],
                'price_unit': 100,
                'product_id': product.id,
                'price_subtotal': 100,
                'price_subtotal_incl': 115,
                'tax_ids': [(6, 0, self.tax_15.ids)],
                'qty': 1,
            }]],
            'name': 'Order 00044-003-0014',
            'state': 'order',
            'partner_id': invoice_partner_address.id,
            'pos_session_id': current_session.id,
            'sequence_number': self.pos_config.journal_id.id,
            'statement_ids': [[0, 0, {
                'amount': 115,
                'name': fields.Datetime.now(),
                'payment_method_id': self.pos_config.payment_method_ids[0].id
            }]],
            'uid': '00044-003-0014',
            'user_id': self.env.uid,
            'to_invoice': True},
            'to_invoice': False}

        # I create an order on an open session
        self.env['pos.order'].create_from_ui([order_data])
