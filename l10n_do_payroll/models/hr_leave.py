# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    vacation_payslip_id = fields.Many2one('hr.payslip', string='Nomina de vacaciones', copy=False, readonly=True)
    payroll_vacation_days = fields.Float(
        string='Dias vacaciones nomina',
        compute='_compute_payroll_vacation_days',
        readonly=True,
    )

    @api.depends('date_from', 'date_to', 'request_date_from', 'request_date_to')
    def _compute_payroll_vacation_days(self):
        for leave in self:
            date_from, date_to = leave._get_effective_leave_dates()
            if not date_from or not date_to or date_to < date_from:
                leave.payroll_vacation_days = 0.0
                continue

            # Contar dias laborables (L-V) para evitar pagar fines de semana en vacaciones.
            total_days = (date_to - date_from).days + 1
            full_weeks, extra_days = divmod(total_days, 7)
            weekdays = full_weeks * 5
            start_weekday = date_from.weekday()
            for i in range(extra_days):
                if (start_weekday + i) % 7 < 5:
                    weekdays += 1

            leave.payroll_vacation_days = float(weekdays)

    def _get_effective_leave_dates(self):
        self.ensure_one()
        date_from = (self.date_from and self.date_from.date()) or self.request_date_from
        date_to = (self.date_to and self.date_to.date()) or self.request_date_to
        return date_from, date_to

    def _get_pending_vacation_for_payroll(self, employee, date_from, date_to):
        if not employee:
            return self.env['hr.leave']
        candidates = self.search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('vacation_payslip_id', '=', False),
        ], order='date_from asc, request_date_from asc')
        valid_leaves = candidates.filtered(
            lambda leave: leave._get_effective_leave_dates()[0]
            and leave._get_effective_leave_dates()[1]
            and leave._get_effective_leave_dates()[0] <= date_to
            and leave._get_effective_leave_dates()[1] >= date_from
        )
        return valid_leaves

    def _create_vacation_payslip(self, source_payslip=False):
        for leave in self:
            if leave.vacation_payslip_id:
                continue
            if leave.state != 'validate' or not leave.employee_id:
                continue

            date_from, date_to = leave._get_effective_leave_dates()
            if not date_from or not date_to:
                continue

            version = leave.employee_id._get_version(date=date_from)
            if not version:
                continue

            struct = version.structure_type_id.default_struct_id or version.structure_id
            if not struct:
                continue

            # Si por alguna razón aún no existe entrada de trabajo de la licencia, forzar su generación.
            if 'hr.work.entry' in self.env and 'leave_id' in self.env['hr.work.entry']._fields:
                has_work_entry = bool(self.env['hr.work.entry'].search_count([('leave_id', '=', leave.id)]))
                if not has_work_entry and hasattr(leave, '_cancel_work_entry_conflict'):
                    leave.sudo()._cancel_work_entry_conflict()

            generated_on = fields.Date.context_today(self)
            period_label = '%s al %s' % (date_from, date_to)
            slip_name = '%s - Vacaciones (%s)' % (period_label, generated_on)

            slip_vals = {
                'name': slip_name,
                'employee_id': leave.employee_id.id,
                'version_id': version.id,
                'struct_id': struct.id,
                'date_from': date_from,
                'date_to': date_to,
                'pay_vacation': True,
                'vacation_type': 'enjoyed',
                'vacation_leave_id': leave.id,
                'vacation_source_payslip_id': source_payslip.id if source_payslip else False,
                'payslip_run_id': source_payslip.payslip_run_id.id if source_payslip and source_payslip.payslip_run_id else False,
            }
            slip = self.env['hr.payslip'].with_context(default_date_to=date_to).create(slip_vals)
            slip._onchange_employee()

            if source_payslip:
                source_input_by_code = {
                    line.code: line.amount
                    for line in source_payslip.input_line_ids
                    if line.code
                }
                for input_line in slip.input_line_ids.filtered(lambda l: l.code and l.code != 'VACA'):
                    if input_line.code in source_input_by_code:
                        input_line.amount = source_input_by_code[input_line.code]

            # Generar líneas salariales y deducciones al crear la nómina de vacaciones.
            slip.compute_sheet()

            # Blindaje: aunque la regla VACA exista, no mostrar esa línea en el recibo.
            vaca_lines = slip.line_ids.filtered(lambda l: l.code == 'VACA')
            if vaca_lines and 'appears_on_payslip' in vaca_lines._fields:
                vaca_lines.write({'appears_on_payslip': False})

            leave.vacation_payslip_id = slip.id
