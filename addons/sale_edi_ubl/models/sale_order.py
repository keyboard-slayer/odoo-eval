from odoo import _, api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # EDI
    # -------------------------------------------------------------------------

    def _get_order_edi_decoder(self, file_data):
        """ Override of sale to add edi decoder for xml files.

        :param dict file_data: File data to decode.
        :return function: Function with decoding capibility `_import_order_ubl` for different xml
        formats.
        """
        if file_data['type'] == 'xml':
            ubl_cii_xml_builder = self._get_order_ubl_builder_from_xml_tree(file_data['xml_tree'])
            if ubl_cii_xml_builder is not None:
                return ubl_cii_xml_builder._import_order_ubl

        return super()._get_order_edi_decoder(file_data)

    @api.model
    def _get_order_ubl_builder_from_xml_tree(self, tree):
        """ Return sale order ubl builder with decording capibily to given tree

        :param xml tree: xml tree to find builder.
        :return class: class object of builder for given tree if found else none.
        """
        customization_id = tree.find('{*}CustomizationID')
        if customization_id is not None:
            if customization_id.text == 'urn:fdc:peppol.eu:poacc:trns:order:3':
                return self.env['sale.edi.xml.ubl_bis3']

    def _create_activity_set_details(self):
        """ Create activity on sale order to set details.

        Note: self.ensure_one()

        :return: None.
        """
        self.ensure_one()

        activity_message = _(
            "Some information could't not be imported"
        )
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.env.user.id,
            note=activity_message,
        )
