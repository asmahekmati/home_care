from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    care_entitlement_ids = fields.One2many(
        'care.package.entitlement',
        'subscription_id',
        string='Care Entitlements',
    )
    care_request_ids = fields.One2many(
        'care.service.request',
        'sale_order_id',
        string='Care Requests',
    )

    def action_confirm(self):
        res = super().action_confirm()
        self._home_care_create_entitlements()
        return res

    def write(self, vals):
        res = super().write(vals)
        if 'subscription_state' in vals or 'end_date' in vals or 'start_date' in vals:
            self.filtered(
                lambda o: o.is_subscription and o.subscription_state == '3_progress'
            )._home_care_create_entitlements()
        return res

    def _home_care_create_entitlements(self):
        Entitlement = self.env['care.package.entitlement']
        for order in self:
            if order.is_subscription and order.subscription_state != '3_progress':
                continue
            for line in order.order_line.filtered(
                lambda l: not l.display_type and l.product_id.product_tmpl_id.is_care_package
            ):
                Entitlement._create_from_subscription(order, line)

    @api.model
    def _get_care_standalone_products_domain(self):
        return [('is_care_service', '=', True), ('is_care_package', '=', False)]


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    care_request_ids = fields.One2many(
        'care.service.request',
        'sale_order_line_id',
        string='Care Requests',
    )
    care_remaining_qty = fields.Float(
        string='Remaining Quota',
        compute='_compute_care_remaining_qty',
    )

    def _compute_care_remaining_qty(self):
        Request = self.env['care.service.request']
        for line in self:
            if not line.product_id.is_care_service:
                line.care_remaining_qty = 0.0
                continue
            used = Request.search_count([
                ('sale_order_line_id', '=', line.id),
                ('quota_consumed', '=', True),
            ])
            line.care_remaining_qty = max(line.product_uom_qty - used, 0.0)

    def name_get(self):
        if self.env.context.get('care_service_request_line'):
            return [
                (
                    line.id,
                    '%s — %s (Remaining: %s)'
                    % (line.order_id.name, line.product_id.display_name, line.care_remaining_qty),
                )
                for line in self
            ]
        return super().name_get()
