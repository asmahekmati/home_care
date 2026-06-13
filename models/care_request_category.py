from odoo import fields, models


class CareRequestCategory(models.Model):
    _name = 'care.request.category'
    _description = 'دسته‌بندی درخواست مراقبت'
    _order = 'sequence, name'

    name = fields.Char(string='نام', required=True, translate=True)
    code = fields.Char(string='کد', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string='توضیحات')
    workflow_id = fields.Many2one(
        'care.workflow.template',
        string='فرآیند پیش‌فرض',
        ondelete='restrict',
    )
    default_team_id = fields.Many2one(
        'care.team',
        string='تیم پیش‌فرض',
        ondelete='set null',
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'کد دسته‌بندی باید یکتا باشد.'),
    ]
