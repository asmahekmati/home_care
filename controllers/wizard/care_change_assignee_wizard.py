# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CareChangeAssigneeWizard(models.TransientModel):
    _name = 'care.change.assignee.wizard'
    _description = 'Change Request Provider'

    request_id = fields.Many2one(
        'care.service.request',
        string='Request',
        required=True,
        ondelete='cascade',
    )
    current_user_id = fields.Many2one(
        'res.users',
        string='Current Provider',
        readonly=True,
    )
    new_user_id = fields.Many2one(
        'res.users',
        string='New Provider',
        required=True,
        domain="[('id', 'in', team_member_ids)]",
    )
    team_member_ids = fields.Many2many(
        'res.users',
        related='request_id.team_member_ids',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        req = self.env['care.service.request'].browse(
            self.env.context.get('default_request_id')
        )
        if req:
            res['current_user_id'] = req.user_id.id
        return res

    def action_confirm(self):
        self.ensure_one()
        req = self.request_id
        old_user = req.user_id
        new_user = self.new_user_id
        if not req.assignee_confirmed:
            raise UserError(_('The provider is not confirmed yet.'))
        if not new_user:
            raise UserError(_('Select a new provider.'))
        if old_user == new_user:
            raise UserError(_('The new provider is the same as the current provider.'))
        if new_user not in req.team_member_ids:
            raise UserError(_('The new provider must be a team member.'))
        req.with_context(change_assignee_wizard=True).write({'user_id': new_user.id})
        req._sync_manual_assignment(new_user)
        req._notify_assignee_change(old_user, new_user)
        return {'type': 'ir.actions.act_window_close'}
