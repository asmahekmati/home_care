# -*- coding: utf-8 -*-
"""Patient and insurance fields on care service requests."""

from odoo import api, fields, models, _


class CareServiceRequestPatient(models.Model):
    _inherit = 'care.service.request'

    patient_relation = fields.Selection(
        [
            ('self', 'For Myself'),
            ('other', 'For Someone Else'),
        ],
        string='Request For',
        default='self',
        required=True,
        tracking=True,
    )
    patient_first_name = fields.Char(string='Patient First Name', tracking=True)
    patient_last_name = fields.Char(string='Patient Last Name', tracking=True)
    patient_national_id = fields.Char(string='National ID', tracking=True)
    patient_full_name = fields.Char(
        string='Patient Full Name',
        compute='_compute_patient_full_name',
        store=True,
        tracking=True,
    )
    patient_case_code = fields.Char(string='Case / Patient Code', tracking=True)
    patient_age = fields.Integer(string='Age')
    patient_gender = fields.Selection(
        [
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
        ],
        string='Gender',
        tracking=True,
    )
    patient_phone = fields.Char(string='Patient Phone', tracking=True)
    patient_mobile = fields.Char(string='Patient Mobile', tracking=True)
    patient_address = fields.Text(string='Patient Address')

    insurance_primary_id = fields.Many2one(
        'care.insurance',
        string='Primary Insurance',
        domain=[('insurance_type', '=', 'primary')],
        tracking=True,
    )
    insurance_primary_name = fields.Char(
        string='Primary Insurance Name',
        related='insurance_primary_id.name',
        store=True,
        readonly=True,
    )
    insurance_primary_number = fields.Char(string='Insurance / Booklet Number', tracking=True)
    insurance_primary_policy = fields.Char(string='Contract / Insured Number', tracking=True)

    insurance_supplementary_id = fields.Many2one(
        'care.insurance',
        string='Supplementary Insurance',
        domain=[('insurance_type', '=', 'supplementary')],
        tracking=True,
    )
    insurance_supplementary_name = fields.Char(
        string='Supplementary Insurance Name',
        related='insurance_supplementary_id.name',
        store=True,
        readonly=True,
    )
    insurance_supplementary_number = fields.Char(string='Supplementary Insurance Number', tracking=True)
    insurance_supplementary_policy = fields.Char(string='Supplementary Contract Number', tracking=True)

    assignment_offer_ids = fields.One2many(
        'care.request.assignment.offer',
        'request_id',
        string='Assignment Offers',
    )
    can_current_user_accept = fields.Boolean(
        compute='_compute_can_current_user_accept',
    )
    pending_assignment_count = fields.Integer(
        compute='_compute_pending_assignment_count',
    )
    activity_count = fields.Integer(
        string='Activity Count',
        compute='_compute_activity_count',
    )
    assignee_name = fields.Char(related='user_id.name', string='Provider Name')
    assignee_phone = fields.Char(compute='_compute_assignee_phone')
    assignee_image_url = fields.Char(compute='_compute_assignee_image_url')
    assignee_team_name = fields.Char(related='team_id.name', string='Provider Team')
    can_customer_reject_assignee = fields.Boolean(compute='_compute_can_customer_reject_assignee')
    can_step_create_invoice = fields.Boolean(compute='_compute_can_step_create_invoice')
    can_provider_complete_service = fields.Boolean(compute='_compute_can_provider_complete_service')
    can_provider_cancel_service = fields.Boolean(compute='_compute_can_provider_cancel_service')
    can_customer_cancel_request = fields.Boolean(compute='_compute_can_customer_cancel_request')

    @api.depends('user_id', 'user_id.partner_id.phone')
    def _compute_assignee_phone(self):
        for req in self:
            partner = req.user_id.partner_id if req.user_id else False
            req.assignee_phone = partner.phone if partner else False

    @api.depends('user_id', 'user_id.partner_id')
    def _compute_assignee_image_url(self):
        for req in self:
            partner = req.user_id.partner_id if req.user_id else False
            req.assignee_image_url = (
                '/web/image/res.partner/%s/avatar_128' % partner.id
                if partner else False
            )

    @api.depends('user_id', 'state', 'current_step_id.team_acceptance_mode')
    def _compute_can_customer_reject_assignee(self):
        for req in self:
            req.can_customer_reject_assignee = bool(
                req.state == 'in_progress' and req.user_id
                and req.current_step_id and req.current_step_id.team_acceptance_mode
            )

    @api.depends('user_id', 'state', 'current_step_id.allow_provider_complete')
    def _compute_can_provider_complete_service(self):
        user = self.env.user
        for req in self:
            req.can_provider_complete_service = bool(
                req.state == 'in_progress'
                and req.user_id == user
                and req.current_step_id
                and req.current_step_id.allow_provider_complete
            )

    @api.depends('user_id', 'state', 'current_step_id.allow_provider_cancel')
    def _compute_can_provider_cancel_service(self):
        user = self.env.user
        for req in self:
            req.can_provider_cancel_service = bool(
                req.state == 'in_progress'
                and req.user_id == user
                and req.current_step_id
                and req.current_step_id.allow_provider_cancel
            )

    @api.depends('state', 'current_step_id.allow_customer_cancel')
    def _compute_can_customer_cancel_request(self):
        for req in self:
            req.can_customer_cancel_request = bool(
                req.state in ('draft', 'in_progress')
                and req.current_step_id
                and req.current_step_id.allow_customer_cancel
            )

    @api.depends('current_step_id.allow_create_invoice', 'state')
    def _compute_can_step_create_invoice(self):
        for req in self:
            req.can_step_create_invoice = bool(
                req.state in ('draft', 'in_progress')
                and req.current_step_id and req.current_step_id.allow_create_invoice
            )

    @api.depends('activity_ids')
    def _compute_activity_count(self):
        for req in self:
            req.activity_count = len(req.activity_ids)

    def action_view_activities(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Activities'),
            'res_model': 'mail.activity',
            'view_mode': 'list,form',
            'domain': [
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
            ],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }

    @api.depends('patient_first_name', 'patient_last_name')
    def _compute_patient_full_name(self):
        for req in self:
            parts = [p for p in (req.patient_first_name, req.patient_last_name) if p]
            req.patient_full_name = ' '.join(parts) if parts else False

    @api.depends('assignment_offer_ids.state', 'assignment_offer_ids.user_id', 'user_id', 'current_step_id')
    def _compute_can_current_user_accept(self):
        user = self.env.user
        for req in self:
            req.can_current_user_accept = bool(
                req.current_step_id
                and req.current_step_id.team_acceptance_mode
                and not req.user_id
                and req.assignment_offer_ids.filtered(
                    lambda o: o.user_id == user
                    and o.state == 'pending'
                    and o.step_id == req.current_step_id
                )
            )

    @api.depends('assignment_offer_ids.state', 'current_step_id')
    def _compute_pending_assignment_count(self):
        for req in self:
            req.pending_assignment_count = len(
                req.assignment_offer_ids.filtered(
                    lambda o: o.state == 'pending' and o.step_id == req.current_step_id
                )
            )

    @api.onchange('patient_relation', 'partner_id')
    def _onchange_patient_relation(self):
        if self.patient_relation == 'self' and self.partner_id:
            self._prefill_patient_from_partner()
        elif self.patient_relation == 'other':
            self.patient_first_name = False
            self.patient_last_name = False
            self.patient_national_id = False
            self.patient_case_code = False
            self.patient_age = False
            self.patient_gender = False
            self.patient_phone = False
            self.patient_mobile = False
            self.patient_address = False

    def _prefill_patient_from_partner(self):
        self.ensure_one()
        if not self.partner_id:
            return
        name_parts = (self.partner_id.name or '').strip().split(' ', 1)
        self.patient_first_name = name_parts[0] if name_parts else False
        self.patient_last_name = name_parts[1] if len(name_parts) > 1 else False
        self.patient_phone = self.partner_id.phone
        self.patient_mobile = self.partner_id.phone
        self.patient_address = (
            self.partner_id.contact_address_inline or self.partner_id.street
        )
        if hasattr(self.partner_id, 'vat') and self.partner_id.vat:
            self.patient_national_id = self.partner_id.vat

    @api.onchange('partner_id')
    def _onchange_partner_prefill_patient(self):
        if self.patient_relation == 'self' and self.partner_id:
            self._prefill_patient_from_partner()
