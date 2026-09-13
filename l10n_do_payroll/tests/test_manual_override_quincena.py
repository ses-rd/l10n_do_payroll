from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_do_manual_override')
class TestManualOverrideQuincena(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.country_do = cls.env.ref('base.do')
        cls.structure = cls.env.ref('l10n_do_payroll.structure_permanent_employees')
        if not cls.structure.use_worked_day_lines:
            cls.structure.use_worked_day_lines = True
        cls.structure_type = cls.env.ref('hr.structure_type_employee')
        cls.attendance_type = cls.env.ref('hr_work_entry.work_entry_type_attendance')
        cls.company = cls.env['res.company'].create({
            'name': 'DO Payroll Test Company',
            'country_id': cls.country_do.id,
            'currency_id': cls.env.company.currency_id.id,
            'resource_calendar_id': cls.env.company.resource_calendar_id.id,
        })

    def _create_employee_and_version(self, name):
        employee = self.env['hr.employee'].create({
            'name': name,
            'company_id': self.company.id,
            'resource_calendar_id': self.company.resource_calendar_id.id,
        })
        version = self.env['hr.version'].create({
            'name': f'Contract {name}',
            'employee_id': employee.id,
            'company_id': self.company.id,
            'contract_date_start': date(2026, 1, 1),
            'date_version': date(2026, 1, 1),
            'structure_type_id': self.structure_type.id,
            'resource_calendar_id': self.company.resource_calendar_id.id,
            'wage': 50000.0,
            'contract_wage': 50000.0,
        })
        employee.flush_recordset()
        version.flush_recordset()
        return employee, version

    def _create_biweekly_slip(self, employee, version, date_from, date_to):
        payrun = self.env['hr.payslip.run'].create({
            'name': f'Run {employee.name} {date_from.isoformat()} {date_to.isoformat()}',
            'company_id': self.company.id,
            'structure_id': self.structure.id,
            'date_start': date_from,
            'date_end': date_to,
            'schedule_pay': 'bi-weekly',
        })
        slip = self.env['hr.payslip'].create({
            'name': f'Slip {employee.name} {date_from.isoformat()} {date_to.isoformat()}',
            'employee_id': employee.id,
            'company_id': self.company.id,
            'version_id': version.id,
            'struct_id': self.structure.id,
            'payslip_run_id': payrun.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        slip._compute_worked_days_line_ids()
        attendance_line = slip.worked_days_line_ids.filtered(
            lambda line: line.code == self.attendance_type.code and not line.work_entry_type_id.is_extra_hours
        )[:1]
        self.assertTrue(attendance_line, 'El fixture del test debe generar una línea WORK100/attendance')
        return slip

    def _line_total(self, slip, code):
        return sum(slip.line_ids.filtered(lambda line: line.code == code).mapped('total'))

    def _monthly_isr_from_scisr(self, monthly_scisr):
        annual_base = monthly_scisr * 12
        if annual_base <= 416220.0:
            return 0.0
        if annual_base <= 624329.0:
            return ((annual_base - 416220.01) * 0.15) / 12
        if annual_base <= 867123.0:
            tasa1 = (624329.0 - 416220.0) * 0.15
            return (tasa1 + ((annual_base - 624329.01) * 0.20)) / 12
        tasa1 = (624329.0 - 416220.0) * 0.15
        tasa2 = (867123.0 - 624329.0) * 0.20
        return (tasa1 + tasa2 + ((annual_base - 867123.01) * 0.25)) / 12

    def test_normal_first_quincena_keeps_monthly_gross_reference(self):
        employee, version = self._create_employee_and_version('Normal Quincena')
        slip = self._create_biweekly_slip(employee, version, date(2026, 1, 1), date(2026, 1, 15))

        self.assertFalse(slip.l10n_do_manual_attendance_override)
        self.assertFalse(slip.partial_worked_days)
        self.assertAlmostEqual(slip._get_l10n_do_period_wage(), 25000.0, places=2)
        self.assertAlmostEqual(slip._l10n_do_get_manual_worked_day_ratio(), 1.0, places=6)
        self.assertAlmostEqual(slip._l10n_do_get_effective_gross_reference_wage(), 50000.0, places=2)

        slip.compute_sheet()

        self.assertAlmostEqual(version.wage, 50000.0, places=2)

    def test_first_quincena_manual_override_uses_current_period_base_only(self):
        employee, version = self._create_employee_and_version('Manual First Quincena')
        slip = self._create_biweekly_slip(employee, version, date(2026, 1, 1), date(2026, 1, 15))
        worked_days = slip.worked_days_line_ids.filtered(lambda line: line.code == 'WORK100')[:1]

        worked_days.write({'number_of_days': 5.0})
        expected_ratio = 5.0 / slip._get_l10n_do_expected_paid_days()
        expected_period_amount = 25000.0 * expected_ratio

        self.assertTrue(slip.l10n_do_manual_attendance_override)
        self.assertTrue(slip.partial_worked_days)
        self.assertAlmostEqual(slip._l10n_do_get_manual_worked_day_ratio(), expected_ratio, places=6)
        self.assertAlmostEqual(slip._l10n_do_get_effective_period_wage(), expected_period_amount, places=2)
        self.assertAlmostEqual(slip._l10n_do_get_effective_gross_reference_wage(), expected_period_amount, places=2)

        slip.compute_sheet()

        self.assertAlmostEqual(version.wage, 50000.0, places=2)

    def test_second_quincena_after_manual_first_does_not_carry_previous_gross(self):
        employee, version = self._create_employee_and_version('Second After Manual')
        first_slip = self._create_biweekly_slip(employee, version, date(2026, 1, 1), date(2026, 1, 15))
        first_worked_days = first_slip.worked_days_line_ids.filtered(lambda line: line.code == 'WORK100')[:1]
        first_worked_days.write({'number_of_days': 5.0})
        first_slip.compute_sheet()

        second_slip = self._create_biweekly_slip(employee, version, date(2026, 1, 16), date(2026, 1, 31))
        second_slip.compute_sheet()

        self.assertAlmostEqual(version.wage, 50000.0, places=2)
        self.assertLess(first_slip._l10n_do_get_effective_gross_reference_wage(), 25000.0)
        self.assertFalse(second_slip.l10n_do_manual_attendance_override)
        self.assertFalse(second_slip.partial_worked_days)
        self.assertAlmostEqual(second_slip._get_l10n_do_period_wage(), 25000.0, places=2)
        self.assertAlmostEqual(second_slip._l10n_do_get_effective_gross_reference_wage(), 50000.0, places=2)

    def test_second_quincena_partial_after_full_first_reconciles_on_accumulated_base(self):
        employee, version = self._create_employee_and_version('Second Partial After Full First')
        first_slip = self._create_biweekly_slip(employee, version, date(2026, 1, 1), date(2026, 1, 15))
        first_slip.compute_sheet()

        second_slip = self._create_biweekly_slip(employee, version, date(2026, 1, 16), date(2026, 1, 31))
        second_worked_days = second_slip.worked_days_line_ids.filtered(lambda line: line.code == 'WORK100')[:1]
        second_worked_days.write({'number_of_days': 10.5})
        second_slip.compute_sheet()

        first_half_base = first_slip._l10n_do_get_effective_contribution_period_base()
        second_half_base = second_slip._l10n_do_get_effective_contribution_period_base()
        accumulated_base = first_half_base + second_half_base
        expected_sfs = -((accumulated_base * 0.0304) - abs(self._line_total(first_slip, 'SFST')))
        expected_afp = -((accumulated_base * 0.0287) - abs(self._line_total(first_slip, 'SVDS')))
        expected_cinf = (accumulated_base * 0.01) - self._line_total(first_slip, 'CINF')

        self.assertTrue(second_slip._l10n_do_has_previous_same_month_payslip())
        self.assertTrue(second_slip.l10n_do_manual_attendance_override)
        self.assertTrue(second_slip.partial_worked_days)
        self.assertAlmostEqual(second_half_base, 25000.0 * (10.5 / second_slip._get_l10n_do_expected_paid_days()), places=2)
        self.assertAlmostEqual(second_slip._l10n_do_get_accumulated_contribution_period_base(), accumulated_base, places=2)
        self.assertLess(self._line_total(second_slip, 'SFST'), 0.0)
        self.assertLess(self._line_total(second_slip, 'SVDS'), 0.0)
        self.assertAlmostEqual(self._line_total(second_slip, 'SFST'), expected_sfs, places=2)
        self.assertAlmostEqual(self._line_total(second_slip, 'SVDS'), expected_afp, places=2)
        self.assertAlmostEqual(self._line_total(second_slip, 'CINF'), expected_cinf, places=2)

    def test_second_quincena_without_previous_first_stays_stable(self):
        employee, version = self._create_employee_and_version('Second Only')
        slip = self._create_biweekly_slip(employee, version, date(2026, 1, 16), date(2026, 1, 31))

        self.assertFalse(slip._l10n_do_has_previous_same_month_payslip())

        slip.compute_sheet()

        self.assertAlmostEqual(version.wage, 50000.0, places=2)
        self.assertFalse(slip.l10n_do_manual_attendance_override)
        self.assertFalse(slip.partial_worked_days)
        self.assertAlmostEqual(slip._get_l10n_do_period_wage(), 25000.0, places=2)
        self.assertAlmostEqual(slip._l10n_do_get_effective_gross_reference_wage(), 50000.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'SFST'), -(50000.0 * 0.0304 * 0.5), places=2)
        self.assertAlmostEqual(self._line_total(slip, 'SVDS'), -(50000.0 * 0.0287 * 0.5), places=2)
        self.assertAlmostEqual(self._line_total(slip, 'CINF'), 50000.0 * 0.01 * 0.5, places=2)

    def test_second_quincena_partial_without_previous_first_has_no_isr(self):
        employee, version = self._create_employee_and_version('Second Partial Without First ISR')
        slip = self._create_biweekly_slip(employee, version, date(2026, 1, 16), date(2026, 1, 31))
        worked_days = slip.worked_days_line_ids.filtered(lambda line: line.code == 'WORK100')[:1]

        worked_days.write({'number_of_days': 5.5})
        slip.compute_sheet()

        expected_basic = 25000.0 * (5.5 / slip._get_l10n_do_expected_paid_days())

        self.assertFalse(slip._l10n_do_has_previous_same_month_payslip())
        self.assertTrue(slip.l10n_do_manual_attendance_override)
        self.assertTrue(slip.partial_worked_days)
        self.assertAlmostEqual(slip._l10n_do_get_effective_period_wage(), expected_basic, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'ISR'), 0.0, places=2)

    def test_second_quincena_isr_does_not_spike_after_correct_first_withholding(self):
        employee, version = self._create_employee_and_version('Balanced ISR Across Quincenas')
        first_slip = self._create_biweekly_slip(employee, version, date(2026, 1, 1), date(2026, 1, 15))
        first_slip.compute_sheet()

        second_slip = self._create_biweekly_slip(employee, version, date(2026, 1, 16), date(2026, 1, 31))
        second_slip.compute_sheet()

        first_isr = abs(self._line_total(first_slip, 'ISR'))
        second_isr = abs(self._line_total(second_slip, 'ISR'))

        self.assertGreater(first_isr, 0.0)
        self.assertGreater(second_isr, 0.0)
        self.assertAlmostEqual(first_isr, second_isr, delta=0.01)

    def test_biweekly_isr_respects_payment_recurrence(self):
        employee, version = self._create_employee_and_version('Biweekly ISR Recurrence')
        first_slip = self._create_biweekly_slip(employee, version, date(2026, 1, 1), date(2026, 1, 15))
        first_slip.compute_sheet()

        second_slip = self._create_biweekly_slip(employee, version, date(2026, 1, 16), date(2026, 1, 31))
        second_slip.compute_sheet()

        first_scisr = first_slip._l10n_do_get_current_scisr_base(
            gross_base=self._line_total(first_slip, 'GROSS'),
            extra_hours=self._line_total(first_slip, 'HOREX'),
            incentives=self._line_total(first_slip, 'INCENT'),
            commissions=self._line_total(first_slip, 'COMM'),
        )
        second_scisr = second_slip._l10n_do_get_current_scisr_base(
            gross_base=self._line_total(second_slip, 'GROSS'),
            extra_hours=self._line_total(second_slip, 'HOREX'),
            incentives=self._line_total(second_slip, 'INCENT'),
            commissions=self._line_total(second_slip, 'COMM'),
        )
        first_isr = abs(self._line_total(first_slip, 'ISR'))
        second_isr = abs(self._line_total(second_slip, 'ISR'))
        expected_monthly_isr = self._monthly_isr_from_scisr(first_slip._l10n_do_get_isr_monthly_reference(first_scisr))

        self.assertAlmostEqual(first_scisr, second_scisr, places=2)
        self.assertAlmostEqual(first_isr, expected_monthly_isr / 2.0, delta=0.01)
        self.assertAlmostEqual(second_isr, expected_monthly_isr / 2.0, delta=0.01)