# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'LinkedIn Recruitment',
    'version': '1.0',
    'category': 'Human Resources/Recruitment',
    'sequence': 90,
    'website': 'https://www.odoo.com/app/recruitment',
    'depends': [
        'website_hr_recruitment',
    ],
    'data': [
        'data/job_feed_template.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}