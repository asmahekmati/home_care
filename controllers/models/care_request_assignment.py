from odoo import fields, models


class CareRequestAssignmentOffer(models.Model):
    _name = 'care.request.assignment.offer'
    _description = 'Care Request Assignment Offer'
    _order = 'create_date desc, id desc'

    request_id = fields.Many2one(
        'care.service.request',
        string='Request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    step_id = fields.Many2one(
        'care.workflow.step',
        string='Step',
        required=True,
        ondelete='restrict',
    )
    team_id = fields.Many2one(
        'care.team',
        string='Team',
        required=True,
        ondelete='restrict',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Team Member',
        required=True,
        ondelete='restrict',
        index=True,
    )
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='pending',
        required=True,
        index=True,
    )
    accepted_at = fields.Datetime(string='Accepted At')
    sms_sent = fields.Boolean(string='SMS Sent', default=False)

    _sql_constraints = [
        (
            'request_user_step_uniq',
            'unique(request_id, step_id, user_id)',
            'Each member can have only one offer per step.',
        ),
    ]
