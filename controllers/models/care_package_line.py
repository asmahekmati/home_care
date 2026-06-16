from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CarePackageLine(models.Model):
    _name = 'care.package.line'
    _description = 'Care Package Line'
    _order = 'package_product_id, sequence, id'

    package_product_id = fields.Many2one(
        'product.template',
        string='Package',
        required=True,
        ondelete='cascade',
        domain=[('is_care_package', '=', True)],
    )
    sequence = fields.Integer(default=10)
    included_service_id = fields.Many2one(
        'product.product',
        string='Included Service',
        required=True,
        domain=[('is_care_service', '=', True)],
    )
    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        required=True,
    )
    category_id = fields.Many2one(
        'care.request.category',
        string='Category',
        related='included_service_id.request_category_id',
        store=True,
        readonly=True,
    )

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_('Package service quantity must be greater than zero.'))

    @api.constrains('included_service_id', 'package_product_id')
    def _check_not_self_reference(self):
        for line in self:
            if line.included_service_id.product_tmpl_id == line.package_product_id:
                raise ValidationError(_('A package cannot include itself.'))
