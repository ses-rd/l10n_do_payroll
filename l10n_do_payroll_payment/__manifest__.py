# -*- coding: utf-8 -*-
{
    'name': 'Dominican Payroll Payment',
    'summary': 'Integracion entre lotes de nomina y batch payments',
    'author': 'NetVux',
    'license': 'LGPL-3',
    'category': 'Localization/Payroll',
    'version': '19.0.1.0.0',
    'depends': [
        'l10n_do_payroll',
        'account_batch_payment',
    ],
    'data': [
        'data/res_bank_payroll_data.xml',
        'views/hr_payslip_run_views.xml',
        'views/account_batch_payment_views.xml',
        'views/account_journal_views.xml',
        'views/res_partner_bank_views.xml',
    ],
    'installable': True,
    'application': False,
}
