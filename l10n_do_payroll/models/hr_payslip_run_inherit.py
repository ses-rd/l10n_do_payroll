# -*- coding: utf-8 -*-

from odoo import models

class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_payroll_hr_version_list_view_payrun(self, date_start=None, date_end=None, structure_id=None, company_id=None, schedule_pay=None):
        # Acción personalizada: mostrar todos los hr.version activos para la compañía y fechas, sin filtrar por estructura ni schedule_pay
        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.action_payroll_hr_version_list_view_payrun')
        version_domain = [
            ('company_id', '=', company_id or self.company_id.id),
            ('employee_id', '!=', False),
            ('contract_date_start', '<=', date_end or self.date_end),
            '|',
                ('contract_date_end', '=', False),
                ('contract_date_end', '>=', date_start or self.date_start),
            ('date_version', '<=', date_end or self.date_end),
        ]
        valid_version_ids = self.env['hr.version'].search(version_domain).ids
        action['domain'] = [('id', 'in', valid_version_ids)]
        return action
