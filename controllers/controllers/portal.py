import base64

from odoo import fields, http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class CustomerPortal(CustomerPortal):

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        CareRequest = request.env['care.service.request']
        values['is_care_provider'] = (
            CareRequest._is_care_provider()
            if CareRequest.has_access('read') else False
        )
        return values

    def _parse_preferred_datetime(self, value):
        if not value or not str(value).strip():
            return False
        normalized = str(value).strip().replace('T', ' ')
        if len(normalized) == 16:
            normalized += ':00'
        return fields.Datetime.to_datetime(normalized)

    def _check_customer_request_access(self, care_request):
        care_request.check_access('read')
        if care_request.partner_id.commercial_partner_id != request.env.user.partner_id.commercial_partner_id:
            raise AccessError(_('You do not have access to this request.'))

    def _validate_insurance_id(self, insurance_id, insurance_type):
        if not insurance_id or not str(insurance_id).strip().isdigit():
            return False
        insurance = request.env['care.insurance'].sudo().browse(int(insurance_id))
        if (
            not insurance.exists()
            or not insurance.active
            or insurance.insurance_type != insurance_type
        ):
            raise AccessError(_('The selected insurance is not valid.'))
        return insurance.id

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        CareRequest = request.env['care.service.request']
        if 'care_request_count' in counters:
            values['care_request_count'] = CareRequest.search_count([
                ('partner_id', 'child_of', partner.commercial_partner_id.id),
                ('state', 'not in', ('cancelled',)),
            ]) if CareRequest.has_access('read') else 0
        if 'care_eligible_count' in counters:
            entitlements = self._get_active_entitlements(partner)
            standalone_lines = CareRequest._get_available_standalone_lines(partner)
            values['care_eligible_count'] = len(entitlements) + len(standalone_lines)
        return values

    def _get_active_entitlements(self, partner):
        today = fields.Date.today()
        return request.env['care.package.entitlement'].search([
            ('partner_id', 'child_of', partner.commercial_partner_id.id),
            ('state', '=', 'active'),
            ('date_start', '<=', today),
            ('date_end', '>=', today),
        ])

    @http.route(['/my/care/requests', '/my/care/requests/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_care_requests(self, page=1, **kw):
        partner = request.env.user.partner_id
        CareRequest = request.env['care.service.request']
        domain = [('partner_id', 'child_of', partner.commercial_partner_id.id)]

        total = CareRequest.search_count(domain)
        pager = portal_pager(
            url='/my/care/requests',
            total=total,
            page=page,
            step=20,
        )
        requests = CareRequest.search(
            domain,
            order='create_date desc',
            limit=20,
            offset=pager['offset'],
        )
        values = self._prepare_portal_layout_values()
        values.update({
            'requests': requests,
            'page_name': 'care_requests',
            'pager': pager,
            'default_url': '/my/care/requests',
        })
        return request.render('home_care.portal_care_requests', values)

    @http.route(['/my/care/requests/<int:request_id>'],
                type='http', auth='user', website=True)
    def portal_care_request_detail(self, request_id, **kw):
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            self._check_customer_request_access(care_request)
        except AccessError:
            return request.redirect('/my')

        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        care_invoices = care_request._filter_portal_customer_invoices(partner)
        values.update({
            'care_request': care_request,
            'care_invoices': care_invoices,
            'invoice_count': len(care_invoices),
            'page_name': 'care_request_detail',
            'error': kw.get('error'),
            'success': kw.get('success'),
        })
        return request.render('home_care.portal_care_request_detail', values)

    @http.route(['/my/care/requests/<int:request_id>/assignee'],
                type='http', auth='user', website=True)
    def portal_care_request_assignee(self, request_id, **kw):
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            self._check_customer_request_access(care_request)
        except AccessError:
            return request.redirect('/my')
        if not care_request.user_id:
            return request.redirect('/my/care/requests/%s' % request_id)
        values = self._prepare_portal_layout_values()
        values.update({'care_request': care_request, 'page_name': 'care_request_assignee'})
        return request.render('home_care.portal_care_request_assignee', values)

    @http.route(['/my/care/requests/<int:request_id>/reject-assignee'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_care_reject_assignee(self, request_id, **post):
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            care_request.check_access('write')
            self._check_customer_request_access(care_request)
        except AccessError:
            return request.redirect('/my')
        try:
            care_request.action_customer_reject_assignee()
        except UserError as exc:
            return request.redirect('/my/care/requests/%s?error=%s' % (request_id, exc.args[0]))
        return request.redirect('/my/care/requests/%s?success=reject' % request_id)

    @http.route(['/my/care/requests/<int:request_id>/cancel'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_care_cancel_request(self, request_id, **post):
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            care_request.check_access('write')
            self._check_customer_request_access(care_request)
        except AccessError:
            return request.redirect('/my')
        try:
            care_request.action_customer_cancel_request()
        except UserError as exc:
            return request.redirect('/my/care/requests/%s?error=%s' % (request_id, exc.args[0]))
        return request.redirect('/my/care/requests?success=cancelled')

    @http.route(['/my/care/request/new'], type='http', auth='user', website=True)
    def portal_care_request_new(self, **kw):
        partner = request.env.user.partner_id
        entitlements = self._get_active_entitlements(partner)
        standalone_lines = request.env['care.service.request']._get_available_standalone_lines(partner)

        values = self._prepare_portal_layout_values()
        Insurance = request.env['care.insurance'].sudo()
        values.update({
            'entitlements': entitlements,
            'standalone_lines': standalone_lines,
            'primary_insurances': Insurance.search([
                ('insurance_type', '=', 'primary'),
                ('active', '=', True),
            ]),
            'supplementary_insurances': Insurance.search([
                ('insurance_type', '=', 'supplementary'),
                ('active', '=', True),
            ]),
            'page_name': 'care_request_new',
            'error': kw.get('error'),
            'partner_prefill': {
                'name': partner.name or '',
                'phone': partner.phone or '',
                'address': partner.contact_address_inline or partner.street or '',
                'national_id': partner.vat or '',
            },
        })
        return request.render('home_care.portal_care_request_new', values)

    @http.route(['/my/care/request/create'], type='http', auth='user', website=True, methods=['POST'])
    def portal_care_request_create(self, **post):
        partner = request.env.user.partner_id
        CareRequest = request.env['care.service.request']

        request_type = post.get('request_type', 'package')
        preferred_start = self._parse_preferred_datetime(post.get('preferred_datetime_start'))
        preferred_end = self._parse_preferred_datetime(post.get('preferred_datetime_end'))
        description = post.get('description') or ''
        patient_relation = post.get('patient_relation', 'self')

        try:
            if not preferred_start or not preferred_end:
                raise UserError(_('Preferred time window (start and end) is required.'))
            if preferred_end <= preferred_start:
                raise UserError(_('Preferred end time must be after the start time.'))
        except (UserError, ValidationError) as exc:
            return request.redirect('/my/care/request/new?error=%s' % exc.args[0])

        vals = {
            'partner_id': partner.id,
            'request_type': request_type,
            'preferred_datetime_start': preferred_start,
            'preferred_datetime_end': preferred_end,
            'description': description,
            'state': 'draft',
            'patient_relation': patient_relation,
            'patient_first_name': post.get('patient_first_name') or False,
            'patient_last_name': post.get('patient_last_name') or False,
            'patient_national_id': post.get('patient_national_id') or False,
            'patient_case_code': post.get('patient_case_code') or False,
            'patient_age': int(post['patient_age']) if post.get('patient_age', '').isdigit() else False,
            'patient_gender': post.get('patient_gender') or False,
            'patient_phone': post.get('patient_phone') or False,
            'patient_mobile': post.get('patient_mobile') or False,
            'patient_address': post.get('patient_address') or False,
        }
        primary_insurance_id = self._validate_insurance_id(
            post.get('insurance_primary_id'), 'primary'
        )
        supplementary_insurance_id = self._validate_insurance_id(
            post.get('insurance_supplementary_id'), 'supplementary'
        )
        if primary_insurance_id:
            vals['insurance_primary_id'] = primary_insurance_id
        if supplementary_insurance_id:
            vals['insurance_supplementary_id'] = supplementary_insurance_id

        try:
            if request_type == 'package':
                entitlement_id = int(post.get('entitlement_id') or 0)
                product_id = int(post.get('product_id') or 0)
                entitlement = request.env['care.package.entitlement'].browse(entitlement_id)
                entitlement.check_access('read')
                if entitlement.partner_id.commercial_partner_id != partner.commercial_partner_id:
                    raise AccessError(_('You do not have access to this package.'))
                product = request.env['product.product'].browse(product_id)
                if product not in entitlement.get_available_service_products():
                    raise UserError(_('This service is not available in your package entitlement.'))
                vals.update({
                    'entitlement_id': entitlement.id,
                    'product_id': product.id,
                })
            else:
                line_id = int(post.get('sale_order_line_id') or 0)
                line = request.env['sale.order.line'].browse(line_id)
                if line.order_id.partner_id.commercial_partner_id != partner.commercial_partner_id:
                    raise AccessError(_('You do not have access to this order.'))
                if not line.product_id.is_care_service:
                    raise UserError(_('The selected product is not a care service.'))
                vals.update({
                    'sale_order_line_id': line.id,
                    'product_id': line.product_id.id,
                })

            care_request = CareRequest.create(vals)
            care_request.action_start()
            return request.redirect('/my/care/requests/%s' % care_request.id)
        except (UserError, ValidationError, AccessError) as exc:
            return request.redirect('/my/care/request/new?error=%s' % exc.args[0])

    @http.route(['/my/care/requests/<int:request_id>/upload'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_care_request_upload(self, request_id, **post):
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            care_request.check_access('write')
            self._check_customer_request_access(care_request)
        except AccessError:
            return request.redirect('/my')

        uploaded = request.httprequest.files.get('document')
        if not uploaded or not care_request.can_portal_upload:
            return request.redirect('/my/care/requests/%s' % request_id)

        data = base64.b64encode(uploaded.read())
        attachment = request.env['ir.attachment'].sudo().create({
            'name': uploaded.filename,
            'datas': data,
            'res_model': 'care.service.request',
            'res_id': care_request.id,
            'type': 'binary',
        })
        request.env['care.request.document'].create({
            'name': uploaded.filename,
            'request_id': care_request.id,
            'step_id': care_request.current_step_id.id,
            'attachment_id': attachment.id,
            'uploaded_by_id': request.env.user.id,
        })
        return request.redirect('/my/care/requests/%s' % request_id)

    @http.route(['/my/care/requests/<int:request_id>/documents/<int:document_id>/download'],
                type='http', auth='user', website=True)
    def portal_care_document_download(self, request_id, document_id, **kw):
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            self._check_customer_request_access(care_request)
        except AccessError:
            return request.redirect('/my')
        document = request.env['care.request.document'].browse(document_id)
        if document.request_id != care_request or not document.attachment_id:
            return request.redirect('/my/care/requests/%s' % request_id)
        attachment = document.attachment_id.sudo()
        filename = document.name or attachment.name or 'document'
        return request.make_response(
            base64.b64decode(attachment.datas or b''),
            headers=[
                ('Content-Type', attachment.mimetype or 'application/octet-stream'),
                (
                    'Content-Disposition',
                    'attachment; filename="%s"' % filename.replace('"', ''),
                ),
            ],
        )

    @http.route(['/my/care/requests/<int:request_id>/advance'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_care_request_advance(self, request_id, **post):
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            care_request.check_access('write')
            self._check_customer_request_access(care_request)
        except AccessError:
            return request.redirect('/my')

        if not care_request.can_portal_advance:
            return request.redirect('/my/care/requests/%s' % request_id)

        try:
            care_request.action_advance_step()
        except UserError as exc:
            return request.redirect('/my/care/requests/%s?error=%s' % (request_id, exc.args[0]))
        return request.redirect('/my/care/requests/%s' % request_id)

    @http.route(['/my/care/entitlement/<int:entitlement_id>/services'],
                type='jsonrpc', auth='user', website=True)
    def portal_entitlement_services(self, entitlement_id):
        partner = request.env.user.partner_id
        entitlement = request.env['care.package.entitlement'].browse(entitlement_id)
        entitlement.check_access('read')
        if entitlement.partner_id.commercial_partner_id != partner.commercial_partner_id:
            raise AccessError(_('Access denied.'))
        products = entitlement.get_available_service_products()
        return [{
            'id': p.id,
            'name': p.display_name,
            'category': p.request_category_id.name,
        } for p in products]
