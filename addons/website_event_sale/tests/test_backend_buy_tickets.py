# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests

from odoo.addons.base.tests.common import HttpCaseWithUserDemo
from odoo.addons.website_event_sale.tests.common import TestWebsiteEventSaleCommon
from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.tools import mute_logger


@odoo.tests.common.tagged('post_install', '-at_install')
class TestUi(HttpCaseWithUserDemo, TestWebsiteEventSaleCommon, PaymentHttpCommon):

    def setUp(self):
        super().setUp()

    @mute_logger('odoo.http')
    def test_check_seats_avail_before_purchase(self):
        self.authenticate(None, None)
        so_line = self.env['sale.order.line'].create({
            'event_id': self.event.id,
            'event_ticket_id': self.ticket.id,
            'name': self.event.name,
            'order_id': self.so.id,
            'product_id': self.ticket.product_id.id,
            'product_uom_qty': 1,
        })
        self.so._cart_update(line_id=so_line.id, product_id=self.ticket.product_id.id, set_qty=1)
        url = self._build_url(f'/shop/payment/transaction/{self.so.id}')
        self.ticket.write({
            'seats_taken': 1,
            'seats_max': 1,
            'seats_limited': True,
        })
        self.env['event.registration'].create([{'event_id': self.event.id, 'sale_order_id': self.so.id} for _ in range(2)])
        route_kwargs = {
            'provider_id': self.provider.id,
            'payment_method_id': self.payment_method.id,
            'token_id': None,
            'amount': self.so.amount_total,
            'flow': 'direct',
            'tokenization_requested': False,
            'landing_route': '/shop/payment/validate',
            'is_validation': False,
            'csrf_token': odoo.http.Request.csrf_token(self),
            'access_token': self.so._portal_ensure_token(),
        }
        with mute_logger("odoo.http"), self.assertRaises(
            odoo.tests.JsonRpcException, msg='odoo.exceptions.ValidationError'
        ):
            self.make_jsonrpc_request(url, route_kwargs)
