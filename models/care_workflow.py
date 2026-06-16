from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CareWorkflowTemplate(models.Model):
    _name = 'care.workflow.template'
    _description = 'Care Workflow Template'
    _order = 'name'

    name = fields.Char(string='Workflow Name', required=True, translate=True)
    active = fields.Boolean(default=True)
    category_id = fields.Many2one(
        'care.request.category',
        string='Category',
        ondelete='restrict',
    )
    description = fields.Text(string='Description')
    step_ids = fields.One2many(
        'care.workflow.step',
        'workflow_id',
        string='Steps',
        copy=True,
    )
    step_count = fields.Integer(compute='_compute_step_count')

    @api.depends('step_ids')
    def _compute_step_count(self):
        for workflow in self:
            workflow.step_count = len(workflow.step_ids)

    def get_first_step(self):
        self.ensure_one()
        return self.step_ids.sorted('sequence').filtered(
            lambda s: not s.is_cancel_step
        )[:1]


class CareWorkflowStep(models.Model):
    _name = 'care.workflow.step'
    _description = 'Care Workflow Step'
    _order = 'workflow_id, sequence, id'

    name = fields.Char(string='Step Name', required=True, translate=True)
    workflow_id = fields.Many2one(
        'care.workflow.template',
        string='Workflow',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    description = fields.Text(string='Internal Notes')
    portal_instruction = fields.Html(
        string='Customer Instructions',
        translate=True,
        help='Text shown to the customer in the portal for this step.',
    )
    requires_attachment = fields.Boolean(
        string='Requires Attachment',
        help='At least one document must be uploaded before moving to the next step.',
    )
    allow_portal_upload = fields.Boolean(
        string='Portal Upload',
        default=True,
    )
    allow_portal_advance = fields.Boolean(
        string='Portal Advance',
        help='The customer can move to the next step in the portal when conditions are met.',
    )
    consumes_quota = fields.Boolean(
        string='Consumes Quota',
        help='Entering this step consumes one unit from the service entitlement.',
    )
    is_cancel_step = fields.Boolean(
        string='Cancel Step',
        help='Clicking cancel moves the request to this step.',
    )
    allow_create_invoice = fields.Boolean(
        string='Allow Create Invoice',
        help='Shows the create invoice action in the provider portal and backend on this workflow step.',
    )
    allow_provider_complete = fields.Boolean(
        string='Provider Complete Button',
        help='The provider can mark the service as completed from the portal (move to next step).',
    )
    allow_provider_cancel = fields.Boolean(
        string='Provider Cancel Process Button',
        help='The provider can cancel the request from the portal with a cancellation note.',
    )
    allow_customer_cancel = fields.Boolean(
        string='Customer Cancel Request Button',
        help='The customer can cancel the entire request from the portal at this step.',
    )
    invoice_product_id = fields.Many2one(
        'product.product',
        string='Default Invoice Product',
        ondelete='set null',
    )
    send_sms = fields.Boolean(string='Send SMS to Customer', default=True)
    sms_body = fields.Text(
        string='Customer SMS Text',
        default=(
            'Dear {partner_name},\n'
            'Request {request_name} is at step "{step_name}".\n'
            'Service: {service_name}'
        ),
        help='Variables: {partner_name}, {request_name}, {step_name}, {service_name}, {package_name}, {visit_schedule}',
    )
    send_team_sms = fields.Boolean(
        string='Send SMS to Team',
        help='Send SMS to team members (e.g. assignment step).',
    )
    team_sms_body = fields.Text(
        string='Team SMS Text',
        default=(
            'Dear {user_name},\n'
            'Request {request_name} — Patient: {patient_name}\n'
            'Step: {step_name} — Team: {team_name}\n'
            'Please accept the request in the system.'
        ),
        help='Variables: {user_name}, {request_name}, {patient_name}, {step_name}, {team_name}, {service_name}',
    )
    team_acceptance_mode = fields.Boolean(
        string='Team Acceptance (First Responder)',
        help='Like ride-hailing: SMS team members; the first to accept becomes the assignee.',
    )
    is_provider_accepted_status = fields.Boolean(
        string='Provider Accepted Status',
        help='Requests at this step are considered for provider visit schedule overlap checks.',
    )
    requires_visit_schedule = fields.Boolean(
        string='Visit Schedule on Acceptance',
        help='The provider must enter visit date and time window when accepting.',
    )
    send_assignee_customer_sms = fields.Boolean(
        string='Assignee SMS to Customer',
        default=True,
    )
    assignee_customer_sms_body = fields.Text(
        string='Assignee SMS Text',
        default=(
            'Dear {partner_name},\n'
            'Request {request_name} was accepted by {assignee_name}.\n'
            'Visit time: {visit_schedule}\n'
            'Contact: {assignee_phone}\n'
            'Profile: {assignee_link}'
        ),
    )
    auto_team_id = fields.Many2one(
        'care.team',
        string='Auto-assign Team',
        ondelete='set null',
    )
    auto_user_id = fields.Many2one(
        'res.users',
        string='Auto-assign User',
        ondelete='set null',
        domain="[('id', 'in', auto_team_member_ids)]",
    )
    auto_team_member_ids = fields.Many2many(
        'res.users',
        compute='_compute_auto_team_member_ids',
    )
    action_ids = fields.One2many(
        'care.workflow.action',
        'step_id',
        string='Additional Actions',
    )

    @api.depends('auto_team_id.member_ids', 'auto_team_id.leader_id')
    def _compute_auto_team_member_ids(self):
        for step in self:
            members = step.auto_team_id.member_ids
            if step.auto_team_id.leader_id:
                members |= step.auto_team_id.leader_id
            step.auto_team_member_ids = members

    @api.constrains('is_cancel_step', 'workflow_id')
    def _check_single_cancel_step(self):
        for step in self.filtered('is_cancel_step'):
            others = step.workflow_id.step_ids.filtered(
                lambda s: s.id != step.id and s.is_cancel_step
            )
            if others:
                raise ValidationError(
                    _('Only one step per workflow can be marked as the cancel step.')
                )

    @api.constrains('is_provider_accepted_status', 'workflow_id')
    def _check_single_provider_accepted_step(self):
        for step in self:
            if not step.is_provider_accepted_status:
                continue
            others = step.workflow_id.step_ids.filtered(
                lambda s: s.id != step.id and s.is_provider_accepted_status
            )
            if others:
                raise ValidationError(
                    _('Only one step per workflow can be marked as provider accepted status.')
                )

    @api.constrains('consumes_quota', 'workflow_id')
    def _check_single_quota_step(self):
        for step in self:
            if not step.consumes_quota:
                continue
            others = step.workflow_id.step_ids.filtered(
                lambda s: s.id != step.id and s.consumes_quota
            )
            if others:
                raise ValidationError(
                    _('Only one step per workflow can consume quota.')
                )


class CareWorkflowAction(models.Model):
    _name = 'care.workflow.action'
    _description = 'Workflow Step Action'
    _order = 'step_id, sequence, id'

    name = fields.Char(string='Name', required=True)
    step_id = fields.Many2one(
        'care.workflow.step',
        string='Step',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    trigger = fields.Selection(
        [
            ('on_enter', 'On Enter'),
            ('on_exit', 'On Exit'),
        ],
        string='Trigger',
        required=True,
        default='on_enter',
    )
    action_type = fields.Selection(
        [
            ('assign_team', 'Assign Team'),
            ('assign_user', 'Assign User'),
            ('email', 'Send Email'),
            ('activity', 'Create Activity'),
        ],
        string='Action Type',
        required=True,
    )
    team_id = fields.Many2one('care.team', string='Team')
    user_id = fields.Many2one('res.users', string='User')
    email_template_id = fields.Many2one('mail.template', string='Email Template')
    activity_summary = fields.Char(string='Activity Summary')
    activity_note = fields.Text(string='Activity Note')

    def run_on_request(self, request):
        self.ensure_one()
        if self.action_type == 'assign_team' and self.team_id:
            request.team_id = self.team_id
        elif self.action_type == 'assign_user' and self.user_id:
            request.user_id = self.user_id
            if self.team_id:
                request.team_id = self.team_id
        elif self.action_type == 'email' and self.email_template_id:
            self.email_template_id.send_mail(request.id, force_send=True)
        elif self.action_type == 'activity' and self.user_id:
            request.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.user_id.id,
                summary=self.activity_summary or self.name,
                note=self.activity_note or '',
            )
