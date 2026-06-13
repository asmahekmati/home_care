from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CarePackageLine(models.Model):
    _name = 'care.package.line'
    _description = 'خط پکیج مراقبت'
    _order = 'package_product_id, sequence, id'

    package_product_id = fields.Many2one(
        'product.template',
        string='پکیج',
        required=True,
        ondelete='cascade',
        domain=[('is_care_package', '=', True)],
    )
    sequence = fields.Integer(default=10)
    included_service_id = fields.Many2one(
        'product.product',
        string='خدمت زیرمجموعه',
        required=True,
        domain=[('is_care_service', '=', True)],
    )
    quantity = fields.Float(
        string='تعداد',
        default=1.0,
        required=True,
    )
    category_id = fields.Many2one(
        'care.request.category',
        string='دسته‌بندی',
        related='included_service_id.request_category_id',
        store=True,
        readonly=True,
    )

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError('تعداد خدمت در پکیج باید بزرگ‌تر از صفر باشد.')

    @api.constrains('included_service_id', 'package_product_id')
    def _check_not_self_reference(self):
        for line in self:
            if line.included_service_id.product_tmpl_id == line.package_product_id:
                raise ValidationError('پکیج نمی‌تواند شامل خودش باشد.')
