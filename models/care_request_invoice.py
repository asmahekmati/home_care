# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CareServiceRequestInvoice(models.Model):
    _inherit = 'care.service.request'

    invoice_ids = fields.Many2many(
        'account.move',
        'care_request_invoice_rel',
        'request_id',
        'invoice_id',
        string='Invoices',
        copy=False,
    )
    invoice_count = fields.Integer(compute='_compute_invoice_count')
    document_count = fields.Integer(compute='_compute_document_count')
    related_request_count = fields.Integer(compute='_compute_related_request_count')
    sale_order_count = fields.Integer(compute='_compute_sale_order_count')
    entitlement_count = fields.Integer(compute='_compute_entitlement_count')

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for req in self:
            req.invoice_count = len(req.invoice_ids)

    @api.depends('document_ids')
    def _compute_document_count(self):
        for req in self:
            req.document_count = len(req.document_ids)

    @api.depends('partner_id')
    def _compute_related_request_count(self):
        for req in self:
            if not req.partner_id:
                req.related_request_count = 0
                continue
            req.related_request_count = self.search_count([
                ('id', '!=', req.id),
                ('partner_id', 'child_of', req.partner_id.commercial_partner_id.id),
            ])

    @api.depends('sale_order_id')
    def _compute_sale_order_count(self):
        for req in self:
            req.sale_order_count = 1 if req.sale_order_id else 0

    @api.depends('entitlement_id')
    def _compute_entitlement_count(self):
        for req in self:
            req.entitlement_count = 1 if req.entitlement_id else 0

    def _compute_access_url(self):
        for req in self:
            req.access_url = '/my/care/requests/%s' % req.id

    def _get_assignee_profile_url(self):
        self.ensure_one()
        return '%s/my/care/requests/%s/assignee' % (
            self.get_base_url().rstrip('/'),
            self.id,
        )

    def action_create_step_invoice(self):
        self.ensure_one()
        step = self.current_step_id
        if not step or not step.allow_create_invoice:
            raise UserError(_('Invoice creation is not enabled on the current workflow step.'))
        if self.state == 'cancelled':
            raise UserError(_('The request has been cancelled.'))
        product = step.invoice_product_id or self.product_id
        move = self.env['account.move'].create(
            self._prepare_invoice_vals(product, step)
        )
        self.invoice_ids = [(4, move.id)]
        return self._action_view_invoices(move)

    def _prepare_invoice_vals(self, product, step):
        self.ensure_one()
        return {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'care_service_request_id': self.id,
            'care_workflow_step_id': step.id if step else False,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'quantity': 1.0,
                'name': _('Request %s — Step %s') % (self.name, step.name if step else ''),
            })],
        }

    def action_view_invoices(self):
        return self._action_view_invoices()

    def _action_view_invoices(self, invoices=False):
        self.ensure_one()
        invoices = invoices or self.invoice_ids
        action = self.env['ir.actions.actions']._for_xml_id(
            'account.action_move_out_invoice_type'
        )
        if len(invoices) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = invoices.id
        else:
            action['domain'] = [('id', 'in', invoices.ids)]
        action['context'] = {
            'default_move_type': 'out_invoice',
            'default_partner_id': self.partner_id.id,
            'default_care_service_request_id': self.id,
        }
        return action

    def action_view_related_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Related Requests'),
            'res_model': 'care.service.request',
            'view_mode': 'list,kanban,form,graph,pivot',
            'domain': [
                ('id', '!=', self.id),
                ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
            ],
            'context': {'default_partner_id': self.partner_id.id},
        }

    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('No related sales order found.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
        }

    def action_view_entitlement(self):
        self.ensure_one()
        if not self.entitlement_id:
            raise UserError(_('No package entitlement found.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'care.package.entitlement',
            'view_mode': 'form',
            'res_id': self.entitlement_id.id,
        }

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'care.request.document',
            'view_mode': 'list',
            'domain': [('request_id', '=', self.id)],
            'context': {'default_request_id': self.id},
        }

    def _filter_portal_customer_invoices(self, partner=None):
        """Invoices visible to the customer in the portal for this request."""
        self.ensure_one()
        partner = partner or self.env.user.partner_id
        return self.invoice_ids.filtered(
            lambda inv: inv.partner_id.commercial_partner_id == partner.commercial_partner_id
            and inv.state != 'cancel'
            and inv.move_type in ('out_invoice', 'out_refund', 'out_receipt')
        )

    portal_status_display = fields.Char(
        string='Status (Step)',
        compute='_compute_portal_status_display',
    )

    @api.depends('current_step_id', 'current_step_id.name', 'state')
    def _compute_portal_status_display(self):
        for req in self:
            if req.current_step_id:
                req.portal_status_display = req.current_step_id.name
            else:
                req.portal_status_display = dict(
                    req._fields['state'].selection
                ).get(req.state, req.state)

    def provider_can_create_invoice(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        step = self.current_step_id
        return bool(
            self.state == 'in_progress'
            and self.user_id == user
            and step
            and step.allow_create_invoice
        )

    def action_open_provider_invoice_wizard(self):
        self.ensure_one()
        action, _wizard = self._prepare_provider_invoice_wizard_action()
        return action

    def _prepare_provider_invoice_wizard_action(self, return_url=False):
        self.ensure_one()
        if self.state in ('done', 'cancelled'):
            raise UserError(_('Invoices cannot be created in the current request state.'))
        step = self.current_step_id
        if (not step or not step.allow_create_invoice) and not self.env.user.has_group(
            'home_care.group_care_manager'
        ):
            raise UserError(_('Invoice creation is not enabled on the current workflow step.'))
        is_staff = (
            self.env.user.has_group('home_care.group_care_manager')
            or self.env.user.has_group('home_care.group_care_user')
        )
        if not is_staff and not self.provider_can_create_invoice():
            raise UserError(_('You cannot create an invoice for this request.'))
        Wizard = self.env['care.request.invoice.wizard']
        defaults = Wizard.with_context(
            default_request_id=self.id,
            default_partner_id=self.partner_id.id,
        ).default_get(['request_id', 'partner_id', 'line_ids'])
        if return_url:
            defaults['return_url'] = return_url
        wizard = Wizard.create(defaults)
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Create Invoice'),
            'res_model': 'care.request.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wizard.id,
            'context': {
                'default_request_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }
        return action, wizard

    def get_provider_invoice_wizard_url(self, return_url):
        """URL to open the invoice wizard in the web client (same admin form)."""
        self.ensure_one()
        _action, wizard = self._prepare_provider_invoice_wizard_action(return_url=return_url)
        action = self.env.ref('home_care.action_care_request_invoice_wizard_popup')
        return (
            '/web#id=%d&action=%d&model=care.request.invoice.wizard&view_type=form'
        ) % (wizard.id, action.id)

    def _link_invoice(self, move):
        self.ensure_one()
        if move.id not in self.invoice_ids.ids:
            self.invoice_ids = [(4, move.id)]

    def _prepare_invoice_vals_from_lines(self, lines, step=False):
        """lines: list of dicts with product/section/note fields."""
        self.ensure_one()
        step = step or self.current_step_id
        invoice_lines = []
        for line in lines:
            display_type = line.get('display_type', 'product')
            if display_type in ('line_section', 'line_note'):
                invoice_lines.append((0, 0, {
                    'display_type': display_type,
                    'name': line.get('name') or line.get('description') or '',
                }))
                continue
            product = line.get('product')
            if not product:
                continue
            line_vals = {
                'product_id': product.id,
                'quantity': line.get('quantity', 1.0),
                'name': product.display_name,
            }
            price_unit = line.get('price_unit')
            if price_unit is not None and price_unit is not False:
                line_vals['price_unit'] = price_unit
            discount = line.get('discount')
            if discount is not None and discount is not False:
                line_vals['discount'] = discount
            tax_ids = line.get('tax_ids')
            if tax_ids:
                line_vals['tax_ids'] = [(6, 0, tax_ids)]
            description = line.get('description')
            if description:
                line_vals['description'] = description
            invoice_lines.append((0, 0, line_vals))
        product_lines = [l for l in lines if l.get('display_type', 'product') == 'product']
        if not product_lines:
            raise UserError(_('At least one product line is required.'))
        if not invoice_lines:
            raise UserError(_('Enter at least one invoice line.'))
        return {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'care_service_request_id': self.id,
            'care_workflow_step_id': step.id if step else False,
            'invoice_line_ids': invoice_lines,
        }

    def action_create_invoice_from_lines(self, lines_data):
        self.ensure_one()
        Product = self.env['product.product']
        parsed = []
        for item in lines_data:
            display_type = item.get('display_type', 'product')
            if display_type in ('line_section', 'line_note'):
                parsed.append({
                    'display_type': display_type,
                    'name': item.get('name') or item.get('description') or '',
                })
                continue
            product = Product.browse(int(item.get('product_id', 0)))
            if not product.exists():
                continue
            parsed.append({
                'display_type': 'product',
                'product': product,
                'quantity': int(float(item.get('quantity') or 1)),
                'price_unit': float(item['price_unit']) if item.get('price_unit') not in (None, '') else None,
                'discount': float(item['discount']) if item.get('discount') not in (None, '') else None,
                'tax_ids': [int(t) for t in item.get('tax_ids', []) if t],
                'description': item.get('description') or '',
            })
        move = self.env['account.move'].create(
            self._prepare_invoice_vals_from_lines(parsed)
        )
        self._link_invoice(move)
        return move
