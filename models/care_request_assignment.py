from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CareRequestAssignmentOffer(models.Model):
    _name = 'care.request.assignment.offer'
    _description = 'پیشنهاد پذیرش درخواست به عضو تیم'
    _order = 'create_date desc, id desc'

    request_id = fields.Many2one(
        'care.service.request',
        string='درخواست',
        required=True,
        ondelete='cascade',
        index=True,
    )
    step_id = fields.Many2one(
        'care.workflow.step',
        string='مرحله',
        required=True,
        ondelete='restrict',
    )
    team_id = fields.Many2one(
        'care.team',
        string='تیم',
        required=True,
        ondelete='restrict',
    )
    user_id = fields.Many2one(
        'res.users',
        string='عضو تیم',
        required=True,
        ondelete='restrict',
        index=True,
    )
    state = fields.Selection(
        [
            ('pending', 'در انتظار'),
            ('accepted', 'پذیرفته‌شده'),
            ('cancelled', 'لغوشده'),
        ],
        string='وضعیت',
        default='pending',
        required=True,
        index=True,
    )
    accepted_at = fields.Datetime(string='زمان پذیرش')
    sms_sent = fields.Boolean(string='SMS ارسال شد', default=False)

    _sql_constraints = [
        (
            'request_user_step_uniq',
            'unique(request_id, step_id, user_id)',
            'هر عضو فقط یک پیشنهاد برای هر مرحله می‌تواند داشته باشد.',
        ),
    ]
