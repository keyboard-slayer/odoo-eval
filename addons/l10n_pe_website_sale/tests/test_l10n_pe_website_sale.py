# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests


@odoo.tests.tagged('post_install_l10n', 'post_install', '-at_install')
class TestWebsiteSalePe(odoo.tests.HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['product.product'].create({
            'name': 'Test Product',
            'standard_price': 70.0,
            'list_price': 70.0,
            'website_published': True,
        })
        website = cls.env['website'].get_current_website()
        website.company_id.account_fiscal_country_id = website.company_id.country_id = cls.env.ref('base.pe')

    def test_change_address(self):
        self.start_tour("/", 'update_the_address_for_peru_company', login="admin")
