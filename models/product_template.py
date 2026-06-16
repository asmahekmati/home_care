from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_care_package = fields.Boolean(
        string='Care Package',
        help='Subscription product that includes multiple included services.',
    )
    is_care_service = fields.Boolean(
        string='Care Service',
        help='Service that can be requested in the home care system.',
    )
    care_package_line_ids = fields.One2many(
        'care.package.line',
        'package_product_id',
        string='Package Services',
    )
    request_category_id = fields.Many2one(
        'care.request.category',
        string='Request Category',
        ondelete='restrict',
    )
    default_care_team_id = fields.Many2one(
        'care.team',
        string='Default Team',
        ondelete='set null',
    )

    @api.constrains('is_care_package', 'is_care_service', 'recurring_invoice')
    def _check_care_package_subscription(self):
        for product in self:
            if product.is_care_package and not product.recurring_invoice:
                raise ValidationError(
                    _('A care package must be defined as a subscription product.')
                )
            if product.is_care_package and product.is_care_service:
                raise ValidationError(
                    _('A product cannot be both a package and a service.')
                )

    @api.constrains('is_care_service', 'request_category_id')
    def _check_service_category(self):
        for product in self:
            if product.is_care_service and not product.request_category_id:
                raise ValidationError(
                    _('Request category is required for care services.')
                )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_care_service = fields.Boolean(
        related='product_tmpl_id.is_care_service',
        store=True,
    )
    request_category_id = fields.Many2one(
        related='product_tmpl_id.request_category_id',
        store=True,
    )
