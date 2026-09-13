# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xlsxwriter
import string
import base64
from datetime import date
from datetime import datetime


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    payroll_xlsx_file_name = fields.Char()
    payroll_xlsx_binary = fields.Binary(string="Archivo xls para el banco")
    is_christmas_salary = fields.Boolean(string='Nómina de doble sueldo / regalía')

    def assign_worked_hours(self):
        for payslip in self.slip_ids:
            for wdl in payslip.worked_days_line_ids:
                wdl.number_of_hours = payslip.real_worked_hours

    def generate_payroll_xlsx(self):

        if len(self.slip_ids) < 1:
            raise ValidationError(u"Debe generar alguna nómina primero.")

        records = []
        cont = 1
        for rec in self.slip_ids:
            records.append([rec.employee_id.bank_account_id.bank_id.name or '',
                            rec.employee_id.bank_account_id.acc_number or '',
                            rec.employee_id.name,
                            "'" + (rec.employee_id.identification_id or ''),
                            cont,
                            rec.line_ids.filtered(lambda line_ids: line_ids.code == 'NET').total or '',
                            self.name or '',
                            rec.employee_id.work_email or ''])
            cont += 1

        payroll_date = str(self.date_end.year) + str(self.date_end.month) + str(self.date_end.day)

        file_header = ['Banco',
                       'Número de la cuenta',
                       'Nombre del empleado',
                       'Cédula',
                       'Numero de referencia',
                       'Monto de pago',
                       'Concepto',
                       u'Correo electrónico']

        file_path = '/tmp/NOMINA{}.xlsx'.format(payroll_date)
        workbook = xlsxwriter.Workbook(file_path, {'strings_to_numbers': True})
        worksheet = workbook.add_worksheet()
        # Add a bold format to use to highlight cells.
        bold = workbook.add_format({'bold': 1})

        # List the alphabet
        alphabet = ["%s%d" % (l, 1) for l in string.ascii_uppercase]

        for letter, header in zip(alphabet, file_header):
            worksheet.write(str(letter), str(header), bold)

        row = 1
        for rec in records:
            for col, detail in enumerate(rec):
                worksheet.write(row, col, detail)
            row += 1

        workbook.close()

        self.write({
            'payroll_xlsx_file_name': file_path.replace('/tmp/', ''),
            'payroll_xlsx_binary': base64.b64encode(open(file_path, 'rb').read())
        })

    def compute_all_payslips(self):
        if len(self.slip_ids) < 1:
            raise ValidationError(u"Debe generar alguna nómina primero.")
        # self.assign_worked_hours()
        for payslip in self.slip_ids.filtered(lambda slip: slip.state != 'done'):
            payslip.compute_sheet()

    def confirm_all_payslips(self):
        for payslip in self.slip_ids.filtered(lambda slip: slip.state != 'done'):
            payslip.action_payslip_done()

    @api.onchange('date_start')
    def onchange_date_start(self):
        if not self.date_start:
            return
        for payslip in self.slip_ids:
            payslip.date_from = self.date_start

    @api.onchange('date_end')
    def onchange_date_end(self):
        if not self.date_end:
            return
        for payslip in self.slip_ids:
            payslip.date_to = self.date_end

    def action_mail_send(self):
        done_slips = self.slip_ids.filtered(lambda s: s.state == 'done')
        if not done_slips:
            raise UserError(_('There are no done payslips to send.'))

        sent_count = 0
        for slip in done_slips:
            slip.action_mail_send()
            sent_count += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Emails sent'),
                'message': _('%s payslips were sent.') % sent_count,
                'type': 'success',
                'sticky': False,
            },
        }


"""
El asistente 'hr.payslip.employees' ya no existe en esta versión.
Se elimina la herencia del wizard para evitar errores de registro.
La generación de nóminas debe hacerse mediante las acciones del lote (hr.payslip.run).
"""
