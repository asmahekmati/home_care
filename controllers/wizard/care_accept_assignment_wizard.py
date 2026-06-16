# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class CareAcceptAssignmentWizard(models.TransientModel):
    _name = 'care.accept.assignment.wizard'
    _description = 'Accept Request with Visit Schedule'

    request_id = fields.Many2one(
        'care.service.request',
        string='Request',
        required=True,
        ondelete='cascade',
    )
    visit_datetime_start = fields.Datetime(
        string='Visit Start',
        required=True,
    )
    visit_datetime_end = fields.Datetime(
        string='Visit End',
        required=True,
    )

    def action_accept(self):
        self.ensure_one()
        req = self.request_id
        if not req.can_current_user_accept:
            raise UserError(_('You cannot accept this request.'))
        req.action_accept_assignment(
            visit_start=self.visit_datetime_start,
            visit_end=self.visit_datetime_end,
        )
        return {'type': 'ir.actions.act_window_close'}
