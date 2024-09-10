from odoo.tests.common import HttpCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestUi(HttpCase):

    def test_checkout_address_ec(self):
        company = self.env['res.company'].create({
            'name': "EC Test Company",
            'vat': "1792366836001",
            'street': "Avenida Machala 42",
            'zip': "090514",
            'city': "Guayaquil",
            'country_id': self.env.ref('base.ec').id,
        })
        self.env.company = company

        self.env.ref('base.user_admin').write({
            'company_id': self.env.company.id,
            'company_ids': [(4, self.env.company.id)],
        })
        self.env['product.product'].create({
            'name': 'Test Product',
            'sale_ok': True,
            'website_published': True,
        })
        self.env['ir.config_parameter'].set_param('sale.automatic_invoice', True)
        self.env['website'].get_current_website().company_id = self.env.company.id
        user_admin = self.env.ref('base.user_admin')
        user_admin.company_ids = user_admin.company_ids + self.env.company
        self.start_tour('/shop', 'shop_checkout_address_ec', login='admin')
