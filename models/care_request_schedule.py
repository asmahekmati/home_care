# -*- coding: utf-8 -*-
"""زمان‌بندی حضور پذیرنده و کنترل همپوشانی."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class CareServiceRequestSchedule(models.Model):
    _inherit = 'care.service.request'

    preferred_datetime_start = fields.Datetime(
        string='شروع بازه ترجیحی',
        tracking=True,
    )
    preferred_datetime_end = fields.Datetime(
        string='پایان بازه ترجیحی',
        tracking=True,
    )
    preferred_schedule_display = fields.Char(
        string='بازه ترجیحی',
        compute='_compute_preferred_schedule_display',
    )
    provider_complete_note = fields.Text(string='توضیحات تکمیل پذیرنده')
    provider_cancel_note = fields.Text(string='توضیحات لغو پذیرنده')

    visit_datetime_start = fields.Datetime(
        string='شروع حضور',
        tracking=True,
    )
    visit_datetime_end = fields.Datetime(
        string='پایان حضور',
        tracking=True,
    )
    visit_schedule_display = fields.Char(
        string='بازه حضور',
        compute='_compute_visit_schedule_display',
    )

    @api.depends(
        'preferred_datetime_start', 'preferred_datetime_end', 'preferred_datetime',
    )
    def _compute_preferred_schedule_display(self):
        for req in self:
            start = req.preferred_datetime_start or req.preferred_datetime
            end = req.preferred_datetime_end
            if start and end:
                start_dt = fields.Datetime.context_timestamp(req, start)
                end_dt = fields.Datetime.context_timestamp(req, end)
                req.preferred_schedule_display = '%s — %s' % (
                    start_dt.strftime('%Y/%m/%d %H:%M'),
                    end_dt.strftime('%H:%M'),
                )
            elif start:
                start_dt = fields.Datetime.context_timestamp(req, start)
                req.preferred_schedule_display = start_dt.strftime('%Y/%m/%d %H:%M')
            else:
                req.preferred_schedule_display = False

    @api.depends('visit_datetime_start', 'visit_datetime_end')
    def _compute_visit_schedule_display(self):
        for req in self:
            if req.visit_datetime_start and req.visit_datetime_end:
                start = fields.Datetime.context_timestamp(req, req.visit_datetime_start)
                end = fields.Datetime.context_timestamp(req, req.visit_datetime_end)
                req.visit_schedule_display = '%s — %s' % (
                    start.strftime('%Y/%m/%d %H:%M'),
                    end.strftime('%H:%M'),
                )
            elif req.visit_datetime_start:
                start = fields.Datetime.context_timestamp(req, req.visit_datetime_start)
                req.visit_schedule_display = start.strftime('%Y/%m/%d %H:%M')
            else:
                req.visit_schedule_display = False

    @api.constrains('preferred_datetime_start', 'preferred_datetime_end')
    def _check_preferred_datetime_order(self):
        for req in self:
            if req.preferred_datetime_start and req.preferred_datetime_end:
                if req.preferred_datetime_end <= req.preferred_datetime_start:
                    raise ValidationError(
                        _('پایان بازه ترجیحی باید بعد از شروع آن باشد.')
                    )

    @api.constrains('visit_datetime_start', 'visit_datetime_end')
    def _check_visit_datetime_order(self):
        for req in self:
            if req.visit_datetime_start and req.visit_datetime_end:
                if req.visit_datetime_end <= req.visit_datetime_start:
                    raise ValidationError(
                        _('زمان پایان حضور باید بعد از زمان شروع باشد.')
                    )

    @api.model
    def _get_provider_accepted_step_ids(self):
        return self.env['care.workflow.step'].search([
            ('is_provider_accepted_status', '=', True),
        ]).ids

    def _check_visit_overlap(self, user, visit_start, visit_end):
        """بررسی همپوشانی با سایر درخواست‌های پذیرفته‌شده توسط همین پذیرنده."""
        self.ensure_one()
        if not visit_start or not visit_end:
            raise UserError(_('تاریخ و بازه زمانی حضور الزامی است.'))
        if visit_end <= visit_start:
            raise UserError(_('زمان پایان حضور باید بعد از زمان شروع باشد.'))

        accepted_step_ids = self._get_provider_accepted_step_ids()
        domain = [
            ('user_id', '=', user.id),
            ('id', '!=', self.id),
            ('state', '=', 'in_progress'),
            ('visit_datetime_start', '!=', False),
            ('visit_datetime_end', '!=', False),
        ]
        if accepted_step_ids:
            domain.append(('current_step_id', 'in', accepted_step_ids))
        else:
            domain.append(('assignee_confirmed', '=', True))

        for other in self.search(domain):
            if visit_start < other.visit_datetime_end and visit_end > other.visit_datetime_start:
                raise UserError(_(
                    'بازه زمانی حضور با درخواست «%s» (%s) همپوشانی دارد.'
                ) % (other.name, other.visit_schedule_display or ''))

    def _check_visit_within_preferred(self, visit_start, visit_end):
        """بازه حضور پذیرنده باید داخل بازه درخواستی مشتری باشد."""
        self.ensure_one()
        pref_start = self.preferred_datetime_start or self.preferred_datetime
        pref_end = self.preferred_datetime_end
        if not pref_start or not pref_end:
            return
        if visit_start < pref_start or visit_end > pref_end:
            raise UserError(_(
                'بازه زمانی حضور باید داخل بازه درخواستی مشتری (%s) باشد.'
            ) % (self.preferred_schedule_display or ''))

    @api.model
    def action_view_my_provider_tasks(self):
        user = self.env.user
        accepted_step_ids = self._get_provider_accepted_step_ids()
        domain = [
            ('user_id', '=', user.id),
            ('state', '=', 'in_progress'),
            ('visit_datetime_start', '!=', False),
        ]
        if accepted_step_ids:
            domain.append(('current_step_id', 'in', accepted_step_ids))
        return {
            'type': 'ir.actions.act_window',
            'name': _('کارهای من'),
            'res_model': 'care.service.request',
            'view_mode': 'list,form,calendar',
            'domain': domain,
            'context': {'default_user_id': user.id},
        }
