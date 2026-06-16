from odoo import http, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import pager as portal_pager

from .portal import CustomerPortal


class CareProviderPortal(CustomerPortal):

    def _ensure_care_provider(self):
        if not request.env['care.service.request']._is_care_provider():
            return request.redirect('/my')
        return None

    def _check_provider_request(self, care_request):
        if not care_request.exists():
            raise AccessError(_('Request not found.'))
        care_request.check_access('read')
        if not care_request.provider_can_access():
            raise AccessError(_('This request has not been assigned to you.'))

    def _get_provider_invoices(self, care_request):
        care_request.check_access('read')
        return care_request.sudo().invoice_ids

    def _get_provider_invoice_form_values(self):
        Product = request.env['product.product'].sudo()
        Tax = request.env['account.tax'].sudo()
        return {
            'sale_products': Product.search([('sale_ok', '=', True)], order='name'),
            'sale_taxes': Tax.search([
                ('type_tax_use', '=', 'sale'),
                ('active', '=', True),
            ], order='name'),
        }

    def _parse_provider_invoice_lines(self, post):
        lines_data = []
        line_indexes = set()
        for key in post:
            if not key.startswith('line_'):
                continue
            remainder = key[5:]
            if remainder.startswith('_'):
                line_indexes.add(0)
                continue
            if '_' in remainder:
                index_part = remainder.split('_', 1)[0]
                if index_part.isdigit():
                    line_indexes.add(int(index_part))
        for index in sorted(line_indexes):
            prefix = 'line_%s_' % index
            if index == 0 and prefix + 'product_id' not in post:
                prefix = 'line__'
            product_id = post.get(prefix + 'product_id')
            if not product_id or not str(product_id).strip().isdigit():
                continue
            tax_raw = request.httprequest.form.getlist(prefix + 'tax_ids')
            lines_data.append({
                'display_type': 'product',
                'product_id': int(product_id),
                'quantity': post.get(prefix + 'quantity') or 1,
                'price_unit': post.get(prefix + 'price_unit'),
                'discount': post.get(prefix + 'discount') or 0,
                'tax_ids': [int(t) for t in tax_raw if t and str(t).isdigit()],
                'description': post.get(prefix + 'description') or '',
            })
        return lines_data

    @http.route(['/my/care/provider/requests', '/my/care/provider/requests/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_provider_requests(self, page=1, **kw):
        redirect = self._ensure_care_provider()
        if redirect:
            return redirect
        CareRequest = request.env['care.service.request']
        domain = CareRequest._provider_portal_domain()
        total = CareRequest.search_count(domain)
        pager = portal_pager(url='/my/care/provider/requests', total=total, page=page, step=20)
        requests = CareRequest.search(
            domain,
            order='preferred_datetime_start desc, create_date desc',
            limit=20,
            offset=pager['offset'],
        )
        values = self._prepare_portal_layout_values()
        values.update({
            'requests': requests,
            'page_name': 'care_provider_requests',
            'pager': pager,
        })
        return request.render('home_care.portal_provider_requests', values)

    @http.route(['/my/care/provider/requests/<int:request_id>'],
                type='http', auth='user', website=True)
    def portal_provider_request_detail(self, request_id, **kw):
        redirect = self._ensure_care_provider()
        if redirect:
            return redirect
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            self._check_provider_request(care_request)
        except AccessError:
            return request.redirect('/my')
        care_invoices = self._get_provider_invoices(care_request)
        values = self._prepare_portal_layout_values()
        values.update({
            'care_request': care_request,
            'can_accept': care_request.provider_can_accept(),
            'can_complete': care_request.provider_can_complete_service(),
            'can_cancel': care_request.provider_can_cancel_service(),
            'can_create_invoice': care_request.provider_can_create_invoice(),
            'care_invoices': care_invoices,
            'invoice_count': len(care_invoices),
            'page_name': 'care_provider_request_detail',
            'error': kw.get('error'),
            'success': kw.get('success'),
        })
        if care_request.provider_can_create_invoice():
            values.update(self._get_provider_invoice_form_values())
        return request.render('home_care.portal_provider_request_detail', values)

    @http.route(['/my/care/provider/requests/<int:request_id>/invoice/create'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_provider_invoice_create(self, request_id, **post):
        redirect = self._ensure_care_provider()
        if redirect:
            return redirect
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            self._check_provider_request(care_request)
            care_request.check_access('write')
            if not care_request.provider_can_create_invoice():
                raise UserError(_('You cannot create an invoice for this request.'))
            lines_data = self._parse_provider_invoice_lines(post)
            if not lines_data:
                raise UserError(_('Enter at least one invoice line.'))
            care_request.sudo().action_create_invoice_from_lines(lines_data)
        except (AccessError, UserError) as exc:
            return request.redirect(
                '/my/care/provider/requests/%s?error=%s' % (request_id, exc.args[0])
            )
        return request.redirect(
            '/my/care/provider/requests/%s?success=invoice' % request_id
        )

    @http.route(['/my/care/provider/requests/<int:request_id>/accept'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_provider_accept(self, request_id, **post):
        redirect = self._ensure_care_provider()
        if redirect:
            return redirect
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            self._check_provider_request(care_request)
            care_request.check_access('write')
            visit_start = self._parse_preferred_datetime(post.get('visit_datetime_start'))
            visit_end = self._parse_preferred_datetime(post.get('visit_datetime_end'))
            care_request.action_accept_assignment(
                visit_start=visit_start,
                visit_end=visit_end,
            )
        except (AccessError, UserError) as exc:
            return request.redirect(
                '/my/care/provider/requests/%s?error=%s' % (request_id, exc.args[0])
            )
        return request.redirect(
            '/my/care/provider/requests/%s?success=accepted' % request_id
        )

    @http.route(['/my/care/provider/tasks', '/my/care/provider/tasks/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_provider_tasks(self, page=1, **kw):
        redirect = self._ensure_care_provider()
        if redirect:
            return redirect
        CareRequest = request.env['care.service.request']
        user = request.env.user
        accepted_step_ids = CareRequest._get_provider_accepted_step_ids()
        domain = [
            ('user_id', '=', user.id),
            ('state', '=', 'in_progress'),
            ('visit_datetime_start', '!=', False),
        ]
        if accepted_step_ids:
            domain.append(('current_step_id', 'in', accepted_step_ids))
        total = CareRequest.search_count(domain)
        pager = portal_pager(url='/my/care/provider/tasks', total=total, page=page, step=20)
        tasks = CareRequest.search(
            domain,
            order='visit_datetime_start asc',
            limit=20,
            offset=pager['offset'],
        )
        values = self._prepare_portal_layout_values()
        values.update({
            'tasks': tasks,
            'page_name': 'care_provider_tasks',
            'pager': pager,
        })
        return request.render('home_care.portal_provider_tasks', values)

    @http.route(['/my/care/provider/requests/<int:request_id>/complete'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_provider_complete(self, request_id, **post):
        redirect = self._ensure_care_provider()
        if redirect:
            return redirect
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            self._check_provider_request(care_request)
            care_request.check_access('write')
            care_request.action_provider_complete_service(
                note=post.get('complete_note') or False,
            )
        except (AccessError, UserError) as exc:
            return request.redirect(
                '/my/care/provider/requests/%s?error=%s' % (request_id, exc.args[0])
            )
        return request.redirect(
            '/my/care/provider/requests/%s?success=completed' % request_id
        )

    @http.route(['/my/care/provider/requests/<int:request_id>/cancel'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_provider_cancel(self, request_id, **post):
        redirect = self._ensure_care_provider()
        if redirect:
            return redirect
        care_request = request.env['care.service.request'].browse(request_id)
        try:
            self._check_provider_request(care_request)
            care_request.check_access('write')
            care_request.action_provider_cancel_request(
                note=post.get('cancel_note') or False,
            )
        except (AccessError, UserError) as exc:
            return request.redirect(
                '/my/care/provider/requests/%s?error=%s' % (request_id, exc.args[0])
            )
        return request.redirect('/my/care/provider/requests?success=cancelled')
