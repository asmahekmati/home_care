from odoo import api, fields, models


class CareTeam(models.Model):
    _name = 'care.team'
    _description = 'تیم مراقبت در منزل'
    _order = 'name'

    name = fields.Char(string='نام تیم', required=True, translate=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='رنگ')
    leader_id = fields.Many2one(
        'res.users',
        string='سرپرست تیم',
        ondelete='set null',
    )
    member_ids = fields.Many2many(
        'res.users',
        'care_team_user_rel',
        'team_id',
        'user_id',
        string='اعضا',
    )
    description = fields.Text(string='توضیحات')
    request_count = fields.Integer(
        string='تعداد درخواست',
        compute='_compute_request_count',
    )

    @api.model_create_multi
    def create(self, vals_list):
        teams = super().create(vals_list)
        teams._sync_care_provider_group()
        return teams

    def write(self, vals):
        res = super().write(vals)
        if {'member_ids', 'leader_id', 'active'} & set(vals):
            self._sync_care_provider_group()
        return res

    def unlink(self):
        res = super().unlink()
        self._sync_care_provider_group()
        return res

    @api.model
    def _sync_care_provider_group(self):
        group = self.env.ref('home_care.group_care_provider', raise_if_not_found=False)
        if not group:
            return
        teams = self.search([('active', '=', True)])
        users = teams.member_ids | teams.mapped('leader_id')
        users = users.filtered(lambda u: u.active and not u.share)
        group.user_ids = [(6, 0, users.ids)]

    def _compute_request_count(self):
        request_data = self.env['care.service.request']._read_group(
            [('team_id', 'in', self.ids), ('state', 'not in', ('done', 'cancelled'))],
            ['team_id'],
            ['__count'],
        )
        counts = {team.id: count for team, count in request_data}
        for team in self:
            team.request_count = counts.get(team.id, 0)

    def action_view_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'درخواست‌های تیم',
            'res_model': 'care.service.request',
            'view_mode': 'list,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id},
        }
