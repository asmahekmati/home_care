from odoo import _, fields, models
from odoo.exceptions import UserError


class CareRequestDocument(models.Model):
    _name = 'care.request.document'
    _description = 'سند درخواست مراقبت'
    _order = 'create_date desc, id desc'

    name = fields.Char(string='نام فایل', required=True)
    request_id = fields.Many2one(
        'care.service.request',
        string='درخواست',
        required=True,
        ondelete='cascade',
        index=True,
    )
    step_id = fields.Many2one(
        'care.workflow.step',
        string='مرحله',
        ondelete='set null',
    )
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='پیوست',
        required=True,
        ondelete='cascade',
    )
    uploaded_by_id = fields.Many2one(
        'res.users',
        string='آپلودکننده',
        default=lambda self: self.env.user,
    )
    note = fields.Text(string='یادداشت')

    def action_download(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_('فایل پیوست وجود ندارد.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true&filename=%s' % (
                self.attachment_id.id,
                self.name or self.attachment_id.name,
            ),
            'target': 'self',
        }

    def get_portal_download_url(self):
        self.ensure_one()
        return '/my/care/requests/%s/documents/%s/download' % (
            self.request_id.id,
            self.id,
        )
