from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class CareServiceRequest(models.Model):
    _name = 'care.service.request'
    _description = 'Care Service Request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Request Number',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    request_type = fields.Selection(
        [
            ('package', 'From Package'),
            ('standalone', 'Standalone Purchase'),
        ],
        string='Request Type',
        required=True,
        default='package',
        tracking=True,
    )
    entitlement_id = fields.Many2one(
        'care.package.entitlement',
        string='Package Entitlement',
        ondelete='restrict',
        tracking=True,
        index=True,
        domain="[('id', 'in', entitlement_domain_ids)]",
    )
    entitlement_domain_ids = fields.Many2many(
        'care.package.entitlement',
        compute='_compute_filter_domains',
        string='Allowed Entitlements',
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Order Line',
        ondelete='restrict',
        tracking=True,
        index=True,
        domain="[('id', 'in', sale_order_line_domain_ids)]",
    )
    sale_order_line_domain_ids = fields.Many2many(
        'sale.order.line',
        compute='_compute_filter_domains',
        string='Allowed Order Lines',
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        related='sale_order_line_id.order_id',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Service',
        required=True,
        ondelete='restrict',
        domain="[('id', 'in', product_domain_ids)]",
        tracking=True,
    )
    product_domain_ids = fields.Many2many(
        'product.product',
        compute='_compute_filter_domains',
        string='Allowed Services',
    )
    category_id = fields.Many2one(
        'care.request.category',
        string='Category',
        related='product_id.request_category_id',
        store=True,
        readonly=True,
        tracking=True,
    )
    workflow_id = fields.Many2one(
        'care.workflow.template',
        string='Workflow',
        ondelete='restrict',
        tracking=True,
    )
    current_step_id = fields.Many2one(
        'care.workflow.step',
        string='Current Step',
        ondelete='restrict',
        tracking=True,
    )
    team_id = fields.Many2one(
        'care.team',
        string='Team',
        ondelete='set null',
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Assignee',
        ondelete='set null',
        tracking=True,
        domain="[('id', 'in', team_member_ids)]",
    )
    team_member_ids = fields.Many2many(
        'res.users',
        compute='_compute_team_member_ids',
    )
    preferred_datetime = fields.Datetime(string='Preferred Time', tracking=True)
    description = fields.Text(string='Description')
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    quota_consumed = fields.Boolean(
        string='Quota Consumed',
        default=False,
        copy=False,
    )
    document_ids = fields.One2many(
        'care.request.document',
        'request_id',
        string='Documents',
    )
    step_history_ids = fields.One2many(
        'care.request.step.history',
        'request_id',
        string='Step History',
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    portal_step_instruction = fields.Html(
        related='current_step_id.portal_instruction',
        readonly=True,
    )
    can_portal_advance = fields.Boolean(
        compute='_compute_portal_flags',
    )
    can_portal_upload = fields.Boolean(
        compute='_compute_portal_flags',
    )
    attachment_missing = fields.Boolean(
        compute='_compute_portal_flags',
    )
    advance_step_label = fields.Char(
        string='Advance Step Label',
        compute='_compute_advance_step_label',
    )

    @api.depends('team_id.member_ids', 'team_id.leader_id')
    def _compute_team_member_ids(self):
        for req in self:
            members = req.team_id.member_ids if req.team_id else self.env['res.users']
            if req.team_id and req.team_id.leader_id:
                members |= req.team_id.leader_id
            req.team_member_ids = members

    @api.depends(
        'current_step_id',
        'current_step_id.requires_attachment',
        'current_step_id.allow_portal_advance',
        'current_step_id.allow_portal_upload',
        'document_ids',
        'document_ids.step_id',
        'state',
    )
    def _compute_portal_flags(self):
        for req in self:
            step = req.current_step_id
            req.can_portal_upload = bool(
                step and step.allow_portal_upload and req.state == 'in_progress'
            )
            req.can_portal_advance = bool(
                step and step.allow_portal_advance and req.state == 'in_progress'
            )
            if step and step.requires_attachment:
                docs = req.document_ids.filtered(lambda d: d.step_id == step)
                req.attachment_missing = not docs
            else:
                req.attachment_missing = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'care.service.request'
                ) or 'New'
            self._apply_product_defaults(vals)
        records = super().create(vals_list)
        for record in records:
            if record.state == 'in_progress' and record.current_step_id:
                record._on_step_enter(record.current_step_id)
        return records

    def write(self, vals):
        if vals.get('product_id'):
            self._apply_product_defaults(vals)
        res = super().write(vals)
        if {'partner_id', 'request_type', 'entitlement_id', 'sale_order_line_id'} & set(vals):
            for req in self:
                clear_vals = req._get_incompatible_clear_vals()
                if clear_vals:
                    super(CareServiceRequest, req).write(clear_vals)
        return res

    @api.model
    def _apply_product_defaults(self, vals):
        product = self.env['product.product'].browse(vals['product_id']) if vals.get('product_id') else False
        if not product:
            return
        if not vals.get('workflow_id') and product.request_category_id.workflow_id:
            vals['workflow_id'] = product.request_category_id.workflow_id.id
        if not vals.get('team_id'):
            if product.product_tmpl_id.default_care_team_id:
                vals['team_id'] = product.product_tmpl_id.default_care_team_id.id
            elif product.request_category_id.default_team_id:
                vals['team_id'] = product.request_category_id.default_team_id.id

    @api.model
    def _partners_match(self, partner, other_partner):
        if not partner or not other_partner:
            return False
        return bool(self.env['res.partner'].search_count([
            ('id', '=', other_partner.id),
            ('id', 'child_of', partner.commercial_partner_id.id),
        ], limit=1))

    @api.model
    def _get_entitlement_ids_for_partner(self, partner):
        if not partner:
            return []
        today = fields.Date.today()
        entitlements = self.env['care.package.entitlement'].search([
            ('partner_id', 'child_of', partner.commercial_partner_id.id),
            ('state', '=', 'active'),
            ('date_start', '<=', today),
            ('date_end', '>=', today),
        ])
        return entitlements.filtered(
            lambda ent: ent.get_available_service_products()
        ).ids

    @api.model
    def _get_product_ids_for_request(self, partner, request_type, entitlement=False, sale_order_line=False):
        Product = self.env['product.product']
        if request_type == 'package':
            if entitlement:
                return entitlement.get_available_service_products().ids
            if partner:
                products = Product
                entitlements = self.env['care.package.entitlement'].browse(
                    self._get_entitlement_ids_for_partner(partner)
                )
                for ent in entitlements:
                    products |= ent.get_available_service_products()
                return products.ids
        elif request_type == 'standalone':
            if sale_order_line:
                return [sale_order_line.product_id.id]
            if partner:
                return self._get_available_standalone_lines(partner).mapped('product_id').ids
        return []

    @api.depends(
        'partner_id',
        'partner_id.commercial_partner_id',
        'request_type',
        'entitlement_id',
        'sale_order_line_id',
    )
    def _compute_filter_domains(self):
        Entitlement = self.env['care.package.entitlement']
        Line = self.env['sale.order.line']
        Product = self.env['product.product']
        for req in self:
            if req.request_type == 'package' and req.partner_id:
                req.entitlement_domain_ids = Entitlement.browse(
                    req._get_entitlement_ids_for_partner(req.partner_id)
                )
            else:
                req.entitlement_domain_ids = Entitlement

            if req.request_type == 'standalone' and req.partner_id:
                req.sale_order_line_domain_ids = req._get_available_standalone_lines(req.partner_id)
            else:
                req.sale_order_line_domain_ids = Line

            product_ids = req._get_product_ids_for_request(
                req.partner_id,
                req.request_type,
                req.entitlement_id,
                req.sale_order_line_id,
            )
            req.product_domain_ids = Product.browse(product_ids) if product_ids else Product

    def _get_incompatible_clear_vals(self):
        self.ensure_one()
        vals = {}
        if self.request_type == 'package':
            if self.sale_order_line_id:
                vals['sale_order_line_id'] = False
        elif self.entitlement_id:
            vals['entitlement_id'] = False

        if self.partner_id:
            if self.entitlement_id and not self._partners_match(
                self.partner_id, self.entitlement_id.partner_id
            ):
                vals['entitlement_id'] = False
            if self.sale_order_line_id and not self._partners_match(
                self.partner_id, self.sale_order_line_id.order_id.partner_id
            ):
                vals['sale_order_line_id'] = False

        allowed_product_ids = self._get_product_ids_for_request(
            self.partner_id,
            self.request_type,
            self.entitlement_id if 'entitlement_id' not in vals else False,
            self.sale_order_line_id if 'sale_order_line_id' not in vals else False,
        )
        if self.product_id and allowed_product_ids and self.product_id.id not in allowed_product_ids:
            vals['product_id'] = False
        return vals

    def _clear_incompatible_linked_fields(self):
        self.ensure_one()
        clear_vals = self._get_incompatible_clear_vals()
        for field, value in clear_vals.items():
            setattr(self, field, value)

    @api.onchange('partner_id', 'request_type', 'entitlement_id', 'sale_order_line_id')
    def _onchange_linked_fields(self):
        if self.entitlement_id:
            self.request_type = 'package'
            if not self.partner_id:
                self.partner_id = self.entitlement_id.partner_id
        if self.sale_order_line_id:
            self.request_type = 'standalone'
            if not self.partner_id:
                self.partner_id = self.sale_order_line_id.order_id.partner_id

        self._clear_incompatible_linked_fields()

        if self.request_type == 'standalone' and self.sale_order_line_id:
            self.product_id = self.sale_order_line_id.product_id

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if self.product_id.request_category_id.workflow_id:
                self.workflow_id = self.product_id.request_category_id.workflow_id
            if self.product_id.product_tmpl_id.default_care_team_id:
                self.team_id = self.product_id.product_tmpl_id.default_care_team_id
            elif self.product_id.request_category_id.default_team_id:
                self.team_id = self.product_id.request_category_id.default_team_id

    @api.constrains('partner_id', 'request_type', 'entitlement_id', 'sale_order_line_id', 'product_id')
    def _check_linked_fields(self):
        for req in self:
            if req.request_type == 'package':
                if req.entitlement_id and not req._partners_match(req.partner_id, req.entitlement_id.partner_id):
                    raise ValidationError(_('The selected package entitlement does not belong to this customer.'))
                if req.entitlement_id and req.product_id:
                    if req.product_id not in req.entitlement_id.get_available_service_products():
                        raise ValidationError(_('This service is not available in the selected package entitlement.'))
            elif req.request_type == 'standalone':
                if req.sale_order_line_id and not req._partners_match(
                    req.partner_id, req.sale_order_line_id.order_id.partner_id
                ):
                    raise ValidationError(_('The selected order line does not belong to this customer.'))
                if req.sale_order_line_id and req.product_id:
                    if req.product_id != req.sale_order_line_id.product_id:
                        raise ValidationError(_('The service must match the order line product.'))

    @api.constrains('product_id')
    def _check_product_category(self):
        for req in self:
            if req.product_id and not req.product_id.request_category_id:
                raise ValidationError(
                    _('Service "%s" has no request category. Configure it on the product first.')
                    % req.product_id.display_name
                )

    @api.constrains('team_id', 'user_id')
    def _check_user_in_team(self):
        for req in self:
            if req.user_id and req.team_id:
                members = req.team_id.member_ids
                if req.team_id.leader_id:
                    members |= req.team_id.leader_id
                if req.user_id not in members:
                    raise ValidationError(
                        _('The assignee must be a member of team "%s".')
                        % req.team_id.name
                    )

    @api.depends('state', 'workflow_id', 'current_step_id', 'product_id', 'category_id')
    def _compute_advance_step_label(self):
        for req in self:
            label = False
            if req.state == 'draft':
                workflow = req.workflow_id
                if not workflow and req.product_id:
                    workflow = req.product_id.request_category_id.workflow_id
                first_step = workflow.get_first_step() if workflow else False
                label = first_step.name if first_step else _('Start Workflow')
            elif req.state == 'in_progress' and req.current_step_id:
                next_step = req._get_next_step(req.current_step_id)
                label = next_step.name if next_step else _('Complete Request')
            req.advance_step_label = label

    def action_proceed_workflow(self):
        for req in self:
            if req.state == 'draft':
                req.action_start()
            elif req.state == 'in_progress':
                req.action_advance_step()

    def action_start(self):
        for req in self.filtered(lambda r: r.state == 'draft'):
            req._prepare_workflow()
            first_step = req.workflow_id.get_first_step()
            if not first_step:
                raise UserError(_('No workflow step is defined for this category.'))
            req.write({
                'state': 'in_progress',
                'current_step_id': first_step.id,
            })
            req._on_step_enter(first_step)

    def action_advance_step(self):
        for req in self.filtered(lambda r: r.state == 'in_progress'):
            req._validate_step_requirements()
            current = req.current_step_id
            if not current:
                raise UserError(_('Current step is not set.'))
            req._run_step_exit_actions(current)
            if current.consumes_quota:
                req._consume_quota()
            next_step = req._get_next_step(current)
            if next_step:
                req.current_step_id = next_step
                req._on_step_enter(next_step)
            else:
                req.state = 'done'
                req.message_post(body=_('Request completed successfully.'))

    def action_cancel(self):
        for req in self.filtered(lambda r: r.state not in ('done', 'cancelled')):
            req._move_to_cancel_step()

    def _get_cancel_step(self):
        self.ensure_one()
        workflow = self.workflow_id
        if not workflow and self.product_id:
            workflow = self.product_id.request_category_id.workflow_id
        if not workflow:
            return self.env['care.workflow.step']
        return workflow.step_ids.filtered('is_cancel_step')[:1]

    def _move_to_cancel_step(self):
        self.ensure_one()
        cancel_step = self._get_cancel_step()
        if cancel_step:
            old = self.current_step_id
            if old and old != cancel_step:
                self._run_step_exit_actions(old)
            self.write({
                'current_step_id': cancel_step.id,
                'state': 'cancelled',
            })
            if not old or old != cancel_step:
                self._on_step_enter(cancel_step)
        else:
            self.write({'state': 'cancelled'})

    def action_set_step(self, step):
        self.ensure_one()
        if step.workflow_id != self.workflow_id:
            raise UserError(_('The selected step does not belong to this request workflow.'))
        old = self.current_step_id
        if old:
            self._run_step_exit_actions(old)
        self.current_step_id = step
        if self.state == 'draft':
            self.state = 'in_progress'
        self._on_step_enter(step)

    def _prepare_workflow(self):
        self.ensure_one()
        if not self.category_id:
            self.category_id = self.product_id.request_category_id
        if not self.workflow_id:
            self.workflow_id = self.category_id.workflow_id
        if not self.workflow_id:
            raise UserError(
                _('No workflow is defined for category "%s".')
                % self.category_id.name
            )

    def _get_next_step(self, current_step):
        steps = self.workflow_id.step_ids.sorted('sequence').filtered(
            lambda s: not s.is_cancel_step
        )
        found = False
        for step in steps:
            if found:
                return step
            if step == current_step:
                found = True
        return self.env['care.workflow.step']

    def _validate_step_requirements(self):
        self.ensure_one()
        if self.env.context.get('care_skip_attachment_validation'):
            return
        step = self.current_step_id
        if step.requires_attachment:
            docs = self.document_ids.filtered(lambda d: d.step_id == step)
            if not docs:
                raise UserError(
                    _('Document upload is required at step "%s" before proceeding.')
                    % step.name
                )

    def _consume_quota(self):
        self.ensure_one()
        if self.quota_consumed:
            return
        if self.request_type == 'package':
            if not self.entitlement_id:
                raise UserError(_('Package entitlement is not set.'))
            self.entitlement_id.consume_service(self.product_id)
        elif self.request_type == 'standalone':
            if not self.sale_order_line_id:
                raise UserError(_('Order line is not set.'))
            line = self.sale_order_line_id
            used = self.search_count([
                ('sale_order_line_id', '=', line.id),
                ('quota_consumed', '=', True),
                ('id', '!=', self.id),
            ])
            if used >= line.product_uom_qty:
                raise UserError(_('The purchase quota for this service is exhausted.'))
        self.quota_consumed = True

    def _on_step_enter(self, step):
        self.ensure_one()
        if step.is_cancel_step:
            self.state = 'cancelled'
        self.env['care.request.step.history'].sudo().create({
            'request_id': self.id,
            'step_id': step.id,
            'entered_at': fields.Datetime.now(),
        })
        if step.auto_team_id:
            self.team_id = step.auto_team_id
        if step.auto_user_id:
            self.user_id = step.auto_user_id
        for action in step.action_ids.filtered(lambda a: a.trigger == 'on_enter'):
            action.run_on_request(self)
        if step.send_sms:
            self._send_step_sms(step)

    def _run_step_exit_actions(self, step):
        self.ensure_one()
        history = self.step_history_ids.filtered(
            lambda h: h.step_id == step and not h.exited_at
        )[:1]
        if history:
            history.sudo().exited_at = fields.Datetime.now()
        for action in step.action_ids.filtered(lambda a: a.trigger == 'on_exit'):
            action.run_on_request(self)

    def _get_partner_sms_number(self, partner):
        phone_info = partner._sms_get_recipients_info().get(partner.id, {})
        return phone_info.get('sanitized') or phone_info.get('number')

    def _send_step_sms(self, step):
        self.ensure_one()
        partner = self.partner_id
        number = self._get_partner_sms_number(partner)
        if not number:
            self.message_post(
                body=_('Could not send SMS: customer phone number is missing.'),
                subtype_xmlid='mail.mt_note',
            )
            return
        body = self._render_sms_body(step.sms_body or '', step)
        sms = self.env['sms.sms'].sudo().create({
            'number': number,
            'body': body,
            'partner_id': partner.id,
        })
        try:
            sms.send()
            self.message_post(
                body=_('SMS sent to customer: %s') % body,
                subtype_xmlid='mail.mt_note',
            )
        except Exception:
            self.message_post(
                body=_('Failed to send SMS to customer.'),
                subtype_xmlid='mail.mt_note',
            )

    def _render_sms_body(self, template, step):
        self.ensure_one()
        values = {
            'partner_name': self.partner_id.name or '',
            'request_name': self.name or '',
            'step_name': step.name or '',
            'service_name': self.product_id.display_name or '',
            'package_name': self.entitlement_id.package_product_id.display_name
            if self.entitlement_id else '',
        }
        body = template
        for key, val in values.items():
            body = body.replace('{%s}' % key, val)
        return body

    def _get_portal_return_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/my/care/requests/%s' % self.id,
            'target': 'self',
        }

    @api.model
    def _get_available_standalone_lines(self, partner):
        """Confirmed order lines with care services that still have quota."""
        lines = self.env['sale.order.line'].search([
            ('order_id.partner_id', 'child_of', partner.commercial_partner_id.id),
            ('order_id.state', '=', 'sale'),
            ('product_id.product_tmpl_id.is_care_service', '=', True),
            ('product_id.product_tmpl_id.is_care_package', '=', False),
        ])
        available = self.env['sale.order.line']
        for line in lines:
            used = self.search_count([
                ('sale_order_line_id', '=', line.id),
                ('quota_consumed', '=', True),
            ])
            pending = self.search_count([
                ('sale_order_line_id', '=', line.id),
                ('state', 'in', ('draft', 'in_progress')),
            ])
            remaining = line.product_uom_qty - used
            if remaining > 0 or pending > 0:
                available |= line
        return available


class CareRequestStepHistory(models.Model):
    _name = 'care.request.step.history'
    _description = 'Care Request Step History'
    _order = 'entered_at desc, id desc'

    request_id = fields.Many2one(
        'care.service.request',
        required=True,
        ondelete='cascade',
    )
    step_id = fields.Many2one(
        'care.workflow.step',
        required=True,
        ondelete='restrict',
    )
    entered_at = fields.Datetime(string='Entered', required=True)
    exited_at = fields.Datetime(string='Exited')
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
    )
