# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import _, models


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    def action_register_departure(self):
        super(HrDepartureWizard, self).action_register_departure()
        employee_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_to', '>', self.departure_date),
        ])

        employee_leaves_departure_date = employee_leaves.filtered(lambda leave: leave.date_from.date() <= self.departure_date)
        leave_to_modify = self.env['hr.leave']
        values_to_create = []
        for leave in employee_leaves_departure_date:
            leave_date_to = leave.request_date_to
            leave_to_modify += leave
            values_to_create.append({
                'request_date_to': leave_date_to,
                'state': 'cancel',
                'request_date_from': self.departure_date + timedelta(days=1),
                'holiday_status_id': leave.holiday_status_id.id,
                'employee_id': leave.employee_id.id,
            })
            leave.with_context(leave_skip_state_check=True).message_post(
                body=_('End date has been updated because the employee will leave the company on %(departure_date)s.',
                    departure_date=self.departure_date),
                subtype_xmlid='mail.mt_comment'
            )
        leave_to_modify.with_context(leave_skip_state_check=True).write({'request_date_to': self.departure_date})
        self.env['hr.leave'].with_context(leave_skip_state_check=True).create(values_to_create)
        leaves = employee_leaves - employee_leaves_departure_date
        leave_to_cancel = leaves.filtered(lambda leave: leave.state in ['validate', 'refuse'])
        leave_to_delete = leaves - leave_to_cancel
        cancel_text = _('The employee will leave the company on %(departure_date)s.',
            departure_date=self.departure_date)
        leave_to_cancel._force_cancel(cancel_text, notify_responsibles=False)
        leave_to_delete.with_context(leave_skip_state_check=True).unlink()

        employee_allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id),
            '|',
                ('date_to', '=', False),
                ('date_to', '>', self.departure_date),
        ])
        to_delete = self.env['hr.leave.allocation']
        to_modify = self.env['hr.leave.allocation']
        allocation_text = _('Validity End date has been updated because \
            the employee will leave the company on %(departure_date)s.',
            departure_date=self.departure_date
        )
        for allocation in employee_allocations:
            if allocation.date_from > self.departure_date:
                to_delete |= allocation
            else:
                to_modify |= allocation
                allocation.message_post(body=allocation_text, subtype_xmlid='mail.mt_comment')
        to_delete.write({'state': 'confirm'}) # Needs to be confirmed before it can be unlinked
        to_delete.unlink()
        to_modify.date_to = self.departure_date
