# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class CareAcceptAssignmentWizard(models.TransientModel):
    _name = 'care.accept.assignment.wizard'
    _description = 'پذیرش درخواست با زمان‌بندی حضور'

    request_id = fields.Many2one(
        'care.service.request',
        string='درخواست',
        required=True,
        ondelete='cascade',
    )
    visit_datetime_start = fields.Datetime(
        string='شروع حضور',
        required=True,
    )
    visit_datetime_end = fields.Datetime(
        string='پایان حضور',
        required=True,
    )

    def action_accept(self):
        self.ensure_one()
        req = self.request_id
        if not req.can_current_user_accept:
            raise UserError(_('امکان پذیرش این درخواست برای شما وجود ندارد.'))
        req.action_accept_assignment(
            visit_start=self.visit_datetime_start,
            visit_end=self.visit_datetime_end,
        )
        return {'type': 'ir.actions.act_window_close'}
