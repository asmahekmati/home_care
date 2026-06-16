# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CareRequestInvoiceWizardLine(models.TransientModel):
    _name = 'care.request.invoice.wizard.line'
    _description = 'Care Request Invoice Wizard Line'

    wizard_id = fields.Many2one(
        'care.request.invoice.wizard',
        required=True,
        ondelete='cascade',
    )
    display_type = fields.Selection(
        [
            ('product', 'Product'),
            ('line_section', 'Section'),
            ('line_note', 'Note'),
        ],
        string='Type',
        default='product',
        required=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Service',
        domain="[('sale_ok', '=', True)]",
    )
    name = fields.Char(string='Label')
    quantity = fields.Integer(string='Quantity', default=1)
    price_unit = fields.Float(string='Unit Price')
    discount = fields.Float(string='Discount (%)', default=0.0)
    tax_ids = fields.Many2many(
        'account.tax',
        string='Taxes',
        domain="[('type_tax_use', '=', 'sale')]",
    )
    description = fields.Char(string='Description')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and self.display_type == 'product':
            self.price_unit = self.product_id.lst_price
            self.tax_ids = self.product_id.taxes_id


class CareRequestInvoiceWizard(models.TransientModel):
    _name = 'care.request.invoice.wizard'
    _description = 'Create Care Request Invoice'

    request_id = fields.Many2one('care.service.request', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', required=True)
    return_url = fields.Char(string='Portal Return URL')
    line_ids = fields.One2many(
        'care.request.invoice.wizard.line',
        'wizard_id',
        string='Invoice Lines',
    )

    def _check_wizard_request_access(self):
        self.ensure_one()
        req = self.request_id
        if self.env.user.has_group('home_care.group_care_manager'):
            return
        if self.env.user.has_group('home_care.group_care_user'):
            req.check_access('write')
            return
        if req.provider_can_create_invoice():
            return
        raise UserError(_('You do not have access to this invoice wizard.'))

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            wizard._check_wizard_request_access()
        return wizards

    def write(self, vals):
        res = super().write(vals)
        for wizard in self:
            wizard._check_wizard_request_access()
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        req = self.env['care.service.request'].browse(
            self.env.context.get('default_request_id')
        )
        if req and req.product_id:
            res['line_ids'] = [(0, 0, {
                'display_type': 'product',
                'product_id': req.product_id.id,
                'quantity': 1,
                'price_unit': req.product_id.lst_price,
            })]
        return res

    def action_create_invoice(self):
        self.ensure_one()
        req = self.request_id
        if req.state in ('done', 'cancelled'):
            raise UserError(_('Invoices cannot be created in the current request state.'))
        if not req.provider_can_create_invoice() and not self.env.user.has_group(
            'home_care.group_care_manager'
        ) and not (
            self.env.user.has_group('home_care.group_care_user')
            and req.current_step_id
            and req.current_step_id.allow_create_invoice
        ):
            raise UserError(_('You cannot create an invoice for this request.'))
        if not self.line_ids:
            raise UserError(_('Enter at least one invoice line.'))
        product_lines = self.line_ids.filtered(lambda l: l.display_type == 'product')
        if not product_lines:
            raise UserError(_('At least one product line is required.'))
        for line in product_lines:
            if not line.product_id:
                raise UserError(_('Select a product for each invoice line.'))
        lines_data = []
        for line in self.line_ids.sorted('id'):
            if line.display_type in ('line_section', 'line_note'):
                lines_data.append({
                    'display_type': line.display_type,
                    'name': line.name or '',
                })
            else:
                lines_data.append({
                    'display_type': 'product',
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'tax_ids': line.tax_ids.ids,
                    'description': line.description or '',
                })
        move = req.sudo().action_create_invoice_from_lines(lines_data)
        if self.return_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.return_url + '?success=invoice',
                'target': 'self',
            }
        return req._action_view_invoices(move)
