from odoo.tests.common import TransactionCase


class TestPropertiesExportImport(TransactionCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ModelDefinition = cls.env['import.properties.definition']
        cls.ModelProperty = cls.env['import.properties']
        cls.definition_records = cls.ModelDefinition.create(
            [
                {
                    'properties_definition': [
                        {'name': 'char_prop', 'type': 'char', 'string': 'TextType', 'default': 'Def'},
                        {'name': 'separator_prop', 'type': 'separator', 'string': 'Separator'},
                        {
                            'name': 'selection_prop',
                            'type': 'selection',
                            'string': 'One Selection',
                            'selection': [
                                ['selection_1', 'aaaaaaa'],
                                ['selection_2', 'bbbbbbb'],
                                ['selection_3', 'ccccccc'],
                            ],
                        },
                        {
                            'name': 'm2o_prop',
                            'type': 'many2one',
                            'string': 'many2one',
                            'comodel': 'res.partner',
                        },
                    ]
                },
                {
                    'properties_definition': [
                        {'name': 'bool_prop', 'type': 'boolean', 'string': 'CheckBox'},
                        {
                            'name': 'tags_prop',
                            'tags': [['aa', 'AA', 5], ['bb', 'BB', 6], ['cc', 'CC', 7]],
                            'type': 'tags',
                            'string': 'Tags',
                        },
                        {
                            'name': 'm2m_prop',
                            'type': 'many2many',
                            'string': 'M2M',
                            'comodel': 'res.partner',
                        },
                    ]
                },
            ]
        )
        cls.partners = cls.env['res.partner'].create(
            [
                {'name': 'Name Partner 1'},
                {'name': 'Name Partner 2'},
                {'name': 'Name Partner 3'},
            ]
        )

        cls.properties_records = cls.ModelProperty.create(
            [
                {
                    'record_definition_id': cls.definition_records[0].id,
                    'properties': {
                        'char_prop': 'Not the default',
                        'selection_prop': 'selection_2',
                    },
                },
                {
                    'record_definition_id': cls.definition_records[0].id,
                    'properties': {
                        'm2o_prop': cls.partners[0].id,
                    },
                },
                {
                    'record_definition_id': cls.definition_records[1].id,
                    'properties': {
                        'tags_prop': ['aa', 'bb'],
                        'bool_prop': True,
                    },
                },
                {
                    'record_definition_id': cls.definition_records[1].id,
                    'properties': {
                        'm2m_prop': cls.partners.ids,
                    },
                },
            ]
        )

    def test_export_properties(self):
        all_properties = [
            [f"properties.{property_dict_type['name']}"]
            for property_dict_type in self.definition_records[0].properties_definition
            + self.definition_records[1].properties_definition
            if property_dict_type['type'] != 'separator'
        ]
        # Without import compatibility
        self.assertEqual(
            self.properties_records.with_context(import_compat=False)._export_rows(all_properties),
            [
                ['Not the default', 'bbbbbbb', '', '', '', ''],
                ['Def', '', 'Name Partner 1', '', '', ''],
                ['', '', '', True, 'AA,BB', ''],
                ['', '', '', '', '', 'Name Partner 1'],
                ['', '', '', '', '', 'Name Partner 2'],
                ['', '', '', '', '', 'Name Partner 3'],
            ],
        )
        # With import compatibility
        self.assertEqual(
            self.properties_records._export_rows(all_properties),
            [
                ['Not the default', 'bbbbbbb', '', '', '', ''],
                ['Def', '', 'Name Partner 1', '', '', ''],
                ['', '', '', True, 'AA,BB', ''],
                ['', '', '', '', '', 'Name Partner 1,Name Partner 2,Name Partner 3'],
            ],
        )

    def test_export_grouped(self):
        # test url /web/export/csv
        pass
