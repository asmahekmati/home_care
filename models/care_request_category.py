from odoo import fields, models


class CareRequestCategory(models.Model):
    _name = 'care.request.category'
    _description = 'Care Request Category'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    workflow_id = fields.Many2one(
        'care.workflow.template',
        string='Default Workflow',
        ondelete='restrict',
    )
    default_team_id = fields.Many2one(
        'care.team',
        string='Default Team',
        ondelete='set null',
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Category code must be unique.'),
    ]
