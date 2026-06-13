# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    care_service_request_id = fields.Many2one(
        'care.service.request',
        string='درخواست مراقبت',
        ondelete='set null',
        index=True,
    )
    care_workflow_step_id = fields.Many2one(
        'care.workflow.step',
        string='مرحله فرآیند',
        ondelete='set null',
    )
