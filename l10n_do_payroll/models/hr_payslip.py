# -*- coding: utf-8 -*-

from odoo import models, fields, api
from calendar import monthrange


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    total_to_pay = fields.Float(compute='_compute_worked_hours', store=True)
    real_worked_hours = fields.Float()
    vacation_leave_id = fields.Many2one('hr.leave', string='Solicitud de vacaciones', copy=False, readonly=True)
    vacation_source_payslip_id = fields.Many2one('hr.payslip', string='Nomina origen', copy=False, readonly=True)
    vacation_generated_payslip_ids = fields.One2many(
        'hr.payslip',
        'vacation_source_payslip_id',
        string='Nominas de vacaciones generadas',
        readonly=True,
    )
    vacation_generated_payslip_count = fields.Integer(
        compute='_compute_vacation_generated_payslip_count',
        string='Nominas de vacaciones',
    )
    loan_line_ids = fields.One2many('hr.employee.loan.line', 'payslip_id', string="Cuotas de préstamo")
    disbursed_loan_ids = fields.One2many('hr.employee.loan', 'disbursement_payslip_id', string="Préstamos desembolsados")
    l10n_do_deduction_period = fields.Selection([
        ('weekly', 'Semanal'),
        ('bi-weekly', 'Quincenal'),
        ('monthly', 'Mensual'),
    ], compute='_compute_l10n_do_deduction_period_flags', store=False)
    l10n_do_is_deduction_period_closing = fields.Boolean(
        compute='_compute_l10n_do_deduction_period_flags',
        store=False,
    )
    l10n_do_is_deduction_period_second = fields.Boolean(
        compute='_compute_l10n_do_deduction_period_flags',
        store=False,
    )

    def _compute_vacation_generated_payslip_count(self):
        for rec in self:
            rec.vacation_generated_payslip_count = len(rec.vacation_generated_payslip_ids)

    def action_open_vacation_generated_payslips(self):
        self.ensure_one()
        slips = self.vacation_generated_payslip_ids
        action = {
            'name': 'Nominas de vacaciones',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', slips.ids)],
            'context': dict(self.env.context),
        }
        if len(slips) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': slips.id,
            })
        return action

    def _get_l10n_do_effective_schedule_pay(self, employee=False, version=False):
        self.ensure_one()
        employee = employee or self.employee_id
        version = version or self.version_id or (employee and employee.version_id)
        schedule_candidates = [
            getattr(getattr(self, 'payslip_run_id', False), 'schedule_pay', False),
            getattr(getattr(self, 'struct_id', False), 'schedule_pay', False),
            getattr(getattr(self, 'struct_type_id', False), 'default_schedule_pay', False),
            getattr(version, 'schedule_pay', False) if version else False,
            getattr(getattr(employee, 'current_version_id', False), 'schedule_pay', False) if employee else False,
            getattr(getattr(version, 'structure_type_id', False), 'default_schedule_pay', False) if version else False,
            getattr(getattr(getattr(employee, 'current_version_id', False), 'structure_type_id', False), 'default_schedule_pay', False) if employee else False,
        ]
        for candidate in schedule_candidates:
            if candidate:
                return candidate
        return 'monthly'

    def _l10n_do_has_manual_partial_worked_days(self):
        self.ensure_one()
        return bool(self.partial_worked_days and getattr(self, 'l10n_do_manual_attendance_override', False))

    def _l10n_do_get_additional_dependants_amount(self):
        self.ensure_one()
        dependants = 0.0
        dependant_amount = 1919.78
        version = self.version_id or (self.employee_id.version_id if self.employee_id else False)
        codependants = (version and version.codependants) or 'none'

        if codependants == '1':
            dependants = dependant_amount / 2
        elif codependants == '2':
            dependants = dependant_amount
        elif codependants == '3':
            dependants = (dependant_amount * 3) / 2

        return dependants

    def _l10n_do_get_salary_cap(self, cap_type):
        self.ensure_one()
        field_map = {
            'ars': 'l10n_do_ars_salary_cap',
            'afp': 'l10n_do_afp_salary_cap',
            'srl': 'l10n_do_srl_salary_cap',
        }
        default_map = {
            'ars': 232230.0,
            'afp': 464460.0,
            'srl': 92892.0,
        }
        field_name = field_map.get(cap_type)
        if not field_name:
            return 0.0
        value = getattr(self.company_id, field_name, 0.0) if self.company_id else 0.0
        return value or default_map.get(cap_type, 0.0)

    def _l10n_do_get_additional_per_capita_payment(self):
        self.ensure_one()
        dependants = self._l10n_do_get_additional_dependants_amount()
        if not dependants:
            return 0.0

        weekly_mode = self.employee_id.deduction_calc_mode == 'period' and self.employee_id.deduction_calc_period == 'weekly'
        payslip_day = self.date_to.day if self.date_to else 0

        if self._get_l10n_do_effective_schedule_pay() == 'hourly':
            return dependants

        if payslip_day >= 25 and payslip_day <= 31 and not weekly_mode:
            if self.pay_vacation and self.vacation_type == 'enjoyed':
                return dependants
            if self._l10n_do_has_manual_partial_worked_days() or self.env.context.get('l10n_do_skip_per_capita_second_half'):
                return 0.0
            if self._get_l10n_do_effective_schedule_pay() == 'bi-weekly' and not self._l10n_do_has_manual_partial_worked_days():
                version = self.version_id or self.employee_id.version_id
                gross_reference = (version and version.wage) or 0.0
                if gross_reference > self._l10n_do_get_salary_cap('ars'):
                    return 0.0
            return dependants

        return dependants

    def _l10n_do_get_additional_per_capita_monthly_reference(self):
        self.ensure_one()
        dependants = self._l10n_do_get_additional_dependants_amount()
        if not dependants:
            return 0.0

        multiplier = {
            'weekly': 4.0,
            'bi-weekly': 2.0,
        }.get(self._get_l10n_do_effective_schedule_pay(), 1.0)
        return dependants * multiplier

    def _l10n_do_get_isr_recurrence_fraction(self):
        self.ensure_one()
        period = self._map_schedule_to_deduction_period(self._get_l10n_do_effective_schedule_pay())
        if period == 'weekly':
            return 0.25
        if period == 'bi-weekly':
            return 0.5
        return 1.0

    def _l10n_do_get_previous_same_month_payslip(self):
        self.ensure_one()
        if not self.employee_id or not self.date_to:
            return self.env['hr.payslip']
        previous_slips = self._l10n_do_get_previous_same_month_payslips()
        return previous_slips[-1:] if previous_slips else self.env['hr.payslip']

    def _l10n_do_get_previous_same_month_payslips(self):
        self.ensure_one()
        if not self.employee_id or not self.date_to:
            return self.env['hr.payslip']
        return self.employee_id.slip_ids.filtered(
            lambda slip: slip.id != self.id
            and slip.date_to
            and slip.date_to < self.date_to
            and slip.date_to.month == self.date_to.month
            and slip.date_to.year == self.date_to.year
            and slip.state != 'cancel'
        ).sorted(key=lambda slip: (slip.date_to, slip.id))

    def _l10n_do_has_previous_same_month_payslip(self):
        self.ensure_one()
        return bool(self._l10n_do_get_previous_same_month_payslip())

    def _l10n_do_get_previous_same_month_line_total(self, code, absolute=False):
        self.ensure_one()
        previous_slip = self._l10n_do_get_previous_same_month_payslip()
        if not previous_slip:
            return 0.0
        amount = sum(previous_slip.line_ids.filtered(lambda line: line.code == code).mapped('total'))
        return abs(amount) if absolute else amount

    def _l10n_do_get_previous_same_month_line_totals(self, code, absolute=False):
        self.ensure_one()
        previous_slips = self._l10n_do_get_previous_same_month_payslips()
        if not previous_slips:
            return 0.0
        amount = sum(previous_slips.mapped('line_ids').filtered(lambda line: line.code == code).mapped('total'))
        return abs(amount) if absolute else amount

    def _l10n_do_get_line_total(self, code, absolute=False):
        self.ensure_one()
        amount = sum(self.line_ids.filtered(lambda line: line.code == code).mapped('total'))
        return abs(amount) if absolute else amount

    def _l10n_do_get_effective_contribution_period_base(self):
        self.ensure_one()
        basic_total = sum(self.line_ids.filtered(lambda line: line.code == 'BASIC').mapped('total'))
        if basic_total:
            return basic_total
        return self._l10n_do_get_effective_period_wage()

    def _l10n_do_get_accumulated_contribution_period_base(self):
        self.ensure_one()
        current_base = self._l10n_do_get_effective_contribution_period_base()
        previous_slip = self._l10n_do_get_previous_same_month_payslip()
        if not previous_slip:
            return current_base
        return current_base + previous_slip._l10n_do_get_effective_contribution_period_base()

    def _l10n_do_get_current_scisr_base(self, gross_base=0.0, extra_hours=0.0, incentives=0.0, commissions=0.0):
        self.ensure_one()
        # afp = 0.0287
        afp = self._rule_parameter('l10n_do_afp') / 100
        # sfs = 0.0304
        sfs = self._rule_parameter('l10n_do_sfs') / 100
        taxable_gross = gross_base or 0.0
        additional_per_capita = self._l10n_do_get_additional_per_capita_payment()

        if self._get_l10n_do_effective_schedule_pay() == 'bi-weekly' and not self._l10n_do_has_manual_partial_worked_days():
            gross_reference = self._l10n_do_get_effective_gross_reference_wage()
            taxable_gross = taxable_gross - gross_reference + self._get_l10n_do_period_wage()

        if taxable_gross < 0.0:
            taxable_gross = 0.0

        base = taxable_gross + extra_hours + incentives + commissions - additional_per_capita
        if base < 0.0:
            base = 0.0
        result = base - (taxable_gross * afp) - (taxable_gross * sfs)
        return result if result > 0.0 else 0.0

    def _l10n_do_get_accumulated_scisr_base(self, current_scisr=0.0):
        self.ensure_one()
        previous_scisr = 0.0
        for previous_slip in self._l10n_do_get_previous_same_month_payslips():
            previous_scisr += previous_slip._l10n_do_get_current_scisr_base(
                gross_base=previous_slip._l10n_do_get_line_total('GROSS'),
                extra_hours=previous_slip._l10n_do_get_line_total('HOREX'),
                incentives=previous_slip._l10n_do_get_line_total('INCENT'),
                commissions=previous_slip._l10n_do_get_line_total('COMM'),
            )
        return previous_scisr + current_scisr

    def _l10n_do_get_isr_monthly_reference(self, current_scisr=0.0):
        self.ensure_one()
        current_scisr = current_scisr if current_scisr else 0.0
        accumulated_scisr = self._l10n_do_get_accumulated_scisr_base(current_scisr)
        recurrence_fraction = self._l10n_do_get_isr_recurrence_fraction()
        is_closing = bool(self.date_to and self.date_to.day >= 25)

        if self._l10n_do_has_previous_same_month_payslip() or is_closing or recurrence_fraction >= 1.0:
            return accumulated_scisr
        if recurrence_fraction <= 0.0:
            return accumulated_scisr
        return current_scisr / recurrence_fraction

    def _l10n_do_get_isr_current_share(self, current_scisr=0.0, monthly_reference=0.0):
        self.ensure_one()
        if monthly_reference <= 0.0:
            return 0.0
        share = current_scisr / monthly_reference
        if share < 0.0:
            return 0.0
        if share > 1.0:
            return 1.0
        return share

    def _l10n_do_get_manual_worked_day_ratio(self):
        self.ensure_one()
        if not self._l10n_do_has_manual_partial_worked_days():
            return 1.0
        expected_days = self._get_l10n_do_expected_paid_days()
        if not expected_days:
            return 1.0
        return max(self._get_l10n_do_paid_worked_days(), 0.0) / expected_days

    def _l10n_do_get_effective_period_wage(self):
        self.ensure_one()
        return self._get_l10n_do_period_wage() * self._l10n_do_get_manual_worked_day_ratio()

    def _l10n_do_get_effective_gross_reference_wage(self):
        self.ensure_one()
        version = self.version_id or self.employee_id.version_id
        monthly_wage = (version and version.wage) or 0.0
        if self._l10n_do_has_manual_partial_worked_days():
            return self._l10n_do_get_effective_period_wage()
        if self._get_l10n_do_effective_schedule_pay() == 'bi-weekly':
            return monthly_wage
        return self._get_l10n_do_period_wage()

    def _get_l10n_do_effective_deduction_period(self, employee, version):
        calc_mode = getattr(employee, 'deduction_calc_mode', False) or 'payment_recurrence'
        if calc_mode == 'period':
            return getattr(employee, 'deduction_calc_period', False) or 'monthly'

        schedule_pay = self._get_l10n_do_effective_schedule_pay(employee=employee, version=version)
        return self._map_schedule_to_deduction_period(schedule_pay)

    @api.depends(
        'employee_id',
        'employee_id.version_id',
        'employee_id.current_version_id',
        'employee_id.deduction_calc_mode',
        'employee_id.deduction_calc_period',
        'struct_id',
        'struct_id.schedule_pay',
        'struct_type_id',
        'payslip_run_id',
        'payslip_run_id.schedule_pay',
        'date_to',
    )
    def _compute_l10n_do_deduction_period_flags(self):
        for rec in self:
            version = rec.employee_id.version_id if rec.employee_id else False
            period = rec._get_l10n_do_effective_deduction_period(rec.employee_id, version) if rec.employee_id else 'monthly'
            rec.l10n_do_deduction_period = period
            rec.l10n_do_is_deduction_period_closing = rec._is_period_closing_date(rec.date_to, period)
            rec.l10n_do_is_deduction_period_second = bool(rec.date_to and rec.date_to.day >= 25)

    def _map_schedule_to_deduction_period(self, schedule_pay):
        mapping = {
            'weekly': 'weekly',
            'bi-weekly': 'bi-weekly',
            'semi-monthly': 'bi-weekly',
            'monthly': 'monthly',
        }
        return mapping.get(schedule_pay, 'monthly')

    def _is_period_closing_date(self, date_to, period):
        if not date_to:
            return False
        if period == 'weekly':
            return True
        if period == 'bi-weekly':
            return date_to.day <= 15 or date_to.day >= 25
        if period == 'monthly':
            return date_to.day == monthrange(date_to.year, date_to.month)[1]
        return False

    def _get_l10n_do_expected_paid_days(self):
        self.ensure_one()
        weekly_mode = self.employee_id.deduction_calc_mode == 'period' and self.employee_id.deduction_calc_period == 'weekly'
        if weekly_mode:
            return 23.83 / 4.0
        if self._get_l10n_do_effective_schedule_pay() == 'bi-weekly':
            return 23.83 / 2.0
        return 23.83

    def _get_l10n_do_period_wage(self):
        self.ensure_one()
        weekly_mode = self.employee_id.deduction_calc_mode == 'period' and self.employee_id.deduction_calc_period == 'weekly'
        version = self.version_id or self.employee_id.version_id
        wage = (version and version.wage) or 0.0
        if weekly_mode:
            return wage / 4.0
        if self._get_l10n_do_effective_schedule_pay() == 'bi-weekly':
            return wage / 2.0
        return wage

    def _get_l10n_do_payroll_hours_per_day(self):
        self.ensure_one()
        calendar = self.version_id.resource_calendar_id or self.employee_id.resource_calendar_id or self.company_id.resource_calendar_id
        weekly_hours = calendar.hours_per_week if calendar else 0.0
        expected_days = self._get_l10n_do_expected_paid_days()
        if not weekly_hours or not expected_days:
            return calendar.hours_per_day if calendar else 0.0

        weekly_mode = self.employee_id.deduction_calc_mode == 'period' and self.employee_id.deduction_calc_period == 'weekly'
        if weekly_mode:
            expected_hours = weekly_hours
        else:
            monthly_hours = weekly_hours * 52.0 / 12.0
            expected_hours = monthly_hours / 2.0 if self._get_l10n_do_effective_schedule_pay() == 'bi-weekly' else monthly_hours
        return expected_hours / expected_days if expected_days else (calendar.hours_per_day if calendar else 0.0)

    def _get_worked_day_lines_hours_per_day(self):
        hours_per_day = super()._get_worked_day_lines_hours_per_day()
        self.ensure_one()
        if self.country_code != 'DO' or self.wage_type == 'hourly' or not self.struct_id or not self.struct_id.use_worked_day_lines:
            return hours_per_day
        return self._get_l10n_do_payroll_hours_per_day() or hours_per_day

    def _l10n_do_should_cap_quincenal_days(self):
        self.ensure_one()
        return bool(
            self.country_code == 'DO'
            and self.struct_id
            and self.struct_id.use_worked_day_lines
            and self.wage_type != 'hourly'
            and not self.pay_vacation
            and self._get_l10n_do_effective_schedule_pay() == 'bi-weekly'
        )

    def _l10n_do_cap_quincenal_work_entry_days(self):
        precision = 0.0001
        for payslip in self:
            if self.env.context.get('l10n_do_skip_cap_quincenal_days') or not payslip._l10n_do_should_cap_quincenal_days():
                continue
            paid_lines = payslip.worked_days_line_ids.filtered(
                lambda line: line.is_paid and line.code != 'OUT' and not line.work_entry_type_id.is_extra_hours
            )
            expected_days = payslip._get_l10n_do_expected_paid_days()
            paid_days = sum(paid_lines.mapped('number_of_days'))
            excess_days = paid_days - expected_days
            if excess_days <= precision:
                continue
            main_line = paid_lines.filtered(lambda line: line.code == 'WORK100')[:1]
            if not main_line:
                continue
            capped_days = max(main_line.number_of_days - excess_days, 0.0)
            if abs(main_line.number_of_days - capped_days) <= precision:
                continue
            main_line.with_context(
                l10n_do_skip_cap_quincenal_days=True,
                l10n_do_skip_manual_attendance_flag=True,
            ).write({'number_of_days': capped_days})

    def _get_l10n_do_paid_worked_days(self):
        self.ensure_one()
        paid_lines = self.worked_days_line_ids.filtered(
            lambda line: line.is_paid and line.code != 'OUT' and not line.work_entry_type_id.is_extra_hours
        )
        paid_days = sum(paid_lines.mapped('number_of_days'))
        if self._l10n_do_should_cap_quincenal_days():
            return min(paid_days, self._get_l10n_do_expected_paid_days())
        return paid_days

    def _sync_partial_worked_days_from_lines(self):
        precision = 0.0001
        for payslip in self:
            if not payslip.employee_id or not payslip.struct_id or not payslip.struct_id.use_worked_day_lines or payslip.pay_vacation:
                continue
            if not payslip.l10n_do_manual_attendance_override:
                payslip.partial_worked_days = False
                continue
            payslip._l10n_do_cap_quincenal_work_entry_days()
            expected_days = payslip._get_l10n_do_expected_paid_days()
            paid_days = payslip._get_l10n_do_paid_worked_days()
            payslip.partial_worked_days = abs(paid_days - expected_days) > precision

    def _get_deduction_fixed_component(self, employee, version, amount, date_to):
        amount = amount or 0.0
        calc_mode = getattr(employee, 'deduction_calc_mode', False) or 'payment_recurrence'

        if calc_mode == 'period':
            period = getattr(employee, 'deduction_calc_period', False) or 'monthly'
            return amount if self._is_period_closing_date(date_to, period) else 0.0

        period = self._get_l10n_do_effective_deduction_period(employee, version)
        divisor_by_period = {
            'weekly': 4.0,
            'bi-weekly': 2.0,
            'monthly': 1.0,
        }
        divisor = divisor_by_period.get(period, 1.0)
        return amount / divisor if divisor else amount

    def _auto_adjust_regular_period_for_vacations(self):
        self.ensure_one()
        if self.pay_vacation or not self.employee_id or not self.date_from or not self.date_to:
            return False

        # En Odoo 19 no se debe forzar partial_worked_days por vacaciones,
        # porque altera las deducciones por recurrencia (semanal/quincenal).
        # Conservamos el método para detectar presencia de vacaciones.
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', self.date_to),
            ('request_date_to', '>=', self.date_from),
        ], order='request_date_from asc')
        return bool(leaves)

    def _get_vacation_days_overlap(self):
        self.ensure_one()
        if not self.employee_id or not self.date_from or not self.date_to:
            return 0.0

        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('vacation_payslip_id', '!=', False),
            ('request_date_from', '<=', self.date_to),
            ('request_date_to', '>=', self.date_from),
        ])

        overlap_days = 0.0
        for leave in leaves:
            l_from = leave.request_date_from or (leave.date_from and leave.date_from.date())
            l_to = leave.request_date_to or (leave.date_to and leave.date_to.date())
            if not l_from or not l_to:
                continue
            start = max(self.date_from, l_from)
            end = min(self.date_to, l_to)
            if start <= end:
                total_days = (end - start).days + 1
                full_weeks, extra_days = divmod(total_days, 7)
                weekdays = full_weeks * 5
                start_weekday = start.weekday()
                for i in range(extra_days):
                    if (start_weekday + i) % 7 < 5:
                        weekdays += 1
                overlap_days += weekdays
        return overlap_days

    @api.onchange('employee_id', 'struct_id', 'date_from', 'date_to')
    def _onchange_employee(self):
        exclude_vaca_input = bool(self.pay_vacation and self.vacation_leave_id)
        # Inicializar inputs definidos en la estructura
        self.input_line_ids = [
            (0, 0, {'input_type_id': input.id})
            for input in self.struct_id.input_line_type_ids
            if input.id not in self.input_line_ids.mapped('input_type_id').ids
            and (not exclude_vaca_input or input.code != 'VACA')
        ]

        # En Odoo 19 no existe método padre _onchange_employee en hr.payslip
        # por lo que no llamamos a super y operamos directamente sobre self
        res = {}

        # Importar descuentos externos y asignar montos a inputs por código
        discount_import_ids = self.env['payroll.discount.import'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to)
        ])

        codes = []
        for line in discount_import_ids:
            if line.discount_code not in codes:
                codes.append(line.discount_code)

        discount_amount_dict = {}
        for code in codes:
            amount = 0
            for discount in discount_import_ids.filtered(lambda di: di.discount_code == code):
                amount += discount.amount
            discount_amount_dict.update({code: amount})

        for code, amount in discount_amount_dict.items():
            element = self.input_line_ids.filtered(lambda di: di.code == code)
            if element:
                element[0].amount = amount

        # Importar horas trabajadas
        working_hours_import_ids = self.env['working.hours.import'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to)
        ])
        normal_hours = sum(working_hours_import_ids.mapped('hours_amount'))
        extra_hours = sum(working_hours_import_ids.mapped('extra_hours_amount'))
        holiday_hours = sum(working_hours_import_ids.mapped('holiday_hours_amount'))

        element = self.worked_days_line_ids.filtered(lambda di: di.code == 'WORK100')
        if element:
            current_hours = element[0].number_of_hours or 0.0
            if current_hours <= 0.0:
                element[0].number_of_hours = normal_hours

        version = self.employee_id.version_id
        fixed_loan = self._get_deduction_fixed_component(
            self.employee_id,
            version,
            getattr(version, 'fixed_loan', 0.0),
            self.date_to,
        )
        amount_saved = self._get_deduction_fixed_component(
            self.employee_id,
            version,
            getattr(version, 'amount_saved', 0.0),
            self.date_to,
        )

        for input in self.input_line_ids.filtered(lambda ipi: ipi.code in ['HE35', 'HE100', 'FINAN', 'AHORRO']):
            if input.code == 'HE35':
                input.amount = extra_hours
            elif input.code == 'HE100':
                input.amount = holiday_hours
            elif input.code == 'FINAN':
                # Sumar cuotas de préstamos por fecha dentro del período del recibo
                finan_amount = 0.0
                loans = self.employee_id.loan_ids.filtered(lambda l: l.state in ('approved', 'to_disburse'))
                if loans:
                    for loan in loans:
                        # Tomar solo cuotas cuya fecha cae dentro del rango de la nómina
                        due_lines = loan.loan_line_ids.filtered(lambda ln: ln.date and self.date_from <= ln.date <= self.date_to and not ln.paid and not ln.payslip_id)
                        if due_lines:
                            finan_amount += sum(due_lines.mapped('dues'))
                base = finan_amount + fixed_loan
                input.amount = base
            elif input.code == 'AHORRO':
                input.amount = amount_saved

        return res

    def _get_last_payslip_vacation(self):
        payslip_day = self.date_to.day
        payslips = self.employee_id.slip_ids.sorted('id')
        payslips_ids = [p.id for p in payslips]

        if len(payslips_ids) > 1:
            last_slip = self.env['hr.payslip'].browse([payslips_ids[payslips_ids.index(self.id) - 1]])
            if payslip_day >= 25 and payslip_day <= 31:
                if last_slip.pay_vacation and last_slip.vacation_type in ['enjoyed', 'worked', 'unpayed']:
                    self.last_payslip_vacation = True
                else:
                    self.last_payslip_vacation = False
            else:
                self.last_payslip_vacation = False
        else:
            self.last_payslip_vacation = False

    pay_vacation = fields.Boolean(string="Vacaciones",
                                  help="Seleccione si el empleado va a cobrar vacaciones")
    vacation_type = fields.Selection([('enjoyed', 'Vacaciones disfrutadas'),
                                      ('worked', 'Vacaciones trabajadas'),
                                      ('unpayed', 'Vacaciones disfrutadas sin adelanto')],
                                       string="Tipo de vacaciones")
    last_payslip_vacation = fields.Boolean(compute='_get_last_payslip_vacation', store=False)

    partial_worked_days = fields.Boolean(string=u"Días trabajados parciales", help='Usar por ejemplo si un empleado entró a mitad de quincena (No usar si el empleado cobra por hora)')
    l10n_do_manual_attendance_override = fields.Boolean(
        string='Asistencia manual',
        copy=False,
        help='Se activa cuando los días/horas trabajados se modifican manualmente y habilita el prorrateo por asistencia.',
    )

    def action_refresh_from_work_entries(self):
        result = super().action_refresh_from_work_entries()
        self.write({
            'l10n_do_manual_attendance_override': False,
            'partial_worked_days': False,
        })
        return result

    def compute_commission_amount(self, payslip):
        payment_domain = [('payment_date', '<=', payslip.date_to),
                          ('state', 'in', ['posted', 'sent', 'reconciled']),
                          ('commissioned', '=', False),
                          ('user_id', '=', payslip.employee_id.user_id.id)]
        payment_fields = ['id', 'amount', 'amount_tax']
        payments_by_employee = payslip.env['account.payment'].search_read(payment_domain, payment_fields)

        payments_amount = sum([p.get('amount') - p.get('amount_tax') for p in payments_by_employee])
        com_rate = getattr(payslip.employee_id.version_id, 'comission_rate', 0) or 0
        commission_amount = (payments_amount * com_rate) / 100
        for line in payslip.input_line_ids:
            if line.code == 'COMIVE':
                line.amount = commission_amount

    def compute_sheet(self):
        # computar segunda quincena con if pay_vacation and vacation_type
        # obtener nomina anterior y revisar lo anterior,
        # si es verdadero establecer todos los line_ids en 0

        for rec in self:
            # Generar nómina de vacaciones separada para solicitudes aprobadas del empleado.
            if not rec.pay_vacation and rec.employee_id and rec.date_from and rec.date_to:
                pending_leaves = self.env['hr.leave']._get_pending_vacation_for_payroll(
                    rec.employee_id,
                    rec.date_from,
                    rec.date_to,
                )
                if pending_leaves:
                    pending_leaves._create_vacation_payslip(source_payslip=rec)

            # Asegurar inputs de la estructura y calcular cuotas de préstamos/ahorro
            if rec.struct_id and rec.struct_id.input_line_type_ids:
                missing_types = [
                    it for it in rec.struct_id.input_line_type_ids
                    if it.id not in rec.input_line_ids.mapped('input_type_id').ids
                ]
                if missing_types:
                    rec.input_line_ids = [(0, 0, {'input_type_id': it.id}) for it in missing_types] + [(1, line.id, {}) for line in rec.input_line_ids]

            version = rec.employee_id.version_id
            if not version:
                continue

            # Marcar desembolso al generar el recibo (Calcular hoja),
            # sin depender de fechas de inicio.
            for loan in rec.employee_id.loan_ids.filtered(lambda l: l.state == 'to_disburse'):
                if not loan.disbursement_payslip_id:
                    loan.mark_disbursed(rec)

            # Si hay vacaciones superpuestas ya pagadas en el período, forzar prorrateo.
            vacation_days_overlap = 0.0
            if not rec.pay_vacation:
                vacation_days_overlap = rec._get_vacation_days_overlap()

            # Asignar monto de desembolso al input DESPRE (si existe en la estructura)
            # Usar búsqueda directa para evitar issues de caché en One2many.
            disb_amount = 0.0
            disbursed_loans = self.env['hr.employee.loan'].search([('disbursement_payslip_id', '=', rec.id)])
            if disbursed_loans:
                disb_amount = sum(disbursed_loans.mapped('amount'))
            for line in rec.input_line_ids.filtered(lambda ipi: ipi.code == 'DESPRE'):
                line.amount = disb_amount

            for line in rec.input_line_ids:
                assurance_amount = getattr(version, 'assurance_amount', 0.0) or 0.0
                if assurance_amount > 0.0 and line.code == 'SEGMED':
                    line.amount = assurance_amount / 2

            # Calcular y asignar FINAN/AHORRO desde préstamos y versión
            fixed_loan = rec._get_deduction_fixed_component(
                rec.employee_id,
                version,
                getattr(version, 'fixed_loan', 0.0),
                rec.date_to,
            )
            amount_saved = rec._get_deduction_fixed_component(
                rec.employee_id,
                version,
                getattr(version, 'amount_saved', 0.0),
                rec.date_to,
            )
            # Sumar cuotas de préstamos por fecha dentro del período del recibo
            finan_amount = 0.0
            loans = rec.employee_id.loan_ids.filtered(lambda l: l.state in ('approved', 'to_disburse')) if rec.employee_id else False
            if loans:
                for loan in loans:
                    due_lines = loan.loan_line_ids.filtered(lambda ln: ln.date and rec.date_from <= ln.date <= rec.date_to and not ln.paid and not ln.payslip_id)
                    if due_lines:
                        finan_amount += sum(due_lines.mapped('dues'))

            for line in rec.input_line_ids.filtered(lambda ipi: ipi.code in ['FINAN', 'AHORRO']):
                if line.code == 'FINAN':
                    base = finan_amount + fixed_loan
                    line.amount = base
                elif line.code == 'AHORRO':
                    base = amount_saved
                    line.amount = base

            # Calcular comisión en base al porcentaje en la versión
            if getattr(version, 'comission_rate', 0) > 0:
                self.compute_commission_amount(rec)

        super(HrPayslip, self).compute_sheet()

        return True

    def action_mail_send(self):
        template_id = self.env.ref('l10n_do_payroll.email_template_mass_send')
        template_id.send_mail(self.id, force_send=True)
