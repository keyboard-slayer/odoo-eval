{
    "name": """Indian - E-waybill thru IRN""",
    "countries": ["in"],
    "version": "1.03.00",
    "category": "Accounting/Localizations",
    "depends": [
        "l10n_in_ewaybill",
        "l10n_in_edi"
        "iap",
    ],
    "description": """
Indian - E-waybill thru IRN
====================================
This module provides facility to generate E-waybill through IRN.
    """,
    "data": [
    ],
    "installable": True,
    # not auto_install because the company can be related to the service industry
    "license": "LGPL-3",
}
