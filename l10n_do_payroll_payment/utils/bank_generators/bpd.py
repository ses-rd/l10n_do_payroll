# -*- coding: utf-8 -*-

import base64
import io
import time

from odoo import _
from .bpd_catalog import CURRENCY_CODES, get_bpd_bank_code_and_digit, remove_accent

def _get_beneficiary_name(line):
    employee = getattr(line, 'employee_id', False)
    partner = getattr(line, 'partner_id', False)
    return (employee and employee.name) or (partner and partner.name) or _('BENEFICIARIO')


def _get_beneficiary_email(line):
    employee = getattr(line, 'employee_id', False)
    partner = getattr(line, 'partner_id', False)
    return (employee and employee.work_email) or (partner and partner.email) or ''


def _get_document_data(line):
    employee = getattr(line, 'employee_id', False)
    partner = getattr(line, 'partner_id', False)
    country = (employee and employee.country_id) or (partner and partner.country_id)
    country_code = country.code if country else False
    identification = (employee and employee.identification_id) or (partner and partner.vat)
    passport = (employee and employee.passport_id) or False

    if passport and country_code and country_code != 'DO':
        return 'PS', passport
    if identification:
        return ('CE' if not country_code or country_code == 'DO' else 'OT'), identification
    if passport:
        return 'PS', passport

    fallback_value = str((partner and partner.id) or (employee and employee.id) or '')
    return 'OT', fallback_value


def _get_currency_name(obj, bank_account):
    source_currency = obj.journal_id.bank_account_id.currency_id.name if obj.journal_id.bank_account_id and obj.journal_id.bank_account_id.currency_id else False
    target_currency = bank_account.currency_id.name if bank_account.currency_id else False
    currency_name = target_currency or source_currency or obj.company_id.currency_id.name or 'DOP'
    if currency_name not in CURRENCY_CODES:
        currency_name = 'DOP'
    return currency_name


def _get_destination_bank_data(bank_account, currency_name):
    if not bank_account or not bank_account.bank_id:
        return '00000000', ' '

    bank_code, bank_digit = bank_account.bank_id.get_electronic_payroll_bank_code_and_digit(currency_name)
    if not bank_code:
        bank_code, bank_digit = get_bpd_bank_code_and_digit(bank_account.bank_id.name, currency_name)
    if not bank_code:
        return '00000000', ' '
    return bank_code, bank_digit or ' '


def _next_sequence(obj):
    seq = obj.sequence
    if not seq:
        seq = obj.env['ir.sequence'].next_by_code('BPD')
        if not seq:
            seq = str(int(time.time()))[-7:].zfill(7)
        obj.sequence = seq
    return str(seq).zfill(7)


def generate_bpd_txt(obj):
    rnc = obj.company_id.vat or ''

    sequence = _next_sequence(obj)
    effective_date = '{:%Y%m%d}'.format(obj.effective_date)
    create_date = '{:%Y%m%d}'.format(obj.create_date)
    create_hour = '{:%H%M}'.format(obj.create_date)
    payroll_email = obj.journal_id.payroll_email or obj.company_id.email or ''
    company_code = (obj.journal_id.payroll_company_bank_code or '00001').zfill(5)

    file_io = io.BytesIO()
    lines = []
    credit_lines = 0
    amount_credit = 0.0
    position = 1

    for line in obj.line_ids:
        if line.no_file:
            continue

        employee = getattr(line, 'employee_id', False)
        partner = getattr(line, 'partner_id', False)
        bank_account = line.bank_account_id

        doc_type, num_doc = _get_document_data(line)
        currency_name = _get_currency_name(obj, bank_account)
        currency_code = CURRENCY_CODES[currency_name]
        bank_code, bank_digit = _get_destination_bank_data(bank_account, currency_name)
        account_type = '1' if bank_account and bank_account.account_type == 'CC' else '2'
        operation_code = '22' if account_type == '1' else '32'
        account_number = ((bank_account and bank_account.acc_number) or '').replace('-', '').replace(' ', '')

        beneficiary_name = remove_accent(_get_beneficiary_name(line) or '').upper()
        amount = str('%.2f' % line.amount).replace('.', '').zfill(13)
        beneficiary_email = _get_beneficiary_email(line)
        work_email = beneficiary_email[0:40].ljust(40) if beneficiary_email else ' '.ljust(40)
        contact_type = '1' if beneficiary_email else ' '

        txt_line = (
            'N{rnc}{seq}{position}{account}{account_type}{currency}{bank_code}{bank_digit}{operation}'
            '{amount}{doc_type}{document}{name}{reference}{concept}{due_date}{contact}{email}{fax}'
            '{acquirer}{authorization}{remote_return}{remote_reason}{internal_reason}{processor}{status}{filler}'
        ).format(
            rnc=str(rnc).ljust(15)[:15],
            seq=sequence,
            position=str(position).zfill(7),
            account=account_number.ljust(20)[:20],
            account_type=account_type,
            currency=currency_code,
            bank_code=bank_code,
            bank_digit=bank_digit,
            operation=operation_code,
            amount=amount,
            doc_type=doc_type,
            document=num_doc.replace(' ', '').replace('-', '').ljust(15)[:15],
            name=beneficiary_name.ljust(35)[:35],
            reference=' '.ljust(12),
            concept=(obj.description or 'PAGO NOMINA').ljust(40)[:40],
            due_date=' '.ljust(4),
            contact=contact_type,
            email=work_email,
            fax=' '.ljust(12),
            acquirer='00',
            authorization=' '.ljust(15),
            remote_return=' '.ljust(3),
            remote_reason=' '.ljust(3),
            internal_reason=' '.ljust(3),
            processor=' ',
            status=' '.ljust(2),
            filler=' '.ljust(52),
        )
        lines.append(txt_line)
        position += 1
        credit_lines += 1
        amount_credit += line.amount

    if not lines:
        lines.append('')

    header = (
        'H{rnc}{company_name}{sequence}{service_type}{effective_date}{debit_count}{debit_amount}{credit_count}'
        '{credit_amount}{affiliate_number}{create_date}{create_hour}{email}{status}{filler}'
    ).format(
        rnc=str(rnc).ljust(15)[:15],
        company_name=(obj.company_id.name or '').ljust(35)[:35],
        sequence=sequence,
        service_type='01',
        effective_date=effective_date,
        debit_count='00000000000',
        debit_amount='0000000000000',
        credit_count=str(credit_lines).zfill(11),
        credit_amount=str('%.2f' % amount_credit).replace('.', '').zfill(13),
        affiliate_number='000000000000000',
        create_date=create_date,
        create_hour=create_hour,
        email=str(payroll_email).ljust(40)[:40],
        status=' ',
        filler=' '.ljust(136),
    )

    file_io.write((header + '\r\n').encode())
    for txt_line in lines:
        file_io.write((txt_line + '\r\n').encode())

    file_value = file_io.getvalue()
    try:
        report = base64.encodebytes(file_value)
    except Exception:
        report = base64.b64encode(file_value)

    report_name = 'PE{company_code}01{month:02d}{day:02d}{sequence}E.TXT'.format(
        company_code=company_code,
        month=obj.effective_date.month,
        day=obj.effective_date.day,
        sequence=sequence,
    )
    if obj.payslip_run_id:
        obj.name = 'PAGO - %s' % obj.payslip_run_id.name
    else:
        obj.name = obj.description or obj.name
    file_io.close()
    return report, report_name