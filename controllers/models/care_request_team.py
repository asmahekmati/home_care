from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CareServiceRequestTeam(models.Model):
    _inherit = 'care.service.request'

    assignee_confirmed = fields.Boolean(
        string='Provider Confirmed',
        default=False,
        copy=False,
        tracking=True,
    )

    @api.model
    def _is_care_provider(self, user=None):
        user = user or self.env.user
        if user.has_group('home_care.group_care_manager'):
            return True
        if user.has_group('home_care.group_care_provider'):
            return True
        return bool(self.env['care.team'].sudo().search_count([
            '|',
            ('member_ids', 'in', user.id),
            ('leader_id', '=', user.id),
        ]))

    def action_open_change_assignee_wizard(self):
        self.ensure_one()
        if not self.assignee_confirmed or not self.user_id:
            raise UserError(_('There is no confirmed provider to change.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Change Provider'),
            'res_model': 'care.change.assignee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_current_user_id': self.user_id.id,
            },
        }

    def _notify_assignee_change(self, old_user, new_user):
        self.ensure_one()
        if old_user:
            self.message_post(
                body=_(
                    'Request %s was unassigned from you. Customer: %s — Service: %s'
                ) % (
                    self.name,
                    self.partner_id.name or '',
                    self.product_id.display_name or '',
                ),
                partner_ids=old_user.partner_id.ids,
                subtype_xmlid='mail.mt_comment',
            )
        if new_user:
            self.message_post(
                body=_(
                    'Request %s was assigned to you. Customer: %s — Service: %s'
                ) % (
                    self.name,
                    self.partner_id.name or '',
                    self.product_id.display_name or '',
                ),
                partner_ids=new_user.partner_id.ids,
                subtype_xmlid='mail.mt_comment',
            )
            self._send_assignee_notification_sms(new_user)

    def _send_assignee_notification_sms(self, user):
        self.ensure_one()
        step = self.current_step_id
        if not step or not step.send_team_sms:
            return
        partner = user.partner_id
        number = self._get_partner_sms_number(partner)
        if not number:
            return
        body = self._render_team_sms_body(step.team_sms_body or '', step, user)
        sms = self.env['sms.sms'].sudo().create({
            'number': number,
            'body': body,
            'partner_id': partner.id,
        })
        try:
            sms.send()
        except Exception:
            pass

    @api.model
    def action_view_my_provider_requests(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Requests (Provider)'),
            'res_model': 'care.service.request',
            'view_mode': 'list,form',
            'domain': self._provider_portal_domain(),
        }

    @api.model
    def _provider_portal_domain(self, user=None):
        """Requests where the provider is assigned or has a pending assignment offer."""
        user = user or self.env.user
        pending_request_ids = self.env['care.request.assignment.offer'].search([
            ('user_id', '=', user.id),
            ('state', '=', 'pending'),
            ('request_id.user_id', '=', False),
        ]).mapped('request_id').ids
        return [
            '|',
            ('user_id', '=', user.id),
            '&',
            ('user_id', '=', False),
            ('id', 'in', pending_request_ids or [0]),
        ]

    def _provider_has_pending_offer(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(self.assignment_offer_ids.filtered(
            lambda o: (
                o.user_id == user
                and o.state == 'pending'
                and o.step_id == self.current_step_id
            )
        ))

    def provider_can_access(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if self.user_id == user:
            return True
        return self._provider_has_pending_offer(user)

    def provider_can_accept(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return (
            self.state == 'in_progress'
            and not self.user_id
            and self._provider_has_pending_offer(user)
        )

    def provider_can_complete_service(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return (
            self.state == 'in_progress'
            and self.user_id == user
            and self.current_step_id
            and self.current_step_id.allow_provider_complete
        )

    def write(self, vals):
        if 'user_id' in vals and not self.env.context.get('change_assignee_wizard'):
            for req in self.filtered('assignee_confirmed'):
                new_uid = vals['user_id']
                if new_uid and new_uid != req.user_id.id:
                    raise UserError(_(
                        'The provider is confirmed. Use the "Change Provider" button to reassign.'
                    ))
        if vals.get('user_id') is False:
            vals['assignee_confirmed'] = False
        res = super().write(vals)
        if vals.get('user_id') and not self.env.context.get('skip_manual_assign_sync'):
            for req in self.filtered(
                lambda r: r.current_step_id and r.current_step_id.team_acceptance_mode
            ):
                req._sync_manual_assignment(self.env['res.users'].browse(vals['user_id']))
        return res

    def action_confirm_manual_assignee(self):
        for req in self:
            if not req.user_id:
                raise UserError(_('Select an assignee first.'))
            if req.assignee_confirmed:
                raise UserError(_('The provider is already confirmed.'))
            req._sync_manual_assignment(req.user_id)
            req.assignee_confirmed = True
        return True

    def _sync_manual_assignment(self, user):
        self.ensure_one()
        step = self.current_step_id
        if not step or not user:
            return
        self.assignment_offer_ids.filtered(
            lambda o: o.step_id == step and o.state == 'pending'
        ).write({'state': 'cancelled'})
        offer = self.assignment_offer_ids.filtered(
            lambda o: o.step_id == step and o.user_id == user
        )[:1]
        if offer:
            offer.write({
                'state': 'accepted',
                'accepted_at': fields.Datetime.now(),
            })
        else:
            team = self.team_id or step.auto_team_id
            if team:
                self.env['care.request.assignment.offer'].create({
                    'request_id': self.id,
                    'step_id': step.id,
                    'team_id': team.id,
                    'user_id': user.id,
                    'state': 'accepted',
                    'accepted_at': fields.Datetime.now(),
                })
        self.message_post(
            body=_('Assignee set manually: %s') % user.name,
            subtype_xmlid='mail.mt_note',
        )

    def provider_can_cancel_service(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return (
            self.state == 'in_progress'
            and self.user_id == user
            and self.current_step_id
            and self.current_step_id.allow_provider_cancel
        )

    def action_provider_complete_service(self, note=False):
        user = self.env.user
        for req in self:
            if req.user_id != user and not self.env.user.has_group(
                'home_care.group_care_manager'
            ):
                raise UserError(_('Only the assigned provider can mark the service as completed.'))
            if not req.current_step_id or not req.current_step_id.allow_provider_complete:
                raise UserError(_('Service completion is not allowed at this step.'))
            if note:
                req.provider_complete_note = note
                req.message_post(
                    body=_('Completion notes by provider: %s') % note,
                    subtype_xmlid='mail.mt_note',
                )
            req.action_proceed_workflow()
        return True

    def action_provider_cancel_request(self, note=False):
        user = self.env.user
        for req in self.filtered(lambda r: r.state not in ('done', 'cancelled')):
            if req.user_id != user and not self.env.user.has_group(
                'home_care.group_care_manager'
            ):
                raise UserError(_('Only the assigned provider can cancel the request.'))
            if not req.current_step_id or not req.current_step_id.allow_provider_cancel:
                raise UserError(_('Provider cancellation is not allowed at this step.'))
            if note:
                req.provider_cancel_note = note
                req.message_post(
                    body=_('Cancellation notes by provider: %s') % note,
                    subtype_xmlid='mail.mt_note',
                )
            req._move_to_cancel_step()
        return True

    def action_open_accept_assignment_wizard(self):
        self.ensure_one()
        if not self.can_current_user_accept:
            raise UserError(_('You cannot accept this request.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Accept Request and Schedule Visit'),
            'res_model': 'care.accept.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_accept_assignment(self, visit_start=False, visit_end=False):
        user = self.env.user
        for req in self:
            offer = req.assignment_offer_ids.filtered(
                lambda o: o.user_id == user
                and o.state == 'pending'
                and o.step_id == req.current_step_id
            )[:1]
            if not offer:
                raise UserError(_('You have no active offer to accept.'))
            if req.user_id:
                raise UserError(
                    _('This request was already accepted by %s.')
                    % req.user_id.name
                )
            step = req.current_step_id
            needs_schedule = step and (
                step.requires_visit_schedule or step.team_acceptance_mode
            )
            if needs_schedule:
                if not visit_start or not visit_end:
                    raise UserError(_('Visit date and time window are required.'))
                req._check_visit_within_preferred(visit_start, visit_end)
                req._check_visit_overlap(user, visit_start, visit_end)

            offer.write({
                'state': 'accepted',
                'accepted_at': fields.Datetime.now(),
            })
            other_offers = req.assignment_offer_ids.filtered(
                lambda o: o.id != offer.id
                and o.step_id == req.current_step_id
                and o.state == 'pending'
            )
            other_offers.write({'state': 'cancelled'})
            write_vals = {
                'user_id': user.id,
                'assignee_confirmed': True,
            }
            if visit_start and visit_end:
                write_vals.update({
                    'visit_datetime_start': visit_start,
                    'visit_datetime_end': visit_end,
                })
            req.with_context(skip_manual_assign_sync=True).write(write_vals)
            schedule_msg = ''
            if visit_start and visit_end:
                schedule_msg = _(' — Visit time: %s') % req.visit_schedule_display
            req.message_post(
                body=_('Request accepted by %s.%s') % (user.name, schedule_msg),
                subtype_xmlid='mail.mt_note',
            )
            req._send_customer_assignee_sms()
            if req.state == 'in_progress' and req.current_step_id:
                next_step = req._get_next_step(req.current_step_id)
                if next_step:
                    req.with_context(
                        care_skip_attachment_validation=True,
                    ).action_advance_step()
        return True

    def _send_customer_assignee_sms(self):
        for req in self.filtered(lambda r: r.user_id and r.state == 'in_progress'):
            step = req.current_step_id
            if not step or not step.send_assignee_customer_sms:
                continue
            partner = req.partner_id
            number = req._get_partner_sms_number(partner)
            if not number:
                continue
            assignee = req.user_id
            ap = assignee.partner_id
            pinfo = ap._sms_get_recipients_info().get(ap.id, {})
            phone = pinfo.get('sanitized') or pinfo.get('number') or ap.phone or ''
            body = (step.assignee_customer_sms_body or '').replace(
                '{partner_name}', partner.name or ''
            ).replace('{request_name}', req.name or '').replace(
                '{assignee_name}', assignee.name or ''
            ).replace('{assignee_phone}', phone).replace(
                '{assignee_link}', req._get_assignee_profile_url()
            ).replace(
                '{visit_schedule}', req.visit_schedule_display or ''
            )
            sms = self.env['sms.sms'].sudo().create({
                'number': number, 'body': body, 'partner_id': partner.id,
            })
            try:
                sms.send()
            except Exception:
                pass

    def action_customer_reject_assignee(self):
        for req in self.filtered(lambda r: r.state == 'in_progress' and r.user_id):
            step = req.current_step_id
            if not step or not step.team_acceptance_mode:
                raise UserError(_('This request is not in team acceptance mode.'))
            old = req.user_id
            req.assignment_offer_ids.filtered(
                lambda o: o.step_id == step and o.user_id == old
            ).write({'state': 'cancelled'})
            req.with_context(change_assignee_wizard=True).write({
                'user_id': False,
                'assignee_confirmed': False,
            })
            req.message_post(body=_('Customer rejected provider %s.') % old.name)
            req._create_team_assignment_offers(step)
            if step.send_team_sms:
                req._send_team_assignment_sms(step)
        return True

    def customer_can_cancel_request(self):
        self.ensure_one()
        return bool(
            self.state in ('draft', 'in_progress')
            and self.current_step_id
            and self.current_step_id.allow_customer_cancel
        )

    def action_customer_cancel_request(self):
        for req in self.filtered(lambda r: r.state not in ('done', 'cancelled')):
            if not req.customer_can_cancel_request():
                raise UserError(_('Customer cancellation is not allowed at the current step.'))
            req._move_to_cancel_step()
        return True

    def _get_team_users(self, team):
        users = team.member_ids
        if team.leader_id:
            users |= team.leader_id
        return users

    def _create_team_assignment_offers(self, step):
        self.ensure_one()
        Offer = self.env['care.request.assignment.offer'].sudo()
        team = self.team_id or step.auto_team_id
        if not team:
            return
        self.assignment_offer_ids.filtered(
            lambda o: o.step_id == step and o.state == 'pending'
        ).write({'state': 'cancelled'})
        if step.auto_user_id:
            self.write({
                'user_id': step.auto_user_id.id,
                'assignee_confirmed': True,
            })
            return
        if not step.team_acceptance_mode:
            return
        self.write({'user_id': False, 'assignee_confirmed': False})
        team_users = self._get_team_users(team)
        if not team_users:
            return
        for user in team_users:
            Offer.create({
                'request_id': self.id,
                'step_id': step.id,
                'team_id': team.id,
                'user_id': user.id,
                'state': 'pending',
            })

    def _send_team_assignment_sms(self, step):
        self.ensure_one()
        if not step.send_team_sms:
            return
        team = self.team_id or step.auto_team_id
        if not team:
            return
        body_template = step.team_sms_body or ''
        team_users = self._get_team_users(team)
        if not team_users:
            return
        for user in team_users:
            partner = user.partner_id
            number = self._get_partner_sms_number(partner)
            if not number:
                self.message_post(
                    body=_('Could not send SMS to %s: no phone number on file.')
                    % user.name,
                    subtype_xmlid='mail.mt_note',
                )
                continue
            body = self._render_team_sms_body(body_template, step, user)
            sms = self.env['sms.sms'].sudo().create({
                'number': number,
                'body': body,
                'partner_id': partner.id,
            })
            try:
                sms.send()
                offers = self.assignment_offer_ids.filtered(
                    lambda o: o.user_id == user and o.step_id == step
                )
                offers.write({'sms_sent': True})
            except Exception:
                self.message_post(
                    body=_('Failed to send SMS to %s') % user.name,
                    subtype_xmlid='mail.mt_note',
                )

    def _render_team_sms_body(self, template, step, user):
        self.ensure_one()
        values = {
            'partner_name': self.partner_id.name or '',
            'patient_name': self.patient_full_name or self.partner_id.name or '',
            'request_name': self.name or '',
            'step_name': step.name or '',
            'service_name': self.product_id.display_name or '',
            'user_name': user.name or '',
            'team_name': (self.team_id or step.auto_team_id).name if (self.team_id or step.auto_team_id) else '',
        }
        body = template
        for key, val in values.items():
            body = body.replace('{%s}' % key, val)
        return body

    def _validate_step_requirements(self):
        super()._validate_step_requirements()
        for req in self:
            step = req.current_step_id
            if step and step.team_acceptance_mode and not step.auto_user_id and not req.user_id:
                raise UserError(
                    _('A team member must accept the request before step "%s".')
                    % step.name
                )

    def _on_step_enter(self, step):
        super()._on_step_enter(step)
        for req in self:
            if step.team_acceptance_mode:
                req._create_team_assignment_offers(step)
            if step.send_team_sms:
                req._send_team_assignment_sms(step)
