from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_care_package = fields.Boolean(
        string='پکیج مراقبت',
        help='محصول اشتراکی که شامل چند خدمت زیرمجموعه است.',
    )
    is_care_service = fields.Boolean(
        string='خدمت مراقبت',
        help='خدمت قابل درخواست در سیستم مراقبت در منزل.',
    )
    care_package_line_ids = fields.One2many(
        'care.package.line',
        'package_product_id',
        string='خدمات پکیج',
    )
    request_category_id = fields.Many2one(
        'care.request.category',
        string='دسته‌بندی درخواست',
        ondelete='restrict',
    )
    default_care_team_id = fields.Many2one(
        'care.team',
        string='تیم پیش‌فرض',
        ondelete='set null',
    )

    @api.constrains('is_care_package', 'is_care_service', 'recurring_invoice')
    def _check_care_package_subscription(self):
        for product in self:
            if product.is_care_package and not product.recurring_invoice:
                raise ValidationError(
                    'پکیج مراقبت باید به‌عنوان محصول اشتراک (Subscription) تعریف شود.'
                )
            if product.is_care_package and product.is_care_service:
                raise ValidationError(
                    'یک محصول نمی‌تواند هم‌زمان پکیج و خدمت باشد.'
                )

    @api.constrains('is_care_service', 'request_category_id')
    def _check_service_category(self):
        for product in self:
            if product.is_care_service and not product.request_category_id:
                raise ValidationError(
                    'برای خدمت مراقبت، دسته‌بندی درخواست الزامی است.'
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
