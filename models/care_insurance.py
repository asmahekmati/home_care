from odoo import fields, models


class CareInsurance(models.Model):
    _name = 'care.insurance'
    _description = 'Home Care Insurance'
    _order = 'insurance_type, sequence, name'

    name = fields.Char(string='Insurance Name', required=True, translate=True)
    insurance_type = fields.Selection(
        [
            ('primary', 'Primary Insurance'),
            ('supplementary', 'Supplementary Insurance'),
        ],
        string='Type',
        required=True,
        default='primary',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    code = fields.Char(string='Code')
