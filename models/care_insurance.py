from odoo import fields, models


class CareInsurance(models.Model):
    _name = 'care.insurance'
    _description = 'بیمه مراقبت در منزل'
    _order = 'insurance_type, sequence, name'

    name = fields.Char(string='نام بیمه', required=True, translate=True)
    insurance_type = fields.Selection(
        [
            ('primary', 'بیمه پایه'),
            ('supplementary', 'بیمه تکمیلی'),
        ],
        string='نوع',
        required=True,
        default='primary',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    code = fields.Char(string='کد')
