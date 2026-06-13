from odoo import api, fields, models


class CarePackageEntitlement(models.Model):
    _name = 'care.package.entitlement'
    _description = 'سهمیه پکیج مشتری'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='شماره',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='مشتری',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    package_product_id = fields.Many2one(
        'product.product',
        string='پکیج',
        required=True,
        ondelete='restrict',
        domain=[('product_tmpl_id.is_care_package', '=', True)],
        tracking=True,
    )
    subscription_id = fields.Many2one(
        'sale.order',
        string='اشتراک',
        ondelete='set null',
        index=True,
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='خط سفارش',
        ondelete='set null',
    )
    date_start = fields.Date(string='شروع', required=True, tracking=True)
    date_end = fields.Date(string='پایان', required=True, tracking=True)
    state = fields.Selection(
        [
            ('active', 'فعال'),
            ('expired', 'منقضی'),
            ('cancelled', 'لغوشده'),
        ],
        string='وضعیت',
        default='active',
        required=True,
        tracking=True,
        compute='_compute_state',
        store=True,
        readonly=False,
    )
    line_ids = fields.One2many(
        'care.package.entitlement.line',
        'entitlement_id',
        string='سهمیه خدمات',
        copy=True,
    )
    request_ids = fields.One2many(
        'care.service.request',
        'entitlement_id',
        string='درخواست‌ها',
    )
    request_count = fields.Integer(compute='_compute_request_count')
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )

    @api.depends('date_end', 'state')
    def _compute_state(self):
        today = fields.Date.today()
        for ent in self:
            if ent.state == 'cancelled':
                continue
            if ent.date_end and ent.date_end < today:
                ent.state = 'expired'
            elif ent.state == 'expired' and ent.date_end and ent.date_end >= today:
                ent.state = 'active'

    def _compute_request_count(self):
        data = self.env['care.service.request']._read_group(
            [('entitlement_id', 'in', self.ids)],
            ['entitlement_id'],
            ['__count'],
        )
        counts = {ent.id: count for ent, count in data}
        for ent in self:
            ent.request_count = counts.get(ent.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'care.package.entitlement'
                ) or 'New'
        return super().create(vals_list)

    @api.model
    def _create_from_subscription(self, subscription, order_line):
        product = order_line.product_id
        if not product.product_tmpl_id.is_care_package:
            return self.env['care.package.entitlement']

        existing = self.search([
            ('subscription_id', '=', subscription.id),
            ('package_product_id', '=', product.id),
            ('state', '=', 'active'),
        ], limit=1)
        if existing:
            existing._refresh_period(subscription)
            return existing

        date_start = subscription.start_date or fields.Date.today()
        date_end = subscription.end_date
        if not date_end and subscription.plan_id:
            date_end = date_start + subscription.plan_id.billing_period

        lines = []
        for pkg_line in product.product_tmpl_id.care_package_line_ids:
            lines.append((0, 0, {
                'included_service_id': pkg_line.included_service_id.id,
                'qty_total': pkg_line.quantity,
                'qty_used': 0.0,
            }))

        return self.create({
            'partner_id': subscription.partner_id.id,
            'package_product_id': product.id,
            'subscription_id': subscription.id,
            'sale_order_line_id': order_line.id,
            'date_start': date_start,
            'date_end': date_end or date_start,
            'line_ids': lines,
        })

    def _refresh_period(self, subscription):
        self.ensure_one()
        vals = {}
        if subscription.end_date:
            vals['date_end'] = subscription.end_date
        if subscription.start_date:
            vals['date_start'] = subscription.start_date
        if vals:
            self.write(vals)
        if self.state == 'expired' and self.date_end >= fields.Date.today():
            self.state = 'active'

    def get_available_service_products(self):
        """خدمات قابل درخواست از این سهمیه."""
        self.ensure_one()
        if self.state != 'active':
            return self.env['product.product']
        return self.line_ids.filtered(
            lambda l: l.qty_remaining > 0
        ).mapped('included_service_id')

    def name_get(self):
        if self.env.context.get('care_service_request'):
            return [
                (
                    ent.id,
                    '%s — %s (%s)'
                    % (ent.name, ent.package_product_id.display_name, ent.partner_id.name),
                )
                for ent in self
            ]
        return super().name_get()

    def consume_service(self, product):
        self.ensure_one()
        line = self.line_ids.filtered(
            lambda l: l.included_service_id == product
        )[:1]
        if not line:
            from odoo.exceptions import UserError
            raise UserError('این خدمت در سهمیه پکیج شما وجود ندارد.')
        line.consume_one()
        return line


class CarePackageEntitlementLine(models.Model):
    _name = 'care.package.entitlement.line'
    _description = 'خط سهمیه خدمت'
    _order = 'entitlement_id, id'

    entitlement_id = fields.Many2one(
        'care.package.entitlement',
        string='سهمیه',
        required=True,
        ondelete='cascade',
    )
    included_service_id = fields.Many2one(
        'product.product',
        string='خدمت',
        required=True,
        domain=[('is_care_service', '=', True)],
    )
    qty_total = fields.Float(string='کل', required=True)
    qty_used = fields.Float(string='مصرف‌شده', default=0.0)
    qty_remaining = fields.Float(
        string='باقیمانده',
        compute='_compute_qty_remaining',
        store=True,
    )

    @api.depends('qty_total', 'qty_used')
    def _compute_qty_remaining(self):
        for line in self:
            line.qty_remaining = max(line.qty_total - line.qty_used, 0.0)

    def consume_one(self):
        self.ensure_one()
        if self.qty_remaining <= 0:
            from odoo.exceptions import UserError
            raise UserError('سهمیه این خدمت تمام شده است.')
        self.qty_used += 1.0
