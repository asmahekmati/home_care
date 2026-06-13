from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CareWorkflowTemplate(models.Model):
    _name = 'care.workflow.template'
    _description = 'قالب فرآیند مراقبت'
    _order = 'name'

    name = fields.Char(string='نام فرآیند', required=True, translate=True)
    active = fields.Boolean(default=True)
    category_id = fields.Many2one(
        'care.request.category',
        string='دسته‌بندی',
        ondelete='restrict',
    )
    description = fields.Text(string='توضیحات')
    step_ids = fields.One2many(
        'care.workflow.step',
        'workflow_id',
        string='مراحل',
        copy=True,
    )
    step_count = fields.Integer(compute='_compute_step_count')

    @api.depends('step_ids')
    def _compute_step_count(self):
        for workflow in self:
            workflow.step_count = len(workflow.step_ids)

    def get_first_step(self):
        self.ensure_one()
        return self.step_ids.sorted('sequence').filtered(
            lambda s: not s.is_cancel_step
        )[:1]


class CareWorkflowStep(models.Model):
    _name = 'care.workflow.step'
    _description = 'مرحله فرآیند مراقبت'
    _order = 'workflow_id, sequence, id'

    name = fields.Char(string='نام مرحله', required=True, translate=True)
    workflow_id = fields.Many2one(
        'care.workflow.template',
        string='فرآیند',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    description = fields.Text(string='توضیحات داخلی')
    portal_instruction = fields.Html(
        string='راهنمای مشتری',
        translate=True,
        help='متن نمایش‌داده‌شده به مشتری در پورتال برای این مرحله.',
    )
    requires_attachment = fields.Boolean(
        string='نیاز به پیوست',
        help='قبل از رفتن به مرحله بعد، حداقل یک سند باید آپلود شود.',
    )
    allow_portal_upload = fields.Boolean(
        string='آپلود از پورتال',
        default=True,
    )
    allow_portal_advance = fields.Boolean(
        string='پیشرفت از پورتال',
        help='مشتری می‌تواند در پورتال به مرحله بعد برود (در صورت برآورده شدن شرایط).',
    )
    consumes_quota = fields.Boolean(
        string='مصرف سهمیه',
        help='با ورود به این مرحله، یک واحد از سهمیه خدمت کسر می‌شود.',
    )
    is_cancel_step = fields.Boolean(
        string='مرحله لغو',
        help='با زدن دکمه لغو، درخواست به این مرحله منتقل می‌شود.',
    )
    allow_create_invoice = fields.Boolean(string='امکان ایجاد فاکتور')
    allow_provider_complete = fields.Boolean(
        string='دکمه انجام خدمت (پذیرنده)',
        help='پذیرنده می‌تواند از پورتال خدمت را انجام‌شده اعلام کند (رفتن به مرحله بعد).',
    )
    allow_provider_cancel = fields.Boolean(
        string='دکمه لغو فرآیند (پذیرنده)',
        help='پذیرنده می‌تواند از پورتال درخواست را با توضیحات لغو کند.',
    )
    allow_customer_cancel = fields.Boolean(
        string='دکمه لغو درخواست (مشتری)',
        help='مشتری می‌تواند از پورتال کل درخواست را در این مرحله لغو کند.',
    )
    invoice_product_id = fields.Many2one(
        'product.product',
        string='محصول پیش‌فرض فاکتور',
        ondelete='set null',
    )
    send_sms = fields.Boolean(string='ارسال SMS به مشتری', default=True)
    sms_body = fields.Text(
        string='متن SMS مشتری',
        default=(
            'مشتری گرامی {partner_name}،\n'
            'درخواست {request_name} در مرحله «{step_name}» قرار دارد.\n'
            'خدمت: {service_name}'
        ),
        help='متغیرها: {partner_name}, {request_name}, {step_name}, {service_name}, {package_name}, {visit_schedule}',
    )
    send_team_sms = fields.Boolean(
        string='ارسال SMS به تیم',
        help='ارسال پیامک به اعضای تیم (مثلاً مرحله ارجاع).',
    )
    team_sms_body = fields.Text(
        string='متن SMS تیم',
        default=(
            'همکار گرامی {user_name}،\n'
            'درخواست {request_name} — بیمار: {patient_name}\n'
            'مرحله: {step_name} — تیم: {team_name}\n'
            'لطفاً در سیستم درخواست را بپذیرید.'
        ),
        help='متغیرها: {user_name}, {request_name}, {patient_name}, {step_name}, {team_name}, {service_name}',
    )
    team_acceptance_mode = fields.Boolean(
        string='پذیرش توسط تیم (اولین نفر)',
        help='مشابه اسنپ: SMS به اعضای تیم؛ اولین نفری که «پذیرش» بزند مسئول می‌شود.',
    )
    is_provider_accepted_status = fields.Boolean(
        string='وضعیت پذیرفته‌شده توسط پذیرنده',
        help='درخواست‌های در این مرحله برای کنترل همپوشانی زمان حضور پذیرنده در نظر گرفته می‌شوند.',
    )
    requires_visit_schedule = fields.Boolean(
        string='زمان‌بندی حضور هنگام پذیرش',
        help='پذیرنده هنگام پذیرش باید تاریخ و بازه زمانی حضور را وارد کند.',
    )
    send_assignee_customer_sms = fields.Boolean(
        string='SMS پذیرنده به مشتری',
        default=True,
    )
    assignee_customer_sms_body = fields.Text(
        string='متن SMS پذیرنده',
        default=(
            'مشتری گرامی {partner_name}،\n'
            'درخواست {request_name} توسط {assignee_name} پذیرفته شد.\n'
            'زمان حضور: {visit_schedule}\n'
            'تماس: {assignee_phone}\n'
            'مشخصات: {assignee_link}'
        ),
    )
    auto_team_id = fields.Many2one(
        'care.team',
        string='واگذاری خودکار به تیم',
        ondelete='set null',
    )
    auto_user_id = fields.Many2one(
        'res.users',
        string='واگذاری خودکار به شخص',
        ondelete='set null',
        domain="[('id', 'in', auto_team_member_ids)]",
    )
    auto_team_member_ids = fields.Many2many(
        'res.users',
        compute='_compute_auto_team_member_ids',
    )
    action_ids = fields.One2many(
        'care.workflow.action',
        'step_id',
        string='اکشن‌های اضافی',
    )

    @api.depends('auto_team_id.member_ids', 'auto_team_id.leader_id')
    def _compute_auto_team_member_ids(self):
        for step in self:
            members = step.auto_team_id.member_ids
            if step.auto_team_id.leader_id:
                members |= step.auto_team_id.leader_id
            step.auto_team_member_ids = members

    @api.constrains('is_cancel_step', 'workflow_id')
    def _check_single_cancel_step(self):
        for step in self.filtered('is_cancel_step'):
            others = step.workflow_id.step_ids.filtered(
                lambda s: s.id != step.id and s.is_cancel_step
            )
            if others:
                raise ValidationError(
                    'در هر فرآیند فقط یک مرحله می‌تواند «مرحله لغو» باشد.'
                )

    @api.constrains('is_provider_accepted_status', 'workflow_id')
    def _check_single_provider_accepted_step(self):
        for step in self:
            if not step.is_provider_accepted_status:
                continue
            others = step.workflow_id.step_ids.filtered(
                lambda s: s.id != step.id and s.is_provider_accepted_status
            )
            if others:
                raise ValidationError(
                    'در هر فرآیند فقط یک مرحله می‌تواند «وضعیت پذیرفته‌شده توسط پذیرنده» باشد.'
                )

    @api.constrains('consumes_quota', 'workflow_id')
    def _check_single_quota_step(self):
        for step in self:
            if not step.consumes_quota:
                continue
            others = step.workflow_id.step_ids.filtered(
                lambda s: s.id != step.id and s.consumes_quota
            )
            if others:
                raise ValidationError(
                    'در هر فرآیند فقط یک مرحله می‌تواند «مصرف سهمیه» باشد.'
                )


class CareWorkflowAction(models.Model):
    _name = 'care.workflow.action'
    _description = 'اکشن مرحله فرآیند'
    _order = 'step_id, sequence, id'

    name = fields.Char(string='نام', required=True)
    step_id = fields.Many2one(
        'care.workflow.step',
        string='مرحله',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    trigger = fields.Selection(
        [
            ('on_enter', 'ورود به مرحله'),
            ('on_exit', 'خروج از مرحله'),
        ],
        string='زمان اجرا',
        required=True,
        default='on_enter',
    )
    action_type = fields.Selection(
        [
            ('assign_team', 'واگذاری تیم'),
            ('assign_user', 'واگذاری شخص'),
            ('email', 'ارسال ایمیل'),
            ('activity', 'ایجاد Activity'),
        ],
        string='نوع اکشن',
        required=True,
    )
    team_id = fields.Many2one('care.team', string='تیم')
    user_id = fields.Many2one('res.users', string='کاربر')
    email_template_id = fields.Many2one('mail.template', string='قالب ایمیل')
    activity_summary = fields.Char(string='عنوان Activity')
    activity_note = fields.Text(string='یادداشت Activity')

    def run_on_request(self, request):
        self.ensure_one()
        if self.action_type == 'assign_team' and self.team_id:
            request.team_id = self.team_id
        elif self.action_type == 'assign_user' and self.user_id:
            request.user_id = self.user_id
            if self.team_id:
                request.team_id = self.team_id
        elif self.action_type == 'email' and self.email_template_id:
            self.email_template_id.send_mail(request.id, force_send=True)
        elif self.action_type == 'activity' and self.user_id:
            request.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.user_id.id,
                summary=self.activity_summary or self.name,
                note=self.activity_note or '',
            )
